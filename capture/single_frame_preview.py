# -*- coding: utf-8 -*-
"""
单帧预览捕获器 - 专门用于快速预览一帧图像

极致优化，只做最必要的操作，避免任何复杂会话管理
"""
import time
import ctypes
from typing import Optional, Union
import numpy as np

# Windows API
from ctypes import wintypes
user32 = ctypes.windll.user32

# 内部模块
from .wgc_backend import WGC_AVAILABLE
from auto_approve.logger_manager import get_logger


class SingleFramePreview:
    """
    单帧预览捕获器 - 专门用于快速预览
    
    设计原则：
    1. 只捕获一帧，不做持续捕获
    2. 最小化会话管理
    3. 避免线程和回调
    4. 快速失败，快速释放
    """
    
    def __init__(self):
        self._logger = get_logger()
        self._session = None
        
        if not WGC_AVAILABLE:
            self._logger.error("Windows Graphics Capture 不可用")
            raise RuntimeError("WGC 库未安装或不兼容")
    
    def capture_single_frame(self, target: Union[str, int], 
                           timeout_sec: float = 0.5) -> Optional[np.ndarray]:
        """
        捕获单帧图像用于预览
        
        Args:
            target: 窗口标题(str)、进程名(str)或窗口句柄(int)
            timeout_sec: 超时时间（秒）
            
        Returns:
            np.ndarray: BGR图像，失败返回None
        """
        start_time = time.time()
        self._logger.info(f"开始单帧捕获，目标: {target}, 超时: {timeout_sec}秒")
        
        try:
            # 1. 快速解析目标
            self._logger.debug("正在解析目标...")
            hwnd = self._resolve_target(target)
            if not hwnd:
                self._logger.warning(f"无法解析目标: {target}")
                return None
            
            self._logger.info(f"解析到窗口句柄: {hwnd}")
            
            # 检查超时
            if time.time() - start_time > timeout_sec:
                self._logger.warning("解析目标超时")
                return None
            
            # 2. 创建最简单的会话
            self._logger.debug("正在创建会话...")
            self._session = self._create_minimal_session(hwnd)
            if not self._session:
                self._logger.warning("创建会话失败")
                return None
            
            self._logger.debug("会话创建成功")
            
            # 检查超时
            if time.time() - start_time > timeout_sec:
                self._logger.warning("创建会话超时")
                self._cleanup()
                return None
            
            # 3. 等待第一帧（调整等待时间）
            remaining_time = timeout_sec - (time.time() - start_time)
            wait_time = max(0.1, min(remaining_time, 0.4))  # 至少100ms，最多400ms
            
            self._logger.debug(f"等待第一帧，超时时间: {wait_time:.2f}秒")
            frame = self._wait_for_first_frame(wait_time)
            
            if frame is not None:
                self._logger.info(f"成功捕获帧，形状: {frame.shape}")
            else:
                self._logger.warning("未获取到帧")
            
            # 4. 立即清理资源
            self._cleanup()
            
            return frame
            
        except Exception as e:
            self._logger.error(f"单帧捕获异常: {e}")
            import traceback
            self._logger.debug(f"异常详情: {traceback.format_exc()}")
            self._cleanup()
            return None
    
    def _resolve_target(self, target: Union[str, int]) -> Optional[int]:
        """快速解析目标句柄"""
        if isinstance(target, int):
            # 直接验证窗口句柄
            if user32.IsWindow(target):
                return target
            return None
        
        if isinstance(target, str):
            # 尝试按标题查找
            hwnd = self._find_window_by_title(target)
            if hwnd:
                return hwnd
            
            # 尝试按进程名查找
            hwnd = self._find_window_by_process(target)
            if hwnd:
                return hwnd
        
        return None
    
    def _find_window_by_title(self, title: str) -> Optional[int]:
        """按标题查找窗口（快速版本）"""
        try:
            # 枚举窗口查找匹配标题
            def enum_callback(hwnd, lParam):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buf = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buf, length + 1)
                        if title.lower() in buf.value.lower():
                            # 找到匹配窗口，存储句柄并停止枚举
                            lParam.value = hwnd
                            return False  # 停止枚举
                return True  # 继续枚举
            
            hwnd_param = wintypes.HWND(0)
            callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            callback = callback_type(enum_callback)
            
            user32.EnumWindows(callback, ctypes.byref(hwnd_param))
            return hwnd_param.value if hwnd_param.value else None
            
        except Exception:
            return None
    
    def _find_window_by_process(self, process_name: str) -> Optional[int]:
        """按进程名查找窗口（快速版本）"""
        try:
            # 简化实现：只找第一个可见窗口
            def enum_callback(hwnd, lParam):
                if user32.IsWindowVisible(hwnd):
                    try:
                        # 获取进程ID
                        pid = wintypes.DWORD()
                        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        
                        # 获取进程名
                        import psutil
                        try:
                            process = psutil.Process(pid.value)
                            if process_name.lower() in process.name().lower():
                                lParam.value = hwnd
                                return False  # 停止枚举
                        except:
                            pass
                    except:
                        pass
                return True  # 继续枚举
            
            hwnd_param = wintypes.HWND(0)
            callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            callback = callback_type(enum_callback)
            
            user32.EnumWindows(callback, ctypes.byref(hwnd_param))
            return hwnd_param.value if hwnd_param.value else None
            
        except ImportError:
            # 如果没有psutil，返回None
            return None
        except Exception:
            return None
    
    def _get_window_title(self, hwnd: int) -> Optional[str]:
        """获取窗口标题"""
        try:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                return buf.value
            return None
        except Exception:
            return None
    
    def _create_minimal_session(self, hwnd: int) -> Optional[object]:
        """创建最小化会话"""
        try:
            import windows_capture
            
            # 获取窗口名称
            window_name = self._get_window_title(hwnd)
            self._logger.debug(f"获取窗口名称: {window_name}")
            
            if not window_name:
                self._logger.warning("无法获取窗口名称，无法创建会话")
                return None
            
            # 构造参数 - WindowsCapture只支持monitor_index或window_name
            session_kwargs = dict(
                cursor_capture=False,
                draw_border=False,
                minimum_update_interval=1000,  # 很长的间隔，避免频繁捕获
                dirty_region=False,
                window_name=window_name
            )
            
            self._logger.debug(f"创建WindowsCapture会话，参数: {session_kwargs}")
            
            # 创建会话
            session = windows_capture.WindowsCapture(**session_kwargs)
            self._logger.debug("会话创建成功")
            
            return session
            
        except Exception as e:
            self._logger.debug(f"创建会话失败: {e}")
            return None
    
    def _wait_for_first_frame(self, timeout: float) -> Optional[np.ndarray]:
        """等待第一帧到达"""
        try:
            # WGC必须启动会话才能捕获帧，即使只需要一帧
            if not hasattr(self._session, 'start') or not hasattr(self._session, 'frame_handler'):
                return None
            
            import threading
            frame_result = [None]
            capture_done = [False]
            capture_started = [False]
            
            def frame_handler(*args, **kwargs):
                self._logger.debug(f"单帧预览收到回调: args={len(args)}, kwargs={kwargs}")
                if not capture_done[0] and len(args) >= 1:
                    try:
                        frame_obj = args[0]
                        control_obj = args[1] if len(args) > 1 else None
                        
                        if frame_obj is not None:
                            frame_result[0] = self._extract_frame(frame_obj)
                            capture_done[0] = True
                            self._logger.debug("成功提取第一帧")
                            
                            # 捕获到第一帧后立即停止
                            if control_obj and hasattr(control_obj, 'stop'):
                                control_obj.stop()
                                self._logger.debug("已停止捕获")
                    except Exception as e:
                        self._logger.debug(f"帧处理失败: {e}")
            
            # 设置帧处理器和关闭处理器
            self._session.frame_handler = frame_handler
            
            def closed_handler():
                self._logger.debug("单帧预览会话已关闭")
            
            self._session.closed_handler = closed_handler
            self._logger.debug("处理器设置完成")
            
            try:
                # 启动捕获会话
                self._session.start()
                capture_started[0] = True
                
                # 等待帧到达或超时
                start_wait = time.time()
                while time.time() - start_wait < timeout and not capture_done[0]:
                    time.sleep(0.01)  # 10ms检查一次
                
                # 如果没有获取到帧，记录调试信息
                if not capture_done[0]:
                    self._logger.debug(f"超时未获取到帧: {timeout:.2f}秒")
                
                return frame_result[0]
                
            except Exception as e:
                self._logger.debug(f"启动捕获失败: {e}")
                return None
            finally:
                # 确保停止捕获
                try:
                    if capture_started[0] and hasattr(self._session, 'stop'):
                        self._session.stop()
                except Exception:
                    pass
                
        except Exception as e:
            self._logger.debug(f"等待第一帧失败: {e}")
            return None
    
    def _extract_frame(self, frame_obj) -> Optional[np.ndarray]:
        """从帧对象提取BGR图像"""
        try:
            self._logger.debug(f"开始提取帧，帧对象类型: {type(frame_obj)}")
            
            # 方法1：使用convert_to_bgr方法（最可靠）
            if hasattr(frame_obj, 'convert_to_bgr'):
                self._logger.debug("尝试使用convert_to_bgr方法")
                try:
                    result = frame_obj.convert_to_bgr()
                    if result is not None:
                        # 检查结果类型
                        if hasattr(result, 'shape'):
                            self._logger.debug(f"convert_to_bgr成功，结果形状: {result.shape}")
                            return result
                        elif hasattr(result, 'frame_buffer'):
                            # 结果可能是另一个frame对象
                            buffer = result.frame_buffer
                            if buffer is not None and hasattr(buffer, 'shape'):
                                self._logger.debug(f"通过frame_buffer获取图像，形状: {buffer.shape}")
                                return buffer.copy()
                        else:
                            self._logger.debug(f"convert_to_bgr返回了未知类型: {type(result)}")
                    else:
                        self._logger.debug("convert_to_bgr返回None")
                except Exception as e:
                    self._logger.debug(f"convert_to_bgr方法失败: {e}")
            
            # 方法2：尝试访问frame对象的属性
            for attr_name in ['frame_buffer', 'buffer', 'data', 'image']:
                if hasattr(frame_obj, attr_name):
                    self._logger.debug(f"尝试访问{attr_name}属性")
                    try:
                        attr_value = getattr(frame_obj, attr_name)
                        if attr_value is not None:
                            self._logger.debug(f"{attr_name}类型: {type(attr_value)}")
                            
                            # 如果是numpy数组
                            if hasattr(attr_value, 'shape'):
                                buffer = attr_value
                                if len(buffer.shape) == 3:
                                    if buffer.shape[2] == 3:  # BGR
                                        self._logger.debug("成功提取BGR格式")
                                        return buffer.copy()
                                    elif buffer.shape[2] == 4:  # BGRA
                                        self._logger.debug("成功提取BGRA格式，转换为BGR")
                                        return buffer[:, :, :3].copy()
                                else:
                                    self._logger.debug(f"buffer维度不符合预期: {buffer.shape}")
                            else:
                                self._logger.debug(f"{attr_name}没有shape属性")
                        else:
                            self._logger.debug(f"{attr_name}为None")
                    except Exception as e:
                        self._logger.debug(f"访问{attr_name}失败: {e}")
            
            # 方法3：尝试获取尺寸信息并创建临时图像
            try:
                if hasattr(frame_obj, 'width') and hasattr(frame_obj, 'height'):
                    width = frame_obj.width
                    height = frame_obj.height
                    self._logger.debug(f"获取到帧尺寸: {width}x{height}")
                    
                    # 如果有save_to_file方法，先保存再读取
                    if hasattr(frame_obj, 'save_to_file'):
                        import tempfile
                        import os
                        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                            temp_path = tmp_file.name
                        
                        try:
                            frame_obj.save_to_file(temp_path)
                            import cv2
                            img = cv2.imread(temp_path)
                            if img is not None:
                                self._logger.debug(f"通过临时文件成功读取图像，形状: {img.shape}")
                                return img
                        finally:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
            except Exception as e:
                self._logger.debug(f"临时文件方法失败: {e}")
            
            self._logger.debug("所有提取方法都失败")
            return None
            
        except Exception as e:
            self._logger.debug(f"帧提取异常: {e}")
            import traceback
            self._logger.debug(f"异常详情: {traceback.format_exc()}")
            return None
    
    def _cleanup(self):
        """清理资源"""
        try:
            if self._session:
                if hasattr(self._session, 'stop'):
                    self._session.stop()
                if hasattr(self._session, 'close'):
                    self._session.close()
                self._session = None
        except Exception:
            pass
    
    def __del__(self):
        self._cleanup()


# 全局实例
_global_preview_capturer: Optional[SingleFramePreview] = None


def get_single_frame_preview() -> SingleFramePreview:
    """获取全局单帧预览捕获器"""
    global _global_preview_capturer
    if _global_preview_capturer is None:
        _global_preview_capturer = SingleFramePreview()
    return _global_preview_capturer
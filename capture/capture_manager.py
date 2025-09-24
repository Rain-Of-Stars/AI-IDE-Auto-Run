# -*- coding: utf-8 -*-
"""
统一捕获管理器

提供高级的窗口和显示器捕获接口，封装 WGC 会话管理、
最小化窗口处理、异常恢复等功能。
"""

from __future__ import annotations
import ctypes
import time
from typing import Optional, Union, Tuple
import numpy as np

# Windows API
from ctypes import wintypes
user32 = ctypes.windll.user32

# 内部模块
from .wgc_backend import WGCCaptureSession, WGC_AVAILABLE
from .monitor_utils import enum_windows, get_monitor_handles, find_window_by_process
from .shared_frame_cache import get_shared_frame_cache
from .cache_manager import get_global_cache_manager
from auto_approve.logger_manager import get_logger

# Windows API 常量
SW_SHOWNOACTIVATE = 4
SW_MINIMIZE = 6
SWP_NOACTIVATE = 0x0010
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004


class CaptureManager:
    """
    统一捕获管理器

    提供简化的窗口/显示器捕获接口，自动处理：
    - 窗口查找和验证
    - 最小化窗口的无感恢复
    - WGC 会话生命周期管理
    - 异常处理和重试机制
    """

    def __init__(self):
        self._logger = get_logger()
        self._session: Optional[WGCCaptureSession] = None
        self._target_hwnd: Optional[int] = None
        self._target_hmonitor: Optional[int] = None
        self._was_minimized = False
        self._restore_minimized = True

        # 性能配置
        self._target_fps = 30
        self._include_cursor = False
        self._border_required = False
        
        # 性能优化缓存
        self._last_minimize_check = 0.0
        self._minimize_check_interval = 1.0  # 减少检查频率

        if not WGC_AVAILABLE:
            self._logger.error("Windows Graphics Capture 不可用")
            raise RuntimeError("WGC 库未安装或不兼容")

        # 共享帧缓存
        self._frame_cache = get_shared_frame_cache()
        self._global_cache_manager = get_global_cache_manager()

    def open_window_fast(self, target: Union[str, int], partial_match: bool = True) -> bool:
        """
        快速打开窗口捕获（跳过复杂验证，用于性能敏感场景）

        Args:
            target: 窗口标题(str)、进程名(str)或窗口句柄(int)
            partial_match: 字符串匹配时是否允许部分匹配

        Returns:
            bool: 是否成功打开
        """
        try:
            # 快速解析目标
            hwnd = self._resolve_window_target(target, partial_match)
            if not hwnd:
                return False

            # 快速创建WGC会话
            self._session = WGCCaptureSession.from_hwnd(hwnd)
            
            # 禁用健康检查和日志以提高性能
            if hasattr(self._session, '_health_check_enabled'):
                self._session._health_check_enabled = False
            if hasattr(self._session, '_logger'):
                # 禁用日志输出
                import logging
                self._session._logger.setLevel(logging.CRITICAL)

            self._target_hwnd = hwnd
            self._capture_mode = 'window'
            
            # 快速启动，使用最低帧率
            return self._session.start(target_fps=1, include_cursor=False, border_required=False)

        except Exception:
            # 静默失败
            return False

    def open_window(self, target: Union[str, int], partial_match: bool = True,
                    async_init: bool = True, timeout: float = 0.5) -> bool:
        """
        打开窗口捕获

        Args:
            target: 窗口标题(str)、进程名(str)或窗口句柄(int)
            partial_match: 字符串匹配时是否允许部分匹配
            async_init: 是否异步初始化（跳过帧验证，避免阻塞）
            timeout: 初始化超时时间（秒），防止长时间卡死

        Returns:
            bool: 是否成功打开
        """
        import time
        start_time = time.time()

        try:
            # 解析目标
            hwnd = self._resolve_window_target(target, partial_match)
            if not hwnd:
                self._logger.error(f"无法找到目标窗口: {target}")
                return False

            # 验证窗口
            if not user32.IsWindow(hwnd):
                self._logger.error(f"无效的窗口句柄: {hwnd}")
                return False

            # 检查超时
            if time.time() - start_time > timeout:
                self._logger.error(f"窗口捕获初始化超时: {timeout}s")
                return False

            # 关闭现有会话
            self.close()

            # 创建新会话
            self._session = WGCCaptureSession.from_hwnd(hwnd)
            self._target_hwnd = hwnd

            # 检查超时
            if time.time() - start_time > timeout:
                self._logger.error(f"窗口捕获初始化超时: {timeout}s")
                self._session = None
                self._target_hwnd = None
                return False

            # 启动捕获
            success = self._session.start(
                target_fps=self._target_fps,
                include_cursor=self._include_cursor,
                border_required=self._border_required
            )

            if not success:
                self._logger.error(f"窗口捕获启动失败: hwnd={hwnd}")
                self._session = None
                self._target_hwnd = None
                return False

            # 启动后快速验证是否有帧输出，避免卡在"初始化中"
            # 深度优化：完全跳过同步验证，实现真正的异步初始化
            if async_init:
                self._logger.info("异步初始化模式：完全跳过帧验证，实现真正的异步")
                self._logger.info(f"窗口捕获已启动: hwnd={hwnd}, title='{self._get_window_title(hwnd)}'")
                return True
            # 同步模式：也大幅减少验证时间
            remaining_time = timeout - (time.time() - start_time)
            if remaining_time <= 0.05:  # 减少到50ms
                self._logger.warning("窗口捕获初始化接近超时，跳过帧验证")
                self._logger.info(f"窗口捕获已启动: hwnd={hwnd}, title='{self._get_window_title(hwnd)}'")
                return True

            try:
                # 大幅减少验证超时时间，最多50ms
                verify_timeout = min(0.05, remaining_time)  # 从100ms减少到50ms
                test_frame = self._session.wait_for_frame(timeout=verify_timeout)
                if test_frame is None:
                    self._logger.debug("窗口捕获启动后暂无帧输出，跳过验证")
                    # 完全跳过验证，不阻塞
                else:
                    self._logger.debug("窗口捕获帧验证成功")
            except Exception as e:
                self._logger.debug(f"窗口捕获验证帧失败: {e}，跳过验证")
                # 完全跳过验证，不阻塞

            # 无论验证如何，都认为启动成功
            self._logger.info(f"窗口捕获已启动: hwnd={hwnd}, title='{self._get_window_title(hwnd)}'")
            return True

        except Exception as e:
            self._logger.error(f"打开窗口捕获失败: {e}")
            # 确保清理资源
            if hasattr(self, '_session') and self._session:
                try:
                    self._session.close()
                except:
                    pass
                self._session = None
            self._target_hwnd = None
            return False

    def open_monitor(self, target: Union[int, str]) -> bool:
        """
        打开显示器捕获

        Args:
            target: 显示器索引(int)或显示器句柄(int)

        Returns:
            bool: 是否成功打开
        """
        try:
            # 解析显示器目标
            hmonitor = self._resolve_monitor_target(target)
            if not hmonitor:
                # 获取显示器信息用于错误提示
                from .monitor_utils import get_all_monitors_info
                monitors_info = get_all_monitors_info()
                self._logger.error(f"无法找到目标显示器: {target}")
                self._logger.error(f"当前系统有 {len(monitors_info)} 个显示器，有效索引: 0-{len(monitors_info)-1}")
                return False

            # 关闭现有会话
            self.close()

            # 创建新会话
            self._session = WGCCaptureSession.from_monitor(hmonitor)
            self._target_hmonitor = hmonitor

            # 启动捕获
            success = self._session.start(
                target_fps=self._target_fps,
                include_cursor=self._include_cursor,
                border_required=self._border_required
            )

            if not success:
                self._logger.error(f"显示器捕获启动失败: hmonitor={hmonitor}")
                self._session = None
                self._target_hmonitor = None
                return False

            # 深度优化：大幅减少显示器捕获的验证时间
            try:
                test_frame = self._session.wait_for_frame(timeout=0.05)  # 从100ms减少到50ms
                if test_frame is None:
                    self._logger.debug("显示器捕获启动后暂无帧输出，跳过验证")
                    # 完全跳过验证，不阻塞
            except Exception as e:
                self._logger.debug(f"显示器捕获验证帧失败: {e}，跳过验证")
                # 完全跳过验证，不阻塞

            self._logger.info(f"显示器捕获已启动: hmonitor={hmonitor}")
            return True

        except Exception as e:
            self._logger.error(f"打开显示器捕获失败: {e}")
            return False

    def capture_frame(self, restore_after_capture: bool = False) -> Optional[np.ndarray]:
        """
        捕获一帧图像

        Args:
            restore_after_capture: 捕获后是否恢复窗口最小化状态

        Returns:
            np.ndarray: BGR 图像，失败返回 None
        """
        if not self._session:
            self._logger.error("捕获会话未初始化")
            return None

        try:
            # 处理最小化窗口
            if self._target_hwnd and self._restore_minimized:
                self._handle_minimized_window()

            # 捕获帧
            frame = self._session.grab()

            # 恢复最小化状态
            if restore_after_capture and self._was_minimized:
                self._restore_window_state()

            return frame

        except Exception as e:
            self._logger.error(f"捕获帧失败: {e}")
            return None

    def capture_frame_fast(self, restore_after_capture: bool = False) -> Optional[np.ndarray]:
        """
        快速捕获一帧图像（极致性能优化版本）

        Args:
            restore_after_capture: 捕获后是否恢复窗口最小化状态

        Returns:
            np.ndarray: BGR 图像，失败返回 None
        """
        if not self._session:
            return None

        try:
            # 直接使用快速捕获，跳过所有检查
            frame = self._session.grab_fast()
            return frame

        except Exception:
            # 静默失败，不记录日志
            return None

    def wait_for_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """等待新帧（非阻塞优化版本）"""
        if not self._session:
            return None
        
        # 使用更短的超时以避免长时间阻塞
        safe_timeout = min(timeout, 0.05)  # 最多阻塞50ms
        return self._session.wait_for_frame(safe_timeout)

    def get_shared_frame(self, user_id: str, session_type: str = "unknown") -> Optional[np.ndarray]:
        """
        从共享缓存获取帧（内存共享，避免拷贝）

        Args:
            user_id: 使用者ID（如"preview", "detection", "test"等）
            session_type: 会话类型（用于统计和管理）

        Returns:
            np.ndarray: BGR图像数据的视图，如果缓存无效则返回None
        """
        if not self._session:
            return None

        # 注册用户会话（如果尚未注册）
        self._global_cache_manager.register_user(user_id, session_type, self._target_hwnd)

        # 更新访问时间
        self._global_cache_manager.update_user_access(user_id)

        return self._session.get_shared_frame(user_id)

    def release_shared_frame(self, user_id: str) -> None:
        """
        释放共享帧的使用者引用

        当预览窗口关闭或检测完成时调用此方法

        Args:
            user_id: 使用者ID
        """
        if self._session:
            self._session.release_shared_frame(user_id)

        # 从全局缓存管理器注销用户
        self._global_cache_manager.unregister_user(user_id)

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息"""
        return self._global_cache_manager.get_statistics()

    def configure(self, fps: int = 30, include_cursor: bool = False,
                  border_required: bool = False, restore_minimized: bool = True):
        """
        配置捕获参数

        Args:
            fps: 目标帧率
            include_cursor: 是否包含鼠标光标
            border_required: 是否需要窗口边框
            restore_minimized: 是否自动恢复最小化窗口
        """
        self._target_fps = max(1, min(fps, 60))
        self._include_cursor = include_cursor
        self._border_required = border_required
        self._restore_minimized = restore_minimized

        # 如果会话已启动，需要重启以应用新配置
        if self._session:
            if self._target_hwnd:
                hwnd = self._target_hwnd
                self.close()
                self.open_window(hwnd)
            elif self._target_hmonitor:
                hmonitor = self._target_hmonitor
                self.close()
                self.open_monitor(hmonitor)

    def get_stats(self) -> dict:
        """获取捕获统计信息"""
        if self._session:
            stats = self._session.get_stats()
            stats.update({
                'target_hwnd': self._target_hwnd,
                'target_hmonitor': self._target_hmonitor,
                'was_minimized': self._was_minimized
            })
            return stats
        return {}

    def close(self):
        """关闭捕获会话"""
        if self._session:
            self._session.close()
            self._session = None

        # 恢复窗口状态
        if self._was_minimized and self._target_hwnd:
            self._restore_window_state()

        self._target_hwnd = None
        self._target_hmonitor = None
        self._was_minimized = False

    def _resolve_window_target(self, target: Union[str, int], partial_match: bool) -> Optional[int]:
        """解析窗口目标为 HWND"""
        if isinstance(target, int):
            return target

        if isinstance(target, str):
            # 先尝试按标题查找（本地实现，避免依赖已移除的外部函数）
            def _find_window_by_title_local(title: str, allow_partial: bool = True) -> Optional[int]:
                try:
                    if not title:
                        return None
                    title_l = title.lower()
                    for hwnd, t in enum_windows():
                        tl = (t or "").lower()
                        if allow_partial:
                            if title_l in tl:
                                return hwnd
                        else:
                            if title_l == tl:
                                return hwnd
                    return None
                except Exception:
                    return None

            hwnd = _find_window_by_title_local(target, partial_match)
            if hwnd:
                return hwnd

            # 再尝试按进程名查找
            hwnd = find_window_by_process(target, partial_match)
            if hwnd:
                return hwnd

        return None

    def _resolve_monitor_target(self, target: Union[int, str]) -> Optional[int]:
        """解析显示器目标为 HMONITOR"""
        if isinstance(target, int):
            # 如果是小整数，当作索引处理
            if target < 100:
                monitors = get_monitor_handles()
                if 0 <= target < len(monitors):
                    return monitors[target]
                else:
                    # 提供详细的错误信息
                    self._logger.error(f"显示器索引 {target} 无效。当前系统有 {len(monitors)} 个显示器，有效索引范围: 0-{len(monitors)-1}")
                    if len(monitors) > 0:
                        self._logger.info(f"建议使用索引 0 (主显示器)")
                    return None
            else:
                # 大整数当作句柄处理
                return target

        return None

    def _handle_minimized_window(self):
        """处理最小化窗口"""
        if not self._target_hwnd:
            return

        try:
            # 检查是否最小化
            if user32.IsIconic(self._target_hwnd):
                if not self._was_minimized:
                    self._was_minimized = True
                    self._logger.debug(f"检测到最小化窗口: {self._target_hwnd}")

                # 无感恢复（不激活）
                user32.ShowWindow(self._target_hwnd, SW_SHOWNOACTIVATE)

        except Exception as e:
            self._logger.warning(f"处理最小化窗口失败: {e}")

    def _restore_window_state(self):
        """恢复窗口最小化状态"""
        if self._was_minimized and self._target_hwnd:
            try:
                user32.ShowWindow(self._target_hwnd, SW_MINIMIZE)
                self._was_minimized = False
                self._logger.debug(f"已恢复窗口最小化状态: {self._target_hwnd}")
            except Exception as e:
                self._logger.warning(f"恢复窗口状态失败: {e}")

    def _get_window_title(self, hwnd: int) -> str:
        """获取窗口标题"""
        try:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                return buf.value
        except Exception:
            pass
        return ""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

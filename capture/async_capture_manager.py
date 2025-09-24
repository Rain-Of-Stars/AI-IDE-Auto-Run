# -*- coding: utf-8 -*-
"""
异步窗口捕获管理器

提供完全非阻塞的窗口捕获接口，使用Qt的信号槽机制和后台线程
to确保UI始终保持响应状态。
"""

from __future__ import annotations
import time
import threading
import queue
from typing import Optional, Union, Callable, Dict, Any
from dataclasses import dataclass
import numpy as np

from PySide6.QtCore import QObject, Signal, QThread, QTimer, Qt
from PySide6.QtWidgets import QApplication

# 导入捕获相关模块
from .capture_manager import CaptureManager
from .wgc_backend import WGC_AVAILABLE
from auto_approve.logger_manager import get_logger


@dataclass
class CaptureRequest:
    """捕获请求数据包"""
    request_type: str  # 'frame', 'open_window', 'open_monitor', 'close'
    target: Optional[Union[str, int]] = None
    partial_match: bool = True
    async_init: bool = True
    timeout: float = 3.0
    callback: Optional[Callable] = None
    user_data: Optional[Dict[str, Any]] = None


@dataclass 
class CaptureResult:
    """捕获结果数据包"""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    request: Optional[CaptureRequest] = None


class AsyncCaptureWorker(QThread):
    """异步捕获工作线程"""
    
    # 工作线程信号
    capture_started = Signal(str, bool)  # target, success
    frame_ready = Signal(np.ndarray)      # frame data
    capture_error = Signal(str, str)      # operation, error
    stats_updated = Signal(dict)          # statistics
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        self._capture_manager = CaptureManager()
        self._request_queue = queue.Queue()
        self._result_queue = queue.Queue()
        self._running = False
        self._frame_request_pending = False
        
        # 性能配置
        self._target_fps = 30
        self._frame_interval = 1.0 / self._target_fps
        self._last_frame_time = 0
        
    def submit_request(self, request: CaptureRequest) -> bool:
        """提交捕获请求到工作队列"""
        try:
            self._request_queue.put(request, timeout=0.1)
            return True
        except queue.Full:
            self.logger.warning("捕获请求队列已满")
            return False
    
    def get_result(self) -> Optional[CaptureResult]:
        """获取处理结果"""
        try:
            return self._result_queue.get_nowait()
        except queue.Empty:
            return None
    
    def stop_worker(self):
        """停止工作线程"""
        self._running = False
        # 发送停止信号
        stop_request = CaptureRequest(request_type='close')
        try:
            self._request_queue.put(stop_request, timeout=0.1)
        except queue.Full:
            pass
    
    def run(self):
        """工作线程主循环"""
        self._running = True
        self.logger.info("异步捕获工作线程已启动")
        
        try:
            while self._running:
                try:
                    # 处理捕获请求（非阻塞）
                    request = self._request_queue.get(timeout=0.01)
                    
                    if request.request_type == 'close':
                        break
                    
                    self._process_request(request)
                    
                except queue.Empty:
                    # 没有新请求，继续处理帧捕获
                    if self._frame_request_pending:
                        self._capture_frame()
                
                # 控制帧率
                current_time = time.time()
                if current_time - self._last_frame_time >= self._frame_interval:
                    if self._frame_request_pending:
                        self._capture_frame()
                        self._last_frame_time = current_time
                
                # 更新统计信息
                if current_time % 1.0 < 0.01:  # 每秒更新一次
                    stats = self._capture_manager.get_stats()
                    self.stats_updated.emit(stats)
                    
        except Exception as e:
            self.logger.error(f"异步捕获工作线程异常: {e}")
            self.capture_error.emit('worker', str(e))
        finally:
            # 清理资源
            try:
                self._capture_manager.close()
            except:
                pass
            self.logger.info("异步捕获工作线程已停止")
    
    def _process_request(self, request: CaptureRequest):
        """处理捕获请求"""
        try:
            if request.request_type == 'open_window':
                self._handle_open_window(request)
            elif request.request_type == 'open_monitor':
                self._handle_open_monitor(request)
            elif request.request_type == 'frame':
                self._frame_request_pending = True
            elif request.request_type == 'close':
                self._handle_close()
                
        except Exception as e:
            self.logger.error(f"处理捕获请求失败: {e}")
            result = CaptureResult(
                success=False,
                error=str(e),
                request=request
            )
            try:
                self._result_queue.put(result, timeout=0.1)
            except queue.Full:
                pass
            
            if request.callback:
                try:
                    request.callback(result)
                except:
                    pass
    
    def _handle_open_window(self, request: CaptureRequest):
        """处理打开窗口请求"""
        try:
            success = self._capture_manager.open_window(
                target=request.target,
                partial_match=request.partial_match,
                async_init=request.async_init,
                timeout=request.timeout
            )
            
            result = CaptureResult(success=success, request=request)
            
            # 发送信号
            if success:
                self.capture_started.emit(str(request.target), True)
            else:
                self.capture_error.emit('open_window', f"Failed to open window: {request.target}")
            
        except Exception as e:
            result = CaptureResult(success=False, error=str(e), request=request)
            self.capture_error.emit('open_window', str(e))
        
        # 通知结果
        try:
            self._result_queue.put(result, timeout=0.1)
        except queue.Full:
            pass
            
        if request.callback:
            try:
                request.callback(result)
            except:
                pass
    
    def _handle_open_monitor(self, request: CaptureRequest):
        """处理打开显示器请求"""
        try:
            success = self._capture_manager.open_monitor(request.target)
            result = CaptureResult(success=success, request=request)
            
            if success:
                self.capture_started.emit(str(request.target), True)
            else:
                self.capture_error.emit('open_monitor', f"Failed to open monitor: {request.target}")
                
        except Exception as e:
            result = CaptureResult(success=False, error=str(e), request=request)
            self.capture_error.emit('open_monitor', str(e))
        
        try:
            self._result_queue.put(result, timeout=0.1)
        except queue.Full:
            pass
            
        if request.callback:
            try:
                request.callback(result)
            except:
                pass
    
    def _handle_close(self):
        """处理关闭请求"""
        try:
            self._capture_manager.close()
            self._frame_request_pending = False
            self.logger.info("捕获会话已关闭")
        except Exception as e:
            self.logger.error(f"关闭捕获会话失败: {e}")
    
    def _capture_frame(self):
        """捕获帧"""
        try:
            frame = self._capture_manager.capture_frame()
            if frame is not None:
                self.frame_ready.emit(frame)
                
                # 添加结果到队列
                result = CaptureResult(
                    success=True,
                    data=frame
                )
                try:
                    self._result_queue.put(result, timeout=0.01)
                except queue.Full:
                    pass  # 结果队列满，跳过
                    
        except Exception as e:
            self.logger.error(f"捕获帧失败: {e}")
            self.capture_error.emit('capture', str(e))


class AsyncCaptureManager(QObject):
    """异步捕获管理器 - 提供完全非阻塞的捕获接口"""
    
    # 捕获状态信号
    capture_started = Signal(str, bool)    # target, success
    capture_stopped = Signal()              # 捕获已停止
    frame_ready = Signal(np.ndarray)        # 新帧可用
    capture_error = Signal(str, str)        # operation, error_message
    stats_updated = Signal(dict)           # 统计信息更新
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        
        # 创建工作线程
        self._worker = AsyncCaptureWorker()
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)
        
        # 连接信号
        self._connect_worker_signals()
        
        # 状态管理
        self._is_capturing = False
        self._current_target = None
        self._frame_request_timer = QTimer()
        self._frame_request_timer.timeout.connect(self._request_frame)
        
        # 配置参数
        self._fps = 30
        self._frame_interval = 1000 // self._fps  # 毫秒
        
        # 启动工作线程
        self._worker_thread.started.connect(self._on_worker_started)
        self._worker_thread.start()
    
    def _connect_worker_signals(self):
        """连接工作线程信号"""
        self._worker.capture_started.connect(self._on_capture_started)
        self._worker.frame_ready.connect(self._on_frame_ready)
        self._worker.capture_error.connect(self._on_capture_error)
        self._worker.stats_updated.connect(self.stats_updated)
    
    def _on_worker_started(self):
        """工作线程启动时的处理"""
        self.logger.debug("异步捕获工作线程已启动")
    
    def _on_capture_started(self, target: str, success: bool):
        """捕获开始时"""
        self.logger.debug(f"捕获启动: {target}, 成功: {success}")
        if success:
            self._is_capturing = True
            self._current_target = target
            self.capture_started.emit(target, True)
            
            # 开始定时请求帧
            self._frame_request_timer.start(self._frame_interval)
        else:
            self.capture_started.emit(target, False)
    
    def _on_frame_ready(self, frame: np.ndarray):
        """帧准备好时"""
        self.frame_ready.emit(frame)
    
    def _on_capture_error(self, operation: str, error: str):
        """捕获错误时"""
        self.logger.error(f"捕获错误 [{operation}]: {error}")
        self.capture_error.emit(operation, error)
    
    def _request_frame(self):
        """请求捕获帧"""
        request = CaptureRequest(request_type='frame')
        self._worker.submit_request(request)
    
    def open_window_capture(self, target: Union[str, int], 
                           partial_match: bool = True,
                           async_init: bool = True,
                           timeout: float = 3.0,
                           callback: Optional[Callable] = None) -> bool:
        """
        异步打开窗口捕获
        
        Args:
            target: 窗口标题、进程名或窗口句柄
            partial_match: 是否允许部分匹配
            async_init: 是否异步初始化
            timeout: 超时时间
            callback: 结果回调函数
            
        Returns:
            bool: 请求是否已提交成功
        """
        request = CaptureRequest(
            request_type='open_window',
            target=target,
            partial_match=partial_match,
            async_init=async_init,
            timeout=timeout,
            callback=callback
        )
        return self._worker.submit_request(request)
    
    def open_monitor_capture(self, target: Union[int, str],
                           callback: Optional[Callable] = None) -> bool:
        """
        异步打开显示器捕获
        
        Args:
            target: 显示器索引或句柄
            callback: 结果回调函数
            
        Returns:
            bool: 请求是否已提交成功
        """
        request = CaptureRequest(
            request_type='open_monitor',
            target=target,
            callback=callback
        )
        return self._worker.submit_request(request)
    
    def stop_capture(self) -> bool:
        """停止捕获"""
        if not self._is_capturing:
            return True
            
        # 停止帧请求定时器
        self._frame_request_timer.stop()
        
        # 提交停止请求
        request = CaptureRequest(request_type='close')
        success = self._worker.submit_request(request)
        
        if success:
            self._is_capturing = False
            self._current_target = None
            self.capture_stopped.emit()
        
        return success
    
    def set_fps(self, fps: int):
        """设置捕获帧率"""
        self._fps = max(1, min(fps, 60))
        self._frame_interval = 1000 // self._fps
        
        # 如果正在捕获，重启定时器
        if self._frame_request_timer.isActive():
            self._frame_request_timer.stop()
            self._frame_request_timer.start(self._frame_interval)
    
    def configure_capture(self, fps: int = 30, include_cursor: bool = False,
                         border_required: bool = False, restore_minimized: bool = True):
        """配置捕获参数"""
        # 注意：这个设置需要重新启动捕获才能生效
        # 在实际实现中，我们需要将这些参数传递给工作线程
        pass
    
    def is_capturing(self) -> bool:
        """是否正在捕获"""
        return self._is_capturing
    
    def get_current_target(self) -> Optional[str]:
        """获取当前捕获目标"""
        return self._current_target
    
    def get_result(self) -> Optional[CaptureResult]:
        """获取最新的处理结果"""
        return self._worker.get_result()
    
    def stop(self):
        """完全停止异步管理器"""
        self.logger.info("正在停止异步捕获管理器...")
        
        # 停止捕获
        if self._is_capturing:
            self.stop_capture()
        
        # 停止帧定时器
        if self._frame_request_timer.isActive():
            self._frame_request_timer.stop()
        
        # 停止工作线程
        if hasattr(self, '_worker'):
            self._worker.stop_worker()
        
        # 等待线程结束
        if self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(5000)  # 最多等待5秒
        
        self.logger.info("异步捕获管理器已停止")
    
    def __del__(self):
        """析构函数"""
        try:
            if hasattr(self, '_worker_thread') and self._worker_thread.isRunning():
                self.stop()
        except:
            pass


# 全局实例
_global_async_manager: Optional[AsyncCaptureManager] = None


def get_async_capture_manager() -> AsyncCaptureManager:
    """获取全局异步捕获管理器"""
    global _global_async_manager
    if _global_async_manager is None:
        _global_async_manager = AsyncCaptureManager()
    return _global_async_manager


def start_async_window_capture(target: Union[str, int], 
                              partial_match: bool = True,
                              callback: Optional[Callable] = None) -> bool:
    """便捷函数：异步启动窗口捕获"""
    manager = get_async_capture_manager()
    return manager.open_window_capture(target, partial_match, callback=callback)


def stop_async_capture() -> bool:
    """便捷函数：停止异步捕获"""
    manager = get_async_capture_manager()
    return manager.stop_capture()
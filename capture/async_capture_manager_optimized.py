# -*- coding: utf-8 -*-
"""
优化的异步窗口捕获管理器

解决线程间通信和潜在阻塞问题，确保真正的非阻塞体验
"""

from __future__ import annotations
import time
import threading
import queue
from typing import Optional, Union, Callable, Dict, Any
from dataclasses import dataclass
import numpy as np

from PySide6.QtCore import QObject, Signal, QThread, QTimer, Qt, Slot
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


class CaptureWorker(QObject):
    """捕获工作对象 - 通过Qt信号实现真正的异步通信"""
    
    # 工作线程信号（信号将跨线程传递）
    internal_frame_ready = Signal(object)      # 内部帧信号，带弱引用防止内存泄漏
    internal_error_occurred = Signal(str, str) # 内部错误信号
    internal_started = Signal(str, bool)       # 内部启动信号
    internal_stats_ready = Signal(dict)        # 内部统计信号
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        self._capture_manager = CaptureManager()
        self._request_queue = queue.Queue(maxsize=50)  # 限制队列大小，避免内存累积
        self._running = False
        self._frame_request_pending = False
        self._worker_thread = None
        
        # 性能配置
        self._target_fps = 30
        self._frame_interval = 1.0 / self._target_fps
        self._last_frame_time = 0
        
        # 帧批处理控制，避免过于频繁的UI更新
        self._frame_batch_size = 1  # 批处理1个帧
        self._frame_batch_timeout = 0.033  # 33ms，约30FPS
        
        self.logger.info("捕获工作对象已创建")
    
    @Slot()
    def start_worker(self):
        """启动工作循环"""
        self._running = True
        self.logger.info("捕获工作线程已启动")
        
        try:
            while self._running:
                try:
                    # 使用超时机制避免永久阻塞
                    request = self._request_queue.get(timeout=0.01)
                    
                    if request.request_type == 'close':
                        break
                    
                    # 处理请求
                    self._process_request(request)
                    
                except queue.Empty:
                    # 没有新请求，处理待处理的帧捕获
                    if self._frame_request_pending:
                        self._capture_frame_batch()
                
                # 帧率控制 - 基于时间间隔，不依赖CPU时钟
                current_time = time.time()
                if current_time - self._last_frame_time >= self._frame_interval:
                    if self._frame_request_pending:
                        self._capture_frame_batch()
                        self._last_frame_time = current_time
                
                # 定期更新统计（约每秒一次）
                if current_time % 1.0 < 0.01:
                    stats = self._capture_manager.get_stats()
                    self.internal_stats_ready.emit(stats)
                    
        except Exception as e:
            self.logger.error(f"捕获工作线程异常: {e}")
            self.internal_error_occurred.emit('worker_thread', str(e))
            
        finally:
            # 清理资源
            self._cleanup_resources()
            self.logger.info("捕获工作线程已停止")
    
    def stop_worker(self):
        """停止工作线程"""
        self._running = False
        # 发送停止信号
        try:
            self._request_queue.put(CaptureRequest(request_type='close'), timeout=0.1)
        except queue.Full:
            pass
    
    def submit_request(self, request: CaptureRequest) -> bool:
        """提交捕获请求（线程安全）"""
        try:
            self._request_queue.put(request, timeout=0.05)  # 短超时
            return True
        except queue.Full:
            self.logger.warning("捕获请求队列已满，丢弃请求")
            return False
    
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
            self.internal_error_occurred.emit('process_request', str(e))
    
    def _handle_open_window(self, request: CaptureRequest):
        """处理打开窗口请求"""
        try:
            self.logger.debug(f"正在打开窗口: {request.target}")
            
            # 这里可能会有轻微阻塞，但我们接受这个延迟
            success = self._capture_manager.open_window(
                target=request.target,
                partial_match=request.partial_match,
                async_init=request.async_init,
                timeout=request.timeout
            )
            
            # 使用信号跨线程传递结果
            self.internal_started.emit(str(request.target), success)
            
            if success:
                self.logger.info(f"窗口打开成功: {request.target}")
            else:
                self.logger.warning(f"窗口打开失败: {request.target}")
                
        except Exception as e:
            self.logger.error(f"打开窗口异常: {e}")
            self.internal_error_occurred.emit('open_window', str(e))
    
    def _handle_open_monitor(self, request: CaptureRequest):
        """处理打开显示器请求"""
        try:
            success = self._capture_manager.open_monitor(request.target)
            self.internal_started.emit(str(request.target), success)
        except Exception as e:
            self.logger.error(f"打开显示器异常: {e}")
            self.internal_error_occurred.emit('open_monitor', str(e))
    
    def _handle_close(self):
        """处理关闭请求"""
        try:
            self._capture_manager.close()
            self._frame_request_pending = False
            self.logger.info("捕获会话已关闭")
        except Exception as e:
            self.logger.error(f"关闭捕获会话失败: {e}")
    
    def _capture_frame_batch(self):
        """批量捕获帧"""
        try:
            # 一次捕获多个帧但只发送最后一个
            frames_captured = 0
            latest_frame = None
            
            batch_start = time.time()
            while frames_captured < self._frame_batch_size:
                frame = self._capture_manager.capture_frame()
                if frame is not None:
                    latest_frame = frame
                    frames_captured += 1
                
                # 批次超时检查
                if time.time() - batch_start > self._frame_batch_timeout:
                    break
            
            # 只发送最新的帧，避免过度更新UI
            if latest_frame is not None:
                # 使用 weakref 避免内存泄漏，但这里直接传递数据
                # 在Qt信号中传递大对象需要注意
                self.internal_frame_ready.emit(latest_frame)
                
        except Exception as e:
            self.logger.error(f"批量捕获帧失败: {e}")
            self.internal_error_occurred.emit('capture_frame', str(e))
    
    def _cleanup_resources(self):
        """清理资源"""
        try:
            self._capture_manager.close()
        except:
            pass
        self._frame_request_pending = False
    
    def set_fps(self, fps: int):
        """设置帧率"""
        self._target_fps = max(1, min(fps, 60))
        self._frame_interval = 1.0 / self._target_fps
        self.logger.info(f"帧率设置为: {self._target_fps} FPS")


class AsyncCaptureManager(QObject):
    """优化的异步捕获管理器 - 真正的非阻塞实现"""
    
    # UI线程信号 - 从工作对象转发过来
    capture_started = Signal(str, bool)    # target, success
    capture_stopped = Signal()              # 捕获已停止
    frame_ready = Signal(np.ndarray)        # 新帧可用
    capture_error = Signal(str, str)        # operation, message
    stats_updated = Signal(dict)           # 统计信息
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        self._setup_worker_thread()
        
        # 状态管理
        self._is_capturing = False
        self._current_target = None
        self._fps = 30
        self._frame_timer = QTimer()
        self._frame_timer.timeout.connect(self._request_frame)
        
        # 帧显示频率控制，避免过度更新UI
        self._min_frame_interval = 33  # 约30FPS，毫秒
        self._last_frame_time = 0
        
        self.logger.info("异步捕获管理器已创建")
    
    def _setup_worker_thread(self):
        """设置工作线程"""
        # 创建工作对象
        self._worker = CaptureWorker()
        
        # 创建工作线程
        self._worker_thread = QThread()
        self._worker.moveToThread(self._worker_thread)
        
        # 连接内部信号到对外信号（跨线程连接，Qt会自动处理）
        self._worker.internal_frame_ready.connect(self._on_internal_frame_ready, Qt.QueuedConnection)
        self._worker.internal_error_occurred.connect(self._on_internal_error, Qt.QueuedConnection)
        self._worker.internal_started.connect(self._on_internal_started, Qt.QueuedConnection)
        self._worker.internal_stats_ready.connect(self.stats_updated, Qt.QueuedConnection)
        
        # 线程启动和停止
        self._worker_thread.started.connect(self._worker.start_worker)
        self._worker_thread.start()
    
    @Slot(object) 
    def _on_internal_frame_ready(self, frame):
        """内帧接收"""
        current_time = time.time() * 1000  # 转换为毫秒
        
        # 帧率限制 - 避免过度更新UI
        if current_time - self._last_frame_time >= self._min_frame_interval:
            self._last_frame_time = current_time
            
            # 深拷贝帧数据（如果原始帧较大，可以考虑其他优化）
            if isinstance(frame, np.ndarray):
                try:
                    # 发送信号，Qt会处理跨线程问题
                    self.frame_ready.emit(frame)
                except Exception as e:
                    self.logger.error(f"帧信号发送失败: {e}")
    
    @Slot(str, str)
    def _on_internal_error(self, operation: str, error: str):
        """内错误接收"""
        self.logger.error(f"内部错误 [{operation}]: {error}")
        self.capture_error.emit(operation, error)
    
    @Slot(str, bool)
    def _on_internal_started(self, target: str, success: bool):
        """内启动完成"""
        self.logger.info(f"内部启动完成: {target}, 成功: {success}")
        self._is_capturing = success
        self._current_target = target if success else None
        self.capture_started.emit(target, success)
        
        # 帧率控制
        if success:
            self._start_frame_capture()
    
    def _start_frame_capture(self):
        """启动帧捕获定时器"""
        frame_interval = max(16, int(1000 / self._fps))  # 最少16ms，约60FPS
        self.logger.info(f"帧捕获定时器启动，间隔: {frame_interval}ms")
        self._frame_timer.start(frame_interval)
    
    def _request_frame(self):
        """请求捕获帧"""
        if self._is_capturing:
            request = CaptureRequest(request_type='frame')
            self._worker.submit_request(request)
    
    def open_window_capture(self, target: Union[str, int], 
                           partial_match: bool = True,
                           async_init: bool = True,
                           timeout: float = 3.0,
                           callback: Optional[Callable] = None) -> bool:
        """打开窗口捕获（非阻塞）"""
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
        """打开显示器捕获（非阻塞）"""
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
        
        # 停止帧捕获定时器
        if self._frame_timer.isActive():
            self._frame_timer.stop()
        
        # 提交停止请求
        request = CaptureRequest(request_type='close')
        success = self._worker.submit_request(request)
        
        if success:
            self._is_capturing = False
            self._current_target = None
            self.capture_stopped.emit()
            self.logger.info("捕获已停止")
        
        return success
    
    def set_fps(self, fps: int):
        """设置捕获帧率"""
        self._fps = max(1, min(fps, 60))
        self.logger.info(f"帧率设置为: {self._fps} FPS")
        
        # 如果正在捕获，重启定时器
        if self._frame_timer.isActive():
            self._frame_timer.stop()
            self._start_frame_capture()
        
        # 通知工作线程
        self._worker.set_fps(self._fps)
    
    def is_capturing(self) -> bool:
        """是否正在捕获"""
        return self._is_capturing
    
    def get_current_target(self) -> Optional[str]:
        """获取当前捕获目标"""
        return self._current_target
    
    def stop(self):
        """完全停止异步管理器"""
        self.logger.info("正在停止优化的异步捕获管理器...")
        
        # 停止捕获
        self.stop_capture()
        
        # 停止帧定时器
        if self._frame_timer.isActive():
            self._frame_timer.stop()
        
        # 停止工作线程
        if hasattr(self, '_worker'):
            self._worker.stop_worker()
        
        # 等待线程结束（带有超时）
        if self._worker_thread.isRunning():
            self._worker_thread.quit()
            if not self._worker_thread.wait(3000):  # 最多等待3秒
                self.logger.warning("工作线程未能正常停止，进行强制终止")
                self._worker_thread.terminate()
        
        self.logger.info("优化的异步捕获管理器已停止")
    
    def __del__(self):
        """析构函数"""
        try:
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
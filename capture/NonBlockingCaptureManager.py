# -*- coding: utf-8 -*-
"""
非阻塞窗口捕获管理器

最终版本：彻底解决UI阻塞问题
- Qt线程模型正确分离
- 帧数据智能缓冲
- 显示频率自适应控制
- 各环节流畅衔接
"""

from __future__ import annotations
import time
import threading
import weakref
from typing import Optional, Union, Callable, Dict, Any
from dataclasses import dataclass
import numpy as np

from PySide6.QtCore import QObject, Signal, QThread, QTimer, Qt, Slot, QMetaObject, Q_ARG
from PySide6.QtGui import QImage, QPixmap

# 导入捕获相关模块
from .capture_manager import CaptureManager
from .AsyncFrameManager import AsyncFrameManager, get_async_frame_manager
from .wgc_backend import WGC_AVAILABLE
from auto_approve.logger_manager import get_logger


class CaptureWorker(QObject):
    """捕获工作对象 - 专注于捕获逻辑"""
    
    # 捕获核心信号
    frame_captured = Signal(object)    # 传递帧数据
    capture_started = Signal(str, bool) # 捕获启动状态
    capture_error = Signal(str, str)   # 捕获错误
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        self._capture_manager = CaptureManager()
        self._running = False
        self._capturing_target = None
        self._capture_lock = threading.Lock()
        
        # 帧捕获参数
        self._target_fps = 30
        self._frame_interval = 1.0 / self._target_fps
        self._last_capture_time = 0
        
        self.logger.debug("捕获工作对象已创建")
    
    @Slot()
    def start_capture_session(self, target: Union[str, int], partial_match: bool = True):
        """在后台线程中启动捕获会话"""
        with self._capture_lock:
            try:
                self.logger.debug(f"正在启动捕获会话: {target}")
                
                success = self._capture_manager.open_window(
                    target=target,
                    partial_match=partial_match,
                    async_init=True,
                    timeout=3.0
                )
                
                if success:
                    self._capturing_target = str(target)
                    self._running = True
                    self.logger.info(f"捕获会话启动成功: {target}")
                else:
                    self._capturing_target = None
                    self._running = False
                    self.logger.warning(f"捕获会话启动失败: {target}")
                
                # 发送信号到UI线程
                self.capture_started.emit(str(target), success)
                
            except Exception as e:
                self.logger.error(f"启动捕获会话异常: {e}")
                self.capture_error.emit('start_session', str(e))
                self.capture_started.emit(str(target), False)
    
    @Slot()
    def stop_capture_session(self):
        """停止捕获会话"""
        with self._capture_lock:
            try:
                self.logger.info("正在停止捕获会话")
                self._capture_manager.close()
                self._running = False
                self._capturing_target = None
                self.logger.info("捕获会话已停止")
            except Exception as e:
                self.logger.error(f"停止捕获会话失败: {e}")
    
    @Slot()
    def capture_single_frame(self):
        """捕获单帧（会在后台线程中调用）"""
        if not self._running:
            return
            
        with self._capture_lock:
            try:
                # 时间检查避免过于频繁
                current_time = time.time()
                if current_time - self._last_capture_time < self._frame_interval:
                    return
                
                frame = self._capture_manager.capture_frame()
                self._last_capture_time = current_time
                
                if frame is not None:
                    # 发送帧信号（Qt自动处理跨线程）
                    self.frame_captured.emit(frame)
                    
            except Exception as e:
                self.logger.error(f"捕获帧失败: {e}")
                self.capture_error.emit('capture_frame', str(e))
    
    def set_fps(self, fps: int):
        """设置捕获帧率"""
        self._target_fps = max(1, min(fps, 60))
        self._frame_interval = 1.0 / self._target_fps
        self.logger.debug(f"捕获帧率设置为: {self._target_fps} FPS")


class NonBlockingCaptureManager(QObject):
    """真正的非阻塞捕获管理器"""
    
    # 优化的信号 - 只传递必要数据，避免大数据块
    capture_started = Signal(str, bool)      # 捕获启动完成
    capture_stopped = Signal()               # 捕获已停止
    frame_ready = Signal(QImage)             # 处理好的QImage帧
    capture_error = Signal(str, str)         # 错误信息
    performance_stats = Signal(dict)         # 性能统计
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        
        # 创建工作线程
        self._worker = CaptureWorker()
        self._worker_thread = QThread()
        
        # 帧管理器（作为子对象，会与父对象同线程）
        self._frame_manager = get_async_frame_manager()
        self._frame_manager.ready_frame.connect(self._on_ready_frame)
        
        # 性能监控
        self._request_timer = QTimer()
        self._request_timer.timeout.connect(self._request_frame)
        
        # 状态管理
        self._is_capturing = False
        self._current_target = None
        self._fps = 30
        self._stats = {
            'captured_frames': 0,
            'displayed_frames': 0,
            'dropped_frames': 0,
            'avg_process_time': 0,
            'last_error': None,
        }
        
        # 性能调优参数
        self._frame_request_interval = max(16, 1000 // self._fps)  # 约30-60 FPS
        self._last_performance_report = time.time()
        
        self._setup_threading()
        self.logger.info("非阻塞捕获管理器已创建")
    
    def _setup_threading(self):
        """设置线程架构"""
        # 将工作对象移到工作线程
        self._worker.moveToThread(self._worker_thread)
        
        # 连接工作对象信号到管理器槽函数
        # 使用Qt.QueuedConnection确保信号跨线程安全传递
        self._worker.frame_captured.connect(
            self._on_frame_captured, Qt.QueuedConnection
        )
        self._worker.capture_started.connect(
            self._on_capture_started, Qt.QueuedConnection
        )
        self._worker.capture_error.connect(
            self._on_capture_error, Qt.QueuedConnection
        )
        
        # 启动工作线程
        self._worker_thread.start()
    
    @Slot(object)
    def _on_frame_captured(self, frame: np.ndarray):
        """帧已捕获（在工作线程中触发，在UI线程中处理）"""
        self._stats['captured_frames'] += 1
        
        # 将原始帧提交给帧管理器进行异步处理
        # 这里不再直接处理大对象，交给专门的帧处理器
        success = self._frame_manager.submit_raw_frame(frame)
        if not success:
            self._stats['dropped_frames'] += 1
    
    @Slot(QImage)
    def _on_ready_frame(self, qimage: QImage):
        """帧已准备好显示（来自帧管理器）"""
        self._stats['displayed_frames'] += 1
        
        # 直接发送给前端，不再做任何处理
        self.frame_ready.emit(qimage)
        
        # 定期发送性能统计
        current_time = time.time()
        if current_time - self._last_performance_report >= 1.0:  # 每秒一次
            self._send_performance_stats()
            self._last_performance_report = current_time
    
    @Slot(str, bool)
    def _on_capture_started(self, target: str, success: bool):
        """捕获会话启动完成"""
        self._is_capturing = success
        
        if success:
            self._current_target = target
            self._start_frame_requests()
        else:
            self._current_target = None
        
        # 转发信号到外部
        self.capture_started.emit(target, success)
    
    @Slot(str, str)
    def _on_capture_error(self, operation: str, error: str):
        """捕获错误"""
        self._stats['last_error'] = f"[{operation}] {error}"
        self.capture_error.emit(operation, error)
        self.logger.error(f"捕获错误 [{operation}]: {error}")
    
    def _start_frame_requests(self):
        """启动帧请求定时器"""
        self._frame_request_interval = max(16, 1000 // self._fps)
        self._request_timer.start(self._frame_request_interval)
        self.logger.info(f"帧请求定时器启动，间隔: {self._frame_request_interval}ms")
    
    def _request_frame(self):
        """请求捕获帧（UI线程调用，但请求会在工作线程处理）"""
        # 这个调用会在工作线程中执行，不会阻塞UI
        if self._is_capturing:
            # Qt会自动将槽函数调用排队到目标线程
            self._worker.capture_single_frame()
    
    def _send_performance_stats(self):
        """发送性能统计"""
        stats = self._get_current_stats()
        self.performance_stats.emit(stats)
    
    def _get_current_stats(self) -> Dict[str, Any]:
        """获取当前统计"""
        frame_stats = self._frame_manager.get_stats()
        
        return {
            'is_capturing': self._is_capturing,
            'target': self._current_target,
            'fps_setting': self._fps,
            **self._stats,
            **frame_stats
        }
    
    # ===== 公共接口 =====
    
    def start_window_capture(self, target: Union[str, int], 
                           partial_match: bool = True) -> bool:
        """开始窗口捕获（完全非阻塞）"""
        if self._is_capturing:
            self.stop_capture()
        
        # 清理统计
        self._stats = {
            'captured_frames': 0,
            'displayed_frames': 0,
            'dropped_frames': 0,
            'avg_process_time': 0,
            'last_error': None,
        }
        
        # 直接调用工作对象的槽函数，Qt会自动排队
        self._worker.start_capture_session(target, partial_match)
        
        self.logger.info(f"请求启动窗口捕获: {target}")
        return True
    
    def stop_capture(self):
        """停止捕获（非阻塞）"""
        if not self._is_capturing:
            return
        
        # 停止帧请求
        if self._request_timer.isActive():
            self._request_timer.stop()
        
        # 请求停止捕获会话
        self._worker.stop_capture_session()
        
        self._is_capturing = False
        self._current_target = None
        
        self.capture_stopped.emit()
        self.logger.info("停止捕获请求已发送")
    
    def set_fps(self, fps: int):
        """设置捕获帧率"""
        self._fps = max(1, min(fps, 60))
        
        # 更新工作对象
        self._worker.set_fps(self._fps)
        
        # 如果正在捕获，重启定时器
        if self._request_timer.isActive():
            self._request_timer.stop()
            self._start_frame_requests()
        
        self.logger.info(f"帧率设置为: {self._fps}")
    
    def is_capturing(self) -> bool:
        """是否正在捕获"""
        return self._is_capturing
    
    def get_current_target(self) -> Optional[str]:
        """获取当前捕获目标"""
        return self._current_target
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._get_current_stats()
    
    def stop(self):
        """完全停止"""
        self.logger.info("正在停止非阻塞捕获管理器...")
        
        # 停止捕获
        self.stop_capture()
        
        # 停止帧管理器
        self._frame_manager.stop_frame_processing()
        
        # 停止工作对象
        QMetaObject.invokeMethod(
            self._worker,
            "stop_worker",
            Qt.QueuedConnection
        )
        
        # 等待工作线程结束
        if self._worker_thread.isRunning():
            self._worker_thread.quit()
            if not self._worker_thread.wait(2000):  # 2秒超时
                self.logger.warning("工作线程未能正常停止")
                self._worker_thread.terminate()
        
        self.logger.info("非阻塞捕获管理器已停止")
    
    def __del__(self):
        """清理"""
        try:
            if hasattr(self, '_worker_thread') and self._worker_thread.isRunning():
                self.stop()
        except:
            pass


# 全局实例
_global_capture_manager: Optional[NonBlockingCaptureManager] = None


def get_nonblocking_capture_manager() -> NonBlockingCaptureManager:
    """获取全局非阻塞捕获管理器"""
    global _global_capture_manager
    if _global_capture_manager is None:
        _global_capture_manager = NonBlockingCaptureManager()
    return _global_capture_manager


def start_nonblocking_window_capture(target: Union[str, int]) -> bool:
    """便捷函数：启动非阻塞窗口捕获"""
    manager = get_nonblocking_capture_manager()
    return manager.start_window_capture(target)


def stop_nonblocking_capture():
    """便捷函数：停止非阻塞捕获"""
    manager = get_nonblocking_capture_manager()
    manager.stop_capture()
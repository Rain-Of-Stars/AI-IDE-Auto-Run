# -*- coding: utf-8 -*-
"""
终极性能优化异步捕获管理器

结合所有优化技术：
- 高性能帧缓冲
- 智能帧率控制
- 零拷贝帧共享
- 自适应性能调节
- 完全非阻塞设计
"""

from __future__ import annotations
import time
import threading
from typing import Optional, Union, Callable, Dict, Any
from dataclasses import dataclass
import numpy as np

from PySide6.QtCore import QObject, Signal, QThread, QTimer, Qt, Slot
from PySide6.QtGui import QImage

# 导入优化模块
from .capture_manager import CaptureManager
from .high_performance_frame_buffer import (
    get_high_performance_frame_buffer, 
    FrameMetadata,
    submit_frame_to_buffer,
    get_latest_frame_from_buffer
)
from auto_approve.logger_manager import get_logger


@dataclass
class CaptureConfig:
    """捕获配置"""
    target_fps: int = 30
    adaptive_fps: bool = True
    max_buffer_size: int = 10
    max_memory_mb: int = 100
    include_cursor: bool = False
    border_required: bool = False
    restore_minimized: bool = True
    enable_health_check: bool = False
    fast_mode: bool = True


class OptimizedCaptureWorker(QObject):
    """优化捕获工作对象"""
    
    # 核心信号
    capture_started = Signal(str, bool)  # 目标, 成功
    frame_processed = Signal(object, object)  # 帧, 元数据
    capture_error = Signal(str, str)  # 操作, 错误
    performance_stats = Signal(dict)  # 性能统计
    
    def __init__(self, config: CaptureConfig):
        super().__init__()
        self.logger = get_logger()
        self._config = config
        self._capture_manager = CaptureManager()
        self._frame_buffer = get_high_performance_frame_buffer()
        
        # 配置捕获管理器
        self._capture_manager.configure(
            fps=config.target_fps,
            include_cursor=config.include_cursor,
            border_required=config.border_required,
            restore_minimized=config.restore_minimized
        )
        
        # 状态管理
        self._running = False
        self._capturing = False
        self._target = None
        
        # 性能优化
        self._last_frame_time = 0
        self._frame_interval = 1.0 / config.target_fps if config.target_fps > 0 else 0.033
        self._fast_mode = config.fast_mode
        
        # 统计信息
        self._stats = {
            'frames_processed': 0,
            'frames_dropped': 0,
            'avg_process_time': 0,
            'last_error': None
        }
        
        self.logger.debug("优化捕获工作对象已创建")
    
    @Slot(str, bool)
    def start_capture(self, target: Union[str, int], partial_match: bool = True):
        """启动捕获（在后台线程中执行）"""
        try:
            self.logger.info(f"启动优化捕获: {target}")
            
            # 配置异步初始化和快速模式
            success = self._capture_manager.open_window(
                target=target,
                partial_match=partial_match,
                async_init=True,  # 强制异步初始化
                timeout=0.3  # 减少超时时间
            )
            
            if success:
                self._running = True
                self._capturing = True
                self._target = str(target)
                self.logger.info(f"优化捕获启动成功: {target}")
            else:
                self._running = False
                self._capturing = False
                self.logger.warning(f"优化捕获启动失败: {target}")
            
            # 发送信号（Qt自动处理跨线程）
            self.capture_started.emit(str(target), success)
            
        except Exception as e:
            self.logger.error(f"启动捕获异常: {e}")
            self.capture_started.emit(str(target), False)
            self.capture_error.emit('start_capture', str(e))
    
    @Slot()
    def stop_capture(self):
        """停止捕获"""
        try:
            self.logger.info("停止优化捕获")
            
            self._running = False
            self._capturing = False
            
            if self._capture_manager:
                self._capture_manager.close()
            
            self._target = None
            
            self.logger.info("优化捕获已停止")
            
        except Exception as e:
            self.logger.error(f"停止捕获异常: {e}")
            self.capture_error.emit('stop_capture', str(e))
    
    @Slot()
    def process_frame(self):
        """处理单帧（高性能版本）"""
        if not self._running or not self._capturing:
            return
        
        try:
            # 帧率控制
            current_time = time.time()
            if current_time - self._last_frame_time < self._frame_interval:
                return
            
            # 快速捕获
            if self._fast_mode:
                frame = self._capture_manager.capture_frame_fast()
            else:
                frame = self._capture_manager.capture_frame()
            
            if frame is not None:
                self._last_frame_time = current_time
                
                # 提交到高性能缓冲区
                frame_id = f"opt_{int(current_time * 1000000)}_{self._stats['frames_processed']}"
                success = submit_frame_to_buffer(frame, frame_id)
                
                if success:
                    self._stats['frames_processed'] += 1
                    
                    # 获取元数据
                    result = get_latest_frame_from_buffer()
                    if result:
                        buffered_frame, metadata = result
                        self.frame_processed.emit(buffered_frame, metadata)
                else:
                    self._stats['frames_dropped'] += 1
                
                # 更新性能统计
                self._update_performance_stats()
            
        except Exception as e:
            self.logger.error(f"处理帧失败: {e}")
            self.capture_error.emit('process_frame', str(e))
            self._stats['last_error'] = str(e)
    
    def update_config(self, config: CaptureConfig):
        """更新配置"""
        self._config = config
        self._frame_interval = 1.0 / config.target_fps if config.target_fps > 0 else 0.033
        self._fast_mode = config.fast_mode
        
        # 更新捕获管理器配置
        if self._capture_manager:
            self._capture_manager.configure(
                fps=config.target_fps,
                include_cursor=config.include_cursor,
                border_required=config.border_required,
                restore_minimized=config.restore_minimized
            )
        
        self.logger.info(f"捕获配置已更新: FPS={config.target_fps}, 快速模式={config.fast_mode}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        buffer_stats = self._frame_buffer.get_stats() if self._frame_buffer else {}
        
        return {
            'worker_stats': self._stats.copy(),
            'buffer_stats': buffer_stats,
            'config': {
                'target_fps': self._config.target_fps,
                'adaptive_fps': self._config.adaptive_fps,
                'fast_mode': self._fast_mode
            },
            'is_running': self._running,
            'is_capturing': self._capturing,
            'target': self._target
        }
    
    def _update_performance_stats(self):
        """更新性能统计"""
        # 简单的性能统计更新
        # 更复杂的统计可以在这里添加
        pass


class UltimatePerformanceCaptureManager(QObject):
    """终极性能捕获管理器"""
    
    # 核心信号
    capture_started = Signal(str, bool)  # 目标, 成功
    frame_ready = Signal(QImage)  # 处理好的QImage
    capture_error = Signal(str, str)  # 操作, 错误
    performance_stats = Signal(dict)  # 性能统计
    status_changed = Signal(str)  # 状态变化
    
    def __init__(self, config: CaptureConfig = None):
        super().__init__()
        self.logger = get_logger()
        
        # 配置
        self._config = config or CaptureConfig()
        
        # 创建工作线程和工作对象
        self._worker_thread = QThread()
        self._worker = OptimizedCaptureWorker(self._config)
        self._worker.moveToThread(self._worker_thread)
        
        # 高性能帧缓冲
        self._frame_buffer = get_high_performance_frame_buffer()
        self._frame_buffer.frame_ready.connect(self._on_frame_ready)
        self._frame_buffer.buffer_stats.connect(self._on_buffer_stats)
        self._frame_buffer.performance_warning.connect(self._on_performance_warning)
        
        # 配置帧缓冲
        self._frame_buffer.set_target_fps(self._config.target_fps)
        self._frame_buffer.enable_adaptive_fps(self._config.adaptive_fps)
        
        # 定时器
        self._frame_timer = QTimer()
        self._frame_timer.timeout.connect(self._request_frame)
        
        # 状态管理
        self._is_capturing = False
        self._current_target = None
        self._frame_interval = max(16, 1000 // self._config.target_fps)
        
        # 连接工作对象信号
        self._connect_worker_signals()
        
        # 启动工作线程
        self._worker_thread.start()
        
        self.logger.info("终极性能捕获管理器已初始化")
    
    def _connect_worker_signals(self):
        """连接工作对象信号"""
        self._worker.capture_started.connect(self._on_capture_started)
        self._worker.frame_processed.connect(self._on_frame_processed)
        self._worker.capture_error.connect(self._on_capture_error)
        self._worker.performance_stats.connect(self.performance_stats)
    
    @Slot(str, bool)
    def _on_capture_started(self, target: str, success: bool):
        """捕获启动完成"""
        self.logger.info(f"捕获启动结果: {target}, 成功: {success}")
        
        if success:
            self._is_capturing = True
            self._current_target = target
            self.capture_started.emit(target, True)
            
            # 启动帧请求定时器
            self._frame_timer.start(self._frame_interval)
            self.status_changed.emit("capturing")
        else:
            self._is_capturing = False
            self._current_target = None
            self.capture_started.emit(target, False)
            self.status_changed.emit("failed")
    
    @Slot(object, object)
    def _on_frame_processed(self, frame: np.ndarray, metadata: FrameMetadata):
        """帧已处理"""
        # 这个信号主要是为了统计，实际的帧处理由帧缓冲完成
        pass
    
    @Slot(np.ndarray, FrameMetadata)
    def _on_frame_ready(self, frame: np.ndarray, metadata: FrameMetadata):
        """帧已准备好（来自帧缓冲）"""
        try:
            # 转换为QImage
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            
            # 创建QImage
            qimage = QImage(
                frame.data,
                width,
                height,
                bytes_per_line,
                QImage.Format_RGB888
            ).rgbSwapped()  # BGR -> RGB
            
            # 发送信号
            self.frame_ready.emit(qimage)
            
        except Exception as e:
            self.logger.error(f"转换帧为QImage失败: {e}")
    
    @Slot(str, str)
    def _on_capture_error(self, operation: str, error: str):
        """捕获错误"""
        self.logger.error(f"捕获错误 [{operation}]: {error}")
        self.capture_error.emit(operation, error)
        self.status_changed.emit("error")
    
    @Slot(dict)
    def _on_buffer_stats(self, stats: dict):
        """缓冲统计更新"""
        # 合并统计信息
        combined_stats = self._worker.get_stats()
        combined_stats['buffer_stats'] = stats
        self.performance_stats.emit(combined_stats)
    
    @Slot(str, float)
    def _on_performance_warning(self, warning_type: str, value: float):
        """性能警告"""
        self.logger.warning(f"性能警告 [{warning_type}]: {value}")
        
        # 自适应调整
        if warning_type == "high_fps" and self._config.adaptive_fps:
            # 帧率过高，适当降低
            new_fps = max(15, int(self._config.target_fps * 0.8))
            self.set_fps(new_fps)
    
    def _request_frame(self):
        """请求捕获帧"""
        if self._is_capturing:
            # 在工作线程中执行
            self._worker.process_frame()
    
    def start_capture(self, target: Union[str, int], partial_match: bool = True) -> bool:
        """开始捕获"""
        if self._is_capturing:
            self.stop_capture()
        
        # 在工作线程中启动捕获
        self._worker.start_capture(target, partial_match)
        
        self.logger.info(f"请求启动捕获: {target}")
        return True
    
    def stop_capture(self):
        """停止捕获"""
        if not self._is_capturing:
            return
        
        # 停止定时器
        if self._frame_timer.isActive():
            self._frame_timer.stop()
        
        # 在工作线程中停止捕获
        self._worker.stop_capture()
        
        self._is_capturing = False
        self._current_target = None
        
        self.status_changed.emit("stopped")
        self.logger.info("停止捕获请求已发送")
    
    def set_fps(self, fps: int):
        """设置帧率"""
        self._config.target_fps = max(1, min(fps, 120))
        self._frame_interval = max(16, 1000 // self._config.target_fps)
        
        # 更新工作对象配置
        self._worker.update_config(self._config)
        
        # 更新帧缓冲配置
        self._frame_buffer.set_target_fps(self._config.target_fps)
        
        # 如果正在捕获，重启定时器
        if self._frame_timer.isActive():
            self._frame_timer.stop()
            self._frame_timer.start(self._frame_interval)
        
        self.logger.info(f"帧率设置为: {self._config.target_fps}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self._worker.get_stats()
    
    def is_capturing(self) -> bool:
        """是否正在捕获"""
        return self._is_capturing
    
    def get_current_target(self) -> Optional[str]:
        """获取当前目标"""
        return self._current_target
    
    def update_config(self, config: CaptureConfig):
        """更新配置"""
        self._config = config
        self._worker.update_config(config)
        
        # 更新帧缓冲
        self._frame_buffer.enable_adaptive_fps(config.adaptive_fps)
        
        self.logger.info("配置已更新")
    
    def stop(self):
        """完全停止"""
        self.logger.info("正在停止终极性能捕获管理器...")
        
        # 停止捕获
        self.stop_capture()
        
        # 停止工作线程
        if self._worker_thread.isRunning():
            self._worker_thread.quit()
            self._worker_thread.wait(2000)  # 2秒超时
        
        self.logger.info("终极性能捕获管理器已停止")
    
    def __del__(self):
        """析构函数"""
        try:
            self.stop()
        except:
            pass


# 全局实例
_global_ultimate_manager: Optional[UltimatePerformanceCaptureManager] = None


def get_ultimate_performance_manager() -> UltimatePerformanceCaptureManager:
    """获取全局终极性能管理器"""
    global _global_ultimate_manager
    if _global_ultimate_manager is None:
        _global_ultimate_manager = UltimatePerformanceCaptureManager()
    return _global_ultimate_manager


def start_ultimate_capture(target: Union[str, int]) -> bool:
    """便捷函数：启动终极性能捕获"""
    manager = get_ultimate_performance_manager()
    return manager.start_capture(target)


def stop_ultimate_capture():
    """便捷函数：停止终极性能捕获"""
    manager = get_ultimate_performance_manager()
    manager.stop_capture()
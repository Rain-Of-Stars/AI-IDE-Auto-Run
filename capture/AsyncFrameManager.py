# -*- coding: utf-8 -*-
"""
异步帧数据管理器

专门解决帧数据传输和显示中的性能问题，确保真正的非阻塞体验
"""

from __future__ import annotations
import time
import threading
import weakref
from typing import Optional, Dict, Any, Tuple
import numpy as np

from PySide6.QtCore import QObject, Signal, QTimer, QMutex, QMutexLocker, Slot
from PySide6.QtGui import QImage, QPixmap


class FrameQueue:
    """线程安全的帧队列 - 使用双重缓冲区策略"""
    
    def __init__(self, max_size: int = 3):
        # 使用简单的双缓冲区策略，避免复杂的队列管理
        self._buffer_a: Optional[np.ndarray] = None
        self._buffer_b: Optional[np.ndarray] = None
        self._current_buffer = 'a'
        self._mutex = QMutex()
        self._max_size = max_size
        self._frame_count = 0
        self._dropped_frames = 0
        
    def put_frame(self, frame: np.ndarray) -> bool:
        """提交帧到队列"""
        with QMutexLocker(self._mutex):
            try:
                # 只保留最新帧，丢弃旧帧（避免累积延迟）
                if self._current_buffer == 'a':
                    self._buffer_b = frame.copy()
                    self._current_buffer = 'b'
                else:
                    self._buffer_a = frame.copy()
                    self._current_buffer = 'a'
                
                self._frame_count += 1
                return True
            except Exception:
                self._dropped_frames += 1
                return False
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """获取最新帧"""
        with QMutexLocker(self._mutex):
            if self._current_buffer == 'a' and self._buffer_a is not None:
                return self._buffer_a
            elif self._current_buffer == 'b' and self._buffer_b is not None:
                return self._buffer_b
            return None
    
    def get_stats(self) -> Dict[str, Any]:
        """获取队列统计"""
        with QMutexLocker(self._mutex):
            return {
                'frame_count': self._frame_count,
                'dropped_frames': self._dropped_frames,
                'current_buffer': self._current_buffer,
                'has_frame': self._buffer_a is not None or self._buffer_b is not None
            }


class FrameDisplayOptimizer(QObject):
    """帧显示优化器 - 管理帧到UI的高效显示"""
    
    # 优化的显示信号 - 使用QImage直接传递，避免numpy转换在UI线程
    optimized_frame_ready = Signal(QImage)  
    display_stats_updated = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.frame_queue = FrameQueue()
        self.display_timer = QTimer()
        self.display_timer.timeout.connect(self._process_display)
        
        # 显示参数
        self.display_fps = 30
        self._display_interval = max(16, 1000 // self.display_fps)  # 最少16ms
        self._last_display_time = 0
        
        # 统计信息
        self._displayed_frames = 0
        self._conversion_time = 0
        self._scale_time = 0
        
        # 缩放缓存，避免重复计算
        self._last_target_size = None
        self._scaled_frame_cache = None
        
        # 帧转换缓存
        self._conversion_cache: Dict[Tuple[int, int, int], QImage] = {}
        self._cache_mutex = QMutex()
        
    def set_display_fps(self, fps: int):
        """设置显示帧率"""
        self.display_fps = max(5, min(fps, 60))
        self._display_interval = max(16, 1000 // self.display_fps)
        
        if self.display_timer.isActive():
            self.display_timer.stop()
            self.display_timer.start(self._display_interval)
    
    def start_display_processing(self):
        """开始显示处理"""
        self.display_timer.start(self._display_interval)
    
    def stop_display_processing(self):
        """停止显示处理"""
        self.display_timer.stop()
    
    def submit_frame_for_display(self, frame: np.ndarray) -> bool:
        """提交帧用于显示"""
        return self.frame_queue.put_frame(frame)
    
    @Slot()
    def _process_display(self):
        """处理显示（在UI线程中运行，但必须快速执行）"""
        current_time = time.time() * 1000  # 毫秒
        
        # 帧率限制
        if current_time - self._last_display_time < self._display_interval:
            return
        
        self._last_display_time = current_time
        
        # 获取最新帧
        frame = self.frame_queue.get_latest_frame()
        if frame is None:
            return
        
        try:
            # 快速转换为QImage
            qimage = self._fast_convert_to_qimage(frame)
            if qimage:
                # 发送信号，避免在槽函数中做复杂处理
                self.optimized_frame_ready.emit(qimage)
                self._displayed_frames += 1
                
        except Exception as e:
            print(f"帧显示处理错误: {e}")
        
        # 定期发送统计
        if self._displayed_frames % 30 == 0:  # 每30帧发送一次统计
            self._send_stats()
    
    def _fast_convert_to_qimage(self, frame: np.ndarray) -> Optional[QImage]:
        """快速转换为QImage（核心优化）"""
        try:
            conversion_start = time.time()
            
            height, width = frame.shape[:2]
            
            # 使用缓存键
            cache_key = (height, width, len(frame.shape))
            
            # 检查转换缓存
            with QMutexLocker(self._cache_mutex):
                if cache_key in self._conversion_cache:
                    # 使用缓存的QImage（深拷贝避免数据竞争）
                    cached_image = self._conversion_cache[cache_key]
                    if cached_image.size() == (width, height):
                        return cached_image.copy()
            
            # 缓存未命中，执行转换
            if len(frame.shape) == 3 and frame.shape[2] == 3:  # BGR
                # BGR -> RGB
                rgb_frame = frame[:, :, ::-1]
                bytes_per_line = 3 * width
                qimage = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            elif len(frame.shape) == 2:  # 灰度图
                bytes_per_line = width
                qimage = QImage(frame.data, width, height, bytes_per_line, QImage.Format_Grayscale8)
            else:
                return None
            
            # 缓存转换结果（但需要小心内存使用）
            if len(self._conversion_cache) < 10:  # 限制缓存大小
                with QMutexLocker(self._cache_mutex):
                    self._conversion_cache[cache_key] = qimage.copy()
            
            self._conversion_time = time.time() - conversion_start
            return qimage
            
        except Exception as e:
            print(f"QImage转换错误: {e}")
            return None
    
    def _send_stats(self):
        """发送显示统计"""
        stats = self.frame_queue.get_stats()
        stats.update({
            'displayed_frames': self._displayed_frames,
            'display_fps': self.display_fps,
            'conversion_time_ms': self._conversion_time * 1000,
            'is_active': self.display_timer.isActive()
        })
        self.display_stats_updated.emit(stats)
    
    def clear_cache(self):
        """清除转换缓存"""
        with QMutexLocker(self._cache_mutex):
            self._conversion_cache.clear()


class AsyncFrameManager(QObject):
    """异步帧管理器 - 完整的帧获取和显示解决方案"""
    
    # 保护的信号 - 只从UI线程发送
    ready_frame = Signal(QImage)          # 转换好的QImage
    frame_stats_updated = Signal(dict)    # 帧统计更新
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = None  # 将延迟导入
        
        # 帧数据队列
        self.frame_queue = FrameQueue()
        
        # 显示优化器
        self.display_optimizer = FrameDisplayOptimizer()
        self.display_optimizer.optimized_frame_ready.connect(self.ready_frame)
        self.display_optimizer.display_stats_updated.connect(self.frame_stats_updated)
        
        # 帧处理定时器
        self.process_timer = QTimer()
        self.process_timer.timeout.connect(self._process_frame_queue)
        
        # 统计信息
        self._received_frames = 0
        self._dropped_frames = 0
        self._processing_time = 0
        
        # 性能配置
        self.processing_fps = 60  # 处理帧率高于显示帧率
        self._processing_interval = max(8, 1000 // self.processing_fps)  # 最少8ms
        
    def set_logger(self, logger):
        """设置日志器"""
        self.logger = logger
    
    def start_frame_processing(self):
        """开始帧处理"""
        self.process_timer.start(self._processing_interval)
        self.display_optimizer.start_display_processing()
        
        if self.logger:
            self.logger.info(f"异步帧处理已启动，处理间隔: {self._processing_interval}ms")
    
    def stop_frame_processing(self):
        """停止帧处理"""
        self.process_timer.stop()
        self.display_optimizer.stop_display_processing()
        
        if self.logger:
            self.logger.info("异步帧处理已停止")
    
    def submit_raw_frame(self, frame: np.ndarray) -> bool:
        """提交原始帧数据"""
        self._received_frames += 1
        
        # 快速提交到队列
        success = self.frame_queue.put_frame(frame)
        if not success:
            self._dropped_frames += 1
            
        return success
    
    @Slot()
    def _process_frame_queue(self):
        """处理帧队列（快速处理，避免阻塞）"""
        start_time = time.time()
        
        # 获取最新帧（非阻塞）
        frame = self.frame_queue.get_latest_frame()
        if frame is not None:
            # 提交给显示优化器（后续在显示线程中处理）
            self.display_optimizer.submit_frame_for_display(frame)
        
        self._processing_time = time.time() - start_time
        
        # 定期发送统计
        if self._received_frames % 60 == 0:
            self._send_stats()
    
    def _send_stats(self):
        """发送统计信息"""
        queue_stats = self.frame_queue.get_stats()
        total_stats = {
            'received_frames': self._received_frames,
            'dropped_frames': self._dropped_frames,
            'processing_time_ms': self._processing_time * 1000,
            'queue_stats': queue_stats,
            'is_processing': self.process_timer.isActive()
        }
        
        self.frame_stats_updated.emit(total_stats)
        
        if self.logger and self._received_frames % 300 == 0:  # 每300帧记录一次
            self.logger.debug(f"帧统计 - 接收:{self._received_frames}, "
                            f"丢弃:{self._dropped_frames}, "
                            f"处理时间:{self._processing_time*1000:.1f}ms")
    
    def set_fps_targets(self, capture_fps: int, display_fps: int):
        """设置帧率目标"""
        self.processing_fps = max(10, min(capture_fps, 120))
        self._processing_interval = max(8, 1000 // self.processing_fps)
        
        if self.process_timer.isActive():
            self.process_timer.stop()
            self.process_timer.start(self._processing_interval)
        
        self.display_optimizer.set_display_fps(display_fps)
        
    def clear_all_caches(self):
        """清除所有缓存"""
        self.display_optimizer.clear_cache()
        
    def get_stats(self) -> dict:
        """获取完整统计"""
        queue_stats = self.frame_queue.get_stats()
        return {
            'received_frames': self._received_frames,
            'dropped_frames': self._dropped_frames,
            'processing_time_ms': self._processing_time * 1000,
            'processing_fps': self.processing_fps,
            'display_fps': self.display_optimizer.display_fps,
            'queue_stats': queue_stats,
            'is_active': self.process_timer.isActive()
        }


# 全局帧管理器实例
_global_frame_manager: Optional[AsyncFrameManager] = None


def get_async_frame_manager() -> AsyncFrameManager:
    """获取全局异步帧管理器"""
    global _global_frame_manager
    if _global_frame_manager is None:
        _global_frame_manager = AsyncFrameManager()
    return _global_frame_manager


def submit_frame_for_async_display(frame: np.ndarray) -> bool:
    """便捷函数：提交帧用于异步显示"""
    manager = get_async_frame_manager()
    return manager.submit_raw_frame(frame)
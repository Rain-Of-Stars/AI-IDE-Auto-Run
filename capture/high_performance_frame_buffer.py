# -*- coding: utf-8 -*-
"""
高性能异步帧缓冲管理器

专门用于解决捕获过程中的性能瓶颈：
- 智能帧缓冲避免重复处理
- 自适应帧率控制
- 内存使用优化
- 零拷贝帧共享
"""

from __future__ import annotations
import time
import threading
import weakref
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass
from collections import deque
import numpy as np

from PySide6.QtCore import QObject, Signal, QTimer, QThread
from auto_approve.logger_manager import get_logger


@dataclass
class FrameMetadata:
    """帧元数据"""
    timestamp: float
    frame_id: str
    width: int
    height: int
    format: str
    size_bytes: int


class HighPerformanceFrameBuffer(QObject):
    """高性能帧缓冲管理器"""
    
    # 信号
    frame_ready = Signal(np.ndarray, FrameMetadata)  # 帧就绪
    buffer_stats = Signal(dict)  # 缓冲统计
    performance_warning = Signal(str, float)  # 性能警告
    
    def __init__(self, max_buffer_size: int = 10, max_memory_mb: int = 100):
        super().__init__()
        self.logger = get_logger()
        
        # 缓冲配置
        self._max_buffer_size = max_buffer_size
        self._max_memory_bytes = max_memory_mb * 1024 * 1024
        self._current_memory_usage = 0
        
        # 帧缓冲
        self._frame_buffer: deque = deque(maxlen=max_buffer_size)
        self._frame_metadata: Dict[str, FrameMetadata] = {}
        self._frame_cache: Dict[str, np.ndarray] = {}
        
        # 性能监控
        self._stats = {
            'total_frames': 0,
            'dropped_frames': 0,
            'buffer_hits': 0,
            'buffer_misses': 0,
            'avg_processing_time': 0.0,
            'memory_usage_mb': 0.0,
            'buffer_efficiency': 0.0
        }
        
        # 自适应控制
        self._adaptive_fps = True
        self._target_fps = 30
        self._actual_fps = 0
        self._frame_times = deque(maxlen=30)  # 30帧平均
        
        # 线程安全
        self._lock = threading.RLock()
        self._processing = False
        
        # 清理定时器
        self._cleanup_timer = QTimer()
        self._cleanup_timer.timeout.connect(self._cleanup_old_frames)
        self._cleanup_timer.start(5000)  # 5秒清理一次
        
        self.logger.info(f"高性能帧缓冲管理器已初始化: 最大缓冲={max_buffer_size}, 内存限制={max_memory_mb}MB")
    
    def submit_frame(self, frame: np.ndarray, frame_id: str = None) -> bool:
        """
        提交帧到缓冲区
        
        Args:
            frame: 帧数据
            frame_id: 帧ID，自动生成如果为None
            
        Returns:
            bool: 是否成功提交
        """
        if frame is None:
            return False
        
        start_time = time.time()
        
        try:
            # 生成帧ID
            if frame_id is None:
                frame_id = f"frame_{int(time.time() * 1000000)}_{self._stats['total_frames']}"
            
            # 计算帧大小
            frame_size = frame.nbytes
            
            # 检查内存限制
            with self._lock:
                if self._current_memory_usage + frame_size > self._max_memory_bytes:
                    # 内存不足，清理旧帧
                    self._force_cleanup(frame_size)
                    
                    if self._current_memory_usage + frame_size > self._max_memory_bytes:
                        # 仍然内存不足，丢弃帧
                        self._stats['dropped_frames'] += 1
                        self.logger.warning(f"内存不足丢弃帧: {frame_size} bytes")
                        return False
                
                # 创建元数据
                metadata = FrameMetadata(
                    timestamp=time.time(),
                    frame_id=frame_id,
                    width=frame.shape[1],
                    height=frame.shape[0],
                    format='BGR',
                    size_bytes=frame_size
                )
                
                # 添加到缓冲区
                self._frame_buffer.append((frame_id, frame.copy()))
                self._frame_metadata[frame_id] = metadata
                self._frame_cache[frame_id] = frame.copy()
                
                # 更新内存使用
                self._current_memory_usage += frame_size
                self._stats['total_frames'] += 1
                
                # 更新帧率统计
                self._update_fps_stats()
                
                # 发送信号
                self.frame_ready.emit(frame, metadata)
                
                # 更新性能统计
                processing_time = (time.time() - start_time) * 1000
                self._update_performance_stats(processing_time)
                
                return True
                
        except Exception as e:
            self.logger.error(f"提交帧失败: {e}")
            return False
    
    def get_latest_frame(self) -> Optional[tuple[np.ndarray, FrameMetadata]]:
        """获取最新帧"""
        with self._lock:
            if self._frame_buffer:
                frame_id, frame = self._frame_buffer[-1]
                metadata = self._frame_metadata.get(frame_id)
                if metadata:
                    return frame.copy(), metadata
        return None
    
    def get_frame_by_id(self, frame_id: str) -> Optional[np.ndarray]:
        """根据ID获取帧"""
        with self._lock:
            return self._frame_cache.get(frame_id)
    
    def get_frame_cached(self, frame_id: str) -> Optional[np.ndarray]:
        """获取缓存的帧（零拷贝）"""
        with self._lock:
            frame = self._frame_cache.get(frame_id)
            if frame is not None:
                self._stats['buffer_hits'] += 1
                return frame
            else:
                self._stats['buffer_misses'] += 1
                return None
    
    def release_frame(self, frame_id: str):
        """释放帧引用"""
        with self._lock:
            if frame_id in self._frame_cache:
                metadata = self._frame_metadata.get(frame_id)
                if metadata:
                    self._current_memory_usage -= metadata.size_bytes
                
                del self._frame_cache[frame_id]
    
    def set_target_fps(self, fps: int):
        """设置目标帧率"""
        self._target_fps = max(1, min(fps, 120))
        self.logger.info(f"目标帧率设置为: {self._target_fps} FPS")
    
    def enable_adaptive_fps(self, enabled: bool):
        """启用/禁用自适应帧率"""
        self._adaptive_fps = enabled
        self.logger.info(f"自适应帧率: {'启用' if enabled else '禁用'}")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        with self._lock:
            stats = self._stats.copy()
            stats['memory_usage_mb'] = self._current_memory_usage / 1024 / 1024
            stats['buffer_size'] = len(self._frame_buffer)
            stats['actual_fps'] = self._actual_fps
            stats['target_fps'] = self._target_fps
            
            # 计算缓冲效率
            total_accesses = stats['buffer_hits'] + stats['buffer_misses']
            if total_accesses > 0:
                stats['buffer_efficiency'] = stats['buffer_hits'] / total_accesses
            else:
                stats['buffer_efficiency'] = 0.0
            
            return stats
    
    def _update_fps_stats(self):
        """更新帧率统计"""
        current_time = time.time()
        self._frame_times.append(current_time)
        
        if len(self._frame_times) >= 2:
            time_span = self._frame_times[-1] - self._frame_times[0]
            if time_span > 0:
                self._actual_fps = (len(self._frame_times) - 1) / time_span
                
                # 自适应帧率控制
                if self._adaptive_fps and self._actual_fps > self._target_fps * 1.2:
                    # 实际帧率过高，发出警告
                    self.performance_warning.emit("high_fps", self._actual_fps)
    
    def _update_performance_stats(self, processing_time_ms: float):
        """更新性能统计"""
        # 移动平均处理时间
        alpha = 0.1  # 平滑因子
        self._stats['avg_processing_time'] = (
            alpha * processing_time_ms + 
            (1 - alpha) * self._stats['avg_processing_time']
        )
        
        # 检查性能警告
        if processing_time_ms > 50:  # 超过50ms
            self.performance_warning.emit("slow_processing", processing_time_ms)
    
    def _cleanup_old_frames(self):
        """清理旧帧"""
        with self._lock:
            current_time = time.time()
            cleanup_threshold = 10.0  # 10秒前的帧
            
            frames_to_remove = []
            for frame_id, metadata in self._frame_metadata.items():
                if current_time - metadata.timestamp > cleanup_threshold:
                    frames_to_remove.append(frame_id)
            
            for frame_id in frames_to_remove:
                self._remove_frame(frame_id)
            
            if frames_to_remove:
                self.logger.debug(f"清理了 {len(frames_to_remove)} 个旧帧")
    
    def _force_cleanup(self, required_size: int):
        """强制清理以释放内存"""
        with self._lock:
            # 按时间排序，清理最老的帧
            sorted_frames = sorted(
                self._frame_metadata.items(),
                key=lambda x: x[1].timestamp
            )
            
            freed_size = 0
            for frame_id, metadata in sorted_frames:
                if freed_size >= required_size:
                    break
                
                freed_size += metadata.size_bytes
                self._remove_frame(frame_id)
            
            if freed_size > 0:
                self.logger.debug(f"强制清理释放了 {freed_size} bytes")
    
    def _remove_frame(self, frame_id: str):
        """移除单个帧"""
        if frame_id in self._frame_metadata:
            metadata = self._frame_metadata[frame_id]
            self._current_memory_usage -= metadata.size_bytes
            del self._frame_metadata[frame_id]
        
        if frame_id in self._frame_cache:
            del self._frame_cache[frame_id]
        
        # 从缓冲区移除
        for i, (fid, _) in enumerate(self._frame_buffer):
            if fid == frame_id:
                del self._frame_buffer[i]
                break
    
    def clear_all(self):
        """清空所有缓冲"""
        with self._lock:
            self._frame_buffer.clear()
            self._frame_metadata.clear()
            self._frame_cache.clear()
            self._current_memory_usage = 0
            self.logger.info("已清空所有帧缓冲")
    
    def __del__(self):
        """析构函数"""
        self.clear_all()


# 全局实例
_global_frame_buffer: Optional[HighPerformanceFrameBuffer] = None


def get_high_performance_frame_buffer() -> HighPerformanceFrameBuffer:
    """获取全局高性能帧缓冲管理器"""
    global _global_frame_buffer
    if _global_frame_buffer is None:
        _global_frame_buffer = HighPerformanceFrameBuffer()
    return _global_frame_buffer


def submit_frame_to_buffer(frame: np.ndarray, frame_id: str = None) -> bool:
    """便捷函数：提交帧到缓冲区"""
    buffer = get_high_performance_frame_buffer()
    return buffer.submit_frame(frame, frame_id)


def get_latest_frame_from_buffer() -> Optional[tuple[np.ndarray, FrameMetadata]]:
    """便捷函数：获取最新帧"""
    buffer = get_high_performance_frame_buffer()
    return buffer.get_latest_frame()
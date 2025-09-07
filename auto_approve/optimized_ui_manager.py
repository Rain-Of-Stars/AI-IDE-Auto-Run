# -*- coding: utf-8 -*-
"""
优化的UI响应性管理器 - 解决进度条卡顿问题

主要优化：
1. 完全非阻塞的进度更新机制
2. 智能信号批处理和优先级调度
3. 零延迟的UI更新队列
4. 自适应的更新频率控制
5. 性能监控和自动调节
"""

from __future__ import annotations
import time
import threading
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass, field
from collections import deque
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QObject, Signal, QTimer, QElapsedTimer, Qt, QCoreApplication

from auto_approve.logger_manager import get_logger


@dataclass
class OptimizedUIUpdate:
    """优化的UI更新请求"""
    widget_id: str
    update_type: str
    data: Dict[str, Any]
    priority: int = 0
    timestamp: float = field(default_factory=time.time)
    callback: Optional[Callable] = None
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


class NonBlockingProgressManager(QObject):
    """非阻塞进度管理器 - 彻底解决进度条卡顿"""
    
    # 信号
    progress_updated = Signal(str, int)  # widget_id, progress_value
    status_updated = Signal(str, str)   # widget_id, status_text
    critical_update = Signal(str, dict) # widget_id, full_data
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        
        # 进度状态管理
        self._progress_states: Dict[str, dict] = {}
        self._state_lock = threading.Lock()
        
        # 更新队列（使用deque提升性能）
        self._update_queue = deque()
        self._queue_lock = threading.Lock()
        
        # 高性能定时器
        self._update_timer = QTimer()
        self._update_timer.setTimerType(Qt.PreciseTimer)  # 高精度定时器
        self._update_timer.timeout.connect(self._process_updates)
        
        # 性能优化配置
        self._update_interval_ms = 16  # 约60FPS
        self._max_batch_size = 10      # 每次最多处理10个更新
        self._enable_adaptive = True   # 启用自适应调节
        
        # 性能统计
        self._stats = {
            'total_updates': 0,
            'processed_updates': 0,
            'dropped_updates': 0,
            'avg_processing_time': 0.0,
            'last_update_time': 0.0
        }
        
        # 启动更新循环
        self._start_update_loop()
        
        self.logger.info("非阻塞进度管理器已初始化")
    
    def _start_update_loop(self):
        """启动更新循环"""
        self._update_timer.start(self._update_interval_ms)
        self.logger.debug(f"更新循环已启动，间隔: {self._update_interval_ms}ms")
    
    def update_progress(self, widget_id: str, progress: int, 
                       status: str = "", priority: int = 5):
        """更新进度 - 非阻塞"""
        update = OptimizedUIUpdate(
            widget_id=widget_id,
            update_type='progress',
            data={'progress': progress, 'status': status},
            priority=priority
        )
        
        self._enqueue_update(update)
    
    def update_status(self, widget_id: str, status: str, 
                     priority: int = 3):
        """更新状态 - 非阻塞"""
        update = OptimizedUIUpdate(
            widget_id=widget_id,
            update_type='status',
            data={'status': status},
            priority=priority
        )
        
        self._enqueue_update(update)
    
    def _enqueue_update(self, update: OptimizedUIUpdate):
        """将更新加入队列"""
        with self._queue_lock:
            # 检查队列长度，防止内存泄漏
            if len(self._update_queue) > 100:
                # 队列过长，清理低优先级的旧更新
                self._cleanup_queue()
            
            # 添加到队列
            self._update_queue.append(update)
            self._stats['total_updates'] += 1
    
    def _cleanup_queue(self):
        """清理队列 - 保留高优先级更新"""
        with self._queue_lock:
            if len(self._update_queue) <= 50:
                return
            
            # 按优先级和时间排序
            sorted_updates = sorted(
                self._update_queue, 
                key=lambda x: (x.priority, x.timestamp),
                reverse=True
            )
            
            # 保留前50个最重要的更新
            self._update_queue = deque(sorted_updates[:50])
            dropped_count = len(self._update_queue) - 50
            self._stats['dropped_updates'] += dropped_count
            
            self.logger.warning(f"清理更新队列，丢弃了 {dropped_count} 个低优先级更新")
    
    def _process_updates(self):
        """处理更新批次 - 高性能"""
        if not self._update_queue:
            return
        
        start_time = QElapsedTimer()
        start_time.start()
        
        # 批量获取更新
        batch = self._extract_batch()
        
        if not batch:
            return
        
        # 按优先级排序
        batch.sort(key=lambda x: x.priority, reverse=True)
        
        # 处理批次
        processed_count = 0
        for update in batch:
            try:
                self._execute_update(update)
                processed_count += 1
            except Exception as e:
                self.logger.error(f"执行UI更新失败: {e}")
        
        # 更新统计
        processing_time = start_time.elapsed()
        self._update_stats(processing_time, processed_count)
        
        # 自适应调节
        if self._enable_adaptive:
            self._adjust_performance(processing_time)
    
    def _extract_batch(self) -> List[OptimizedUIUpdate]:
        """提取更新批次"""
        with self._queue_lock:
            if not self._update_queue:
                return []
            
            batch_size = min(len(self._update_queue), self._max_batch_size)
            batch = []
            
            for _ in range(batch_size):
                if self._update_queue:
                    batch.append(self._update_queue.popleft())
            
            return batch
    
    def _execute_update(self, update: OptimizedUIUpdate):
        """执行单个更新"""
        if update.update_type == 'progress':
            progress = update.data.get('progress', 0)
            status = update.data.get('status', '')
            
            # 发送进度更新信号
            self.progress_updated.emit(update.widget_id, progress)
            
            if status:
                self.status_updated.emit(update.widget_id, status)
            
            # 更新内部状态
            with self._state_lock:
                self._progress_states[update.widget_id] = {
                    'progress': progress,
                    'status': status,
                    'last_update': time.time()
                }
        
        elif update.update_type == 'status':
            status = update.data.get('status', '')
            self.status_updated.emit(update.widget_id, status)
            
            # 更新内部状态
            with self._state_lock:
                if update.widget_id in self._progress_states:
                    self._progress_states[update.widget_id]['status'] = status
                    self._progress_states[update.widget_id]['last_update'] = time.time()
    
    def _update_stats(self, processing_time: float, processed_count: int):
        """更新性能统计"""
        self._stats['processed_updates'] += processed_count
        self._stats['last_update_time'] = time.time()
        
        # 计算平均处理时间
        if self._stats['processed_updates'] > 0:
            total_time = (self._stats['avg_processing_time'] * 
                         (self._stats['processed_updates'] - processed_count) + 
                         processing_time)
            self._stats['avg_processing_time'] = total_time / self._stats['processed_updates']
    
    def _adjust_performance(self, processing_time: float):
        """自适应性能调节"""
        # 如果处理时间过长，减少批处理大小
        if processing_time > 20:  # 超过20ms
            self._max_batch_size = max(3, self._max_batch_size - 1)
            self.logger.debug(f"处理时间过长({processing_time}ms)，减少批处理大小至: {self._max_batch_size}")
        
        # 如果处理时间很短，可以增加批处理大小
        elif processing_time < 5 and self._max_batch_size < 20:  # 少于5ms
            self._max_batch_size += 1
            self.logger.debug(f"处理时间很短({processing_time}ms)，增加批处理大小至: {self._max_batch_size}")
    
    def get_progress_state(self, widget_id: str) -> Optional[dict]:
        """获取进度状态"""
        with self._state_lock:
            return self._progress_states.get(widget_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        stats = self._stats.copy()
        stats['queue_size'] = len(self._update_queue)
        stats['active_states'] = len(self._progress_states)
        stats['processing_efficiency'] = (
            stats['processed_updates'] / max(1, stats['total_updates']) * 100
        )
        return stats
    
    def reset_progress(self, widget_id: str):
        """重置进度状态"""
        with self._state_lock:
            if widget_id in self._progress_states:
                del self._progress_states[widget_id]
        
        self.update_progress(widget_id, 0, "已重置")
    
    def cleanup_old_states(self, max_age_seconds: float = 300):
        """清理过期的状态"""
        current_time = time.time()
        with self._state_lock:
            expired_states = [
                widget_id for widget_id, state in self._progress_states.items()
                if current_time - state['last_update'] > max_age_seconds
            ]
            
            for widget_id in expired_states:
                del self._progress_states[widget_id]
        
        if expired_states:
            self.logger.debug(f"清理了 {len(expired_states)} 个过期状态")


class OptimizedSignalEmitter(QObject):
    """优化的信号发射器 - 减少信号传递开销"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        
        # 信号批处理
        self._signal_buffer: Dict[str, List[Tuple]] = {}
        self._buffer_lock = threading.Lock()
        
        # 批处理定时器
        self._batch_timer = QTimer()
        self._batch_timer.setSingleShot(True)
        self._batch_timer.timeout.connect(self._emit_batched_signals)
        
        # 信号定义
        self.signals = {
            'progress': Signal(str, int),
            'status': Signal(str, str),
            'error': Signal(str, str),
            'warning': Signal(str, str),
            'info': Signal(str, str)
        }
    
    def emit_signal(self, signal_type: str, *args, batch: bool = True):
        """发射信号（支持批处理）"""
        if signal_type not in self.signals:
            self.logger.warning(f"未知信号类型: {signal_type}")
            return
        
        if batch:
            # 批处理模式
            with self._buffer_lock:
                if signal_type not in self._signal_buffer:
                    self._signal_buffer[signal_type] = []
                self._signal_buffer[signal_type].append(args)
            
            # 启动批处理定时器
            if not self._batch_timer.isActive():
                self._batch_timer.start(10)  # 10ms批处理延迟
        else:
            # 立即发射
            signal = self.signals[signal_type]
            signal.emit(*args)
    
    def _emit_batched_signals(self):
        """发射批处理的信号"""
        with self._buffer_lock:
            buffer = self._signal_buffer.copy()
            self._signal_buffer.clear()
        
        # 发射所有缓存的信号
        for signal_type, args_list in buffer.items():
            if args_list:  # 只发射有内容的信号
                signal = self.signals[signal_type]
                # 只发射最后一个相同类型的信号（去重）
                last_args = args_list[-1]
                signal.emit(*last_args)
    
    def force_emit_all(self):
        """强制发射所有缓存的信号"""
        if self._batch_timer.isActive():
            self._batch_timer.stop()
        self._emit_batched_signals()


# 全局实例
_global_progress_manager: Optional[NonBlockingProgressManager] = None
_global_signal_emitter: Optional[OptimizedSignalEmitter] = None


def get_progress_manager() -> NonBlockingProgressManager:
    """获取全局进度管理器"""
    global _global_progress_manager
    if _global_progress_manager is None:
        _global_progress_manager = NonBlockingProgressManager()
    return _global_progress_manager


def get_signal_emitter() -> OptimizedSignalEmitter:
    """获取全局信号发射器"""
    global _global_signal_emitter
    if _global_signal_emitter is None:
        _global_signal_emitter = OptimizedSignalEmitter()
    return _global_signal_emitter


# 便捷函数
def update_progress_non_blocking(widget_id: str, progress: int, status: str = ""):
    """非阻塞进度更新"""
    manager = get_progress_manager()
    manager.update_progress(widget_id, progress, status)


def update_status_non_blocking(widget_id: str, status: str):
    """非阻塞状态更新"""
    manager = get_progress_manager()
    manager.update_status(widget_id, status)


def emit_signal_batched(signal_type: str, *args):
    """批处理信号发射"""
    emitter = get_signal_emitter()
    emitter.emit_signal(signal_type, *args)
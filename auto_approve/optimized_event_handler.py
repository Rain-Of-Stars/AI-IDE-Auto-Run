# -*- coding: utf-8 -*-
"""
优化的事件处理和信号传递机制

解决UI响应性问题的关键组件：
1. 零延迟信号发射
2. 智能信号批处理
3. 优先级信号调度
4. 线程安全的信号传递
"""

from __future__ import annotations
import time
import threading
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QObject, Signal, QTimer, QElapsedTimer, Qt, QCoreApplication
from PySide6.QtWidgets import QApplication

from auto_approve.logger_manager import get_logger


@dataclass
class SignalRequest:
    """信号请求"""
    signal_type: str
    args: tuple
    priority: int = 0
    timestamp: float = field(default_factory=time.time)
    callback: Optional[Callable] = None


class OptimizedSignalDispatcher(QObject):
    """优化的信号分发器 - 解决信号传递阻塞问题"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        
        # 信号缓存（使用deque提升性能）
        self._signal_cache: Dict[str, deque] = defaultdict(deque)
        self._cache_lock = threading.Lock()
        
        # 优先级队列
        self._priority_queue: List[SignalRequest] = []
        self._queue_lock = threading.Lock()
        
        # 信号定义
        self._signals = {}
        self._setup_signals()
        
        # 高性能定时器
        self._dispatch_timer = QTimer()
        self._dispatch_timer.setTimerType(Qt.PreciseTimer)
        self._dispatch_timer.timeout.connect(self._dispatch_signals)
        
        # 性能配置
        self._dispatch_interval_ms = 8  # 约120FPS
        self._max_batch_size = 20
        self._enable_batching = True
        self._enable_priority = True
        
        # 性能统计
        self._stats = {
            'total_signals': 0,
            'dispatched_signals': 0,
            'batched_signals': 0,
            'dropped_signals': 0,
            'avg_dispatch_time': 0.0,
            'last_dispatch_time': 0.0
        }
        
        # 启动分发器
        self._start_dispatcher()
        
        self.logger.info("优化信号分发器已初始化")
    
    def _setup_signals(self):
        """设置信号定义"""
        signal_definitions = {
            # 进度相关信号
            'progress_updated': Signal(str, int),     # widget_id, progress
            'status_updated': Signal(str, str),      # widget_id, status
            'progress_started': Signal(str),          # widget_id
            'progress_finished': Signal(str),         # widget_id
            
            # 错误相关信号
            'error_occurred': Signal(str, str),       # operation, error
            'warning_occurred': Signal(str, str),    # operation, warning
            
            # 状态相关信号
            'state_changed': Signal(str, str),       # widget_id, state
            'property_changed': Signal(str, str, Any), # widget_id, property, value
            
            # 通用信号
            'data_updated': Signal(str, dict),       # widget_id, data
            'action_triggered': Signal(str, str),     # action_id, action_type
        }
        
        for signal_name, signal_template in signal_definitions.items():
            self._signals[signal_name] = signal_template
            # 动态创建信号属性
            setattr(self, signal_name, signal_template)
    
    def _start_dispatcher(self):
        """启动信号分发器"""
        self._dispatch_timer.start(self._dispatch_interval_ms)
        self.logger.debug(f"信号分发器已启动，间隔: {self._dispatch_interval_ms}ms")
    
    def emit_signal(self, signal_type: str, *args, 
                   priority: int = 0, batch: bool = True, 
                   callback: Optional[Callable] = None):
        """发射信号（优化版本）"""
        if signal_type not in self._signals:
            self.logger.warning(f"未知信号类型: {signal_type}")
            return
        
        # 创建信号请求
        request = SignalRequest(
            signal_type=signal_type,
            args=args,
            priority=priority,
            callback=callback
        )
        
        if batch and self._enable_batching:
            # 批处理模式
            self._enqueue_batched_signal(request)
        else:
            # 立即发射
            self._emit_immediately(request)
    
    def _enqueue_batched_signal(self, request: SignalRequest):
        """将信号加入批处理队列"""
        with self._queue_lock:
            # 检查队列长度，防止内存泄漏
            if len(self._priority_queue) > 200:
                self._cleanup_queue()
            
            # 添加到优先级队列
            self._priority_queue.append(request)
            self._stats['total_signals'] += 1
    
    def _cleanup_queue(self):
        """清理队列 - 保留高优先级信号"""
        with self._queue_lock:
            if len(self._priority_queue) <= 100:
                return
            
            # 按优先级和时间排序
            sorted_requests = sorted(
                self._priority_queue,
                key=lambda x: (x.priority, x.timestamp),
                reverse=True
            )
            
            # 保留前100个最重要的信号
            self._priority_queue = sorted_requests[:100]
            dropped_count = len(self._priority_queue) - 100
            self._stats['dropped_signals'] += dropped_count
            
            self.logger.warning(f"清理信号队列，丢弃了 {dropped_count} 个低优先级信号")
    
    def _emit_immediately(self, request: SignalRequest):
        """立即发射信号"""
        try:
            signal = self._signals.get(request.signal_type)
            if signal:
                # 使用QTimer.singleShot确保在主线程执行
                QtCore.QTimer.singleShot(0, lambda r=request: self._safe_emit(r))
        except Exception as e:
            self.logger.error(f"立即发射信号失败: {e}")
    
    def _safe_emit(self, request: SignalRequest):
        """安全发射信号"""
        try:
            signal = self._signals.get(request.signal_type)
            if signal:
                signal.emit(*request.args)
                
                # 执行回调
                if request.callback:
                    request.callback()
                
                self._stats['dispatched_signals'] += 1
        except Exception as e:
            self.logger.error(f"发射信号失败 {request.signal_type}: {e}")
    
    def _dispatch_signals(self):
        """分发信号批次"""
        if not self._priority_queue:
            return
        
        start_time = QElapsedTimer()
        start_time.start()
        
        # 提取批次
        batch = self._extract_batch()
        
        if not batch:
            return
        
        # 分发批次
        dispatched_count = 0
        for request in batch:
            try:
                self._safe_emit(request)
                dispatched_count += 1
            except Exception as e:
                self.logger.error(f"分发信号失败: {e}")
        
        # 更新统计
        dispatch_time = start_time.elapsed()
        self._update_stats(dispatch_time, dispatched_count)
        
        # 自适应调节
        self._adjust_performance(dispatch_time)
    
    def _extract_batch(self) -> List[SignalRequest]:
        """提取信号批次"""
        with self._queue_lock:
            if not self._priority_queue:
                return []
            
            # 按优先级排序
            if self._enable_priority:
                self._priority_queue.sort(key=lambda x: x.priority, reverse=True)
            
            # 提取批次
            batch_size = min(len(self._priority_queue), self._max_batch_size)
            batch = self._priority_queue[:batch_size]
            self._priority_queue = self._priority_queue[batch_size:]
            
            return batch
    
    def _update_stats(self, dispatch_time: float, dispatched_count: int):
        """更新性能统计"""
        self._stats['dispatched_signals'] += dispatched_count
        self._stats['batched_signals'] += dispatched_count
        self._stats['last_dispatch_time'] = time.time()
        
        # 计算平均分发时间
        if self._stats['dispatched_signals'] > 0:
            total_time = (self._stats['avg_dispatch_time'] * 
                         (self._stats['dispatched_signals'] - dispatched_count) + 
                         dispatch_time)
            self._stats['avg_dispatch_time'] = total_time / self._stats['dispatched_signals']
    
    def _adjust_performance(self, dispatch_time: float):
        """自适应性能调节"""
        # 如果分发时间过长，减少批处理大小
        if dispatch_time > 16:  # 超过16ms
            self._max_batch_size = max(5, self._max_batch_size - 2)
            self.logger.debug(f"分发时间过长({dispatch_time}ms)，减少批处理大小至: {self._max_batch_size}")
        
        # 如果分发时间很短，可以增加批处理大小
        elif dispatch_time < 4 and self._max_batch_size < 50:  # 少于4ms
            self._max_batch_size += 1
            self.logger.debug(f"分发时间很短({dispatch_time}ms)，增加批处理大小至: {self._max_batch_size}")
    
    def force_dispatch_all(self):
        """强制分发所有缓存的信号"""
        if self._dispatch_timer.isActive():
            self._dispatch_timer.stop()
        
        # 处理所有剩余的信号
        while self._priority_queue:
            self._dispatch_signals()
        
        # 重启定时器
        self._dispatch_timer.start(self._dispatch_interval_ms)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        stats = self._stats.copy()
        stats['queue_size'] = len(self._priority_queue)
        stats['dispatch_efficiency'] = (
            stats['dispatched_signals'] / max(1, stats['total_signals']) * 100
        )
        stats['batching_ratio'] = (
            stats['batched_signals'] / max(1, stats['dispatched_signals']) * 100
        )
        return stats
    
    def set_batching_enabled(self, enabled: bool):
        """启用/禁用批处理"""
        self._enable_batching = enabled
        self.logger.info(f"信号批处理已{'启用' if enabled else '禁用'}")
    
    def set_priority_enabled(self, enabled: bool):
        """启用/禁用优先级"""
        self._enable_priority = enabled
        self.logger.info(f"信号优先级已{'启用' if enabled else '禁用'}")
    
    def set_dispatch_interval(self, interval_ms: int):
        """设置分发间隔"""
        self._dispatch_interval_ms = max(1, interval_ms)
        self._dispatch_timer.setInterval(self._dispatch_interval_ms)
        self.logger.info(f"信号分发间隔设置为: {self._dispatch_interval_ms}ms")
    
    def clear_queue(self):
        """清空信号队列"""
        with self._queue_lock:
            cleared_count = len(self._priority_queue)
            self._priority_queue.clear()
        
        if cleared_count > 0:
            self.logger.info(f"清空了 {cleared_count} 个待处理的信号")


class UIEventOptimizer(QObject):
    """UI事件优化器 - 防止事件循环阻塞"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        
        # 事件过滤
        self._event_filter_enabled = True
        self._event_throttle_ms = 8  # 8ms节流
        
        # 事件统计
        self._event_stats = {
            'total_events': 0,
            'processed_events': 0,
            'throttled_events': 0,
            'last_event_time': 0.0
        }
        
        # 安装事件过滤器
        if QApplication.instance():
            QApplication.instance().installEventFilter(self)
        
        self.logger.info("UI事件优化器已初始化")
    
    def eventFilter(self, obj, event):
        """事件过滤器"""
        if not self._event_filter_enabled:
            return super().eventFilter(obj, event)
        
        # 只处理特定类型的事件
        event_type = event.type()
        
        # 节流检查
        if self._should_throttle_event(event_type):
            self._event_stats['throttled_events'] += 1
            return True  # 拦截事件
        
        self._event_stats['total_events'] += 1
        self._event_stats['processed_events'] += 1
        self._event_stats['last_event_time'] = time.time()
        
        return super().eventFilter(obj, event)
    
    def _should_throttle_event(self, event_type) -> bool:
        """检查是否应该节流事件"""
        current_time = time.time()
        last_time = self._event_stats['last_event_time']
        
        # 检查时间间隔
        if current_time - last_time < (self._event_throttle_ms / 1000.0):
            return True
        
        return False
    
    def get_event_stats(self) -> Dict[str, Any]:
        """获取事件统计"""
        stats = self._event_stats.copy()
        stats['throttling_ratio'] = (
            stats['throttled_events'] / max(1, stats['total_events']) * 100
        )
        return stats
    
    def set_event_filter_enabled(self, enabled: bool):
        """启用/禁用事件过滤器"""
        self._event_filter_enabled = enabled
        self.logger.info(f"事件过滤器已{'启用' if enabled else '禁用'}")
    
    def set_throttle_interval(self, interval_ms: int):
        """设置节流间隔"""
        self._event_throttle_ms = max(1, interval_ms)
        self.logger.info(f"事件节流间隔设置为: {self._event_throttle_ms}ms")


# 全局实例
_global_signal_dispatcher: Optional[OptimizedSignalDispatcher] = None
_global_event_optimizer: Optional[UIEventOptimizer] = None


def get_signal_dispatcher() -> OptimizedSignalDispatcher:
    """获取全局信号分发器"""
    global _global_signal_dispatcher
    if _global_signal_dispatcher is None:
        _global_signal_dispatcher = OptimizedSignalDispatcher()
    return _global_signal_dispatcher


def get_event_optimizer() -> UIEventOptimizer:
    """获取全局事件优化器"""
    global _global_event_optimizer
    if _global_event_optimizer is None:
        _global_event_optimizer = UIEventOptimizer()
    return _global_event_optimizer


# 便捷函数
def emit_optimized_signal(signal_type: str, *args, priority: int = 0):
    """便捷函数：发射优化信号"""
    dispatcher = get_signal_dispatcher()
    dispatcher.emit_signal(signal_type, *args, priority=priority)


def emit_immediate_signal(signal_type: str, *args):
    """便捷函数：立即发射信号"""
    dispatcher = get_signal_dispatcher()
    dispatcher.emit_signal(signal_type, *args, batch=False)
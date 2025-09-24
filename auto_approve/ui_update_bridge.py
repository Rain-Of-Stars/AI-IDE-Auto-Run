# -*- coding: utf-8 -*-
"""
UI更新桥接器 - 连接非阻塞进度管理器和UI组件

解决进度条卡顿问题的关键组件：
1. 连接NonBlockingProgressManager和QProgressBar
2. 提供零延迟的UI更新机制
3. 防止UI线程阻塞
4. 智能节流和批处理
"""

from __future__ import annotations
import time
from typing import Dict, Any, Optional, Callable
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QObject, Signal, QTimer, QElapsedTimer, Qt
from PySide6.QtWidgets import QProgressBar, QLabel

from auto_approve.logger_manager import get_logger
from auto_approve.optimized_ui_manager import (
    get_progress_manager, 
    NonBlockingProgressManager,
    OptimizedUIUpdate
)


class UIUpdateBridge(QObject):
    """UI更新桥接器 - 连接非阻塞进度管理器和UI组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        
        # 获取全局进度管理器
        self._progress_manager = get_progress_manager()
        
        # UI组件映射
        self._progress_bars: Dict[str, QProgressBar] = {}
        self._status_labels: Dict[str, QLabel] = {}
        self._custom_handlers: Dict[str, Callable] = {}
        
        # 性能优化
        self._last_update_time: Dict[str, float] = {}
        self._update_throttle_ms = 16  # 约60FPS
        self._enable_throttling = True
        
        # 连接信号
        self._connect_signals()
        
        # 启动性能监控
        self._start_performance_monitoring()
        
        self.logger.info("UI更新桥接器已初始化")
    
    def _connect_signals(self):
        """连接进度管理器信号"""
        self._progress_manager.progress_updated.connect(self._on_progress_updated)
        self._progress_manager.status_updated.connect(self._on_status_updated)
        self._progress_manager.critical_update.connect(self._on_critical_update)
    
    def register_progress_bar(self, widget_id: str, progress_bar: QProgressBar):
        """注册进度条"""
        self._progress_bars[widget_id] = progress_bar
        self._last_update_time[widget_id] = 0.0
        
        # 设置进度条属性
        progress_bar.setTextVisible(True)
        progress_bar.setFormat("%p%")
        progress_bar.setAlignment(Qt.AlignCenter)
        
        self.logger.debug(f"注册进度条: {widget_id}")
    
    def register_status_label(self, widget_id: str, status_label: QLabel):
        """注册状态标签"""
        self._status_labels[widget_id] = status_label
        self._last_update_time[widget_id] = 0.0
        
        self.logger.debug(f"注册状态标签: {widget_id}")
    
    def register_custom_handler(self, widget_id: str, handler: Callable):
        """注册自定义处理器"""
        self._custom_handlers[widget_id] = handler
        self.logger.debug(f"注册自定义处理器: {widget_id}")
    
    def unregister_widget(self, widget_id: str):
        """注销组件"""
        if widget_id in self._progress_bars:
            del self._progress_bars[widget_id]
        if widget_id in self._status_labels:
            del self._status_labels[widget_id]
        if widget_id in self._custom_handlers:
            del self._custom_handlers[widget_id]
        if widget_id in self._last_update_time:
            del self._last_update_time[widget_id]
        
        self.logger.debug(f"注销组件: {widget_id}")
    
    @QtCore.Slot(str, int)
    def _on_progress_updated(self, widget_id: str, progress_value: int):
        """处理进度更新"""
        if widget_id not in self._progress_bars:
            return
        
        # 节流检查
        if self._enable_throttling and self._should_throttle_update(widget_id):
            return
        
        # 使用QTimer.singleShot确保在主线程执行
        QtCore.QTimer.singleShot(0, lambda: self._update_progress_bar(widget_id, progress_value))
    
    @QtCore.Slot(str, str)
    def _on_status_updated(self, widget_id: str, status_text: str):
        """处理状态更新"""
        if widget_id not in self._status_labels:
            return
        
        # 节流检查
        if self._enable_throttling and self._should_throttle_update(widget_id):
            return
        
        # 使用QTimer.singleShot确保在主线程执行
        QtCore.QTimer.singleShot(0, lambda: self._update_status_label(widget_id, status_text))
    
    @QtCore.Slot(str, dict)
    def _on_critical_update(self, widget_id: str, data: Dict[str, Any]):
        """处理关键更新（无节流）"""
        # 关键更新直接处理，不节流
        
        # 使用QTimer.singleShot确保在主线程执行
        QtCore.QTimer.singleShot(0, lambda: self._handle_critical_update(widget_id, data))
    
    def _should_throttle_update(self, widget_id: str) -> bool:
        """检查是否应该节流更新"""
        current_time = time.time()
        last_time = self._last_update_time.get(widget_id, 0.0)
        
        # 检查时间间隔
        if current_time - last_time < (self._update_throttle_ms / 1000.0):
            return True
        
        self._last_update_time[widget_id] = current_time
        return False
    
    def _update_progress_bar(self, widget_id: str, progress_value: int):
        """更新进度条（在主线程执行）"""
        try:
            progress_bar = self._progress_bars.get(widget_id)
            if progress_bar and progress_bar.isVisible():
                # 确保值在有效范围内
                progress_value = max(0, min(100, progress_value))
                
                # 只有值真的改变了才更新
                if progress_bar.value() != progress_value:
                    progress_bar.setValue(progress_value)
                    
                    # 如果进度条有文本格式，更新显示
                    if progress_bar.textVisible():
                        # 可以在这里添加更多自定义文本格式
                        pass
        except Exception as e:
            self.logger.error(f"更新进度条失败 {widget_id}: {e}")
    
    def _update_status_label(self, widget_id: str, status_text: str):
        """更新状态标签（在主线程执行）"""
        try:
            status_label = self._status_labels.get(widget_id)
            if status_label and status_label.isVisible():
                # 只有文本真的改变了才更新
                if status_label.text() != status_text:
                    status_label.setText(status_text)
                    
                    # 可选：根据状态调整样式
                    self._update_status_style(status_label, status_text)
        except Exception as e:
            self.logger.error(f"更新状态标签失败 {widget_id}: {e}")
    
    def _handle_critical_update(self, widget_id: str, data: Dict[str, Any]):
        """处理关键更新（在主线程执行）"""
        try:
            # 首先尝试自定义处理器
            if widget_id in self._custom_handlers:
                self._custom_handlers[widget_id](data)
                return
            
            # 如果没有自定义处理器，尝试默认处理
            if 'progress' in data and widget_id in self._progress_bars:
                self._update_progress_bar(widget_id, data['progress'])
            
            if 'status' in data and widget_id in self._status_labels:
                self._update_status_label(widget_id, data['status'])
                
        except Exception as e:
            self.logger.error(f"处理关键更新失败 {widget_id}: {e}")
    
    def _update_status_style(self, label: QLabel, status_text: str):
        """根据状态文本更新标签样式"""
        try:
            # 根据状态关键词调整样式
            if any(keyword in status_text.lower() for keyword in ['错误', '失败', 'error', 'fail']):
                label.setStyleSheet("color: #ff4444; font-weight: bold;")
            elif any(keyword in status_text.lower() for keyword in ['警告', 'warning', 'warn']):
                label.setStyleSheet("color: #ff8800; font-weight: bold;")
            elif any(keyword in status_text.lower() for keyword in ['成功', '完成', 'success', 'complete']):
                label.setStyleSheet("color: #44ff44; font-weight: bold;")
            elif any(keyword in status_text.lower() for keyword in ['正在', '查找', '搜索', 'searching']):
                label.setStyleSheet("color: #4488ff; font-weight: normal;")
            else:
                label.setStyleSheet("")  # 恢复默认样式
        except Exception as e:
            self.logger.debug(f"更新状态样式失败: {e}")
    
    def _start_performance_monitoring(self):
        """启动性能监控"""
        self._performance_stats = {
            'total_updates': 0,
            'processed_updates': 0,
            'throttled_updates': 0,
            'avg_update_time': 0.0
        }
        
        # 定期清理过期的组件注册
        # 修复：以前使用局部变量导致QTimer被GC，定时器失效；改为成员变量并指定父对象，确保生命周期。
        if not hasattr(self, '_cleanup_timer') or self._cleanup_timer is None:
            self._cleanup_timer = QTimer(self)
        self._cleanup_timer.timeout.connect(self._cleanup_expired_registrations)
        if not self._cleanup_timer.isActive():
            self._cleanup_timer.start(60000)  # 每分钟清理一次
    
    def _cleanup_expired_registrations(self):
        """清理过期的组件注册"""
        try:
            # 检查进度条是否仍然有效
            expired_widgets = []
            for widget_id, progress_bar in self._progress_bars.items():
                try:
                    # 尝试访问进度条，如果已销毁会抛出异常
                    if not progress_bar.isVisible() and not progress_bar.isEnabled():
                        expired_widgets.append(widget_id)
                except (RuntimeError, AttributeError):
                    expired_widgets.append(widget_id)
            
            # 清理过期组件
            for widget_id in expired_widgets:
                self.unregister_widget(widget_id)
                
            if expired_widgets:
                self.logger.debug(f"清理了 {len(expired_widgets)} 个过期组件")
                
        except Exception as e:
            self.logger.error(f"清理过期注册失败: {e}")
    
    def set_throttle_enabled(self, enabled: bool):
        """启用/禁用节流"""
        self._enable_throttling = enabled
        self.logger.info(f"节流已{'启用' if enabled else '禁用'}")
    
    def set_throttle_interval(self, interval_ms: int):
        """设置节流间隔"""
        self._update_throttle_ms = max(1, interval_ms)
        self.logger.info(f"节流间隔设置为: {self._update_throttle_ms}ms")
    
    def force_update_all(self):
        """强制更新所有组件"""
        # 禁用节流
        old_throttling = self._enable_throttling
        self._enable_throttling = False
        
        try:
            # 强制处理所有待处理的更新
            self._progress_manager.force_process_updates()
        finally:
            # 恢复节流设置
            self._enable_throttling = old_throttling
    
    def get_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        manager_stats = self._progress_manager.get_stats()
        
        return {
            'bridge_stats': {
                'registered_progress_bars': len(self._progress_bars),
                'registered_status_labels': len(self._status_labels),
                'custom_handlers': len(self._custom_handlers),
                'throttling_enabled': self._enable_throttling,
                'throttle_interval_ms': self._update_throttle_ms
            },
            'manager_stats': manager_stats
        }


# 全局实例
_global_ui_bridge: Optional[UIUpdateBridge] = None


def get_ui_bridge() -> UIUpdateBridge:
    """获取全局UI更新桥接器"""
    global _global_ui_bridge
    if _global_ui_bridge is None:
        _global_ui_bridge = UIUpdateBridge()
    return _global_ui_bridge


# 便捷函数
def register_progress_bar(widget_id: str, progress_bar: QProgressBar):
    """便捷函数：注册进度条"""
    bridge = get_ui_bridge()
    bridge.register_progress_bar(widget_id, progress_bar)


def register_status_label(widget_id: str, status_label: QLabel):
    """便捷函数：注册状态标签"""
    bridge = get_ui_bridge()
    bridge.register_status_label(widget_id, status_label)


def setup_progress_updates(progress_bar: QProgressBar, status_label: QLabel = None, widget_id: str = None):
    """便捷函数：设置进度更新
    
    Args:
        progress_bar: 进度条组件
        status_label: 状态标签组件（可选）
        widget_id: 组件ID（可选，如果不提供会自动生成）
    """
    import uuid
    
    if widget_id is None:
        widget_id = f"progress_{uuid.uuid4().hex[:8]}"
    
    bridge = get_ui_bridge()
    bridge.register_progress_bar(widget_id, progress_bar)
    
    if status_label:
        bridge.register_status_label(widget_id, status_label)
    
    return widget_id

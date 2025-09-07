#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UI性能测试 - 验证配置保存不阻塞界面
测试用例主要验证配置保存操作的UI流畅性
"""
import sys
import time
import os
import threading
from PySide6 import QtWidgets, QtCore, QtTest

# 添加项目路径到sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import AppConfig, save_config, load_config
from auto_approve.gui_responsiveness_manager import get_gui_responsiveness_manager, schedule_ui_update
from auto_approve.gui_performance_monitor import get_gui_performance_monitor


class TestUITransition:
    """测试UI转换时的流畅性"""
    
    def test_config_save_ui_responsiveness(self, qapp):
        """测试配置保存期间UI的响应性"""
        # 创建基础配置
        base_config = AppConfig(
            monitor_index=1,
            threshold=0.88,
            template_path="template.png",
            interval_ms=800
        )
        
        # 记录UI响应监控开始的性能指标
        monitor = get_gui_performance_monitor()
        monitor.set_thresholds(response_ms=100)  # 设置100ms的严格阈值
        monitor.start_monitoring()
        
        # 准备配置-此时不执行保存而是立即触发配置更新
        save_start_time = time.time()
        
        # 模拟保存配置 - 配置管理器应该立即返回
        save_config(base_config)
        
        # 检查保存操作是否立即返回（应该在10ms内）
        save_duration = (time.time() - save_start_time) * 1000
        assert save_duration < 10, f"保存操作应该立即返回，但用时 {save_duration}ms"
        
        # 让UI事件循环处理
        QtCore.QTimer.singleShot(50, qapp.quit)  # 50ms后退出
        qapp.exec()
        
        # 检查UI响应性
        metrics = monitor.get_metrics_history()
        if metrics:
            # 检查最后几个周期是否有卡顿
            recent_metrics = metrics[-5:]
            avg_response_time = sum(m.response_time_ms for m in recent_metrics) / len(recent_metrics)
            
            # 配置保存期间平均响应时间不应超过阈值
            assert avg_response_time < 100, f"配置保存期间UI平均响应时间 {avg_response_time}ms 超过了100ms阈值"
            
            # 不应有超过阈值的卡顿
            unresponsive_count = sum(1 for m in recent_metrics if not m.is_responsive)
            assert unresponsive_count == 0, f"配置保存期间不应有卡顿，但检测到 {unresponsive_count} 次"
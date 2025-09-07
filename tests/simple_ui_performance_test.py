#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的UI性能测试 - 验证配置保存流畅性
直接运行，无需复杂测试框架依赖
"""
import sys
import time
import os
from PySide6 import QtWidgets, QtCore
from threading import Thread

# 添加项目路径到sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import AppConfig, save_config, load_config
from auto_approve.gui_responsiveness_manager import get_gui_responsiveness_manager
from auto_approve.gui_performance_monitor import get_gui_performance_monitor, start_gui_monitoring

def test_config_save_performance():
    """测试配置保存的性能表现"""
    print("正在启动UI性能测试...")
    
    # 创建Qt应用
    app = QtWidgets.QApplication([])
    
    # 初始化性能监控
    monitor = get_gui_performance_monitor()
    monitor.set_thresholds(response_ms=50)  # 严格的50ms响应阈值
    start_gui_monitoring()
    
    # 初始化响应性管理器
    gui_manager = get_gui_responsiveness_manager()
    
    print("✓ 初始化完成，开始性能监控")
    
    # 创建测试配置
    config = AppConfig(
        monitor_index=1,
        threshold=0.9,
        template_paths=["assets/images/template1.png", "assets/images/template2.png"],
        interval_ms=500,
        auto_start_scan=True,
        enable_logging=False
    )
    
    print("正在执行配置保存测试...")
    
    # 记录开始时间
    start_time = time.time()
    response_times = []
    
    # 测试中持续监控UI响应性
    def monitor_responsiveness():
        for i in range(10):  # 监控10个周期
            if monitor._monitoring:
                current_metrics = monitor.get_current_metrics()
                if current_metrics:
                    response_times.append(current_metrics.response_time_ms)
                    if current_metrics.response_time_ms > 50:
                        print(f"⚠️ 检测到慢响应: {current_metrics.response_time_ms:.1f}ms")
            time.sleep(0.1)  # 100ms间隔
    
    # 启动监控线程
    monitor_thread = Thread(target=monitor_responsiveness, daemon=True)
    monitor_thread.start()
    
    # 执行异步配置保存
    save_start_time = time.time()
    save_result = save_config(config)
    save_duration = (time.time() - save_start_time) * 1000  # 转换为毫秒
    
    # 让事件循环处理异步操作
    QtCore.QTimer.singleShot(500, app.quit)
    app.exec()
    
    # 等待监控线程完成
    monitor_thread.join(timeout=1)
    
    # 分析结果
    print(f"\n=== 测试结果 ===")
    print(f"配置保存函数返回时间: {save_duration:.1f}ms")
    print(f"测试配置: 2个模板, {len(getattr(config, 'debug_image_dir', ''))} 项配置")
    
    if response_times:
        avg_response = sum(response_times) / len(response_times)
        max_response = max(response_times)
        unresponsive_count = sum(1 for rt in response_times if rt > 50)
        
        print(f"UI平均响应时间: {avg_response:.1f}ms")
        print(f"最大响应时间: {max_response:.1f}ms")
        print(f"超过阈值次数: {unresponsive_count}/{len(response_times)}")
        
        # 性能评价
        if avg_response < 50 and max_response < 100 and unresponsive_count == 0:
            print("✅ 性能优秀：配置保存期间UI保持流畅")
            return True
        elif avg_response < 100 and max_response < 200 and unresponsive_count <= 2:
            print("⚠️ 性能良好：配置保存期间UI基本流畅，偶有小卡顿")
            return True
        else:
            print("❌ 性能需要改进：配置保存影响UI流畅性")
            return False
    else:
        print("⚠️ 未能收集到UI响应数据")
        return False

def main():
    """主函数"""
    print("=== UI响应性性能测试 ===")
    print("测试配置保存期间的UI流畅性")
    print()
    
    success = test_config_save_performance()
    
    print("\n=== 测试完成 ===")
    return 0 if success else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
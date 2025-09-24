# -*- coding: utf-8 -*-
"""
测试信号机制
"""

import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.auto_hwnd_updater import AutoHWNDUpdater
from auto_approve.config_manager import load_config
from PySide6 import QtWidgets, QtCore


def test_signal_mechanism():
    """测试信号机制"""
    print("=== 测试信号机制 ===")
    
    try:
        # 创建应用实例
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication(sys.argv)
        
        # 创建自动更新器
        config = load_config()
        updater = AutoHWNDUpdater()
        updater.set_config(config)
        
        # 设置信号处理
        signal_received = False
        received_hwnd = 0
        
        def on_hwnd_updated(hwnd: int, process_name: str):
            nonlocal signal_received, received_hwnd
            signal_received = True
            received_hwnd = hwnd
            print(f"信号收到！HWND: {hwnd}, 进程: {process_name}")
        
        # 连接信号
        updater.hwnd_updated.connect(on_hwnd_updated)
        print("信号已连接")
        
        # 启动更新器
        updater.start()
        print("更新器已启动")
        
        # 等待智能查找器工作
        import time
        time.sleep(5)
        
        # 检查结果
        print(f"信号接收状态: {signal_received}")
        print(f"接收到的HWND: {received_hwnd}")
        print(f"更新器当前HWND: {updater.get_current_hwnd()}")
        
        # 停止
        updater.stop()
        
        if signal_received:
            print("✓ 信号机制正常工作")
            return True
        else:
            print("✗ 信号机制异常")
            return False
            
    except Exception as e:
        print(f"信号机制测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_manual_signal():
    """手动触发信号"""
    print("\n=== 测试手动信号触发 ===")
    
    try:
        # 创建应用实例
        app = QtWidgets.QApplication.instance()
        if app is None:
            app = QtWidgets.QApplication(sys.argv)
        
        # 创建自动更新器
        config = load_config()
        updater = AutoHWNDUpdater()
        updater.set_config(config)
        
        # 设置信号处理
        signal_received = False
        received_hwnd = 0
        
        def on_hwnd_updated(hwnd: int, process_name: str):
            nonlocal signal_received, received_hwnd
            signal_received = True
            received_hwnd = hwnd
            print(f"手动信号收到！HWND: {hwnd}, 进程: {process_name}")
        
        # 连接信号
        updater.hwnd_updated.connect(on_hwnd_updated)
        
        # 手动触发回调
        test_hwnd = 555666777
        print(f"手动触发信号: {test_hwnd}")
        updater._on_smart_process_found(test_hwnd, "TestProcess.exe", "Test Window")
        
        # 等待处理
        import time
        time.sleep(0.5)
        
        # 检查结果
        print(f"信号接收状态: {signal_received}")
        print(f"接收到的HWND: {received_hwnd}")
        print(f"更新器当前HWND: {updater.get_current_hwnd()}")
        
        if signal_received and received_hwnd == test_hwnd:
            print("✓ 手动信号触发正常")
            return True
        else:
            print("✗ 手动信号触发异常")
            return False
            
    except Exception as e:
        print(f"手动信号测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("测试信号机制\n")
    
    try:
        # 运行测试
        test_results = []
        
        test_results.append(test_signal_mechanism())
        test_results.append(test_manual_signal())
        
        # 汇总结果
        print(f"\n=== 测试结果汇总 ===")
        passed = sum(test_results)
        total = len(test_results)
        print(f"通过测试: {passed}/{total}")
        
        if passed == total:
            print("\n✅ 信号机制正常工作")
        else:
            print("\n❌ 信号机制存在问题")
            
    except Exception as e:
        print(f"测试过程中发生异常: {e}")
        return False
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
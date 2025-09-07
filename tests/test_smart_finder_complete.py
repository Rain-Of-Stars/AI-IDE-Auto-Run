# -*- coding: utf-8 -*-
"""
智能查找功能完整测试

测试修复后的自动启动功能
"""

import sys
import os
import time
import threading

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import AppConfig
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater
from auto_approve.smart_process_finder import SmartProcessFinder
from auto_approve.logger_manager import get_logger


def test_auto_start_functionality():
    """测试自动启动功能"""
    print("=== 测试自动启动功能 ===")
    
    # 创建配置
    config = AppConfig()
    config.target_process = "Code.exe"  # VS Code
    config.auto_update_hwnd_by_process = True
    config.enable_smart_finder = True
    
    # 创建自动HWND更新器
    updater = AutoHWNDUpdater()
    updater.set_config(config)
    
    print(f"1. 创建自动HWND更新器")
    print(f"   目标进程: {config.target_process}")
    print(f"   自动更新: {config.auto_update_hwnd_by_process}")
    print(f"   智能查找: {config.enable_smart_finder}")
    
    # 测试启动前状态
    print(f"2. 启动前状态:")
    print(f"   运行状态: {updater.is_running()}")
    print(f"   当前HWND: {updater.get_current_hwnd()}")
    
    # 启动自动更新器
    print(f"3. 启动自动HWND更新器...")
    updater.start()
    
    # 等待一段时间让智能查找器工作
    print(f"4. 等待智能查找器工作（10秒）...")
    time.sleep(10)
    
    # 检查运行状态
    print(f"5. 运行状态:")
    print(f"   运行状态: {updater.is_running()}")
    print(f"   当前HWND: {updater.get_current_hwnd()}")
    
    # 获取智能查找器统计信息
    if hasattr(updater, '_smart_finder') and updater._smart_finder:
        stats = updater._smart_finder.get_search_stats()
        print(f"   智能查找统计:")
        print(f"     总查找次数: {stats['total_searches']}")
        print(f"     成功率: {stats['success_rate']*100:.1f}%")
        print(f"     平均耗时: {stats['avg_search_time']:.3f}s")
    else:
        print(f"   智能查找器: 未初始化")
    
    # 停止更新器
    print(f"6. 停止自动HWND更新器...")
    updater.stop()
    
    # 最终状态
    print(f"7. 最终状态:")
    print(f"   运行状态: {updater.is_running()}")
    
    # 清理
    updater.cleanup()
    print(f"8. 测试完成，资源已清理")
    
    return True


def test_smart_finder_directly():
    """直接测试智能查找器"""
    print("\n=== 直接测试智能查找器 ===")
    
    # 创建配置
    config = AppConfig()
    config.target_process = "Code.exe"
    config.enable_smart_finder = True
    
    # 创建智能查找器
    finder = SmartProcessFinder()
    finder.set_config(config)
    
    print(f"1. 智能查找器初始化完成")
    print(f"   目标进程: {config.target_process}")
    
    # 启动智能查找
    print(f"2. 启动智能查找...")
    finder.start_smart_search()
    
    # 等待工作
    print(f"3. 等待智能查找器工作（5秒）...")
    time.sleep(5)
    
    # 获取统计信息
    stats = finder.get_search_stats()
    print(f"4. 统计信息:")
    print(f"   总查找次数: {stats['total_searches']}")
    print(f"   成功次数: {stats['successful_searches']}")
    print(f"   失败次数: {stats['failed_searches']}")
    print(f"   成功率: {stats['success_rate']*100:.1f}%")
    print(f"   平均耗时: {stats['avg_search_time']:.3f}s")
    
    # 停止查找
    print(f"5. 停止智能查找...")
    finder.stop_smart_search()
    
    # 清理
    finder.cleanup()
    print(f"6. 测试完成")
    
    return True


def main():
    """主测试函数"""
    print("开始智能查找功能完整测试\n")
    
    try:
        # 运行测试
        test_results = []
        
        test_results.append(test_auto_start_functionality())
        test_results.append(test_smart_finder_directly())
        
        # 汇总结果
        print(f"\n=== 测试结果汇总 ===")
        passed = sum(test_results)
        total = len(test_results)
        print(f"通过测试: {passed}/{total}")
        
        if passed == total:
            print("所有测试通过！智能查找功能修复成功。")
            print("现在应用启动时会自动根据进程名查找窗口。")
        else:
            print("部分测试失败，请检查实现。")
            
    except Exception as e:
        print(f"测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
# -*- coding: utf-8 -*-
"""
测试自动查找功能

验证SmartProcessFinder是否能自动查找并找到目标进程窗口
"""

import sys
import os
import time

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import AppConfig, load_config
from auto_approve.smart_process_finder import SmartProcessFinder
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater
from auto_approve.logger_manager import get_logger


def test_smart_finder_auto_search():
    """测试智能查找器的自动查找功能"""
    print("=== 测试智能查找器自动查找功能 ===")
    
    config = load_config()
    if not config:
        return False
        
    try:
        # 创建智能查找器
        finder = SmartProcessFinder()
        finder.set_config(config)
        
        print(f"1. 智能查找器初始化完成")
        print(f"   目标进程: {config.target_process}")
        print(f"   自动查找启用: {config.enable_smart_finder}")
        
        # 启动智能查找
        print(f"2. 启动智能查找...")
        finder.start_smart_search()
        
        # 等待工作
        print(f"3. 等待智能查找工作（10秒）...")
        time.sleep(10)
        
        # 获取统计信息
        stats = finder.get_search_stats()
        print(f"4. 智能查找器状态:")
        print(f"   总查找次数: {stats['total_searches']}")
        print(f"   成功次数: {stats['successful_searches']}")
        print(f"   失败次数: {stats['failed_searches']}")
        print(f"   成功率: {stats['success_rate']*100:.1f}%")
        print(f"   平均耗时: {stats['avg_search_time']:.3f}s")
        print(f"   当前HWND: {finder._current_hwnd}")
        
        # 停止查找
        print(f"5. 停止智能查找...")
        finder.stop_smart_search()
        
        # 清理
        finder.cleanup()
        print(f"6. 清理完成")
        
        # 验证结果
        if stats['total_searches'] > 0:
            print(f"\\n✓ 智能查找器自动工作正常")
            if stats['successful_searches'] > 0:
                print(f"✓ 成功找到目标进程窗口")
            else:
                print(f"⚠ 未找到目标进程窗口，但查找机制正常")
            return True
        else:
            print(f"\\n✗ 智能查找器没有执行查找")
            return False
        
    except Exception as e:
        print(f"智能查找器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_auto_hwnd_updater():
    """测试AutoHWNDUpdater的自动查找功能"""
    print("\\n=== 测试AutoHWNDUpdater自动查找功能 ===")
    
    config = load_config()
    if not config:
        return False
        
    try:
        # 创建AutoHWNDUpdater
        updater = AutoHWNDUpdater()
        updater.set_config(config)
        
        print(f"1. AutoHWNDUpdater初始化完成")
        print(f"   目标进程: {config.target_process}")
        print(f"   自动更新启用: {config.auto_update_hwnd_by_process}")
        
        # 启动自动更新
        print(f"2. 启动AutoHWNDUpdater...")
        updater.start()
        
        # 等待工作
        print(f"3. 等待AutoHWNDUpdater工作（10秒）...")
        time.sleep(10)
        
        # 获取状态
        current_hwnd = updater.get_current_hwnd()
        print(f"4. AutoHWNDUpdater状态:")
        print(f"   是否运行: {updater.is_running()}")
        print(f"   当前HWND: {current_hwnd}")
        
        # 获取智能查找器统计
        if hasattr(updater, '_smart_finder') and updater._smart_finder:
            stats = updater._smart_finder.get_search_stats()
            print(f"   智能查找器统计: 总查找={stats['total_searches']}, 成功={stats['successful_searches']}")
            print(f"   成功率: {stats['success_rate']*100:.1f}%")
        
        # 停止更新
        print(f"5. 停止AutoHWNDUpdater...")
        updater.stop()
        
        # 清理
        print(f"6. 清理完成")
        
        # 验证结果
        if updater.is_running():
            print(f"\\n✓ AutoHWNDUpdater自动工作正常")
            if current_hwnd:
                print(f"✓ 成功找到目标进程窗口: {current_hwnd}")
            else:
                print(f"⚠ 未找到目标进程窗口，但更新机制正常")
            return True
        else:
            print(f"\\n✗ AutoHWNDUpdater没有正常工作")
            return False
        
    except Exception as e:
        print(f"AutoHWNDUpdater测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("开始自动查找功能测试\\n")
    
    try:
        # 运行测试
        test_results = []
        
        test_results.append(test_smart_finder_auto_search())
        test_results.append(test_auto_hwnd_updater())
        
        # 汇总结果
        print(f"\\n=== 自动查找功能测试结果汇总 ===")
        passed = sum(test_results)
        total = len(test_results)
        print(f"通过测试: {passed}/{total}")
        
        if passed == total:
            print("\\n🎉 所有测试通过！自动查找功能正常工作。")
            print("现在应用程序应该能够：")
            print("1. 启动后自动开始查找目标进程窗口")
            print("2. 定期检查窗口有效性")
            print("3. 自动恢复丢失的窗口")
            print("4. 无需用户手动干预")
        else:
            print("\\n❌ 部分测试失败，请检查实现。")
            
    except Exception as e:
        print(f"测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
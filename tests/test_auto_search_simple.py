# -*- coding: utf-8 -*-
"""
简化的自动查找功能测试
"""

import sys
import os
import time

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import load_config
from auto_approve.smart_process_finder import SmartProcessFinder
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater


def test_auto_search():
    """测试自动查找功能"""
    print("=== 测试自动查找功能 ===")
    
    config = load_config()
    if not config:
        print("配置加载失败")
        return False
        
    try:
        # 测试SmartProcessFinder
        print("1. 测试SmartProcessFinder...")
        finder = SmartProcessFinder()
        finder.set_config(config)
        
        print(f"   目标进程: {config.target_process}")
        print(f"   启动智能查找...")
        finder.start_smart_search()
        
        time.sleep(5)
        
        stats = finder.get_search_stats()
        print(f"   查找统计: 总次数={stats['total_searches']}, 成功={stats['successful_searches']}")
        print(f"   当前HWND: {finder._current_hwnd}")
        
        finder.stop_smart_search()
        finder.cleanup()
        
        # 测试AutoHWNDUpdater
        print("2. 测试AutoHWNDUpdater...")
        updater = AutoHWNDUpdater()
        updater.set_config(config)
        
        print(f"   启动自动更新...")
        updater.start()
        
        time.sleep(5)
        
        print(f"   运行状态: {updater.is_running()}")
        print(f"   当前HWND: {updater.get_current_hwnd()}")
        
        # 先获取状态再停止
        finder_success = stats['total_searches'] > 0 and stats['successful_searches'] > 0
        updater_success = updater.is_running() and updater.get_current_hwnd() > 0
        
        updater.stop()
        
        # 验证结果
        
        if finder_success and updater_success:
            print("\n[成功] 自动查找功能正常工作")
            print(f"  - SmartProcessFinder: 执行了{stats['total_searches']}次查找，成功{stats['successful_searches']}次")
            print(f"  - AutoHWNDUpdater: 正在运行，当前HWND={updater.get_current_hwnd()}")
            return True
        else:
            print("\n[失败] 自动查找功能异常")
            print(f"  - SmartProcessFinder: 查找{stats['total_searches']}次，成功{stats['successful_searches']}次")
            print(f"  - AutoHWNDUpdater: 运行状态={updater.is_running()}，HWND={updater.get_current_hwnd()}")
            return False
            
    except Exception as e:
        print(f"测试失败: {e}")
        return False


if __name__ == "__main__":
    success = test_auto_search()
    print(f"\n测试结果: {'通过' if success else '失败'}")
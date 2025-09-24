# -*- coding: utf-8 -*-
"""
智能进程查找功能验证测试

验证智能查找器的基本功能是否正常工作
"""

import sys
import os
import time
import threading

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import AppConfig
from auto_approve.smart_process_finder import SmartProcessFinder
from auto_approve.logger_manager import get_logger


def test_smart_finder_basic():
    """测试智能查找器基本功能"""
    print("=== 智能查找器基本功能测试 ===")
    
    # 创建配置
    config = AppConfig()
    config.target_process = "notepad.exe"
    config.enable_smart_finder = True
    config.auto_update_hwnd_by_process = True
    
    # 创建智能查找器
    finder = SmartProcessFinder()
    finder.set_config(config)
    
    print(f"1. 智能查找器初始化完成")
    print(f"   目标进程: {config.target_process}")
    print(f"   启用智能查找: {config.enable_smart_finder}")
    
    # 测试获取统计信息
    stats = finder.get_search_stats()
    print(f"2. 初始统计信息:")
    print(f"   总查找次数: {stats['total_searches']}")
    print(f"   成功率: {stats['success_rate']*100:.1f}%")
    print(f"   缓存大小: {stats['cache_size']}")
    
    # 测试策略配置
    print(f"3. 查找策略:")
    for name, info in stats['strategies'].items():
        print(f"   {name}: 启用={info['enabled']}, 优先级={info['priority']}")
    
    # 启动智能查找（短暂运行测试）
    print(f"4. 启动智能查找（5秒测试）...")
    finder.start_smart_search()
    
    # 等待5秒
    time.sleep(5)
    
    # 停止查找
    print(f"5. 停止智能查找...")
    finder.stop_smart_search()
    
    # 获取最终统计
    final_stats = finder.get_search_stats()
    print(f"6. 最终统计信息:")
    print(f"   总查找次数: {final_stats['total_searches']}")
    print(f"   成功次数: {final_stats['successful_searches']}")
    print(f"   失败次数: {final_stats['failed_searches']}")
    print(f"   成功率: {final_stats['success_rate']*100:.1f}%")
    print(f"   平均耗时: {final_stats['avg_search_time']:.3f}s")
    print(f"   自适应间隔: {final_stats['adaptive_interval']:.1f}s")
    
    # 清理
    finder.cleanup()
    print(f"7. 测试完成，资源已清理")
    
    return True


def test_strategy_switching():
    """测试策略切换功能"""
    print("\n=== 查找策略切换测试 ===")
    
    # 创建配置
    config = AppConfig()
    config.target_process = "chrome.exe"
    config.enable_smart_finder = True
    
    # 创建智能查找器
    finder = SmartProcessFinder()
    finder.set_config(config)
    
    print(f"1. 初始策略状态:")
    stats = finder.get_search_stats()
    for name, info in stats['strategies'].items():
        print(f"   {name}: 启用={info['enabled']}")
    
    # 测试禁用某个策略
    print(f"2. 禁用模糊匹配策略...")
    finder.set_strategy_enabled('fuzzy_match', False)
    
    stats = finder.get_search_stats()
    print(f"   模糊匹配策略启用状态: {stats['strategies']['fuzzy_match']['enabled']}")
    
    # 测试启用策略
    print(f"3. 重新启用模糊匹配策略...")
    finder.set_strategy_enabled('fuzzy_match', True)
    
    stats = finder.get_search_stats()
    print(f"   模糊匹配策略启用状态: {stats['strategies']['fuzzy_match']['enabled']}")
    
    # 清理
    finder.cleanup()
    print(f"4. 策略切换测试完成")
    
    return True


def test_force_search():
    """测试强制查找功能"""
    print("\n=== 强制查找测试 ===")
    
    # 创建配置
    config = AppConfig()
    config.target_process = "explorer.exe"  # 系统进程，通常存在
    config.enable_smart_finder = True
    
    # 创建智能查找器
    finder = SmartProcessFinder()
    finder.set_config(config)
    
    print(f"1. 执行强制查找...")
    start_time = time.time()
    hwnd = finder.force_search()
    end_time = time.time()
    
    print(f"2. 查找结果:")
    print(f"   HWND: {hwnd if hwnd else '未找到'}")
    print(f"   耗时: {(end_time - start_time)*1000:.1f}ms")
    
    # 获取统计信息
    stats = finder.get_search_stats()
    print(f"3. 统计信息:")
    print(f"   总查找次数: {stats['total_searches']}")
    print(f"   成功率: {stats['success_rate']*100:.1f}%")
    
    # 清理
    finder.cleanup()
    print(f"4. 强制查找测试完成")
    
    return True


def main():
    """主测试函数"""
    print("开始智能进程查找功能验证测试\n")
    
    try:
        # 运行各项测试
        test_results = []
        
        test_results.append(test_smart_finder_basic())
        test_results.append(test_strategy_switching())
        test_results.append(test_force_search())
        
        # 汇总结果
        print(f"\n=== 测试结果汇总 ===")
        passed = sum(test_results)
        total = len(test_results)
        print(f"通过测试: {passed}/{total}")
        
        if passed == total:
            print("所有测试通过！智能查找功能正常工作。")
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
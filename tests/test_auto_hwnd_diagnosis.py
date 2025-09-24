# -*- coding: utf-8 -*-
"""
诊断AutoHWNDUpdater启动问题

详细检查AutoHWNDUpdater的启动条件和初始化流程
"""

import sys
import os
import time

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import AppConfig, load_config
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater
from auto_approve.smart_process_finder import SmartProcessFinder
from auto_approve.logger_manager import get_logger


def test_config_loading():
    """测试配置加载"""
    print("=== 测试配置加载 ===")
    
    try:
        # 加载配置
        config = load_config()
        print(f"1. 配置加载成功")
        print(f"   auto_update_hwnd_by_process: {config.auto_update_hwnd_by_process}")
        print(f"   enable_smart_finder: {config.enable_smart_finder}")
        print(f"   target_process: {config.target_process}")
        print(f"   target_hwnd: {config.target_hwnd}")
        
        return config
        
    except Exception as e:
        print(f"配置加载失败: {e}")
        return None


def test_auto_hwnd_updater_initialization():
    """测试AutoHWNDUpdater初始化"""
    print("\n=== 测试AutoHWNDUpdater初始化 ===")
    
    config = test_config_loading()
    if not config:
        return False
        
    try:
        # 创建AutoHWNDUpdater
        updater = AutoHWNDUpdater()
        print(f"1. AutoHWNDUpdater创建成功")
        
        # 设置配置
        updater.set_config(config)
        print(f"2. 配置设置成功")
        
        # 检查初始状态
        print(f"3. 初始状态检查:")
        print(f"   is_running(): {updater.is_running()}")
        print(f"   get_current_hwnd(): {updater.get_current_hwnd()}")
        
        # 检查智能查找器状态
        if hasattr(updater, '_smart_finder') and updater._smart_finder:
            print(f"   智能查找器: 已初始化")
            stats = updater._smart_finder.get_search_stats()
            print(f"   智能查找器状态: {stats}")
        else:
            print(f"   智能查找器: 未初始化")
        
        return updater
        
    except Exception as e:
        print(f"AutoHWNDUpdater初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_auto_hwnd_updater_start():
    """测试AutoHWNDUpdater启动"""
    print("\n=== 测试AutoHWNDUpdater启动 ===")
    
    updater = test_auto_hwnd_updater_initialization()
    if not updater:
        return False
        
    try:
        # 启动AutoHWNDUpdater
        print(f"1. 启动AutoHWNDUpdater...")
        updater.start()
        
        # 等待启动
        time.sleep(2)
        
        # 检查启动后状态
        print(f"2. 启动后状态检查:")
        print(f"   is_running(): {updater.is_running()}")
        print(f"   get_current_hwnd(): {updater.get_current_hwnd()}")
        
        # 检查智能查找器状态
        if hasattr(updater, '_smart_finder') and updater._smart_finder:
            print(f"   智能查找器: 已初始化")
            stats = updater._smart_finder.get_search_stats()
            print(f"   智能查找器统计: 总查找={stats['total_searches']}, 成功={stats['successful_searches']}")
        else:
            print(f"   智能查找器: 未初始化")
        
        # 等待智能查找器工作一段时间
        print(f"3. 等待智能查找器工作（10秒）...")
        time.sleep(10)
        
        # 再次检查状态
        print(f"4. 工作后状态检查:")
        print(f"   is_running(): {updater.is_running()}")
        print(f"   get_current_hwnd(): {updater.get_current_hwnd()}")
        
        if hasattr(updater, '_smart_finder') and updater._smart_finder:
            stats = updater._smart_finder.get_search_stats()
            print(f"   智能查找器统计: 总查找={stats['total_searches']}, 成功={stats['successful_searches']}")
            print(f"   成功率: {stats['success_rate']*100:.1f}%")
            print(f"   平均耗时: {stats['avg_search_time']:.3f}s")
        
        # 测试强制查找
        print(f"5. 测试强制查找...")
        hwnd = updater.force_search()
        print(f"   强制查找结果: {hwnd if hwnd else '未找到'}")
        
        return updater
        
    except Exception as e:
        print(f"AutoHWNDUpdater启动失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def test_smart_finder_directly():
    """直接测试智能查找器"""
    print("\n=== 直接测试智能查找器 ===")
    
    config = test_config_loading()
    if not config:
        return False
        
    try:
        # 创建智能查找器
        finder = SmartProcessFinder()
        print(f"1. 智能查找器创建成功")
        
        # 设置配置
        finder.set_config(config)
        print(f"2. 配置设置成功")
        
        # 启动智能查找
        print(f"3. 启动智能查找...")
        finder.start_smart_search()
        
        # 等待工作
        print(f"4. 等待智能查找工作（5秒）...")
        time.sleep(5)
        
        # 检查状态
        stats = finder.get_search_stats()
        print(f"5. 智能查找器状态:")
        print(f"   总查找次数: {stats['total_searches']}")
        print(f"   成功次数: {stats['successful_searches']}")
        print(f"   失败次数: {stats['failed_searches']}")
        print(f"   成功率: {stats['success_rate']*100:.1f}%")
        print(f"   平均耗时: {stats['avg_search_time']:.3f}s")
        
        # 测试强制查找
        print(f"6. 测试强制查找...")
        hwnd = finder.force_search()
        print(f"   强制查找结果: {hwnd if hwnd else '未找到'}")
        
        # 停止查找
        print(f"7. 停止智能查找...")
        finder.stop_smart_search()
        
        # 清理
        finder.cleanup()
        print(f"8. 清理完成")
        
        return True
        
    except Exception as e:
        print(f"智能查找器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_main_program_logic():
    """测试主程序逻辑"""
    print("\n=== 测试主程序逻辑 ===")
    
    config = test_config_loading()
    if not config:
        return False
        
    try:
        # 模拟主程序的初始化过程
        print(f"1. 模拟主程序初始化...")
        
        # 创建AutoHWNDUpdater
        updater = AutoHWNDUpdater()
        print(f"2. AutoHWNDUpdater创建成功")
        
        # 设置配置
        updater.set_config(config)
        print(f"3. 配置设置成功")
        
        # 检查是否应该自动启动
        should_auto_start = getattr(config, 'auto_update_hwnd_by_process', False)
        print(f"4. 检查自动启动条件:")
        print(f"   auto_update_hwnd_by_process: {should_auto_start}")
        print(f"   enable_smart_finder: {config.enable_smart_finder}")
        print(f"   target_process: {config.target_process}")
        
        if should_auto_start:
            print(f"5. 满足自动启动条件，启动AutoHWNDUpdater...")
            updater.start()
            
            # 等待启动
            time.sleep(2)
            
            print(f"6. 启动后状态:")
            print(f"   is_running(): {updater.is_running()}")
            print(f"   get_current_hwnd(): {updater.get_current_hwnd()}")
            
            # 等待工作
            print(f"7. 等待工作（10秒）...")
            time.sleep(10)
            
            print(f"8. 工作后状态:")
            print(f"   is_running(): {updater.is_running()}")
            print(f"   get_current_hwnd(): {updater.get_current_hwnd()}")
            
            if hasattr(updater, '_smart_finder') and updater._smart_finder:
                stats = updater._smart_finder.get_search_stats()
                print(f"   智能查找器统计: 总查找={stats['total_searches']}, 成功={stats['successful_searches']}")
            
            # 停止
            updater.stop()
            print(f"9. 已停止")
        else:
            print(f"5. 不满足自动启动条件")
        
        return True
        
    except Exception as e:
        print(f"主程序逻辑测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("开始AutoHWNDUpdater启动问题诊断\n")
    
    try:
        # 运行测试
        test_results = []
        
        test_results.append(test_config_loading() is not None)
        test_results.append(test_auto_hwnd_updater_initialization() is not None)
        test_results.append(test_auto_hwnd_updater_start() is not None)
        test_results.append(test_smart_finder_directly())
        test_results.append(test_main_program_logic())
        
        # 汇总结果
        print(f"\n=== 诊断结果汇总 ===")
        passed = sum(test_results)
        total = len(test_results)
        print(f"通过测试: {passed}/{total}")
        
        if passed == total:
            print("所有测试通过！AutoHWNDUpdater应该能正常工作。")
            print("如果实际应用中仍然不工作，可能是：")
            print("1. 应用启动时的配置加载时机问题")
            print("2. 延迟启动的定时器没有触发")
            print("3. 其他组件的初始化顺序问题")
        else:
            print("部分测试失败，请检查实现。")
            
    except Exception as e:
        print(f"诊断过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
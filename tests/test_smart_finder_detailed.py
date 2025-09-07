# -*- coding: utf-8 -*-
"""
详细测试智能查找器的查找过程

检查为什么查找器执行了查找但没有找到窗口
"""

import sys
import os
import time

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import AppConfig, load_config
from auto_approve.smart_process_finder import SmartProcessFinder
from capture.monitor_utils import find_window_by_process
from auto_approve.logger_manager import get_logger


def test_direct_find_window():
    """直接测试find_window_by_process函数"""
    print("=== 直接测试find_window_by_process函数 ===")
    
    try:
        # 测试不同的查找方式
        print("1. 测试精确查找Code.exe...")
        hwnd = find_window_by_process("Code.exe", partial_match=False)
        print(f"   精确查找结果: {hwnd if hwnd else '未找到'}")
        
        print("2. 测试部分查找Code.exe...")
        hwnd = find_window_by_process("Code.exe", partial_match=True)
        print(f"   部分查找结果: {hwnd if hwnd else '未找到'}")
        
        print("3. 测试查找Code...")
        hwnd = find_window_by_process("Code", partial_match=True)
        print(f"   不带扩展名查找结果: {hwnd if hwnd else '未找到'}")
        
        print("4. 测试查找code（小写）...")
        hwnd = find_window_by_process("code", partial_match=True)
        print(f"   小写查找结果: {hwnd if hwnd else '未找到'}")
        
        return True
        
    except Exception as e:
        print(f"直接测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_smart_finder_strategies():
    """测试智能查找器的不同策略"""
    print("\n=== 测试智能查找器的不同策略 ===")
    
    config = load_config()
    if not config:
        return False
        
    try:
        # 创建智能查找器
        finder = SmartProcessFinder()
        finder.set_config(config)
        
        print(f"1. 智能查找器初始化完成")
        print(f"   目标进程: {config.target_process}")
        
        # 测试各个策略
        strategies = ['process_name', 'process_path', 'window_title', 'class_name', 'fuzzy_match']
        
        for strategy in strategies:
            print(f"2. 测试策略: {strategy}")
            
            # 禁用其他策略，只启用当前策略
            for s in strategies:
                finder.set_strategy_enabled(s, s == strategy)
            
            # 执行强制查找
            hwnd = finder.force_search()
            print(f"   {strategy}策略结果: {hwnd if hwnd else '未找到'}")
            
            # 获取统计信息
            stats = finder.get_search_stats()
            print(f"   {strategy}策略统计: 总查找={stats['total_searches']}, 成功={stats['successful_searches']}")
            
            # 重置统计
            finder._reset_stats()
            
        return True
        
    except Exception as e:
        print(f"策略测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_smart_finder_detailed():
    """详细测试智能查找器"""
    print("\n=== 详细测试智能查找器 ===")
    
    config = load_config()
    if not config:
        return False
        
    try:
        # 创建智能查找器
        finder = SmartProcessFinder()
        finder.set_config(config)
        
        print(f"1. 智能查找器初始化完成")
        print(f"   目标进程: {config.target_process}")
        
        # 启用详细日志
        finder.logger.setLevel(10)  # DEBUG
        
        # 启动智能查找
        print(f"2. 启动智能查找...")
        finder.start_smart_search()
        
        # 等待工作
        print(f"3. 等待智能查找工作（5秒）...")
        time.sleep(5)
        
        # 获取统计信息
        stats = finder.get_search_stats()
        print(f"4. 智能查找器状态:")
        print(f"   总查找次数: {stats['total_searches']}")
        print(f"   成功次数: {stats['successful_searches']}")
        print(f"   失败次数: {stats['failed_searches']}")
        print(f"   成功率: {stats['success_rate']*100:.1f}%")
        print(f"   平均耗时: {stats['avg_search_time']:.3f}s")
        print(f"   自适应间隔: {stats['adaptive_interval']:.1f}s")
        
        # 测试强制查找
        print(f"5. 测试强制查找...")
        hwnd = finder.force_search()
        print(f"   强制查找结果: {hwnd if hwnd else '未找到'}")
        
        # 停止查找
        print(f"6. 停止智能查找...")
        finder.stop_smart_search()
        
        # 清理
        finder.cleanup()
        print(f"7. 清理完成")
        
        return True
        
    except Exception as e:
        print(f"详细测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_process_info():
    """测试进程信息获取"""
    print("\n=== 测试进程信息获取 ===")
    
    try:
        import psutil
        
        # 查找Code.exe进程
        print("1. 查找Code.exe进程...")
        code_processes = []
        for proc in psutil.process_iter(['name', 'exe', 'pid']):
            try:
                if 'code' in proc.info['name'].lower():
                    code_processes.append(proc)
                    print(f"   找到Code.exe进程: PID={proc.info['pid']}, 名称={proc.info['name']}")
                    print(f"     可执行文件: {proc.info['exe']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        print(f"2. 总共找到 {len(code_processes)} 个Code.exe进程")
        
        if code_processes:
            # 测试查找这些进程的窗口
            print("3. 测试查找这些进程的窗口...")
            for proc in code_processes[:3]:  # 只测试前3个
                exe_path = proc.info['exe']
                if exe_path:
                    hwnd = find_window_by_process(exe_path, partial_match=False)
                    print(f"   进程 {proc.info['pid']} 窗口查找结果: {hwnd if hwnd else '未找到'}")
        
        return True
        
    except Exception as e:
        print(f"进程信息测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("开始智能查找器详细测试\n")
    
    try:
        # 运行测试
        test_results = []
        
        test_results.append(test_direct_find_window())
        test_results.append(test_smart_finder_strategies())
        test_results.append(test_smart_finder_detailed())
        test_results.append(test_process_info())
        
        # 汇总结果
        print(f"\n=== 详细测试结果汇总 ===")
        passed = sum(test_results)
        total = len(test_results)
        print(f"通过测试: {passed}/{total}")
        
        if passed == total:
            print("所有测试通过。请查看上面的输出以了解查找过程的详细信息。")
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
# -*- coding: utf-8 -*-
"""
验证主应用程序的自动查找功能

检查主程序启动时是否正确配置并启动了自动查找
"""

import sys
import os
import time

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import load_config
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater
from auto_approve.logger_manager import get_logger


def test_main_app_config():
    """测试主应用程序配置"""
    print("=== 测试主应用程序配置 ===")
    
    try:
        config = load_config()
        if not config:
            print("配置加载失败")
            return False
            
        print("配置加载成功:")
        print(f"  target_process: {config.target_process}")
        print(f"  target_hwnd: {config.target_hwnd}")
        print(f"  auto_update_hwnd_by_process: {config.auto_update_hwnd_by_process}")
        print(f"  enable_smart_finder: {config.enable_smart_finder}")
        print(f"  finder_strategies: {config.finder_strategies}")
        
        # 验证关键配置
        if config.auto_update_hwnd_by_process and config.enable_smart_finder:
            print("\\n✓ 自动查找功能已启用")
            return True
        else:
            print("\\n✗ 自动查找功能未启用")
            return False
            
    except Exception as e:
        print(f"配置测试失败: {e}")
        return False


def test_delayed_auto_start():
    """测试延迟自动启动功能"""
    print("\\n=== 测试延迟自动启动功能 ===")
    
    try:
        config = load_config()
        if not config:
            return False
            
        # 模拟主程序的初始化过程
        print("1. 创建AutoHWNDUpdater...")
        updater = AutoHWNDUpdater()
        
        print("2. 设置配置...")
        updater.set_config(config)
        
        print("3. 检查自动启动条件...")
        should_auto_start = getattr(config, 'auto_update_hwnd_by_process', False)
        print(f"   auto_update_hwnd_by_process: {should_auto_start}")
        
        if should_auto_start:
            print("4. 启动AutoHWNDUpdater...")
            updater.start()
            
            # 等待启动
            time.sleep(2)
            
            print("5. 检查启动状态...")
            is_running = updater.is_running()
            current_hwnd = updater.get_current_hwnd()
            
            print(f"   运行状态: {is_running}")
            print(f"   当前HWND: {current_hwnd}")
            
            # 等待智能查找器工作
            print("6. 等待智能查找器工作（5秒）...")
            time.sleep(5)
            
            # 检查智能查找器状态
            if hasattr(updater, '_smart_finder') and updater._smart_finder:
                stats = updater._smart_finder.get_search_stats()
                print(f"   智能查找器统计: 总查找={stats['total_searches']}, 成功={stats['successful_searches']}")
                
                if stats['total_searches'] > 0:
                    print("\\n✓ 延迟自动启动功能正常")
                    success = True
                else:
                    print("\\n⚠ 智能查找器未执行查找")
                    success = False
            else:
                print("\\n✗ 智能查找器未初始化")
                success = False
                
            # 停止
            updater.stop()
            
            return success
        else:
            print("\\n✗ 不满足自动启动条件")
            return False
            
    except Exception as e:
        print(f"延迟启动测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_complete_auto_search_flow():
    """测试完整的自动查找流程"""
    print("\\n=== 测试完整的自动查找流程 ===")
    
    try:
        config = load_config()
        if not config:
            return False
            
        print("1. 初始化AutoHWNDUpdater...")
        updater = AutoHWNDUpdater()
        updater.set_config(config)
        
        print("2. 启动自动查找...")
        updater.start()
        
        print("3. 监控查找过程（10秒）...")
        for i in range(10):
            time.sleep(1)
            if hasattr(updater, '_smart_finder') and updater._smart_finder:
                stats = updater._smart_finder.get_search_stats()
                print(f"   第{i+1}秒: 总查找={stats['total_searches']}, 成功={stats['successful_searches']}, HWND={updater.get_current_hwnd()}")
                
                # 如果已经成功找到，可以提前结束
                if stats['successful_searches'] > 0:
                    break
        
        print("4. 最终状态检查...")
        final_hwnd = updater.get_current_hwnd()
        if hasattr(updater, '_smart_finder') and updater._smart_finder:
            final_stats = updater._smart_finder.get_search_stats()
            print(f"   最终HWND: {final_hwnd}")
            print(f"   查找统计: 总查找={final_stats['total_searches']}, 成功={final_stats['successful_searches']}")
            
            success = final_stats['successful_searches'] > 0 and final_hwnd > 0
        else:
            success = False
        
        updater.stop()
        
        if success:
            print("\\n✓ 完整自动查找流程正常")
        else:
            print("\\n✗ 完整自动查找流程异常")
            
        return success
        
    except Exception as e:
        print(f"完整流程测试失败: {e}")
        return False


def main():
    """主测试函数"""
    print("验证主应用程序的自动查找功能\\n")
    
    try:
        # 运行测试
        test_results = []
        
        test_results.append(test_main_app_config())
        test_results.append(test_delayed_auto_start())
        test_results.append(test_complete_auto_search_flow())
        
        # 汇总结果
        print(f"\\n=== 验证结果汇总 ===")
        passed = sum(test_results)
        total = len(test_results)
        print(f"通过测试: {passed}/{total}")
        
        if passed == total:
            print("\\n🎉 所有验证通过！")
            print("主应用程序的自动查找功能完全正常：")
            print("1. 配置正确加载并启用自动查找")
            print("2. 延迟自动启动机制正常工作")
            print("3. 智能查找器能够自动找到目标进程窗口")
            print("4. 完整的自动查找流程运行正常")
            print("\\n现在用户启动应用程序后，系统会：")
            print("- 自动查找Code.exe进程窗口")
            print("- 定期检查窗口有效性")
            print("- 自动恢复丢失的窗口")
            print("- 无需用户手动干预")
        else:
            print("\\n❌ 部分验证失败，请检查实现。")
            
    except Exception as e:
        print(f"验证过程中发生异常: {e}")
        return False
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
# -*- coding: utf-8 -*-
"""
调试智能查找器的查找过程

添加详细的调试日志来查看查找过程
"""

import sys
import os
import time
import logging

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import AppConfig, load_config
from auto_approve.smart_process_finder import SmartProcessFinder
from capture.monitor_utils import find_window_by_process
from auto_approve.logger_manager import get_logger


def setup_debug_logging():
    """设置调试日志"""
    # 创建logger
    logger = logging.getLogger('smart_finder_debug')
    logger.setLevel(logging.DEBUG)
    
    # 创建控制台handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    
    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # 添加handler
    logger.addHandler(console_handler)
    
    return logger


def test_smart_finder_with_debug():
    """使用调试日志测试智能查找器"""
    print("=== 使用调试日志测试智能查找器 ===")
    
    # 设置调试日志
    debug_logger = setup_debug_logging()
    
    config = load_config()
    if not config:
        return False
        
    try:
        # 创建智能查找器
        finder = SmartProcessFinder()
        finder.set_config(config)
        
        print(f"1. 智能查找器初始化完成")
        print(f"   目标进程: {config.target_process}")
        
        # 重写查找方法以添加调试信息
        original_search = finder._multi_strategy_search
        
        def debug_search():
            debug_logger.debug("开始多策略查找")
            debug_logger.debug(f"当前目标: {finder._current_target}")
            
            # 检查各个策略
            strategies = list(finder._strategies.values())
            debug_logger.debug(f"可用策略: {[s.name for s in strategies if s.enabled]}")
            
            # 按优先级排序
            strategies.sort(key=lambda s: (s.enabled, s.priority, s.get_success_rate()), reverse=True)
            
            for strategy in strategies:
                if not strategy.enabled:
                    debug_logger.debug(f"策略 {strategy.name} 已禁用")
                    continue
                    
                debug_logger.debug(f"尝试策略: {strategy.name}")
                hwnd = finder._try_strategy(strategy.name)
                debug_logger.debug(f"策略 {strategy.name} 结果: {hwnd}")
                
                if hwnd:
                    strategy.record_result(True)
                    debug_logger.debug(f"策略 {strategy.name} 成功，返回 HWND: {hwnd}")
                    return hwnd
                else:
                    strategy.record_result(False)
                    debug_logger.debug(f"策略 {strategy.name} 失败")
                    
            debug_logger.debug("所有策略都失败了")
            return None
        
        # 替换查找方法
        finder._multi_strategy_search = debug_search
        
        # 重写单个策略测试方法
        original_try_strategy = finder._try_strategy
        
        def debug_try_strategy(strategy_name: str):
            debug_logger.debug(f"执行策略: {strategy_name}")
            
            if strategy_name == '进程名称':
                return debug_search_by_process_name(finder)
            elif strategy_name == '进程路径':
                return debug_search_by_process_path(finder)
            elif strategy_name == '窗口标题':
                return debug_search_by_window_title(finder)
            elif strategy_name == '窗口类名':
                return debug_search_by_class_name(finder)
            elif strategy_name == '模糊匹配':
                return debug_search_by_fuzzy_match(finder)
            else:
                debug_logger.debug(f"未知策略: {strategy_name}")
                return None
        
        def debug_search_by_process_name(finder):
            debug_logger.debug("执行进程名称查找")
            try:
                import os
                process_name = os.path.basename(finder._current_target)
                debug_logger.debug(f"提取的进程名: {process_name}")
                
                if not process_name:
                    process_name = finder._current_target
                    debug_logger.debug(f"使用完整目标: {process_name}")
                    
                # 移除扩展名进行匹配
                base_name = os.path.splitext(process_name)[0]
                debug_logger.debug(f"基础名称: {base_name}")
                
                # 先尝试精确匹配
                debug_logger.debug("尝试精确匹配...")
                hwnd = find_window_by_process(process_name, partial_match=False)
                debug_logger.debug(f"精确匹配结果: {hwnd}")
                if hwnd:
                    return hwnd
                    
                # 尝试不带扩展名的匹配
                debug_logger.debug("尝试不带扩展名的匹配...")
                hwnd = find_window_by_process(base_name, partial_match=True)
                debug_logger.debug(f"不带扩展名匹配结果: {hwnd}")
                if hwnd:
                    return hwnd
                    
                # 尝试部分匹配
                debug_logger.debug("尝试部分匹配...")
                hwnd = find_window_by_process(process_name, partial_match=True)
                debug_logger.debug(f"部分匹配结果: {hwnd}")
                return hwnd
                
            except Exception as e:
                debug_logger.debug(f"进程名称查找失败: {e}")
                return None
        
        def debug_search_by_process_path(finder):
            debug_logger.debug("执行进程路径查找")
            try:
                if '\\' not in finder._current_target:
                    debug_logger.debug("目标不是路径，跳过")
                    return None
                    
                debug_logger.debug("尝试路径匹配...")
                hwnd = find_window_by_process(finder._current_target, partial_match=False)
                debug_logger.debug(f"路径匹配结果: {hwnd}")
                return hwnd
                
            except Exception as e:
                debug_logger.debug(f"进程路径查找失败: {e}")
                return None
        
        def debug_search_by_window_title(finder):
            debug_logger.debug("执行窗口标题查找")
            debug_logger.debug("窗口标题查找未实现")
            return None
        
        def debug_search_by_class_name(finder):
            debug_logger.debug("执行窗口类名查找")
            debug_logger.debug("窗口类名查找未实现")
            return None
        
        def debug_search_by_fuzzy_match(finder):
            debug_logger.debug("执行模糊匹配")
            debug_logger.debug("模糊匹配未实现")
            return None
        
        # 替换方法
        finder._try_strategy = debug_try_strategy
        
        # 执行强制查找
        print(f"2. 执行强制查找（带调试日志）...")
        hwnd = finder.force_search()
        
        print(f"3. 强制查找结果: {hwnd if hwnd else '未找到'}")
        
        # 获取统计信息
        stats = finder.get_search_stats()
        print(f"4. 统计信息:")
        print(f"   总查找次数: {stats['total_searches']}")
        print(f"   成功次数: {stats['successful_searches']}")
        print(f"   失败次数: {stats['failed_searches']}")
        print(f"   成功率: {stats['success_rate']*100:.1f}%")
        
        # 清理
        finder.cleanup()
        print(f"5. 清理完成")
        
        return True
        
    except Exception as e:
        print(f"调试测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("开始智能查找器调试测试\n")
    
    try:
        # 运行测试
        success = test_smart_finder_with_debug()
        
        if success:
            print("\n调试测试完成。请查看上面的详细日志输出。")
        else:
            print("\n调试测试失败。")
            
    except Exception as e:
        print(f"测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
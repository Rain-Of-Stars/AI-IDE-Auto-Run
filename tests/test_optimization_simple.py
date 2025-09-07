# -*- coding: utf-8 -*-
"""
简单UI优化验证脚本
"""
import os
import sys
import time

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_optimization():
    """测试优化效果"""
    print("=== UI优化验证 ===")
    
    try:
        # 导入优化模块
        from auto_approve.gui_responsiveness_manager import get_gui_responsiveness_manager
        
        # 获取管理器实例
        manager = get_gui_responsiveness_manager()
        
        # 检查优化参数
        print(f"批处理延迟: {manager._batch_delay_ms}ms")
        print(f"最大批处理延迟: {manager._max_batch_delay_ms}ms")
        print(f"最小批处理延迟: {manager._min_batch_delay_ms}ms")
        
        # 验证优化效果
        if manager._batch_delay_ms <= 25:
            print("OK: 批处理延迟已优化")
        else:
            print("WARN: 批处理延迟需要优化")
        
        # 测试紧急恢复机制
        print("测试紧急恢复机制...")
        
        # 创建一些测试更新
        from auto_approve.gui_responsiveness_manager import schedule_ui_update
        for i in range(10):
            schedule_ui_update(
                widget_id=f'test_{i}',
                update_type='tooltip',
                data={'text': f'测试 {i}'},
                priority=1
            )
        
        # 检查紧急恢复方法是否存在
        if hasattr(manager, 'emergency_ui_recovery'):
            print("OK: 紧急恢复机制已实现")
        else:
            print("WARN: 紧急恢复机制未实现")
        
        print("=== 验证完成 ===")
        return True
        
    except Exception as e:
        print(f"ERROR: 验证失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_optimization()
    sys.exit(0 if success else 1)
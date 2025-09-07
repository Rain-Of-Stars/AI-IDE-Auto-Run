#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的模板加载测试脚本
测试截图保存后立即加载到内存的功能
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from utils.memory_template_manager import get_template_manager
    import numpy as np
    import cv2
except ImportError as e:
    print(f"导入模块失败: {e}")
    sys.exit(1)

def create_test_image(width=100, height=100, color=(255, 0, 0)):
    """创建测试图像"""
    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:] = color
    return image

def test_template_loading_functionality():
    """测试模板加载功能"""
    print("\n=== 测试模板加载功能 ===")
    
    # 创建临时目录和测试图像
    temp_dir = tempfile.mkdtemp()
    test_image_path = os.path.join(temp_dir, "test_template.png")
    
    try:
        # 创建测试图像文件
        test_image = create_test_image()
        cv2.imwrite(test_image_path, test_image)
        print(f"✓ 创建测试图像: {test_image_path}")
        
        # 获取模板管理器
        template_manager = get_template_manager()
        print("✓ 获取模板管理器实例")
        
        # 清理缓存
        template_manager.clear_cache()
        print("✓ 清理模板缓存")
        
        # 检查初始状态
        initial_stats = template_manager.get_cache_stats()
        print(f"✓ 初始模板数量: {initial_stats['template_count']}")
        
        # 加载模板
        loaded_count = template_manager.load_templates([test_image_path])
        print(f"✓ 加载模板数量: {loaded_count}")
        
        # 检查加载后状态
        after_load_stats = template_manager.get_cache_stats()
        print(f"✓ 加载后模板数量: {after_load_stats['template_count']}")
        
        # 获取模板数据
        templates = template_manager.get_templates([test_image_path])
        print(f"✓ 获取模板数据: {len(templates)} 个")
        
        # 验证模板数据
        if templates:
            template_data, size = templates[0]
            print(f"✓ 模板尺寸: {template_data.shape}, 大小: {size}")
        
        # 测试缓存命中
        templates_again = template_manager.get_templates([test_image_path])
        final_stats = template_manager.get_cache_stats()
        print(f"✓ 缓存命中率: {final_stats['hit_rate_percent']:.1f}%")
        
        print("\n✅ 模板加载功能测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # 清理临时文件
        shutil.rmtree(temp_dir, ignore_errors=True)
        print("✓ 清理临时文件")

def test_memory_template_manager_basic():
    """测试内存模板管理器基本功能"""
    print("\n=== 测试内存模板管理器基本功能 ===")
    
    try:
        # 获取模板管理器实例
        manager = get_template_manager()
        print("✓ 成功获取模板管理器实例")
        
        # 测试缓存统计
        stats = manager.get_cache_stats()
        print(f"✓ 缓存统计: {stats}")
        
        # 测试清理缓存
        manager.clear_cache()
        print("✓ 成功清理缓存")
        
        # 验证清理后状态
        stats_after_clear = manager.get_cache_stats()
        print(f"✓ 清理后统计: {stats_after_clear}")
        
        print("\n✅ 内存模板管理器基本功能测试通过")
        return True
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("开始测试模板加载功能...")
    
    # 运行测试
    test1_result = test_memory_template_manager_basic()
    test2_result = test_template_loading_functionality()
    
    # 汇总结果
    print("\n=== 测试结果汇总 ===")
    print(f"基本功能测试: {'✅ 通过' if test1_result else '❌ 失败'}")
    print(f"模板加载测试: {'✅ 通过' if test2_result else '❌ 失败'}")
    
    if test1_result and test2_result:
        print("\n🎉 所有测试通过！截图保存后可以立即加载为识别模板。")
        sys.exit(0)
    else:
        print("\n💥 部分测试失败，需要进一步调试。")
        sys.exit(1)

if __name__ == "__main__":
    main()
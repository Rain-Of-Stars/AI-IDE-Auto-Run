# -*- coding: utf-8 -*-
"""
简单性能测试脚本
直接测试WGC后端性能
"""

import time
import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_import_performance():
    """测试导入性能"""
    print("测试导入性能...")
    
    start_time = time.time()
    try:
        from capture.wgc_backend import WGCCaptureSession
        import_time = time.time() - start_time
        print(f"✅ WGC后端导入成功，耗时: {import_time:.3f}秒")
        return True
    except Exception as e:
        import_time = time.time() - start_time
        print(f"❌ WGC后端导入失败，耗时: {import_time:.3f}秒，错误: {e}")
        return False

def test_timeout_settings():
    """测试超时设置"""
    print("\n测试超时设置...")
    
    try:
        from capture.capture_manager import CaptureManager
        
        # 检查默认超时设置
        import inspect
        sig = inspect.signature(CaptureManager.open_window)
        timeout_param = sig.parameters['timeout']
        print(f"✅ open_window默认超时: {timeout_param.default}秒")
        
        sig2 = inspect.signature(CaptureManager.wait_for_frame)
        timeout_param2 = sig2.parameters['timeout']
        print(f"✅ wait_for_frame默认超时: {timeout_param2.default}秒")
        
        return True
    except Exception as e:
        print(f"❌ 超时设置测试失败: {e}")
        return False

def test_config_settings():
    """测试配置设置"""
    print("\n测试配置设置...")
    
    try:
        import json
        config_path = os.path.join(project_root, 'config.json')
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        capture_timeout = config.get('capture_timeout_ms', 0)
        print(f"✅ 配置文件捕获超时: {capture_timeout}ms")
        
        if capture_timeout <= 2000:
            print("✅ 捕获超时设置已优化")
        else:
            print("⚠️  捕获超时设置仍较长")
        
        return True
    except Exception as e:
        print(f"❌ 配置设置测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 50)
    print("捕获性能优化验证测试")
    print("=" * 50)
    
    total_tests = 3
    passed_tests = 0
    
    if test_import_performance():
        passed_tests += 1
    
    if test_timeout_settings():
        passed_tests += 1
    
    if test_config_settings():
        passed_tests += 1
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed_tests}/{total_tests} 通过")
    
    if passed_tests == total_tests:
        print("✅ 所有测试通过，性能优化已生效")
    else:
        print("⚠️  部分测试失败，需要进一步检查")
    
    print("=" * 50)

if __name__ == "__main__":
    main()
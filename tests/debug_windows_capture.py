# -*- coding: utf-8 -*-
"""
调试WindowsCapture参数要求
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def debug_windows_capture_params():
    """调试WindowsCapture的参数要求"""
    try:
        import windows_capture
        import inspect
        
        print("=== WindowsCapture参数调试 ===")
        
        # 获取WindowsCapture类的签名
        sig = inspect.signature(windows_capture.WindowsCapture.__init__)
        print(f"WindowsCapture.__init__签名: {sig}")
        
        # 获取参数列表
        params = list(sig.parameters.keys())
        print(f"参数列表: {params}")
        
        # 获取参数详情
        for param_name, param in sig.parameters.items():
            print(f"参数 '{param_name}': {param}")
        
        # 尝试创建实例看看需要什么参数
        print("\n=== 尝试不同参数组合 ===")
        
        # 测试基本参数
        test_params_list = [
            {"hwnd": 12345},
            {"window_handle": 12345},
            {"handle": 12345},
            {"hWnd": 12345},
            {"window_hwnd": 12345},
            {"hwnd": 12345, "cursor_capture": False},
            {"hwnd": 12345, "cursor_capture": False, "draw_border": False},
        ]
        
        for i, test_params in enumerate(test_params_list):
            try:
                print(f"测试 {i+1}: {test_params}")
                session = windows_capture.WindowsCapture(**test_params)
                print(f"  成功创建: {type(session)}")
                break
            except Exception as e:
                print(f"  失败: {e}")
        
        # 检查是否需要其他类型的参数
        print("\n=== 检查其他可能需要的参数 ===")
        
        # 检查是否有monitor相关的参数
        monitor_params = ["monitor", "monitor_index", "monitor_handle", "display", "screen"]
        for param in monitor_params:
            if param in params:
                print(f"发现显示器相关参数: {param}")
        
        # 检查是否有其他必需参数
        required_params = []
        for param_name, param in sig.parameters.items():
            if param.default == inspect.Parameter.empty and param_name != 'self':
                required_params.append(param_name)
        
        if required_params:
            print(f"必需参数: {required_params}")
        else:
            print("没有发现必需参数（除了self）")
            
    except Exception as e:
        print(f"调试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_windows_capture_params()
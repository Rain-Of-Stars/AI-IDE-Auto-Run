# -*- coding: utf-8 -*-
"""
调试快速初始化问题
"""

import sys, os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from capture.capture_manager import CaptureManager
import ctypes

# 获取当前窗口句柄
user32 = ctypes.windll.user32
hwnd = user32.GetForegroundWindow()

print(f'窗口句柄: {hwnd}')

# 创建捕获管理器
capture_manager = CaptureManager()

# 测试目标解析
try:
    resolved_hwnd = capture_manager._resolve_window_target(hwnd, True)
    print(f'解析句柄: {resolved_hwnd}')
except Exception as e:
    print(f'解析失败: {e}')
    import traceback
    traceback.print_exc()

# 测试快速初始化
try:
    success = capture_manager.open_window_fast(hwnd)
    print(f'快速初始化结果: {success}')
except Exception as e:
    print(f'快速初始化失败: {e}')
    import traceback
    traceback.print_exc()
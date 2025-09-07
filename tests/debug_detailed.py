# -*- coding: utf-8 -*-
"""
详细调试快速初始化问题
"""

import sys, os
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from capture.capture_manager import CaptureManager
from capture.wgc_backend import WGCCaptureSession
import ctypes

# 获取当前窗口句柄
user32 = ctypes.windll.user32
hwnd = user32.GetForegroundWindow()

print(f'窗口句柄: {hwnd}')

# 创建捕获管理器
capture_manager = CaptureManager()

# 逐步测试快速初始化的每个步骤
try:
    print('\n--- 步骤1: 解析目标 ---')
    resolved_hwnd = capture_manager._resolve_window_target(hwnd, True)
    print(f'解析句柄: {resolved_hwnd}')
    
    print('\n--- 步骤2: 创建WGC会话 ---')
    session = WGCCaptureSession.from_window(hwnd)
    print(f'WGC会话创建成功: {session is not None}')
    
    print('\n--- 步骤3: 禁用健康检查 ---')
    if hasattr(session, '_health_check_enabled'):
        session._health_check_enabled = False
        print('健康检查已禁用')
    else:
        print('健康检查属性不存在')
    
    print('\n--- 步骤4: 禁用日志 ---')
    if hasattr(session, '_logger'):
        import logging
        session._logger.setLevel(logging.CRITICAL)
        print('日志已禁用')
    else:
        print('日志属性不存在')
    
    print('\n--- 步骤5: 设置参数 ---')
    capture_manager._session = session
    capture_manager._target_hwnd = hwnd
    capture_manager._capture_mode = 'window'
    print('参数设置完成')
    
    print('\n--- 步骤6: 启动会话 ---')
    success = session.start(target_fps=1, include_cursor=False, border_required=False)
    print(f'会话启动结果: {success}')
    
    if not success:
        print('\n--- 诊断启动失败原因 ---')
        # 检查WGC是否可用
        from capture.wgc_backend import WGC_AVAILABLE
        print(f'WGC可用性: {WGC_AVAILABLE}')
        
        # 检查窗口是否有效
        is_valid = user32.IsWindow(hwnd)
        print(f'窗口有效性: {is_valid}')
        
        # 获取窗口标题
        length = user32.GetWindowTextLengthW(hwnd)
        print(f'窗口标题长度: {length}')
        
        if length > 0:
            import ctypes
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            print(f'窗口标题: {buffer.value}')

except Exception as e:
    print(f'调试过程中发生错误: {e}')
    import traceback
    traceback.print_exc()
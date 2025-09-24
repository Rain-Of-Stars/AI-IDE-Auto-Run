# -*- coding: utf-8 -*-
"""
测试可见窗口查找

测试Code.exe进程是否有可见的窗口
"""

import sys
import os
import time
import ctypes
from ctypes import wintypes

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from capture.monitor_utils import find_window_by_process
from auto_approve.logger_manager import get_logger


def test_visible_windows():
    """测试Code.exe进程的可见窗口"""
    print("=== 测试Code.exe进程的可见窗口 ===")
    
    # 测试查找Code.exe的窗口
    print("1. 测试精确查找Code.exe...")
    hwnd = find_window_by_process("Code.exe", partial_match=False)
    print(f"   精确查找结果: {hwnd if hwnd else '未找到'}")
    
    print("2. 测试部分查找Code.exe...")
    hwnd = find_window_by_process("Code.exe", partial_match=True)
    print(f"   部分查找结果: {hwnd if hwnd else '未找到'}")
    
    print("3. 测试查找Code（不带扩展名）...")
    hwnd = find_window_by_process("Code", partial_match=True)
    print(f"   不带扩展名查找结果: {hwnd if hwnd else '未找到'}")
    
    # 使用Windows API手动枚举所有Code.exe进程的窗口
    print("\n4. 手动枚举所有Code.exe进程的窗口...")
    
    user32 = ctypes.windll.user32
    psapi = ctypes.windll.psapi
    kernel32 = ctypes.windll.kernel32
    
    def enum_windows_callback(hwnd, lparam):
        """窗口枚举回调函数"""
        try:
            # 检查窗口是否可见
            if user32.IsWindowVisible(hwnd):
                # 获取窗口标题
                title = ctypes.create_unicode_buffer(512)
                user32.GetWindowTextW(hwnd, title, 512)
                
                # 获取窗口所属进程ID
                pid = wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                
                # 打开进程获取可执行文件路径
                PROCESS_QUERY_INFORMATION = 0x0400
                PROCESS_VM_READ = 0x0010
                hprocess = kernel32.OpenProcess(
                    PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, 
                    False, 
                    pid.value
                )
                
                if hprocess:
                    try:
                        buf = ctypes.create_unicode_buffer(1024)
                        if psapi.GetModuleFileNameExW(hprocess, None, buf, 1024):
                            full_path = buf.value
                            base_name = os.path.basename(full_path)
                            
                            if 'code' in base_name.lower():
                                print(f"   找到Code.exe窗口:")
                                print(f"     HWND: {hwnd}")
                                print(f"     标题: '{title.value}'")
                                print(f"     进程: {base_name}")
                                print(f"     完整路径: {full_path}")
                                print()
                                
                    finally:
                        kernel32.CloseHandle(hprocess)
                        
        except Exception as e:
            pass
            
        return True  # 继续枚举
    
    # 枚举所有窗口
    user32.EnumWindows(enum_windows_callback, 0)
    
    print("5. 枚举完成")
    
    return True


def test_other_processes():
    """测试其他进程的窗口查找"""
    print("\n=== 测试其他进程的窗口查找 ===")
    
    # 测试查找记事本
    print("1. 测试查找notepad.exe...")
    hwnd = find_window_by_process("notepad.exe", partial_match=True)
    print(f"   notepad.exe查找结果: {hwnd if hwnd else '未找到'}")
    
    # 测试查找资源管理器
    print("2. 测试查找explorer.exe...")
    hwnd = find_window_by_process("explorer.exe", partial_match=True)
    print(f"   explorer.exe查找结果: {hwnd if hwnd else '未找到'}")
    
    return True


def main():
    """主测试函数"""
    print("开始可见窗口查找测试\n")
    
    try:
        # 运行测试
        test_results = []
        
        test_results.append(test_visible_windows())
        test_results.append(test_other_processes())
        
        # 汇总结果
        print(f"\n=== 测试结果汇总 ===")
        passed = sum(test_results)
        total = len(test_results)
        print(f"通过测试: {passed}/{total}")
        
        if passed == total:
            print("测试完成。请查看上面的输出以了解Code.exe进程的窗口情况。")
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
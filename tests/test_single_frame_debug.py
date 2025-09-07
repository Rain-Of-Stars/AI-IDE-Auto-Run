# -*- coding: utf-8 -*-
"""
单帧预览调试测试脚本

专门用于调试单帧预览功能，找出为什么无法获取图像的问题
"""
import os
import sys
import time
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置详细的日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('single_frame_debug.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def debug_single_frame_preview():
    """调试单帧预览功能"""
    print("=== 单帧预览调试测试 ===")
    
    try:
        # 1. 检查WGC可用性
        print("1. 检查WGC可用性...")
        from capture.wgc_backend import WGC_AVAILABLE
        print(f"   WGC_AVAILABLE: {WGC_AVAILABLE}")
        
        if not WGC_AVAILABLE:
            print("   ERROR: WGC不可用")
            return False
            
        # 2. 尝试导入单帧预览器
        print("2. 导入单帧预览器...")
        from capture.single_frame_preview import get_single_frame_preview
        print("   OK: 单帧预览器导入成功")
        
        # 3. 创建预览器实例
        print("3. 创建预览器实例...")
        previewer = get_single_frame_preview()
        print("   OK: 预览器创建成功")
        
        # 4. 获取当前窗口句柄进行测试
        print("4. 获取测试窗口句柄...")
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        
        # 获取当前活动窗口
        hwnd = user32.GetForegroundWindow()
        print(f"   当前活动窗口句柄: {hwnd}")
        
        if hwnd == 0:
            print("   ERROR: 无法获取当前活动窗口")
            return False
            
        # 获取窗口标题
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value
            # 清理特殊字符
            title = ''.join(char for char in title if ord(char) < 128 or char.isprintable())
            print(f"   窗口标题: {title}")
        
        # 5. 测试单帧预览
        print("5. 开始单帧预览测试...")
        start_time = time.time()
        
        # 使用较短的超时时间进行测试
        image = previewer.capture_single_frame(hwnd, timeout_sec=1.0)
        
        end_time = time.time()
        print(f"   预览耗时: {end_time - start_time:.3f}秒")
        
        if image is not None:
            print(f"   OK: 成功获取图像，形状: {image.shape}")
            print(f"   图像类型: {type(image)}")
            print(f"   图像大小: {image.size} 字节")
            
            # 保存图像用于检查
            import cv2
            cv2.imwrite('debug_preview.png', image)
            print("   OK: 图像已保存为 debug_preview.png")
            
            return True
        else:
            print("   ERROR: 未获取到图像")
            
            # 检查日志文件获取更详细的信息
            if os.path.exists('single_frame_debug.log'):
                print("   检查详细日志...")
                with open('single_frame_debug.log', 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    # 显示最后20行日志
                    print("   最后20行日志:")
                    for line in lines[-20:]:
                        print(f"   {line.strip()}")
            
            return False
            
    except Exception as e:
        print(f"ERROR: 调试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_alternative_methods():
    """测试其他捕获方法作为对比"""
    print("\n=== 其他捕获方法对比测试 ===")
    
    try:
        # 1. 测试标准CaptureManager
        print("1. 测试标准CaptureManager...")
        from capture.capture_manager import CaptureManager
        
        manager = CaptureManager()
        
        # 获取当前窗口句柄
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        
        if hwnd != 0:
            print(f"   使用窗口句柄: {hwnd}")
            
            # 配置为快速模式
            manager.configure(
                fps=1,
                include_cursor=False,
                border_required=False,
                restore_minimized=False
            )
            
            # 尝试打开窗口
            start_time = time.time()
            success = manager.open_window(hwnd)
            open_time = time.time() - start_time
            
            print(f"   打开窗口结果: {success}, 耗时: {open_time:.3f}秒")
            
            if success:
                # 等待一小段时间
                time.sleep(0.1)
                
                # 尝试捕获一帧
                start_time = time.time()
                image = manager.capture_frame()
                capture_time = time.time() - start_time
                
                print(f"   捕获结果: {'成功' if image is not None else '失败'}, 耗时: {capture_time:.3f}秒")
                
                if image is not None:
                    print(f"   图像形状: {image.shape}")
                    # 保存对比图像
                    import cv2
                    cv2.imwrite('debug_standard.png', image)
                    print("   OK: 标准捕获图像已保存为 debug_standard.png")
                
                # 关闭管理器
                manager.close()
            else:
                print("   ERROR: 无法打开窗口")
        else:
            print("   ERROR: 无法获取窗口句柄")
            
    except Exception as e:
        print(f"ERROR: 标准CaptureManager测试失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主测试函数"""
    print("开始单帧预览调试...")
    
    # 设置控制台编码避免中文乱码
    try:
        import sys
        if sys.platform == 'win32':
            # 在Windows上设置UTF-8输出
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass
    
    # 运行单帧预览调试
    preview_success = debug_single_frame_preview()
    
    # 运行对比测试
    test_alternative_methods()
    
    print("\n=== 调试总结 ===")
    if preview_success:
        print("OK: 单帧预览功能正常工作")
        print("问题可能是超时设置过短或特定窗口不兼容")
    else:
        print("ERROR: 单帧预览功能存在问题")
        print("需要检查:")
        print("1. WGC库是否正确安装")
        print("2. 目标窗口是否支持捕获")
        print("3. 权限是否足够")
        print("4. 是否有其他进程占用捕获设备")
    
    # 清理日志文件
    if os.path.exists('single_frame_debug.log'):
        print(f"\n详细日志已保存到: single_frame_debug.log")
    
    return 0 if preview_success else 1

if __name__ == "__main__":
    sys.exit(main())
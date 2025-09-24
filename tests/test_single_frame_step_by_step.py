# -*- coding: utf-8 -*-
"""
详细测试单帧预览器的每个步骤
"""
import os
import sys
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置详细的日志记录
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# 确保auto_approver的日志级别也是DEBUG
auto_approver_logger = logging.getLogger('auto_approver')
auto_approver_logger.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

def test_single_frame_step_by_step():
    """逐步测试单帧预览器"""
    print("=== 单帧预览器逐步测试 ===")
    
    try:
        # 1. 导入单帧预览器
        print("1. 导入单帧预览器...")
        from capture.single_frame_preview import SingleFramePreview
        print("   OK: 导入成功")
        
        # 2. 创建实例
        print("2. 创建实例...")
        previewer = SingleFramePreview()
        print("   OK: 实例创建成功")
        
        # 3. 获取测试窗口
        print("3. 获取测试窗口...")
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        print(f"   窗口句柄: {hwnd}")
        
        if hwnd == 0:
            print("   ERROR: 无法获取窗口句柄")
            return False
        
        # 4. 测试_get_window_title方法
        print("4. 测试_get_window_title方法...")
        window_title = previewer._get_window_title(hwnd)
        print(f"   窗口标题: {window_title}")
        
        if not window_title:
            print("   ERROR: 无法获取窗口标题")
            return False
        
        # 5. 测试_create_minimal_session方法
        print("5. 测试_create_minimal_session方法...")
        session = previewer._create_minimal_session(hwnd)
        print(f"   会话对象: {session}")
        print(f"   会话类型: {type(session)}")
        
        if session is None:
            print("   ERROR: 无法创建会话")
            return False
        
        # 6. 检查会话属性
        print("6. 检查会话属性...")
        print(f"   hasattr(session, 'start'): {hasattr(session, 'start')}")
        print(f"   hasattr(session, 'frame_handler'): {hasattr(session, 'frame_handler')}")
        print(f"   hasattr(session, 'stop'): {hasattr(session, 'stop')}")
        
        # 7. 测试_wait_for_first_frame方法
        print("7. 测试_wait_for_first_frame方法...")
        print("   开始等待帧...")
        frame = previewer._wait_for_first_frame(2.0)  # 增加等待时间
        print(f"   帧对象: {frame}")
        print(f"   帧类型: {type(frame)}")
        
        if frame is not None:
            print(f"   帧形状: {frame.shape}")
            print("   OK: 成功获取帧")
            
            # 保存帧
            import cv2
            cv2.imwrite('test_single_frame.png', frame)
            print("   OK: 帧已保存为 test_single_frame.png")
            
            return True
        else:
            print("   ERROR: 未获取到帧")
            
            # 尝试直接调试会话
            print("   开始直接调试会话...")
            session = previewer._create_minimal_session(hwnd)
            if session:
                print("   创建调试会话成功")
                
                # 设置一个简单的测试帧处理器
                test_frame_received = [False]
                def test_frame_handler(*args, **kwargs):
                    print(f"   测试帧处理器被调用: {len(args)}, {kwargs}")
                    test_frame_received[0] = True
                
                def test_closed_handler():
                    print("   测试关闭处理器被调用")
                
                session.frame_handler = test_frame_handler
                session.closed_handler = test_closed_handler
                print("   设置测试帧处理器和关闭处理器")
                
                # 启动会话
                print("   启动会话...")
                session.start()
                print("   会话已启动")
                
                # 等待一段时间看看是否有回调
                import time
                print("   等待3秒...")
                time.sleep(3)
                
                if test_frame_received[0]:
                    print("   OK: 测试帧处理器被调用")
                else:
                    print("   ERROR: 测试帧处理器未被调用")
            else:
                print("   ERROR: 无法创建调试会话")
            
            return False
            
    except Exception as e:
        print(f"ERROR: 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # 设置控制台编码
    try:
        import sys
        if sys.platform == 'win32':
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except:
        pass
    
    success = test_single_frame_step_by_step()
    
    print("\n=== 测试结果 ===")
    if success:
        print("OK: 单帧预览器测试成功")
    else:
        print("ERROR: 单帧预览器测试失败")
    
    sys.exit(0 if success else 1)
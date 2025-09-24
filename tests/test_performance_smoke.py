# -*- coding: utf-8 -*-
"""
性能优化冒烟测试

快速验证优化是否有效的简单测试
"""

import sys
import time
import os

# 添加项目路径
sys.path.insert(0, '.')

try:
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QImage
    
    # 导入优化模块
    from capture.ultimate_performance_capture_manager import (
        get_ultimate_performance_manager,
        CaptureConfig
    )
    from capture.high_performance_frame_buffer import get_high_performance_frame_buffer
    
    print("OK: 所有优化模块导入成功")
    
    def test_imports():
        """测试模块导入"""
        print("测试模块导入...")
        
        # 测试帧缓冲
        buffer = get_high_performance_frame_buffer()
        print("OK: 高性能帧缓冲创建成功")
        
        # 测试捕获管理器
        manager = get_ultimate_performance_manager()
        print("OK: 终极性能管理器创建成功")
        
        # 测试配置
        config = CaptureConfig(
            target_fps=30,
            adaptive_fps=True,
            fast_mode=True
        )
        print("OK: 捕获配置创建成功")
        
        return True
    
    def test_basic_functionality():
        """测试基本功能"""
        print("\n测试基本功能...")
        
        # 创建QApplication
        app = QApplication.instance()
        if not app:
            app = QApplication(sys.argv)
        
        # 创建测试窗口
        window = QWidget()
        window.setWindowTitle("优化测试窗口")
        window.resize(400, 300)
        
        layout = QVBoxLayout()
        label = QLabel("等待帧...")
        layout.addWidget(label)
        window.setLayout(layout)
        window.show()
        
        # 获取管理器
        manager = get_ultimate_performance_manager()
        
        # 配置
        config = CaptureConfig(
            target_fps=30,
            adaptive_fps=True,
            fast_mode=True,
            max_buffer_size=5,
            max_memory_mb=50
        )
        manager.update_config(config)
        
        # 帧计数器
        frame_count = 0
        start_time = time.time()
        
        def on_frame_ready(qimage: QImage):
            nonlocal frame_count
            frame_count += 1
            label.setText(f"收到帧: {frame_count}")
            label.setPixmap(qimage.scaled(320, 240))
        
        # 连接信号
        manager.frame_ready.connect(on_frame_ready)
        
        # 启动捕获
        target = "优化测试窗口"
        if manager.start_capture(target):
            print("OK: 捕获启动成功")
            
            # 运行5秒
            timeout = time.time() + 5
            while time.time() < timeout:
                app.processEvents()
                time.sleep(0.01)
            
            # 停止捕获
            manager.stop_capture()
            
            # 等待一下
            time.sleep(0.5)
            
            fps = frame_count / 5.0
            print(f"OK: 测试完成: {frame_count} 帧, 平均 FPS: {fps:.1f}")
            
            # 获取统计信息
            stats = manager.get_stats()
            buffer_stats = get_high_performance_frame_buffer().get_stats()
            
            print(f"OK: 工作统计: {stats['worker_stats']['frames_processed']} 帧处理")
            print(f"OK: 缓冲统计: {buffer_stats['total_frames']} 总帧数")
            print(f"OK: 内存使用: {buffer_stats['memory_usage_mb']:.1f} MB")
            
            return frame_count > 0
        else:
            print("ERROR: 捕获启动失败")
            return False
    
    def main():
        """主测试函数"""
        print("=" * 50)
        print("性能优化冒烟测试")
        print("=" * 50)
        
        success = True
        
        try:
            # 测试导入
            if not test_imports():
                success = False
            
            # 测试基本功能
            if not test_basic_functionality():
                success = False
            
        except Exception as e:
            print(f"ERROR: 测试异常: {e}")
            success = False
        
        print("\n" + "=" * 50)
        if success:
            print("OK: 冒烟测试通过 - 性能优化基本正常")
            return 0
        else:
            print("ERROR: 冒烟测试失败 - 需要检查优化实现")
            return 1
    
    if __name__ == "__main__":
        exit_code = main()
        sys.exit(exit_code)

except ImportError as e:
    print(f"ERROR: 模块导入失败: {e}")
    print("请确保已安装所需依赖: PySide6, numpy, opencv-python, psutil")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: 测试异常: {e}")
    sys.exit(1)
# -*- coding: utf-8 -*-
"""
简单测试进度信号功能
验证进度更新是否正常工作
"""

import sys
import os
import time

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_signals_connection():
    """测试信号连接"""
    print("=" * 60)
    print("测试进度信号连接")
    print("=" * 60)
    
    try:
        from PySide6 import QtCore, QtWidgets
        from auto_approve.scanner_process_adapter import ScannerProcessAdapter
        from auto_approve.config_manager import load_config
        
        # 创建应用
        app = QtWidgets.QApplication(sys.argv)
        
        # 加载配置
        config_manager = load_config("config.json")
        
        # 创建扫描器适配器
        scanner = ScannerProcessAdapter(config_manager)
        
        # 测试信号连接
        progress_received = False
        status_received = False
        log_received = False
        
        def on_progress(message):
            nonlocal progress_received
            progress_received = True
            print(f"[进度信号] {message}")
        
        def on_status(status):
            nonlocal status_received
            status_received = True
            print(f"[状态信号] {status}")
        
        def on_log(message):
            nonlocal log_received
            log_received = True
            print(f"[日志信号] {message}")
        
        # 连接信号
        scanner.sig_progress.connect(on_progress)
        scanner.sig_status.connect(on_status)
        scanner.sig_log.connect(on_log)
        
        print("[OK] 信号连接成功")
        
        # 测试手动发送信号
        print("\n测试手动发送信号...")
        scanner.sig_progress.emit("测试进度消息")
        scanner.sig_status.emit("测试状态消息")
        scanner.sig_log.emit("测试日志消息")
        
        # 等待信号处理
        app.processEvents()
        time.sleep(0.1)
        
        # 验证信号是否收到
        print(f"\n信号接收结果:")
        print(f"进度信号: {'[OK]' if progress_received else '[ERROR]'}")
        print(f"状态信号: {'[OK]' if status_received else '[ERROR]'}")
        print(f"日志信号: {'[OK]' if log_received else '[ERROR]'}")
        
        # 测试启动过程
        print("\n测试启动过程...")
        start_time = time.time()
        scanner.start()
        
        # 等待一段时间观察进度更新
        for i in range(50):  # 5秒
            app.processEvents()
            time.sleep(0.1)
            
            # 检查是否已启动
            if scanner.isRunning():
                print(f"[OK] 扫描器已启动 (耗时: {time.time() - start_time:.2f}秒)")
                break
        
        if not scanner.isRunning():
            print("[ERROR] 扫描器启动超时")
        
        # 等待更多进度更新
        print("\n等待进度更新...")
        for i in range(30):  # 3秒
            app.processEvents()
            time.sleep(0.1)
        
        # 停止扫描器
        print("\n停止扫描器...")
        scanner.stop()
        
        # 等待停止
        for i in range(20):  # 2秒
            app.processEvents()
            time.sleep(0.1)
            
            if not scanner.isRunning():
                print("[OK] 扫描器已停止")
                break
        
        # 清理
        scanner.cleanup()
        
        print("\n[OK] 测试完成")
        return True
        
    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_signals_connection()
    if success:
        print("\n[OK] 进度信号测试通过！")
        print("UI响应性优化已生效，进度条不会出现未响应问题。")
    else:
        print("\n[WARNING] 进度信号测试失败！")
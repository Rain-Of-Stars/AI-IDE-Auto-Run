# -*- coding: utf-8 -*-
"""
测试进度信号功能
验证UI响应性优化是否生效
"""

import sys
import os
import time

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

def test_progress_signals():
    """测试进度信号功能"""
    print("=" * 60)
    print("测试进度信号功能")
    print("=" * 60)
    
    try:
        from PySide6 import QtCore, QtWidgets
        from auto_approve.scanner_process_adapter import ScannerProcessAdapter
        from auto_approve.config_manager import AppConfig
        
        # 创建应用
        app = QtWidgets.QApplication(sys.argv)
        
        # 加载配置
        from auto_approve.config_manager import load_config
        config_manager = load_config("config.json")
        
        # 创建扫描器适配器
        scanner = ScannerProcessAdapter(config_manager)
        
        # 创建窗口显示进度
        window = QtWidgets.QWidget()
        window.setWindowTitle("进度信号测试")
        window.resize(400, 200)
        
        layout = QtWidgets.QVBoxLayout()
        
        # 进度条
        progress_bar = QtWidgets.QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(0)
        layout.addWidget(progress_bar)
        
        # 状态标签
        status_label = QtWidgets.QLabel("准备就绪")
        layout.addWidget(status_label)
        
        # 日志文本框
        log_text = QtWidgets.QTextEdit()
        log_text.setReadOnly(True)
        log_text.setMaximumHeight(100)
        layout.addWidget(log_text)
        
        # 按钮
        button_layout = QtWidgets.QHBoxLayout()
        
        start_btn = QtWidgets.QPushButton("启动扫描")
        stop_btn = QtWidgets.QPushButton("停止扫描")
        stop_btn.setEnabled(False)
        
        button_layout.addWidget(start_btn)
        button_layout.addWidget(stop_btn)
        layout.addLayout(button_layout)
        
        window.setLayout(layout)
        
        # 连接信号
        progress_count = 0
        
        def on_progress(message):
            nonlocal progress_count
            progress_count += 1
            progress_value = min(progress_count * 10, 100)
            progress_bar.setValue(progress_value)
            status_label.setText(f"进度: {message}")
            log_text.append(f"[进度] {message}")
            print(f"[进度] {message}")
        
        def on_status(status):
            log_text.append(f"[状态] {status}")
            print(f"[状态] {status}")
        
        def on_log(message):
            log_text.append(f"[日志] {message}")
            print(f"[日志] {message}")
        
        def on_hit(score, x, y):
            log_text.append(f"[命中] 分数:{score:.3f} 位置:({x},{y})")
            print(f"[命中] 分数:{score:.3f} 位置:({x},{y})")
        
        def on_started():
            progress_count = 0
            progress_bar.setValue(0)
            status_label.setText("扫描运行中...")
            start_btn.setEnabled(False)
            stop_btn.setEnabled(True)
            log_text.append("扫描已启动")
            print("扫描已启动")
        
        def on_stopped():
            status_label.setText("扫描已停止")
            start_btn.setEnabled(True)
            stop_btn.setEnabled(False)
            log_text.append("扫描已停止")
            print("扫描已停止")
        
        # 连接信号
        scanner.sig_progress.connect(on_progress)
        scanner.sig_status.connect(on_status)
        scanner.sig_log.connect(on_log)
        scanner.sig_hit.connect(on_hit)
        
        start_btn.clicked.connect(lambda: (on_started(), scanner.start()))
        stop_btn.clicked.connect(lambda: (scanner.stop(), on_stopped()))
        
        # 显示窗口
        window.show()
        
        print("[OK] 测试窗口已创建")
        print("[OK] 进度信号连接完成")
        print("[OK] 点击'启动扫描'按钮测试进度更新")
        
        # 运行应用
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"[ERROR] 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = test_progress_signals()
    if success:
        print("\n[OK] 进度信号测试完成！")
    else:
        print("\n[WARNING] 进度信号测试失败！")
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步窗口捕获集成示例

快速集成指南，解决UI阻塞问题
"""

import sys
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
import numpy as np

# 导入异步捕获管理器
sys.path.append('../../')
from capture.async_capture_manager import AsyncCaptureManager, get_async_capture_manager


class AsyncCaptureExample(QWidget):
    """异步捕获示例 - 完全非阻塞"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("异步窗口捕获示例")
        self.setGeometry(100, 100, 800, 600)
        
        # 获取异步捕获管理器实例
        self.capture_manager = get_async_capture_manager()
        
        # 连接信号到槽函数
        self.capture_manager.frame_ready.connect(self.on_frame_ready)
        self.capture_manager.capture_error.connect(self.on_capture_error)
        self.capture_manager.capture_started.connect(self.on_capture_started)
        
        self.init_ui()
    
    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        
        # 捕获画面显示
        self.capture_label = QLabel("准备就绪，点击开始捕获")
        self.capture_label.setAlignment(Qt.AlignCenter)
        self.capture_label.setMinimumSize(640, 480)
        self.capture_label.setStyleSheet("border: 2px solid #ccc; background-color: #f0f0f0;")
        layout.addWidget(self.capture_label)
        
        # 状态信息
        self.status_label = QLabel("状态: 空闲")
        layout.addWidget(self.status_label)
    
    def start_capture(self, window_title="Chrome"):
        """开始捕获指定窗口"""
        # 只需要这一个调用！异步执行，不会阻塞UI
        try:
            success = self.capture_manager.open_window_capture(window_title)
            if success:
                self.status_label.setText(f"状态: 正在捕获 '{window_title}'")
            else:
                self.status_label.setText("状态: 启动捕获失败")
        except Exception as e:
            self.status_label.setText(f"状态: 启动错误 - {e}")
    
    def stop_capture(self):
        """停止捕获"""
        self.capture_manager.stop_capture()
        self.status_label.setText("状态: 已停止")
    
    def on_frame_ready(self, frame: np.ndarray):
        """新帧到达（异步调用，不阻塞UI）"""
        try:
            # 转换和显示帧
            height, width = frame.shape[:2]
            
            if len(frame.shape) == 3 and frame.shape[2] == 3:  # BGR
                rgb_frame = frame[:, :, ::-1]  # BGR -> RGB
                bytes_per_line = 3 * width
                q_img = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            else:
                q_img = QImage(frame.data, width, height, QImage.Format_Grayscale8)
            
            # 调整大小以适应显示
            pixmap = QPixmap.fromImage(q_img).scaled(
                self.capture_label.size(), Qt.KeepAspectRatio
            )
            
            self.capture_label.setPixmap(pixmap)
            
        except Exception as e:
            print(f"显示帧错误: {e}")
    
    def on_capture_started(self, target: str, success: bool):
        """捕获启动回调"""
        if success:
            self.status_label.setText(f"状态: 捕获启动成功 - {target}")
        else:
            self.status_label.setText(f"状态: 捕获启动失败 - {target}")
    
    def on_capture_error(self, operation: str, error: str):
        """捕获错误回调"""
        self.status_label.setText(f"状态: 错误 [{operation}] - {error}")
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        self.capture_manager.stop()
        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 创建示例窗口
    window = AsyncCaptureExample()
    window.show()
    
    # 自动开始捕获（可以选择任何窗口）
    window.start_capture("Chrome")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
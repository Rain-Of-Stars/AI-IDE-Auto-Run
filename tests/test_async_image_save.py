#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试异步图像保存功能
验证非阻塞保存是否能正常工作，不会冻结UI
"""

import sys
import time
import numpy as np
from pathlib import Path
from PySide6 import QtWidgets, QtCore, QtGui

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from workers.io_tasks import submit_image_save


class TestAsyncSaveDialog(QtWidgets.QDialog):
    """测试异步保存对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("异步图像保存测试")
        self.resize(400, 300)
        
        # 创建一个测试图像 (彩色渐变)
        self.test_image = np.zeros((480, 640, 3), dtype=np.uint8)
        for i in range(480):
            for j in range(640):
                self.test_image[i, j] = [j % 256, i % 256, (i+j) % 256]
        
        self._setup_ui()
    
    def _setup_ui(self):
        """设置UI"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # 信息标签
        self.info_label = QtWidgets.QLabel("准备测试异步图像保存功能")
        self.info_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.info_label)
        
        # 状态标签
        self.status_label = QtWidgets.QLabel("状态: 就绪")
        self.status_label.setStyleSheet("color: #666;")
        layout.addWidget(self.status_label)
        
        # 进度条
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # 测试按钮
        button_layout = QtWidgets.QHBoxLayout()
        
        self.test_button = QtWidgets.QPushButton("开始异步保存测试")
        self.test_button.clicked.connect(self.test_async_save)
        button_layout.addWidget(self.test_button)
        
        self.sync_test_button = QtWidgets.QPushButton("测试阻塞保存(对比)")
        self.sync_test_button.clicked.connect(self.test_sync_save)
        button_layout.addWidget(self.sync_test_button)
        
        layout.addLayout(button_layout)
        
        # 计时器 (用于测试UI响应性)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self._update_timer)
        self.timer.start(100)  # 100ms 更新一次
        
        self.counter = 0
    
    def _update_timer(self):
        """更新计时器，验证UI是否冻结"""
        self.counter += 1
        if self.counter % 10 == 0:  # 每1秒更新一次标题
            self.setWindowTitle(f"异步图像保存测试 - 运行中... ({self.counter//10}s)")
    
    def test_async_save(self):
        """测试异步保存"""
        # 选择保存路径
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "选择保存位置",
            "async_test_image.png",
            "PNG图像 (*.png);;JPEG图像 (*.jpg)"
        )
        
        if not filename:
            return
        
        self.test_button.setEnabled(False)
        self.sync_test_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("正在异步保存图像...")
        
        def on_success(task_id, result):
            """保存成功回调"""
            self.test_button.setEnabled(True)
            self.sync_test_button.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_label.setText("异步保存成功!")
            
            file_size_mb = result['file_size'] / (1024 * 1024)
            QtWidgets.QMessageBox.information(
                self,
                "保存成功",
                f"图像已异步保存:\n{result['file_path']}\n"
                f"大小: {file_size_mb:.2f} MB\n"
                f"UI始终保持响应状态!"
            )
        
        def on_error(task_id, error_message, exception):
            """保存失败回调"""
            self.test_button.setEnabled(True)
            self.sync_test_button.setEnabled(True)
            self.progress_bar.setVisible(False)
            self.status_label.setText("异步保存失败")
            
            QtWidgets.QMessageBox.critical(
                self,
                "保存失败",
                f"异步保存失败:\n{error_message}"
            )
        
        def on_progress(task_id, progress_percent, message):
            """进度回调"""
            self.progress_bar.setValue(progress_percent)
            self.status_label.setText(f"保存进度: {message}")
        
        # 提交异步保存任务
        try:
            from workers.io_tasks import ImageSaveTask, submit_io
            
            task = ImageSaveTask(self.test_image, filename)
            task.signals.progress.connect(on_progress)
            
            submit_io(task, on_success, on_error)
            
        except Exception as e:
            self.test_button.setEnabled(True)
            self.sync_test_button.setEnabled(True)
            self.progress_bar.setVisible(False)
            QtWidgets.QMessageBox.critical(self, "错误", f"无法提交异步任务:\n{e}")
    
    def test_sync_save(self):
        """测试同步保存（会阻塞UI）"""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "选择保存位置(阻塞测试)",
            "sync_test_image.png",
            "PNG图像 (*.png)"
        )
        
        if not filename:
            return
        
        self.test_button.setEnabled(False)
        self.sync_test_button.setEnabled(False)
        self.status_label.setText("正在同步保存图像...")
        QtWidgets.QApplication.processEvents()
        
        # 模拟一个大文件保存，故意延迟
        import cv2
        import time
        
        # 创建一个更大的图像来延长保存时间
        large_image = np.zeros((1080, 1920, 3), dtype=np.uint8)
        for i in range(1080):
            for j in range(1920):
                large_image[i, j] = [j % 256, i % 256, (i+j) % 256]
        
        time.sleep(2)  # 模拟阻塞操作
        
        try:
            success = cv2.imwrite(filename, large_image)
            if success:
                self.status_label.setText("同步保存完成")
                QtWidgets.QMessageBox.information(
                    self,
                    "同步保存完成",
                    "同步保存完成!\n注意：保存期间UI被阻塞了约2秒"
                )
            else:
                self.status_label.setText("同步保存失败")
                QtWidgets.QMessageBox.warning(self, "失败", "保存失败")
        except Exception as e:
            self.status_label.setText("同步保存失败")
            QtWidgets.QMessageBox.critical(self, "错误", f"保存失败: {e}")
        finally:
            self.test_button.setEnabled(True)
            self.sync_test_button.setEnabled(True)


def main():
    """主函数"""
    app = QtWidgets.QApplication(sys.argv)
    dialog = TestAsyncSaveDialog()
    dialog.show()
    
    print("异步图像保存测试工具已启动")
    print("1. 点击'开始异步保存测试' - 测试非阻塞保存")
    print("2. 点击'测试阻塞保存(对比)' - 体验传统阻塞保存")
    print("3. 观察UI计时器是否持续更新，验证界面响应性")
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异步窗口捕获非阻塞测试

测试异步捕获管理器是否能保持UI响应性，区别于传统的同步捕获方法
"""

import sys
import time
import numpy as np
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QLabel, QTextEdit, QProgressBar, QSpinBox,
                              QComboBox, QMessageBox)
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QImage, QPixmap

# 导入捕获管理器
sys.path.append('../../')
from capture.async_capture_manager import AsyncCaptureManager, CaptureResult
from capture.capture_manager import CaptureManager
from auto_approve.logger_manager import get_logger


class UIResponsivnessTest(QObject):
    """UI响应性测试类"""
    
    # 测试信号
    ui_response_test = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        self._test_active = False
        self._response_times = []
        self._test_timer = QTimer()
        self._test_timer.timeout.connect(self._perform_responsiveness_test)
    
    def start_test(self, interval_ms: int = 100):
        """开始响应性测试"""
        self._test_active = True
        self._response_times = []
        self._test_timer.start(interval_ms)
        self.logger.info(f"UI响应性测试已开始，间隔: {interval_ms}ms")
    
    def stop_test(self):
        """停止响应性测试"""
        self._test_active = False
        self._test_timer.stop()
        self.logger.info("UI响应性测试已停止")
    
    def _perform_responsiveness_test(self):
        """执行响应性测试"""
        test_start = time.time()
        
        # 发送信号测试UI线程响应
        self.ui_response_test.emit()
        
        # 计算响应时间
        response_time = (time.time() - test_start) * 1000  # 转换为毫秒
        self._response_times.append(response_time)
        
        # 保持最近的100个样本
        if len(self._response_times) > 100:
            self._response_times.pop(0)
    
    def get_average_response_time(self) -> float:
        """获取平均响应时间"""
        if not self._response_times:
            return 0.0
        return sum(self._response_times) / len(self._response_times)
    
    def get_max_response_time(self) -> float:
        """获取最大响应时间"""
        if not self._response_times:
            return 0.0
        return max(self._response_times)
    
    def get_stats(self) -> dict:
        """获取测试统计"""
        if not self._response_times:
            return {
                'avg_response_ms': 0.0,
                'max_response_ms': 0.0,
                'samples': 0,
                'test_active': self._test_active
            }
        
        return {
            'avg_response_ms': self.get_average_response_time(),
            'max_response_ms': self.get_max_response_time(),
            'samples': len(self._response_times),
            'test_active': self._test_active
        }


class AsyncCaptureTestWindow(QMainWindow):
    """异步捕获测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        
        # 捕获管理器
        self._async_manager = AsyncCaptureManager()
        self._sync_manager = CaptureManager()  # 用于对比测试
        
        # UI响应性测试器
        self._ui_test = UIResponsivnessTest()
        self._ui_test.ui_response_test.connect(self._handle_ui_test_signal)
        
        # 状态变量
        self._using_async = True
        self._capturing = False
        self._frames_captured = 0
        self._capture_start_time = 0
        
        self.init_ui()
        self.connect_signals()
        
    def init_ui(self):
        """初始化UI界面"""
        self.setWindowTitle("异步窗口捕获非阻塞测试")
        self.setGeometry(100, 100, 1200, 800)
        
        # 主布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # 控制面板
        control_group = QWidget()
        control_layout = QVBoxLayout(control_group)
        
        # 捕获模式选择
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("捕获模式:"))
        
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["异步捕获", "同步捕获 (对比测试)"])
        mode_layout.addWidget(self.mode_combo)
        
        self.start_btn = QPushButton("开始捕获")
        self.stop_btn = QPushButton("停止捕获")
        self.stop_btn.setEnabled(False)
        
        mode_layout.addWidget(self.start_btn)
        mode_layout.addWidget(self.stop_btn)
        control_layout.addLayout(mode_layout)
        
        # 目标选择
        target_layout = QHBoxLayout()
        target_layout.addWidget(QLabel("捕获目标:"))
        
        self.target_input = QComboBox()
        self.target_input.setEditable(True)
        self.target_input.addItems([
            "Chrome",
            "Visual Studio Code",
            "Notepad",
            "cmd.exe",
            "资源管理器"
        ])
        target_layout.addWidget(self.target_input)
        
        target_layout.addWidget(QLabel("帧率:"))
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 60)
        self.fps_spin.setValue(30)
        target_layout.addWidget(self.fps_spin)
        
        control_layout.addLayout(target_layout)
        
        # 统计信息
        stats_layout = QHBoxLayout()
        self.stats_label = QLabel("准备就绪")
        self.frame_count_label = QLabel("帧数: 0")
        self.capture_time_label = QLabel("捕获时间: 0s")
        self.ui_response_label = QLabel("UI响应: 0ms")
        
        stats_layout.addWidget(self.stats_label)
        stats_layout.addWidget(self.frame_count_label)
        stats_layout.addWidget(self.capture_time_label)
        stats_layout.addWidget(self.ui_response_label)
        
        control_layout.addLayout(stats_layout)
        
        layout.addWidget(control_group)
        
        # 影像显示区域
        display_layout = QHBoxLayout()
        
        # 左侧 - 捕获画面
        left_panel = QVBoxLayout()
        left_panel.addWidget(QLabel("捕获画面:"))
        
        self.capture_label = QLabel("等待捕获...")
        self.capture_label.setMinimumSize(640, 480)
        self.capture_label.setStyleSheet("border: 2px solid #ccc; background-color: #f0f0f0;")
        self.capture_label.setAlignment(Qt.AlignCenter)
        left_panel.addWidget(self.capture_label)
        
        display_layout.addLayout(left_panel)
        
        # 右侧 - 响应性测试
        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("UI响应性测试:"))
        
        self.response_text = QTextEdit()
        self.response_text.setMaximumHeight(200)
        right_panel.addWidget(self.response_text)
        
        # 响应性测试按钮
        test_btn_layout = QHBoxLayout()
        self.start_test_btn = QPushButton("开始响应性测试")
        self.stop_test_btn = QPushButton("停止响应性测试")
        self.stop_test_btn.setEnabled(False)
        
        test_btn_layout.addWidget(self.start_test_btn)
        test_btn_layout.addWidget(self.stop_test_btn)
        right_panel.addLayout(test_btn_layout)
        
        # 动态响应性指示器
        self.response_bar = QProgressBar()
        self.response_bar.setRange(0, 1000)  # 0-1000ms范围
        self.response_bar.setValue(0)
        self.response_bar.setTextVisible(True)
        self.response_bar.setFormat("UI响应: %vms")
        right_panel.addWidget(self.response_bar)
        
        display_layout.addLayout(right_panel)
        layout.addLayout(display_layout)
        
        # 日志输出
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("background-color: #f8f8f8; font-family: monospace;")
        layout.addWidget(QLabel("日志输出:"))
        layout.addWidget(self.log_text)
        
        # 状态栏
        self.statusBar().showMessage("准备就绪，选择捕获模式并点击开始捕获")
    
    def connect_signals(self):
        """连接信号槽"""
        self.start_btn.clicked.connect(self.start_capture)
        self.stop_btn.clicked.connect(self.stop_capture)
        
        self.start_test_btn.clicked.connect(self.start_ui_test)
        self.stop_test_btn.clicked.connect(self.stop_ui_test)
        
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        self.fps_spin.valueChanged.connect(self.on_fps_changed)
        
        # 捕获管理器信号
        self._async_manager.frame_ready.connect(self.on_async_frame_ready)
        self._async_manager.capture_error.connect(self.on_capture_error)
        self._async_manager.capture_started.connect(self.on_capture_started)
    
    def on_mode_changed(self, mode_text):
        """捕获模式改变"""
        self._using_async = ("异步" in mode_text)
        self.logger.info(f"切换到 {'异步' if self._using_async else '同步'} 捕获模式")
        
        # 如果正在捕获，提示重新启动
        if self._capturing:
            self.log_message("警告: 需要停止并重新启动捕获才能应用新模式")
    
    def on_fps_changed(self, fps):
        """帧率改变"""
        if self._using_async:
            self._async_manager.set_fps(fps)
            self.log_message(f"异步捕获帧率设置为: {fps} FPS")
    
    def start_capture(self):
        """开始捕获"""
        target = self.target_input.currentText().strip()
        if not target:
            QMessageBox.warning(self, "警告", "请输入捕获目标")
            return
        
        self._capturing = True
        self._frames_captured = 0
        self._capture_start_time = time.time()
        
        # 重置捕获画面
        self.capture_label.setText("正在启动捕获...")
        self.capture_label.setStyleSheet("border: 2px solid #007acc; background-color: #e6f3ff;")
        
        # 更新UI状态
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.target_input.setEnabled(False)
        self.mode_combo.setEnabled(False)
        
        if self._using_async:
            # 异步捕获
            fps = self.fps_spin.value()
            self._async_manager.set_fps(fps)
            success = self._async_manager.open_window_capture(
                target=target,
                partial_match=True,
                callback=self.on_async_open_result
            )
            if success:
                self.log_message(f"异步捕获已启动，目标: {target}, FPS: {fps}")
                self.statusBar().showMessage(f"异步捕获运行中 - 目标: {target}")
            else:
                self.log_message("异步捕获启动失败")
                self.stop_capture()
        else:
            # 同步捕获（对比测试）
            try:
                success = self._sync_manager.open_window(target)
                if success:
                    self.log_message(f"同步捕获已启动，目标: {target}")
                    # 手动定时捕获
                    self.start_sync_capture_loop()
                    self.statusBar().showMessage(f"同步捕获运行中 - 目标: {target}")
                else:
                    self.log_message("同步捕获启动失败")
                    self.stop_capture()
            except Exception as e:
                self.log_message(f"同步捕获异常: {e}")
                self.stop_capture()
    
    def stop_capture(self):
        """停止捕获"""
        self._capturing = False
        
        if self._using_async:
            self._async_manager.stop_capture()
        
        # 重置UI状态
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.target_input.setEnabled(True)
        self.mode_combo.setEnabled(True)
        
        self.capture_label.setText("捕获已停止")
        self.capture_label.setStyleSheet("border: 2px solid #ccc; background-color: #f0f0f0;")
        
        self.statusBar().showMessage("捕获已停止")
        self.log_message("捕获已停止")
    
    def start_sync_capture_loop(self):
        """同步捕获循环"""
        if not self._capturing or self._using_async:
            return
        
        try:
            frame = self._sync_manager.capture_frame()
            if frame is not None:
                self.on_sync_frame_ready(frame)
        except Exception as e:
            self.log_message(f"同步捕获帧失败: {e}")
        
        if self._capturing:
            # 继续使用定时器，限制帧率
            fps = self.fps_spin.value()
            interval = max(16, 1000 // fps)  # 最少16ms，约60FPS
            QTimer.singleShot(interval, self.start_sync_capture_loop)
    
    def on_async_frame_ready(self, frame: np.ndarray):
        """异步捕获帧准备好"""
        self.handle_frame_ready(frame, "异步")
    
    def on_sync_frame_ready(self, frame: np.ndarray):
        """同步捕获帧准备好"""
        self.handle_frame_ready(frame, "同步")
    
    def handle_frame_ready(self, frame: np.ndarray, capture_type: str):
        """处理捕获帧"""
        self._frames_captured += 1
        
        # 转换为QImage显示
        try:
            height, width = frame.shape[:2]
            if len(frame.shape) == 3 and frame.shape[2] == 3:  # BGR
                # OpenCV BGR -> Qt RGB
                rgb_frame = frame[:, :, ::-1]
                bytes_per_line = 3 * width
                q_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            else:
                q_image = QImage(frame.data, width, height, QImage.Format_Grayscale8)
            
            # 缩放以适应显示区域
            scaled_pixmap = QPixmap.fromImage(q_image).scaled(
                640, 480, Qt.KeepAspectRatio
            )
            self.capture_label.setPixmap(scaled_pixmap)
            
        except Exception as e:
            self.log_message(f"显示帧失败: {e}")
        
        # 更新统计信息
        capture_time = time.time() - self._capture_start_time
        self.frame_count_label.setText(f"帧数: {self._frames_captured}")
        self.capture_time_label.setText(f"捕获时间: {capture_time:.1f}s")
        self.stats_label.setText(f"{capture_type}捕获 - 正常运行")
        
        # 更新UI响应性测试统计
        self.update_ui_response_stats()
    
    def on_async_open_result(self, result: CaptureResult):
        """异步打开结果"""
        self.log_message(f"异步捕获启动结果: {'成功' if result.success else '失败'}")
        if not result.success:
            self.log_message(f"错误信息: {result.error}")
            self.stop_capture()
    
    def on_capture_started(self, target: str, success: bool):
        """捕获启动回调"""
        self.log_message(f"捕获启动: {target}, 成功: {success}")
    
    def on_capture_error(self, operation: str, error: str):
        """捕获错误"""
        self.log_message(f"捕获错误 [{operation}]: {error}")
        QMessageBox.critical(self, "捕获错误", f"{operation}: {error}")
        self.stop_capture()
    
    def start_ui_test(self):
        """开始UI响应性测试"""
        self._ui_test.start_test(interval_ms=100)  # 100ms间隔
        
        self.start_test_btn.setEnabled(False)
        self.stop_test_btn.setEnabled(True)
        
        self.log_message("UI响应性测试已启动")
    
    def stop_ui_test(self):
        """停止UI响应性测试"""
        self._ui_test.stop_test()
        
        self.start_test_btn.setEnabled(True)
        self.stop_test_btn.setEnabled(False)
        
        # 显示测试结果
        stats = self._ui_test.get_stats()
        self.log_message(f"UI响应性测试停止 - 平均响应: {stats['avg_response_ms']:.1f}ms, 最大响应: {stats['max_response_ms']:.1f}ms")
    
    def _handle_ui_test_signal(self):
        """处理UI测试信号"""
        # 信号已接收到，用于测试UI线程响应
        pass
    
    def update_ui_response_stats(self):
        """更新UI响应性统计"""
        stats = self._ui_test.get_stats()
        if stats['samples'] > 0:
            self.ui_response_label.setText(f"UI响应: {stats['avg_response_ms']:.1f}ms")
            # 更新进度条
            response_ms = min(1000, int(stats['avg_response_ms']))  # 限制在1000ms以内
            self.response_bar.setValue(response_ms)
            
            # 根据响应时间设置颜色
            if response_ms < 50:
                self.response_bar.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
            elif response_ms < 100:
                self.response_bar.setStyleSheet("QProgressBar::chunk { background-color: #FFC107; }")
            else:
                self.response_bar.setStyleSheet("QProgressBar::chunk { background-color: #F44336; }")
    
    def log_message(self, message: str):
        """记录日志消息"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        self.log_text.append(log_entry)
        self.logger.info(message)
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止所有活动
        if self._capturing:
            self.stop_capture()
        
        if self._ui_test.get_stats()['test_active']:
            self.stop_ui_test()
        
        # 停止异步管理器
        self._async_manager.stop()
        
        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 创建并显示测试窗口
    window = AsyncCaptureTestWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
# -*- coding: utf-8 -*-
"""
UI响应性测试脚本

测试修复后的捕获功能是否还会导致UI卡顿
"""

import sys
import time
import threading
from PySide6 import QtWidgets, QtCore, QtGui

# 添加项目路径
sys.path.insert(0, r'd:\Person_project\AI_IDE_Auto_Run_github_main_V4.2')


class UIResponsivenessTest(QtWidgets.QMainWindow):
    """UI响应性测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UI响应性测试 - 捕获功能修复验证")
        self.resize(600, 400)
        
        # 设置中央部件
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        
        # 布局
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # 状态显示
        self.status_label = QtWidgets.QLabel("准备测试...")
        self.status_label.setStyleSheet("font-size: 14px; padding: 10px;")
        layout.addWidget(self.status_label)
        
        # UI响应性指示器
        self.response_indicator = QtWidgets.QProgressBar()
        self.response_indicator.setRange(0, 100)
        self.response_indicator.setValue(0)
        layout.addWidget(QtWidgets.QLabel("UI响应性指示器（绿色=正常，红色=卡顿）:"))
        layout.addWidget(self.response_indicator)
        
        # 测试按钮
        button_layout = QtWidgets.QHBoxLayout()
        
        self.test_old_btn = QtWidgets.QPushButton("测试旧版捕获（会卡顿）")
        self.test_new_btn = QtWidgets.QPushButton("测试新版捕获（已修复）")
        self.test_ui_btn = QtWidgets.QPushButton("测试UI响应性")
        
        button_layout.addWidget(self.test_old_btn)
        button_layout.addWidget(self.test_new_btn)
        button_layout.addWidget(self.test_ui_btn)
        
        layout.addLayout(button_layout)
        
        # 日志显示
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setMaximumHeight(200)
        layout.addWidget(QtWidgets.QLabel("测试日志:"))
        layout.addWidget(self.log_text)
        
        # 连接信号
        self.test_old_btn.clicked.connect(self.test_old_capture)
        self.test_new_btn.clicked.connect(self.test_new_capture)
        self.test_ui_btn.clicked.connect(self.test_ui_responsiveness)
        
        # UI响应性监控定时器
        self.ui_timer = QtCore.QTimer()
        self.ui_timer.timeout.connect(self.update_ui_indicator)
        self.ui_timer.start(50)  # 每50ms检查一次
        
        self.last_update_time = time.time()
        self.ui_freeze_count = 0
        
    def log_message(self, message: str):
        """记录日志消息"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        # 确保日志滚动到底部
        cursor = self.log_text.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        self.log_text.setTextCursor(cursor)
        
    def update_ui_indicator(self):
        """更新UI响应性指示器"""
        current_time = time.time()
        time_diff = (current_time - self.last_update_time) * 1000  # 转换为毫秒
        
        if time_diff > 100:  # 超过100ms认为是卡顿
            self.ui_freeze_count += 1
            # 红色表示卡顿
            self.response_indicator.setStyleSheet("""
                QProgressBar::chunk {
                    background-color: #ff4444;
                }
            """)
            self.response_indicator.setValue(max(0, 100 - int(time_diff / 10)))
        else:
            # 绿色表示正常
            self.response_indicator.setStyleSheet("""
                QProgressBar::chunk {
                    background-color: #44ff44;
                }
            """)
            self.response_indicator.setValue(100)
            
        self.last_update_time = current_time
        
    def test_old_capture(self):
        """测试旧版捕获方法（模拟阻塞）"""
        self.log_message("开始测试旧版捕获方法...")
        self.test_old_btn.setEnabled(False)
        
        try:
            # 模拟旧版本的阻塞操作
            self.status_label.setText("正在执行阻塞捕获操作...")
            
            # 直接在主线程中执行耗时操作（模拟旧版本问题）
            start_time = time.time()
            time.sleep(2)  # 模拟2秒阻塞
            end_time = time.time()
            
            duration = (end_time - start_time) * 1000
            self.log_message(f"旧版捕获完成，耗时: {duration:.0f}ms（主线程阻塞）")
            self.status_label.setText(f"旧版捕获测试完成 - 卡顿次数: {self.ui_freeze_count}")
            
        except Exception as e:
            self.log_message(f"测试失败: {e}")
        finally:
            self.test_old_btn.setEnabled(True)
            
    def test_new_capture(self):
        """测试新版捕获方法（非阻塞）"""
        self.log_message("开始测试新版非阻塞捕获方法...")
        self.test_new_btn.setEnabled(False)
        
        try:
            from tests.test_non_blocking_capture import NonBlockingCaptureTest
            
            self.status_label.setText("正在执行非阻塞捕获操作...")
            
            # 创建非阻塞测试器
            self.capture_tester = NonBlockingCaptureTest(self)
            
            # 连接信号
            self.capture_tester.progress_updated.connect(self.on_capture_progress)
            self.capture_tester.test_completed.connect(self.on_capture_completed)
            self.capture_tester.test_failed.connect(self.on_capture_failed)
            
            # 使用一个虚拟HWND进行测试（不会真正捕获）
            self.test_start_time = time.time()
            self.capture_tester.test_window_capture_async(123456, timeout_sec=1.0)
            
        except Exception as e:
            self.log_message(f"测试失败: {e}")
            self.test_new_btn.setEnabled(True)
            
    def on_capture_progress(self, progress: int, message: str):
        """捕获进度回调"""
        self.status_label.setText(f"新版捕获进度: {progress}% - {message}")
        
    def on_capture_completed(self, result):
        """捕获完成回调"""
        duration = (time.time() - self.test_start_time) * 1000
        self.log_message(f"新版捕获完成，耗时: {duration:.0f}ms（后台线程执行）")
        self.status_label.setText(f"新版捕获测试完成 - 卡顿次数: {self.ui_freeze_count}")
        self.test_new_btn.setEnabled(True)
        
    def on_capture_failed(self, error_message: str):
        """捕获失败回调"""
        duration = (time.time() - self.test_start_time) * 1000
        self.log_message(f"新版捕获失败: {error_message}，耗时: {duration:.0f}ms")
        self.status_label.setText(f"新版捕获测试失败 - 卡顿次数: {self.ui_freeze_count}")
        self.test_new_btn.setEnabled(True)
        
    def test_ui_responsiveness(self):
        """测试UI响应性"""
        self.log_message("开始UI响应性测试...")
        
        # 重置卡顿计数
        old_freeze_count = self.ui_freeze_count
        self.ui_freeze_count = 0
        
        # 启动一个高频率的UI更新任务
        self.ui_test_counter = 0
        self.ui_test_timer = QtCore.QTimer()
        self.ui_test_timer.timeout.connect(self.update_ui_test)
        self.ui_test_timer.start(10)  # 每10ms更新一次
        
        # 5秒后停止测试
        QtCore.QTimer.singleShot(5000, self.stop_ui_test)
        
    def update_ui_test(self):
        """更新UI测试"""
        self.ui_test_counter += 1
        self.status_label.setText(f"UI测试中... 更新次数: {self.ui_test_counter}")
        
    def stop_ui_test(self):
        """停止UI测试"""
        if hasattr(self, 'ui_test_timer'):
            self.ui_test_timer.stop()
        
        self.log_message(f"UI响应性测试完成，5秒内更新{self.ui_test_counter}次，卡顿{self.ui_freeze_count}次")
        
        if self.ui_freeze_count == 0:
            self.status_label.setText("✅ UI响应性测试通过 - 无卡顿")
        else:
            self.status_label.setText(f"⚠️ UI响应性测试完成 - 检测到{self.ui_freeze_count}次卡顿")


class TestApplication:
    """测试应用程序"""
    
    def __init__(self):
        self.app = QtWidgets.QApplication(sys.argv)
        self.app.setApplicationName("UI响应性测试")
        
    def run(self):
        """运行测试"""
        # 创建测试窗口
        window = UIResponsivenessTest()
        window.show()
        
        # 显示使用说明
        QtWidgets.QMessageBox.information(
            window,
            "使用说明",
            "这个工具用于测试捕获功能修复后的UI响应性：\n\n"
            "1. 点击'测试旧版捕获'会模拟原来的阻塞问题\n"
            "2. 点击'测试新版捕获'使用修复后的非阻塞方法\n"
            "3. 点击'测试UI响应性'进行综合响应性测试\n\n"
            "观察进度条颜色：绿色=正常，红色=卡顿\n"
            "查看日志了解详细测试结果。"
        )
        
        # 启动事件循环
        return self.app.exec()


def main():
    """主函数"""
    print("🧪 启动UI响应性测试...")
    
    try:
        test_app = TestApplication()
        exit_code = test_app.run()
        
        print(f"✅ 测试完成，退出代码: {exit_code}")
        return exit_code
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

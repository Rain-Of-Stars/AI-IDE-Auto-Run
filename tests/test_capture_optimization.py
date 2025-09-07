# -*- coding: utf-8 -*-
"""
捕获测试优化验证脚本
验证测试捕获功能优化后的效果
"""
import os
import sys
import time
import threading
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets, QtCore
from auto_approve.smart_capture_test_manager import get_smart_capture_manager
from auto_approve.logger_manager import get_logger


class CaptureOptimizationTest(QtWidgets.QWidget):
    """捕获优化测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        self.test_results: List[Dict[str, Any]] = []
        
        # 获取智能捕获测试管理器
        self.capture_manager = get_smart_capture_manager()
        
        # 连接信号
        self.capture_manager.test_started.connect(self._on_test_started)
        self.capture_manager.progress_updated.connect(self._on_progress_updated)
        self.capture_manager.test_completed.connect(self._on_test_completed)
        self.capture_manager.test_failed.connect(self._on_test_failed)
        self.capture_manager.test_finished.connect(self._on_test_finished)
        
        self._setup_ui()
        
        self.logger.info("捕获优化测试初始化完成")
    
    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("捕获功能优化验证")
        self.setGeometry(100, 100, 800, 600)
        
        layout = QtWidgets.QVBoxLayout()
        
        # 标题
        title = QtWidgets.QLabel("捕获功能优化验证测试")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # 测试控制
        control_layout = QtWidgets.QHBoxLayout()
        
        self.btn_test_window = QtWidgets.QPushButton("测试窗口捕获")
        self.btn_test_window.clicked.connect(self._test_window_capture)
        control_layout.addWidget(self.btn_test_window)
        
        self.btn_test_monitor = QtWidgets.QPushButton("测试屏幕捕获")
        self.btn_test_monitor.clicked.connect(self._test_monitor_capture)
        control_layout.addWidget(self.btn_test_monitor)
        
        self.btn_stress_test = QtWidgets.QPushButton("压力测试")
        self.btn_stress_test.clicked.connect(self._stress_test)
        control_layout.addWidget(self.btn_stress_test)
        
        self.btn_clear_results = QtWidgets.QPushButton("清空结果")
        self.btn_clear_results.clicked.connect(self._clear_results)
        control_layout.addWidget(self.btn_clear_results)
        
        layout.addLayout(control_layout)
        
        # 测试参数
        params_layout = QtWidgets.QHBoxLayout()
        
        params_layout.addWidget(QtWidgets.QLabel("测试HWND:"))
        self.hwnd_input = QtWidgets.QSpinBox()
        self.hwnd_input.setRange(0, 999999)
        self.hwnd_input.setValue(123456)  # 默认测试值
        params_layout.addWidget(self.hwnd_input)
        
        params_layout.addWidget(QtWidgets.QLabel("屏幕索引:"))
        self.monitor_input = QtWidgets.QSpinBox()
        self.monitor_input.setRange(0, 9)
        self.monitor_input.setValue(0)
        params_layout.addWidget(self.monitor_input)
        
        layout.addLayout(params_layout)
        
        # 进度显示
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        self.status_label = QtWidgets.QLabel("就绪")
        self.status_label.setStyleSheet("font-size: 12px; padding: 5px;")
        layout.addWidget(self.status_label)
        
        # 测试结果显示
        results_group = QtWidgets.QGroupBox("测试结果")
        results_layout = QtWidgets.QVBoxLayout()
        
        self.text_results = QtWidgets.QTextEdit()
        self.text_results.setMaximumHeight(300)
        results_layout.addWidget(self.text_results)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        self.setLayout(layout)
    
    def _test_window_capture(self):
        """测试窗口捕获"""
        hwnd = self.hwnd_input.value()
        if hwnd <= 0:
            QtWidgets.QMessageBox.warning(self, "警告", "请输入有效的HWND")
            return
            
        self._update_ui_state(False)
        self.status_label.setText("正在测试窗口捕获...")
        
        # 启动智能测试
        self.capture_manager.start_smart_window_test(hwnd)
    
    def _test_monitor_capture(self):
        """测试屏幕捕获"""
        monitor_index = self.monitor_input.value()
        
        self._update_ui_state(False)
        self.status_label.setText(f"正在测试屏幕捕获（显示器 {monitor_index}）...")
        
        # 启动智能测试
        self.capture_manager.start_smart_monitor_test(monitor_index)
    
    def _stress_test(self):
        """压力测试"""
        self._update_ui_state(False)
        self.status_label.setText("正在进行压力测试...")
        
        # 在后台线程运行压力测试
        def stress_test_thread():
            try:
                # 连续测试多次
                for i in range(5):
                    if i % 2 == 0:
                        # 窗口捕获测试
                        hwnd = self.hwnd_input.value() or 123456
                        self.capture_manager.start_smart_window_test(hwnd)
                    else:
                        # 屏幕捕获测试
                        monitor_index = self.monitor_input.value()
                        self.capture_manager.start_smart_monitor_test(monitor_index)
                    
                    # 等待测试完成
                    time.sleep(1)
                
                # 在主线程更新UI
                QtCore.QTimer.singleShot(0, lambda: self.status_label.setText("压力测试完成"))
                QtCore.QTimer.singleShot(0, lambda: self._update_ui_state(True))
                
            except Exception as e:
                error_msg = f"压力测试失败: {e}"
                QtCore.QTimer.singleShot(0, lambda: self.status_label.setText(error_msg))
                QtCore.QTimer.singleShot(0, lambda: self._update_ui_state(True))
        
        threading.Thread(target=stress_test_thread, daemon=True).start()
    
    def _clear_results(self):
        """清空测试结果"""
        self.test_results.clear()
        self.text_results.clear()
        self.status_label.setText("结果已清空")
    
    def _update_ui_state(self, enabled: bool):
        """更新UI状态"""
        self.btn_test_window.setEnabled(enabled)
        self.btn_test_monitor.setEnabled(enabled)
        self.btn_stress_test.setEnabled(enabled)
        self.hwnd_input.setEnabled(enabled)
        self.monitor_input.setEnabled(enabled)
        
        if enabled:
            self.progress_bar.setValue(0)
    
    def _on_test_started(self, test_type: str):
        """测试开始"""
        self.logger.info(f"捕获测试开始: {test_type}")
        self.status_label.setText(f"正在测试{test_type}捕获...")
    
    def _on_progress_updated(self, progress: int, message: str):
        """进度更新"""
        self.progress_bar.setValue(progress)
        self.status_label.setText(message)
    
    def _on_test_completed(self, result):
        """测试完成"""
        # 记录结果
        test_result = {
            'success': result.success,
            'duration_ms': result.duration_ms,
            'metadata': result.metadata,
            'timestamp': time.time()
        }
        self.test_results.append(test_result)
        
        # 显示结果
        result_text = f"✅ 测试完成 (耗时: {result.duration_ms}ms)\n"
        if result.metadata:
            if 'hwnd' in result.metadata:
                result_text += f"   HWND: {result.metadata['hwnd']}\n"
            if 'monitor_index' in result.metadata:
                result_text += f"   显示器: {result.metadata['monitor_index']}\n"
            if 'image_shape' in result.metadata:
                shape = result.metadata['image_shape']
                result_text += f"   图像尺寸: {shape}\n"
        
        self.text_results.append(result_text)
        
        self.logger.info(f"捕获测试完成: 成功={result.success}, 耗时={result.duration_ms}ms")
    
    def _on_test_failed(self, error_message: str):
        """测试失败"""
        # 记录失败结果
        test_result = {
            'success': False,
            'error': error_message,
            'timestamp': time.time()
        }
        self.test_results.append(test_result)
        
        # 显示失败信息
        self.text_results.append(f"❌ 测试失败: {error_message}\n")
        
        self.logger.warning(f"捕获测试失败: {error_message}")
    
    def _on_test_finished(self):
        """测试完成（最终清理）"""
        self.status_label.setText("测试完成")
        self._update_ui_state(True)
        
        # 显示自适应超时信息
        timeout = self.capture_manager.get_adaptive_timeout()
        self.text_results.append(f"当前自适应超时: {timeout:.1f}秒\n")
    
    def show_statistics(self):
        """显示统计信息"""
        if not self.test_results:
            QtWidgets.QMessageBox.information(self, "统计", "暂无测试数据")
            return
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.get('success', False))
        failed_tests = total_tests - successful_tests
        
        if successful_tests > 0:
            successful_durations = [r['duration_ms'] for r in self.test_results if r.get('success', False)]
            avg_duration = sum(successful_durations) / len(successful_durations)
            min_duration = min(successful_durations)
            max_duration = max(successful_durations)
        else:
            avg_duration = min_duration = max_duration = 0
        
        stats_text = f"""测试统计信息:
总测试次数: {total_tests}
成功次数: {successful_tests}
失败次数: {failed_tests}
成功率: {successful_tests/total_tests*100:.1f}%

平均耗时: {avg_duration:.1f}ms
最短耗时: {min_duration:.1f}ms
最长耗时: {max_duration:.1f}ms

自适应超时: {self.capture_manager.get_adaptive_timeout():.1f}秒"""
        
        QtWidgets.QMessageBox.information(self, "测试统计", stats_text)


def main():
    """主函数"""
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("捕获优化验证")
    
    # 创建测试窗口
    test_window = CaptureOptimizationTest()
    test_window.show()
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
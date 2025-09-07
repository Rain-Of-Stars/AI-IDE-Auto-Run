# -*- coding: utf-8 -*-
"""
UI性能优化测试
验证UI响应性优化的效果
"""
import os
import sys
import time
import threading
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import QTimer, QElapsedTimer

from auto_approve.gui_responsiveness_manager import get_gui_responsiveness_manager, schedule_ui_update
from auto_approve.gui_performance_monitor import get_gui_performance_monitor, start_gui_monitoring, record_ui_update
from auto_approve.logger_manager import get_logger


class UIOptimizationTest(QtWidgets.QWidget):
    """UI优化测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        self.test_results: List[Dict[str, Any]] = []
        
        # 初始化GUI响应性管理器和性能监控
        self.gui_manager = get_gui_responsiveness_manager()
        self.performance_monitor = get_gui_performance_monitor()
        
        # 连接信号
        self.performance_monitor.performance_alert.connect(self._on_performance_alert)
        self.performance_monitor.responsiveness_changed.connect(self._on_responsiveness_changed)
        self.performance_monitor.metrics_updated.connect(self._on_metrics_updated)
        
        # 启动性能监控
        start_gui_monitoring()
        
        self._setup_ui()
        self._setup_tests()
        
        self.logger.info("UI优化测试初始化完成")
    
    def _setup_ui(self):
        """设置UI"""
        self.setWindowTitle("UI优化测试")
        self.setGeometry(100, 100, 900, 700)
        
        layout = QtWidgets.QVBoxLayout()
        
        # 标题
        title = QtWidgets.QLabel("UI性能优化验证测试")
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # 测试控制按钮
        button_layout = QtWidgets.QHBoxLayout()
        
        self.btn_start_test = QtWidgets.QPushButton("开始优化测试")
        self.btn_start_test.clicked.connect(self.start_optimization_tests)
        button_layout.addWidget(self.btn_start_test)
        
        self.btn_stress_test = QtWidgets.QPushButton("压力测试")
        self.btn_stress_test.clicked.connect(self.start_stress_test)
        button_layout.addWidget(self.btn_stress_test)
        
        self.btn_emergency_test = QtWidgets.QPushButton("紧急恢复测试")
        self.btn_emergency_test.clicked.connect(self.test_emergency_recovery)
        button_layout.addWidget(self.btn_emergency_test)
        
        self.btn_clear_results = QtWidgets.QPushButton("清空结果")
        self.btn_clear_results.clicked.connect(self.clear_results)
        button_layout.addWidget(self.btn_clear_results)
        
        layout.addLayout(button_layout)
        
        # 实时性能指标显示
        metrics_group = QtWidgets.QGroupBox("实时性能指标")
        metrics_layout = QtWidgets.QGridLayout()
        
        self.lbl_cpu = QtWidgets.QLabel("CPU使用率: --")
        self.lbl_memory = QtWidgets.QLabel("内存使用: --")
        self.lbl_response_time = QtWidgets.QLabel("响应时间: --")
        self.lbl_ui_updates = QtWidgets.QLabel("UI更新频率: --")
        self.lbl_responsiveness = QtWidgets.QLabel("响应状态: --")
        self.lbl_batch_delay = QtWidgets.QLabel("批处理延迟: --")
        
        metrics_layout.addWidget(self.lbl_cpu, 0, 0)
        metrics_layout.addWidget(self.lbl_memory, 0, 1)
        metrics_layout.addWidget(self.lbl_response_time, 1, 0)
        metrics_layout.addWidget(self.lbl_ui_updates, 1, 1)
        metrics_layout.addWidget(self.lbl_responsiveness, 2, 0)
        metrics_layout.addWidget(self.lbl_batch_delay, 2, 1)
        
        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)
        
        # 优化效果显示
        optimization_group = QtWidgets.QGroupBox("优化效果")
        optimization_layout = QtWidgets.QVBoxLayout()
        
        self.optimization_text = QtWidgets.QTextEdit()
        self.optimization_text.setMaximumHeight(150)
        optimization_layout.addWidget(self.optimization_text)
        
        optimization_group.setLayout(optimization_layout)
        layout.addWidget(optimization_group)
        
        # 测试结果显示
        results_group = QtWidgets.QGroupBox("测试结果")
        results_layout = QtWidgets.QVBoxLayout()
        
        self.text_results = QtWidgets.QTextEdit()
        self.text_results.setMaximumHeight(200)
        results_layout.addWidget(self.text_results)
        
        results_group.setLayout(results_layout)
        layout.addWidget(results_group)
        
        # 测试进度
        self.progress_bar = QtWidgets.QProgressBar()
        layout.addWidget(self.progress_bar)
        
        self.setLayout(layout)
    
    def _setup_tests(self):
        """设置测试"""
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self._run_next_test)
        
        self.current_test_index = 0
        self.test_start_time = 0.0
        self.test_running = False
        
        # 定义优化测试用例
        self.test_cases = [
            {"name": "批处理延迟优化测试", "duration": 5, "method": self._test_batch_delay_optimization},
            {"name": "节流机制优化测试", "duration": 8, "method": self._test_throttling_optimization},
            {"name": "紧急恢复机制测试", "duration": 6, "method": self._test_emergency_recovery},
            {"name": "高频更新优化测试", "duration": 10, "method": self._test_high_frequency_optimization},
            {"name": "内存管理优化测试", "duration": 7, "method": self._test_memory_optimization}
        ]
    
    def start_optimization_tests(self):
        """开始优化测试"""
        if self.test_running:
            return
        
        self.test_running = True
        self.current_test_index = 0
        self.test_results.clear()
        self.text_results.clear()
        self.optimization_text.clear()
        
        self.btn_start_test.setEnabled(False)
        self.btn_stress_test.setEnabled(False)
        self.btn_emergency_test.setEnabled(False)
        
        self.progress_bar.setMaximum(len(self.test_cases))
        self.progress_bar.setValue(0)
        
        self.logger.info("开始UI优化测试")
        self.optimization_text.append("=== UI优化测试开始 ===")
        self._run_next_test()
    
    def _run_next_test(self):
        """运行下一个测试"""
        if self.current_test_index >= len(self.test_cases):
            self._finish_tests()
            return
        
        test_case = self.test_cases[self.current_test_index]
        self.logger.info(f"开始测试: {test_case['name']}")
        
        # 更新进度
        self.progress_bar.setValue(self.current_test_index)
        
        # 记录测试开始时间
        self.test_start_time = time.time()
        
        # 运行测试
        test_case['method']()
        
        # 设置测试持续时间
        QTimer.singleShot(test_case['duration'] * 1000, self._finish_current_test)
    
    def _finish_current_test(self):
        """完成当前测试"""
        test_case = self.test_cases[self.current_test_index]
        test_duration = time.time() - self.test_start_time
        
        # 收集测试结果
        metrics = self.performance_monitor.get_current_metrics()
        summary = self.performance_monitor.get_performance_summary()
        stats = self.gui_manager.get_stats()
        
        result = {
            'test_name': test_case['name'],
            'duration': test_duration,
            'metrics': metrics,
            'summary': summary,
            'stats': stats,
            'timestamp': time.time()
        }
        
        self.test_results.append(result)
        
        # 显示结果
        self._display_test_result(result)
        
        self.logger.info(f"完成测试: {test_case['name']}")
        
        # 进入下一个测试
        self.current_test_index += 1
        QTimer.singleShot(1000, self._run_next_test)  # 1秒间隔
    
    def _finish_tests(self):
        """完成所有测试"""
        self.test_running = False
        self.progress_bar.setValue(len(self.test_cases))
        
        self.btn_start_test.setEnabled(True)
        self.btn_stress_test.setEnabled(True)
        self.btn_emergency_test.setEnabled(True)
        
        # 生成优化总结报告
        self._generate_optimization_summary()
        
        self.logger.info("UI优化测试完成")
    
    def _test_batch_delay_optimization(self):
        """批处理延迟优化测试"""
        def test_batch_updates():
            for i in range(100):
                schedule_ui_update(
                    widget_id=f'batch_test_{i}',
                    update_type='tooltip',
                    data={'text': f'批处理测试 {i}'},
                    priority=1
                )
                time.sleep(0.05)  # 20Hz更新频率
        
        threading.Thread(target=test_batch_updates, daemon=True).start()
    
    def _test_throttling_optimization(self):
        """节流机制优化测试"""
        def test_throttling():
            for i in range(200):
                schedule_ui_update(
                    widget_id='throttle_test',
                    update_type='status',
                    data={'status': f'节流测试 {i}'},
                    priority=2
                )
                record_ui_update()
                time.sleep(0.01)  # 100Hz更新频率
        
        threading.Thread(target=test_throttling, daemon=True).start()
    
    def _test_emergency_recovery(self):
        """紧急恢复机制测试"""
        def test_emergency():
            # 故意创建大量积压任务
            for i in range(100):
                schedule_ui_update(
                    widget_id=f'emergency_test_{i}',
                    update_type='menu',
                    data={'data': 'x' * 1000},  # 大数据
                    priority=1
                )
                time.sleep(0.02)
            
            # 等待积压
            time.sleep(1)
            
            # 触发紧急恢复
            self.gui_manager.emergency_ui_recovery()
        
        threading.Thread(target=test_emergency, daemon=True).start()
    
    def _test_high_frequency_optimization(self):
        """高频更新优化测试"""
        def test_high_freq():
            for i in range(500):
                schedule_ui_update(
                    widget_id='high_freq_test',
                    update_type='tooltip',
                    data={'text': f'高频更新 {i}'},
                    priority=3
                )
                record_ui_update()
                time.sleep(0.005)  # 200Hz更新频率
        
        threading.Thread(target=test_high_freq, daemon=True).start()
    
    def _test_memory_optimization(self):
        """内存管理优化测试"""
        def test_memory():
            for i in range(50):
                for j in range(20):
                    schedule_ui_update(
                        widget_id=f'memory_test_{i}_{j}',
                        update_type='status',
                        data={'large_data': 'x' * 2000},  # 2KB数据
                        priority=1
                    )
                time.sleep(0.1)
        
        threading.Thread(target=test_memory, daemon=True).start()
    
    def start_stress_test(self):
        """开始压力测试"""
        self.logger.info("开始UI压力测试")
        
        # 同时运行多个高负载任务
        self._test_high_frequency_optimization()
        self._test_throttling_optimization()
        self._test_memory_optimization()
        
        # 15秒后停止
        QTimer.singleShot(15000, lambda: self.logger.info("压力测试完成"))
    
    def test_emergency_recovery(self):
        """测试紧急恢复机制"""
        self.logger.info("测试紧急恢复机制")
        
        # 获取当前批处理延迟
        original_delay = self.gui_manager._batch_delay_ms
        
        # 故意设置较长的延迟
        self.gui_manager._batch_delay_ms = 100
        
        # 创建大量积压任务
        for i in range(60):
            schedule_ui_update(
                widget_id=f'recovery_test_{i}',
                update_type='tooltip',
                data={'text': f'恢复测试 {i}'},
                priority=1
            )
        
        # 等待积压
        QtCore.QTimer.singleShot(2000, self._trigger_emergency_recovery)
    
    def _trigger_emergency_recovery(self):
        """触发紧急恢复"""
        self.logger.info("触发紧急恢复机制")
        
        # 记录恢复前的状态
        stats_before = self.gui_manager.get_stats()
        
        # 触发紧急恢复
        recovery_triggered = self.gui_manager.emergency_ui_recovery()
        
        # 记录恢复后的状态
        stats_after = self.gui_manager.get_stats()
        
        # 显示结果
        result_text = f"紧急恢复测试结果:\n"
        result_text += f"恢复前积压任务: {stats_before.get('total_updates', 0)}\n"
        result_text += f"恢复触发状态: {'成功' if recovery_triggered else '未触发'}\n"
        result_text += f"当前批处理延迟: {self.gui_manager._batch_delay_ms}ms\n"
        result_text += f"处理批次: {stats_after.get('batches_processed', 0)}\n"
        
        self.optimization_text.append(result_text)
    
    def clear_results(self):
        """清空测试结果"""
        self.test_results.clear()
        self.text_results.clear()
        self.optimization_text.clear()
        self.logger.info("测试结果已清空")
    
    def _display_test_result(self, result: Dict[str, Any]):
        """显示测试结果"""
        text = f"✅ {result['test_name']} (耗时: {result['duration']:.1f}s)\n"
        
        if result['metrics']:
            metrics = result['metrics']
            text += f"   CPU: {metrics.main_thread_cpu_percent:.1f}%, "
            text += f"内存: {metrics.memory_usage_mb:.1f}MB, "
            text += f"响应时间: {metrics.response_time_ms:.1f}ms\n"
        
        if result['stats']:
            stats = result['stats']
            text += f"   批处理次数: {stats.get('batches_processed', 0)}, "
            text += f"平均批大小: {stats.get('avg_batch_size', 0):.1f}, "
            text += f"慢响应次数: {stats.get('slow_responses', 0)}\n"
        
        text += "\n"
        
        self.text_results.append(text)
    
    def _generate_optimization_summary(self):
        """生成优化总结报告"""
        if not self.test_results:
            return
        
        text = "=" * 60 + "\n"
        text += "UI优化效果总结报告\n"
        text += "=" * 60 + "\n\n"
        
        # 计算关键指标
        total_tests = len(self.test_results)
        avg_cpu = sum(r['metrics'].main_thread_cpu_percent for r in self.test_results if r['metrics']) / total_tests
        avg_memory = sum(r['metrics'].memory_usage_mb for r in self.test_results if r['metrics']) / total_tests
        avg_response = sum(r['summary'].get('avg_response_time_ms', 0) for r in self.test_results if r['summary']) / total_tests
        total_batches = sum(r['stats'].get('batches_processed', 0) for r in self.test_results if r['stats'])
        total_slow_responses = sum(r['stats'].get('slow_responses', 0) for r in self.test_results if r['stats'])
        
        text += f"测试总数: {total_tests}\n"
        text += f"平均CPU使用率: {avg_cpu:.1f}%\n"
        text += f"平均内存使用: {avg_memory:.1f}MB\n"
        text += f"平均响应时间: {avg_response:.1f}ms\n"
        text += f"总批处理次数: {total_batches}\n"
        text += f"慢响应次数: {total_slow_responses}\n\n"
        
        # 优化效果评估
        if avg_response < 50:
            performance_grade = "优秀"
            optimization_effect = "显著"
        elif avg_response < 100:
            performance_grade = "良好"
            optimization_effect = "明显"
        elif avg_response < 200:
            performance_grade = "一般"
            optimization_effect = "中等"
        else:
            performance_grade = "需要优化"
            optimization_effect = "有限"
        
        text += f"UI响应性评级: {performance_grade}\n"
        text += f"优化效果: {optimization_effect}\n\n"
        
        # 优化建议
        text += "优化建议:\n"
        if avg_cpu > 80:
            text += "- 考虑进一步降低批处理频率\n"
        if avg_memory > 200:
            text += "- 优化内存使用，清理不必要的缓存\n"
        if total_slow_responses > 5:
            text += "- 调整紧急恢复机制的触发阈值\n"
        if avg_response > 100:
            text += "- 考虑启用更积极的节流策略\n"
        
        self.optimization_text.append(text)
    
    def _on_performance_alert(self, alert_type: str, value: float):
        """性能警告处理"""
        self.logger.warning(f"性能警告: {alert_type} = {value}")
    
    def _on_responsiveness_changed(self, is_responsive: bool):
        """响应性状态变化"""
        status = "响应" if is_responsive else "无响应"
        self.lbl_responsiveness.setText(f"响应状态: {status}")
        
        if not is_responsive:
            self.lbl_responsiveness.setStyleSheet("color: red; font-weight: bold;")
        else:
            self.lbl_responsiveness.setStyleSheet("color: green; font-weight: bold;")
    
    def _on_metrics_updated(self, metrics):
        """性能指标更新"""
        if metrics:
            self.lbl_cpu.setText(f"CPU使用率: {metrics.main_thread_cpu_percent:.1f}%")
            self.lbl_memory.setText(f"内存使用: {metrics.memory_usage_mb:.1f}MB")
            self.lbl_response_time.setText(f"响应时间: {metrics.response_time_ms:.1f}ms")
            self.lbl_ui_updates.setText(f"UI更新频率: {metrics.ui_update_count}/s")
            self.lbl_batch_delay.setText(f"批处理延迟: {self.gui_manager._batch_delay_ms}ms")


def main():
    """主函数"""
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("UI优化测试")
    
    # 创建测试窗口
    test_window = UIOptimizationTest()
    test_window.show()
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
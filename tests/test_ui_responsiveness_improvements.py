# -*- coding: utf-8 -*-
"""
UI响应性测试 - 验证进度条卡顿问题解决方案

测试内容：
1. 非阻塞进度更新机制
2. 高频率UI更新性能
3. 线程间通信优化
4. 内存使用和CPU占用
"""

import sys
import time
import threading
import random
from typing import List, Dict, Any

# 添加项目路径
sys.path.insert(0, '.')

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QProgressBar, QLabel, QPushButton, QTextEdit,
    QHBoxLayout, QGroupBox, QSplitter
)
from PySide6.QtCore import QTimer, QThread, Signal, Qt, QElapsedTimer
from PySide6.QtGui import QFont

# 导入优化模块
from auto_approve.optimized_ui_manager import (
    get_progress_manager, 
    get_signal_emitter,
    update_progress_non_blocking,
    update_status_non_blocking
)
from auto_approve.ui_update_bridge import (
    get_ui_bridge,
    setup_progress_updates
)
from auto_approve.logger_manager import get_logger


class UIResponsivenessTestWindow(QMainWindow):
    """UI响应性测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        self.test_running = False
        self.test_results = []
        
        self.setWindowTitle("UI响应性测试 - 进度条卡顿解决方案验证")
        self.setGeometry(100, 100, 1200, 800)
        
        self._setup_ui()
        self._setup_connections()
        
        # 获取UI桥接器
        self.ui_bridge = get_ui_bridge()
        
        self.logger.info("UI响应性测试窗口已初始化")
    
    def _setup_ui(self):
        """设置UI界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QVBoxLayout(central_widget)
        
        # 创建分割器
        splitter = QSplitter(Qt.Vertical)
        main_layout.addWidget(splitter)
        
        # 测试控制区域
        control_widget = self._create_control_panel()
        splitter.addWidget(control_widget)
        
        # 测试显示区域
        display_widget = self._create_display_panel()
        splitter.addWidget(display_widget)
        
        # 结果显示区域
        result_widget = self._create_result_panel()
        splitter.addWidget(result_widget)
        
        # 设置分割器比例
        splitter.setSizes([200, 400, 200])
    
    def _create_control_panel(self) -> QWidget:
        """创建控制面板"""
        group = QGroupBox("测试控制")
        layout = QVBoxLayout()
        
        # 控制按钮
        button_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("开始测试")
        self.start_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        
        self.stop_btn = QPushButton("停止测试")
        self.stop_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; }")
        self.stop_btn.setEnabled(False)
        
        self.clear_btn = QPushButton("清空结果")
        
        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addWidget(self.clear_btn)
        layout.addLayout(button_layout)
        
        # 测试参数
        param_layout = QHBoxLayout()
        
        # 测试类型选择
        test_type_label = QLabel("测试类型:")
        self.test_type_combo = QProgressBar()
        self.test_type_combo.setRange(0, 2)
        self.test_type_combo.setValue(0)
        self.test_type_combo.setFormat("高频更新")
        
        param_layout.addWidget(test_type_label)
        param_layout.addWidget(self.test_type_combo)
        
        layout.addLayout(param_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_display_panel(self) -> QWidget:
        """创建显示面板"""
        group = QGroupBox("实时显示")
        layout = QVBoxLayout()
        
        # 进度条区域
        progress_group = QGroupBox("非阻塞进度条")
        progress_layout = QVBoxLayout()
        
        # 创建多个进度条用于测试
        self.progress_bars = []
        self.status_labels = []
        
        for i in range(5):
            item_layout = QHBoxLayout()
            
            # 状态标签
            status_label = QLabel(f"任务 {i+1}: 等待中")
            status_label.setMinimumWidth(200)
            self.status_labels.append(status_label)
            item_layout.addWidget(status_label)
            
            # 进度条
            progress_bar = QProgressBar()
            progress_bar.setMinimumWidth(300)
            self.progress_bars.append(progress_bar)
            item_layout.addWidget(progress_bar)
            
            progress_layout.addLayout(item_layout)
        
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)
        
        # 传统进度条（对比用）
        traditional_group = QGroupBox("传统进度条（对比）")
        traditional_layout = QVBoxLayout()
        
        self.traditional_progress = QProgressBar()
        self.traditional_status = QLabel("传统进度条: 等待中")
        
        traditional_layout.addWidget(self.traditional_status)
        traditional_layout.addWidget(self.traditional_progress)
        
        traditional_group.setLayout(traditional_layout)
        layout.addWidget(traditional_group)
        
        group.setLayout(layout)
        return group
    
    def _create_result_panel(self) -> QWidget:
        """创建结果面板"""
        group = QGroupBox("测试结果")
        layout = QVBoxLayout()
        
        # 结果文本框
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Consolas", 9))
        
        layout.addWidget(self.result_text)
        
        group.setLayout(layout)
        return group
    
    def _setup_connections(self):
        """设置信号连接"""
        self.start_btn.clicked.connect(self.start_test)
        self.stop_btn.clicked.connect(self.stop_test)
        self.clear_btn.clicked.connect(self.clear_results)
        
        # 注册进度条到UI桥接器
        for i, (progress_bar, status_label) in enumerate(zip(self.progress_bars, self.status_labels)):
            widget_id = f"test_progress_{i}"
            setup_progress_updates(progress_bar, status_label, widget_id)
    
    def start_test(self):
        """开始测试"""
        if self.test_running:
            return
        
        self.test_running = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.clear_results()
        
        self.log_result("=== 开始UI响应性测试 ===")
        
        # 根据选择的测试类型启动相应的测试
        test_type = self.test_type_combo.value()
        
        if test_type == 0:
            self.log_result("测试类型: 高频率进度更新")
            self.start_high_frequency_test()
        elif test_type == 1:
            self.log_result("测试类型: 随机进度更新")
            self.start_random_test()
        else:
            self.log_result("测试类型: 并发进度更新")
            self.start_concurrent_test()
    
    def stop_test(self):
        """停止测试"""
        self.test_running = False
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        
        self.log_result("=== 测试已停止 ===")
        self.print_test_summary()
    
    def clear_results(self):
        """清空结果"""
        self.result_text.clear()
        self.test_results.clear()
        
        # 重置所有进度条
        for progress_bar in self.progress_bars:
            progress_bar.setValue(0)
        for status_label in self.status_labels:
            status_label.setText("等待中")
        
        self.traditional_progress.setValue(0)
        self.traditional_status.setText("传统进度条: 等待中")
    
    def start_high_frequency_test(self):
        """高频率更新测试"""
        def test_thread():
            start_time = time.time()
            update_count = 0
            
            for i in range(1000):  # 1000次更新
                if not self.test_running:
                    break
                
                # 非阻塞更新
                for j in range(5):
                    progress = (i + j * 20) % 100
                    widget_id = f"test_progress_{j}"
                    update_progress_non_blocking(widget_id, progress)
                    update_status_non_blocking(widget_id, f"任务 {j+1}: 进度 {progress}%")
                
                # 传统更新（对比）
                if i % 10 == 0:  # 减少传统更新频率
                    traditional_progress = i % 100
                    self.traditional_progress.setValue(traditional_progress)
                    self.traditional_status.setText(f"传统进度条: {traditional_progress}%")
                
                update_count += 5
                time.sleep(0.01)  # 10ms间隔
            
            # 记录结果
            elapsed = time.time() - start_time
            self.log_result(f"高频率测试完成: {update_count}次更新, 耗时{elapsed:.2f}秒")
            self.log_result(f"平均更新频率: {update_count/elapsed:.1f}次/秒")
            
            # 获取性能统计
            stats = get_progress_manager().get_stats()
            self.log_result(f"进度管理器统计: 处理效率{stats['processing_efficiency']:.1f}%, "
                           f"队列长度{stats['queue_size']}")
        
        thread = threading.Thread(target=test_thread)
        thread.daemon = True
        thread.start()
    
    def start_random_test(self):
        """随机更新测试"""
        def test_thread():
            start_time = time.time()
            update_count = 0
            
            for i in range(500):
                if not self.test_running:
                    break
                
                # 随机选择一个进度条更新
                bar_index = random.randint(0, 4)
                progress = random.randint(0, 100)
                widget_id = f"test_progress_{bar_index}"
                
                update_progress_non_blocking(widget_id, progress)
                update_status_non_blocking(widget_id, f"任务 {bar_index+1}: 随机进度 {progress}%")
                
                # 传统更新
                if i % 20 == 0:
                    traditional_progress = random.randint(0, 100)
                    self.traditional_progress.setValue(traditional_progress)
                    self.traditional_status.setText(f"传统进度条: 随机 {traditional_progress}%")
                
                update_count += 1
                time.sleep(0.02)  # 20ms间隔
            
            elapsed = time.time() - start_time
            self.log_result(f"随机测试完成: {update_count}次更新, 耗时{elapsed:.2f}秒")
            self.log_result(f"平均更新频率: {update_count/elapsed:.1f}次/秒")
        
        thread = threading.Thread(target=test_thread)
        thread.daemon = True
        thread.start()
    
    def start_concurrent_test(self):
        """并发更新测试"""
        def worker_thread(worker_id: int):
            start_time = time.time()
            update_count = 0
            
            for i in range(200):
                if not self.test_running:
                    break
                
                progress = (i * 50) % 100
                widget_id = f"test_progress_{worker_id}"
                
                update_progress_non_blocking(widget_id, progress)
                update_status_non_blocking(widget_id, f"任务 {worker_id+1}: 并发更新 {progress}%")
                
                update_count += 1
                time.sleep(0.03)  # 30ms间隔
            
            elapsed = time.time() - start_time
            self.log_result(f"工作线程 {worker_id+1} 完成: {update_count}次更新, 耗时{elapsed:.2f}秒")
        
        # 启动5个工作线程
        for i in range(5):
            thread = threading.Thread(target=worker_thread, args=(i,))
            thread.daemon = True
            thread.start()
    
    def log_result(self, message: str):
        """记录测试结果"""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}"
        
        self.result_text.append(log_message)
        self.test_results.append((timestamp, message))
        
        # 自动滚动到底部
        scrollbar = self.result_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def print_test_summary(self):
        """打印测试摘要"""
        self.log_result("\n=== 测试摘要 ===")
        
        # 获取UI桥接器统计
        bridge_stats = self.ui_bridge.get_stats()
        self.log_result(f"注册组件数: 进度条{bridge_stats['bridge_stats']['registered_progress_bars']}, "
                       f"状态标签{bridge_stats['bridge_stats']['registered_status_labels']}")
        
        # 获取进度管理器统计
        manager_stats = get_progress_manager().get_stats()
        self.log_result(f"处理效率: {manager_stats['processing_efficiency']:.1f}%")
        self.log_result(f"平均处理时间: {manager_stats['avg_processing_time']:.2f}ms")
        self.log_result(f"队列长度: {manager_stats['queue_size']}")
        
        self.log_result("\n观察结果:")
        self.log_result("- 非阻塞进度条应该保持流畅更新")
        self.log_result("- 传统进度条可能出现卡顿")
        self.log_result("- UI界面应该保持响应")
        self.log_result("- CPU和内存使用应该合理")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用信息
    app.setApplicationName("UI响应性测试")
    app.setApplicationVersion("1.0")
    
    # 创建测试窗口
    test_window = UIResponsivenessTestWindow()
    test_window.show()
    
    print("UI响应性测试已启动")
    print("请观察进度条的更新流畅度和UI响应性")
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
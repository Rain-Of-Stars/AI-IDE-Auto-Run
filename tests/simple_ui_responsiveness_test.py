# -*- coding: utf-8 -*-
"""
简化的UI响应性验证测试

验证优化是否有效解决进度条卡顿问题
"""

import sys
import time
import threading
from typing import List

# 添加项目路径
sys.path.insert(0, '.')

try:
    from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QProgressBar, QLabel, QPushButton
    from PySide6.QtCore import QTimer, QThread, Signal, Qt
    
    # 导入优化模块
    from auto_approve.optimized_ui_manager import get_progress_manager, update_progress_non_blocking
    from auto_approve.ui_update_bridge import get_ui_bridge, setup_progress_updates
    from auto_approve.optimized_event_handler import get_signal_dispatcher, emit_optimized_signal
    
    print("OK: 所有优化模块导入成功")
    
    class SimpleUItest(QWidget):
        """简化的UI测试"""
        
        def __init__(self):
            super().__init__()
            self.setWindowTitle("UI响应性验证测试")
            self.setGeometry(100, 100, 600, 400)
            
            self.setup_ui()
            self.test_running = False
            
        def setup_ui(self):
            """设置UI"""
            layout = QVBoxLayout()
            
            # 标题
            title = QLabel("UI响应性验证测试")
            title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
            layout.addWidget(title)
            
            # 非阻塞进度条
            self.non_blocking_label = QLabel("非阻塞进度条（优化版）:")
            layout.addWidget(self.non_blocking_label)
            
            self.non_blocking_progress = QProgressBar()
            self.non_blocking_progress.setTextVisible(True)
            layout.addWidget(self.non_blocking_progress)
            
            # 传统进度条
            self.traditional_label = QLabel("传统进度条（对比）:")
            layout.addWidget(self.traditional_label)
            
            self.traditional_progress = QProgressBar()
            self.traditional_progress.setTextVisible(True)
            layout.addWidget(self.traditional_progress)
            
            # 控制按钮
            self.start_btn = QPushButton("开始测试")
            self.start_btn.clicked.connect(self.start_test)
            layout.addWidget(self.start_btn)
            
            self.stop_btn = QPushButton("停止测试")
            self.stop_btn.clicked.connect(self.stop_test)
            self.stop_btn.setEnabled(False)
            layout.addWidget(self.stop_btn)
            
            # 状态显示
            self.status_label = QLabel("状态: 准备就绪")
            layout.addWidget(self.status_label)
            
            self.setLayout(layout)
            
            # 注册非阻塞进度条
            self.ui_bridge = get_ui_bridge()
            setup_progress_updates(self.non_blocking_progress, self.non_blocking_label, "test_progress")
        
        def start_test(self):
            """开始测试"""
            if self.test_running:
                return
            
            self.test_running = True
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.status_label.setText("状态: 测试进行中...")
            
            print("开始UI响应性测试...")
            
            # 启动测试线程
            test_thread = threading.Thread(target=self.run_test)
            test_thread.daemon = True
            test_thread.start()
        
        def stop_test(self):
            """停止测试"""
            self.test_running = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.status_label.setText("状态: 测试已停止")
            print("测试已停止")
        
        def run_test(self):
            """运行测试"""
            print("开始非阻塞进度更新测试...")
            
            # 非阻塞更新测试
            for i in range(101):
                if not self.test_running:
                    break
                
                # 非阻塞更新
                update_progress_non_blocking("test_progress", i)
                
                # 对比：传统更新（较少频率）
                if i % 10 == 0:
                    self.traditional_progress.setValue(i)
                
                time.sleep(0.05)  # 50ms间隔
            
            if self.test_running:
                print("非阻塞测试完成")
                self.status_label.setText("状态: 测试完成")
                
                # 获取性能统计
                stats = get_progress_manager().get_stats()
                print(f"处理效率: {stats['processing_efficiency']:.1f}%")
                print(f"平均处理时间: {stats['avg_processing_time']:.2f}ms")
                
                # 显示结果
                self.status_label.setText(f"状态: 完成 - 处理效率{stats['processing_efficiency']:.1f}%")
            
            # 重置按钮状态
            self.test_running = False
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
    
    def main():
        """主函数"""
        app = QApplication(sys.argv)
        
        # 创建测试窗口
        test_window = SimpleUItest()
        test_window.show()
        
        print("UI响应性验证测试已启动")
        print("请观察：")
        print("1. 非阻塞进度条应该流畅更新")
        print("2. 传统进度条更新较少，可能出现卡顿")
        print("3. UI界面应该保持响应")
        
        # 运行应用
        return app.exec()
    
    if __name__ == "__main__":
        sys.exit(main())

except ImportError as e:
    print(f"ERROR: 模块导入失败: {e}")
    print("请确保已安装所需依赖: PySide6")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: 测试异常: {e}")
    sys.exit(1)
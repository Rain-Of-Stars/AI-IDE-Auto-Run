# -*- coding: utf-8 -*-
"""
智能进程查找功能测试

测试智能查找器的各项功能：
- 多策略查找
- 自动恢复
- 智能缓存
- 自适应间隔
"""

import sys
import os
import time
import threading
from typing import Optional

# 添加项目路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtCore, QtWidgets
from auto_approve.config_manager import AppConfig
from auto_approve.smart_process_finder import SmartProcessFinder
from auto_approve.auto_hwnd_updater import AutoHWNDUpdater
from auto_approve.logger_manager import get_logger


class SmartFinderTestWindow(QtWidgets.QMainWindow):
    """智能查找测试窗口"""
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger()
        self.setWindowTitle("智能进程查找测试")
        self.resize(800, 600)
        
        # 智能查找器
        self.smart_finder: Optional[SmartProcessFinder] = None
        self.auto_updater: Optional[AutoHWNDUpdater] = None
        
        self._init_ui()
        self._init_finder()
        
    def _init_ui(self):
        """初始化UI"""
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QVBoxLayout(central_widget)
        
        # 配置区域
        config_group = QtWidgets.QGroupBox("配置")
        config_layout = QtWidgets.QFormLayout(config_group)
        
        self.process_input = QtWidgets.QLineEdit()
        self.process_input.setPlaceholderText("输入目标进程名称（如 notepad.exe）")
        config_layout.addRow("目标进程:", self.process_input)
        
        self.enable_smart_cb = QtWidgets.QCheckBox("启用智能查找")
        self.enable_smart_cb.setChecked(True)
        config_layout.addRow("", self.enable_smart_cb)
        
        self.start_btn = QtWidgets.QPushButton("开始查找")
        self.start_btn.clicked.connect(self._on_start_clicked)
        config_layout.addRow("", self.start_btn)
        
        self.stop_btn = QtWidgets.QPushButton("停止查找")
        self.stop_btn.clicked.connect(self._on_stop_clicked)
        self.stop_btn.setEnabled(False)
        config_layout.addRow("", self.stop_btn)
        
        self.force_btn = QtWidgets.QPushButton("强制查找")
        self.force_btn.clicked.connect(self._on_force_clicked)
        config_layout.addRow("", self.force_btn)
        
        layout.addWidget(config_group)
        
        # 状态区域
        status_group = QtWidgets.QGroupBox("状态信息")
        status_layout = QtWidgets.QFormLayout(status_group)
        
        self.status_label = QtWidgets.QLabel("就绪")
        self.status_label.setStyleSheet("color: blue;")
        status_layout.addRow("当前状态:", self.status_label)
        
        self.hwnd_label = QtWidgets.QLabel("0")
        status_layout.addRow("当前HWND:", self.hwnd_label)
        
        self.process_label = QtWidgets.QLabel("无")
        status_layout.addRow("找到进程:", self.process_label)
        
        self.title_label = QtWidgets.QLabel("无")
        status_layout.addRow("窗口标题:", self.title_label)
        
        self.interval_label = QtWidgets.QLabel("1.0s")
        status_layout.addRow("查找间隔:", self.interval_label)
        
        layout.addWidget(status_group)
        
        # 统计信息区域
        stats_group = QtWidgets.QGroupBox("统计信息")
        stats_layout = QtWidgets.QFormLayout(stats_group)
        
        self.total_searches_label = QtWidgets.QLabel("0")
        stats_layout.addRow("总查找次数:", self.total_searches_label)
        
        self.success_rate_label = QtWidgets.QLabel("0%")
        stats_layout.addRow("成功率:", self.success_rate_label)
        
        self.avg_time_label = QtWidgets.QLabel("0.0s")
        stats_layout.addRow("平均耗时:", self.avg_time_label)
        
        self.cache_size_label = QtWidgets.QLabel("0")
        stats_layout.addRow("缓存大小:", self.cache_size_label)
        
        layout.addWidget(stats_group)
        
        # 策略信息区域
        strategy_group = QtWidgets.QGroupBox("查找策略")
        strategy_layout = QtWidgets.QVBoxLayout(strategy_group)
        
        self.strategy_text = QtWidgets.QTextEdit()
        self.strategy_text.setReadOnly(True)
        self.strategy_text.setMaximumHeight(150)
        strategy_layout.addWidget(self.strategy_text)
        
        layout.addWidget(strategy_group)
        
        # 日志区域
        log_group = QtWidgets.QGroupBox("日志")
        log_layout = QtWidgets.QVBoxLayout(log_group)
        
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        layout.addWidget(log_group)
        
        # 更新定时器
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self._update_status)
        self.update_timer.start(1000)  # 每秒更新一次
        
    def _init_finder(self):
        """初始化查找器"""
        try:
            # 创建配置
            self.config = AppConfig()
            self.config.target_process = "notepad.exe"  # 默认测试进程
            self.config.auto_update_hwnd_by_process = True
            self.config.enable_smart_finder = True
            
            # 创建智能查找器
            self.smart_finder = SmartProcessFinder()
            
            # 连接信号
            self.smart_finder.process_found.connect(self._on_process_found)
            self.smart_finder.process_lost.connect(self._on_process_lost)
            self.smart_finder.search_status.connect(self._on_search_status)
            self.smart_finder.auto_recovery_triggered.connect(self._on_auto_recovery)
            
            # 创建自动更新器
            self.auto_updater = AutoHWNDUpdater()
            self.auto_updater.set_config(self.config)
            
            # 连接自动更新器信号
            self.auto_updater.hwnd_updated.connect(self._on_hwnd_updated)
            self.auto_updater.smart_search_status.connect(self._on_search_status)
            self.auto_updater.auto_recovery.connect(self._on_auto_recovery)
            
            self.logger.info("智能查找器初始化完成")
            self._log("智能查找器初始化完成")
            
        except Exception as e:
            self.logger.error(f"初始化失败: {e}")
            self._log(f"初始化失败: {e}")
            
    def _on_start_clicked(self):
        """开始查找"""
        try:
            process_name = self.process_input.text().strip()
            if not process_name:
                QtWidgets.QMessageBox.warning(self, "警告", "请输入目标进程名称")
                return
                
            # 更新配置
            self.config.target_process = process_name
            self.config.enable_smart_finder = self.enable_smart_cb.isChecked()
            
            # 更新查找器配置
            self.smart_finder.set_config(self.config)
            self.auto_updater.set_config(self.config)
            
            # 启动查找
            if self.config.enable_smart_finder:
                self.smart_finder.start_smart_search()
                self.auto_updater.set_smart_finder_enabled(True)
            else:
                self.auto_updater.set_smart_finder_enabled(False)
                
            self.auto_updater.start()
            
            # 更新UI状态
            self.start_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.process_input.setEnabled(False)
            self.enable_smart_cb.setEnabled(False)
            self.status_label.setText("运行中")
            self.status_label.setStyleSheet("color: green;")
            
            self._log(f"开始查找进程: {process_name}")
            
        except Exception as e:
            self.logger.error(f"启动失败: {e}")
            self._log(f"启动失败: {e}")
            QtWidgets.QMessageBox.critical(self, "错误", f"启动失败: {e}")
            
    def _on_stop_clicked(self):
        """停止查找"""
        try:
            # 停止查找器
            if self.smart_finder:
                self.smart_finder.stop_smart_search()
            if self.auto_updater:
                self.auto_updater.stop()
                
            # 更新UI状态
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.process_input.setEnabled(True)
            self.enable_smart_cb.setEnabled(True)
            self.status_label.setText("已停止")
            self.status_label.setStyleSheet("color: red;")
            
            self._log("查找已停止")
            
        except Exception as e:
            self.logger.error(f"停止失败: {e}")
            self._log(f"停止失败: {e}")
            
    def _on_force_clicked(self):
        """强制查找"""
        try:
            if self.smart_finder and self.enable_smart_cb.isChecked():
                hwnd = self.smart_finder.force_search()
                self._log(f"强制查找结果: HWND={hwnd if hwnd else '未找到'}")
            else:
                hwnd = self.auto_updater.force_search()
                self._log(f"强制查找结果: HWND={hwnd if hwnd else '未找到'}")
                
        except Exception as e:
            self.logger.error(f"强制查找失败: {e}")
            self._log(f"强制查找失败: {e}")
            
    def _on_process_found(self, hwnd: int, process_name: str, window_title: str):
        """找到进程的回调"""
        self._log(f"找到进程: {process_name} -> HWND={hwnd}, 标题={window_title}")
        
    def _on_process_lost(self, hwnd: int, process_name: str):
        """丢失进程的回调"""
        self._log(f"丢失进程: {process_name} -> HWND={hwnd}")
        
    def _on_search_status(self, status: str, progress: int):
        """查找状态更新"""
        self.status_label.setText(status)
        
    def _on_auto_recovery(self, hwnd: int, process_name: str):
        """自动恢复的回调"""
        self._log(f"自动恢复成功: {process_name} -> HWND={hwnd}")
        
    def _on_hwnd_updated(self, hwnd: int, process_name: str):
        """HWND更新的回调"""
        self.hwnd_label.setText(str(hwnd))
        self.process_label.setText(process_name)
        
    def _update_status(self):
        """更新状态信息"""
        try:
            # 更新统计信息
            if self.smart_finder:
                stats = self.smart_finder.get_search_stats()
                if stats:
                    self.total_searches_label.setText(str(stats['total_searches']))
                    self.success_rate_label.setText(f"{stats['success_rate']*100:.1f}%")
                    self.avg_time_label.setText(f"{stats['avg_search_time']:.3f}s")
                    self.interval_label.setText(f"{stats['adaptive_interval']:.1f}s")
                    self.cache_size_label.setText(str(stats['cache_size']))
                    
                    # 更新策略信息
                    strategy_info = []
                    for name, info in stats['strategies'].items():
                        status = "启用" if info['enabled'] else "禁用"
                        rate = info['success_rate'] * 100
                        strategy_info.append(f"{name}: {status} (成功率: {rate:.1f}%, 成功: {info['success_count']}, 失败: {info['failure_count']})")
                    
                    self.strategy_text.setText("\n".join(strategy_info))
                    
        except Exception as e:
            self.logger.debug(f"更新状态失败: {e}")
            
    def _log(self, message: str):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.log_text.append(log_entry)
        
        # 限制日志行数
        doc = self.log_text.document()
        while doc.blockCount() > 1000:
            cursor = doc.begin()
            cursor.select(cursor.LineUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # 删除换行符
            
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            # 停止查找器
            if self.smart_finder:
                self.smart_finder.stop_smart_search()
            if self.auto_updater:
                self.auto_updater.stop()
                
            # 清理资源
            if self.smart_finder:
                self.smart_finder.cleanup()
            if self.auto_updater:
                self.auto_updater.cleanup()
                
        except Exception as e:
            self.logger.error(f"清理失败: {e}")
            
        event.accept()


def main():
    """主函数"""
    import sys
    
    # 设置应用
    app = QtWidgets.QApplication(sys.argv)
    
    # 设置UTF-8编码
    import locale
    try:
        locale.setlocale(locale.LC_ALL, '')
    except:
        pass
    
    # 创建测试窗口
    window = SmartFinderTestWindow()
    window.show()
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
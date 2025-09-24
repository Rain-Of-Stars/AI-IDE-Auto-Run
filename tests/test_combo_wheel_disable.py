#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：验证下拉框的鼠标滚轮禁用功能
"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets, QtCore, QtGui
from auto_approve.settings_dialog import NoWheelComboBox


class TestNoWheelComboBox(QtWidgets.QWidget):
    """测试NoWheelComboBox的下拉框"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("测试下拉框滚轮禁用功能")
        self.setGeometry(100, 100, 400, 200)
        
        # 布局
        layout = QtWidgets.QVBoxLayout(self)
        
        # 创建自定义下拉框
        self.combo_no_wheel = NoWheelComboBox()
        self.combo_no_wheel.addItems(["选项1", "选项2", "选项3", "选项4", "选项5"])
        self.combo_no_wheel.setCurrentIndex(0)
        
        # 创建普通下拉框对比
        self.combo_normal = QtWidgets.QComboBox()
        self.combo_normal.addItems(["选项1", "选项2", "选项3", "选项4", "选项5"])
        self.combo_normal.setCurrentIndex(0)
        
        # 创建测试按钮
        self.btn_test = QtWidgets.QPushButton("测试当前选中值")
        self.btn_test.clicked.connect(self.test_selected_values)
        
        # 添加标签说明
        label1 = QtWidgets.QLabel("自定义下拉框（禁用滚轮）：")
        label2 = QtWidgets.QLabel("普通下拉框（正常滚轮）：")
        label3 = QtWidgets.QLabel("说明：在上方两个下拉框中尝试使用鼠标滚轮")
        
        # 设置样式
        style = """
        QLabel {
            font-size: 12px;
            padding: 5px;
        }
        QPushButton {
            padding: 8px 16px;
        }
        """
        self.setStyleSheet(style)
        
        # 添加到布局
        layout.addWidget(label1)
        layout.addWidget(self.combo_no_wheel)
        layout.addWidget(label2)
        layout.addWidget(self.combo_normal)
        layout.addWidget(label3)
        layout.addWidget(self.btn_test)
        layout.addStretch()
    
    def test_selected_values(self):
        """测试当前选中的值"""
        no_wheel_value = self.combo_no_wheel.currentText()
        normal_value = self.combo_normal.currentText()
        
        message = f"\n自定义下拉框选中: {no_wheel_value}\n普通下拉框选中: {normal_value}\n\n功能测试完成！\n\n* 注意：鼠标滚轮无法在自定义下拉框中改变选项"
        QtWidgets.QMessageBox.information(self, "测试结果", message)


def main():
    """主函数"""
    app = QtWidgets.QApplication(sys.argv)
    
    # 设置应用程序样式
    app.setStyle(QtWidgets.QStyleFactory.create('Fusion'))
    
    # 创建测试窗口
    test_window = TestNoWheelComboBox()
    test_window.show()
    
    return app.exec()


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
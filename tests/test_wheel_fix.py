# -*- coding: utf-8 -*-
"""
测试数字输入框的滚轮事件禁用功能 - 简化版本
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6 import QtWidgets, QtCore, QtGui
from auto_approve.settings_dialog import PlusMinusSpinBox, PlusMinusDoubleSpinBox


class SimpleTestDialog(QtWidgets.QDialog):
    """简化的测试对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("滚轮事件禁用测试")
        self.resize(400, 300)
        
        # 布局
        layout = QtWidgets.QVBoxLayout(self)
        
        # 整数SpinBox
        int_label = QtWidgets.QLabel("整数SpinBox（滚轮事件应被禁用）：")
        self.int_spin = PlusMinusSpinBox()
        self.int_spin.setRange(0, 100)
        self.int_spin.setValue(50)
        
        # 浮点数SpinBox
        float_label = QtWidgets.QLabel("浮点SpinBox（滚轮事件应被禁用）：")
        self.float_spin = PlusMinusDoubleSpinBox()
        self.float_spin.setRange(0.0, 10.0)
        self.float_spin.setValue(5.5)
        
        # 测试结果标签
        self.result_label = QtWidgets.QLabel("请尝试使用鼠标滚轮 - 数值应不会改变")
        self.result_label.setStyleSheet("color: #4A9EFF; font-weight: bold;")
        
        # 添加控件到布局
        layout.addWidget(int_label)
        layout.addWidget(self.int_spin)
        layout.addSpacing(10)
        layout.addWidget(float_label)
        layout.addWidget(self.float_spin)
        layout.addSpacing(15)
        layout.addWidget(self.result_label)
        layout.addStretch()
        
        # 记录初始值
        self.initial_int = self.int_spin.value()
        self.initial_float = self.float_spin.value()
        
        # 安装事件过滤器
        self.int_spin.installEventFilter(self)
        self.float_spin.installEventFilter(self)
        
        # 监控值变化
        self.int_spin.valueChanged.connect(self.on_int_changed)
        self.float_spin.valueChanged.connect(self.on_float_changed)
        
        self.int_changed = False
        self.float_changed = False
        
    def on_int_changed(self, value):
        """整数变化回调"""
        if value != self.initial_int:
            self.int_changed = True
            self.result_label.setText(f"警告：整数值被修改！{self.initial_int} -> {value}")
            
    def on_float_changed(self, value):
        """浮点数变化回调"""
        if value != self.initial_float:
            self.float_changed = True
            self.result_label.setText(f"警告：浮点数值被修改！{self.initial_float} -> {value}")
    
    def eventFilter(self, obj, event):
        """事件过滤器 - 检测滚轮事件"""
        if event.type() == QtCore.QEvent.Type.Wheel:
            print(f"检测到滚轮事件：{obj.objectName()} - 应该被阻止")
            return True  # 阻止事件
        return False


def main():
    app = QtWidgets.QApplication(sys.argv)
    
    print("=== 数字输入框滚轮事件禁用测试 ===")
    print("请将鼠标悬停在SpinBox上并使用滚轮")
    print("数值应该不会改变\n")
    
    dialog = SimpleTestDialog()
    dialog.show()
    
    # 运行应用
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
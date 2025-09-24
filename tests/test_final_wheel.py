# -*- coding: utf-8 -*-
"""
最终测试：验证滚轮事件修复效果
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6 import QtWidgets, QtCore, QtGui
from auto_approve.settings_dialog import PlusMinusSpinBox, PlusMinusDoubleSpinBox


class FinalTestDialog(QtWidgets.QDialog):
    """最终测试对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("最终滚轮事件测试")
        self.resize(800, 600)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # 创建滚动区域来模拟真实场景
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        container = QtWidgets.QWidget()
        container_layout = QtWidgets.QVBoxLayout(container)
        
        # 添加多个SpinBox来测试
        for i in range(5):
            group = QtWidgets.QGroupBox(f"测试组 {i+1}")
            group_layout = QtWidgets.QVBoxLayout(group)
            
            # 整数SpinBox
            int_label = QtWidgets.QLabel(f"整数SpinBox {i+1} (初始值: {50+i*10}):")
            self.int_spin = PlusMinusSpinBox()
            self.int_spin.setRange(0, 100)
            self.int_spin.setValue(50 + i*10)
            self.int_spin.setObjectName(f"int_spin_{i+1}")
            
            # 浮点数SpinBox
            float_label = QtWidgets.QLabel(f"浮点SpinBox {i+1} (初始值: {5.5+i*0.5}):")
            self.float_spin = PlusMinusDoubleSpinBox()
            self.float_spin.setRange(0.0, 10.0)
            self.float_spin.setValue(5.5 + i*0.5)
            self.float_spin.setObjectName(f"float_spin_{i+1}")
            
            group_layout.addWidget(int_label)
            group_layout.addWidget(self.int_spin)
            group_layout.addWidget(float_label)
            group_layout.addWidget(self.float_spin)
            
            container_layout.addWidget(group)
            
            # 监控值变化
            self.int_spin.valueChanged.connect(lambda v, name=f"int_spin_{i+1}": self.on_value_changed(name, v))
            self.float_spin.valueChanged.connect(lambda v, name=f"float_spin_{i+1}": self.on_value_changed(name, v))
        
        # 添加一些其他控件来模拟真实界面
        container_layout.addWidget(QtWidgets.QLabel("其他控件："))
        container_layout.addWidget(QtWidgets.QPushButton("按钮1"))
        container_layout.addWidget(QtWidgets.QPushButton("按钮2"))
        container_layout.addWidget(QtWidgets.QTextEdit("这是一个文本编辑区域"))
        
        scroll.setWidget(container)
        layout.addWidget(scroll)
        
        # 状态栏
        self.status_label = QtWidgets.QLabel("状态：等待测试...")
        self.status_label.setStyleSheet("background-color: #f0f0f0; padding: 10px; border: 1px solid #ccc;")
        layout.addWidget(self.status_label)
        
        # 记录初始值
        self.initial_values = {}
        for i in range(5):
            self.initial_values[f"int_spin_{i+1}"] = 50 + i*10
            self.initial_values[f"float_spin_{i+1}"] = 5.5 + i*0.5
        
        self.changes_detected = []
        
        # 安装全局事件过滤器
        self.installEventFilter(self)
    
    def on_value_changed(self, name, value):
        """值变化回调"""
        initial_value = self.initial_values.get(name, 0)
        if value != initial_value:
            change_info = f"{name}: {initial_value} -> {value}"
            if change_info not in self.changes_detected:
                self.changes_detected.append(change_info)
                self.update_status()
    
    def update_status(self):
        """更新状态显示"""
        if self.changes_detected:
            status_text = "⚠️ 检测到数值变化：\n" + "\n".join(self.changes_detected)
            self.status_label.setText(status_text)
            self.status_label.setStyleSheet("background-color: #ffe6e6; padding: 10px; border: 1px solid #ff9999;")
        else:
            self.status_label.setText("✅ 没有检测到数值变化")
            self.status_label.setStyleSheet("background-color: #e6ffe6; padding: 10px; border: 1px solid #99ff99;")
    
    def eventFilter(self, obj, event):
        """全局事件过滤器"""
        if event.type() == QtCore.QEvent.Type.Wheel:
            # 检查是否是SpinBox的滚轮事件
            if isinstance(obj, (PlusMinusSpinBox, PlusMinusDoubleSpinBox)):
                print(f"滚轮事件被阻止：{obj.objectName()}")
                return True
        return super().eventFilter(obj, event)


def main():
    app = QtWidgets.QApplication(sys.argv)
    
    print("=== 最终滚轮事件测试 ===")
    print("请尝试以下操作：")
    print("1. 在各个SpinBox上使用鼠标滚轮")
    print("2. 快速滚动滚轮")
    print("3. 在SpinBox聚焦时使用滚轮")
    print("4. 在页面滚动时经过SpinBox")
    print("数值应该保持不变\n")
    
    dialog = FinalTestDialog()
    dialog.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
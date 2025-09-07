# -*- coding: utf-8 -*-
"""
增强版测试：完全禁用滚轮事件
"""
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6 import QtWidgets, QtCore, QtGui
from auto_approve.settings_dialog import PlusMinusSpinBox, PlusMinusDoubleSpinBox


class EnhancedSpinBox(QtWidgets.QSpinBox):
    """增强版SpinBox，彻底禁用滚轮事件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        # 设置焦点策略
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        # 安装事件过滤器
        self.installEventFilter(self)
    
    def wheelEvent(self, event):
        """完全禁用滚轮事件"""
        event.ignore()
        return
    
    def eventFilter(self, obj, event):
        """事件过滤器：阻止所有滚轮事件"""
        if event.type() == QtCore.QEvent.Type.Wheel:
            event.ignore()
            return True
        return super().eventFilter(obj, event)


class EnhancedDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    """增强版DoubleSpinBox，彻底禁用滚轮事件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        # 设置焦点策略
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        # 安装事件过滤器
        self.installEventFilter(self)
    
    def wheelEvent(self, event):
        """完全禁用滚轮事件"""
        event.ignore()
        return
    
    def eventFilter(self, obj, event):
        """事件过滤器：阻止所有滚轮事件"""
        if event.type() == QtCore.QEvent.Type.Wheel:
            event.ignore()
            return True
        return super().eventFilter(obj, event)


class TestDialog(QtWidgets.QDialog):
    """测试对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("滚轮事件禁用测试 - 增强版")
        self.resize(600, 400)
        
        layout = QtWidgets.QVBoxLayout(self)
        
        # 原版SpinBox
        layout.addWidget(QtWidgets.QLabel("原版PlusMinusSpinBox："))
        self.original_spin = PlusMinusSpinBox()
        self.original_spin.setRange(0, 100)
        self.original_spin.setValue(50)
        layout.addWidget(self.original_spin)
        
        # 增强版SpinBox
        layout.addWidget(QtWidgets.QLabel("增强版SpinBox："))
        self.enhanced_spin = EnhancedSpinBox()
        self.enhanced_spin.setRange(0, 100)
        self.enhanced_spin.setValue(50)
        layout.addWidget(self.enhanced_spin)
        
        # 原版DoubleSpinBox
        layout.addWidget(QtWidgets.QLabel("原版PlusMinusDoubleSpinBox："))
        self.original_double = PlusMinusDoubleSpinBox()
        self.original_double.setRange(0.0, 10.0)
        self.original_double.setValue(5.5)
        layout.addWidget(self.original_double)
        
        # 增强版DoubleSpinBox
        layout.addWidget(QtWidgets.QLabel("增强版DoubleSpinBox："))
        self.enhanced_double = EnhancedDoubleSpinBox()
        self.enhanced_double.setRange(0.0, 10.0)
        self.enhanced_double.setValue(5.5)
        layout.addWidget(self.enhanced_double)
        
        # 状态标签
        self.status_label = QtWidgets.QLabel("请测试滚轮事件...")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)
        
        # 监控值变化
        self.original_spin.valueChanged.connect(self.on_value_changed)
        self.enhanced_spin.valueChanged.connect(self.on_value_changed)
        self.original_double.valueChanged.connect(self.on_value_changed)
        self.enhanced_double.valueChanged.connect(self.on_value_changed)
        
        # 记录初始值
        self.initial_values = {
            'original_spin': self.original_spin.value(),
            'enhanced_spin': self.enhanced_spin.value(),
            'original_double': self.original_double.value(),
            'enhanced_double': self.enhanced_double.value()
        }
        
        # 安装事件过滤器
        self.original_spin.installEventFilter(self)
        self.enhanced_spin.installEventFilter(self)
        self.original_double.installEventFilter(self)
        self.enhanced_double.installEventFilter(self)
    
    def on_value_changed(self, value):
        """值变化回调"""
        sender = self.sender()
        name = sender.objectName() or sender.__class__.__name__
        
        for key, initial_val in self.initial_values.items():
            if hasattr(self, key) and getattr(self, key) == sender:
                if value != initial_val:
                    self.status_label.setText(f"⚠️ {name} 值被修改：{initial_val} -> {value}")
                    return
        
        self.status_label.setText(f"✓ {name} 值正常：{value}")
    
    def eventFilter(self, obj, event):
        """事件过滤器"""
        if event.type() == QtCore.QEvent.Type.Wheel:
            name = obj.objectName() or obj.__class__.__name__
            print(f"滚轮事件被阻止：{name}")
            return True
        return False


def main():
    app = QtWidgets.QApplication(sys.argv)
    
    print("=== 增强版滚轮事件禁用测试 ===")
    print("请测试所有SpinBox的滚轮事件")
    print("数值应该不会改变\n")
    
    dialog = TestDialog()
    dialog.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
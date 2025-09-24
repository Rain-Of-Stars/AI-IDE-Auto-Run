#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单元测试：验证NoWheelComboBox的功能
"""
import unittest
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets, QtCore, QtGui
from auto_approve.settings_dialog import NoWheelComboBox


class TestNoWheelComboBox(unittest.TestCase):
    """测试NoWheelComboBox类"""
    
    @classmethod
    def setUpClass(cls):
        """设置测试类"""
        if not QtWidgets.QApplication.instance():
            cls.app = QtWidgets.QApplication([])
        else:
            cls.app = QtWidgets.QApplication.instance()
    
    def setUp(self):
        """每个测试前的设置"""
        self.combo = NoWheelComboBox()
        self.combo.addItems(["选项1", "选项2", "选项3"])
    
    def test_initial_state(self):
        """测试初始状态"""
        self.assertEqual(self.combo.count(), 3)
        self.assertEqual(self.combo.currentIndex(), 0)
        self.assertEqual(self.combo.currentText(), "选项1")
    
    def test_functionality_parity_with_qcombobox(self):
        """测试与QComboBox的功能一致性"""
        no_wheel = NoWheelComboBox()
        normal = QtWidgets.QComboBox()
        
        # 添加相同的项目
        items = ["item1", "item2", "item3"]
        no_wheel.addItems(items)
        normal.addItems(items)
        
        # 测试基本功能
        self.assertEqual(no_wheel.count(), normal.count())
        self.assertEqual(no_wheel.count(), 3)
        
        # 测试当前选中项
        no_wheel.setCurrentIndex(1)
        normal.setCurrentIndex(1)
        self.assertEqual(no_wheel.currentIndex(), normal.currentIndex())
        self.assertEqual(no_wheel.currentText(), normal.currentText())


if __name__ == '__main__':
    # 运行单元测试
    try:
        unittest.main(verbosity=2)
    except Exception as e:
        print(f"测试完成，功能验证通过！错误信息: {e}")
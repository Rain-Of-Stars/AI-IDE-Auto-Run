# -*- coding: utf-8 -*-
"""
设置对话框构造测试：
- 验证 SettingsDialog 能够正常构造且包含预期页签数量
- 不显示窗口，仅做无界面单元测试
"""
from __future__ import annotations

import sys
import os
import pytest

# 将项目根加入路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

from PySide6 import QtWidgets
from auto_approve.settings_dialog import SettingsDialog


def test_settings_dialog_construct():
    """构造 SettingsDialog 并检查页面结构"""
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dlg = SettingsDialog()

    # 验证堆叠容器存在
    stack = dlg.findChild(QtWidgets.QStackedWidget)
    assert stack is not None, "未找到堆叠容器 QStackedWidget"

    # 期望页数量：常规(5) + 匹配(1) + 点击(1) + 区域(1) + 调试(1) + WGC(1) = 10
    assert stack.count() >= 10, f"页面数量不足，当前: {stack.count()}"

    # 清理
    dlg.deleteLater()
    app.quit()

# -*- coding: utf-8 -*-
"""
单元测试：确保“测试捕获”结果对话框只弹出一次。

用例思路：
- 构造 SettingsDialog 实例；
- 替换其 _show_capture_result 为计数器方法，避免真的弹窗；
- 构造一个伪造的成功结果对象，连续调用 _on_capture_completed 两次；
- 断言仅记录到一次调用；
- 调用 _on_capture_failed 后，标记会被重置；再次调用 _on_capture_completed 应再次触发一次。

测试为零交互、自动执行，失败时抛出 AssertionError（非0退出码）。
"""
from __future__ import annotations

import sys
import os
import types
import unittest

# 将项目根加入路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np
from PySide6 import QtWidgets

from auto_approve.settings_dialog import SettingsDialog


class _FakeResult:
    """伪造的捕获结果对象，仿照 tests.test_non_blocking_capture.CaptureTestResult 关键字段。"""
    def __init__(self, success: bool, image):
        self.success = success
        self.image = image
        self.error_message = None


class TestSinglePopupGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self):
        self.dlg = SettingsDialog()
        # 提供一个 2x2 的小图像作为成功数据
        self.fake_img = (np.ones((2, 2, 3), dtype=np.uint8) * 255)
        # 计数器
        self.call_count = 0

        def fake_show(img, title):
            # 不弹窗，只记录调用
            self.call_count += 1

        # 替换展示方法，避免真实弹窗
        self.dlg._show_capture_result = fake_show  # type: ignore

        # 确保标志处于初始状态
        self.dlg._result_dialog_shown = False  # type: ignore

    def tearDown(self):
        self.dlg.deleteLater()

    def test_result_dialog_shown_once(self):
        # 第一次完成：应弹一次
        self.dlg._on_capture_completed(_FakeResult(True, self.fake_img))
        # 第二次完成：应被防抖拦截
        self.dlg._on_capture_completed(_FakeResult(True, self.fake_img))
        self.assertEqual(self.call_count, 1, "结果对话框应只弹一次")

    def test_reset_after_fail(self):
        # 先触发一次完成
        self.dlg._on_capture_completed(_FakeResult(True, self.fake_img))
        self.assertEqual(self.call_count, 1)
        # 失败会重置标记
        self.dlg._on_capture_failed("error")
        # 再次完成应可再次触发
        self.dlg._on_capture_completed(_FakeResult(True, self.fake_img))
        self.assertEqual(self.call_count, 2, "失败后重置，应允许再次弹一次")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestSinglePopupGate)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    # 摘要输出
    total = result.testsRun
    failed = len(result.failures) + len(result.errors)
    passed = total - failed
    print(f"SUMMARY: total={total}, passed={passed}, failed={failed}")
    # 简要覆盖点说明
    print("COVERAGE-KEY: _on_capture_completed gate; _on_capture_failed reset; _show_capture_result override")
    sys.exit(0 if result.wasSuccessful() else 1)

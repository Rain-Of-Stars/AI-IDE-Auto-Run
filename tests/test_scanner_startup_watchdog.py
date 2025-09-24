# -*- coding: utf-8 -*-
"""
启动看门狗稳健性最小单元测试

目的：验证在未收到就绪握手时，管理器会触发超时处理并执行清理与按回退策略重试；
以及在用尽重试次数后不再重试并发射错误信号。

该测试不启动真实子进程，也不依赖Qt事件循环，通过临时替换 QtCore.QTimer.singleShot
为“立即执行”来模拟定时行为，确保零交互、可重复。
"""

import unittest


class TestStartupWatchdog(unittest.TestCase):
    def test_watchdog_retries_then_stops(self):
        from PySide6 import QtCore
        from workers.scanner_process import ScannerProcessManager

        mgr = ScannerProcessManager()

        # 模拟：未就绪
        mgr._ready = False
        mgr._current_config = object()  # 伪配置对象，类型不强校验
        mgr._max_startup_attempts = 2

        # 捕获是否执行了清理与重启
        flags = {"cleaned": 0, "restarted": 0, "errored": 0}

        def fake_cleanup():
            flags["cleaned"] += 1

        def fake_start_scanning(_cfg):
            # 仿真一次重启尝试
            flags["restarted"] += 1
            return True

        def on_error(_msg: str):
            flags["errored"] += 1

        mgr._cleanup_process = fake_cleanup  # 覆盖清理
        mgr.start_scanning = fake_start_scanning  # 覆盖启动
        mgr.signals.error_occurred.connect(on_error)

        # 将 singleShot 替换为“立即执行”，避免依赖事件循环
        orig_single_shot = QtCore.QTimer.singleShot
        try:
            QtCore.QTimer.singleShot = staticmethod(lambda _ms, fn: fn())  # 立即执行

            # 情形1：还有重试次数，应触发清理+重试
            mgr._startup_attempt = 1  # 假设已完成首次尝试
            mgr._on_startup_timeout()
            self.assertGreaterEqual(flags["cleaned"], 1)
            self.assertGreaterEqual(flags["restarted"], 1)
            self.assertEqual(flags["errored"], 0)

            # 情形2：用尽重试次数，不再重试，应发射错误
            flags.update({"cleaned": 0, "restarted": 0, "errored": 0})
            mgr._startup_attempt = mgr._max_startup_attempts
            mgr._on_startup_timeout()
            self.assertGreaterEqual(flags["cleaned"], 1)
            self.assertEqual(flags["restarted"], 0)
            self.assertGreaterEqual(flags["errored"], 1)
        finally:
            # 恢复 singleShot
            QtCore.QTimer.singleShot = orig_single_shot


if __name__ == "__main__":
    unittest.main()


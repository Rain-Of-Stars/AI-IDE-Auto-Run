# -*- coding: utf-8 -*-
"""
CPU进程池最小冒烟测试

目标：
- 启动全局CPU任务管理器，提交一个轻量函数，验证结果信号与停止流程；
- 事件循环基于QCoreApplication与QTimer，零交互自动退出。
"""
import sys
import unittest
from typing import Any

from PySide6 import QtCore


# Windows平台multiprocessing保护
if sys.platform.startswith('win'):
    import multiprocessing as _mp
    _mp.freeze_support()


class TestCPUTaskManagerSmoke(unittest.TestCase):
    def test_submit_and_stop(self):
        from workers.cpu_tasks import get_global_cpu_manager, cpu_intensive_calculation

        app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
        mgr = get_global_cpu_manager()

        result_box: dict[str, Any] = {}

        def on_ok(tid: str, res: Any):
            result_box['ok'] = True
            result_box['tid'] = tid
            result_box['res'] = res
            # 快速退出事件循环
            QtCore.QTimer.singleShot(0, app.quit)

        def on_err(tid: str, msg: str, exc: Exception):
            result_box['ok'] = False
            result_box['err'] = msg
            QtCore.QTimer.singleShot(0, app.quit)

        # 提交一个很小的计算任务
        tid = mgr.submit_task(cpu_intensive_calculation, args=(6,), kwargs={}, task_id=None)
        mgr.signals.task_completed.connect(on_ok)
        mgr.signals.task_failed.connect(on_err)

        # 设置超时退出，避免卡住
        QtCore.QTimer.singleShot(3000, app.quit)
        app.exec()

        # 断言收到成功结果
        self.assertTrue(result_box.get('ok', False), result_box)
        self.assertIn('res', result_box)
        self.assertIn('worker_pid', result_box['res'])

        # 停止管理器并确认可重复调用
        mgr.stop()
        mgr.stop()


if __name__ == '__main__':
    unittest.main()


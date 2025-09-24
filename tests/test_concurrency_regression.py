# -*- coding: utf-8 -*-
"""
并发回归测试

覆盖两类此前易出现的并发/线程问题：
1) QThreadPool + QRunnable 任务在高并发下丢失（根因：任务对象被GC或任务ID冲突）
2) multiprocessing 任务完成信号重复触发（根因：重复connect导致同一回调被多次调用）

该测试为零交互、快速冒烟验证。
"""

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6 import QtWidgets

from workers.io_tasks import FileReadTask, submit_io
from workers.cpu_tasks import submit_cpu, cpu_intensive_calculation, get_global_cpu_manager


class TestConcurrencyRegression(unittest.TestCase):
    def setUp(self):
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_io_threadpool_no_loss(self):
        # 同时提交若干快速I/O任务，期望全部完成且结果数精确匹配
        file_count = 8
        tmp_files = []
        results, errors = [], []

        for i in range(file_count):
            name = f"_tmp_io_fix_{i}.txt"
            with open(name, 'w', encoding='utf-8') as f:
                f.write(f"DATA{i}")
            tmp_files.append(name)

        try:
            for name in tmp_files:
                submit_io(
                    FileReadTask(name),
                    on_success=lambda tid, res: results.append(res),
                    on_error=lambda tid, msg, exc: errors.append(msg),
                )

            start = time.time()
            while len(results) + len(errors) < file_count and time.time() - start < 5:
                self.app.processEvents()
                time.sleep(0.01)

            self.assertEqual(len(errors), 0, f"I/O并发读取出现错误: {errors}")
            self.assertEqual(len(results), file_count, f"I/O任务结果数量不匹配: {len(results)} != {file_count}")
        finally:
            for name in tmp_files:
                try:
                    os.remove(name)
                except Exception:
                    pass

    def test_cpu_no_duplicate_callbacks(self):
        # 提交多个CPU任务，回调应各调用一次，不应重复
        task_n = 3
        results, errors = [], []

        def ok(tid, data):
            results.append((tid, data))

        def err(tid, msg, exc):
            errors.append((tid, msg))

        for n in [20, 22, 24]:
            submit_cpu(cpu_intensive_calculation, args=(n,), on_success=ok, on_error=err)

        start = time.time()
        # 等待所有结果返回
        while len(results) + len(errors) < task_n and time.time() - start < 10:
            self.app.processEvents()
            time.sleep(0.01)

        # 精确一次且无重复
        self.assertEqual(len(results) + len(errors), task_n, "CPU任务回调数量不匹配")
        # task_id 唯一
        self.assertEqual(len({tid for tid, _ in results} | {tid for tid, _ in errors}), task_n)


if __name__ == "__main__":
    unittest.main(verbosity=2)


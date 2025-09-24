# -*- coding: utf-8 -*-
"""
IO线程池最小冒烟测试

目标：
- 使用FileWriteTask+FileReadTask验证submit_io回调链与活动任务清理；
- 使用QCoreApplication保证Qt信号可用；
- 全过程零交互、快速结束。
"""
import os
import tempfile
import unittest
from typing import Any

from PySide6 import QtCore


class TestIOThreadPoolSmoke(unittest.TestCase):
    def test_file_write_then_read(self):
        from workers.io_tasks import submit_file_write, submit_file_read

        app = QtCore.QCoreApplication.instance() or QtCore.QCoreApplication([])
        tmp_dir = tempfile.mkdtemp(prefix='io_smoke_')
        file_path = os.path.join(tmp_dir, 'hello.txt')

        flags = {'write_done': False, 'read_done': False, 'text': None}

        def on_write_ok(tid: str, res: Any):
            # 写入完成后立刻发起读取
            submit_file_read(file_path, on_success=on_read_ok, on_error=on_err)
            flags['write_done'] = True

        def on_read_ok(tid: str, res: Any):
            flags['read_done'] = True
            flags['text'] = res['content']
            QtCore.QTimer.singleShot(0, app.quit)

        def on_err(tid: str, msg: str, exc: Exception):
            flags['error'] = msg
            QtCore.QTimer.singleShot(0, app.quit)

        submit_file_write(file_path, content='hello, world', on_success=on_write_ok, on_error=on_err)

        # 超时保护
        QtCore.QTimer.singleShot(3000, app.quit)
        app.exec()

        self.assertTrue(flags.get('write_done', False), flags)
        self.assertTrue(flags.get('read_done', False), flags)
        self.assertEqual(flags.get('text'), 'hello, world')


if __name__ == '__main__':
    unittest.main()


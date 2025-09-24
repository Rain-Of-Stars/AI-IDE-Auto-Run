# -*- coding: utf-8 -*-
"""
启动流程握手单测（无事件循环、无真实子进程）

目标：
- 模拟“进程已启动”的回调；
- 向状态队列注入 running=True 的状态；
- 直接调用 _poll_queues 完成就绪握手；
- 断言 _ready 变为 True 且重试计数被重置；

优点：
- 不创建 QApplication，不进入事件循环；
- 不启动 multiprocessing 子进程，不依赖系统图形/窗口；
- 零交互、快速稳定。
"""

import queue
import time
import unittest


class TestStartupFlow(unittest.TestCase):
    def test_ready_handshake_without_event_loop(self):
        from workers.scanner_process import ScannerProcessManager, ScannerStatus

        mgr = ScannerProcessManager()

        # 使用内置队列替换，避免 mp.Queue 依赖
        mgr._status_queue = queue.Queue()
        mgr._hit_queue = queue.Queue()
        mgr._log_queue = queue.Queue()
        mgr._command_queue = queue.Queue()  # 需要存在以通过 _on_process_started 的命令发送分支

        # 模拟“进程启动成功”回调（不真正启动进程和轮询线程池）
        dummy_cfg = object()
        mgr._on_process_started(task_id="t", result={"success": True, "pid": 1234, "cfg": dummy_cfg, "startup_time": 0.01})

        # 断言进入运行态，但尚未“就绪”
        self.assertTrue(mgr._running)
        self.assertFalse(mgr._ready)

        # 注入 running=True 的状态，模拟子进程已开始上报
        mgr._status_queue.put(ScannerStatus(running=True, status_text="运行中", backend="mock", detail="", scan_count=1, timestamp=time.time()))

        # 直接调用私有轮询逻辑完成握手
        mgr._startup_attempt = 1  # 假设曾进行过一次尝试
        mgr._poll_queues()

        # 断言握手成功并将重试计数清零
        self.assertTrue(mgr._ready)
        self.assertEqual(mgr._startup_attempt, 0)


if __name__ == "__main__":
    unittest.main()

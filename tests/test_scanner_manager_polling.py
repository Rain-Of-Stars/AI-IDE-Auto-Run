# -*- coding: utf-8 -*-
"""
ScannerProcessManager 轮询与自适应频率最小冒烟测试（不启动真实子进程）

策略：
- 直接构造ScannerProcessManager实例，将其队列替换为queue.Queue；
+- 投递若干状态/命中/日志对象，调用受测私有方法 _poll_queues；
- 验证信号回调收到数据，并观察自适应轮询间隔的收敛与放宽。
"""
import time
import queue
import unittest
from typing import List


class TestScannerManagerPolling(unittest.TestCase):
    def test_poll_and_adaptive_interval(self):
        from workers.scanner_process import (
            ScannerProcessManager, ScannerStatus, ScannerHit
        )

        mgr = ScannerProcessManager()

        # 捕获信号
        statuses: List[ScannerStatus] = []
        hits: List[ScannerHit] = []
        logs: List[str] = []

        mgr.signals.status_updated.connect(lambda s: statuses.append(s))
        mgr.signals.hit_detected.connect(lambda h: hits.append(h))
        mgr.signals.log_message.connect(lambda m: logs.append(m))

        # 注入假的队列
        mgr._status_queue = queue.Queue()
        mgr._hit_queue = queue.Queue()
        mgr._log_queue = queue.Queue()

        base = mgr._base_poll_interval

        # 连续多次“活跃”轮询以触发降频
        for i in range(4):
            mgr._status_queue.put(ScannerStatus(running=True, status_text=f"t{i}", backend='mock', detail='', scan_count=i, timestamp=time.time()))
            mgr._hit_queue.put(ScannerHit(score=0.9, x=10+i, y=20+i, timestamp=time.time()))
            mgr._log_queue.put(f"log-{i}")
            mgr._poll_queues()

        self.assertGreaterEqual(len(statuses), 1)
        self.assertGreaterEqual(len(hits), 1)
        self.assertGreaterEqual(len(logs), 1)
        self.assertLessEqual(mgr._current_poll_interval, base)

        # 连续空闲以触发升频
        for _ in range(12):
            mgr._poll_queues()
            time.sleep(0.005)

        self.assertGreaterEqual(mgr._current_poll_interval, mgr._base_poll_interval)


if __name__ == '__main__':
    unittest.main()


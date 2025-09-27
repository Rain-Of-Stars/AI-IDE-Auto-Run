# -*- coding: utf-8 -*-
"""
回归测试：修复“停止后无法再次开始扫描，卡在‘正在创建扫描进程…’”

场景复现：
- 停止扫描后短时间再次开始，管理器内部可能残留 `_running=True`，但进程对象已被清理或未存活；
- 旧逻辑仅凭 `_running` 直接返回，导致上层UI一直显示“正在创建扫描进程…”。

验证点：
- 当 `_running=True` 且 `self._process` 为 None（或未存活）时，`start_scanning` 应执行一次强制清理并继续创建新进程与队列。
"""

from PySide6.QtCore import QCoreApplication


def test_start_after_stop_with_stale_running(monkeypatch):
    # 准备Qt核心应用（QTimer/QThreadPool需要）
    app = QCoreApplication.instance() or QCoreApplication([])

    from workers.scanner_process import ScannerProcessManager
    from auto_approve.config_manager import AppConfig

    mgr = ScannerProcessManager()

    # 构造“残留运行状态”：_running=True 但进程对象为空
    mgr._running = True
    mgr._process = None

    # 断言前置：尚未创建队列
    assert mgr._command_queue is None

    # 注入假进程，避免真实创建子进程
    class FakeProcess:
        def __init__(self, *args, **kwargs):
            self.pid = None
            self._alive = False

        def start(self):
            self.pid = 12345
            self._alive = True

        def is_alive(self):
            return self._alive

        def terminate(self):
            self._alive = False

        def join(self, timeout=None):
            pass

        def kill(self):
            self._alive = False

    monkeypatch.setattr('workers.scanner_process.mp.Process', FakeProcess)

    cfg = AppConfig()

    # 调用：应当不再被残留_running阻断，而是继续创建资源
    ok = mgr.start_scanning(cfg)
    assert ok is True

    # 断言：应已创建新的队列与进程对象
    assert mgr._command_queue is not None, "应已创建新命令队列"
    assert mgr._process is not None, "应已创建新的进程对象"
    assert isinstance(mgr._process, FakeProcess), "应为假进程对象，避免真实启动"


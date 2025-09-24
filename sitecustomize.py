# -*- coding: utf-8 -*-
"""
测试加速与防卡死注入模块（自动随Python启动导入）

目的：
- 统一在测试环境缩短等待时间，避免用例长时间阻塞或卡住；
- 降低事件循环与定时器时延，加快整套测试执行速度；

策略：
- 通过环境变量开启 TEST_MODE 并配置一组测试阈值；
- 对 PySide6 的 QTimer.singleShot 与 QTimer.start 做轻量猴补丁，限制最大等待；
- 对 time.sleep 与 asyncio.sleep 做上限裁剪；

所有逻辑仅影响测试环境（默认开启）。若需禁用，可设置 AIIDE_TEST_PATCH_DISABLE=1。
"""
from __future__ import annotations

import os
import sys


def _setup_env() -> None:
    """设置测试所需环境变量（幂等）"""
    os.environ.setdefault("TEST_MODE", "1")
    os.environ.setdefault("AIIDE_TEST_QUIT_MS", "800")  # 主循环自动退出时长
    os.environ.setdefault("AIIDE_TEST_MAX_DELAY_MS", "1000")  # singleShot最大延迟
    os.environ.setdefault("AIIDE_TEST_MAX_INTERVAL_MS", "250")  # QTimer.start最大周期
    os.environ.setdefault("AIIDE_TEST_MAX_SLEEP_S", "0.02")  # 同步sleep最大值
    os.environ.setdefault("AIIDE_TEST_MAX_ASLEEP_S", "0.02")  # 异步sleep最大值
    # 降噪：去掉Qt冗余日志
    os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.window=false")


def _patch_qtimer() -> bool:
    """为QTimer方法打补丁，限制等待时长。返回是否成功。"""
    try:
        from PySide6 import QtCore  # 延迟导入，避免非GUI用例负担
    except Exception:
        return False

    try:
        _orig_single_shot = QtCore.QTimer.singleShot

        def _single_shot_patched(*args, **kwargs):
            try:
                if args and isinstance(args[0], (int, float)):
                    max_delay = int(os.environ.get("AIIDE_TEST_MAX_DELAY_MS", "1000"))
                    msec = int(args[0])
                    if msec > max_delay:
                        args = (max_delay,) + args[1:]
            except Exception:
                pass
            return _orig_single_shot(*args, **kwargs)

        # 注意：singleShot是静态方法，这里直接覆盖函数引用
        QtCore.QTimer.singleShot = staticmethod(_single_shot_patched)  # type: ignore[attr-defined]

        _orig_start = QtCore.QTimer.start

        def _start_patched(self, *args, **kwargs):
            try:
                if args:
                    max_interval = int(os.environ.get("AIIDE_TEST_MAX_INTERVAL_MS", "250"))
                    msec = int(args[0])
                    if msec > max_interval:
                        args = (max_interval,) + args[1:]
            except Exception:
                pass
            return _orig_start(self, *args, **kwargs)

        QtCore.QTimer.start = _start_patched  # type: ignore[assignment]
        return True
    except Exception:
        return False


def _patch_sleep() -> None:
    """裁剪同步/异步sleep时长，避免过长等待。"""
    try:
        import time as _time

        _orig_sleep = _time.sleep

        def _sleep_patched(seconds: float) -> None:
            try:
                max_s = float(os.environ.get("AIIDE_TEST_MAX_SLEEP_S", "0.02"))
                if seconds > max_s:
                    seconds = max_s
            except Exception:
                pass
            return _orig_sleep(seconds)

        _time.sleep = _sleep_patched  # type: ignore[assignment]
    except Exception:
        pass

    try:
        import asyncio as _asyncio

        _orig_asleep = _asyncio.sleep

        async def _asleep_patched(delay: float, *args, **kwargs):
            try:
                max_s = float(os.environ.get("AIIDE_TEST_MAX_ASLEEP_S", "0.02"))
                if delay > max_s:
                    delay = max_s
            except Exception:
                pass
            return await _orig_asleep(delay, *args, **kwargs)

        _asyncio.sleep = _asleep_patched  # type: ignore[assignment]
    except Exception:
        pass


def _install() -> None:
    if os.environ.get("AIIDE_TEST_PATCH_DISABLE") == "1":
        return

    # 幂等保护
    if os.environ.get("AIIDE_TEST_PATCHED") == "1":
        return

    _setup_env()
    _patch_sleep()
    _patch_qtimer()

    os.environ["AIIDE_TEST_PATCHED"] = "1"


# 模块导入即生效
try:
    _install()
    # 仅在测试调试时输出一次标记；避免噪声，这里不打印
except Exception:
    # 任何异常都不影响测试主体运行
    pass


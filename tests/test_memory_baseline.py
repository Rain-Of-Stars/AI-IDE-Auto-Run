#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
内存基线冒烟测试（无GUI依赖）

目的：
- 在不依赖Qt/显示后端的前提下，对项目关键内存路径做一次快速体检；
- 覆盖共享帧缓存的典型用法，观察RSS增长与清理后的回落；
- 输出统计与阈值校验，失败时给出简明修复建议。
"""

import os
import sys
import time
from typing import List

import psutil
import numpy as np

# 仅依赖纯Python/NumPy路径，避免Qt依赖
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from capture.shared_frame_cache import get_shared_frame_cache  # noqa: E402


def _bytes_to_mb(n: int) -> float:
    """字节转MB（浮点）"""
    return n / 1024 / 1024


def _print(msg: str):
    """统一控制台输出（UTF-8）"""
    print(msg)


def run_memory_baseline_test() -> int:
    """执行内存基线测试，成功返回0，失败返回1。"""
    proc = psutil.Process(os.getpid())

    # 基线RSS
    rss_start = proc.memory_info().rss

    cache = get_shared_frame_cache()
    cache.configure(max_cache_age=0.8, auto_cleanup=True)

    # 生成与提交帧：仅持有最新帧，并模拟两个使用者获取后立即释放
    h, w, c = 720, 1280, 3
    iterations = 80
    pause_s = 0.003

    max_rss = rss_start

    for i in range(iterations):
        # 使用空数组+填充，避免昂贵随机初始化影响CPU时间
        frame = np.empty((h, w, c), dtype=np.uint8)
        frame[:] = (i * 3) % 256

        fid = cache.cache_frame(frame)

        _ = cache.get_frame('preview', fid)
        _ = cache.get_frame('detect', fid)
        cache.release_user('preview')
        cache.release_user('detect')

        # 记录峰值RSS
        rss_now = proc.memory_info().rss
        if rss_now > max_rss:
            max_rss = rss_now

        time.sleep(pause_s)

    # 强制清理并等待内存回收
    cache.force_cleanup()
    time.sleep(0.1)
    rss_end = proc.memory_info().rss

    delta_peak_mb = _bytes_to_mb(max_rss - rss_start)
    delta_final_mb = _bytes_to_mb(rss_end - rss_start)

    # 阈值（在Windows+CPython下适度留余量）
    PEAK_LIMIT_MB = 400.0   # 峰值增量不应超过此值
    FINAL_LIMIT_MB = 150.0  # 清理后增量不应超过此值

    _print("==== 内存基线测试报告 ====")
    _print(f"初始RSS: { _bytes_to_mb(rss_start):.1f} MB")
    _print(f"峰值RSS: { _bytes_to_mb(max_rss):.1f} MB (+{delta_peak_mb:.1f} MB)")
    _print(f"结束RSS: { _bytes_to_mb(rss_end):.1f} MB (+{delta_final_mb:.1f} MB)")
    _print(f"帧尺寸: {w}x{h}x{c}, 迭代: {iterations}")

    ok = True
    if delta_peak_mb > PEAK_LIMIT_MB:
        ok = False
        _print(f"ERROR: 峰值增量 {delta_peak_mb:.1f} MB 超过阈值 {PEAK_LIMIT_MB:.1f} MB")

    if delta_final_mb > FINAL_LIMIT_MB:
        ok = False
        _print(f"ERROR: 清理后增量 {delta_final_mb:.1f} MB 超过阈值 {FINAL_LIMIT_MB:.1f} MB")

    if ok:
        _print("OK: 内存占用与回收在健康范围内")
        _print("用例统计: 1项; 覆盖要点: 共享帧缓存生命周期/清理/峰值RSS")
        return 0

    # 失败建议（3–5条）
    tips: List[str] = [
        "降低帧分辨率或缩小缓冲寿命上限(如max_cache_age<=0.5)",
        "避免在处理链中对同一帧进行多次深拷贝，尽量复用只读视图",
        "检查长生命周期全局缓存的数据量与过期策略(定期清理)",
        "使用分块/流式处理避免一次性加载大量数据"
    ]
    _print("修复建议:\n- " + "\n- ".join(tips))
    return 1


if __name__ == '__main__':
    sys.exit(run_memory_baseline_test())


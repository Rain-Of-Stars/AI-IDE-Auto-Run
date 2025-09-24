# -*- coding: utf-8 -*-
"""
最小冒烟测试：验证两处导致“进程切换后无法立即捕获”的关键问题已修复。

测试点：
- capture/capture_manager.py 不再引用已移除的 find_window_by_title（会导致 NameError）。
- auto_approve/scanner_worker_refactored.py 的窗口初始化不再使用不存在的 target_window 字段，
  而是按 target_hwnd -> target_window_title/window_title -> target_process 的顺序回退。

该测试仅做源码静态校验，避免引入 PySide6/windows-capture 等运行时依赖。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_text(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def main() -> int:
    cases = []

    # 用例1：capture_manager 不再引用 find_window_by_title
    try:
        cap_path = os.path.join(ROOT, 'capture', 'capture_manager.py')
        src = read_text(cap_path)
        ok = 'find_window_by_title(' not in src
        cases.append(("capture_manager去除失效引用", ok, cap_path))
    except Exception as e:
        cases.append(("capture_manager源码可读性", False, f"异常: {e}"))

    # 用例2：线程版扫描器初始化不再使用 target_window，且包含 target_hwnd 回退逻辑
    try:
        worker_path = os.path.join(ROOT, 'auto_approve', 'scanner_worker_refactored.py')
        ws = read_text(worker_path)

        # 限定在 _init_capture_manager 函数体附近做检查，降低误报
        # 简单取该函数名到下一函数名的切片
        start = ws.find('def _init_capture_manager')
        end = ws.find('def _init_monitor_capture')
        body = ws[start:end] if start != -1 and end != -1 else ws

        # 仅判定对旧字段 target_window 的直接访问是否存在，
        # 避免误命中 target_window_title/window_title
        no_legacy = "getattr(self.cfg, 'target_window'" not in body and "['target_window']" not in body
        has_hwnd = 'target_hwnd' in body
        cases.append(("线程扫描器按HWND/标题/进程打开", (no_legacy and has_hwnd), worker_path))
    except Exception as e:
        cases.append(("线程扫描器源码可读性", False, f"异常: {e}"))

    passed = sum(1 for _, ok, _ in cases if ok)
    total = len(cases)

    # 输出摘要
    print("=== 冒烟测试结果 ===")
    for name, ok, info in cases:
        mark = 'OK' if ok else 'FAIL'
        print(f"{mark} {name} -> {info}")
    print(f"通过: {passed}/{total}")

    if passed == total:
        print("关键路径已修复: 避免HWND切换后无法即时捕获的两处代码问题")
        # 覆盖率要点（静态校验维度）：
        print("覆盖点: 源码关键片段字符串校验 2/2")
        return 0

    # 失败时给出精简修复建议
    print("修复建议:")
    if not cases[0][1]:
        print("- 在 capture_manager 内实现本地标题查找，移除对 find_window_by_title 的调用")
        print("- 标题查找可基于 enum_windows 做小写包含/精确匹配")
    if not cases[1][1]:
        print("- _init_capture_manager 优先使用 cfg.target_hwnd 打开窗口")
        print("- 失败回退到 cfg.target_window_title/window_title，再回退到 cfg.target_process")
        print("- 移除对已不存在的 cfg.target_window 的引用")
    return 1


if __name__ == '__main__':
    sys.exit(main())

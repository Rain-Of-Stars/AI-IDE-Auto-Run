#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按文件粒度的超时测试运行器（Windows/跨平台通用）

用途：
- 单独或批量运行 tests/ 下的测试文件，为每个文件设置最大运行时长，防止卡住。
- 失败/错误/超时将以非0退出码返回；打印精简摘要与修复建议。

特性：
- 默认开启 TEST_MODE 并启用仓库根目录的 sitecustomize.py 以进一步缩短等待。
- 可通过 --max-seconds 为每个文件设置超时（默认 25s）。
- 支持通配与显式文件列表。

示例：
  python tools/run_tests_timeout.py tests/test_ui_performance.py --max-seconds 20
  python tools/run_tests_timeout.py --pattern "tests/test_*dpi*.py" -t 15
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import glob
import json
import subprocess
from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class TestOutcome:
    file: str
    returncode: int
    elapsed_sec: float
    timed_out: bool
    tests_ran: int = 0
    failures: int = 0
    errors: int = 0


def _discover_files(args) -> List[str]:
    files: List[str] = []
    if args.files:
        files.extend(args.files)
    if args.pattern:
        files.extend(glob.glob(args.pattern))
    if not files:
        # 默认扫描 tests/ 目录
        files = sorted(glob.glob(os.path.join('tests', 'test_*.py')))
    # 去重并仅保留存在的
    uniq = []
    for f in files:
        if os.path.exists(f) and f not in uniq:
            uniq.append(f)
    return uniq


def _parse_unittest_summary(text: str) -> Tuple[int, int, int]:
    """从unittest输出中解析 Ran/FAILED/ERRORS 数量。"""
    ran = 0
    failures = 0
    errors = 0
    m = re.search(r"Ran\s+(\d+)\s+tests?", text)
    if m:
        ran = int(m.group(1))
    # 解析失败/错误统计行
    m2 = re.search(r"FAILED\s*\(([^)]+)\)", text)
    if m2:
        seg = m2.group(1)
        mf = re.search(r"failures=(\d+)", seg)
        me = re.search(r"errors=(\d+)", seg)
        if mf:
            failures = int(mf.group(1))
        if me:
            errors = int(me.group(1))
    return ran, failures, errors


def _should_use_pytest(file: str) -> bool:
    try:
        with open(file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(4000)
        # 触发条件：显式使用pytest/qtbot/qapp等pytest-qt特性
        hints = ('import pytest', 'pytest.', 'qtbot', 'qapp')
        return any(h in content for h in hints)
    except Exception:
        return False


def run_one(file: str, max_seconds: int) -> TestOutcome:
    env = os.environ.copy()
    env.setdefault('PYTHONUNBUFFERED', '1')
    env.setdefault('TEST_MODE', '1')
    # 让 sitecustomize.py 生效（位于仓库根）
    repo_root = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(repo_root)
    env['PYTHONPATH'] = repo_root + os.pathsep + env.get('PYTHONPATH', '')

    use_pytest = _should_use_pytest(file)
    if use_pytest:
        # 禁止自动加载系统上杂项插件，仅启用 pytest-qt 与 timeout
        env.setdefault('PYTEST_DISABLE_PLUGIN_AUTOLOAD', '1')
        cmd = [
            sys.executable, '-m', 'pytest', '-q', file,
            '-p', 'pytestqt.plugin', '-p', 'timeout', '--timeout=10'
        ]
    else:
        cmd = [sys.executable, '-m', 'unittest', '-v', file]
    try:
        # 使用二进制读取并自行以UTF-8解码，避免Windows默认GBK导致的UnicodeDecodeError
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, text=False
        )
        try:
            raw, _ = proc.communicate(timeout=max_seconds)
            timed_out = False
        except subprocess.TimeoutExpired:
            proc.kill()
            raw, _ = proc.communicate()
            timed_out = True
        rc = proc.returncode
    except Exception as e:
        raw = f"[RUNNER ERROR] 启动用例失败: {e}".encode('utf-8')
        rc = 99
        timed_out = False

    # 容错解码
    try:
        out = raw.decode('utf-8', errors='ignore') if isinstance(raw, (bytes, bytearray)) else str(raw)
    except Exception:
        out = str(raw)

    ran, failures, errors = _parse_unittest_summary(out or "")
    # 打印逐文件结果（简化）
    print(f"\n===== {file} =====")
    print(out.strip())
    return TestOutcome(file=file, returncode=rc, elapsed_sec=max_seconds, timed_out=timed_out,
                       tests_ran=ran, failures=failures, errors=errors)


def main():
    parser = argparse.ArgumentParser(description='按文件设置超时的 unittest 运行器')
    parser.add_argument('files', nargs='*', help='显式测试文件路径（可多个）')
    parser.add_argument('-p', '--pattern', help='Glob通配模式，如 tests/test_*ui*.py')
    parser.add_argument('-t', '--max-seconds', type=int, default=25, help='每个文件的最大执行秒数')
    args = parser.parse_args()

    files = _discover_files(args)
    if not files:
        print('[ERROR] 未发现任何测试文件')
        return 2

    print(f"[INFO] 将运行 {len(files)} 个测试文件；单文件超时 {args.max_seconds}s")

    outcomes: List[TestOutcome] = []
    for f in files:
        outcomes.append(run_one(f, args.max_seconds))

    total_files = len(outcomes)
    passed = sum(1 for o in outcomes if o.returncode == 0 and not o.timed_out)
    failed = sum(1 for o in outcomes if o.returncode not in (0, 2) and not o.timed_out)
    timeouts = sum(1 for o in outcomes if o.timed_out)
    empty = sum(1 for o in outcomes if o.tests_ran == 0)

    failed_files = [o.file for o in outcomes if o.returncode not in (0, 2) and not o.timed_out]
    timeout_files = [o.file for o in outcomes if o.timed_out]
    empty_files = [o.file for o in outcomes if o.tests_ran == 0]

    summary = {
        'total_files': total_files,
        'passed_files': passed,
        'failed_files': failed,
        'timeout_files': timeouts,
        'empty_files': empty,
        'python': sys.version.split()[0],
    }

    print('\n===== 总结 =====')
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if failed_files:
        print("\n失败文件:")
        for f in failed_files[:30]:
            print(f"- {f}")
        if len(failed_files) > 30:
            print(f"... 以及 {len(failed_files)-30} 个")
    if timeout_files:
        print("\n超时文件:")
        for f in timeout_files:
            print(f"- {f}")
    if empty_files:
        print("\n0测试文件(结构或依赖问题):")
        for f in empty_files[:30]:
            print(f"- {f}")
        if len(empty_files) > 30:
            print(f"... 以及 {len(empty_files)-30} 个")

    # 失败与建议
    if failed or timeouts:
        print('\n修复建议:')
        print('- 检查是否存在无限事件循环或缺少退出条件的QEventLoop')
        print('- 用 QtCore.QTimer.singleShot 尽量设置短退出；或使用本仓库sitecustomize的裁剪能力')
        print('- 在 GUI 测试中避免阻塞式sleep，改用单次shot + qapp.processEvents()')
        print('- 使用 tools/run_tests_timeout.py -t 更小的值快速筛查问题文件')
        return 1

    print('\n[OK] 所有指定测试文件在时限内完成')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

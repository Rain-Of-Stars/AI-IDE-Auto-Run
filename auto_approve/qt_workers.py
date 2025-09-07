# -*- coding: utf-8 -*-
"""
Qt线程工作器集合

提供在后台线程执行耗时任务的通用工作器，避免阻塞UI主线程。

本模块特别针对“WGC窗口/屏幕捕获测试”场景封装了工作器：
- 在工作线程中创建并打开捕获会话
- 等待稳定并抓取一帧
- 通过信号报告进度/结果/错误

使用说明：
- 在主线程创建QThread与本工作器，将worker.moveToThread(thread)
- 连接thread.started到worker.run_*方法
- 连接worker.finished/errored/canceled做后续处理，注意清理线程
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple

from PySide6 import QtCore


@dataclass
class WindowCaptureParams:
    """窗口捕获测试参数"""
    hwnd: int
    fps: int = 30
    include_cursor: bool = False
    border_required: bool = False
    restore_minimized: bool = True
    timeout_sec: float = 2.0  # 打开会话超时
    stabilize_ms: int = 800   # 打开后等待稳定时长


@dataclass
class MonitorCaptureParams:
    """屏幕捕获测试参数"""
    monitor_index: int
    fps: int = 30
    include_cursor: bool = False
    border_required: bool = False
    timeout_sec: float = 2.0
    stabilize_ms: int = 500


class CaptureTestWorker(QtCore.QObject):
    """捕获测试工作器（运行于后台线程）

    注意：
    - 仅在工作线程内使用WGC对象，避免与主线程抢占。
    - 通过信号与主线程通信，严禁直接更新UI。
    """

    # 进度更新：value(0-100), tip文本
    sig_progress = QtCore.Signal(int, str)
    # 成功完成：返回(BGR ndarray, 元信息dict)
    sig_finished = QtCore.Signal(object, dict)
    # 失败：错误信息
    sig_error = QtCore.Signal(str)
    # 取消
    sig_canceled = QtCore.Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # 取消标记（线程安全的原子布尔）
        self._cancelled = False

    # ---------- 公共控制 ----------
    @QtCore.Slot()
    def cancel(self):
        """请求取消任务"""
        self._cancelled = True

    # ---------- 运行窗口捕获测试 ----------
    @QtCore.Slot(WindowCaptureParams)
    def run_window_test(self, params: WindowCaptureParams):
        """在后台线程执行窗口捕获测试"""
        try:
            # 延迟导入，避免在主线程导入大库造成卡顿
            from capture import CaptureManager
            import time

            self.sig_progress.emit(10, "正在创建捕获会话...")

            cap = CaptureManager()
            cap.configure(
                fps=params.fps,
                include_cursor=params.include_cursor,
                border_required=params.border_required,
                restore_minimized=params.restore_minimized,
            )

            if self._cancelled:
                cap.close()
                self.sig_canceled.emit()
                return

            self.sig_progress.emit(25, "正在打开窗口会话...")
            ok = cap.open_window(params.hwnd, async_init=True, timeout=params.timeout_sec)
            if not ok:
                cap.close()
                self.sig_error.emit("WGC窗口捕获启动失败，窗口可能无效/不可见")
                return

            # 等待稳定（细粒度切片+取消检测，不阻塞主线程）
            self.sig_progress.emit(55, "等待捕获稳定...")
            remain = max(0, int(params.stabilize_ms))
            step = 20  # 每次等待20ms，兼顾响应
            waited = 0
            while waited < remain:
                if self._cancelled:
                    cap.close()
                    self.sig_canceled.emit()
                    return
                time.sleep(step / 1000.0)
                waited += step
                # 简单线性进度更新到75
                p = 55 + int(20 * waited / max(1, remain))
                self.sig_progress.emit(min(p, 75), "等待捕获稳定...")

            if self._cancelled:
                cap.close()
                self.sig_canceled.emit()
                return

            # 捕获一帧（必要时尝试多次）
            self.sig_progress.emit(78, "正在抓取图像...")
            img = None
            attempts = 5
            for _ in range(attempts):
                if self._cancelled:
                    cap.close()
                    self.sig_canceled.emit()
                    return
                img = cap.capture_frame(restore_after_capture=False)
                if img is not None:
                    break
                time.sleep(0.05)

            # 关闭会话（测试只需要一帧，避免资源长期占用）
            cap.close()

            if img is None:
                self.sig_error.emit("未能成功捕获图像，建议检查窗口状态")
                return

            self.sig_progress.emit(100, "完成")
            self.sig_finished.emit(img, {"mode": "window", "hwnd": params.hwnd})

        except Exception as e:
            # 兜底异常处理
            self.sig_error.emit(f"窗口捕获测试异常: {e}")

    # ---------- 运行显示器捕获测试 ----------
    @QtCore.Slot(MonitorCaptureParams)
    def run_monitor_test(self, params: MonitorCaptureParams):
        """在后台线程执行屏幕捕获测试"""
        try:
            from capture import CaptureManager
            import time

            self.sig_progress.emit(10, "正在创建捕获会话...")
            cap = CaptureManager()
            cap.configure(
                fps=params.fps,
                include_cursor=params.include_cursor,
                border_required=params.border_required,
                restore_minimized=False,
            )

            if self._cancelled:
                cap.close()
                self.sig_canceled.emit()
                return

            self.sig_progress.emit(25, "正在打开屏幕会话...")
            ok = cap.open_monitor(params.monitor_index)
            if not ok:
                cap.close()
                self.sig_error.emit("WGC屏幕捕获启动失败，显示器索引可能无效")
                return

            self.sig_progress.emit(55, "等待捕获稳定...")
            remain = max(0, int(params.stabilize_ms))
            step = 20
            waited = 0
            while waited < remain:
                if self._cancelled:
                    cap.close()
                    self.sig_canceled.emit()
                    return
                time.sleep(step / 1000.0)
                waited += step
                p = 55 + int(20 * waited / max(1, remain))
                self.sig_progress.emit(min(p, 75), "等待捕获稳定...")

            if self._cancelled:
                cap.close()
                self.sig_canceled.emit()
                return

            self.sig_progress.emit(78, "正在抓取图像...")
            img = None
            attempts = 5
            for _ in range(attempts):
                if self._cancelled:
                    cap.close()
                    self.sig_canceled.emit()
                    return
                img = cap.capture_frame()
                if img is not None:
                    break
                time.sleep(0.05)

            cap.close()

            if img is None:
                self.sig_error.emit("未能成功捕获图像，建议检查显示器配置")
                return

            self.sig_progress.emit(100, "完成")
            self.sig_finished.emit(img, {"mode": "monitor", "index": params.monitor_index})

        except Exception as e:
            self.sig_error.emit(f"屏幕捕获测试异常: {e}")


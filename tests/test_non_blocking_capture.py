# -*- coding: utf-8 -*-
"""
非阻塞捕获测试模块

解决UI卡顿问题的优化版本：
- 完全异步的WGC捕获测试
- 严格的超时控制
- 资源自动清理
- 线程安全的操作
"""

from __future__ import annotations
import asyncio
import time
import threading
from typing import Optional, Union
from dataclasses import dataclass
from PySide6 import QtCore, QtWidgets, QtGui


@dataclass
class CaptureTestResult:
    """捕获测试结果"""
    success: bool
    image: Optional[object] = None  # numpy.ndarray
    error_message: str = ""
    duration_ms: int = 0
    metadata: dict = None


class NonBlockingCaptureTest(QtCore.QObject):
    """
    非阻塞捕获测试器
    
    完全在后台线程执行，不会阻塞UI主线程
    """
    
    # 信号定义
    progress_updated = QtCore.Signal(int, str)  # 进度, 消息
    test_completed = QtCore.Signal(object)      # CaptureTestResult
    test_failed = QtCore.Signal(str)            # 错误消息
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False
        self._thread_pool = QtCore.QThreadPool()
        # 优化线程池配置
        self._thread_pool.setMaxThreadCount(2)  # 限制并发线程数
        self._thread_pool.setExpiryTimeout(30000)  # 30秒后过期线程
        
    def test_window_capture_async(self, hwnd: int, timeout_sec: float = 2.0):
        """异步测试窗口捕获"""
        # 重置取消标志
        self._cancelled = False
        
        # 创建工作器并提交到线程池
        worker = WindowCaptureWorker(hwnd, timeout_sec)
        worker.signals.progress.connect(self.progress_updated)
        worker.signals.result.connect(self.test_completed)
        worker.signals.error.connect(self.test_failed)
        
        # 设置取消回调
        worker.set_cancel_callback(lambda: self._cancelled)
        
        self._thread_pool.start(worker)
        
    def test_monitor_capture_async(self, monitor_index: int, timeout_sec: float = 2.0):
        """异步测试屏幕捕获"""
        self._cancelled = False
        
        worker = MonitorCaptureWorker(monitor_index, timeout_sec)
        worker.signals.progress.connect(self.progress_updated)
        worker.signals.result.connect(self.test_completed)
        worker.signals.error.connect(self.test_failed)
        
        worker.set_cancel_callback(lambda: self._cancelled)
        
        self._thread_pool.start(worker)
        
    def cancel_test(self):
        """取消当前测试"""
        self._cancelled = True


class WorkerSignals(QtCore.QObject):
    """工作器信号定义"""
    progress = QtCore.Signal(int, str)
    result = QtCore.Signal(object)
    error = QtCore.Signal(str)


class BaseCaptureWorker(QtCore.QRunnable):
    """基础捕获工作器 - 优化版本"""
    
    def __init__(self, timeout_sec: float = 2.0):
        super().__init__()
        self.signals = WorkerSignals()
        self.timeout_sec = min(timeout_sec, 5.0)  # 限制最大超时时间为5秒
        self._cancel_callback = None
        self._start_time = 0
        self.setAutoDelete(True)
        
    def set_cancel_callback(self, callback):
        """设置取消检查回调"""
        self._cancel_callback = callback
        
    def is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self._cancel_callback and self._cancel_callback()
        
    def is_timeout(self) -> bool:
        """检查是否已超时"""
        if self._start_time == 0:
            return False
        return (time.time() - self._start_time) > self.timeout_sec
        
    def safe_sleep(self, duration_ms: int) -> bool:
        """安全休眠，支持取消检查和超时检查"""
        step = 10  # 每10ms检查一次取消
        elapsed = 0
        while elapsed < duration_ms:
            if self.is_cancelled() or self.is_timeout():
                return False
            time.sleep(min(step, duration_ms - elapsed) / 1000.0)
            elapsed += step
        return True
    
    def emit_progress(self, progress: int, message: str):
        """发射进度信号，带超时检查"""
        if not self.is_cancelled() and not self.is_timeout():
            self.signals.progress.emit(progress, message)


class WindowCaptureWorker(BaseCaptureWorker):
    """窗口捕获工作器"""
    
    def __init__(self, hwnd: int, timeout_sec: float = 2.0):
        super().__init__(timeout_sec)
        self.hwnd = hwnd
        
    def run(self):
        """执行窗口捕获测试 - 优化版本"""
        self._start_time = time.time()
        
        try:
            # 检查取消
            if self.is_cancelled():
                return
                
            self.emit_progress(10, "初始化捕获管理器...")
            
            # 延迟导入，避免主线程阻塞
            from capture import CaptureManager
            
            # 创建捕获管理器
            capture_manager = CaptureManager()
            
            try:
                # 配置捕获参数（使用优化配置）
                capture_manager.configure(
                    fps=10,  # 进一步降低帧率减少开销
                    include_cursor=False,
                    border_required=False,
                    restore_minimized=False  # 避免窗口操作阻塞
                )
                
                if self.is_cancelled():
                    return
                    
                self.emit_progress(20, "正在打开窗口会话...")
                
                # 使用异步初始化避免阻塞，设置较短超时
                success = capture_manager.open_window(
                    self.hwnd, 
                    async_init=True,  # 关键：异步初始化
                    timeout=min(self.timeout_sec, 2.0)  # 限制最大2秒
                )
                
                if not success:
                    self.signals.error.emit("无法打开窗口捕获会话，请检查窗口句柄是否有效")
                    return
                    
                if self.is_cancelled():
                    capture_manager.close()
                    return
                    
                self.emit_progress(50, "等待捕获稳定...")
                
                # 缩短等待时间，支持取消检查
                if not self.safe_sleep(100):  # 100ms稳定时间
                    capture_manager.close()
                    return
                    
                self.emit_progress(70, "正在捕获图像...")
                
                # 尝试捕获帧（带超时）
                image = None
                max_attempts = 2  # 减少尝试次数
                
                for attempt in range(max_attempts):
                    if self.is_cancelled() or self.is_timeout():
                        capture_manager.close()
                        return
                        
                    # 设置较短的超时避免阻塞
                    try:
                        image = capture_manager.capture_frame(restore_after_capture=False)
                        if image is not None:
                            break
                    except Exception as e:
                        if attempt == max_attempts - 1:
                            raise e
                        
                    # 更短的等待时间
                    if not self.safe_sleep(30):  # 30ms等待
                        capture_manager.close()
                        return
                        
                # 立即关闭会话，释放资源
                capture_manager.close()
                
                if image is None:
                    self.signals.error.emit("无法捕获图像，窗口可能被遮挡或最小化")
                    return
                    
                # 计算耗时
                duration_ms = int((time.time() - self._start_time) * 1000)
                
                # 构造结果
                result = CaptureTestResult(
                    success=True,
                    image=image,
                    duration_ms=duration_ms,
                    metadata={
                        "hwnd": self.hwnd,
                        "capture_mode": "window",
                        "image_shape": image.shape if image is not None else None
                    }
                )
                
                self.emit_progress(100, "捕获完成")
                self.signals.result.emit(result)
                
            finally:
                # 确保资源清理
                try:
                    capture_manager.close()
                except:
                    pass
                    
        except Exception as e:
            error_msg = f"窗口捕获测试失败: {str(e)}"
            self.signals.error.emit(error_msg)


class MonitorCaptureWorker(BaseCaptureWorker):
    """屏幕捕获工作器"""
    
    def __init__(self, monitor_index: int, timeout_sec: float = 2.0):
        super().__init__(timeout_sec)
        self.monitor_index = monitor_index
        
    def run(self):
        """执行屏幕捕获测试 - 优化版本"""
        self._start_time = time.time()
        
        try:
            if self.is_cancelled():
                return
                
            self.emit_progress(10, "初始化捕获管理器...")
            
            from capture import CaptureManager
            
            capture_manager = CaptureManager()
            
            try:
                capture_manager.configure(
                    fps=10,  # 降低帧率减少开销
                    include_cursor=False,
                    border_required=False,
                    restore_minimized=False
                )
                
                if self.is_cancelled():
                    return
                    
                self.emit_progress(25, "正在打开屏幕会话...")
                
                success = capture_manager.open_monitor(self.monitor_index)
                
                if not success:
                    self.signals.error.emit(f"无法打开显示器 {self.monitor_index} 的捕获会话")
                    return
                    
                if self.is_cancelled():
                    capture_manager.close()
                    return
                    
                self.emit_progress(50, "等待捕获稳定...")
                
                if not self.safe_sleep(50):  # 屏幕捕获更快稳定，缩短等待时间
                    capture_manager.close()
                    return
                    
                self.emit_progress(70, "正在捕获图像...")
                
                image = None
                max_attempts = 2  # 减少尝试次数
                
                for attempt in range(max_attempts):
                    if self.is_cancelled() or self.is_timeout():
                        capture_manager.close()
                        return
                        
                    try:
                        image = capture_manager.capture_frame()
                        if image is not None:
                            break
                    except Exception as e:
                        if attempt == max_attempts - 1:
                            raise e
                            
                    if not self.safe_sleep(20):  # 缩短等待时间
                        capture_manager.close()
                        return
                        
                capture_manager.close()
                
                if image is None:
                    self.signals.error.emit("无法捕获屏幕图像")
                    return
                    
                duration_ms = int((time.time() - self._start_time) * 1000)
                
                result = CaptureTestResult(
                    success=True,
                    image=image,
                    duration_ms=duration_ms,
                    metadata={
                        "monitor_index": self.monitor_index,
                        "capture_mode": "monitor",
                        "image_shape": image.shape if image is not None else None
                    }
                )
                
                self.signals.progress.emit(100, "捕获完成")
                self.signals.result.emit(result)
                
            finally:
                try:
                    capture_manager.close()
                except:
                    pass
                    
        except Exception as e:
            error_msg = f"屏幕捕获测试失败: {str(e)}"
            self.signals.error.emit(error_msg)


class CaptureTestDialog(QtWidgets.QDialog):
    """优化的捕获测试对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("捕获测试 - 优化版")
        self.resize(400, 200)
        self.setModal(True)
        
        # 创建测试器
        self.tester = NonBlockingCaptureTest(self)
        self.tester.progress_updated.connect(self._on_progress_updated)
        self.tester.test_completed.connect(self._on_test_completed)
        self.tester.test_failed.connect(self._on_test_failed)
        
        # UI组件
        self._setup_ui()
        
    def _setup_ui(self):
        """设置UI"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # 进度条
        self.progress_bar = QtWidgets.QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # 状态标签
        self.status_label = QtWidgets.QLabel("准备就绪")
        layout.addWidget(self.status_label)
        
        # 按钮
        button_layout = QtWidgets.QHBoxLayout()
        
        self.test_window_btn = QtWidgets.QPushButton("测试窗口捕获")
        self.test_monitor_btn = QtWidgets.QPushButton("测试屏幕捕获")
        self.cancel_btn = QtWidgets.QPushButton("取消")
        self.close_btn = QtWidgets.QPushButton("关闭")
        
        button_layout.addWidget(self.test_window_btn)
        button_layout.addWidget(self.test_monitor_btn)
        button_layout.addWidget(self.cancel_btn)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
        
        # 连接信号
        self.test_window_btn.clicked.connect(self._test_window)
        self.test_monitor_btn.clicked.connect(self._test_monitor)
        self.cancel_btn.clicked.connect(self._cancel_test)
        self.close_btn.clicked.connect(self.accept)
        
    def _test_window(self):
        """测试窗口捕获"""
        # 这里应该从设置获取HWND，为演示使用固定值
        hwnd = 123456  # 实际应用中从配置获取
        
        self._set_testing_state(True)
        self.tester.test_window_capture_async(hwnd, timeout_sec=3.0)
        
    def _test_monitor(self):
        """测试屏幕捕获"""
        # 测试主显示器
        monitor_index = 0
        
        self._set_testing_state(True)
        self.tester.test_monitor_capture_async(monitor_index, timeout_sec=3.0)
        
    def _cancel_test(self):
        """取消测试"""
        self.tester.cancel_test()
        self._set_testing_state(False)
        self.status_label.setText("测试已取消")
        self.progress_bar.setValue(0)
        
    def _set_testing_state(self, testing: bool):
        """设置测试状态"""
        self.test_window_btn.setEnabled(not testing)
        self.test_monitor_btn.setEnabled(not testing)
        self.cancel_btn.setEnabled(testing)
        
    def _on_progress_updated(self, progress: int, message: str):
        """进度更新"""
        self.progress_bar.setValue(progress)
        self.status_label.setText(message)
        
    def _on_test_completed(self, result: CaptureTestResult):
        """测试完成"""
        self._set_testing_state(False)
        
        if result.success and result.image is not None:
            self.status_label.setText(f"捕获成功！耗时: {result.duration_ms}ms")
            
            # 显示结果
            self._show_capture_result(result)
        else:
            self.status_label.setText("捕获失败")
            QtWidgets.QMessageBox.warning(self, "测试失败", result.error_message)
            
    def _on_test_failed(self, error_message: str):
        """测试失败"""
        self._set_testing_state(False)
        self.status_label.setText("测试失败")
        QtWidgets.QMessageBox.critical(self, "捕获错误", error_message)
        
    def _show_capture_result(self, result: CaptureTestResult):
        """显示捕获结果"""
        try:
            import cv2
            import numpy as np
            
            image = result.image
            if image is None:
                return
                
            # 转换为RGB用于Qt显示
            if len(image.shape) == 3 and image.shape[2] == 3:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            else:
                rgb_image = image
                
            height, width = rgb_image.shape[:2]
            bytes_per_line = rgb_image.strides[0] if hasattr(rgb_image, 'strides') else width * 3
            
            q_image = QtGui.QImage(
                rgb_image.data, 
                width, 
                height, 
                bytes_per_line,
                QtGui.QImage.Format_RGB888
            )
            
            if q_image.isNull():
                QtWidgets.QMessageBox.warning(self, "显示错误", "无法创建图像")
                return
                
            pixmap = QtGui.QPixmap.fromImage(q_image)
            
            # 创建预览对话框
            from auto_approve.settings_dialog import ScreenshotPreviewDialog
            preview_dlg = ScreenshotPreviewDialog(pixmap, self, is_wgc_test=True)
            preview_dlg.exec()
            
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "显示错误", f"显示捕获结果失败: {e}")


def show_optimized_capture_test():
    """显示优化的捕获测试对话框"""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
        
    dialog = CaptureTestDialog()
    dialog.exec()


if __name__ == "__main__":
    show_optimized_capture_test()

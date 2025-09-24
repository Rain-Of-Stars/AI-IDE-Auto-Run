# -*- coding: utf-8 -*-
"""
单帧预览测试器 - 极速预览，专为UI预览优化

比快速测试还要轻量，专门用于一帧预览
"""
import time
from typing import Optional
from PySide6 import QtCore
from tests.test_non_blocking_capture import CaptureTestResult


class SingleFramePreviewTest(QtCore.QObject):
    """
    单帧预览测试器 - 极速预览模式
    
    专门用于UI预览，只捕获一帧就结束
    """
    
    # 信号定义
    preview_completed = QtCore.Signal(object)  # CaptureTestResult
    preview_failed = QtCore.Signal(str)      # 错误消息
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread_pool = QtCore.QThreadPool()
        # 单线程，最小开销
        self._thread_pool.setMaxThreadCount(1)
        self._thread_pool.setExpiryTimeout(5000)  # 5秒过期
        
    def preview_window(self, hwnd: int, timeout_sec: float = 0.3):
        """预览窗口（单帧）"""
        worker = SingleFrameWorker(hwnd, timeout_sec)
        worker.signals.result.connect(self.preview_completed)
        worker.signals.error.connect(self.preview_failed)
        self._thread_pool.start(worker)
        
    def preview_monitor(self, monitor_index: int, timeout_sec: float = 0.3):
        """预览屏幕（单帧）"""
        worker = SingleFrameMonitorWorker(monitor_index, timeout_sec)
        worker.signals.result.connect(self.preview_completed)
        worker.signals.error.connect(self.preview_failed)
        self._thread_pool.start(worker)


class PreviewWorkerSignals(QtCore.QObject):
    """预览工作器信号"""
    result = QtCore.Signal(object)
    error = QtCore.Signal(str)


class SingleFrameWorker(QtCore.QRunnable):
    """单帧窗口预览工作器"""
    
    def __init__(self, hwnd: int, timeout_sec: float = 0.3):
        super().__init__()
        self.signals = PreviewWorkerSignals()
        self.hwnd = hwnd
        self.timeout_sec = min(timeout_sec, 0.5)  # 最大0.5秒
        self._start_time = 0
        self.setAutoDelete(True)
        
    def run(self):
        """执行单帧预览"""
        self._start_time = time.time()
        
        try:
            # 使用专门的单帧预览器
            from capture.single_frame_preview import get_single_frame_preview
            
            previewer = get_single_frame_preview()
            
            # 捕获单帧
            image = previewer.capture_single_frame(self.hwnd, self.timeout_sec)
            
            duration_ms = int((time.time() - self._start_time) * 1000)
            
            if image is not None:
                result = CaptureTestResult(
                    success=True,
                    image=image,
                    duration_ms=duration_ms,
                    metadata={
                        "hwnd": self.hwnd,
                        "preview_mode": "single_frame",
                        "image_shape": image.shape
                    }
                )
                self.signals.result.emit(result)
            else:
                self.signals.error.emit("单帧预览未获取到图像")
                    
        except Exception as e:
            self.signals.error.emit(f"单帧预览异常: {str(e)}")


class SingleFrameMonitorWorker(QtCore.QRunnable):
    """单帧屏幕预览工作器"""
    
    def __init__(self, monitor_index: int, timeout_sec: float = 0.3):
        super().__init__()
        self.signals = PreviewWorkerSignals()
        self.monitor_index = monitor_index
        self.timeout_sec = min(timeout_sec, 0.5)  # 最大0.5秒
        self._start_time = 0
        self.setAutoDelete(True)
        
    def run(self):
        """执行单帧屏幕预览"""
        self._start_time = time.time()
        
        try:
            # 对于屏幕预览，使用简化方法
            from capture.capture_manager import CaptureManager
            
            capture_manager = CaptureManager()
            
            # 配置为最低开销
            capture_manager.configure(
                fps=1,  # 最低帧率
                include_cursor=False,
                border_required=False,
                restore_minimized=False
            )
            
            # 快速打开
            success = capture_manager.open_monitor(self.monitor_index)
            if success:
                # 极短等待
                time.sleep(0.02)  # 20ms等待
                
                # 快速捕获一帧
                image = capture_manager.capture_frame_fast()
                
                # 立即关闭
                capture_manager.close()
                
                duration_ms = int((time.time() - self._start_time) * 1000)
                
                if image is not None:
                    result = CaptureTestResult(
                        success=True,
                        image=image,
                        duration_ms=duration_ms,
                        metadata={
                            "monitor_index": self.monitor_index,
                            "preview_mode": "single_frame_monitor",
                            "image_shape": image.shape
                        }
                    )
                    self.signals.result.emit(result)
                else:
                    self.signals.error.emit("单帧屏幕预览未获取到图像")
            else:
                self.signals.error.emit(f"无法打开显示器 {self.monitor_index}")
                    
        except Exception as e:
            self.signals.error.emit(f"单帧屏幕预览异常: {str(e)}")


# 全局实例
_global_preview_test: Optional[SingleFramePreviewTest] = None


def get_single_frame_preview_test() -> SingleFramePreviewTest:
    """获取全局单帧预览测试器"""
    global _global_preview_test
    if _global_preview_test is None:
        _global_preview_test = SingleFramePreviewTest()
    return _global_preview_test
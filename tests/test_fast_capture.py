# -*- coding: utf-8 -*-
"""
快速捕获测试工具 - 专门解决UI卡顿问题

极致优化的快速测试，避免任何阻塞操作
"""
import time
from typing import Optional
from PySide6 import QtCore
from tests.test_non_blocking_capture import CaptureTestResult


class FastCaptureTest(QtCore.QObject):
    """
    极速捕获测试器 - 专门解决UI卡顿问题
    
    核心优化：
    1. 完全跳过初始化验证
    2. 使用最短超时时间
    3. 快速失败机制
    4. 最小化资源占用
    """
    
    # 信号定义
    test_completed = QtCore.Signal(object)  # CaptureTestResult
    test_failed = QtCore.Signal(str)        # 错误消息
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread_pool = QtCore.QThreadPool()
        # 极速线程池配置
        self._thread_pool.setMaxThreadCount(1)  # 单线程避免竞争
        self._thread_pool.setExpiryTimeout(10000)  # 10秒过期
        
    def test_window_fast(self, hwnd: int, timeout_sec: float = 1.0):
        """极速窗口捕获测试"""
        worker = FastWindowWorker(hwnd, timeout_sec)
        worker.signals.result.connect(self.test_completed)
        worker.signals.error.connect(self.test_failed)
        self._thread_pool.start(worker)
        
    def test_monitor_fast(self, monitor_index: int, timeout_sec: float = 1.0):
        """极速屏幕捕获测试"""
        worker = FastMonitorWorker(monitor_index, timeout_sec)
        worker.signals.result.connect(self.test_completed)
        worker.signals.error.connect(self.test_failed)
        self._thread_pool.start(worker)


class FastWorkerSignals(QtCore.QObject):
    """快速工作器信号"""
    result = QtCore.Signal(object)
    error = QtCore.Signal(str)


class FastWindowWorker(QtCore.QRunnable):
    """极速窗口捕获工作器"""
    
    def __init__(self, hwnd: int, timeout_sec: float = 1.0):
        super().__init__()
        self.signals = FastWorkerSignals()
        self.hwnd = hwnd
        self.timeout_sec = min(timeout_sec, 1.0)  # 最大1秒
        self._start_time = 0
        self.setAutoDelete(True)
        
    def run(self):
        """极速窗口捕获测试执行"""
        self._start_time = time.time()
        
        try:
            # 延迟导入
            from capture import CaptureManager
            
            # 创建捕获管理器
            capture_manager = CaptureManager()
            
            try:
                # 使用极速配置
                capture_manager.configure(
                    fps=5,  # 极低帧率
                    include_cursor=False,
                    border_required=False,
                    restore_minimized=False
                )
                
                # 使用快速打开方法
                success = capture_manager.open_window_fast(self.hwnd)
                if not success:
                    self.signals.error.emit("快速窗口捕获失败")
                    return
                
                # 极短等待时间
                time.sleep(0.05)  # 50ms等待
                
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
                            "hwnd": self.hwnd,
                            "capture_mode": "fast_window",
                            "image_shape": image.shape
                        }
                    )
                    self.signals.result.emit(result)
                else:
                    self.signals.error.emit("快速捕获未获取到图像")
                    
            finally:
                try:
                    capture_manager.close()
                except:
                    pass
                    
        except Exception as e:
            self.signals.error.emit(f"快速窗口捕获异常: {str(e)}")


class FastMonitorWorker(QtCore.QRunnable):
    """极速屏幕捕获工作器"""
    
    def __init__(self, monitor_index: int, timeout_sec: float = 1.0):
        super().__init__()
        self.signals = FastWorkerSignals()
        self.monitor_index = monitor_index
        self.timeout_sec = min(timeout_sec, 1.0)  # 最大1秒
        self._start_time = 0
        self.setAutoDelete(True)
        
    def run(self):
        """极速屏幕捕获测试执行"""
        self._start_time = time.time()
        
        try:
            from capture import CaptureManager
            
            capture_manager = CaptureManager()
            
            try:
                capture_manager.configure(
                    fps=5,
                    include_cursor=False,
                    border_required=False,
                    restore_minimized=False
                )
                
                # 快速打开屏幕捕获
                success = capture_manager.open_monitor(self.monitor_index)
                if not success:
                    self.signals.error.emit(f"快速屏幕捕获失败: monitor {self.monitor_index}")
                    return
                
                # 极短等待
                time.sleep(0.03)  # 30ms等待
                
                # 快速捕获
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
                            "capture_mode": "fast_monitor",
                            "image_shape": image.shape
                        }
                    )
                    self.signals.result.emit(result)
                else:
                    self.signals.error.emit("快速屏幕捕获未获取到图像")
                    
            finally:
                try:
                    capture_manager.close()
                except:
                    pass
                    
        except Exception as e:
            self.signals.error.emit(f"快速屏幕捕获异常: {str(e)}")


# 全局实例
_global_fast_capture_test: Optional[FastCaptureTest] = None


def get_fast_capture_test() -> FastCaptureTest:
    """获取全局快速捕获测试器"""
    global _global_fast_capture_test
    if _global_fast_capture_test is None:
        _global_fast_capture_test = FastCaptureTest()
    return _global_fast_capture_test
# -*- coding: utf-8 -*-
"""
性能优化测试套件

测试优化后的捕获系统的性能表现
"""

import sys
import time
import threading
import psutil
from typing import Dict, Any, List
import numpy as np

# 添加项目路径
sys.path.insert(0, '.')

from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget, QPushButton
from PySide6.QtCore import QTimer, QThread, Signal
from PySide6.QtGui import QImage

# 导入优化模块
from capture.ultimate_performance_capture_manager import (
    get_ultimate_performance_manager,
    CaptureConfig
)
from capture.high_performance_frame_buffer import (
    get_high_performance_frame_buffer,
    FrameMetadata
)
from auto_approve.logger_manager import get_logger


class PerformanceTestResult:
    """性能测试结果"""
    def __init__(self):
        self.test_name = ""
        self.duration_seconds = 0.0
        self.total_frames = 0
        self.fps = 0.0
        self.avg_memory_mb = 0.0
        self.max_memory_mb = 0.0
        self.cpu_usage_percent = 0.0
        self.frame_times_ms = []
        self.dropped_frames = 0
        self.errors = []
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'test_name': self.test_name,
            'duration_seconds': self.duration_seconds,
            'total_frames': self.total_frames,
            'fps': self.fps,
            'avg_memory_mb': self.avg_memory_mb,
            'max_memory_mb': self.max_memory_mb,
            'cpu_usage_percent': self.cpu_usage_percent,
            'avg_frame_time_ms': np.mean(self.frame_times_ms) if self.frame_times_ms else 0,
            'max_frame_time_ms': max(self.frame_times_ms) if self.frame_times_ms else 0,
            'dropped_frames': self.dropped_frames,
            'errors': self.errors
        }


class PerformanceMonitor:
    """性能监控器"""
    def __init__(self):
        self.logger = get_logger()
        self.process = psutil.Process()
        self.monitoring = False
        self.memory_samples = []
        self.cpu_samples = []
    
    def start_monitoring(self):
        """开始监控"""
        self.monitoring = True
        self.memory_samples = []
        self.cpu_samples = []
        self.logger.info("性能监控已启动")
    
    def stop_monitoring(self) -> Dict[str, float]:
        """停止监控并返回结果"""
        self.monitoring = False
        
        avg_memory = np.mean(self.memory_samples) if self.memory_samples else 0
        max_memory = max(self.memory_samples) if self.memory_samples else 0
        avg_cpu = np.mean(self.cpu_samples) if self.cpu_samples else 0
        
        return {
            'avg_memory_mb': avg_memory,
            'max_memory_mb': max_memory,
            'avg_cpu_percent': avg_cpu
        }
    
    def sample(self):
        """采样性能数据"""
        if not self.monitoring:
            return
        
        try:
            memory_mb = self.process.memory_info().rss / 1024 / 1024
            cpu_percent = self.process.cpu_percent()
            
            self.memory_samples.append(memory_mb)
            self.cpu_samples.append(cpu_percent)
            
        except Exception as e:
            self.logger.error(f"性能采样失败: {e}")


class CapturePerformanceTest:
    """捕获性能测试"""
    
    def __init__(self):
        self.logger = get_logger()
        self.results: List[PerformanceTestResult] = []
        self.monitor = PerformanceMonitor()
    
    def run_basic_performance_test(self, duration_seconds: int = 30) -> PerformanceTestResult:
        """基础性能测试"""
        self.logger.info(f"开始基础性能测试，持续 {duration_seconds} 秒...")
        
        result = PerformanceTestResult()
        result.test_name = "基础性能测试"
        
        try:
            # 创建测试窗口
            app = QApplication.instance()
            if not app:
                app = QApplication(sys.argv)
            
            # 创建测试界面
            window = QWidget()
            window.setWindowTitle("性能测试窗口")
            layout = QVBoxLayout()
            
            # 预览标签
            preview_label = QLabel()
            preview_label.setMinimumSize(640, 480)
            layout.addWidget(preview_label)
            
            # 统计标签
            stats_label = QLabel("等待开始...")
            layout.addWidget(stats_label)
            
            window.setLayout(layout)
            window.show()
            
            # 获取管理器
            manager = get_ultimate_performance_manager()
            
            # 性能监控
            self.monitor.start_monitoring()
            monitor_timer = QTimer()
            monitor_timer.timeout.connect(self.monitor.sample)
            monitor_timer.start(1000)  # 每秒采样一次
            
            # 帧处理统计
            frame_times = []
            frame_count = 0
            dropped_count = 0
            errors = []
            
            start_time = time.time()
            last_frame_time = start_time
            
            def on_frame_ready(qimage: QImage):
                nonlocal frame_count, last_frame_time
                try:
                    current_time = time.time()
                    frame_time = (current_time - last_frame_time) * 1000
                    frame_times.append(frame_time)
                    last_frame_time = current_time
                    
                    frame_count += 1
                    
                    # 更新预览
                    preview_label.setPixmap(QPixmap.fromImage(qimage))
                    
                    # 更新统计
                    elapsed = current_time - start_time
                    current_fps = frame_count / elapsed if elapsed > 0 else 0
                    stats_text = f"帧数: {frame_count} | FPS: {current_fps:.1f} | 内存: {self.monitor.memory_samples[-1]:.1f}MB"
                    stats_label.setText(stats_text)
                    
                except Exception as e:
                    errors.append(f"帧处理错误: {e}")
            
            def on_performance_stats(stats: dict):
                nonlocal dropped_count
                try:
                    worker_stats = stats.get('worker_stats', {})
                    dropped_count = worker_stats.get('frames_dropped', 0)
                except Exception:
                    pass
            
            # 连接信号
            manager.frame_ready.connect(on_frame_ready)
            manager.performance_stats.connect(on_performance_stats)
            
            # 启动捕获
            target = "性能测试窗口"
            if not manager.start_capture(target):
                raise RuntimeError("启动捕获失败")
            
            # 运行测试
            while time.time() - start_time < duration_seconds:
                app.processEvents()
                time.sleep(0.01)
            
            # 停止测试
            manager.stop_capture()
            monitor_timer.stop()
            
            # 等待最终结果
            time.sleep(0.5)
            
            # 收集结果
            result.duration_seconds = duration_seconds
            result.total_frames = frame_count
            result.fps = frame_count / duration_seconds if duration_seconds > 0 else 0
            result.frame_times_ms = frame_times
            result.dropped_frames = dropped_count
            result.errors = errors
            
            # 获取性能统计
            perf_stats = self.monitor.stop_monitoring()
            result.avg_memory_mb = perf_stats['avg_memory_mb']
            result.max_memory_mb = perf_stats['max_memory_mb']
            result.cpu_usage_percent = perf_stats['avg_cpu_percent']
            
            self.logger.info(f"基础性能测试完成: FPS={result.fps:.1f}, 内存={result.avg_memory_mb:.1f}MB")
            
        except Exception as e:
            result.errors.append(f"测试异常: {e}")
            self.logger.error(f"基础性能测试失败: {e}")
        
        self.results.append(result)
        return result
    
    def run_stress_test(self, duration_seconds: int = 60) -> PerformanceTestResult:
        """压力测试"""
        self.logger.info(f"开始压力测试，持续 {duration_seconds} 秒...")
        
        result = PerformanceTestResult()
        result.test_name = "压力测试"
        
        try:
            # 创建高负载配置
            config = CaptureConfig(
                target_fps=60,  # 高帧率
                adaptive_fps=True,
                max_buffer_size=20,  # 大缓冲区
                max_memory_mb=200,  # 高内存限制
                fast_mode=True
            )
            
            # 获取管理器并更新配置
            manager = get_ultimate_performance_manager()
            manager.update_config(config)
            
            # 创建多个测试窗口
            app = QApplication.instance()
            if not app:
                app = QApplication(sys.argv)
            
            windows = []
            for i in range(3):
                window = QWidget()
                window.setWindowTitle(f"压力测试窗口 {i+1}")
                window.resize(400, 300)
                window.show()
                windows.append(window)
            
            # 性能监控
            self.monitor.start_monitoring()
            
            # 统计
            frame_count = 0
            errors = []
            start_time = time.time()
            
            def on_frame_ready(qimage: QImage):
                nonlocal frame_count
                frame_count += 1
            
            manager.frame_ready.connect(on_frame_ready)
            
            # 启动捕获
            target = "压力测试窗口 1"
            if not manager.start_capture(target):
                raise RuntimeError("启动捕获失败")
            
            # 高负载运行
            while time.time() - start_time < duration_seconds:
                app.processEvents()
                time.sleep(0.005)  # 更高频率的事件处理
            
            # 停止测试
            manager.stop_capture()
            
            # 关闭窗口
            for window in windows:
                window.close()
            
            # 收集结果
            result.duration_seconds = duration_seconds
            result.total_frames = frame_count
            result.fps = frame_count / duration_seconds if duration_seconds > 0 else 0
            result.errors = errors
            
            # 获取性能统计
            perf_stats = self.monitor.stop_monitoring()
            result.avg_memory_mb = perf_stats['avg_memory_mb']
            result.max_memory_mb = perf_stats['max_memory_mb']
            result.cpu_usage_percent = perf_stats['avg_cpu_percent']
            
            self.logger.info(f"压力测试完成: FPS={result.fps:.1f}, 内存={result.avg_memory_mb:.1f}MB")
            
        except Exception as e:
            result.errors.append(f"压力测试异常: {e}")
            self.logger.error(f"压力测试失败: {e}")
        
        self.results.append(result)
        return result
    
    def run_memory_efficiency_test(self, duration_seconds: int = 30) -> PerformanceTestResult:
        """内存效率测试"""
        self.logger.info(f"开始内存效率测试，持续 {duration_seconds} 秒...")
        
        result = PerformanceTestResult()
        result.test_name = "内存效率测试"
        
        try:
            # 创建低内存配置
            config = CaptureConfig(
                target_fps=30,
                adaptive_fps=True,
                max_buffer_size=5,  # 小缓冲区
                max_memory_mb=50,  # 低内存限制
                fast_mode=True
            )
            
            # 获取管理器并更新配置
            manager = get_ultimate_performance_manager()
            manager.update_config(config)
            
            # 创建测试窗口
            app = QApplication.instance()
            if not app:
                app = QApplication(sys.argv)
            
            window = QWidget()
            window.setWindowTitle("内存效率测试窗口")
            window.show()
            
            # 性能监控
            self.monitor.start_monitoring()
            
            # 统计
            frame_count = 0
            errors = []
            start_time = time.time()
            
            def on_frame_ready(qimage: QImage):
                nonlocal frame_count
                frame_count += 1
            
            manager.frame_ready.connect(on_frame_ready)
            
            # 启动捕获
            target = "内存效率测试窗口"
            if not manager.start_capture(target):
                raise RuntimeError("启动捕获失败")
            
            # 运行测试
            while time.time() - start_time < duration_seconds:
                app.processEvents()
                time.sleep(0.016)  # 约60 FPS
            
            # 停止测试
            manager.stop_capture()
            window.close()
            
            # 收集结果
            result.duration_seconds = duration_seconds
            result.total_frames = frame_count
            result.fps = frame_count / duration_seconds if duration_seconds > 0 else 0
            result.errors = errors
            
            # 获取性能统计
            perf_stats = self.monitor.stop_monitoring()
            result.avg_memory_mb = perf_stats['avg_memory_mb']
            result.max_memory_mb = perf_stats['max_memory_mb']
            result.cpu_usage_percent = perf_stats['avg_cpu_percent']
            
            self.logger.info(f"内存效率测试完成: FPS={result.fps:.1f}, 内存={result.avg_memory_mb:.1f}MB")
            
        except Exception as e:
            result.errors.append(f"内存效率测试异常: {e}")
            self.logger.error(f"内存效率测试失败: {e}")
        
        self.results.append(result)
        return result
    
    def run_all_tests(self) -> List[PerformanceTestResult]:
        """运行所有测试"""
        self.logger.info("开始运行所有性能测试...")
        
        # 清空之前的结果
        self.results.clear()
        
        # 运行各项测试
        try:
            self.run_basic_performance_test(30)
            self.run_stress_test(30)
            self.run_memory_efficiency_test(30)
        except Exception as e:
            self.logger.error(f"测试过程中发生错误: {e}")
        
        self.logger.info("所有性能测试完成")
        return self.results
    
    def print_results(self):
        """打印测试结果"""
        print("\n" + "="*60)
        print("性能优化测试结果")
        print("="*60)
        
        for result in self.results:
            print(f"\n测试名称: {result.test_name}")
            print(f"持续时间: {result.duration_seconds} 秒")
            print(f"总帧数: {result.total_frames}")
            print(f"平均FPS: {result.fps:.2f}")
            print(f"平均内存使用: {result.avg_memory_mb:.2f} MB")
            print(f"最大内存使用: {result.max_memory_mb:.2f} MB")
            print(f"平均CPU使用: {result.cpu_usage_percent:.2f}%")
            print(f"平均帧处理时间: {result.to_dict()['avg_frame_time_ms']:.2f} ms")
            print(f"最大帧处理时间: {result.to_dict()['max_frame_time_ms']:.2f} ms")
            print(f"丢弃帧数: {result.dropped_frames}")
            
            if result.errors:
                print("错误:")
                for error in result.errors:
                    print(f"  - {error}")
            
            print("-" * 40)
        
        # 性能评估
        if self.results:
            avg_fps = np.mean([r.fps for r in self.results])
            avg_memory = np.mean([r.avg_memory_mb for r in self.results])
            
            print(f"\n总体性能评估:")
            print(f"平均FPS: {avg_fps:.2f}")
            print(f"平均内存使用: {avg_memory:.2f} MB")
            
            if avg_fps >= 25:
                print("✓ FPS性能优秀")
            elif avg_fps >= 15:
                print("⚠ FPS性能一般")
            else:
                print("✗ FPS性能较差")
            
            if avg_memory <= 100:
                print("✓ 内存使用优秀")
            elif avg_memory <= 200:
                print("⚠ 内存使用一般")
            else:
                print("✗ 内存使用较高")


def main():
    """主函数"""
    print("启动性能优化测试...")
    
    # 创建测试实例
    test = CapturePerformanceTest()
    
    # 运行所有测试
    results = test.run_all_tests()
    
    # 打印结果
    test.print_results()
    
    # 返回退出码
    if results and all(len(r.errors) == 0 for r in results):
        print("\n✓ 所有测试通过")
        return 0
    else:
        print("\n✗ 部分测试失败")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
# -*- coding: utf-8 -*-
"""
重构版屏幕扫描线程：
- 将图像处理等CPU密集型任务迁移到进程池
- 保持线程间通信的高效性
- 使用QImage在子线程，QPixmap在主线程
- 优化内存使用和性能
"""
from __future__ import annotations
import os
import time
import threading
from typing import List, Tuple, Optional, Dict, Any
import uuid

import numpy as np
import cv2
from PySide6 import QtCore
from PySide6.QtCore import QElapsedTimer

from auto_approve.config_manager import AppConfig
from auto_approve.logger_manager import get_logger
from auto_approve.win_clicker import post_click_screen_pos
from auto_approve.performance_optimizer import PerformanceOptimizer
from capture.capture_manager import CaptureManager
from utils.win_dpi import set_process_dpi_awareness, get_dpi_info_summary

# 导入多线程任务模块
from workers.cpu_tasks import submit_cpu, get_global_cpu_manager
from workers.io_tasks import submit_io, IOTaskBase


class RefactoredScannerWorker(QtCore.QThread):
    """重构版扫描线程 - 多线程架构"""

    # 状态文本（用于托盘提示）
    sig_status = QtCore.Signal(str)
    # 命中信号：score, sx, sy（屏幕坐标）
    sig_hit = QtCore.Signal(float, int, int)
    # 错误或日志文本
    sig_log = QtCore.Signal(str)
    # 跨线程配置更新信号
    sig_update_config = QtCore.Signal(object)

    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg
        self._logger = get_logger()
        self._running = False
        self._config_snapshot = self._create_config_snapshot(cfg)
        self._active_capture_signature: Optional[Tuple[str, int]] = None
        
        # 性能监控
        self._performance_timer = QElapsedTimer()
        self._scan_count = 0
        self._total_scan_time = 0.0
        
        # 模板缓存（在主线程加载，传递给子进程）
        self._templates: List[Tuple[np.ndarray, Tuple[int, int]]] = []
        self._template_paths: List[str] = []
        
        # 捕获管理器
        self._capture_manager: Optional[CaptureManager] = None
        
        # 性能优化器
        self._performance_optimizer = PerformanceOptimizer()
        
        # 点击控制
        self._consecutive = 0
        self._next_allowed = 0.0
        
        # 状态更新节流
        self._last_status_emit = 0.0
        self._status_emit_interval = 1.0  # 每秒最多更新一次状态
        
        # CPU任务管理
        self._pending_cpu_tasks: Dict[str, float] = {}  # task_id -> start_time
        self._cpu_task_timeout = 5.0  # CPU任务超时时间
        
        # 连接配置更新信号
        self.sig_update_config.connect(self._on_config_update)
        
        # 确保CPU任务管理器已启动
        cpu_manager = get_global_cpu_manager()
        if not cpu_manager._started:
            cpu_manager.start()
        
        # 连接CPU任务完成信号
        cpu_manager.signals.task_completed.connect(self._on_cpu_task_completed)
        cpu_manager.signals.task_failed.connect(self._on_cpu_task_failed)

    def update_config(self, new_cfg: AppConfig):
        """线程安全的配置更新"""
        self.sig_update_config.emit(new_cfg)

    def stop(self):
        """停止扫描"""
        self._running = False
        self._logger.info("扫描线程停止请求")

    def run(self):
        """主运行循环"""
        self._running = True
        self._consecutive = 0
        self._next_allowed = 0.0
        self._performance_timer.start()
        
        # 异步加载模板
        self._load_templates_async()
        
        # 设置 DPI 感知
        set_process_dpi_awareness()
        
        # 记录 DPI 信息
        if self.cfg.debug_mode:
            dpi_info = get_dpi_info_summary()
            self._logger.info(f"DPI 信息: {dpi_info}")
        
        # 选择捕获模式
        use_monitor = getattr(self.cfg, 'use_monitor', False)
        
        if use_monitor:
            self._run_monitor_capture_loop()
        else:
            self._run_window_capture_loop()

    def _load_templates_async(self):
        """异步加载模板"""
        def load_templates_task():
            """IO任务：加载模板文件"""
            templates = []
            template_paths = []
            
            try:
                for template_path in self.cfg.template_paths:
                    if not os.path.exists(template_path):
                        self._logger.warning(f"模板文件不存在: {template_path}")
                        continue
                    
                    # 加载模板图像
                    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
                    if template is None:
                        self._logger.warning(f"无法加载模板: {template_path}")
                        continue
                    
                    h, w = template.shape[:2]
                    templates.append((template, (w, h)))
                    template_paths.append(template_path)
                
                return {
                    'templates': templates,
                    'template_paths': template_paths,
                    'count': len(templates)
                }
            except Exception as e:
                return {'error': str(e)}
        
        def on_templates_loaded(task_id: str, result):
            """模板加载完成回调"""
            if 'error' in result:
                self._logger.error(f"模板加载失败: {result['error']}")
                return
            
            self._templates = result['templates']
            self._template_paths = result['template_paths']
            self._logger.info(f"已加载 {result['count']} 个模板")
        
        def on_templates_error(task_id: str, error_msg: str, exception):
            """模板加载失败回调"""
            self._logger.error(f"模板加载失败: {error_msg}")
        
        # 创建模板加载任务
        class TemplateLoadTask(IOTaskBase):
            def __init__(self, config):
                super().__init__("load_templates")
                self.config = config
            
            def execute(self):
                return load_templates_task()
        
        task = TemplateLoadTask(self.cfg)
        submit_io(task, on_templates_loaded, on_templates_error)

    def _create_config_snapshot(self, cfg: AppConfig) -> dict:
        """提取配置快照用于目标变更检测"""
        title = (getattr(cfg, 'target_window_title', '') or getattr(cfg, 'window_title', '') or '').strip()
        process = (getattr(cfg, 'target_process', '') or '').strip()
        return {
            'use_monitor': bool(getattr(cfg, 'use_monitor', False)),
            'target_hwnd': int(getattr(cfg, 'target_hwnd', 0) or 0),
            'target_window_title': title.lower(),
            'raw_window_title': title,
            'target_process': process.lower(),
            'raw_target_process': process,
            'monitor_index': getattr(cfg, 'monitor_index', 0)
        }

    def _window_target_changed(self, old_snap: dict, new_snap: dict) -> bool:
        """判断窗口捕获目标是否发生变化"""
        if new_snap['target_hwnd'] != old_snap.get('target_hwnd', 0):
            return True
        if new_snap['target_hwnd'] == 0 and old_snap.get('target_hwnd', 0) != 0:
            return True
        if new_snap['target_hwnd'] == 0:
            if new_snap['target_window_title'] and new_snap['target_window_title'] != old_snap.get('target_window_title', ''):
                return True
            if new_snap['target_process'] and new_snap['target_process'] != old_snap.get('target_process', ''):
                return True
        return False

    def _configure_capture_manager_for_current_mode(self, use_monitor: Optional[bool] = None):
        """按照当前模式更新捕获参数"""
        if not self._capture_manager:
            return
        target_monitor = bool(getattr(self.cfg, 'use_monitor', False)) if use_monitor is None else bool(use_monitor)
        fps = getattr(self.cfg, 'target_fps', 30)
        include_cursor = getattr(self.cfg, 'include_cursor', False)
        border_key = 'screen_border_required' if target_monitor else 'window_border_required'
        border_required = bool(getattr(self.cfg, border_key, getattr(self.cfg, 'border_required', False)))
        restore_minimized = getattr(self.cfg, 'restore_minimized_after_capture', False)
        self._capture_manager.configure(
            fps=fps,
            include_cursor=include_cursor,
            border_required=border_required,
            restore_minimized=restore_minimized
        )

    def _open_capture_target_for_current_config(self) -> bool:
        """根据最新配置打开捕获目标"""
        if not self._capture_manager:
            return False

        use_monitor = bool(getattr(self.cfg, 'use_monitor', False))
        if use_monitor:
            monitor_index = getattr(self.cfg, 'monitor_index', 0)
            success = self._capture_manager.open_monitor(monitor_index)
            if success:
                self._refresh_active_capture_signature()
                self._logger.info(f'显示器捕获初始化成功: {monitor_index}')
            else:
                self._active_capture_signature = None
                self._logger.error(f'无法打开显示器捕获: {monitor_index}')
            return success

        target_hwnd = int(getattr(self.cfg, 'target_hwnd', 0) or 0)
        title = (getattr(self.cfg, 'target_window_title', '') or getattr(self.cfg, 'window_title', '') or '').strip()
        process = (getattr(self.cfg, 'target_process', '') or '').strip()
        success = False

        if target_hwnd > 0:
            success = self._capture_manager.open_window(target_hwnd, partial_match=False, async_init=True)
        if (not success) and title:
            success = self._capture_manager.open_window(title, partial_match=True, async_init=True)
        if (not success) and process:
            success = self._capture_manager.open_window(process, partial_match=True, async_init=True)

        if success:
            self._refresh_active_capture_signature()
            stats = self._capture_manager.get_stats()
            hwnd = int(stats.get('target_hwnd') or 0)
            if hwnd:
                self._logger.info(f'窗口捕获初始化成功，当前句柄: {hwnd}')
            else:
                self._logger.info('窗口捕获初始化成功')
        else:
            self._active_capture_signature = None
            self._logger.error('无法打开窗口捕获：请检查 target_hwnd/target_window_title/target_process 配置')
        return success

    def _refresh_active_capture_signature(self):
        """刷新当前捕获目标签名"""
        if not self._capture_manager:
            self._active_capture_signature = None
            return
        stats = self._capture_manager.get_stats() or {}
        hwnd = int(stats.get('target_hwnd') or 0)
        if hwnd:
            self._active_capture_signature = ('hwnd', hwnd)
            return
        if stats.get('target_hmonitor'):
            monitor_index = getattr(self.cfg, 'monitor_index', 0)
            self._active_capture_signature = ('monitor', monitor_index)
            return
        self._active_capture_signature = None

    def _run_window_capture_loop(self):
        """窗口捕获主循环"""
        self._logger.info("启动窗口捕获循环")
        
        # 初始化捕获管理器
        if not self._init_capture_manager():
            self.sig_status.emit("WGC 窗口捕获初始化失败")
            return
        
        try:
            while self._running:
                loop_start = time.monotonic()
                
                try:
                    # 应用挂起的配置
                    self._apply_pending_config_if_any()
                    
                    # 执行扫描（异步）
                    self._scan_and_maybe_click_async()
                    
                    # 更新状态
                    self._emit_status_throttled("运行中 | 后端: WGC 窗口捕获")
                    
                except Exception as e:
                    self._logger.exception("窗口扫描异常: %s", e)
                    self.sig_log.emit(f"窗口扫描异常: {e}")
                
                # 自适应间隔控制
                loop_time = (time.monotonic() - loop_start) * 1000.0
                adaptive_interval = self._performance_optimizer.get_adaptive_interval(self.cfg.interval_ms)
                sleep_ms = max(0, int(adaptive_interval - loop_time))
                
                if sleep_ms > 0:
                    time.sleep(sleep_ms / 1000.0)
                    
        finally:
            self._cleanup_capture_manager()

    def _run_monitor_capture_loop(self):
        """显示器捕获主循环"""
        self._logger.info("启动显示器捕获循环")
        
        # 初始化显示器捕获
        if not self._init_monitor_capture():
            self.sig_status.emit("WGC 显示器捕获初始化失败")
            return
        
        try:
            while self._running:
                loop_start = time.monotonic()
                
                try:
                    # 应用挂起的配置
                    self._apply_pending_config_if_any()
                    
                    # 执行扫描（异步）
                    self._scan_and_maybe_click_async()
                    
                    # 更新状态
                    backend_desc = "WGC 显示器捕获"
                    if getattr(self.cfg, 'enable_multi_screen_polling', False):
                        current_monitor = getattr(self, '_current_polling_monitor', 0)
                        status_msg = f"运行中 | 后端: {backend_desc} | 多屏轮询 | 当前屏幕: {current_monitor}"
                    else:
                        status_msg = f"运行中 | 后端: {backend_desc}"
                    
                    self._emit_status_throttled(status_msg)
                    
                except Exception as e:
                    self._logger.exception("显示器扫描异常: %s", e)
                    self.sig_log.emit(f"显示器扫描异常: {e}")
                
                # 自适应间隔控制
                loop_time = (time.monotonic() - loop_start) * 1000.0
                adaptive_interval = self._performance_optimizer.get_adaptive_interval(self.cfg.interval_ms)
                sleep_ms = max(0, int(adaptive_interval - loop_time))
                
                if sleep_ms > 0:
                    time.sleep(sleep_ms / 1000.0)
                    
        finally:
            self._cleanup_capture_manager()

    def _scan_and_maybe_click_async(self):
        """异步扫描和点击"""
        # 检查模板是否就绪
        if not self._templates:
            return
        
        if not self._capture_manager:
            self._logger.error("捕获管理器未初始化")
            return
        
        # 捕获帧（IO操作，在当前线程执行）
        restore_after = getattr(self.cfg, 'restore_minimized_after_capture', False)
        img = self._capture_manager.capture_frame(restore_after_capture=restore_after)
        
        if img is None:
            if self.cfg.debug_mode:
                self._logger.warning("捕获帧失败")
            return
        
        # 应用 ROI（轻量操作，在当前线程执行）
        roi_img, roi_left, roi_top = self._apply_roi_to_image(img)
        
        # 提交CPU密集型任务：模板匹配
        task_id = f"template_match_{uuid.uuid4().hex[:8]}"
        self._pending_cpu_tasks[task_id] = time.monotonic()
        
        # 准备任务参数
        match_params = {
            'roi_img': roi_img,
            'templates': self._templates,
            'threshold': self.cfg.threshold,
            'grayscale': self.cfg.grayscale,
            'roi_offset': (roi_left, roi_top),
            'click_offset': self.cfg.click_offset,
            'task_id': task_id
        }
        
        # 提交到CPU进程池
        submit_cpu(
            func=template_matching_task,
            args=(match_params,),
            task_id=task_id,
            on_success=self._on_cpu_task_completed,
            on_error=self._on_cpu_task_failed
        )
        
        # 清理超时的任务
        self._cleanup_timeout_tasks()

    def _on_cpu_task_completed(self, task_id: str, result: Dict[str, Any]):
        """CPU任务完成处理"""
        if task_id not in self._pending_cpu_tasks:
            return
        
        # 移除任务记录
        start_time = self._pending_cpu_tasks.pop(task_id)
        execution_time = time.monotonic() - start_time
        
        # 更新性能统计
        self._scan_count += 1
        self._total_scan_time += execution_time
        
        # 处理匹配结果
        if result.get('match_found'):
            click_x = result['click_x']
            click_y = result['click_y']
            score = result['confidence']
            
            # 执行点击
            self._perform_click(click_x, click_y, score)
        
        # 发送状态更新
        score = result.get('confidence', 0.0)
        avg_time = self._total_scan_time / self._scan_count if self._scan_count > 0 else 0
        status_detail = f"匹配: {score:.3f} | 平均耗时: {avg_time*1000:.1f}ms"
        self._emit_status_throttled(f"运行中 | {status_detail}")

    def _on_cpu_task_failed(self, task_id: str, error_msg: str, exception):
        """CPU任务失败处理"""
        if task_id in self._pending_cpu_tasks:
            del self._pending_cpu_tasks[task_id]
        
        self._logger.error(f"模板匹配任务失败: {error_msg}")
        self.sig_log.emit(f"模板匹配失败: {error_msg}")

    def _cleanup_timeout_tasks(self):
        """清理超时的CPU任务"""
        current_time = time.monotonic()
        timeout_tasks = []
        
        for task_id, start_time in self._pending_cpu_tasks.items():
            if current_time - start_time > self._cpu_task_timeout:
                timeout_tasks.append(task_id)
        
        for task_id in timeout_tasks:
            del self._pending_cpu_tasks[task_id]
            self._logger.warning(f"CPU任务超时: {task_id}")

    def _perform_click(self, x: int, y: int, score: float):
        """执行点击"""
        now = time.monotonic()
        if now < self._next_allowed:
            return
        
        try:
            # 获取目标窗口句柄
            stats = self._capture_manager.get_stats() if self._capture_manager else {}
            target_hwnd = stats.get('target_hwnd')
            
            # 执行点击
            success = post_click_screen_pos(x, y, debug=getattr(self.cfg, 'debug_mode', False))
            
            if success:
                self._consecutive += 1
                self._next_allowed = now + self.cfg.cooldown_s
                
                # 发送命中信号
                self.sig_hit.emit(score, x, y)
                
                self._logger.info(f"点击成功: ({x}, {y}), 置信度: {score:.3f}")
            else:
                self._logger.warning(f"点击失败: ({x}, {y})")
                
        except Exception as e:
            self._logger.error(f"执行点击异常: {e}")

    def _emit_status_throttled(self, status: str):
        """节流的状态更新"""
        current_time = time.monotonic()
        if current_time - self._last_status_emit >= self._status_emit_interval:
            self.sig_status.emit(status)
            self._last_status_emit = current_time

    def _init_capture_manager(self) -> bool:
        """初始化窗口捕获管理器"""
        try:
            self._capture_manager = CaptureManager()
            self._active_capture_signature = None
            self._configure_capture_manager_for_current_mode(use_monitor=False)
            if not self._open_capture_target_for_current_config():
                return False
            return True

        except Exception as e:
            self._logger.error(f"初始化窗口捕获失败: {e}")
            return False

    def _init_monitor_capture(self) -> bool:
        """初始化显示器捕获管理器"""
        try:
            self._capture_manager = CaptureManager()
            self._active_capture_signature = None
            self._configure_capture_manager_for_current_mode(use_monitor=True)
            if not self._open_capture_target_for_current_config():
                return False
            return True

        except Exception as e:
            self._logger.error(f"初始化显示器捕获失败: {e}")
            return False

    def _cleanup_capture_manager(self):
        """清理捕获管理器"""
        if self._capture_manager:
            try:
                self._capture_manager.close()
                self._logger.info("捕获管理器已清理")
            except Exception as e:
                self._logger.error(f"清理捕获管理器失败: {e}")
            finally:
                self._capture_manager = None
                self._active_capture_signature = None

    def _apply_roi_to_image(self, img: np.ndarray) -> Tuple[np.ndarray, int, int]:
        """应用ROI到图像"""
        if not hasattr(self.cfg, 'roi') or not self.cfg.roi:
            return img, 0, 0

        roi = self.cfg.roi
        h, w = img.shape[:2]

        # 计算ROI边界
        left = max(0, min(roi.get('left', 0), w))
        top = max(0, min(roi.get('top', 0), h))
        right = max(left, min(roi.get('right', w), w))
        bottom = max(top, min(roi.get('bottom', h), h))

        # 提取ROI
        roi_img = img[top:bottom, left:right]

        return roi_img, left, top

    def _apply_pending_config_if_any(self):
        """应用挂起的配置更新"""
        # 这个方法在原版中用于处理配置更新
        # 在重构版中，配置更新通过信号处理
        pass

    def _on_config_update(self, new_cfg: AppConfig):
        """配置更新处理"""
        old_snapshot = self._config_snapshot or {}
        self.cfg = new_cfg
        self._config_snapshot = self._create_config_snapshot(new_cfg)
        self._logger.info("扫描器配置已更新")

        # 重新加载模板
        self._load_templates_async()

        if not self._capture_manager:
            return

        new_snapshot = self._config_snapshot
        use_monitor = new_snapshot['use_monitor']
        mode_switched = old_snapshot.get('use_monitor') != use_monitor
        monitor_target_changed = use_monitor and (
            mode_switched or new_snapshot['monitor_index'] != old_snapshot.get('monitor_index')
        )
        window_target_changed = (not use_monitor) and (
            mode_switched or self._window_target_changed(old_snapshot, new_snapshot)
        )
        target_changed = mode_switched or monitor_target_changed or window_target_changed

        if target_changed:
            self._logger.info("检测到捕获目标发生变更，准备重建捕获会话")
            try:
                self._capture_manager.close()
            except Exception as e:
                self._logger.warning(f"关闭旧捕获会话时出现异常: {e}")
            finally:
                self._active_capture_signature = None

        self._configure_capture_manager_for_current_mode(use_monitor=use_monitor)

        if target_changed:
            if not self._open_capture_target_for_current_config():
                status_msg = "WGC 显示器捕获初始化失败" if use_monitor else "WGC 窗口捕获初始化失败"
                self.sig_status.emit(status_msg)
        else:
            self._refresh_active_capture_signature()


# ==================== CPU密集型任务函数 ====================
# 注意：这些函数将在独立进程中执行

def template_matching_task(params: Dict[str, Any]) -> Dict[str, Any]:
    """模板匹配任务（CPU密集型）

    在独立进程中执行，不能访问Qt对象
    """
    import cv2
    import numpy as np
    import time

    start_time = time.time()

    try:
        roi_img = params['roi_img']
        templates = params['templates']
        threshold = params['threshold']
        grayscale = params['grayscale']
        roi_offset = params['roi_offset']
        click_offset = params['click_offset']
        task_id = params['task_id']

        best_score = 0.0
        best_loc = None
        best_template_size = None

        # 遍历所有模板进行匹配
        for tpl, (tw, th) in templates:
            if grayscale:
                # 转换为灰度图
                gray_roi = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY) if len(roi_img.shape) == 3 else roi_img
                gray_tpl = cv2.cvtColor(tpl, cv2.COLOR_BGR2GRAY) if len(tpl.shape) == 3 else tpl
                result = cv2.matchTemplate(gray_roi, gray_tpl, cv2.TM_CCOEFF_NORMED)
            else:
                result = cv2.matchTemplate(roi_img, tpl, cv2.TM_CCOEFF_NORMED)

            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val > best_score:
                best_score = max_val
                best_loc = max_loc
                best_template_size = (tw, th)

        execution_time = time.time() - start_time

        # 检查是否找到匹配
        match_found = best_score >= threshold and best_loc is not None

        result = {
            'task_id': task_id,
            'match_found': match_found,
            'confidence': best_score,
            'execution_time': execution_time,
            'worker_pid': os.getpid()
        }

        if match_found:
            # 计算点击坐标
            tw, th = best_template_size
            roi_left, roi_top = roi_offset

            click_x = roi_left + best_loc[0] + tw // 2 + click_offset[0]
            click_y = roi_top + best_loc[1] + th // 2 + click_offset[1]

            result.update({
                'click_x': click_x,
                'click_y': click_y,
                'template_size': best_template_size,
                'match_location': best_loc
            })

        return result

    except Exception as e:
        return {
            'task_id': params.get('task_id', 'unknown'),
            'match_found': False,
            'confidence': 0.0,
            'error': str(e),
            'execution_time': time.time() - start_time,
            'worker_pid': os.getpid()
        }

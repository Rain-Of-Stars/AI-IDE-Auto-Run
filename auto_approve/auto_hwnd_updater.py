# -*- coding: utf-8 -*-
"""
自动窗口句柄更新模块
根据配置的进程名称自动查找并更新目标窗口HWND
集成智能查找算法，提供更强大的自动窗口管理功能
"""
from __future__ import annotations
import threading
import time
from typing import Optional, Callable

from PySide6 import QtCore

from capture.monitor_utils import find_window_by_process
from auto_approve.logger_manager import get_logger
from auto_approve.config_manager import AppConfig
from auto_approve.smart_process_finder import SmartProcessFinder


class AutoHWNDUpdater(QtCore.QObject):
    """增强的自动窗口句柄更新器"""
    
    # 信号：HWND更新完成
    hwnd_updated = QtCore.Signal(int, str)  # hwnd, process_name
    # 新增信号：智能查找状态
    smart_search_status = QtCore.Signal(str, int)  # status_message, progress
    # 新增信号：自动恢复事件
    auto_recovery = QtCore.Signal(int, str)  # hwnd, process_name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        self._config: Optional[AppConfig] = None
        self._update_timer: Optional[threading.Timer] = None
        self._running = False
        self._lock = threading.Lock()
        self._current_hwnd = 0
        self._update_callback: Optional[Callable[[int], None]] = None
        
        # 智能查找器
        self._smart_finder: Optional[SmartProcessFinder] = None
        self._use_smart_finder = True  # 默认启用智能查找
        
    def set_config(self, config: AppConfig):
        """设置配置"""
        with self._lock:
            self._config = config
            self._init_smart_finder()
            self._restart_if_needed()
            
    def set_update_callback(self, callback: Optional[Callable[[int], None]]):
        """设置HWND更新回调函数"""
        self._update_callback = callback
        
    def _init_smart_finder(self):
        """初始化智能查找器"""
        if not self._config or not self._use_smart_finder:
            return
            
        try:
            # 创建智能查找器
            if self._smart_finder is None:
                self._smart_finder = SmartProcessFinder()
                
                # 连接信号
                self._smart_finder.process_found.connect(self._on_smart_process_found)
                self._smart_finder.process_lost.connect(self._on_smart_process_lost)
                self._smart_finder.search_status.connect(self.smart_search_status.emit)
                self._smart_finder.auto_recovery_triggered.connect(self.auto_recovery.emit)
                
            # 设置配置
            self._smart_finder.set_config(self._config)
            
            self.logger.info("智能查找器初始化完成")
            
        except Exception as e:
            self.logger.error(f"智能查找器初始化失败: {e}")
            self._smart_finder = None
            
    def _on_smart_process_found(self, hwnd: int, process_name: str, window_title: str):
        """智能查找器找到进程的回调"""
        with self._lock:
            if hwnd != self._current_hwnd:
                self._current_hwnd = hwnd
                self.logger.info(f"智能查找器找到进程: {process_name} -> HWND={hwnd}")
                
                # 发出信号
                self.hwnd_updated.emit(hwnd, process_name)
                
                # 调用回调函数
                if self._update_callback:
                    try:
                        self._update_callback(hwnd)
                    except Exception as e:
                        self.logger.error(f"HWND更新回调失败: {e}")
                        
    def _on_smart_process_lost(self, hwnd: int, process_name: str):
        """智能查找器丢失进程的回调"""
        with self._lock:
            if hwnd == self._current_hwnd:
                self.logger.warning(f"智能查找器丢失进程: {process_name}")
                # 不自动清空_current_hwnd，让智能查找器尝试恢复
        
    def start(self):
        """启动自动更新"""
        with self._lock:
            if self._running:
                return
            self._running = True
            
            # 启动智能查找器
            if self._smart_finder and self._use_smart_finder:
                self._smart_finder.start_smart_search()
                self.logger.info("智能查找器已启动")
            else:
                # 使用传统定时器方式
                self._schedule_next_update()
                
            self.logger.info("自动窗口句柄更新器已启动")
            
    def stop(self):
        """停止自动更新"""
        with self._lock:
            self._running = False
            
            # 停止智能查找器
            if self._smart_finder:
                self._smart_finder.stop_smart_search()
                
            # 停止传统定时器
            if self._update_timer:
                self._update_timer.cancel()
                self._update_timer = None
                
            self.logger.info("自动窗口句柄更新器已停止")
            
    def _restart_if_needed(self):
        """根据配置重启更新器"""
        if self._config and self._config.auto_update_hwnd_by_process and self._running:
            # 重启智能查找器
            if self._smart_finder and self._use_smart_finder:
                self._smart_finder.stop_smart_search()
                self._smart_finder.set_config(self._config)
                self._smart_finder.start_smart_search()
            else:
                # 传统模式：取消当前定时器
                if self._update_timer:
                    self._update_timer.cancel()
                    self._update_timer = None
                # 立即执行一次更新
                self._perform_update()
                # 重新调度
                self._schedule_next_update()
        elif self._running and (not self._config or not self._config.auto_update_hwnd_by_process):
            # 如果配置禁用，停止更新
            self.stop()
            
    def _schedule_next_update(self):
        """调度下一次更新"""
        with self._lock:
            if not self._running or not self._config:
                return
                
            if not self._config.auto_update_hwnd_by_process:
                return
                
            interval_ms = max(1000, self._config.auto_update_hwnd_interval_ms)
            self._update_timer = threading.Timer(interval_ms / 1000.0, self._perform_update)
            self._update_timer.start()
            
    def _perform_update(self):
        """执行HWND更新 - 仅基于进程名称检测"""
        try:
            with self._lock:
                if not self._running or not self._config:
                    return
                    
                if not self._config.auto_update_hwnd_by_process:
                    return
                    
                process_name = self._config.target_process
                if not process_name:
                    self.logger.warning("自动更新HWND失败：未配置目标进程名称")
                    return
                    
                partial_match = self._config.process_partial_match
                
            # 在锁外执行查找操作，避免阻塞 - 仅使用进程名称检测
            new_hwnd = find_window_by_process(process_name, partial_match)
            
            with self._lock:
                if new_hwnd and new_hwnd != self._current_hwnd:
                    self._current_hwnd = new_hwnd
                    self.logger.info(f"基于进程检测到目标窗口：进程'{process_name}' -> HWND={new_hwnd}")
                    
                    # 发出信号
                    self.hwnd_updated.emit(new_hwnd, process_name)
                    
                    # 调用回调函数
                    if self._update_callback:
                        try:
                            self._update_callback(new_hwnd)
                        except Exception as e:
                            self.logger.error(f"HWND更新回调失败: {e}")
                            
                elif not new_hwnd:
                    self.logger.debug(f"基于进程检测：未找到进程'{process_name}'的窗口")
                    
        except Exception as e:
            self.logger.error(f"基于进程的HWND检测失败: {e}")
        finally:
            # 调度下一次更新
            self._schedule_next_update()
            
    def get_current_hwnd(self) -> int:
        """获取当前HWND"""
        with self._lock:
            if self._smart_finder:
                return self._smart_finder.get_current_hwnd()
            return self._current_hwnd
            
    def is_running(self) -> bool:
        """检查是否正在运行"""
        with self._lock:
            return self._running
            
    def set_smart_finder_enabled(self, enabled: bool):
        """设置是否启用智能查找器"""
        with self._lock:
            if self._use_smart_finder != enabled:
                self._use_smart_finder = enabled
                
                if enabled and self._running:
                    # 启用智能查找器
                    self._init_smart_finder()
                    if self._smart_finder:
                        self._smart_finder.start_smart_search()
                        # 停止传统定时器
                        if self._update_timer:
                            self._update_timer.cancel()
                            self._update_timer = None
                elif not enabled and self._smart_finder:
                    # 禁用智能查找器
                    self._smart_finder.stop_smart_search()
                    # 启动传统定时器
                    self._schedule_next_update()
                    
                self.logger.info(f"智能查找器已{'启用' if enabled else '禁用'}")
                
    def force_search(self) -> Optional[int]:
        """强制执行一次查找"""
        with self._lock:
            if self._smart_finder and self._use_smart_finder:
                return self._smart_finder.force_search()
            else:
                # 传统模式查找
                self._perform_update()
                return self._current_hwnd
                
    def get_smart_finder_stats(self) -> Optional[Dict]:
        """获取智能查找器统计信息"""
        if self._smart_finder:
            return self._smart_finder.get_search_stats()
        return None
        
    def set_finder_strategy(self, strategy_name: str, enabled: bool):
        """设置查找策略"""
        if self._smart_finder:
            self._smart_finder.set_strategy_enabled(strategy_name, enabled)
            
    def cleanup(self):
        """清理资源"""
        self.stop()
        if self._smart_finder:
            self._smart_finder.cleanup()
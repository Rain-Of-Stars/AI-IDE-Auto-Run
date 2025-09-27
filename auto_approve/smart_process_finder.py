# -*- coding: utf-8 -*-
"""
智能自动进程查找增强模块

提供智能化的进程自动查找和窗口管理功能：
- 多策略进程查找算法
- 智能缓存和预测机制
- 自动进程恢复和重连
- 智能优先级排序
- 自适应查找间隔
"""

from __future__ import annotations
import time
import threading
from typing import Optional, Dict, List, Tuple, Set, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
import ctypes
from ctypes import wintypes

from PySide6 import QtCore
from capture.monitor_utils import find_window_by_process, enum_windows, get_window_rect
from auto_approve.logger_manager import get_logger
from auto_approve.config_manager import AppConfig
from auto_approve.optimized_ui_manager import get_progress_manager


@dataclass
class ProcessInfo:
    """进程信息"""
    name: str
    hwnd: int
    title: str
    path: str
    last_seen: float
    priority: int = 0
    reliability_score: float = 1.0
    
    def update_seen(self):
        """更新最后发现时间"""
        self.last_seen = time.time()
        
    def update_reliability(self, success: bool):
        """更新可靠性评分"""
        if success:
            self.reliability_score = min(1.0, self.reliability_score + 0.1)
        else:
            self.reliability_score = max(0.0, self.reliability_score - 0.2)


@dataclass
class FindStrategy:
    """查找策略"""
    name: str
    priority: int
    enabled: bool = True
    success_count: int = 0
    failure_count: int = 0
    last_used: float = 0.0
    
    def get_success_rate(self) -> float:
        """获取成功率"""
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0
        
    def record_result(self, success: bool):
        """记录查找结果"""
        self.last_used = time.time()
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1


class SmartProcessFinder(QtCore.QObject):
    """智能进程查找器"""
    
    # 信号
    process_found = QtCore.Signal(int, str, str)  # hwnd, process_name, window_title
    process_lost = QtCore.Signal(int, str)  # hwnd, process_name
    search_status = QtCore.Signal(str, int)  # status_message, progress
    auto_recovery_triggered = QtCore.Signal(int, str)  # hwnd, process_name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.logger = get_logger()
        
        # 配置
        self._config: Optional[AppConfig] = None
        
        # 非阻塞进度管理器
        self._progress_manager = get_progress_manager()
        
        # 查找策略
        self._strategies = {
            'process_name': FindStrategy('进程名称', 10),
            'process_path': FindStrategy('进程路径', 9),
            'window_title': FindStrategy('窗口标题', 8),
            'class_name': FindStrategy('窗口类名', 7),
            'fuzzy_match': FindStrategy('模糊匹配', 6)
        }
        
        # 进程缓存
        self._process_cache: Dict[str, ProcessInfo] = {}
        self._hwnd_to_process: Dict[int, str] = {}
        
        # 查找历史
        self._search_history = deque(maxlen=100)
        self._success_patterns = defaultdict(int)
        self._failure_patterns = defaultdict(int)
        
        # 智能查找状态
        self._current_target = ""
        self._current_hwnd = 0
        self._last_find_time = 0.0
        self._find_count = 0
        self._success_count = 0
        
        # 自适应参数
        self._base_interval = 1.0  # 基础查找间隔（秒）
        self._adaptive_interval = self._base_interval
        self._max_interval = 30.0  # 最大查找间隔
        self._min_interval = 0.5   # 最小查找间隔
        
        # 自动恢复机制
        self._recovery_enabled = True
        self._recovery_attempts = 0
        self._max_recovery_attempts = 5
        self._recovery_cooldown = 10.0  # 恢复冷却时间（秒）
        self._last_recovery_time = 0.0
        
        # 智能预测
        self._prediction_cache = {}
        self._prediction_accuracy = 0.0
        
        # 线程控制
        self._search_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        # WinEventHook 相关：用于即时捕获HWND变化
        self._win_event_thread: Optional[threading.Thread] = None
        self._win_event_stop = threading.Event()
        self._win_event_ready = threading.Event()
        self._hook_handles: List[int] = []
        self._hook_cbs: List[Callable] = []
        self._event_hook_enabled: bool = True  # 默认启用事件钩子
        
        # 统计信息
        self._stats = {
            'total_searches': 0,
            'successful_searches': 0,
            'failed_searches': 0,
            'avg_search_time': 0.0,
            'last_search_time': 0.0
        }
        
    def set_config(self, config: AppConfig):
        """设置配置"""
        with self._lock:
            self._config = config
            self._update_parameters_from_config()
            self._update_target_from_config()
            # 若配置切换目标，重启事件钩子
            if self._event_hook_enabled and self._search_thread and self._search_thread.is_alive():
                try:
                    self._restart_event_hooks()
                except Exception:
                    # 不因事件钩子失败影响主流程
                    pass
            
    def _update_parameters_from_config(self):
        """从配置更新参数"""
        if not self._config:
            return
            
        # 更新查找间隔
        self._base_interval = getattr(self._config, 'smart_finder_base_interval', 1.0)
        self._max_interval = getattr(self._config, 'smart_finder_max_interval', 30.0)
        self._min_interval = getattr(self._config, 'smart_finder_min_interval', 0.5)
        self._adaptive_interval = self._base_interval
        
        # 更新恢复机制
        self._recovery_enabled = getattr(self._config, 'enable_auto_recovery', True)
        self._max_recovery_attempts = getattr(self._config, 'max_recovery_attempts', 5)
        self._recovery_cooldown = getattr(self._config, 'recovery_cooldown', 10.0)
        
        # 更新查找策略
        strategies_config = getattr(self._config, 'finder_strategies', {})
        for strategy_name, strategy in self._strategies.items():
            strategy.enabled = strategies_config.get(strategy_name, True)
            
    def _update_target_from_config(self):
        """从配置更新目标进程"""
        if not self._config:
            return
            
        target_process = getattr(self._config, 'target_process', '')
        if target_process and target_process != self._current_target:
            self._current_target = target_process
            self._clear_cache()  # 目标改变，清空缓存
            self.logger.info(f"智能查找目标更新为: {target_process}")
            
    def _clear_cache(self):
        """清空缓存"""
        self._process_cache.clear()
        self._hwnd_to_process.clear()
        self._prediction_cache.clear()
        self._recovery_attempts = 0
        
    def start_smart_search(self):
        """启动智能查找"""
        with self._lock:
            if self._search_thread and self._search_thread.is_alive():
                return
                
            self._stop_event.clear()
            self._search_thread = threading.Thread(target=self._smart_search_loop, daemon=True)
            self._search_thread.start()
            self.logger.info("智能进程查找已启动")
            # 启动WinEventHook线程以即时捕获窗口变化
            if self._event_hook_enabled:
                self._start_event_hooks_async()
            
    def stop_smart_search(self):
        """停止智能查找"""
        with self._lock:
            self._stop_event.set()
            if self._search_thread and self._search_thread.is_alive():
                self._search_thread.join(timeout=2.0)
            self.logger.info("智能进程查找已停止")
            # 停止事件钩子线程
            self._stop_event_hooks()
            
    def _smart_search_loop(self):
        """智能查找主循环"""
        while not self._stop_event.is_set():
            try:
                if self._should_search():
                    self._perform_smart_search()
                
                # 自适应间隔
                time.sleep(self._adaptive_interval)
                
            except Exception as e:
                self.logger.error(f"智能查找循环异常: {e}")
                time.sleep(self._base_interval)

    # ===================== WinEventHook: 即时窗口变化捕获 =====================
    def _start_event_hooks_async(self):
        """在独立线程启动WinEventHook，避免阻塞主线程。
        说明：使用 WINEVENT_OUTOFCONTEXT+WINEVENT_SKIPOWNPROCESS，无需消息循环，
        但线程需常驻以持有回调与hook句柄，防止被GC导致钩子失效。
        """
        if self._win_event_thread and self._win_event_thread.is_alive():
            return
        self._win_event_stop.clear()
        self._win_event_ready.clear()
        self._win_event_thread = threading.Thread(target=self._event_hook_thread_main, daemon=True)
        self._win_event_thread.start()
        # 最多等待1秒确认钩子安装成功/失败
        self._win_event_ready.wait(timeout=1.0)

    def _stop_event_hooks(self):
        """停止WinEventHook线程并卸载钩子"""
        try:
            self._win_event_stop.set()
            # 卸载所有钩子
            try:
                user32 = ctypes.WinDLL('user32', use_last_error=True)
                for h in self._hook_handles:
                    try:
                        user32.UnhookWinEvent(h)
                    except Exception:
                        pass
            finally:
                self._hook_handles.clear()
                self._hook_cbs.clear()
            # 等待线程退出
            if self._win_event_thread and self._win_event_thread.is_alive():
                self._win_event_thread.join(timeout=2.0)
        except Exception:
            pass

    def _restart_event_hooks(self):
        """重启事件钩子（用于目标或配置变化）"""
        self._stop_event_hooks()
        self._start_event_hooks_async()

    def _event_hook_thread_main(self):
        """事件钩子线程主函数：安装钩子并保持线程常驻"""
        try:
            # 若无目标，直接返回并标记ready，避免阻塞
            target = None
            with self._lock:
                target = self._current_target
            if not target:
                self._win_event_ready.set()
                # 等待直到被停止
                while not self._win_event_stop.is_set():
                    time.sleep(0.2)
                return

            user32 = ctypes.WinDLL('user32', use_last_error=True)

            # 常量定义（仅此处使用，避免全局污染）
            EVENT_SYSTEM_FOREGROUND = 0x0003
            EVENT_OBJECT_CREATE = 0x8000
            EVENT_OBJECT_DESTROY = 0x8001
            EVENT_OBJECT_SHOW = 0x8002
            EVENT_OBJECT_NAMECHANGE = 0x800C
            WINEVENT_OUTOFCONTEXT = 0x0000
            WINEVENT_SKIPOWNPROCESS = 0x0002

            WinEventProcType = ctypes.WINFUNCTYPE(
                None,
                wintypes.HANDLE,  # HWINEVENTHOOK
                wintypes.DWORD,   # event
                wintypes.HWND,    # hwnd
                wintypes.LONG,    # idObject
                wintypes.LONG,    # idChild
                wintypes.DWORD,   # idEventThread
                wintypes.DWORD    # dwmsEventTime
            )

            def _install(event_min: int, event_max: int, cb):
                # 先创建回调包装对象，既用于传入API，也要保存引用防GC
                cb_wrap = WinEventProcType(cb)
                handle = user32.SetWinEventHook(
                    event_min, event_max,
                    None,
                    cb_wrap,
                    0, 0,
                    WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS
                )
                if handle:
                    self._hook_handles.append(handle)
                    self._hook_cbs.append(cb_wrap)
                return handle

            # 事件回调：将候选窗口提交给评估函数
            def _event_cb_factory(tag: str):
                def _cb(hWinEventHook, event, hwnd, idObject, idChild, idEventThread, dwmsEventTime):
                    try:
                        # 仅处理窗口对象且是顶层窗口
                        if idObject != 0 or idChild != 0:
                            return
                        if not hwnd:
                            return
                        # 提交候选，由内部进行目标与可见性判断
                        self._on_window_event_candidate(int(hwnd), int(event), source=tag)
                    except Exception:
                        pass
                return _cb

            # 安装我们关心的几个事件范围
            ok1 = _install(EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND, _event_cb_factory('FOREGROUND'))
            ok2 = _install(EVENT_OBJECT_CREATE, EVENT_OBJECT_SHOW, _event_cb_factory('CREATE_SHOW'))
            ok3 = _install(EVENT_OBJECT_NAMECHANGE, EVENT_OBJECT_NAMECHANGE, _event_cb_factory('NAMECHANGE'))

            if not (ok1 or ok2 or ok3):
                # 安装失败则直接返回，后续回退到轮询
                self._win_event_ready.set()
                return

            self._win_event_ready.set()
            # 线程常驻：不需要消息泵，保持存活以持有hook与回调
            while not self._win_event_stop.is_set():
                time.sleep(0.2)
        except Exception as e:
            # 任何异常不影响主流程
            try:
                self.logger.debug(f"WinEventHook线程异常: {e}")
            except Exception:
                pass
        finally:
            # 退出前尝试卸载
            try:
                user32 = ctypes.WinDLL('user32', use_last_error=True)
                for h in self._hook_handles:
                    try:
                        user32.UnhookWinEvent(h)
                    except Exception:
                        pass
            except Exception:
                pass
            self._hook_handles.clear()
            self._hook_cbs.clear()

    def _on_window_event_candidate(self, hwnd: int, event_id: int, source: str = ""):
        """处理来自WinEventHook的候选窗口。
        - 验证是否属于目标进程
        - 评估是否更适合作为新的主HWND（前台窗口优先，面积更大优先）
        """
        try:
            with self._lock:
                target = self._current_target
                current = self._current_hwnd
            if not target or not hwnd:
                return

            # 仅当窗口属于目标进程时继续
            info = self._get_window_info(hwnd)
            if not info or not info.get('process'):
                return
            target_lower = target.lower()
            proc_lower = info['process'].lower()
            path_lower = info.get('path', '').lower()
            if (target_lower not in proc_lower) and (target_lower not in path_lower):
                return

            # 窗口有效且可见
            if not self._is_window_valid(hwnd):
                return

            # 如果当前为空，直接采用
            if not current:
                self._adopt_new_hwnd(hwnd, reason=f"event:{source}")
                return

            if hwnd == current:
                return

            # 评估：若是前台事件，直接切换；否则按面积与可见性决定
            EVENT_SYSTEM_FOREGROUND = 0x0003
            if event_id == EVENT_SYSTEM_FOREGROUND:
                self._adopt_new_hwnd(hwnd, reason=f"foreground:{source}")
                return

            # 非前台：比较面积，优先取更大可见窗口，避免工具/对话框占用
            try:
                from capture.monitor_utils import get_window_rect
                rect_new = get_window_rect(hwnd) or {}
                rect_cur = get_window_rect(current) or {}
                area_new = max(0, int(rect_new.get('width', 0))) * max(0, int(rect_new.get('height', 0)))
                area_cur = max(0, int(rect_cur.get('width', 0))) * max(0, int(rect_cur.get('height', 0)))
            except Exception:
                area_new = 0
                area_cur = 0

            if area_new > 0 and area_new >= max(area_cur, 160*120):
                self._adopt_new_hwnd(hwnd, reason=f"area:{source}")
        except Exception:
            # 静默忽略，避免影响主流程
            pass

    def _adopt_new_hwnd(self, hwnd: int, reason: str = ""):
        """采用新的主HWND并发出相应信号。"""
        try:
            start_time = time.time()
            with self._lock:
                self._current_hwnd = hwnd
                self._find_count += 1
                self._success_count += 1
                self._stats['total_searches'] += 1
                self._stats['successful_searches'] += 1
                self._stats['last_search_time'] = 0.0
                # 成功后适当延长间隔，避免抖动
                self._update_adaptive_interval(True)

            window_info = self._get_window_info(hwnd)
            if window_info:
                self.process_found.emit(hwnd, window_info['process'], window_info['title'])
                self._progress_manager.update_progress("process_finder", 100)
                self._progress_manager.update_status("process_finder", f"切换窗口({reason}) -> {window_info['process']}")
                try:
                    self.logger.info(f"事件驱动切换HWND: {hwnd}，原因={reason}")
                except Exception:
                    pass
        except Exception:
            pass
                
    def _should_search(self) -> bool:
        """判断是否应该执行查找"""
        if not self._current_target:
            return False
            
        # 检查是否需要自动恢复
        if self._recovery_enabled and self._should_attempt_recovery():
            return True
            
        # 检查当前窗口是否仍然有效
        if self._current_hwnd:
            if not self._is_window_valid(self._current_hwnd):
                self.logger.info(f"当前窗口失效: HWND={self._current_hwnd}")
                self.process_lost.emit(self._current_hwnd, self._current_target)
                self._current_hwnd = 0
                return True
            else:
                # 新增：即使当前句柄仍有效，也周期性核对是否出现了更合适的顶层窗口（例如主窗口重建）
                # 频率受自适应间隔控制，避免过度消耗
                try:
                    candidate = self._search_by_process_name()
                    if candidate and candidate != self._current_hwnd:
                        # 仅当候选明显更优（如面积更大）时才切换，降低误切
                        from capture.monitor_utils import get_window_rect
                        rect_new = get_window_rect(candidate) or {}
                        rect_cur = get_window_rect(self._current_hwnd) or {}
                        area_new = max(0, int(rect_new.get('width', 0))) * max(0, int(rect_new.get('height', 0)))
                        area_cur = max(0, int(rect_cur.get('width', 0))) * max(0, int(rect_cur.get('height', 0)))
                        if area_new > max(area_cur, 200*150):
                            self._adopt_new_hwnd(candidate, reason="periodic-better")
                            return False
                except Exception:
                    pass
        else:
            # 首次启动或当前无窗口，执行查找
            return True
                
        return False
        
    def _should_attempt_recovery(self) -> bool:
        """判断是否应该尝试自动恢复"""
        if not self._current_hwnd:
            return False
            
        current_time = time.time()
        if (current_time - self._last_recovery_time < self._recovery_cooldown or
            self._recovery_attempts >= self._max_recovery_attempts):
            return False
            
        return not self._is_window_valid(self._current_hwnd)
        
    def _is_window_valid(self, hwnd: int) -> bool:
        """检查窗口是否仍然有效"""
        try:
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            return bool(user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd))
        except Exception:
            return False
            
    def _perform_smart_search(self):
        """执行智能查找"""
        start_time = time.time()
        
        try:
            # 使用非阻塞进度更新
            self._progress_manager.update_status("process_finder", f"正在查找进程: {self._current_target}")
            self._progress_manager.update_progress("process_finder", 0)
            
            # 使用多策略查找
            hwnd = self._multi_strategy_search()
            
            if hwnd:
                self._handle_search_success(hwnd, start_time)
            else:
                self._handle_search_failure(start_time)
                
        except Exception as e:
            self.logger.error(f"智能查找失败: {e}")
            self._handle_search_failure(start_time)
            
    def _multi_strategy_search(self) -> Optional[int]:
        """多策略查找"""
        strategies = sorted(self._strategies.values(), 
                         key=lambda s: (s.enabled, s.priority, s.get_success_rate()), 
                         reverse=True)
        
        total_strategies = len([s for s in strategies if s.enabled])
        current_strategy = 0
        
        for strategy in strategies:
            if not strategy.enabled:
                continue
                
            # 更新进度
            current_strategy += 1
            progress = int((current_strategy / total_strategies) * 80)  # 80%用于查找
            self._progress_manager.update_progress("process_finder", progress)
            self._progress_manager.update_status("process_finder", f"正在用{strategy.name}查找...")
                
            hwnd = self._try_strategy(strategy.name)
            if hwnd:
                strategy.record_result(True)
                return hwnd
            else:
                strategy.record_result(False)
                
        return None
        
    def _try_strategy(self, strategy_name: str) -> Optional[int]:
        """尝试特定策略"""
        if not self._current_target:
            return None
            
        if strategy_name == '进程名称':
            return self._search_by_process_name()
        elif strategy_name == '进程路径':
            return self._search_by_process_path()
        elif strategy_name == '窗口标题':
            return self._search_by_window_title()
        elif strategy_name == '窗口类名':
            return self._search_by_class_name()
        elif strategy_name == '模糊匹配':
            return self._search_by_fuzzy_match()
            
        return None
        
    def _search_by_process_name(self) -> Optional[int]:
        """按进程名称查找"""
        try:
            # 从目标进程中提取进程名
            import os
            process_name = os.path.basename(self._current_target)
            if not process_name:
                process_name = self._current_target
                
            # 移除扩展名进行匹配
            base_name = os.path.splitext(process_name)[0]
            
            # 先尝试精确匹配（严格）
            hwnd = find_window_by_process(process_name, partial_match=False)
            if hwnd:
                return hwnd

            # 是否允许部分匹配由配置控制；未配置时默认允许
            allow_partial = True
            if self._config is not None:
                allow_partial = getattr(self._config, 'process_partial_match', True)

            if not allow_partial:
                # 严格模式：不进行任何部分匹配
                return None

            # 尝试不带扩展名的部分匹配（常见：传入 explorer → 匹配 explorer.exe）
            hwnd = find_window_by_process(base_name, partial_match=True)
            if hwnd:
                return hwnd

            # 兜底：对原始名做部分匹配
            return find_window_by_process(process_name, partial_match=True)
            
        except Exception as e:
            self.logger.debug(f"进程名称查找失败: {e}")
            return None
            
    def _search_by_process_path(self) -> Optional[int]:
        """按进程路径查找"""
        try:
            if '\\' not in self._current_target:
                return None
                
            hwnd = find_window_by_process(self._current_target, partial_match=False)
            return hwnd
            
        except Exception as e:
            self.logger.debug(f"进程路径查找失败: {e}")
            return None
            
    def _search_by_window_title(self) -> Optional[int]:
        """按窗口标题查找"""
        try:
            # 获取所有可见窗口
            windows = enum_windows()
            
            # 按标题匹配
            for hwnd, title in windows:
                if self._current_target.lower() in title.lower():
                    return hwnd
                    
            return None
            
        except Exception as e:
            self.logger.debug(f"窗口标题查找失败: {e}")
            return None
            
    def _search_by_class_name(self) -> Optional[int]:
        """按窗口类名查找"""
        try:
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            
            found_hwnd = 0
            
            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def enum_proc(hwnd, lparam):
                nonlocal found_hwnd
                try:
                    if not user32.IsWindowVisible(hwnd):
                        return True
                        
                    # 获取窗口类名
                    buf = ctypes.create_unicode_buffer(256)
                    if user32.GetClassNameW(hwnd, buf, 256) > 0:
                        class_name = buf.value.lower()
                        if self._current_target.lower() in class_name:
                            found_hwnd = hwnd
                            return False
                except Exception:
                    pass
                return True
                
            user32.EnumWindows(enum_proc, 0)
            return found_hwnd if found_hwnd else None
            
        except Exception as e:
            self.logger.debug(f"窗口类名查找失败: {e}")
            return None
            
    def _search_by_fuzzy_match(self) -> Optional[int]:
        """模糊匹配查找"""
        try:
            # 简单的模糊匹配：检查窗口标题和进程名是否包含目标关键词
            windows = enum_windows()
            target_lower = self._current_target.lower()
            
            for hwnd, title in windows:
                title_lower = title.lower()
                
                # 检查标题是否包含目标关键词的任意部分
                target_parts = target_lower.replace('.', ' ').replace('_', ' ').split()
                if any(part in title_lower for part in target_parts if len(part) > 2):
                    return hwnd
                    
            return None
            
        except Exception as e:
            self.logger.debug(f"模糊匹配查找失败: {e}")
            return None
            
    def _handle_search_success(self, hwnd: int, start_time: float):
        """处理查找成功"""
        search_time = time.time() - start_time
        
        with self._lock:
            self._current_hwnd = hwnd
            self._find_count += 1
            self._success_count += 1
            self._stats['total_searches'] += 1
            self._stats['successful_searches'] += 1
            self._stats['last_search_time'] = search_time
            
            # 更新自适应间隔
            self._update_adaptive_interval(True)
            
            # 更新缓存
            self._update_process_cache(hwnd)
            
            # 如果是恢复操作，发出恢复信号
            if self._recovery_attempts > 0:
                self.auto_recovery_triggered.emit(hwnd, self._current_target)
                self._recovery_attempts = 0
                self._last_recovery_time = time.time()
                
        # 获取窗口信息
        window_info = self._get_window_info(hwnd)
        if window_info:
            # 直接发出信号，PyQt6会自动处理跨线程信号传递
            self.process_found.emit(hwnd, window_info['process'], window_info['title'])
            self.logger.info(f"发出process_found信号: HWND={hwnd}, 进程={window_info['process']}")
        
        # 更新进度到100%
        self._progress_manager.update_progress("process_finder", 100)
        self._progress_manager.update_status("process_finder", f"找到进程: {window_info['process'] if window_info else '未知'}")
        
        # 发出状态信号（保持兼容性）
        self.search_status.emit(f"找到进程: {window_info['process'] if window_info else '未知'}", 100)
        self.logger.info(f"智能查找成功: HWND={hwnd}, 耗时={search_time:.3f}s")
        
    def _handle_search_failure(self, start_time: float):
        """处理查找失败"""
        search_time = time.time() - start_time
        
        with self._lock:
            self._find_count += 1
            self._stats['total_searches'] += 1
            self._stats['failed_searches'] += 1
            self._stats['last_search_time'] = search_time
            
            # 更新自适应间隔
            self._update_adaptive_interval(False)
            
        # 更新进度显示失败
        self._progress_manager.update_progress("process_finder", 0)
        self._progress_manager.update_status("process_finder", f"未找到进程: {self._current_target}")
        
        # 发出状态信号（保持兼容性）
        self.search_status.emit(f"未找到进程: {self._current_target}", 0)
        self.logger.warning(f"智能查找失败: 目标={self._current_target}, 耗时={search_time:.3f}s")
        
    def _update_adaptive_interval(self, success: bool):
        """更新自适应查找间隔"""
        if success:
            # 成功时逐渐增加间隔
            self._adaptive_interval = min(self._max_interval, 
                                        self._adaptive_interval * 1.2)
        else:
            # 失败时减少间隔
            self._adaptive_interval = max(self._min_interval, 
                                        self._adaptive_interval * 0.8)
            
    def _update_process_cache(self, hwnd: int):
        """更新进程缓存"""
        try:
            window_info = self._get_window_info(hwnd)
            if not window_info:
                return
                
            process_key = window_info['process']
            
            # 更新或创建进程信息
            if process_key in self._process_cache:
                process_info = self._process_cache[process_key]
                process_info.hwnd = hwnd
                process_info.title = window_info['title']
                process_info.update_seen()
                process_info.update_reliability(True)
            else:
                process_info = ProcessInfo(
                    name=process_key,
                    hwnd=hwnd,
                    title=window_info['title'],
                    path=window_info['path'],
                    last_seen=time.time()
                )
                self._process_cache[process_key] = process_info
                
            self._hwnd_to_process[hwnd] = process_key
            
            # 清理过期缓存
            self._cleanup_cache()
            
        except Exception as e:
            self.logger.debug(f"更新进程缓存失败: {e}")
            
    def _cleanup_cache(self):
        """清理过期缓存"""
        current_time = time.time()
        expire_time = 300  # 5分钟过期
        
        # 清理过期的进程缓存
        expired_keys = []
        for key, process_info in self._process_cache.items():
            if current_time - process_info.last_seen > expire_time:
                expired_keys.append(key)
                
        for key in expired_keys:
            process_info = self._process_cache.pop(key)
            if process_info.hwnd in self._hwnd_to_process:
                del self._hwnd_to_process[process_info.hwnd]
                
    def _get_window_info(self, hwnd: int) -> Optional[Dict]:
        """获取窗口信息"""
        try:
            import os
            
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            psapi = ctypes.WinDLL('psapi', use_last_error=True)
            
            # 获取窗口标题
            length = user32.GetWindowTextLengthW(hwnd)
            title = ""
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                
            # 获取进程信息
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            
            process_path = ""
            process_name = ""
            if pid.value:
                hprocess = kernel32.OpenProcess(0x0400 | 0x0010, False, pid.value)
                if hprocess:
                    try:
                        buf = ctypes.create_unicode_buffer(1024)
                        if psapi.GetModuleFileNameExW(hprocess, None, buf, 1024):
                            process_path = buf.value
                            process_name = os.path.basename(process_path)
                    finally:
                        kernel32.CloseHandle(hprocess)
                        
            return {
                'hwnd': hwnd,
                'title': title,
                'process': process_name,
                'path': process_path
            }
            
        except Exception as e:
            self.logger.debug(f"获取窗口信息失败: {e}")
            return None
            
    def get_current_hwnd(self) -> int:
        """获取当前窗口句柄"""
        with self._lock:
            return self._current_hwnd
            
    def get_search_stats(self) -> Dict:
        """获取查找统计信息"""
        with self._lock:
            # 构建策略信息字典
            strategies_dict = {}
            for name, strategy in self._strategies.items():
                strategies_dict[name] = {
                    'enabled': strategy.enabled,
                    'priority': strategy.priority,
                    'success_rate': strategy.get_success_rate(),
                    'success_count': strategy.success_count,
                    'failure_count': strategy.failure_count
                }
            
            # 构建完整统计信息
            stats_dict = {
                **self._stats,
                'find_count': self._find_count,
                'success_count': self._success_count,
                'success_rate': self._success_count / self._find_count if self._find_count > 0 else 0.0,
                'adaptive_interval': self._adaptive_interval,
                'cache_size': len(self._process_cache),
                'strategies': strategies_dict
            }
            
            return stats_dict
            
    def force_search(self) -> Optional[int]:
        """强制执行一次查找"""
        if not self._current_target:
            return None
            
        self._perform_smart_search()
        return self._current_hwnd
        
    def set_strategy_enabled(self, strategy_name: str, enabled: bool):
        """设置策略启用状态"""
        if strategy_name in self._strategies:
            self._strategies[strategy_name].enabled = enabled
            self.logger.info(f"查找策略 '{strategy_name}' 已{'启用' if enabled else '禁用'}")
            
    def _emit_process_found(self, hwnd: int, process_name: str, window_title: str):
        """在主线程中发出process_found信号"""
        self.process_found.emit(hwnd, process_name, window_title)
    
    def _emit_search_status(self, message: str, progress: int):
        """在主线程中发出search_status信号"""
        self.search_status.emit(message, progress)
    
    def cleanup(self):
        """清理资源"""
        self.stop_smart_search()
        self._clear_cache()

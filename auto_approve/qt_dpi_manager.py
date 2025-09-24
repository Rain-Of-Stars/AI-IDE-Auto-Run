# -*- coding: utf-8 -*-
"""
Qt 高DPI/多屏缩放管理器

目标：
- 在创建 QApplication 前后分别做好两件事：
  1) 提前设置 Qt 的高DPI缩放因子取整策略（避免跨屏抖动与警告）；
  2) 在应用创建后监听屏幕变化，尽量保持多屏缩放一致的体验，并提供统一的查询接口。

使用说明：
- 在主入口模块最早位置调用 `set_rounding_policy_early()`（在创建 QApplication 之前）。
- 创建 QApplication 之后，实例化 `QtDpiManager(app)` 以监听屏幕变化并暴露查询工具。

注意：
- 本模块的导入不会强依赖 PySide6，不安装 PySide6 也能导入；只有在实际
  调用 Qt 相关 API 时才会访问 Qt 类型，便于编写可运行的单元测试。
"""

from __future__ import annotations
import os
from dataclasses import dataclass
from typing import Optional, Tuple

# ----------------------- 纯函数与配置解析（可单测，无 Qt 依赖） -----------------------

_POLICY_ENV = "AIIDE_DPI_ROUNDING_POLICY"


def resolve_rounding_policy(env: Optional[dict] = None) -> str:
    """解析取整策略（无 Qt 依赖）

    环境变量优先级：
    - AIIDE_DPI_ROUNDING_POLICY: pass|floor|ceil|round（大小写均可）
    - 若未指定，默认使用 RoundPreferFloor（与现有工程测试保持一致）

    返回值为策略名称字符串，用于后续映射到 Qt 枚举：
    - "PassThrough"
    - "Round"
    - "Ceil"
    - "RoundPreferFloor"(默认)
    """
    e = env or os.environ
    val = str(e.get(_POLICY_ENV, "")).strip().lower()
    if val in ("pass", "passthrough", "p"):
        return "PassThrough"
    if val in ("ceil", "c"):
        return "Ceil"
    if val in ("round", "r"):
        return "Round"
    # 默认：与现有工程测试用例一致
    return "RoundPreferFloor"


def compute_scale_for_dpi(dpi: float, base: float = 96.0) -> float:
    """根据 DPI 计算缩放因子（无 Qt 依赖）"""
    try:
        dpi = float(dpi)
        base = float(base) if base else 96.0
        if dpi <= 0:
            return 1.0
        return dpi / base
    except Exception:
        return 1.0


# ----------------------- Qt 相关：提前设置与运行时管理 -----------------------

def _qt_enums():
    """惰性导入 Qt 并返回需要的枚举，避免无 PySide6 时导入失败。"""
    from PySide6 import QtCore, QtGui
    return QtCore, QtGui


def set_rounding_policy_early(policy_name: Optional[str] = None) -> None:
    """在创建 QApplication 之前设置缩放因子取整策略。

    参数：
    - policy_name: 若为 None 则从环境变量解析；否则应为 resolve_rounding_policy 的返回值。
    """
    try:
        QtCore, QtGui = _qt_enums()
        if hasattr(QtGui.QGuiApplication, 'setHighDpiScaleFactorRoundingPolicy'):
            name = policy_name or resolve_rounding_policy()
            mapping = {
                "PassThrough": QtCore.Qt.HighDpiScaleFactorRoundingPolicy.PassThrough,
                "Round": QtCore.Qt.HighDpiScaleFactorRoundingPolicy.Round,
                "Ceil": QtCore.Qt.HighDpiScaleFactorRoundingPolicy.Ceil,
                "RoundPreferFloor": QtCore.Qt.HighDpiScaleFactorRoundingPolicy.RoundPreferFloor,
            }
            QtGui.QGuiApplication.setHighDpiScaleFactorRoundingPolicy(mapping.get(name, mapping["RoundPreferFloor"]))
    except Exception:
        # 静默降级：保持与 Qt 默认行为一致，避免在不支持的平台上崩溃
        pass


@dataclass
class ScreenScale:
    """屏幕缩放信息快照（简化结构，便于日志与调试）"""
    name: str
    dpi: float
    dpr: float
    scale: float


class QtDpiManager:
    """Qt 高DPI/多屏缩放管理器

    功能：
    - 监听屏幕增删与主屏切换，更新内部缩放信息（用于诊断与可选的统一缩放策略）。
    - 暴露 `effective_scale(widget)` 与 `snapshot()` 便于业务侧做像素/字体等按比例适配。
    - 可选“统一缩放外观”模式：将应用字体按主屏缩放一次性调整，减轻跨屏跳动感。
      注意：该模式不会改变 Qt 的 per-monitor 缩放行为，仅通过字体大小微调达到观感一致。
    """

    def __init__(self, app, unify_appearance: bool = False):
        from PySide6 import QtCore
        self._app = app
        self._unify = unify_appearance
        self._primary = app.primaryScreen()
        self._scales: dict[str, ScreenScale] = {}
        # 记录基准缩放：用于跨屏一致外观计算
        try:
            base_dpi = float(self._primary.logicalDotsPerInch()) if self._primary else 96.0
        except Exception:
            base_dpi = 96.0
        self._base_scale: float = compute_scale_for_dpi(base_dpi)

        # 建立连接：屏幕增删/主屏变更
        app.screenAdded.connect(self._on_screen_added)
        app.screenRemoved.connect(self._on_screen_removed)
        app.primaryScreenChanged.connect(self._on_primary_changed)

        # 初始化现有屏幕
        for s in app.screens():
            self._attach_screen_signals(s)
            self._update_screen_scale(s)

        if self._unify:
            self._apply_unified_font_scale()

    # ------------------- 公共接口 -------------------
    def effective_scale(self, widget) -> float:
        """返回给定部件当前屏幕的缩放因子（dpi/96）。"""
        try:
            screen = (widget.window().windowHandle().screen() if widget else None) or self._app.primaryScreen()
            if screen is None:
                return 1.0
            dpi = float(screen.logicalDotsPerInch())
            return compute_scale_for_dpi(dpi)
        except Exception:
            return 1.0

    def snapshot(self) -> dict:
        """返回当前所有屏幕的缩放信息快照，便于日志与调试。"""
        return {k: vars(v) for k, v in self._scales.items()}

    # 一致外观：计算相对基准屏的比例（>1 表示更“密”，需要放大像素型尺寸）
    def consistency_ratio(self, widget) -> float:
        """返回相对基准屏的缩放比：current_scale / base_scale。"""
        cur = self.effective_scale(widget)
        base = self._base_scale or 1.0
        return max(0.5, min(4.0, cur / base))

    def scale_px(self, px: int, widget) -> int:
        """将像素尺寸按一致外观进行缩放（用于像素单位的控件尺寸/间距/图标）。"""
        try:
            r = self.consistency_ratio(widget)
            return max(1, int(round(px * r)))
        except Exception:
            return px

    # 供业务调用：为窗口安装跨屏自适应适配器
    def attach_window_adapter(self, widget, on_ratio_changed: Optional[callable] = None):
        """为顶层窗口安装DPI适配器：
        - 监听窗口跨屏移动与screenChanged；
        - 计算一致外观比例并回调业务侧处理像素单位控件；
        - 默认回调为空；业务可在回调内按需调整如QToolBar.iconSize、行高等。
        """
        try:
            from PySide6 import QtCore

            class _Adapter(QtCore.QObject):
                def __init__(self, outer, w, cb):
                    super().__init__(w)
                    self.outer = outer
                    self.w = w
                    self.cb = cb
                    self._last_screen = None
                    self._install()

                def _install(self):
                    try:
                        wh = self.w.windowHandle()
                        if wh is not None:
                            try:
                                wh.screenChanged.connect(self._on_screen_changed)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    self.w.installEventFilter(self)
                    # 首次触发
                    QtCore.QTimer.singleShot(0, self._emit_if_changed)

                def _on_screen_changed(self, *args):
                    self._emit_if_changed()

                def eventFilter(self, obj, ev):
                    et = ev.type()
                    # 监听移动/显示/状态变化等可能导致跨屏
                    if et in (QtCore.QEvent.Move, QtCore.QEvent.Show, QtCore.QEvent.WindowStateChange, QtCore.QEvent.Resize):
                        self._emit_if_changed()
                    return super().eventFilter(obj, ev)

                def _emit_if_changed(self):
                    s = choose_screen_for_widget(self.w)
                    if s is not self._last_screen and s is not None:
                        self._last_screen = s
                        ratio = self.outer.consistency_ratio(self.w)
                        # 为窗口打标，方便调试
                        try:
                            self.w.setProperty('aiide_dpi_ratio', ratio)
                        except Exception:
                            pass
                        if callable(self.cb):
                            try:
                                self.cb(self.w, ratio)
                            except Exception:
                                pass

            _Adapter(self, widget, on_ratio_changed)
        except Exception:
            pass

    # ------------------- 内部实现 -------------------
    def _attach_screen_signals(self, screen):
        from PySide6 import QtCore
        # Qt6: QScreen 没有 dpiChanged 信号，但 logicalDotsPerInchChanged/geometryChanged/dpi (间接)
        # 这里选择 geometryChanged + physicalDotsPerInchX/Y 再取一次值
        try:
            screen.geometryChanged.connect(lambda *_: self._update_screen_scale(screen))
        except Exception:
            pass
        try:
            # 某些平台支持以下信号
            getattr(screen, 'physicalDotsPerInchChanged', None) and screen.physicalDotsPerInchChanged.connect(lambda *_: self._update_screen_scale(screen))
        except Exception:
            pass

    def _update_screen_scale(self, screen):
        try:
            name = screen.name() or "Unnamed"
            dpi = float(screen.logicalDotsPerInch())
            dpr = float(getattr(screen, 'devicePixelRatio', lambda: 1.0)())
            scale = compute_scale_for_dpi(dpi)
            self._scales[name] = ScreenScale(name=name, dpi=dpi, dpr=dpr, scale=scale)
            if self._unify:
                self._apply_unified_font_scale()
        except Exception:
            pass

    def _apply_unified_font_scale(self):
        """按主屏缩放一次性调节应用字体，以提高跨屏观感一致性。"""
        try:
            primary = self._app.primaryScreen() or self._primary
            if not primary:
                return
            base_scale = compute_scale_for_dpi(float(primary.logicalDotsPerInch()))
            if base_scale <= 0:
                return
            f = self._app.font()
            # 将 pointSize 调整为相对 10pt 的缩放，避免在多屏来回移动时字体抖动
            ps = max(8, round(10 * base_scale))
            f.setPointSize(ps)
            self._app.setFont(f)
        except Exception:
            pass

    # 屏幕事件处理
    def _on_screen_added(self, screen):
        self._attach_screen_signals(screen)
        self._update_screen_scale(screen)

    def _on_screen_removed(self, screen):
        try:
            name = screen.name() or "Unnamed"
            self._scales.pop(name, None)
        except Exception:
            pass

    def _on_primary_changed(self, screen):
        self._primary = screen
        self._update_screen_scale(screen)


# ------------------- 纯算法：窗口所在屏幕判定（可单测） -------------------

def rect_intersection_area(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> int:
    """返回两个矩形交集面积，矩形为(left, top, right, bottom)。"""
    try:
        l = max(a[0], b[0]); t = max(a[1], b[1])
        r = min(a[2], b[2]); btm = min(a[3], b[3])
        w = max(0, r - l); h = max(0, btm - t)
        return w * h
    except Exception:
        return 0


def choose_screen_by_rect(window_rect: Tuple[int, int, int, int], screens: list[Tuple[int, int, int, int]]) -> int:
    """根据最大交集面积选择窗口所在屏幕，返回索引；若无交集，返回最接近中心点的屏幕索引。"""
    if not screens:
        return -1
    # 先比交集面积
    areas = [rect_intersection_area(window_rect, s) for s in screens]
    idx = max(range(len(screens)), key=lambda i: areas[i])
    if areas[idx] > 0:
        return idx
    # 无交集：取窗口中心点，找包含该点或距离最近的屏
    cx = (window_rect[0] + window_rect[2]) // 2
    cy = (window_rect[1] + window_rect[3]) // 2
    def _dist2(sr):
        # 点到矩形的最短距离平方
        x = cx if sr[0] <= cx <= sr[2] else (sr[0] if cx < sr[0] else sr[2])
        y = cy if sr[1] <= cy <= sr[3] else (sr[1] if cy < sr[1] else sr[3])
        dx = cx - x; dy = cy - y
        return dx*dx + dy*dy
    return min(range(len(screens)), key=lambda i: _dist2(screens[i]))


def choose_screen_for_widget(widget):
    """使用Qt对象判断窗口所在屏幕；在多屏跨越时选择交集面积最大的屏幕。"""
    try:
        from PySide6 import QtCore
        if widget is None:
            return None
        win = widget.window()
        if win is None:
            return None
        fg = win.frameGeometry()
        wr = (fg.left(), fg.top(), fg.right(), fg.bottom())
        app = QtCore.QCoreApplication.instance()
        screens = [s.geometry() for s in app.screens()] if app else []
        rects = [(g.left(), g.top(), g.right(), g.bottom()) for g in screens]
        idx = choose_screen_by_rect(wr, rects)
        if 0 <= idx < len(screens):
            return app.screens()[idx]
    except Exception:
        pass
    # 兜底：直接返回窗口句柄的screen或主屏
    try:
        wh = widget.windowHandle()
        return (wh.screen() if wh else None) or (QtCore.QCoreApplication.instance().primaryScreen())
    except Exception:
        return None

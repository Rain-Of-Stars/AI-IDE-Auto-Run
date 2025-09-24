# -*- coding: utf-8 -*-
"""
全局窗口DPI自动适配器

目标：
- 为应用中新创建的每个顶层窗口自动挂载 QtDpiManager 的窗口适配器，
  在跨屏或DPI变化时根据一致外观比例(r = 当前屏缩放/基准屏缩放)对像素单位属性进行缩放。

设计原则：
- 非侵入：不修改字体点值（点值随DPI自动缩放已由主题/Qt控制），只调整像素型尺寸（图标、行高、间距）。
- 安全回退：异常静默，尽量不影响原有行为。
- 性能：通过定时扫描新顶层窗口（500ms）+ 已适配集合去重，避免高频处理。
"""

from __future__ import annotations
from typing import Optional, Set


def default_on_ratio_changed(window, ratio: float):
    """默认像素单位自适应回调：对常见控件进行按比例缩放。

    提示：
    - 字体采用pt，已随DPI自动缩放，此处不做处理；
    - 仅调整像素单位属性，尽量避免布局抖动。
    """
    try:
        from PySide6 import QtWidgets, QtCore
        from auto_approve.qt_dpi_manager import QtDpiManager
        app = QtWidgets.QApplication.instance()
        if app is None:
            return

        # 获取全局DPI管理器（通过在应用对象上挂载的引用）
        dpi_mgr: Optional[QtDpiManager] = getattr(app, '_aiide_dpi_manager', None)
        if dpi_mgr is None:
            # 找不到管理器则不处理
            return

        def S(px: int) -> int:
            # 使用管理器的scale_px确保和一致外观比例同步
            return dpi_mgr.scale_px(px, window)

        # 1) QAbstractItemView 族：图标大小与行高
        for view in window.findChildren(QtWidgets.QAbstractItemView):
            try:
                # 图标尺寸：若当前为(0,0)或过小则按基线16像素缩放
                icon_size = view.iconSize()
                base_icon = 16
                target = S(max(icon_size.width(), base_icon))
                view.setIconSize(QtCore.QSize(target, target))
            except Exception:
                pass
            try:
                # 行高：表格/树/列表给一个温和默认值
                base_row = 22
                row = S(base_row)
                if hasattr(view, 'setGridSize') and view.viewMode() == getattr(QtWidgets.QListView, 'IconMode', 1):
                    # IconMode 给出格子尺寸
                    view.setGridSize(QtCore.QSize(row * 2, row * 2))
                if hasattr(view, 'verticalHeader') and view.verticalHeader():
                    view.verticalHeader().setDefaultSectionSize(row)
                if hasattr(view, 'setSpacing'):
                    view.setSpacing(max(0, S(4)))
            except Exception:
                pass

        # 2) QToolBar/QToolButton/QPushButton：图标尺寸
        for tb in window.findChildren(QtWidgets.QToolBar):
            try:
                base_icon = max(16, tb.iconSize().width())
                isz = S(base_icon)
                tb.setIconSize(QtCore.QSize(isz, isz))
            except Exception:
                pass
        for btn_cls in (QtWidgets.QToolButton, QtWidgets.QPushButton):
            for btn in window.findChildren(btn_cls):
                try:
                    if hasattr(btn, 'icon') and not btn.icon().isNull():
                        base_icon = max(16, btn.iconSize().width())
                        isz = S(base_icon)
                        btn.setIconSize(QtCore.QSize(isz, isz))
                    # 轻量调整按钮最小高度，避免过扁
                    mh = max(btn.minimumHeight(), S(24))
                    if mh > 0:
                        btn.setMinimumHeight(mh)
                except Exception:
                    pass

        # 3) QTabBar：图标尺寸与最小高度
        for tabbar in window.findChildren(QtWidgets.QTabBar):
            try:
                base_icon = max(16, tabbar.iconSize().width())
                isz = S(base_icon)
                tabbar.setIconSize(QtCore.QSize(isz, isz))
                tabbar.setMinimumHeight(S(28))
            except Exception:
                pass

        # 4) 统一边距/间距的小幅度提升（对顶层布局）
        try:
            lw = window.layout()
            if lw is not None:
                m = max(4, S(8))
                s = max(2, S(4))
                lw.setContentsMargins(m, m, m, m)
                lw.setSpacing(s)
        except Exception:
            pass

        # 5) 局部样式补丁（仅作用于该窗口树），解决QSS中固定像素导致的跨屏不一致
        try:
            base_ss = window.property('aiide_base_stylesheet')
            if base_ss is None:
                base_ss = window.styleSheet() or ''
                window.setProperty('aiide_base_stylesheet', base_ss)

            # 依据项目默认QSS中的关键像素参数给出缩放版片段
            ss_patch = f"""
            /* --- aiide dpi patch begin --- */
            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
              min-height: {S(24)}px;
              padding: {S(6)}px {S(12)}px;
            }}
            QComboBox::drop-down {{
              width: {S(20)}px;
            }}
            QCheckBox::indicator {{
              width: {S(18)}px; height: {S(18)}px;
            }}
            QSplitter::handle {{
              width: {S(2)}px; height: {S(2)}px;
            }}
            QScrollBar:vertical {{ width: {S(12)}px; }}
            QScrollBar::handle:vertical {{ min-height: {S(20)}px; margin: {S(2)}px; }}
            QScrollBar:horizontal {{ height: {S(12)}px; }}
            QScrollBar::handle:horizontal {{ min-width: {S(20)}px; margin: {S(2)}px; }}
            QSlider::groove:horizontal {{ height: {S(6)}px; border-radius: {S(3)}px; }}
            QSlider::handle:horizontal {{ width: {S(16)}px; height: {S(16)}px; margin: -{S(5)}px 0; border-radius: {S(8)}px; }}
            /* --- aiide dpi patch end --- */
            """

            last_ratio = window.property('aiide_dpi_ratio_applied') or 0.0
            if abs(float(last_ratio) - float(ratio)) > 1e-3:
                window.setStyleSheet(base_ss + "\n" + ss_patch)
                window.setProperty('aiide_dpi_ratio_applied', ratio)
        except Exception:
            pass
    except Exception:
        # 全局兜底
        pass


class GlobalDpiAdapter:
    """全局DPI适配器：自动为新顶层窗口挂载一致外观适配器。"""

    def __init__(self, app, dpi_manager, on_ratio_changed=None, scan_interval_ms: int = 500):
        from PySide6 import QtCore
        self._app = app
        self._mgr = dpi_manager
        self._cb = on_ratio_changed or default_on_ratio_changed
        self._seen: Set[int] = set()
        self._timer = QtCore.QTimer()
        self._timer.setInterval(scan_interval_ms)
        self._timer.timeout.connect(self._scan)
        self._timer.start()

        # 将管理器挂到app，便于默认回调获取
        setattr(self._app, '_aiide_dpi_manager', dpi_manager)

        # 立即执行一次扫描
        self._scan()

    def stop(self):
        try:
            self._timer.stop()
        except Exception:
            pass

    def _scan(self):
        from PySide6 import QtWidgets, QtCore
        try:
            for w in self._app.topLevelWidgets():
                # 排除纯弹出类（如QMenu）避免频繁调整
                if isinstance(w, QtWidgets.QMenu):
                    continue
                if (w.windowFlags() & QtCore.Qt.Popup) == QtCore.Qt.Popup:
                    continue
                oid = int(w.winId()) if hasattr(w, 'winId') else id(w)
                if oid in self._seen:
                    continue
                self._seen.add(oid)
                # 挂载窗口适配器
                try:
                    self._mgr.attach_window_adapter(w, self._cb)
                except Exception:
                    pass
        except Exception:
            pass

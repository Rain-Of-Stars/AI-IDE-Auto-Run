# -*- coding: utf-8 -*-
"""
设置对话框：允许用户配置模板路径、阈值、扫描间隔、ROI、显示器索引、冷却时间、
灰度/多尺度/缩放倍率、点击偏移、最少命中帧、启动即扫描与日志开关，并保存到 JSON。
"""
from __future__ import annotations
import os
import shutil
import hashlib
from typing import Tuple, List

from capture.monitor_utils import get_all_monitors_info
from PySide6 import QtWidgets, QtCore, QtGui

from auto_approve.config_manager import AppConfig, ROI, save_config, load_config
from auto_approve.path_utils import get_app_base_dir
from auto_approve.app_state import get_app_state
from auto_approve.ui_enhancements import enhance_widget, UIEnhancementManager
from auto_approve.logger_manager import get_logger


class CustomCheckBox(QtWidgets.QCheckBox):
    """自定义复选框，使用代码绘制白色✓符号，不依赖图标资源文件。"""
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        
    def paintEvent(self, event):
        """重写绘制事件，自定义绘制选中状态的白色✓符号。"""
        # 先调用父类的绘制方法绘制基础样式
        super().paintEvent(event)
        
        # 如果选中状态，绘制白色✓符号
        if self.isChecked():
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            
            # 获取指示器的矩形区域
            option = QtWidgets.QStyleOptionButton()
            self.initStyleOption(option)
            indicator_rect = self.style().subElementRect(
                QtWidgets.QStyle.SE_CheckBoxIndicator, option, self
            )
            
            # 设置白色画笔绘制✓符号
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap, QtCore.Qt.RoundJoin))
            
            # 计算✓符号的坐标
            center_x = indicator_rect.center().x()
            center_y = indicator_rect.center().y()
            size = min(indicator_rect.width(), indicator_rect.height()) * 0.6
            
            # 绘制✓符号的两条线段
            # 第一条线段：从左下到中心
            x1 = center_x - size * 0.3
            y1 = center_y + size * 0.1
            x2 = center_x - size * 0.1
            y2 = center_y + size * 0.3
            painter.drawLine(QtCore.QPointF(x1, y1), QtCore.QPointF(x2, y2))
            
            # 第二条线段：从中心到右上
            x3 = center_x + size * 0.4
            y3 = center_y - size * 0.2
            painter.drawLine(QtCore.QPointF(x2, y2), QtCore.QPointF(x3, y3))
            
            painter.end()


class PlusMinusSpinBox(QtWidgets.QSpinBox):
    """带"+/-"按钮的SpinBox：
    - 隐藏系统默认上下按钮，叠加两个QToolButton来执行 stepUp/stepDown；
    - 通过右侧内边距与自适应布局，保证点击区域足够大，解决"点击不到"。
    - 彻底禁用滚轮事件，防止鼠标滚轮卡住。
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        # 隐藏默认的上下箭头按钮
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        # 给输入区右侧留出空间
        self.setStyleSheet("QAbstractSpinBox{ padding-right: 30px; }")
        # 禁用滚轮事件响应
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        # 安装事件过滤器来彻底阻止滚轮事件
        self.installEventFilter(self)
        # 关键：设置属性来禁用滚轮
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)

        # 上/下两个工具按钮
        self._btn_plus = QtWidgets.QToolButton(self)
        self._btn_plus.setText("+")
        self._btn_plus.setCursor(QtCore.Qt.PointingHandCursor)
        self._btn_plus.setAutoRepeat(True)
        self._btn_plus.setAutoRepeatDelay(250)
        self._btn_plus.setAutoRepeatInterval(60)
        self._btn_plus.clicked.connect(self.stepUp)

        self._btn_minus = QtWidgets.QToolButton(self)
        self._btn_minus.setText("-")
        self._btn_minus.setCursor(QtCore.Qt.PointingHandCursor)
        self._btn_minus.setAutoRepeat(True)
        self._btn_minus.setAutoRepeatDelay(250)
        self._btn_minus.setAutoRepeatInterval(60)
        self._btn_minus.clicked.connect(self.stepDown)

        # 统一按钮样式（与整体暗色风格一致）
        btn_style = (
            "QToolButton { background-color: #3C3F44; border: 1px solid #4A4D52;"
            " border-radius: 4px; padding: 0px; color: #E0E0E0; }"
            "QToolButton:hover { background-color: #4A4D52; border-color: #5A5D62; }"
            "QToolButton:pressed { background-color: #2F80ED; border: 1px solid #4A9EFF; color: white; }"
            "QToolButton:disabled { background-color: #2B2D31; border: 1px solid #3C3F44; color: #666; }"
        )
        self._btn_plus.setStyleSheet(btn_style)
        self._btn_minus.setStyleSheet(btn_style)

        # 工具按钮不抢占焦点，便于键盘输入
        self._btn_plus.setFocusPolicy(QtCore.Qt.NoFocus)
        self._btn_minus.setFocusPolicy(QtCore.Qt.NoFocus)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """彻底禁用鼠标滚轮事件，避免任何系统开销和事件传递"""
        # 完全忽略滚轮事件，不调用基类实现
        # 设置事件为已忽略，防止事件继续传播
        event.ignore()
        return

    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:
        super().resizeEvent(e)
        # 动态定位两个按钮到右侧，垂直上下排列
        w = 24  # 按钮宽度，稍微减小避免遮挡
        total_height = self.height() - 4  # 总可用高度，留出上下边距
        h = max(14, total_height // 2)  # 单个按钮高度
        x = self.width() - w - 2  # X位置，增加右边距
        y_offset = 2  # 顶部偏移
        
        # 确保按钮不会超出控件边界
        if total_height < 28:  # 如果高度太小，调整按钮大小
            h = max(12, total_height // 2)
        
        self._btn_plus.setGeometry(x, y_offset, w, h)
        self._btn_minus.setGeometry(x, y_offset + h, w, total_height - h)

    def eventFilter(self, obj, event):
        """事件过滤器：彻底阻止滚轮事件"""
        if event.type() == QtCore.QEvent.Type.Wheel:
            # 完全阻止滚轮事件
            event.ignore()
            return True
        return super().eventFilter(obj, event)


class PlusMinusDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    """带"+/-"按钮的DoubleSpinBox，彻底禁用滚轮事件，逻辑同上。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setStyleSheet("QAbstractSpinBox{ padding-right: 30px; }")
        # 禁用滚轮事件响应
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        # 安装事件过滤器来彻底阻止滚轮事件
        self.installEventFilter(self)
        # 关键：设置属性来禁用滚轮
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)

        self._btn_plus = QtWidgets.QToolButton(self)
        self._btn_plus.setText("+")
        self._btn_plus.setCursor(QtCore.Qt.PointingHandCursor)
        self._btn_plus.setAutoRepeat(True)
        self._btn_plus.setAutoRepeatDelay(250)
        self._btn_plus.setAutoRepeatInterval(60)
        self._btn_plus.clicked.connect(self.stepUp)

        self._btn_minus = QtWidgets.QToolButton(self)
        self._btn_minus.setText("-")
        self._btn_minus.setCursor(QtCore.Qt.PointingHandCursor)
        self._btn_minus.setAutoRepeat(True)
        self._btn_minus.setAutoRepeatDelay(250)
        self._btn_minus.setAutoRepeatInterval(60)
        self._btn_minus.clicked.connect(self.stepDown)

        btn_style = (
            "QToolButton { background-color: #3C3F44; border: 1px solid #4A4D52;"
            " border-radius: 4px; padding: 0px; color: #E0E0E0; }"
            "QToolButton:hover { background-color: #4A4D52; border-color: #5A5D62; }"
            "QToolButton:pressed { background-color: #2F80ED; border: 1px solid #4A9EFF; color: white; }"
            "QToolButton:disabled { background-color: #2B2D31; border: 1px solid #3C3F44; color: #666; }"
        )
        self._btn_plus.setStyleSheet(btn_style)
        self._btn_minus.setStyleSheet(btn_style)

        self._btn_plus.setFocusPolicy(QtCore.Qt.NoFocus)
        self._btn_minus.setFocusPolicy(QtCore.Qt.NoFocus)

    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """彻底禁用鼠标滚轮事件，避免任何系统开销和事件传递"""
        # 完全忽略滚轮事件，不调用基类实现
        # 设置事件为已忽略，防止事件继续传播
        event.ignore()
        return

    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:
        super().resizeEvent(e)
        # 动态定位两个按钮到右侧，垂直上下排列
        w = 24  # 按钮宽度，稍微减小避免遮挡
        total_height = self.height() - 4  # 总可用高度，留出上下边距
        h = max(14, total_height // 2)  # 单个按钮高度
        x = self.width() - w - 2  # X位置，增加右边距
        y_offset = 2  # 顶部偏移
        
        # 确保按钮不会超出控件边界
        if total_height < 28:  # 如果高度太小，调整按钮大小
            h = max(12, total_height // 2)
        
        self._btn_plus.setGeometry(x, y_offset, w, h)
        self._btn_minus.setGeometry(x, y_offset + h, w, total_height - h)

    def eventFilter(self, obj, event):
        """事件过滤器：彻底阻止滚轮事件"""
        if event.type() == QtCore.QEvent.Type.Wheel:
            # 完全阻止滚轮事件
            event.ignore()
            return True
        return super().eventFilter(obj, event)

class ImagePreviewDialog(QtWidgets.QDialog):
    """简单的图片预览对话框，随窗口大小自适应缩放。"""
    def __init__(self, pixmap: QtGui.QPixmap, path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"预览 - {os.path.basename(path)}")
        self.resize(720, 540)
        self._pixmap = pixmap
        self._label = QtWidgets.QLabel()
        self._label.setAlignment(QtCore.Qt.AlignCenter)
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.addWidget(self._label, 1)
        self._update_view()

    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:
        super().resizeEvent(e)
        self._update_view()

    def _update_view(self):
        if self._pixmap.isNull():
            self._label.setText("无法加载图片")
            return
        scaled = self._pixmap.scaled(self._label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self._label.setPixmap(scaled)


class NoWheelComboBox(QtWidgets.QComboBox):
    """自定义下拉框，彻底禁用鼠标滚轮事件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        # 安装事件过滤器来彻底阻止滚轮事件
        self.installEventFilter(self)
    
    def wheelEvent(self, event: QtGui.QWheelEvent) -> None:
        """重写滚轮事件，完全禁用鼠标滚轮"""
        # 完全忽略滚轮事件，不调用基类实现
        event.ignore()
        return
    
    def eventFilter(self, obj, event):
        """事件过滤器：彻底阻止滚轮事件"""
        if event.type() == QtCore.QEvent.Type.Wheel:
            # 完全阻止滚轮事件
            event.ignore()
            return True
        return super().eventFilter(obj, event)


class NoFocusDelegate(QtWidgets.QStyledItemDelegate):
    """去除项视图(如QTreeWidget/QListWidget)的虚线焦点框委托。

    原理：在绘制前清除`State_HasFocus`标志，交由默认样式绘制，从而仅保留
    选中高亮(背景色/前景色)，不再绘制灰色虚线框。
    """
    def paint(self, painter: QtGui.QPainter, option: QtWidgets.QStyleOptionViewItem, index: QtCore.QModelIndex) -> None:
        # 复制一份绘制参数，避免修改传入的option对象
        opt = QtWidgets.QStyleOptionViewItem(option)
        # 兼容不同PySide6枚举命名：优先使用StateFlag，否则回退旧常量名
        try:
            flag = QtWidgets.QStyle.StateFlag.State_HasFocus
        except AttributeError:
            flag = QtWidgets.QStyle.State_HasFocus
        # 清除焦点状态位，避免绘制虚线框
        opt.state &= ~flag
        super().paint(painter, opt, index)

class ScreenshotPreviewDialog(QtWidgets.QDialog):
    """截图确认预览对话框：显示图片，并提供保存/取消按钮。

    设计要点：
    - 仅负责展示与返回用户意图，不直接负责文件保存；
    - 保存按钮对象名设为primary，匹配现有QSS主按钮样式；
    - 预览区自适应窗口尺寸，平滑缩放。
    - 支持WGC测试模式，显示保存和确定两个按钮。
    """
    def __init__(self, pixmap: QtGui.QPixmap, parent=None, is_wgc_test=False):
        super().__init__(parent)
        self.setWindowTitle("截图预览")
        self.resize(820, 580)
        self._pixmap = pixmap
        self.is_wgc_test = is_wgc_test

        # 预览标签
        self._label = QtWidgets.QLabel()
        self._label.setAlignment(QtCore.Qt.AlignCenter)

        # 底部按钮：根据模式显示不同按钮
        if is_wgc_test:
            # WGC测试模式：显示保存和确定按钮
            self.btn_save = QtWidgets.QPushButton("保存")
            self.btn_save.setObjectName("primary")  # 使用样式表中的主按钮配色
            self.btn_ok = QtWidgets.QPushButton("确定")
            self.btn_save.clicked.connect(self.accept)  # 保存并关闭
            self.btn_ok.clicked.connect(self.reject)    # 仅关闭，不保存
        else:
            # 普通模式：显示保存/取消按钮
            self.btn_save = QtWidgets.QPushButton("保存")
            self.btn_save.setObjectName("primary")  # 使用样式表中的主按钮配色
            self.btn_cancel = QtWidgets.QPushButton("取消")
            self.btn_save.clicked.connect(self.accept)
            self.btn_cancel.clicked.connect(self.reject)

        # 布局
        v = QtWidgets.QVBoxLayout(self)
        v.setContentsMargins(8, 8, 8, 8)
        v.addWidget(self._label, 1)
        h = QtWidgets.QHBoxLayout()
        h.addStretch(1)
        h.addWidget(self.btn_save)
        if is_wgc_test:
            h.addWidget(self.btn_ok)
        else:
            h.addWidget(self.btn_cancel)
        v.addLayout(h)

        self._update_view()

    def resizeEvent(self, e: QtGui.QResizeEvent) -> None:
        super().resizeEvent(e)
        self._update_view()

    def _update_view(self):
        """更新预览图显示，按保持比例缩放到标签尺寸。"""
        if self._pixmap.isNull():
            self._label.setText("无法加载图片")
            return
        scaled = self._pixmap.scaled(self._label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
        self._label.setPixmap(scaled)

class RegionSnipDialog(QtWidgets.QDialog):
    """全屏截图取框对话框：左键拖拽选择；右键或Esc取消。

    关键增强：
    - 跟随鼠标所在屏幕：在未拖拽时，鼠标移到哪个屏幕，取框覆盖就切到哪个屏幕；
    - 高DPI安全：按截图像素比进行区域拷贝，避免缩放误差。
    """
    def __init__(self, screen: QtGui.QScreen, background: QtGui.QPixmap, parent=None):
        super().__init__(parent)
        # 使用无边框置顶窗口，启用窗口级透明背景，以系统真实桌面为背景。
        # 这样可避免预抓屏幕图在混合DPI下的错位，选区所见即所得。
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Dialog | QtCore.Qt.WindowStaysOnTopHint)
        self.setWindowModality(QtCore.Qt.ApplicationModal)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        # 对话框关闭后立即销毁，避免定时器等异步回调导致重新显示
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self._screen = screen  # 当前覆盖的屏幕
        self._origin = None
        self._current = None
        self.selected_pixmap: QtGui.QPixmap | None = None
        # 关闭标志：accept/reject后置为True，所有异步流程应尽快退出
        self._closing: bool = False
        # 绑定到当前屏幕并匹配几何
        self._apply_screen(screen)
        self.setGeometry(screen.geometry())
        self._hint_font = self.font()
        self._hint_font.setPointSize(self._hint_font.pointSize() + 1)

        # 拖拽标志：按下左键开始，释放后结束
        self._dragging: bool = False

        # 鼠标屏幕跟随定时器：未拖拽时根据鼠标位置切换覆盖屏幕
        self._cursor_timer = QtCore.QTimer(self)
        self._cursor_timer.setInterval(80)  # 80ms足够流畅
        self._cursor_timer.timeout.connect(self._follow_cursor_screen)
        self._cursor_timer.start()

    # ---------- 生命周期与关闭控制 ----------
    def _shutdown_timer(self):
        """安全停止内部定时器（多次调用无副作用）。"""
        try:
            if hasattr(self, "_cursor_timer") and self._cursor_timer is not None:
                self._cursor_timer.stop()
                try:
                    self._cursor_timer.timeout.disconnect(self._follow_cursor_screen)
                except Exception:
                    pass
        except Exception:
            pass

    def accept(self) -> None:
        """确认选择：停止定时器并隐藏窗口，避免覆盖层残留。"""
        self._dragging = False
        self._closing = True
        self._shutdown_timer()
        # 先隐藏，防止定时器尾调用触发 _switch_to_screen 把窗口又显示出来
        try:
            # 降级去顶置，避免极端情况下的置顶残留
            self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, False)
            self.setWindowOpacity(0.0)
            self.show()  # 应用窗口标志变更
            self.hide()
        except Exception:
            pass
        # 立即刷新事件队列，尽快让系统移除窗口
        try:
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
        except Exception:
            pass
        super().accept()

    def reject(self) -> None:
        """取消：同样停止定时器并隐藏窗口。"""
        self._dragging = False
        self._closing = True
        self._shutdown_timer()
        try:
            self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, False)
            self.setWindowOpacity(0.0)
            self.show()
            self.hide()
        except Exception:
            pass
        try:
            QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
        except Exception:
            pass
        super().reject()

    def closeEvent(self, e: QtGui.QCloseEvent) -> None:
        """关闭事件：兜底停止定时器。"""
        self._closing = True
        self._shutdown_timer()
        super().closeEvent(e)

    def _apply_screen(self, screen: QtGui.QScreen):
        """将窗口绑定到指定屏幕（用于跨屏与DPI调整）。"""
        try:
            handle = self.windowHandle()
            if handle is not None and screen is not None:
                handle.setScreen(screen)
        except Exception:
            pass

    def _switch_to_screen(self, screen: QtGui.QScreen):
        """切换覆盖到指定屏幕：更新窗口几何与背景截图，并重置选择状态。"""
        # 若窗口已不可见（例如刚刚 accept/reject 关闭），避免被再次显示
        if self._closing or not self.isVisible():
            return
        if screen is None or screen is self._screen:
            return
        self._screen = screen
        # 切换屏幕后重置选择，避免坐标空间混淆
        self._origin = None
        self._current = None
        self._apply_screen(self._screen)
        self.setGeometry(self._screen.geometry())
        # 仅在可见状态下刷新前置，避免在关闭过程中被重新显示
        if not self._closing and self.isVisible():
            try:
                self.raise_(); self.activateWindow(); self.show()
            except Exception:
                pass
        self.update()

    def _follow_cursor_screen(self):
        """定时检查鼠标所在屏幕并切换覆盖，拖拽中不切屏。"""
        # 窗口不可见或正在拖拽时不做任何切换
        if self._closing or not self.isVisible() or self._dragging:
            return
        pos = QtGui.QCursor.pos()
        scr = QtGui.QGuiApplication.screenAt(pos)
        # 兼容回退：若screenAt返回None，手动根据geometry判断
        if scr is None:
            for s in QtGui.QGuiApplication.screens():
                if s.geometry().contains(pos):
                    scr = s
                    break
        if scr is not None and scr is not self._screen:
            self._switch_to_screen(scr)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """绘制半透明遮罩，选区内部完全透明以直透桌面。"""
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        # 覆盖整屏半透明蒙版
        p.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 96))
        if self._origin and self._current:
            rect = QtCore.QRect(self._origin, self._current).normalized()
            # 清除选区为透明，仅保留“挖洞”效果；不绘制任何边框
            p.setCompositionMode(QtGui.QPainter.CompositionMode_Clear)
            p.fillRect(rect, QtCore.Qt.transparent)
            # 恢复正常模式但不再绘制边框或文字
            p.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)
        p.end()

    def mousePressEvent(self, e: QtGui.QMouseEvent) -> None:
        if e.button() == QtCore.Qt.LeftButton:
            self._dragging = True
            self._origin = e.pos()
            self._current = e.pos()
            self.update()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent) -> None:
        if self._origin:
            self._current = e.pos()
            self.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent) -> None:
        if e.button() == QtCore.Qt.LeftButton and self._origin and self._current:
            rect = QtCore.QRect(self._origin, self._current).normalized()
            if rect.width() > 2 and rect.height() > 2:
                # 实时抓取当前屏幕并按DPR裁切，确保跨屏与混合DPI准确
                shot = self._screen.grabWindow(0)
                dpr = shot.devicePixelRatio() or self._screen.devicePixelRatio()
                src = QtCore.QRect(int(rect.x() * dpr), int(rect.y() * dpr), int(rect.width() * dpr), int(rect.height() * dpr))
                self.selected_pixmap = shot.copy(src)
            # 先结束拖拽，再accept，减少与定时器的竞态
            self._dragging = False
            self.accept()
        elif e.button() == QtCore.Qt.RightButton:
            self.reject()
        # 任意释放都结束拖拽
        self._dragging = False

    def keyPressEvent(self, e: QtGui.QKeyEvent) -> None:
        if e.key() == QtCore.Qt.Key_Escape:
            self.reject()
            self._dragging = False

def _parse_pair(text: str, typ=float) -> Tuple:
    """解析形如 "a,b" 的文本为二元组，允许空格。"""
    parts = [p.strip() for p in text.replace("；", ",").split(",") if p.strip()]
    if len(parts) != 2:
        raise ValueError("请输入两个以逗号分隔的数值")
    return typ(parts[0]), typ(parts[1])


def _parse_scales(text: str) -> Tuple[float, ...]:
    """解析倍率列表，如 "1.0,1.25,0.8"。"""
    parts = [p.strip() for p in text.replace("；", ",").split(",") if p.strip()]
    vals = []
    for p in parts:
        vals.append(float(p))
    if not vals:
        vals = [1.0]
    return tuple(vals)


class SettingsDialog(QtWidgets.QDialog):
    """设置窗口对话框。

    变更说明：
    - 新增`saved`信号：点击“保存”时写入配置文件并发出该信号，但不关闭对话框；
      便于外部（托盘）实时应用新配置，同时保持设置窗口不退出。
    """
    # 对外通知“已保存”的信号（携带新配置对象），不触发关闭
    saved = QtCore.Signal(object)
    def __init__(self, parent=None):
        super().__init__(parent)
        # 初始化logger
        self._logger = get_logger()
        # 窗口参数
        self.setWindowTitle("AI-IDE-Auto-Run - 设置")
        self.setModal(True)
        self.resize(860, 560)
        self.setMinimumSize(760, 520)
        
        # 设置整体对话框样式
        self.setStyleSheet("""
            QDialog {
                background-color: #2B2D31;
                color: #E0E0E0;
            }
            QGroupBox {
                background-color: #32343A;
                border: 1px solid #3C3F44;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
                font-weight: 500;
                color: #E0E0E0;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                background-color: #32343A;
                color: #4A9EFF;
                font-weight: 600;
            }
            QLabel {
                color: #E0E0E0;
                background: transparent;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #3C3F44;
                border: 1px solid #4A4D52;
                border-radius: 4px;
                padding: 4px 8px;
                color: #E0E0E0;
                min-height: 18px;
            }
            QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #2F80ED;
            }
            QCheckBox {
                color: #E0E0E0;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #4A4D52;
                border-radius: 3px;
                background-color: #3C3F44;
            }
            QCheckBox::indicator:checked {
                background-color: #2F80ED;
                border: 1px solid #4A9EFF;
            }
            QTableWidget {
                background-color: #32343A;
                border: 1px solid #3C3F44;
                border-radius: 6px;
                gridline-color: #3C3F44;
                color: #E0E0E0;
            }
            QHeaderView::section {
                background-color: #3C3F44;
                border: 1px solid #4A4D52;
                padding: 6px;
                color: #E0E0E0;
                font-weight: 500;
            }
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #32343A;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #4A4D52;
                border-radius: 6px;
                min-height: 20px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5A5D62;
            }
            QScrollBar::handle:vertical:pressed {
                background-color: #2F80ED;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                background-color: #32343A;
                height: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background-color: #4A4D52;
                border-radius: 6px;
                min-width: 20px;
                margin: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #5A5D62;
            }
            QScrollBar::handle:horizontal:pressed {
                background-color: #2F80ED;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                background: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)

        # 载入配置
        self.cfg = load_config()
        # 初始化捕获测试相关状态，防止重复连接与多次弹窗
        # _capture_test_manager 使用全局单例时，必须在每次连接前断开旧连接
        self._capture_test_manager = None
        # 进度对话框对象引用，便于跨槽函数关闭
        self._progress_dialog = None
        # 每次测试只允许弹出一次结果预览对话框
        self._result_dialog_shown = False
        # 记录是否已建立与全局测试管理器的信号连接，避免对未连接的信号执行disconnect导致告警
        self._capture_signals_connected = False

        # ============ 初始化控件（不立刻布局，后续分组放入页面）============
        # 模板列表（支持多图）
        self.list_templates = QtWidgets.QListWidget()
        # 为模板列表设置更明显的选中高亮（蓝底白字）
        self.list_templates.setObjectName("tplList")
        self.list_templates.setStyleSheet(
            """
            #tplList {
                background-color: #2B2D31;
                border: 1px solid #3C3F44;
                border-radius: 8px;
                padding: 6px;
                selection-background-color: #2F80ED;
                selection-color: white;
            }
            #tplList::item {
                padding: 10px 12px;
                margin: 3px 2px;
                border-radius: 6px;
                background-color: #32343A;
                border: 1px solid #3C3F44;
                color: #E0E0E0;
            }
            #tplList::item:selected { 
                background-color: #2F80ED; 
                color: white;
                border: 1px solid #4A9EFF;
                font-weight: 500;
            }
            #tplList::item:selected:active { 
                background-color: #2F80ED; 
                color: white;
                border: 1px solid #4A9EFF;
            }
            #tplList::item:selected:!active { 
                background-color: #2F80ED; 
                color: white;
                border: 1px solid #4A9EFF;
            }
            #tplList::item:hover { 
                background-color: rgba(47,128,237,0.15);
                border: 1px solid rgba(47,128,237,0.5);
                color: white;
            }
            """
        )
        self.list_templates.setAlternatingRowColors(True)
        self.list_templates.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        # 纵向滚动：禁用横向滚动并启用文本换行
        self.list_templates.setWordWrap(True)
        self.list_templates.setTextElideMode(QtCore.Qt.ElideNone)
        self.list_templates.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.list_templates.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.list_templates.setVerticalScrollMode(QtWidgets.QAbstractItemView.ScrollPerPixel)
        self.list_templates.setResizeMode(QtWidgets.QListView.Adjust)
        self.list_templates.setUniformItemSizes(False)
        # 去除列表项的虚线焦点框，仅保留高亮
        self.list_templates.setItemDelegate(NoFocusDelegate(self.list_templates))
        init_paths: List[str] = []
        if getattr(self.cfg, "template_paths", None):
            init_paths = list(self.cfg.template_paths)
        elif getattr(self.cfg, "template_path", None):
            if self.cfg.template_path:
                init_paths = [self.cfg.template_path]
        for p in init_paths:
            self.list_templates.addItem(p)
        self.btn_add_tpl = QtWidgets.QPushButton("添加图片…")
        self.btn_preview_tpl = QtWidgets.QPushButton("预览")
        self.btn_capture_tpl = QtWidgets.QPushButton("截图添加")
        self.btn_del_tpl = QtWidgets.QPushButton("删除选中")
        self.btn_clear_tpl = QtWidgets.QPushButton("清空列表")
        
        # 为按钮设置统一的现代化样式
        button_style = """
            QPushButton {
                background-color: #3C3F44;
                border: 1px solid #4A4D52;
                border-radius: 6px;
                padding: 8px 16px;
                color: #E0E0E0;
                font-weight: 500;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #4A4D52;
                border: 1px solid #5A5D62;
            }
            QPushButton:pressed {
                background-color: #2F80ED;
                border: 1px solid #4A9EFF;
                color: white;
            }
            QPushButton:disabled {
                background-color: #2B2D31;
                border: 1px solid #3C3F44;
                color: #666;
            }
        """
        
        for btn in [self.btn_add_tpl, self.btn_preview_tpl, self.btn_capture_tpl, 
                   self.btn_del_tpl, self.btn_clear_tpl]:
            btn.setStyleSheet(button_style)

        # 基本与性能
        self.sb_monitor = PlusMinusSpinBox(); self.sb_monitor.setRange(1, 16); self.sb_monitor.setValue(self.cfg.monitor_index + 1); self.sb_monitor.setToolTip("显示器索引，1为主屏（索引0）")
        
        # 屏幕列表表格
        self.screen_table = QtWidgets.QTableWidget()
        self.screen_table.setColumnCount(6)
        self.screen_table.setHorizontalHeaderLabels([
            "屏幕编号", "分辨率", "位置 (X, Y)", "尺寸 (宽×高)", "是否主屏", "状态"
        ])
        self.screen_table.setAlternatingRowColors(True)
        self.screen_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.screen_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.screen_table.setMaximumHeight(200)
        self.screen_table.setShowGrid(True)
        self.screen_table.setGridStyle(QtCore.Qt.SolidLine)
        
        # 设置列宽 - 更合理的分配
        header = self.screen_table.horizontalHeader()
        header.setDefaultAlignment(QtCore.Qt.AlignCenter)  # 表头居中对齐
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Fixed)
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.Stretch)  # 状态列自适应
        
        self.screen_table.setColumnWidth(0, 70)   # 屏幕编号 - 稍微缩小
        self.screen_table.setColumnWidth(1, 110)  # 分辨率 - 稍微缩小
        self.screen_table.setColumnWidth(2, 110)  # 位置 - 稍微缩小
        self.screen_table.setColumnWidth(3, 110)  # 尺寸 - 稍微缩小
        self.screen_table.setColumnWidth(4, 75)   # 是否主屏 - 稍微缩小
        
        # 设置垂直表头
        vertical_header = self.screen_table.verticalHeader()
        vertical_header.setDefaultSectionSize(28)  # 行高
        vertical_header.setVisible(False)  # 隐藏行号
        
        # 去除表格项的虚线焦点框
        self.screen_table.setItemDelegate(NoFocusDelegate(self.screen_table))
        
        # 屏幕信息标签
        self.screen_info_label = QtWidgets.QLabel()
        self.screen_info_label.setStyleSheet("color: #666; font-size: 12px;")
        
        # 刷新按钮
        self.btn_refresh_screens = QtWidgets.QPushButton("刷新屏幕列表")
        self.btn_refresh_screens.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_BrowserReload))
        self.sb_interval = PlusMinusSpinBox(); self.sb_interval.setRange(100, 10000); self.sb_interval.setSingleStep(50); self.sb_interval.setSuffix(" ms"); self.sb_interval.setValue(self.cfg.interval_ms); self.sb_interval.setToolTip("扫描间隔越大越省电")
        self.sb_min_det = PlusMinusSpinBox(); self.sb_min_det.setRange(1, 10); self.sb_min_det.setValue(self.cfg.min_detections)
        self.cb_auto_start = CustomCheckBox("启动后自动开始扫描"); self.cb_auto_start.setChecked(self.cfg.auto_start_scan)
        self.cb_logging = CustomCheckBox("启用日志到 log.txt"); self.cb_logging.setChecked(self.cfg.enable_logging)
        # 新增：通知开关（_on_save中会读取）
        self.cb_notifications = CustomCheckBox("启用托盘通知"); self.cb_notifications.setChecked(self.cfg.enable_notifications)
        # 绑定全局状态中心，确保与托盘实时同步
        self.state = get_app_state()
        # 以全局状态为准刷新初值（避免托盘侧已变更而本地仍显示旧状态）
        try:
            self.cb_logging.setChecked(self.state.enable_logging)
        except Exception:
            pass
        # 建立双向同步：UI -> 状态（立即持久化并广播）；状态 -> UI（仅刷新显示，避免环路）
        try:
            self.cb_logging.toggled.connect(self._on_ui_logging_toggled)
            self.state.loggingChanged.connect(self._on_app_state_logging_changed)
        except Exception:
            pass

        # 匹配参数
        self.ds_threshold = PlusMinusDoubleSpinBox(); self.ds_threshold.setRange(0.00, 1.00); self.ds_threshold.setSingleStep(0.01); self.ds_threshold.setDecimals(2); self.ds_threshold.setValue(self.cfg.threshold); self.ds_threshold.setToolTip("越大越严格，建议0.85~0.95")
        self.ds_cooldown = PlusMinusDoubleSpinBox(); self.ds_cooldown.setRange(0.0, 60.0); self.ds_cooldown.setSingleStep(0.5); self.ds_cooldown.setSuffix(" s"); self.ds_cooldown.setValue(self.cfg.cooldown_s); self.ds_cooldown.setToolTip("命中后冷却避免重复点击")
        self.cb_gray = CustomCheckBox("灰度匹配（更省电）"); self.cb_gray.setChecked(self.cfg.grayscale)
        self.cb_multiscale = CustomCheckBox("多尺度匹配"); self.cb_multiscale.setChecked(self.cfg.multi_scale)
        self.le_scales = QtWidgets.QLineEdit(",".join(f"{v:g}" for v in self.cfg.scales))
        self.le_scales.setPlaceholderText("示例：1.0,1.25,0.8（仅多尺度开启时生效）")
        self.le_scales.setToolTip("倍率列表按顺序尝试，建议包含1.0")

        # 点击与坐标
        self.le_offset = QtWidgets.QLineEdit(f"{self.cfg.click_offset[0]},{self.cfg.click_offset[1]}")
        self.le_offset.setPlaceholderText("示例：0,0 或 10,-6")
        self.le_offset.setToolTip("相对命中点的像素偏移，支持负数")
        self.cb_verify_window = CustomCheckBox("点击前验证窗口"); self.cb_verify_window.setChecked(self.cfg.verify_window_before_click)
        self.cb_coord_correction = CustomCheckBox("启用坐标校正"); self.cb_coord_correction.setChecked(self.cfg.enable_coordinate_correction)
        self.le_coord_offset = QtWidgets.QLineEdit(f"{self.cfg.coordinate_offset[0]},{self.cfg.coordinate_offset[1]}"); self.le_coord_offset.setPlaceholderText("示例：0,0")
        self.le_coord_offset.setToolTip("多屏校正时的全局坐标偏移")
        self.combo_click_method = NoWheelComboBox(); self.combo_click_method.addItems(["message", "simulate"]); self.combo_click_method.setCurrentText(self.cfg.click_method)
        self.combo_transform_mode = NoWheelComboBox(); self.combo_transform_mode.addItems(["auto", "manual", "disabled"]); self.combo_transform_mode.setCurrentText(self.cfg.coordinate_transform_mode)

        # 多屏幕
        self.cb_multi_screen_polling = CustomCheckBox("启用多屏幕轮询搜索"); self.cb_multi_screen_polling.setChecked(self.cfg.enable_multi_screen_polling)
        self.cb_multi_screen_polling.setToolTip("在所有屏幕上轮询搜索目标，适用于多屏幕环境")
        self.sb_polling_interval = PlusMinusSpinBox(); self.sb_polling_interval.setRange(500, 5000); self.sb_polling_interval.setSingleStep(100); self.sb_polling_interval.setSuffix(" ms"); self.sb_polling_interval.setValue(self.cfg.screen_polling_interval_ms)

        # ROI 编辑
        self.sb_roi_x = PlusMinusSpinBox(); self.sb_roi_x.setRange(0, 99999); self.sb_roi_x.setValue(self.cfg.roi.x)
        self.sb_roi_y = PlusMinusSpinBox(); self.sb_roi_y.setRange(0, 99999); self.sb_roi_y.setValue(self.cfg.roi.y)
        self.sb_roi_w = PlusMinusSpinBox(); self.sb_roi_w.setRange(0, 99999); self.sb_roi_w.setValue(self.cfg.roi.w)
        self.sb_roi_h = PlusMinusSpinBox(); self.sb_roi_h.setRange(0, 99999); self.sb_roi_h.setValue(self.cfg.roi.h)
        self.btn_roi_reset = QtWidgets.QPushButton("重置为整屏")

        # 调试
        self.cb_debug = CustomCheckBox("启用调试模式"); self.cb_debug.setChecked(self.cfg.debug_mode)
        self.cb_save_debug = CustomCheckBox("保存调试截图"); self.cb_save_debug.setChecked(self.cfg.save_debug_images)
        self.le_debug_dir = QtWidgets.QLineEdit(self.cfg.debug_image_dir)
        self.cb_enhanced_finding = CustomCheckBox("增强窗口查找"); self.cb_enhanced_finding.setChecked(self.cfg.enhanced_window_finding)

        # —— WGC 捕获模式选择
        self.combo_capture_backend = NoWheelComboBox()
        self.combo_capture_backend.addItem("窗口捕获", "window")
        self.combo_capture_backend.addItem("显示器捕获", "monitor")
        # 设置当前值，根据 use_monitor 字段确定模式
        use_monitor = getattr(self.cfg, 'use_monitor', False)
        _cur_backend = 'monitor' if use_monitor else 'window'
        # 兼容旧配置：检查 capture_backend 字段
        old_backend = getattr(self.cfg, 'capture_backend', 'window')
        if old_backend in ['screen', 'auto']:
            _cur_backend = 'monitor'
        elif old_backend == 'monitor':
            _cur_backend = 'monitor'
        _idx = self.combo_capture_backend.findData(_cur_backend)
        if _idx >= 0:
            self.combo_capture_backend.setCurrentIndex(_idx)
        self.combo_capture_backend.setToolTip("选择WGC捕获模式：窗口捕获或显示器捕获")
        self.sb_target_hwnd = PlusMinusSpinBox(); self.sb_target_hwnd.setRange(0, 2_147_483_647); self.sb_target_hwnd.setValue(getattr(self.cfg, 'target_hwnd', 0))
        # 窗口标题检测功能已移除，只保留基于进程的检测
        # 新增：进程匹配输入与选项
        self.le_process = QtWidgets.QLineEdit(getattr(self.cfg, 'target_process', "")); self.le_process.setPlaceholderText("例如: Code.exe 或 进程完整路径")
        self.cb_process_partial = CustomCheckBox("允许部分匹配进程"); self.cb_process_partial.setChecked(getattr(self.cfg, 'process_partial_match', True))
        self.sb_fps_max = PlusMinusSpinBox(); self.sb_fps_max.setRange(1, 60); self.sb_fps_max.setValue(getattr(self.cfg, 'fps_max', 30)); self.sb_fps_max.setSuffix(" FPS")
        self.sb_capture_timeout = PlusMinusSpinBox(); self.sb_capture_timeout.setRange(500, 60000); self.sb_capture_timeout.setValue(getattr(self.cfg, 'capture_timeout_ms', 5000)); self.sb_capture_timeout.setSuffix(" ms")
        self.cb_restore_minimized = CustomCheckBox("恢复最小化窗口（不激活）"); self.cb_restore_minimized.setChecked(getattr(self.cfg, 'restore_minimized_noactivate', True))
        self.cb_restore_after_capture = CustomCheckBox("抓帧后重新最小化"); self.cb_restore_after_capture.setChecked(getattr(self.cfg, 'restore_minimized_after_capture', False))
        self.cb_electron_optimization = CustomCheckBox("Electron/Chromium优化提示"); self.cb_electron_optimization.setChecked(getattr(self.cfg, 'enable_electron_optimization', True))

        # 新增：WGC专用配置
        self.cb_include_cursor = CustomCheckBox("包含鼠标光标"); self.cb_include_cursor.setChecked(getattr(self.cfg, 'include_cursor', False))
        self.cb_border_window = CustomCheckBox("窗口边框"); self.cb_border_window.setChecked(getattr(self.cfg, 'window_border_required', False))
        self.cb_border_screen = CustomCheckBox("屏幕边框"); self.cb_border_screen.setChecked(getattr(self.cfg, 'screen_border_required', False))
        
        # 自动窗口更新配置
        self.cb_auto_update_hwnd = CustomCheckBox("启用自动更新HWND"); self.cb_auto_update_hwnd.setChecked(getattr(self.cfg, 'auto_update_hwnd_by_process', False))
        self.sb_auto_update_interval = PlusMinusSpinBox(); self.sb_auto_update_interval.setRange(1000, 60000); self.sb_auto_update_interval.setValue(getattr(self.cfg, 'auto_update_hwnd_interval_ms', 5000)); self.sb_auto_update_interval.setSuffix(" ms")

        # 按钮
        self.btn_find_process = QtWidgets.QPushButton("按进程查找")
        self.btn_hwnd_picker = QtWidgets.QPushButton("窗口选择器")
        self.btn_test_capture = QtWidgets.QPushButton("测试捕获")
        self.btn_preview_capture = QtWidgets.QPushButton("预览窗口")

        # ============ 右侧堆叠页面容器与各页面 ============
        # 说明：此前缺失 self.stack 与各 page_* 的定义，导致 NameError。
        # 此处补充所有页面并与左侧导航索引保持一致。

        # 堆叠容器
        self.stack = QtWidgets.QStackedWidget()

        # 0) 模板与启动
        page_general_tpl = QtWidgets.QWidget()
        v_tpl = QtWidgets.QVBoxLayout(page_general_tpl)
        v_tpl.setContentsMargins(0, 0, 0, 0)
        v_tpl.addWidget(self.list_templates, 1)
        hb_tpl_btn = QtWidgets.QHBoxLayout()
        hb_tpl_btn.addWidget(self.btn_add_tpl)
        hb_tpl_btn.addWidget(self.btn_preview_tpl)
        hb_tpl_btn.addWidget(self.btn_capture_tpl)
        hb_tpl_btn.addWidget(self.btn_del_tpl)
        hb_tpl_btn.addWidget(self.btn_clear_tpl)
        hb_tpl_btn.addStretch(1)
        v_tpl.addLayout(hb_tpl_btn)
        # 启动相关
        v_tpl.addSpacing(8)
        v_tpl.addWidget(self.cb_auto_start)

        # 1) 扫描与性能
        page_general_misc = QtWidgets.QWidget()
        form_misc = QtWidgets.QFormLayout(page_general_misc)
        form_misc.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        form_misc.setHorizontalSpacing(12)
        form_misc.setVerticalSpacing(8)
        form_misc.addRow("扫描间隔", self.sb_interval)
        form_misc.addRow("最少命中帧", self.sb_min_det)

        # 2) 显示器设置
        page_display = QtWidgets.QWidget()
        v_disp = QtWidgets.QVBoxLayout(page_display)
        v_disp.setContentsMargins(0, 0, 0, 0)
        form_disp_top = QtWidgets.QFormLayout()
        form_disp_top.setHorizontalSpacing(12)
        form_disp_top.setVerticalSpacing(8)
        form_disp_top.addRow("显示器索引", self.sb_monitor)
        v_disp.addLayout(form_disp_top)
        v_disp.addWidget(self.screen_table)
        hb_disp_actions = QtWidgets.QHBoxLayout()
        hb_disp_actions.addWidget(self.btn_refresh_screens)
        hb_disp_actions.addStretch(1)
        v_disp.addLayout(hb_disp_actions)
        v_disp.addWidget(self.screen_info_label)
        # 多屏幕轮询参数放到显示器页
        form_disp_extra = QtWidgets.QFormLayout()
        form_disp_extra.setHorizontalSpacing(12)
        form_disp_extra.setVerticalSpacing(6)
        form_disp_extra.addRow(self.cb_multi_screen_polling)
        form_disp_extra.addRow("轮询间隔", self.sb_polling_interval)
        v_disp.addLayout(form_disp_extra)

        # 3) 日志
        page_log = QtWidgets.QWidget()
        v_log = QtWidgets.QVBoxLayout(page_log)
        v_log.setContentsMargins(0, 0, 0, 0)
        v_log.addWidget(self.cb_logging)
        v_log.addStretch(1)

        # 4) 通知
        page_notify = QtWidgets.QWidget()
        v_notify = QtWidgets.QVBoxLayout(page_notify)
        v_notify.setContentsMargins(0, 0, 0, 0)
        v_notify.addWidget(self.cb_notifications)
        v_notify.addStretch(1)

        # 5) 匹配参数
        page_match = QtWidgets.QWidget()
        form_match = QtWidgets.QFormLayout(page_match)
        form_match.setHorizontalSpacing(12)
        form_match.setVerticalSpacing(8)
        form_match.addRow("阈值", self.ds_threshold)
        form_match.addRow("冷却时间", self.ds_cooldown)
        form_match.addRow(self.cb_gray)
        form_match.addRow(self.cb_multiscale)
        form_match.addRow("尺度列表", self.le_scales)

        # 6) 点击与坐标
        page_click = QtWidgets.QWidget()
        form_click = QtWidgets.QFormLayout(page_click)
        form_click.setHorizontalSpacing(12)
        form_click.setVerticalSpacing(8)
        form_click.addRow("点击偏移", self.le_offset)
        form_click.addRow(self.cb_verify_window)
        form_click.addRow(self.cb_coord_correction)
        form_click.addRow("坐标偏移", self.le_coord_offset)
        form_click.addRow("点击方法", self.combo_click_method)
        form_click.addRow("坐标模式", self.combo_transform_mode)

        # 7) ROI 区域
        page_roi = QtWidgets.QWidget()
        form_roi = QtWidgets.QFormLayout(page_roi)
        form_roi.setHorizontalSpacing(12)
        form_roi.setVerticalSpacing(8)
        form_roi.addRow("X", self.sb_roi_x)
        form_roi.addRow("Y", self.sb_roi_y)
        form_roi.addRow("宽", self.sb_roi_w)
        form_roi.addRow("高", self.sb_roi_h)
        form_roi.addRow(self.btn_roi_reset)

        # 8) 调试与输出
        page_debug = QtWidgets.QWidget()
        form_dbg = QtWidgets.QFormLayout(page_debug)
        form_dbg.setHorizontalSpacing(12)
        form_dbg.setVerticalSpacing(8)
        form_dbg.addRow(self.cb_debug)
        form_dbg.addRow(self.cb_save_debug)
        form_dbg.addRow("调试目录", self.le_debug_dir)
        form_dbg.addRow(self.cb_enhanced_finding)

        # 创建WGC页面和滚动区域
        page_wgc = QtWidgets.QWidget()
        scroll_area_wgc = QtWidgets.QScrollArea()
        scroll_area_wgc.setWidgetResizable(True)
        scroll_area_wgc.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        # 创建WGC内容容器
        wgc_content = QtWidgets.QWidget()
        
        # WGC页面主布局
        wgc_main_layout = QtWidgets.QVBoxLayout(wgc_content)
        wgc_main_layout.setContentsMargins(16, 16, 16, 16)
        wgc_main_layout.setSpacing(16)
        
        # ========== 基础配置组 ==========
        group_basic = QtWidgets.QGroupBox("基础配置")
        group_basic.setStyleSheet("""
            QGroupBox {
                background-color: #32343A;
                border: 1px solid #4A4D52;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 8px;
                font-weight: 600;
                color: #4A9EFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px 0 8px;
                background-color: #32343A;
                color: #4A9EFF;
                font-weight: 600;
            }
        """)
        
        form_basic = QtWidgets.QFormLayout(group_basic)
        form_basic.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        form_basic.setHorizontalSpacing(12)
        form_basic.setVerticalSpacing(10)
        form_basic.addRow("捕获模式", self.combo_capture_backend)
        form_basic.addRow("目标窗口HWND", self.sb_target_hwnd)
        form_basic.addRow("目标进程", self.le_process)
        form_basic.addRow(self.cb_process_partial)
        
        # ========== 窗口查找工具组 ==========
        group_tools = QtWidgets.QGroupBox("窗口查找工具")
        group_tools.setStyleSheet(group_basic.styleSheet())
        
        layout_tools = QtWidgets.QGridLayout(group_tools)
        layout_tools.setContentsMargins(12, 20, 12, 12)
        layout_tools.setSpacing(10)
        
        # 工具按钮布局 - 2x2网格
        layout_tools.addWidget(self.btn_find_process, 0, 0)
        layout_tools.addWidget(self.btn_hwnd_picker, 0, 1)
        layout_tools.addWidget(self.btn_test_capture, 1, 0)
        layout_tools.addWidget(self.btn_preview_capture, 1, 1)
        
        # ========== 性能配置组 ==========
        group_performance = QtWidgets.QGroupBox("性能配置")
        group_performance.setStyleSheet(group_basic.styleSheet())
        
        form_performance = QtWidgets.QFormLayout(group_performance)
        form_performance.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        form_performance.setHorizontalSpacing(12)
        form_performance.setVerticalSpacing(10)
        form_performance.addRow("最大帧率", self.sb_fps_max)
        form_performance.addRow("捕获超时", self.sb_capture_timeout)
        
        # ========== 捕获选项组 ==========
        group_capture = QtWidgets.QGroupBox("捕获选项")
        group_capture.setStyleSheet(group_basic.styleSheet())
        
        layout_capture = QtWidgets.QVBoxLayout(group_capture)
        layout_capture.setContentsMargins(12, 20, 12, 12)
        layout_capture.setSpacing(8)
        
        # 复选框垂直排列
        layout_capture.addWidget(self.cb_include_cursor)
        layout_capture.addWidget(self.cb_border_window)
        layout_capture.addWidget(self.cb_border_screen)
        layout_capture.addWidget(self.cb_restore_minimized)
        layout_capture.addWidget(self.cb_restore_after_capture)
        layout_capture.addWidget(self.cb_electron_optimization)
        
        # ========== 自动更新配置组 ==========
        group_auto = QtWidgets.QGroupBox("自动更新配置")
        group_auto.setStyleSheet(group_basic.styleSheet())
        
        form_auto = QtWidgets.QFormLayout(group_auto)
        form_auto.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        form_auto.setHorizontalSpacing(12)
        form_auto.setVerticalSpacing(10)
        form_auto.addRow(self.cb_auto_update_hwnd)
        form_auto.addRow("更新间隔(ms)", self.sb_auto_update_interval)
        
        # 将所有组添加到主布局
        wgc_main_layout.addWidget(group_basic)
        wgc_main_layout.addWidget(group_tools)
        wgc_main_layout.addWidget(group_performance)
        wgc_main_layout.addWidget(group_capture)
        wgc_main_layout.addWidget(group_auto)
        wgc_main_layout.addStretch(1)  # 弹性空间填充
        
        # 将内容容器设置到滚动区域
        scroll_area_wgc.setWidget(wgc_content)

        # 为page_wgc设置布局，包含滚动区域
        wgc_layout = QtWidgets.QVBoxLayout(page_wgc)
        wgc_layout.setContentsMargins(0, 0, 0, 0)
        wgc_layout.addWidget(scroll_area_wgc)
        
        # 为工具按钮统一样式，使其更美观
        tool_button_style = """
            QPushButton {
                background-color: #3C3F44;
                border: 1px solid #4A4D52;
                border-radius: 6px;
                padding: 10px 16px;
                color: #E0E0E0;
                font-weight: 500;
                min-height: 24px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #4A4D52;
                border: 1px solid #5A5D62;
            }
            QPushButton:pressed {
                background-color: #2F80ED;
                border: 1px solid #4A9EFF;
                color: white;
            }
            QPushButton:disabled {
                background-color: #2B2D31;
                border: 1px solid #3C3F44;
                color: #666;
            }
        """
        
        # 应用工具按钮样式
        for btn in [self.btn_find_process, self.btn_hwnd_picker, self.btn_test_capture, 
                   self.btn_preview_capture]:
            btn.setStyleSheet(tool_button_style)
            btn.setMinimumWidth(120)  # 统一按钮宽度

        pages = [
            page_general_tpl,    # 0
            page_general_misc,   # 1 扫描与性能
            page_display,        # 2 显示器设置
            page_log,            # 3 日志
            page_notify,         # 4 通知
            page_match,          # 5
            page_click,          # 6
            page_roi,            # 7
            page_debug,          # 8
            page_wgc             # 9 窗口捕获
        ]
        for p in pages:
            self.stack.addWidget(p)

        # ============ 左侧多级菜单（QTreeWidget）============
        self.nav = QtWidgets.QTreeWidget()
        # 提升左侧导航的选中可见度（与列表保持一致的蓝色系）
        self.nav.setObjectName("navTree")
        self.nav.setStyleSheet(
            """
            #navTree {
                padding: 8px;
                border-radius: 8px;
                background-color: #2B2D31;
            }
            #navTree::item {
                padding: 8px 12px;
                margin: 1px 0px;
                border: none;
            }
            #navTree::item:selected { 
                background-color: #2F80ED; 
                color: white; 
                font-weight: 500;
            }
            #navTree::item:selected:active { 
                background-color: #2F80ED; 
                color: white; 
            }
            #navTree::item:selected:!active { 
                background-color: #2F80ED; 
                color: white; 
            }
            #navTree::item:hover { 
                background-color: rgba(47,128,237,0.15); 
            }
            #navTree::branch {
                margin: 1px;
            }
            """
        )
        # 去除导航项的虚线焦点框，仅保留高亮
        self.nav.setItemDelegate(NoFocusDelegate(self.nav))
        self.nav.setHeaderHidden(True)
        self.nav.setMaximumWidth(220)  # 稍微减小宽度
        self.nav.setMinimumWidth(200)  # 设置最小宽度
        self.nav.setIndentation(16)    # 设置缩进距离

        # 顶级：常规
        it_general = QtWidgets.QTreeWidgetItem(["常规"])
        it_general_tpl = QtWidgets.QTreeWidgetItem(["模板与启动"])
        it_general_tpl.setData(0, QtCore.Qt.ItemDataRole.UserRole, 0)
        # 将原“日志与显示器”拆分为四项：扫描与性能、显示器设置、日志、通知
        it_general_misc = QtWidgets.QTreeWidgetItem(["扫描与性能"])  # index 1
        it_general_misc.setData(0, QtCore.Qt.ItemDataRole.UserRole, 1)
        it_general_display = QtWidgets.QTreeWidgetItem(["显示器设置"])  # index 2
        it_general_display.setData(0, QtCore.Qt.ItemDataRole.UserRole, 2)
        it_general_log = QtWidgets.QTreeWidgetItem(["日志"])  # index 3
        it_general_log.setData(0, QtCore.Qt.ItemDataRole.UserRole, 3)
        it_general_notify = QtWidgets.QTreeWidgetItem(["通知"])  # index 4
        it_general_notify.setData(0, QtCore.Qt.ItemDataRole.UserRole, 4)
        it_general.addChildren([it_general_tpl, it_general_misc, it_general_display, it_general_log, it_general_notify])

        # 顶级：匹配
        it_match = QtWidgets.QTreeWidgetItem(["匹配"])
        it_match_param = QtWidgets.QTreeWidgetItem(["参数与尺度"])
        it_match_param.setData(0, QtCore.Qt.ItemDataRole.UserRole, 5)
        it_match.addChild(it_match_param)

        # 顶级：点击
        it_click = QtWidgets.QTreeWidgetItem(["点击"])
        it_click_main = QtWidgets.QTreeWidgetItem(["点击与坐标"])
        it_click_main.setData(0, QtCore.Qt.ItemDataRole.UserRole, 6)
        it_click.addChild(it_click_main)

        # 顶级：区域
        it_roi = QtWidgets.QTreeWidgetItem(["区域"])
        it_roi_page = QtWidgets.QTreeWidgetItem(["ROI 区域"])
        it_roi_page.setData(0, QtCore.Qt.ItemDataRole.UserRole, 7)
        it_roi.addChild(it_roi_page)

        # 顶级：调试
        it_debug = QtWidgets.QTreeWidgetItem(["调试"])
        it_debug_page = QtWidgets.QTreeWidgetItem(["调试与输出"])
        it_debug_page.setData(0, QtCore.Qt.ItemDataRole.UserRole, 8)  # 更新索引为8
        it_debug.addChild(it_debug_page)

        # 顶级：窗口捕获
        it_wgc = QtWidgets.QTreeWidgetItem(["窗口捕获"])
        it_wgc_page = QtWidgets.QTreeWidgetItem(["WGC配置"])
        it_wgc_page.setData(0, QtCore.Qt.ItemDataRole.UserRole, 9)
        it_wgc.addChild(it_wgc_page)

        self.nav.addTopLevelItems([it_general, it_match, it_click, it_roi, it_debug, it_wgc])
        self.nav.expandAll()

        # ============ 总体布局（左右分栏 + 底部按钮）============
        splitter = QtWidgets.QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self.nav)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 0)  # 左侧导航不拉伸
        splitter.setStretchFactor(1, 1)  # 右侧内容区域拉伸
        # 设置分割器的初始比例，左侧占用固定宽度
        splitter.setSizes([220, 600])  # 左侧220px，右侧600px（会自动调整）
        splitter.setHandleWidth(2)      # 设置分割条宽度

        v = QtWidgets.QVBoxLayout(self)
        v.addWidget(splitter, 1)

        # 底部按钮区
        self.btn_ok = QtWidgets.QPushButton("保存")
        self.btn_ok.setObjectName("primary")
        self.btn_cancel = QtWidgets.QPushButton("取消")
        hb = QtWidgets.QHBoxLayout()
        hb.setSpacing(8)  # 设置按钮间距
        hb.setContentsMargins(16, 12, 16, 12)  # 设置布局边距
        hb.addStretch(1)
        hb.addWidget(self.btn_ok)
        hb.addWidget(self.btn_cancel)
        v.addLayout(hb)

        # 信号连接
        self.btn_add_tpl.clicked.connect(self._on_add_templates)
        self.btn_preview_tpl.clicked.connect(self._on_preview_template)
        self.btn_capture_tpl.clicked.connect(self._on_screenshot_add_template)
        self.btn_del_tpl.clicked.connect(self._on_remove_selected)
        self.btn_clear_tpl.clicked.connect(self._on_clear_templates)
        self.btn_roi_reset.clicked.connect(self._on_roi_reset)
        self.btn_refresh_screens.clicked.connect(self._on_refresh_screens)
        self.screen_table.itemSelectionChanged.connect(self._on_screen_selection_changed)
        self.btn_ok.clicked.connect(self._on_save)
        self.btn_cancel.clicked.connect(self.reject)
        self.nav.currentItemChanged.connect(self._on_nav_changed)
        # 窗口标题查找功能已移除
        self.btn_find_process.clicked.connect(self._on_find_window_by_process)
        self.btn_hwnd_picker.clicked.connect(self._on_open_hwnd_picker)
        self.btn_test_capture.clicked.connect(self._on_test_capture)
        self.btn_preview_capture.clicked.connect(self._on_preview_window_capture)

        # 列表项双击直接预览：提升操作便捷性
        # 使用 itemDoubleClicked 以获取被双击的具体项，避免多选时歧义
        self.list_templates.itemDoubleClicked.connect(self._on_preview_template_by_item)
        
        # 初始化屏幕信息
        self._load_screen_info()

        # 默认选择第一个子项
        self.nav.setCurrentItem(it_general_tpl)

        # 应用UI增强效果
        self._apply_ui_enhancements()

    def _apply_ui_enhancements(self):
        """应用UI增强效果"""
        try:
            # 为整个对话框应用窗口效果
            UIEnhancementManager.apply_window_effects(self)

            # 为主要按钮添加悬停效果
            for btn in [self.btn_ok, self.btn_cancel, self.btn_add_tpl,
                       self.btn_preview_tpl, self.btn_capture_tpl]:
                if hasattr(self, btn.objectName()) and btn:
                    UIEnhancementManager.apply_button_hover_effect(btn)

            # 为对话框添加淡入动画
            UIEnhancementManager.apply_fade_in_animation(self, 400)

            # 为导航树添加阴影效果
            UIEnhancementManager.apply_shadow_effect(self.nav, 8, (2, 2))

            # 为主要内容区域添加阴影效果
            UIEnhancementManager.apply_shadow_effect(self.stack, 6, (1, 1))

        except Exception as e:
            # 如果UI增强失败，不影响基本功能
            print(f"UI增强效果应用失败: {e}")

    # ---------- 交互逻辑 ----------

    def _on_add_templates(self):
        """添加一个或多个模板图片到列表。
        
        改进：将选择的图片复制到 assets/images 目录，并使用相对路径添加到列表中。
        """
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "选择模板图片", os.getcwd(), "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not paths:
            return
        
        # 确保 assets/images 目录存在
        images_abs, images_rel = self._ensure_assets_images_dir()
        
        # 避免重复添加
        existing = set(self._get_template_paths())
        
        for p in paths:
            if not p:
                continue
                
            # 首先检查是否已经存在相同内容的文件
            duplicate_filename = self._find_duplicate_file_by_content(p, images_abs)
            if duplicate_filename:
                # 文件内容已存在，使用现有文件的相对路径
                rel_path = os.path.join(images_rel, duplicate_filename)
                if rel_path not in existing:
                    self.list_templates.addItem(rel_path)
                    existing.add(rel_path)
                    QtWidgets.QMessageBox.information(
                        self, "文件已存在", 
                        f"检测到相同内容的文件已存在：\n{duplicate_filename}\n\n已添加到模板列表，无需重复复制。"
                    )
                else:
                    QtWidgets.QMessageBox.information(
                        self, "文件已存在", 
                        f"相同内容的文件已存在且已在模板列表中：\n{duplicate_filename}"
                    )
                continue
                
            # 生成目标文件名（保持原始文件名，如果重复则添加计数器）
            original_name = os.path.basename(p)
            name, ext = os.path.splitext(original_name)
            target_name = original_name
            target_abs_path = os.path.join(images_abs, target_name)
            
            # 如果文件名已存在，添加计数器避免冲突
            counter = 1
            while os.path.exists(target_abs_path):
                target_name = f"{name}_{counter}{ext}"
                target_abs_path = os.path.join(images_abs, target_name)
                counter += 1
            
            try:
                # 复制文件到 assets/images 目录
                shutil.copy2(p, target_abs_path)
                
                # 使用相对路径添加到列表
                rel_path = os.path.join(images_rel, target_name)
                if rel_path not in existing:
                    self.list_templates.addItem(rel_path)
                    existing.add(rel_path)
                    
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "复制失败", f"无法复制文件到 assets/images 目录：\n{str(e)}"
                )

    def _on_remove_selected(self):
        """删除选中的模板路径。"""
        for item in self.list_templates.selectedItems():
            row = self.list_templates.row(item)
            self.list_templates.takeItem(row)

    def _on_clear_templates(self):
        """清空模板列表。"""
        self.list_templates.clear()

    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件的MD5哈希值。
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件的MD5哈希值字符串
        """
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return ""
    
    def _find_duplicate_file_by_content(self, source_file: str, target_dir: str) -> str:
        """在目标目录中查找与源文件内容相同的文件。
        
        Args:
            source_file: 源文件路径
            target_dir: 目标目录路径
            
        Returns:
            如果找到重复文件，返回重复文件的文件名；否则返回空字符串
        """
        if not os.path.exists(source_file) or not os.path.exists(target_dir):
            return ""
            
        source_hash = self._calculate_file_hash(source_file)
        if not source_hash:
            return ""
            
        # 遍历目标目录中的所有文件
        for filename in os.listdir(target_dir):
            file_path = os.path.join(target_dir, filename)
            if os.path.isfile(file_path):
                if self._calculate_file_hash(file_path) == source_hash:
                    return filename
                    
        return ""
    
    def _ensure_assets_images_dir(self) -> Tuple[str, str]:
        """确保 assets/images 目录存在，返回(绝对路径, 相对路径)。
        
        变更：基于应用基准目录（exe或主脚本目录）创建与保存，
        避免打包运行时落到临时解包目录。
        """
        proj_root = get_app_base_dir()
        images_abs = os.path.join(proj_root, "assets", "images")
        images_rel = os.path.join("assets", "images")
        os.makedirs(images_abs, exist_ok=True)
        return images_abs, images_rel

    def _resolve_template_path(self, p: str) -> str:
        """解析模板条目的真实绝对路径。"""
        p = (p or "").strip()
        if not p:
            return ""
        if os.path.isabs(p) and os.path.exists(p):
            return p
        
        # 获取项目根目录
        proj_root = get_app_base_dir()
        
        # 优先尝试项目根相对路径
        proj_path = os.path.join(proj_root, p)
        if os.path.exists(proj_path):
            return proj_path
            
        # 项目根下的 assets/images
        images_abs, _ = self._ensure_assets_images_dir()
        candidate = os.path.join(images_abs, os.path.basename(p))
        if os.path.exists(candidate):
            return candidate
            
        # 最后尝试工作目录相对路径（兼容性）
        wd_path = os.path.abspath(os.path.join(os.getcwd(), p))
        if os.path.exists(wd_path):
            return wd_path
            
        return p

    def _on_preview_template(self):
        """预览当前选中的模板图片。"""
        item = self.list_templates.selectedItems()[0] if self.list_templates.selectedItems() else self.list_templates.currentItem()
        if not item:
            QtWidgets.QMessageBox.information(self, "提示", "请先在列表中选择一张图片")
            return
        self._preview_path_from_item(item)

    def _on_preview_template_by_item(self, item: QtWidgets.QListWidgetItem):
        """响应列表项双击事件，直接预览对应图片。

        参数
        - item: 被双击的 `QListWidgetItem` 对象
        """
        if not item:
            return
        self._preview_path_from_item(item)

    def _preview_path_from_item(self, item: QtWidgets.QListWidgetItem):
        """从列表项中解析路径并打开预览对话框。"""
        path = self._resolve_template_path(item.text())
        pm = QtGui.QPixmap(path)
        if pm.isNull():
            QtWidgets.QMessageBox.warning(self, "无法预览", f"图片无法打开：\n{path}")
            return
        ImagePreviewDialog(pm, path, self).exec()

    def _on_screenshot_add_template(self):
        """截图并在预览窗口中让用户决定是否保存为模板。

        改动说明：
        - 屏幕选择策略：优先使用鼠标所在屏幕，其次回退到“显示器索引”。
        - 截图完成后弹出“截图预览”对话框，提供“保存/取消”。
        - 用户点击保存时，统一保存为PNG到项目的 assets/images，并加入模板列表。
        """
        screens = QtGui.QGuiApplication.screens()
        if not screens:
            QtWidgets.QMessageBox.warning(self, "截图失败", "未检测到屏幕")
            return

        # 1) 优先根据鼠标位置选择屏幕；若不可用，回退到索引选择
        cursor_pos = QtGui.QCursor.pos()
        screen = QtGui.QGuiApplication.screenAt(cursor_pos)
        if screen is None:
            # 从“显示器索引”(1-based)选择屏幕（与旧行为兼容）
            idx = max(1, min(self.sb_monitor.value(), len(screens))) - 1
            screen = screens[idx]

        # 2) 截取目标屏幕全屏背景，启动区域取框
        bg = screen.grabWindow(0)
        snip = RegionSnipDialog(screen, bg, self)
        if snip.exec() != QtWidgets.QDialog.Accepted or not snip.selected_pixmap or snip.selected_pixmap.isNull():
            return

        # 3) 弹出确认预览，用户决定是否保存
        confirm = ScreenshotPreviewDialog(snip.selected_pixmap, self)
        if confirm.exec() != QtWidgets.QDialog.Accepted:
            # 用户取消，不保存
            return

        # 4) 保存PNG到 assets/images 下，并加入列表
        images_abs, images_rel = self._ensure_assets_images_dir()
        fname = f"template_{QtCore.QDateTime.currentDateTime().toString('yyyyMMdd_HHmmss_zzz')}.png"
        abs_path = os.path.join(images_abs, fname)
        snip.selected_pixmap.save(abs_path, "PNG")
        rel_path = os.path.join(images_rel, fname)
        # 去重添加并选中新增项
        existing = {self.list_templates.item(i).text().strip() for i in range(self.list_templates.count())}
        if rel_path not in existing:
            self.list_templates.addItem(rel_path)
        # 将焦点移动到新增项，便于用户确认
        for i in range(self.list_templates.count()-1, -1, -1):
            if self.list_templates.item(i).text().strip() == rel_path:
                self.list_templates.setCurrentRow(i)
                break
        
        # 5) 立即将新模板加载到内存模板管理器中，避免需要重启软件
        try:
            from utils.memory_template_manager import get_template_manager
            template_manager = get_template_manager()
            # 强制重新加载新保存的模板
            loaded_count = template_manager.load_templates([abs_path], force_reload=True)
            if loaded_count > 0:
                self._logger.info(f"新模板已立即加载到内存缓存: {rel_path}")
            else:
                self._logger.warning(f"新模板加载到内存缓存失败: {rel_path}")
        except Exception as e:
            self._logger.error(f"加载新模板到内存缓存时发生异常: {e}")
        
        QtWidgets.QMessageBox.information(self, "成功", f"模板图片已创建并加载到内存：\n{rel_path}")

        # 6) 立即保存配置并广播，让扫描器进程/线程立刻应用新模板
        # 说明：
        # - _on_save 会构造 AppConfig（含最新的模板列表）、发出 saved 信号，并进行异步持久化；
        # - 主程序监听 saved 信号后，会通过 GUI 响应管理器下发“配置更新”，触发扫描器重载模板；
        # - 这样可实现“截图→保存”后立即生效与点击新增模板的需求。
        try:
            self._on_save()
        except Exception as e:
            # 保存失败不影响已添加的模板条目，提醒用户可手动点击“保存”按钮
            self._logger.warning(f"截图后自动保存配置失败: {e}")

    def _get_template_paths(self) -> List[str]:
        """读取列表中的所有模板路径。"""
        paths: List[str] = []
        for i in range(self.list_templates.count()):
            txt = self.list_templates.item(i).text().strip()
            if txt:
                paths.append(txt)
        return paths

    def _on_roi_reset(self):
        self.sb_roi_x.setValue(0)
        self.sb_roi_y.setValue(0)
        self.sb_roi_w.setValue(0)
        self.sb_roi_h.setValue(0)

    def _load_screen_info(self):
        """加载屏幕信息到表格中"""
        try:
            # 使用新的WGC后端获取显示器信息
            monitors = get_all_monitors_info()

            # 清空表格
            self.screen_table.setRowCount(0)

            # 添加屏幕信息
            for i, monitor in enumerate(monitors):
                row = self.screen_table.rowCount()
                self.screen_table.insertRow(row)

                # 屏幕编号（从0开始）
                self.screen_table.setItem(row, 0, QtWidgets.QTableWidgetItem(str(i)))

                # 分辨率
                width = monitor['width']
                height = monitor['height']
                resolution = f"{width}×{height}"
                self.screen_table.setItem(row, 1, QtWidgets.QTableWidgetItem(resolution))

                # 位置
                left = monitor['left']
                top = monitor['top']
                position = f"({left}, {top})"
                self.screen_table.setItem(row, 2, QtWidgets.QTableWidgetItem(position))
                
                # 尺寸
                size = f"{width}×{height}"
                self.screen_table.setItem(row, 3, QtWidgets.QTableWidgetItem(size))
                
                # 是否主屏
                is_primary = "是" if monitor.get('is_primary', False) else "否"
                self.screen_table.setItem(row, 4, QtWidgets.QTableWidgetItem(is_primary))
                
                # 状态
                status = "活动"
                self.screen_table.setItem(row, 5, QtWidgets.QTableWidgetItem(status))
            
            # 更新信息标签并验证显示器索引
            total_screens = len(monitors)
            if total_screens > 0:
                total_width = sum(m['width'] for m in monitors)
                total_height = max(m['height'] for m in monitors)

                # 验证当前配置的显示器索引
                current_monitor_index = self.cfg.monitor_index
                if current_monitor_index >= total_screens:
                    warning_text = f"⚠️ 当前显示器索引 {current_monitor_index} 无效！"
                    self.screen_info_label.setText(
                        f"共检测到 {total_screens} 个屏幕 | {warning_text}"
                    )
                    self.screen_info_label.setStyleSheet("color: #FF6B6B; font-weight: bold;")
                else:
                    self.screen_info_label.setText(
                        f"共检测到 {total_screens} 个屏幕，总桌面尺寸: {total_width}×{total_height} 像素"
                    )
                    self.screen_info_label.setStyleSheet("color: #666; font-size: 12px;")
            else:
                self.screen_info_label.setText("未检测到屏幕")
                self.screen_info_label.setStyleSheet("color: #FF6B6B; font-weight: bold;")
                
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "错误", f"加载屏幕信息失败：{str(e)}")
            self.screen_info_label.setText("加载屏幕信息失败")
    
    def _on_refresh_screens(self):
        """刷新屏幕列表"""
        self._load_screen_info()
    
    def _on_screen_selection_changed(self):
        """屏幕选择变化时更新显示器索引"""
        current_row = self.screen_table.currentRow()
        if current_row >= 0:
            # 表格行号对应屏幕编号（从1开始）
            screen_index = current_row + 1
            self.sb_monitor.setValue(screen_index)

    def _on_save(self):
        try:
            scales = _parse_scales(self.le_scales.text())
            dx, dy = _parse_pair(self.le_offset.text(), typ=float)
            coord_dx, coord_dy = _parse_pair(self.le_coord_offset.text(), typ=int)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "输入有误", str(e))
            return

        # 读取模板路径列表，若为空则给出提示但允许保存（将使用默认）
        tpl_paths = self._get_template_paths()
        if not tpl_paths:
            # 用户未配置则回退默认图片
            tpl_paths = []

        cfg = AppConfig(
            # 兼容：保留单模板字段，同时提供多模板列表
            template_path=(tpl_paths[0] if tpl_paths else "approve_pix.png"),
            template_paths=tpl_paths,
            monitor_index=self.sb_monitor.value() - 1,  # 转换为0-based索引
            roi=ROI(
                x=self.sb_roi_x.value(),
                y=self.sb_roi_y.value(),
                w=self.sb_roi_w.value(),
                h=self.sb_roi_h.value(),
            ),
            interval_ms=self.sb_interval.value(),
            threshold=self.ds_threshold.value(),
            cooldown_s=self.ds_cooldown.value(),
            enable_logging=self.cb_logging.isChecked(),
            enable_notifications=self.cb_notifications.isChecked(),
            grayscale=self.cb_gray.isChecked(),
            multi_scale=self.cb_multiscale.isChecked(),
            scales=scales,
            click_offset=(dx, dy),
            min_detections=self.sb_min_det.value(),
            auto_start_scan=self.cb_auto_start.isChecked(),
            # 新增的调试和多屏幕支持配置
            debug_mode=self.cb_debug.isChecked(),
            save_debug_images=self.cb_save_debug.isChecked(),
            debug_image_dir=self.le_debug_dir.text() or "debug_images",
            enable_coordinate_correction=self.cb_coord_correction.isChecked(),
            coordinate_offset=(coord_dx, coord_dy),
            enhanced_window_finding=self.cb_enhanced_finding.isChecked(),
            click_method=self.combo_click_method.currentText(),
            verify_window_before_click=self.cb_verify_window.isChecked(),
            coordinate_transform_mode=self.combo_transform_mode.currentText(),
            enable_multi_screen_polling=self.cb_multi_screen_polling.isChecked(),
            screen_polling_interval_ms=self.sb_polling_interval.value(),
            # WGC 捕获相关
            capture_backend=(self.combo_capture_backend.currentData() or 'window'),
            use_monitor=(self.combo_capture_backend.currentData() == 'monitor'),
            target_hwnd=self.sb_target_hwnd.value(),
            # 窗口标题配置已移除
            target_process=self.le_process.text(),
            process_partial_match=self.cb_process_partial.isChecked(),
            fps_max=self.sb_fps_max.value(),
            capture_timeout_ms=self.sb_capture_timeout.value(),
            restore_minimized_noactivate=self.cb_restore_minimized.isChecked(),
            restore_minimized_after_capture=self.cb_restore_after_capture.isChecked(),
            enable_electron_optimization=self.cb_electron_optimization.isChecked(),
            # WGC专用配置
            include_cursor=self.cb_include_cursor.isChecked(),
            # 新增：分别保存窗口与屏幕边框开关；同时写回旧字段（兼容）
            window_border_required=self.cb_border_window.isChecked(),
            screen_border_required=self.cb_border_screen.isChecked(),
            border_required=(self.cb_border_window.isChecked() or self.cb_border_screen.isChecked()),
            # 自动窗口更新配置
            auto_update_hwnd_by_process=self.cb_auto_update_hwnd.isChecked(),
            auto_update_hwnd_interval_ms=self.sb_auto_update_interval.value(),
        )
        # 非阻塞配置保存 - 立即更新UI状态
        self._show_saving_status()
        
        try:
            # 发出"已保存"信号，供外部应用新配置
            self.saved.emit(cfg)
        except Exception:
            pass
        
        # 最后才调用实际的配置保存（已优化为异步）
        save_config(cfg)
        
        # 给予轻量化反馈（非阻塞，不关闭窗口）
        QtWidgets.QToolTip.showText(
            QtGui.QCursor.pos(),
            "正在保存配置...",
            self,
            self.rect(),
            800,  # 更短的显示时间
        )

    def _show_saving_status(self):
        """显示保存状态 - 减少UI渲染开销"""
        # 禁用保存按钮并立即重绘
        self.btn_ok.setEnabled(False)
        self.btn_ok.setText("保存中...")
        # 只处理必要的UI事件，避免全量刷新
        QtWidgets.QApplication.processEvents(QtCore.QEventLoop.ExcludeUserInputEvents)
        
        # 异步延迟恢复保存按钮状态（让UI立即响应）
        QtCore.QTimer.singleShot(200, self._restore_save_status)

    def _restore_save_status(self):
        """恢复保存状态"""
        self.btn_ok.setEnabled(True) 
        self.btn_ok.setText("保存")

    def _on_ui_logging_toggled(self, checked: bool):
        """当用户在设置窗口中切换“启用日志”时：
        - 立即通过全局状态中心应用并持久化；
        - 由状态中心负责通知托盘与其他组件刷新显示。
        """
        try:
            self.state.set_enable_logging(bool(checked), persist=True, emit_signal=True)
        except Exception:
            pass

    def _on_app_state_logging_changed(self, enabled: bool):
        """当托盘或其他位置变更日志开关时，同步刷新本窗口复选框显示，避免环路触发。"""
        try:
            self.cb_logging.blockSignals(True)
            self.cb_logging.setChecked(bool(enabled))
        finally:
            self.cb_logging.blockSignals(False)

    def _on_nav_changed(self, cur: QtWidgets.QTreeWidgetItem, prev: QtWidgets.QTreeWidgetItem | None):
        """左侧菜单变化时切换到对应页面。"""
        if not cur:
            return
        page_index = cur.data(0, QtCore.Qt.ItemDataRole.UserRole)
        # 若点击的是父节点，则默认跳转到第一个子节点
        if page_index is None and cur.childCount() > 0:
            child = cur.child(0)
            self.nav.setCurrentItem(child)
            return
        if isinstance(page_index, int):
            self.stack.setCurrentIndex(page_index)

    # ---------- 新增：窗口捕获辅助 ----------


    def _on_find_window_by_process(self):
        """根据输入进程名或完整路径查找窗口并回填HWND。"""
        proc = (self.le_process.text() or "").strip()
        if not proc:
            QtWidgets.QMessageBox.information(self, "提示", "请先输入进程名或完整路径，例如 Code.exe")
            return
        try:
            from capture.monitor_utils import find_window_by_process
            hwnd = find_window_by_process(proc, self.cb_process_partial.isChecked())
            if hwnd:
                self.sb_target_hwnd.setValue(int(hwnd))
            else:
                QtWidgets.QMessageBox.warning(self, "未找到", "未找到匹配的窗口，请确认进程名/路径或尝试部分匹配")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"按进程查找窗口失败: {e}")

    def _on_open_hwnd_picker(self):
        """打开HWND获取工具并回填配置。"""
        try:
            from auto_approve.hwnd_picker import HWNDPickerDialog
            dlg = HWNDPickerDialog(self)
            # 连接实时信号：选择新窗口时立即同步回填（不必等待点击“确定”）
            try:
                dlg.hwnd_selected.connect(self._on_hwnd_picked_live)
            except Exception:
                pass
            if dlg.exec() == QtWidgets.QDialog.Accepted:
                hwnd, title = dlg.get_selected_hwnd()
                if hwnd:
                    self.sb_target_hwnd.setValue(int(hwnd))
                    # HWND 拾取器返回的第二个字段已调整为“进程名”，优先回填到进程输入框
                    if title:
                        self.le_process.setText(title)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"打开HWND获取工具失败: {e}")

    def _on_hwnd_picked_live(self, hwnd: int, process_short: str):
        """实时回填HWND与进程短路径（exe名）。
        - hwnd: 顶层窗口句柄
        - process_short: 进程相对路径（exe名），用于稳健匹配
        """
        try:
            if hwnd:
                self.sb_target_hwnd.setValue(int(hwnd))
            if process_short:
                self.le_process.setText(process_short)
        except Exception:
            pass

    # ---------- 提供给外部的同步接口 ----------
    def update_target_hwnd(self, hwnd: int):
        """外部调用：更新设置窗口中的目标HWND显示。
        该方法用于自动HWND更新器或其他模块在找到新窗口后，实时同步UI。
        """
        try:
            self.sb_target_hwnd.setValue(int(hwnd))
        except Exception:
            pass

    def _on_test_capture(self):
        """测试当前配置的捕获功能（根据捕获模式选择窗口或屏幕捕获）。"""
        # 获取当前选择的捕获模式
        capture_mode = self.combo_capture_backend.currentData()

        if capture_mode == "window":
            self._test_window_capture()
        elif capture_mode == "monitor":
            self._test_monitor_capture()
        else:
            QtWidgets.QMessageBox.warning(self, "错误", "未知的捕获模式")

    def _test_window_capture(self):
        """测试窗口捕获功能（优化版，避免UI卡顿）。"""
        hwnd = int(self.sb_target_hwnd.value())
        if hwnd <= 0:
            QtWidgets.QMessageBox.warning(self, "提示", "请先设置有效的HWND")
            return

        try:
            # 使用智能捕获测试管理器
            from auto_approve.smart_capture_test_manager import get_smart_capture_manager
            
            # 获取全局管理器
            self._capture_test_manager = get_smart_capture_manager()
            
            # 创建轻量级进度对话框
            self._progress_dialog = QtWidgets.QProgressDialog("正在测试窗口捕获...", "取消", 0, 100, self)
            self._progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
            self._progress_dialog.setMinimumDuration(0)
            self._progress_dialog.setValue(0)
            
            # 使用 UniqueConnection 方式连接，确保同一对 signal-slot 只会连接一次
            self._capture_test_manager.progress_updated.connect(
                self._on_capture_progress, QtCore.Qt.ConnectionType.UniqueConnection
            )
            self._capture_test_manager.test_completed.connect(
                self._on_capture_completed, QtCore.Qt.ConnectionType.UniqueConnection
            )
            self._capture_test_manager.test_failed.connect(
                self._on_capture_failed, QtCore.Qt.ConnectionType.UniqueConnection
            )
            self._capture_test_manager.test_finished.connect(
                self._on_test_finished, QtCore.Qt.ConnectionType.UniqueConnection
            )
            # 标记已建立连接
            self._capture_signals_connected = True
            
            # 连接取消信号
            self._progress_dialog.canceled.connect(self._capture_test_manager.cancel_current_test)
            
            # 重置“只弹一次结果对话框”的标记
            self._result_dialog_shown = False

            # 启动单帧预览测试（最快速度，只捕获一帧）
            self._capture_test_manager.start_smart_window_test(hwnd, preview_only=True)
            
        except ImportError:
            QtWidgets.QMessageBox.critical(self, "依赖缺失", "WGC功能需要: pip install windows-capture-python")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"测试窗口捕获失败: {e}")
            import traceback
            traceback.print_exc()

    def _on_capture_progress(self, progress: int, message: str):
        """处理捕获进度更新"""
        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            self._progress_dialog.setValue(progress)
            self._progress_dialog.setLabelText(message)

    def _on_capture_completed(self, result):
        """处理捕获完成"""
        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            self._progress_dialog.close()
            
        # 防抖：一次测试只允许弹出一次结果窗口
        if self._result_dialog_shown:
            return

        if result.success and result.image is not None:
            self._result_dialog_shown = True
            # 显示捕获结果
            self._show_capture_result(result.image, "窗口捕获测试结果")
        else:
            QtWidgets.QMessageBox.warning(self, "捕获失败", result.error_message or "未知错误")

    def _on_capture_failed(self, error_message: str):
        """处理捕获失败"""
        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            self._progress_dialog.close()
        # 失败时也重置标记
        self._result_dialog_shown = False
        QtWidgets.QMessageBox.critical(self, "捕获错误", error_message)
        
    def _on_test_finished(self):
        """处理测试完成（无论成功或失败）"""
        # 清理资源
        if hasattr(self, '_progress_dialog') and self._progress_dialog:
            self._progress_dialog.close()
            
        # 断开信号连接并重置状态，防止下次重复触发
        if hasattr(self, '_capture_test_manager') and self._capture_test_manager and getattr(self, '_capture_signals_connected', False):
            try:
                self._capture_test_manager.progress_updated.disconnect(self._on_capture_progress)
            except Exception:
                pass
            try:
                self._capture_test_manager.test_completed.disconnect(self._on_capture_completed)
            except Exception:
                pass
            try:
                self._capture_test_manager.test_failed.disconnect(self._on_capture_failed)
            except Exception:
                pass
            try:
                self._capture_test_manager.test_finished.disconnect(self._on_test_finished)
            except Exception:
                pass
            self._capture_test_manager = None
            self._capture_signals_connected = False
        # 重置一次性弹窗标记
        self._result_dialog_shown = False

    def _test_monitor_capture(self):
        """测试屏幕捕获功能（使用快速异步测试避免UI卡顿）。"""
        monitor_index = int(self.sb_monitor.value()) - 1
        
        try:
            # 使用智能测试管理器，默认启用快速测试模式
            if hasattr(self, '_capture_test_manager') and self._capture_test_manager:
                # 创建进度对话框
                self._progress_dialog = QtWidgets.QProgressDialog("正在测试屏幕捕获...", "取消", 0, 100, self)
                self._progress_dialog.setWindowModality(QtCore.Qt.WindowModal)
                self._progress_dialog.setAutoClose(False)
                self._progress_dialog.setAutoReset(False)
                self._progress_dialog.setValue(0)
                self._progress_dialog.show()
                
                # 连接取消信号
                self._progress_dialog.canceled.connect(self._capture_test_manager.cancel_current_test)
                
                # 启动快速智能异步测试（避免UI卡顿）
                self._capture_test_manager.start_smart_monitor_test(monitor_index, preview_only=True)
            else:
                # 备用方案：使用旧的实现
                from auto_approve.qt_workers import CaptureTestWorker, MonitorCaptureParams

                params = MonitorCaptureParams(
                    monitor_index=monitor_index,
                    fps=int(self.sb_fps_max.value()),
                    include_cursor=self.cb_include_cursor.isChecked(),
                    border_required=self.cb_border_screen.isChecked(),
                    timeout_sec=2.0,
                    stabilize_ms=500,
                )

                progress = QtWidgets.QProgressDialog("正在测试屏幕捕获...", "取消", 0, 100, self)
                progress.setWindowModality(QtCore.Qt.WindowModal)
                progress.setAutoClose(False)
                progress.setAutoReset(False)
                progress.setValue(0)
                progress.show()

                thread = QtCore.QThread(self)
                worker = CaptureTestWorker()
                worker.moveToThread(thread)

                worker.sig_progress.connect(lambda v, t: (progress.setValue(v), progress.setLabelText(t)))

                def _on_finished(img, meta):
                    try:
                        progress.setValue(100)
                        progress.close()
                        self._show_capture_result(img, f"屏幕捕获测试结果 (显示器 {monitor_index + 1})")
                    finally:
                        thread.quit()

                def _on_error(msg: str):
                    try:
                        progress.close()
                        QtWidgets.QMessageBox.warning(self, "捕获失败", msg)
                    finally:
                        thread.quit()

                def _on_canceled():
                    try:
                        progress.close()
                    finally:
                        thread.quit()

                worker.sig_finished.connect(_on_finished)
                worker.sig_error.connect(_on_error)
                worker.sig_canceled.connect(_on_canceled)

                progress.canceled.connect(worker.cancel)

                thread.started.connect(lambda: worker.run_monitor_test(params))
                thread.finished.connect(worker.deleteLater)
                thread.finished.connect(thread.deleteLater)
                thread.start()

        except ImportError:
            QtWidgets.QMessageBox.critical(self, "依赖缺失", "WGC功能需要: pip install windows-capture-python")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"测试屏幕捕获失败: {e}")
            import traceback
            traceback.print_exc()

    def _show_capture_result(self, img, title):
        """显示捕获结果的通用方法。"""
        try:
            import cv2
            import numpy as np

            # 确保图像数据连续
            if not img.flags['C_CONTIGUOUS']:
                img = np.ascontiguousarray(img)

            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]

            # 创建QImage时指定正确的格式和步长
            bytes_per_line = rgb.strides[0] if rgb.strides else w * 3
            qimg = QtGui.QImage(rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)

            if qimg.isNull():
                QtWidgets.QMessageBox.warning(self, "显示失败", "无法创建预览图像")
                return

            pm = QtGui.QPixmap.fromImage(qimg)
            if pm.isNull():
                QtWidgets.QMessageBox.warning(self, "显示失败", "无法创建预览像素图")
                return

            dlg = ScreenshotPreviewDialog(pm, self, is_wgc_test=True)
            dlg.setWindowTitle(title)
            if dlg.exec() == QtWidgets.QDialog.Accepted:
                import time
                path = f"capture_test_{int(time.time())}.png"
                success = cv2.imwrite(path, img)
                if success:
                    QtWidgets.QMessageBox.information(self, "保存成功", f"图片已保存: {path}")
                else:
                    QtWidgets.QMessageBox.warning(self, "保存失败", "无法保存图片文件")

        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "显示错误", f"图像显示失败: {e}")

    def _show_capture_result_shared(self, img, title, capture_manager, user_id):
        """显示共享捕获结果的方法（延迟释放资源）。"""
        try:
            import cv2
            import numpy as np

            # 确保图像数据连续
            if not img.flags['C_CONTIGUOUS']:
                img = np.ascontiguousarray(img)

            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]

            # 创建QImage时指定正确的格式和步长
            bytes_per_line = rgb.strides[0] if rgb.strides else w * 3
            qimg = QtGui.QImage(rgb.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888)

            if qimg.isNull():
                capture_manager.release_shared_frame(user_id)
                capture_manager.close()
                QtWidgets.QMessageBox.warning(self, "显示失败", "无法创建预览图像")
                return

            pm = QtGui.QPixmap.fromImage(qimg)
            if pm.isNull():
                capture_manager.release_shared_frame(user_id)
                capture_manager.close()
                QtWidgets.QMessageBox.warning(self, "显示失败", "无法创建预览像素图")
                return

            dlg = ScreenshotPreviewDialog(pm, self, is_wgc_test=True)
            dlg.setWindowTitle(title)

            # 用户交互完成后再释放资源
            try:
                if dlg.exec() == QtWidgets.QDialog.Accepted:
                    import time
                    path = f"capture_test_{int(time.time())}.png"
                    success = cv2.imwrite(path, img)
                    if success:
                        QtWidgets.QMessageBox.information(self, "保存成功", f"图片已保存: {path}")
                    else:
                        QtWidgets.QMessageBox.warning(self, "保存失败", "无法保存图片文件")
            finally:
                # 确保在用户完成所有操作后释放资源
                capture_manager.release_shared_frame(user_id)
                capture_manager.close()

        except Exception as e:
            # 发生异常时也要释放资源
            capture_manager.release_shared_frame(user_id)
            capture_manager.close()
            QtWidgets.QMessageBox.warning(self, "显示错误", f"图像显示失败: {e}")

    def _on_preview_window_capture(self):
        """打开WGC实时预览窗口"""
        hwnd = int(self.sb_target_hwnd.value())
        if hwnd <= 0:
            QtWidgets.QMessageBox.warning(self, "提示", "请先设置有效的HWND")
            return

        try:
            from auto_approve.wgc_preview_dialog import WGCPreviewDialog

            # 创建并显示预览对话框（使用当前开关：光标/窗口边框）
            preview_dialog = WGCPreviewDialog(
                hwnd,
                self,
                fps=15,
                include_cursor=self.cb_include_cursor.isChecked(),
                border_required=self.cb_border_window.isChecked(),
            )
            preview_dialog.exec()

        except ImportError as e:
            QtWidgets.QMessageBox.critical(self, "依赖缺失", f"WGC预览功能需要相关依赖: {e}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "错误", f"打开预览窗口失败: {e}")




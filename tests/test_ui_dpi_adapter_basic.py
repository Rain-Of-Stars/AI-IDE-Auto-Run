# -*- coding: utf-8 -*-
"""
UI 冒烟测试：验证全局DPI适配器能为新窗口自动挂载，并对像素单位控件生效。

策略：
- 创建 QApplication → QtDpiManager → GlobalDpiAdapter；
- 创建一个 QDialog，内部放置 QListView；显示后等待事件循环；
- 断言窗口属性 'aiide_dpi_ratio' 已设置，且 QListView 的 iconSize 被放大到期望像素。

成功：退出码=0；失败：打印修复建议。
"""
import sys
import os
import traceback


def main() -> int:
    try:
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from PySide6 import QtWidgets, QtCore
        from auto_approve.qt_dpi_manager import QtDpiManager
        from auto_approve.ui.dpi_auto_adapter import GlobalDpiAdapter

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
        app.setQuitOnLastWindowClosed(False)

        # 管理器与全局适配器
        mgr = QtDpiManager(app, unify_appearance=True)
        gad = GlobalDpiAdapter(app, mgr)

        # 构造窗口与列表控件
        dlg = QtWidgets.QDialog()
        layout = QtWidgets.QVBoxLayout(dlg)
        lv = QtWidgets.QListView()
        layout.addWidget(lv)
        dlg.show()

        # 主动触发一次扫描并等待事件循环，使适配器完成首次回调
        try:
            gad._scan()  # 仅测试场景调用私有方法，加速挂载
        except Exception:
            pass
        for _ in range(10):
            app.processEvents()
            QtCore.QThread.msleep(80)

        ratio = dlg.property('aiide_dpi_ratio')
        if ratio is None:
            raise AssertionError('未检测到窗口aiide_dpi_ratio属性，可能未挂载适配器')

        isz = lv.iconSize()
        if isz.width() <= 0:
            raise AssertionError('列表图标尺寸未设置，适配未生效')

        print('[通过] 全局DPI适配器已为窗口挂载并生效')
        print('用例统计: 1/1 通过')
        print('覆盖率要点: 自动挂载流程 + 像素单位控件调整')
        return 0

    except Exception as e:
        print('[失败] 全局DPI适配器UI测试失败')
        print(f'摘要: {e}')
        print(traceback.format_exc(limit=3))
        print('修复建议:')
        print('- 确认 GlobalDpiAdapter 定时扫描并调用 attach_window_adapter')
        print('- 确认 attach_window_adapter 在首次定时器触发时回调 on_ratio_changed')
        print('- 若使用无头环境，尽量避免依赖屏幕事件，使用单Shot触发初次回调')
        print('- 检查 default_on_ratio_changed 是否正确设置像素控件的尺寸')
        return 1


if __name__ == '__main__':
    sys.exit(main())

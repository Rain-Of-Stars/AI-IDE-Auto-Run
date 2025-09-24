# -*- coding: utf-8 -*-
"""
冒烟测试：验证屏幕列表对话框在加载屏幕信息时不抛异常，
并正确更新表格与信息标签（健壮性修复验证）。

成功：退出码=0，打印用例统计与覆盖率要点
失败：退出码!=0，打印精简摘要与3-5条修复建议
"""
import sys
import os
import traceback


def main() -> int:
    try:
        # 确保包导入路径正确
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))

        # 在创建QApplication前设置高DPI策略由主模块负责
        import main_auto_approve_refactored as _main_mod  # noqa: F401

        from PySide6 import QtWidgets
        from auto_approve.screen_list_dialog import ScreenListDialog
        from capture.monitor_utils import get_all_monitors_info

        app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

        dlg = ScreenListDialog()
        # 直接调用加载逻辑，不弹出对话框
        dlg._load_screen_info()

        monitors = get_all_monitors_info() or []
        # 行数应与枚举数量一致
        if dlg.table.rowCount() != len(monitors):
            raise AssertionError(
                f"表格行数不一致: {dlg.table.rowCount()} != {len(monitors)}"
            )

        # 信息标签应非空
        if not dlg.info_label.text():
            raise AssertionError("信息标签未更新")

        print("[通过] 屏幕列表对话框加载信息稳定且无异常")
        print("用例统计: 2/2 通过")
        print("覆盖率要点: 覆盖表格填充与信息标签生成")
        return 0

    except Exception as e:
        print("[失败] 屏幕列表对话框稳健性验证失败")
        print(f"摘要: {e}")
        print(traceback.format_exc(limit=3))
        print("修复建议:")
        print("- 检查未定义变量与空列表处理逻辑")
        print("- 确保从capture.monitor_utils返回的字典字段完整性")
        print("- 避免在循环内重复计算标签文本，统一在循环后计算")
        print("- 确认在创建QApplication前已设置高DPI策略，避免Qt侧面影响")
        return 1


if __name__ == "__main__":
    sys.exit(main())


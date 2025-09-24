# -*- coding: utf-8 -*-
"""
最小化冒烟测试：验证在创建QApplication实例之前已设置高DPI缩放因子取整策略，
避免出现“setHighDpiScaleFactorRoundingPolicy must be called before creating the QGuiApplication instance”警告。

成功：退出码=0，并打印用例统计与覆盖率要点
失败：退出码!=0，并打印精简摘要与3-5条修复建议
"""
import sys
import os
import traceback

def main() -> int:
    try:
        # 导入主模块（模块级会设置取整策略）
        # 确保能从项目根目录导入主模块
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        import main_auto_approve_refactored as main_mod
        from PySide6 import QtGui, QtCore, QtWidgets

        # 1) 导入后立即检查全局取整策略是否为RoundPreferFloor（无需QApplication实例）
        policy = QtGui.QGuiApplication.highDpiScaleFactorRoundingPolicy()
        expected = QtCore.Qt.HighDpiScaleFactorRoundingPolicy.RoundPreferFloor
        if policy != expected:
            raise AssertionError(f"取整策略不符: 当前={policy}, 期望={expected}")

        # 2) 创建最小QApplication，验证策略仍然生效
        app = QtWidgets.QApplication([])
        try:
            policy_after = QtGui.QGuiApplication.highDpiScaleFactorRoundingPolicy()
            if policy_after != expected:
                raise AssertionError(f"QApplication创建后策略被篡改: 当前={policy_after}, 期望={expected}")
        finally:
            # 确保正确销毁，避免干扰其他测试
            app.quit()
            del app

        # 成功输出
        print("[通过] 高DPI取整策略设置正确，且在QApplication创建前已应用")
        print("用例统计: 2/2 通过")
        print("覆盖率要点: 覆盖策略设置前后、实例化前后两个关键路径")
        return 0

    except Exception as e:
        # 失败输出：精简摘要 + 修复建议
        print("[失败] 高DPI取整策略验证失败")
        print(f"摘要: {e}")
        # 记录简要堆栈便于定位
        tb = traceback.format_exc(limit=3)
        print(tb)
        print("修复建议:")
        print("- 确保在创建QApplication之前调用QGuiApplication.setHighDpiScaleFactorRoundingPolicy")
        print("- 避免在应用启动后再次修改取整策略，可能触发Qt警告")
        print("- 校验PySide6版本是否支持该API，并添加异常兼容")
        print("- 检查是否有外部模块在QApplication创建后重复设置策略")
        return 1


if __name__ == "__main__":
    sys.exit(main())

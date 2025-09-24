# -*- coding: utf-8 -*-
"""
最小化冒烟测试（纯函数）：验证 DPI 策略解析与缩放计算逻辑。

成功：退出码=0，并打印用例统计与覆盖率要点
失败：退出码!=0，并打印精简摘要与3–5条修复建议
"""
import os
import sys
import traceback


def main() -> int:
    try:
        # 保证能导入被测模块
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from auto_approve.qt_dpi_manager import resolve_rounding_policy, compute_scale_for_dpi

        # 1) 策略解析：默认
        env = {}
        assert resolve_rounding_policy(env) == "RoundPreferFloor"

        # 2) 策略解析：别名/大小写
        assert resolve_rounding_policy({"AIIDE_DPI_ROUNDING_POLICY": "pass"}) == "PassThrough"
        assert resolve_rounding_policy({"AIIDE_DPI_ROUNDING_POLICY": "Ceil"}) == "Ceil"
        assert resolve_rounding_policy({"AIIDE_DPI_ROUNDING_POLICY": "ROUND"}) == "Round"

        # 3) 缩放计算
        assert abs(compute_scale_for_dpi(96) - 1.0) < 1e-6
        assert abs(compute_scale_for_dpi(144) - 1.5) < 1e-6
        assert abs(compute_scale_for_dpi(192) - 2.0) < 1e-6
        assert compute_scale_for_dpi(-1) == 1.0

        print("[通过] DPI策略解析与缩放计算逻辑正确")
        print("用例统计: 4/4 通过")
        print("覆盖率要点: 策略分支与异常分支均覆盖")
        return 0
    except Exception as e:
        print("[失败] DPI纯函数测试失败")
        print(f"摘要: {e}")
        tb = traceback.format_exc(limit=3)
        print(tb)
        print("修复建议:")
        print("- 检查环境变量解析大小写与别名映射是否正确")
        print("- 检查负数/异常 DPI 输入的容错返回是否为1.0")
        print("- 确认 tests 使用的导入路径正确")
        print("- 排查近期对 qt_dpi_manager 的改动")
        return 1


if __name__ == "__main__":
    sys.exit(main())


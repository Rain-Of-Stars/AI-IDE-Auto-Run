# -*- coding: utf-8 -*-
"""
纯算法测试：窗口所在屏幕判定与交集面积/最近距离回退；以及一致外观比例的计算（纯函数部分）。

成功：退出码=0，并打印用例统计与覆盖率要点
失败：退出码!=0，并打印精简摘要与3–5条修复建议
"""
import os
import sys
import traceback


def main() -> int:
    try:
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from auto_approve.qt_dpi_manager import choose_screen_by_rect, rect_intersection_area, compute_scale_for_dpi

        # 1) 交集面积基础
        a = (0, 0, 100, 100)
        b = (50, 50, 150, 150)
        assert rect_intersection_area(a, b) == 2500

        # 2) 屏幕选择：最大交集
        screens = [(-1920, 0, 0, 1080), (0, 0, 1920, 1080)]
        # 窗口跨越两屏，但右侧交集更大
        win = (-100, 100, 1100, 900)
        idx = choose_screen_by_rect(win, screens)
        assert idx == 1, f"应选择右屏索引1，得到{idx}"

        # 3) 无交集回退：取中心点最近
        win_far = (3000, 100, 3100, 200)  # 远在右侧
        idx2 = choose_screen_by_rect(win_far, screens)
        assert idx2 == 1

        # 4) 一致外观比例：以96为基准
        base = compute_scale_for_dpi(96)
        s144 = compute_scale_for_dpi(144)
        ratio = s144 / base
        assert abs(ratio - 1.5) < 1e-6

        print('[通过] 屏幕判定与比例计算算法正确')
        print('用例统计: 4/4 通过')
        print('覆盖率要点: 交集/回退两个分支 + 比例计算')
        return 0

    except Exception as e:
        print('[失败] 一致外观算法测试失败')
        print(f'摘要: {e}')
        print(traceback.format_exc(limit=3))
        print('修复建议:')
        print('- 检查交集面积与坐标系(left,top,right,bottom)是否一致')
        print('- 无交集场景下的最近距离回退是否正确')
        print('- 比例计算应为 current_scale/base_scale')
        print('- 修改后重新运行 tests/test_consistent_dpi_pure.py')
        return 1


if __name__ == '__main__':
    sys.exit(main())


# -*- coding: utf-8 -*-
"""
最小化冒烟测试：验证基于分辨率高度构造 QT_SCREEN_SCALE_FACTORS 的纯函数，
以及早期注入逻辑在环境变量控制下的行为（通过猴子补丁避免真实枚举与WinAPI）。

成功：退出码=0，并打印用例统计与覆盖率要点
失败：退出码!=0，并打印精简摘要与3–5条修复建议
"""
import os
import sys
import traceback


def main() -> int:
    try:
        # 导入被测模块
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        import utils.win_dpi as win_dpi

        # 1) 纯函数：按高度构造缩放因子（避免依赖真实系统与WinAPI）
        fake_monitors = [
            {'hmonitor': 1, 'width': 1920, 'height': 1080, 'device': 'DISPLAY1'},
            {'hmonitor': 2, 'width': 2560, 'height': 1440, 'device': 'DISPLAY2'},
            {'hmonitor': 3, 'width': 3840, 'height': 2160, 'device': 'DISPLAY3'},
        ]
        factors = win_dpi.build_qt_screen_scale_factors(
            prefer='height', base_height=1080, min_scale=1.0,
            fallback_to_height=True, monitors=fake_monitors
        )
        assert factors == '1.0;1.3;2.0', f"构造出的因子不符: {factors}"

        # 2) 私有纯函数容错：DPI与高度
        assert abs(win_dpi._compute_scale_from_dpi(96) - 1.0) < 1e-6
        assert abs(win_dpi._compute_scale_from_dpi(144) - 1.5) < 1e-6
        assert win_dpi._compute_scale_from_dpi(-1) >= 1.0
        assert abs(win_dpi._compute_scale_from_height(1080) - 1.0) < 1e-6
        assert abs(win_dpi._compute_scale_from_height(2160) - 2.0) < 1e-6

        # 3) 早期注入：猴子补丁build函数，验证环境变量设置
        orig_builder = win_dpi.build_qt_screen_scale_factors
        try:
            def fake_builder(**kwargs):
                return '1.0;1.5'
            win_dpi.build_qt_screen_scale_factors = lambda **kwargs: fake_builder(**kwargs)

            env = {}
            env['AIIDE_ENABLE_QT_SCREEN_SCALE_FACTORS'] = '1'
            env['AIIDE_SCREEN_SCALE_MODE'] = 'dpi'
            # 未设置 QT_SCREEN_SCALE_FACTORS 前应注入
            s = win_dpi.apply_qt_screen_scale_factors_early(env)
            assert s == '1.0;1.5'
            assert env.get('QT_SCREEN_SCALE_FACTORS') == '1.0;1.5'

            # 已设置时保持不变
            env2 = {'QT_SCREEN_SCALE_FACTORS': 'x'}
            s2 = win_dpi.apply_qt_screen_scale_factors_early(env2)
            assert s2 is None and env2['QT_SCREEN_SCALE_FACTORS'] == 'x'
        finally:
            win_dpi.build_qt_screen_scale_factors = orig_builder

        # 4) 排序校验：无序输入应按left/top排序
        unordered = [
            {'hmonitor': 3, 'width': 3840, 'height': 2160, 'left': 1920, 'top': 0, 'device': 'C'},
            {'hmonitor': 1, 'width': 1920, 'height': 1080, 'left': -1920, 'top': 0, 'device': 'A'},
            {'hmonitor': 2, 'width': 2560, 'height': 1440, 'left': 0, 'top': 0, 'device': 'B'},
        ]
        s = win_dpi.build_qt_screen_scale_factors(prefer='height', monitors=unordered)
        parts = s.split(';')
        assert parts[0] == '1.0' and parts[1] == '1.3' and parts[2] == '2.0', f'排序不正确: {parts}'

        print('[通过] 屏幕缩放因子构造与早期注入逻辑正确')
        print('用例统计: 4/4 通过')
        print('覆盖率要点: 纯函数分支、异常/兜底、注入前后判定、排序')
        return 0

    except Exception as e:
        print('[失败] 屏幕缩放因子逻辑测试失败')
        print(f'摘要: {e}')
        tb = traceback.format_exc(limit=3)
        print(tb)
        print('修复建议:')
        print('- 检查高度/基准高度的缩放计算与四舍五入精度')
        print('- 确认早期注入逻辑仅在启用开关时生效，且尊重已有变量')
        print('- 避免在构造函数中调用真实WinAPI，保持纯函数可测')
        print('- 变更后重新运行 tests/test_screen_scale_factors_pure.py')
        return 1


if __name__ == '__main__':
    sys.exit(main())

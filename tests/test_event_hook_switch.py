# -*- coding: utf-8 -*-
"""
事件钩子切换验证测试

目的：当目标进程的主窗口HWND发生变化且旧HWND仍然有效时，
SmartProcessFinder 能通过 WinEventHook/候选评估逻辑及时切换到新HWND。

说明：为避免依赖真实Windows事件，本测试通过mock内部方法，
直接调用候选评估入口 `_on_window_event_candidate` 来模拟事件到达。
"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auto_approve.config_manager import AppConfig
from auto_approve.smart_process_finder import SmartProcessFinder


class TestEventHookSwitch(unittest.TestCase):
    """验证事件驱动的HWND切换逻辑"""

    def setUp(self):
        self.finder = SmartProcessFinder()
        cfg = AppConfig()
        cfg.target_process = 'DemoApp.exe'
        self.finder.set_config(cfg)

    def test_switch_when_new_window_foreground(self):
        """前台事件优先：应立即切换到新的HWND"""
        old_hwnd = 10001
        new_hwnd = 10002

        # mock 窗口有效性与信息/面积
        with patch.object(self.finder, '_is_window_valid', return_value=True), \
             patch.object(self.finder, '_get_window_info') as mock_info, \
             patch('capture.monitor_utils.get_window_rect') as mock_rect:

            def info_side(hwnd):
                if hwnd == old_hwnd:
                    return {'hwnd': old_hwnd, 'title': 'DemoApp - Old', 'process': 'DemoApp.exe', 'path': 'C:/Demo/DemoApp.exe'}
                if hwnd == new_hwnd:
                    return {'hwnd': new_hwnd, 'title': 'DemoApp - New', 'process': 'DemoApp.exe', 'path': 'C:/Demo/DemoApp.exe'}
                return None

            mock_info.side_effect = info_side
            mock_rect.side_effect = lambda hwnd: {'width': 800, 'height': 600} if hwnd == new_hwnd else {'width': 400, 'height': 300}

            # 先设定旧的句柄为当前
            self.finder._current_hwnd = old_hwnd
            # 触发前台事件（EVENT_SYSTEM_FOREGROUND = 0x0003）
            self.finder._on_window_event_candidate(new_hwnd, 0x0003, source='UT')

            # 应切换到 new_hwnd
            self.assertEqual(self.finder.get_current_hwnd(), new_hwnd)

    def test_switch_when_area_bigger(self):
        """非前台事件：面积显著更大时也应切换"""
        old_hwnd = 11001
        new_hwnd = 11002

        with patch.object(self.finder, '_is_window_valid', return_value=True), \
             patch.object(self.finder, '_get_window_info') as mock_info, \
             patch('capture.monitor_utils.get_window_rect') as mock_rect:

            def info_side(hwnd):
                return {'hwnd': hwnd, 'title': 'Demo', 'process': 'DemoApp.exe', 'path': 'C:/Demo/DemoApp.exe'}

            mock_info.side_effect = info_side
            # 新窗口面积远大于旧窗口
            mock_rect.side_effect = lambda hwnd: {'width': 1200, 'height': 800} if hwnd == new_hwnd else {'width': 200, 'height': 150}

            self.finder._current_hwnd = old_hwnd
            # 模拟 CREATE/SHOW 事件（不会强制前台）
            self.finder._on_window_event_candidate(new_hwnd, 0x8002, source='UT')

            self.assertEqual(self.finder.get_current_hwnd(), new_hwnd)


if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(TestEventHookSwitch)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    # 成功打印统计并以0退出，失败非0退出
    print(f"用例统计: 通过={result.testsRun - len(result.failures) - len(result.errors)}, 失败={len(result.failures)}, 错误={len(result.errors)}")
    sys.exit(0 if result.wasSuccessful() else 1)


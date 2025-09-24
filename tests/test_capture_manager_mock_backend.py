# -*- coding: utf-8 -*-
"""
CaptureManager 假后端冒烟测试（不触发WGC）

做法：
- 临时猴补丁 capture.capture_manager 内的 WGCCaptureSession 与 _resolve_monitor_target；
- 使用只在内存中生成的假帧，验证 capture_frame / get_shared_frame / release_shared_frame 流程；
- 全过程零交互、零系统依赖（无需真实窗口/显示器）。
"""
import unittest
import numpy as np


class TestCaptureManagerMockBackend(unittest.TestCase):
    def test_mock_monitor_flow(self):
        from capture import capture_manager as cm
        from capture.shared_frame_cache import get_shared_frame_cache

        # 构造假后端：最小接口集合
        class MockSession:
            def __init__(self):
                self._frame_cache = get_shared_frame_cache()
                self._latest = None

            @classmethod
            def from_monitor(cls, hmonitor):
                return cls()

            @classmethod
            def from_hwnd(cls, hwnd):
                return cls()

            def start(self, target_fps=30, include_cursor=False, border_required=False):
                # 生成一帧固定内容图（只读），模拟捕获输出
                img = np.zeros((20, 30, 3), dtype=np.uint8)
                img[:, :, 0] = 120
                img[:, :, 1] = 60
                try:
                    img.setflags(write=False)
                except Exception:
                    pass
                self._latest = img
                # 写入共享缓存
                self._frame_cache.cache_frame(self._latest, frame_id="mock_0")
                return True

            def grab(self):
                # 返回副本以模拟真实抓取API
                return self._latest.copy() if self._latest is not None else None

            def grab_fast(self):
                return self.grab()

            def wait_for_frame(self, timeout=0.05):
                return self.grab()

            def get_shared_frame(self, user_id: str):
                return self._frame_cache.get_frame(user_id, frame_id="mock_0")

            def release_shared_frame(self, user_id: str):
                self._frame_cache.release_user(user_id)

            def get_stats(self):
                return {"frame_count": 1, "actual_fps": 1}

            def close(self):
                self._latest = None

        # 打补丁：替换类与解析器（避免真实显示器依赖）
        cm.WGCCaptureSession = MockSession  # type: ignore
        cm.CaptureManager._resolve_monitor_target = lambda self, target: 1  # type: ignore

        m = cm.CaptureManager()
        m.configure(fps=10, include_cursor=False, border_required=False)

        # 打开“显示器捕获”（实际是Mock）
        ok = m.open_monitor(0)
        self.assertTrue(ok)

        # 直接抓帧
        img = m.capture_frame()
        self.assertIsNotNone(img)
        self.assertEqual(img.shape, (20, 30, 3))

        # 共享帧路径
        view = m.get_shared_frame("test_user", session_type="test")
        self.assertIsNotNone(view)
        self.assertEqual(view.shape, (20, 30, 3))
        # 共享帧应为只读
        self.assertFalse(view.flags.writeable)
        m.release_shared_frame("test_user")

        # 统计信息可获取
        stats = m.get_stats()
        self.assertIn("actual_fps", stats)

        # 关闭会话
        m.close()


if __name__ == '__main__':
    unittest.main()


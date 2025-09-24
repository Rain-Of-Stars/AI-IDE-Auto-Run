# -*- coding: utf-8 -*-
"""
SharedFrameCache最小单元测试（零依赖WGC/GUI）

验证要点：
- 只读帧零拷贝缓存（对象id不变、不可写）；
- 可写帧会执行一次拷贝并转为只读；
- 命中统计与用户注册/释放逻辑。
"""
import unittest
import numpy as np

from capture.shared_frame_cache import SharedFrameCache


class TestSharedFrameCacheUnit(unittest.TestCase):
    def test_cache_readonly_zero_copy(self):
        cache = SharedFrameCache()

        # 准备一个只读帧
        a = np.zeros((10, 10, 3), dtype=np.uint8)
        a.setflags(write=False)
        fid = cache.cache_frame(a, frame_id="f1")

        # 读取：应返回同一对象、不可写
        b = cache.get_frame(user_id="u1", frame_id=fid)
        self.assertIsNotNone(b)
        self.assertIs(b, a)
        self.assertFalse(b.flags.writeable)
        stats = cache.get_stats()
        self.assertEqual(stats['cache_hits'], 1)
        self.assertEqual(stats['current_users'], 1)

        cache.release_user("u1")
        stats = cache.get_stats()
        self.assertEqual(stats['current_users'], 0)

    def test_cache_writable_copy_once(self):
        cache = SharedFrameCache()

        # 准备一个可写帧
        a = np.ones((5, 5), dtype=np.uint8)
        self.assertTrue(a.flags.writeable)
        fid = cache.cache_frame(a, frame_id="f2")

        # 读取：应不是同一对象、但为只读
        b = cache.get_frame(user_id="u2", frame_id=fid)
        self.assertIsNotNone(b)
        self.assertIsNot(b, a)
        self.assertFalse(b.flags.writeable)

        # 修改源数据不影响缓存
        a[0, 0] = 255
        self.assertEqual(int(b[0, 0]), 1)

        cache.release_user("u2")


if __name__ == '__main__':
    unittest.main()


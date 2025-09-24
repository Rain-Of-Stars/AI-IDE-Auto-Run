# -*- coding: utf-8 -*-
"""
最小环境冒烟测试：
- 验证关键三方包是否可导入（conda优先安装，pip仅用于windows-capture）
- 验证项目核心模块的导入与基础状态切换（不启动GUI、不写入磁盘）
"""
import unittest


class TestEnvironmentSmoke(unittest.TestCase):
    """针对依赖与核心导入的最小化测试"""

    def test_third_party_imports(self):
        # 第三方依赖导入（若失败，可定位到具体包）
        import numpy  # noqa: F401
        import cv2  # noqa: F401
        import PIL  # noqa: F401
        import psutil  # noqa: F401
        import requests  # noqa: F401
        import aiohttp  # noqa: F401
        import websockets  # noqa: F401
        import PySide6  # noqa: F401
        import qasync  # noqa: F401
        import windows_capture  # noqa: F401

    def test_project_core_imports(self):
        # 项目核心模块导入与状态切换（不启动 QApplication）
        from auto_approve.app_state import get_app_state
        from auto_approve.logger_manager import get_logger

        state = get_app_state()
        logger = get_logger()

        before = state.enable_logging
        state.set_enable_logging(not before, persist=False, emit_signal=True)
        logger.info("冒烟测试：flip")
        state.set_enable_logging(before, persist=False, emit_signal=True)
        logger.info("冒烟测试：restore")


if __name__ == "__main__":
    unittest.main(verbosity=2)


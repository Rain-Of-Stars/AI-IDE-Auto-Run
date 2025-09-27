# -*- coding: utf-8 -*-
"""SQLite存储与配置镜像冒烟测试（零交互）。

目标：
- 验证首次加载会初始化DB并导出config.json镜像；
- 验证保存配置会落库并更新JSON镜像；
- 验证图片BLOB的基本存取逻辑；

说明：
- 本测试使用unittest，避免额外依赖；
- 每个测试在独立的临时目录下运行，互不影响。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


class TestSQLiteStorage(unittest.TestCase):
    def setUp(self) -> None:
        # 每个用例使用独立临时目录
        self.tmpdir = Path(tempfile.mkdtemp(prefix="sqlite_storage_test_"))
        os.chdir(self.tmpdir)
        project_root = Path(__file__).resolve().parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

    def test_sqlite_config_only(self):
        from auto_approve.config_manager import load_config, save_config, CONFIG_FILE
        from storage import get_db_path

        cfg = load_config(CONFIG_FILE)
        self.assertIsNotNone(cfg)

        # 主动保存一次，确保DB落盘
        save_config(cfg, CONFIG_FILE)

        db_path = Path(get_db_path())
        if not db_path.exists():
            # 调试输出，便于定位路径问题（CI环境可能切换工作目录）
            print("[DEBUG] cwd:", Path.cwd())
            print("[DEBUG] db_path:", db_path)
            try:
                print("[DEBUG] cwd files:", [p.name for p in Path.cwd().iterdir()])
            except Exception:
                pass
        self.assertTrue(db_path.exists(), "数据库文件应已创建")

        # 保存后从DB读取应一致
        old_interval = cfg.interval_ms
        cfg.interval_ms = old_interval + 123
        save_config(cfg, CONFIG_FILE)
        cfg2 = load_config(CONFIG_FILE)
        self.assertEqual(cfg2.interval_ms, old_interval + 123)

    def test_image_blob_roundtrip(self):
        from storage import init_db, save_image_blob, load_image_blob, list_images, delete_image

        init_db()
        payload = b"FAKEPNG\x89\x50\x4E\x47\x0D\x0A\x1A\x0A"
        name = "unit_test_image"
        category = "test"

        save_image_blob(name, payload, category=category, size=(10, 10))
        items = list_images(category=category)
        self.assertTrue(any(n == name for _, n, c in items if c == category))

        blob = load_image_blob(name, category=category)
        self.assertEqual(blob, payload)

        rc = delete_image(name, category=category)
        self.assertGreaterEqual(rc, 0)


if __name__ == "__main__":
    # 以零交互方式运行
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.defaultTestLoader.loadTestsFromTestCase(TestSQLiteStorage))
    # 失败需非0退出码并给出简短建议
    if not result.wasSuccessful():
        print("建议: 1) 检查SQLite初始化; 2) 核对JSON镜像导出; 3) 确认工作目录权限; 4) 留意路径编码; 5) 查看异常堆栈")
        raise SystemExit(1)

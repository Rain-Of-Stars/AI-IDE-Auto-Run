# -*- coding: utf-8 -*-
"""
SQLite存储实现：统一管理配置与图片等需要持久化的数据。

设计要点：
- config表仅存放一行数据（id=1），字段data为完整配置的JSON文本；
- images表用于存放图片二进制（BLOB）与基本元数据，便于后续扩展；
- 提供JSON镜像导入/导出，兼容依赖config.json的旧流程与测试用例；

说明：
- 由于项目原先以JSON文件为主存储，本模块在读取时若发现数据库为空，
  会尝试从config.json导入；若也不存在，则写入默认配置（由上层提供）。
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# 默认数据库文件名（放在项目根目录）
DB_FILENAME = "app.db"

# 进程内简单连接池（每线程一个连接），避免Qt线程与工作线程间重复打开频繁开销
_local = threading.local()
_current_db_path: str | None = None  # 记录当前连接所指向的数据库路径


def get_db_path(base_dir: Optional[str] = None) -> str:
    """获取数据库文件绝对路径。

    参数：
    - base_dir: 基准目录；缺省为当前工作目录。
    """
    base = Path(base_dir) if base_dir else Path.cwd()
    return str((base / DB_FILENAME).resolve())


def _get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    """获取线程局部的数据库连接；不存在则创建。
    使用 `detect_types=sqlite3.PARSE_DECLTYPES` 便于后续扩展。
    """
    # 目标路径优先级：函数参数 > 环境变量 > 当前工作目录默认
    requested = db_path or os.environ.get("AIIDE_DB_PATH") or get_db_path()

    global _current_db_path

    # 若未建立连接，或请求路径与当前不一致，则新建/切换连接
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(requested, timeout=30, isolation_level=None)
        _local.conn.execute("PRAGMA journal_mode=WAL;")
        _local.conn.execute("PRAGMA synchronous=NORMAL;")
        _local.conn.execute("PRAGMA foreign_keys=ON;")
        _current_db_path = requested
    else:
        if _current_db_path is None or Path(_current_db_path) != Path(requested):
            try:
                _local.conn.close()
            except Exception:
                pass
            _local.conn = sqlite3.connect(requested, timeout=30, isolation_level=None)
            _local.conn.execute("PRAGMA journal_mode=WAL;")
            _local.conn.execute("PRAGMA synchronous=NORMAL;")
            _local.conn.execute("PRAGMA foreign_keys=ON;")
            _current_db_path = requested
    return _local.conn


def init_db(db_path: Optional[str] = None) -> None:
    """初始化数据库（幂等）。创建需要的表与索引。"""
    conn = _get_conn(db_path)
    cur = conn.cursor()
    # 配置表：单行存储完整JSON
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            data TEXT NOT NULL,
            updated_at REAL NOT NULL
        );
        """
    )
    # 图片表：名称与分类可用于查找；data为BLOB
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            category TEXT,
            width INTEGER,
            height INTEGER,
            data BLOB NOT NULL,
            created_at REAL NOT NULL,
            UNIQUE(name, category)
        );
        """
    )
    # 配置备份表：用于保留历史配置快照
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS config_backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT NOT NULL,
            note TEXT,
            created_at REAL NOT NULL
        );
        """
    )
    cur.close()


def get_config_json() -> Optional[Dict[str, Any]]:
    """读取配置JSON；若不存在记录返回None。"""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT data FROM config WHERE id=1;")
    row = cur.fetchone()
    cur.close()
    if row is None:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def set_config_json(cfg: Dict[str, Any]) -> None:
    """将完整配置写入数据库（覆盖式 upsert）。"""
    conn = _get_conn()
    cur = conn.cursor()
    payload = json.dumps(cfg, ensure_ascii=False)
    now_ts = time.time()
    cur.execute(
        "INSERT INTO config (id, data, updated_at) VALUES (1, ?, ?)\n"
        "ON CONFLICT(id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at;",
        (payload, now_ts),
    )
    cur.close()


def import_config_from_json(json_path: str) -> Optional[Dict[str, Any]]:
    """从JSON文件导入配置到数据库；成功时返回配置字典。"""
    p = Path(json_path)
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    set_config_json(data)
    return data


def export_config_to_json(json_path: str) -> Optional[str]:
    """将数据库中的配置导出为JSON文件，返回导出路径或None。"""
    data = get_config_json()
    if data is None:
        return None
    p = Path(json_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return str(p)


def add_config_backup(data: Dict[str, Any], note: str = "") -> int:
    """将当前配置字典作为快照写入备份表，返回备份id。"""
    conn = _get_conn()
    cur = conn.cursor()
    payload = json.dumps(data, ensure_ascii=False)
    ts = time.time()
    cur.execute(
        "INSERT INTO config_backups (data, note, created_at) VALUES (?, ?, ?);",
        (payload, note, ts),
    )
    rowid = cur.lastrowid or 0
    cur.close()
    return int(rowid)


def list_config_backups(limit: int = 20) -> List[Tuple[int, float, str]]:
    """列出最近的配置备份，返回(id, created_at, note)。"""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, created_at, COALESCE(note,'') FROM config_backups ORDER BY id DESC LIMIT ?;",
        (limit,),
    )
    rows = cur.fetchall()
    cur.close()
    return [(int(r[0]), float(r[1]), str(r[2])) for r in rows]


def get_config_backup(backup_id: int) -> Optional[Dict[str, Any]]:
    """按id获取备份的配置字典。"""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT data FROM config_backups WHERE id=?;", (backup_id,))
    row = cur.fetchone()
    cur.close()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


# ================= 图片BLOB存取 =================

def save_image_blob(name: str, data: bytes, *, category: str = "", size: Tuple[int, int] | None = None) -> int:
    """保存图片二进制数据到数据库，返回行id。
    参数：
    - name: 图片名称（可用于唯一约束）；
    - data: 图片字节流（PNG/JPEG等编码格式或原始字节）；
    - category: 业务类别标签，便于区分不同用途；
    - size: (宽, 高)；未知可传None。
    """
    conn = _get_conn()
    cur = conn.cursor()
    w, h = (size or (None, None))
    now_ts = time.time()
    cur.execute(
        """
        INSERT INTO images (name, category, width, height, data, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(name, category) DO UPDATE SET
            data=excluded.data,
            width=excluded.width,
            height=excluded.height,
            created_at=excluded.created_at
        ;
        """,
        (name, category, w, h, sqlite3.Binary(data), now_ts),
    )
    rowid = cur.lastrowid
    cur.close()
    return int(rowid) if rowid is not None else 0


def load_image_blob(name: str, *, category: str = "") -> Optional[bytes]:
    """按名称与类别读取图片二进制。不存在返回None。"""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT data FROM images WHERE name=? AND category=? LIMIT 1;",
        (name, category),
    )
    row = cur.fetchone()
    cur.close()
    if row is None:
        return None
    return bytes(row[0])


def list_images(*, category: str | None = None) -> List[Tuple[int, str, str]]:
    """列出图片条目；返回(id, name, category)列表。"""
    conn = _get_conn()
    cur = conn.cursor()
    if category:
        cur.execute("SELECT id, name, category FROM images WHERE category=? ORDER BY id DESC;", (category,))
    else:
        cur.execute("SELECT id, name, category FROM images ORDER BY id DESC;")
    rows = cur.fetchall()
    cur.close()
    return [(int(r[0]), str(r[1]), str(r[2])) for r in rows]


def delete_image(name: str, *, category: str = "") -> int:
    """删除指定图片，返回受影响行数。"""
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM images WHERE name=? AND category=?;", (name, category))
    rc = cur.rowcount or 0
    cur.close()
    return int(rc)

"""SQLite持久化存储包。

该包提供统一的SQLite数据库接入，包含：
- 配置表：存放完整的配置JSON（单行）；
- 图片表：存放图片二进制BLOB及元数据；

注意：所有代码注释均为中文，不包含作者与时间信息。
"""

# 仅导出主要接口，避免上层直接依赖实现细节
from .sqlite_storage import (
    get_db_path,
    init_db,
    get_config_json,
    set_config_json,
    import_config_from_json,
    save_image_blob,
    load_image_blob,
    list_images,
    delete_image,
    add_config_backup,
    list_config_backups,
    get_config_backup,
)

__all__ = [
    "get_db_path",
    "init_db",
    "get_config_json",
    "set_config_json",
    "import_config_from_json",
    "save_image_blob",
    "load_image_blob",
    "list_images",
    "delete_image",
    "add_config_backup",
    "list_config_backups",
    "get_config_backup",
]

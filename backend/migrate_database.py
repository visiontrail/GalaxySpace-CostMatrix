#!/usr/bin/env python3
"""
数据库迁移脚本 - 删除旧数据库并重新初始化

由于 Employee 表结构变更（添加 level2_department_id 和 level3_department_id），
需要删除旧数据库文件并重新初始化。

使用方法：
    python migrate_database.py
"""

import os
import shutil
from pathlib import Path
from app.db.database import DB_PATH, init_db
from app.utils.logger import get_logger

logger = get_logger(__name__)


def migrate_database():
    """执行数据库迁移：删除旧数据库并重新初始化"""
    backup_dir = DB_PATH.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    if DB_PATH.exists():
        backup_path = backup_dir / f"costmatrix_backup_{DB_PATH.stat().st_mtime}.db"
        logger.info(f"备份数据库到: {backup_path}")
        shutil.copy2(DB_PATH, backup_path)

        logger.info(f"删除旧数据库: {DB_PATH}")
        DB_PATH.unlink()

    logger.info("初始化新数据库...")
    init_db()

    logger.info(f"数据库迁移完成! 新数据库路径: {DB_PATH}")
    logger.info(f"旧数据库备份路径: {backup_dir}")


if __name__ == "__main__":
    migrate_database()

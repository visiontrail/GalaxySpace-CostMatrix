"""
Logging helper for the backend.

Tries to reuse the shared ``logger_config`` module when it is available (e.g. in
local development at the repo root). If it cannot be imported inside the Docker
container, a lightweight fallback logger with console and rotating file handlers
is provided so the application keeps running with useful logs.
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

LOG_FORMAT = "%(asctime)s - [%(levelname)s] - [%(name)s:%(funcName)s:%(lineno)d] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Fallback日志目录放在 backend/logs 下
FALLBACK_LOG_DIR = Path(__file__).resolve().parents[2] / "logs"


def _create_fallback_logger(name: str) -> logging.Logger:
    """
    创建一个简单的日志记录器（控制台 + 文件轮转），供容器内找不到 logger_config 时使用。
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    FALLBACK_LOG_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        FALLBACK_LOG_DIR / f"{name}.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


try:
    # 优先使用仓库根目录提供的 logger_config（开发环境）
    from logger_config import get_logger as _shared_get_logger  # type: ignore
except ModuleNotFoundError:
    _shared_get_logger = None


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器。优先使用共享的 logger_config，否则使用容器内的 fallback。
    """
    if _shared_get_logger:
        return _shared_get_logger(name)
    return _create_fallback_logger(name)


__all__ = ["get_logger"]

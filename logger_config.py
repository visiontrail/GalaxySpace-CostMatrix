"""
日志配置模块
提供统一的日志记录功能，支持文件输出和控制台输出
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
import os


# 日志目录
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 日志格式
LOG_FORMAT = "%(asctime)s - [%(levelname)s] - [%(name)s:%(funcName)s:%(lineno)d] - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    name: str,
    log_file: str = None,
    level: int = logging.INFO,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    配置并返回一个日志记录器
    
    Args:
        name: 日志记录器名称
        log_file: 日志文件名（不含路径）
        level: 日志级别
        max_bytes: 单个日志文件最大字节数
        backup_count: 保留的日志文件备份数量
        
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    
    # 1. 控制台处理器（输出到终端）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # 2. 文件处理器（输出到文件，支持自动轮转）
    if log_file:
        file_path = LOG_DIR / log_file
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取或创建日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        日志记录器实例
    """
    # 如果已存在，直接返回
    if name in logging.Logger.manager.loggerDict:
        return logging.getLogger(name)
    
    # 根据模块名称选择日志文件
    if name == "main":
        return setup_logger(name, "main.log")
    elif name == "data_loader":
        return setup_logger(name, "data_loader.log")
    elif name == "analysis_service":
        return setup_logger(name, "analysis_service.log")
    elif name == "export_service":
        return setup_logger(name, "export_service.log")
    else:
        return setup_logger(name, "app.log")


# 创建通用应用日志记录器
app_logger = get_logger("app")


class RequestLogger:
    """请求日志记录器，用于记录API请求的详细信息"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def log_request_start(self, request_id: str, endpoint: str, file_name: str = None):
        """记录请求开始"""
        self.logger.info(
            f"[REQUEST_START] RequestID: {request_id} | Endpoint: {endpoint} | "
            f"File: {file_name or 'N/A'}"
        )
    
    def log_request_success(self, request_id: str, duration_ms: float, message: str = ""):
        """记录请求成功"""
        self.logger.info(
            f"[REQUEST_SUCCESS] RequestID: {request_id} | Duration: {duration_ms:.2f}ms | "
            f"Message: {message}"
        )
    
    def log_request_error(self, request_id: str, duration_ms: float, error: str):
        """记录请求失败"""
        self.logger.error(
            f"[REQUEST_ERROR] RequestID: {request_id} | Duration: {duration_ms:.2f}ms | "
            f"Error: {error}"
        )
    
    def log_step(self, request_id: str, step: str, message: str):
        """记录请求处理步骤"""
        self.logger.debug(
            f"[REQUEST_STEP] RequestID: {request_id} | Step: {step} | Message: {message}"
        )


def log_exception(logger: logging.Logger, message: str, exc_info=True):
    """
    记录异常信息
    
    Args:
        logger: 日志记录器
        message: 错误描述
        exc_info: 是否包含异常堆栈信息
    """
    logger.error(message, exc_info=exc_info)


def log_performance(logger: logging.Logger, operation: str, duration_ms: float):
    """
    记录性能指标
    
    Args:
        logger: 日志记录器
        operation: 操作名称
        duration_ms: 耗时（毫秒）
    """
    logger.info(f"[PERFORMANCE] Operation: {operation} | Duration: {duration_ms:.2f}ms")


# 导出常用函数
__all__ = [
    'setup_logger',
    'get_logger',
    'app_logger',
    'RequestLogger',
    'log_exception',
    'log_performance',
    'LOG_DIR'
]


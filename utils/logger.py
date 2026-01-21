"""
日志管理模块

负责统一日志格式和管理
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

class LoggerManager:
    """
    日志管理器
    """

    def __init__(self, log_dir: str = "logs"):
        """
        初始化日志管理器

        参数：
        log_dir (str): 日志文件目录
        """
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)

    def get_logger(self, name: str, log_file: Optional[str] = None) -> logging.Logger:
        """
        获取日志记录器

        参数：
        name (str): 日志记录器名称
        log_file (str, optional): 日志文件名称

        返回：
        logging.Logger: 日志记录器
        """
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        # 避免重复添加处理器
        if not logger.handlers:
            # 控制台处理器
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

            # 文件处理器（如果指定了日志文件）
            if log_file:
                log_path = os.path.join(self.log_dir, log_file)
                file_handler = RotatingFileHandler(
                    log_path, maxBytes=10*1024*1024, backupCount=5
                )
                file_handler.setLevel(logging.DEBUG)
                file_formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                file_handler.setFormatter(file_formatter)
                logger.addHandler(file_handler)

        return logger

# 全局日志管理器实例
logger_manager = LoggerManager()

# 便捷函数
def get_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """
    获取日志记录器的便捷函数

    参数：
    name (str): 日志记录器名称
    log_file (str, optional): 日志文件名称

    返回：
    logging.Logger: 日志记录器
    """
    return logger_manager.get_logger(name, log_file)

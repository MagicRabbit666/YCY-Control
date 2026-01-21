"""
配置管理模块

负责加载、保存和管理配置文件
"""

import json
import os
from typing import Dict, Any, Optional

class ConfigManager:
    """
    配置管理器
    """

    def __init__(self, config_dir: str = "config"):
        """
        初始化配置管理器

        参数：
        config_dir (str): 配置文件目录
        """
        self.config_dir = config_dir
        os.makedirs(self.config_dir, exist_ok=True)

    def load_config(self, config_name: str) -> Dict[str, Any]:
        """
        加载配置文件

        参数：
        config_name (str): 配置文件名称（不含扩展名）

        返回：
        dict: 配置数据
        """
        config_path = os.path.join(self.config_dir, f"{config_name}.json")
        if not os.path.exists(config_path):
            return {}

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"加载配置文件失败: {e}")
            return {}

    def save_config(self, config_name: str, config_data: Dict[str, Any]) -> bool:
        """
        保存配置文件

        参数：
        config_name (str): 配置文件名称（不含扩展名）
        config_data (dict): 配置数据

        返回：
        bool: 保存是否成功
        """
        config_path = os.path.join(self.config_dir, f"{config_name}.json")

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=2)
            return True
        except IOError as e:
            print(f"保存配置文件失败: {e}")
            return False

    def get_device_config(self) -> Dict[str, Any]:
        """
        获取设备配置

        返回：
        dict: 设备配置
        """
        return self.load_config("device")

    def save_device_config(self, config_data: Dict[str, Any]) -> bool:
        """
        保存设备配置

        参数：
        config_data (dict): 设备配置

        返回：
        bool: 保存是否成功
        """
        return self.save_config("device", config_data)

    def get_random_config(self) -> Dict[str, Any]:
        """
        获取随机控制配置

        返回：
        dict: 随机控制配置
        """
        return self.load_config("random")

    def save_random_config(self, config_data: Dict[str, Any]) -> bool:
        """
        保存随机控制配置

        参数：
        config_data (dict): 随机控制配置

        返回：
        bool: 保存是否成功
        """
        return self.save_config("random", config_data)

# 全局配置管理器实例
config_manager = ConfigManager()

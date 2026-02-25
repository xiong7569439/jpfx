"""
配置加载器
统一加载所有YAML配置文件
"""

import os
import yaml
from typing import Dict, Any


class ConfigLoader:
    """配置加载器"""
    
    def __init__(self, config_dir: str = "./config"):
        self.config_dir = config_dir
        self._config: Dict[str, Any] = {}
        
    def load_all(self) -> Dict[str, Any]:
        """加载所有配置文件"""
        config_files = [
            'sites.yaml',
            'scheduler.yaml',
            'settings.yaml'
        ]
        
        for filename in config_files:
            filepath = os.path.join(self.config_dir, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data:
                        self._config.update(data)
                        
        return self._config
        
    def get(self, key: str, default=None):
        """获取配置项"""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
                
        return value
        
    @property
    def config(self) -> Dict[str, Any]:
        """获取完整配置"""
        return self._config


# 全局配置实例
_config_loader: ConfigLoader = None


def get_config(config_dir: str = "./config") -> Dict[str, Any]:
    """获取配置（单例）"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(config_dir)
        _config_loader.load_all()
    return _config_loader.config

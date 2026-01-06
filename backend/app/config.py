"""
应用配置模块
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import List
import os

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8180",
    "http://127.0.0.1:8180",
]


class Settings(BaseSettings):
    """应用配置类"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "CorpPilot"
    app_version: str = "1.0.0"
    debug: bool = True

    # CORS 配置
    allowed_origins: List[str] = DEFAULT_ALLOWED_ORIGINS.copy()

    # 文件上传配置
    upload_dir: str = "./uploads"
    max_upload_size: int = 50  # MB

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value):
        """
        支持通过环境变量 ALLOWED_ORIGINS 以逗号分隔配置，保持默认值不变。
        """
        if isinstance(value, str):
            origins = [origin.strip() for origin in value.split(",") if origin.strip()]
            return origins or DEFAULT_ALLOWED_ORIGINS
        return value


settings = Settings()

# 确保上传目录存在
os.makedirs(settings.upload_dir, exist_ok=True)

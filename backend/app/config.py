"""
应用配置模块
"""
from pathlib import Path
from typing import Annotated, List
import os
import json

from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from pydantic import Field, field_validator

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8180",
    "http://127.0.0.1:8180",
]

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INITIAL_PASSWORD_FILE = BASE_DIR.parent / "config" / "initial_admin_password.txt"


class Settings(BaseSettings):
    """应用配置类"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "CostMatrix"
    app_version: str = "1.0.0"
    debug: bool = True

    # CORS 配置
    # Keep raw env value and parse in validator so CSV and JSON array are both supported.
    allowed_origins: Annotated[List[str], NoDecode] = Field(
        default_factory=lambda: DEFAULT_ALLOWED_ORIGINS.copy()
    )

    # 认证配置
    secret_key: str = "change-me-in-env"
    access_token_expire_minutes: int = 24 * 60  # 24 小时
    jwt_algorithm: str = "HS256"
    default_admin_username: str = "admin"
    initial_admin_password_file: str = str(DEFAULT_INITIAL_PASSWORD_FILE)

    # 文件上传配置
    upload_dir: str = "./uploads"
    max_upload_size: int = 50  # MB

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value):
        """
        支持通过环境变量 ALLOWED_ORIGINS 配置：
        1) 逗号分隔字符串: a,b,c
        2) JSON 数组字符串: ["a","b","c"]
        """
        if value is None:
            return DEFAULT_ALLOWED_ORIGINS.copy()

        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return DEFAULT_ALLOWED_ORIGINS.copy()

            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    origins = [str(origin).strip() for origin in parsed if str(origin).strip()]
                    return origins or DEFAULT_ALLOWED_ORIGINS.copy()

            origins = [origin.strip() for origin in stripped.split(",") if origin.strip()]
            return origins or DEFAULT_ALLOWED_ORIGINS.copy()

        if isinstance(value, (list, tuple, set)):
            origins = [str(origin).strip() for origin in value if str(origin).strip()]
            return origins or DEFAULT_ALLOWED_ORIGINS.copy()

        return value


settings = Settings()

# 确保上传目录存在
os.makedirs(settings.upload_dir, exist_ok=True)

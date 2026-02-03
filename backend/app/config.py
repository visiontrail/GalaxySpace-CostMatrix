"""
应用配置模块
"""
from pathlib import Path
from typing import List
import os
import json

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://localhost:8180",
    "http://127.0.0.1:8180",
]

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_INITIAL_PASSWORD_FILE = BASE_DIR.parent / "config" / "initial_admin_password.txt"


def _safe_json_loads(value):
    """Be tolerant of non-JSON env values for complex fields.

    Pydantic will try to JSON-decode values for complex types (e.g. List[str])
    before validators run. In our deployments we often set `ALLOWED_ORIGINS`
    as a simple comma-separated string; that raises `JSONDecodeError` during
    the pre-parsing step. Returning the raw value on decode failure lets our
    field validator handle the flexible formats we support.
    """

    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if not stripped:
        return value

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


class Settings(BaseSettings):
    """应用配置类"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        json_loads=_safe_json_loads,
    )

    app_name: str = "CostMatrix"
    app_version: str = "1.0.0"
    debug: bool = True

    # CORS 配置
    allowed_origins: List[str] = DEFAULT_ALLOWED_ORIGINS.copy()

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
        支持通过环境变量 ALLOWED_ORIGINS 以逗号分隔配置，保持默认值不变。
        """
        if isinstance(value, str):
            origins = [origin.strip() for origin in value.split(",") if origin.strip()]
            return origins or DEFAULT_ALLOWED_ORIGINS
        return value


settings = Settings()

# 确保上传目录存在
os.makedirs(settings.upload_dir, exist_ok=True)

"""Application configuration settings."""

import secrets
import typing as t
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Canventory"
    app_version: str = "1.0.0"
    app_url: str = "http://localhost:8000"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./canventory.db"

    # Authentication
    secret_key: str = secrets.token_urlsafe(32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # Image storage
    image_storage: t.Literal["filesystem", "database"] = "filesystem"
    image_upload_dir: Path = Path("./uploads/images")
    max_image_size_mb: int = 5

    # Expiration alerts
    expiration_warning_days: int = (
        7  # Warn when items expire within this many days
    )
    expiration_critical_days: int = (
        3  # Critical alert when items expire within this
    )
    check_expiration_interval_hours: int = (
        24  # How often to check for expiring items
    )

    # CORS
    cors_origins: t.List[str] = ["*"]

    # Email notifications (optional)
    smtp_enabled: bool = False
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "canventory@localhost"


SETTINGS = Settings()

# Ensure upload directory exists
SETTINGS.image_upload_dir.mkdir(parents=True, exist_ok=True)

"""Global variables."""

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.core.config import SETTINGS

TEMPLATES = Jinja2Templates(directory="app/templates")

OPENAPI_TAGS = [
    {
        "name": "Authentication",
        "description": (
            "User authentication, registration," " and account management"
        ),
    },
    {
        "name": "Food Items",
        "description": "CRUD operations for food items in your inventory",
    },
    {
        "name": "Categories",
        "description": "Manage food item categories",
    },
    {
        "name": "Notifications",
        "description": "Email notification settings and alerts",
    },
    {
        "name": "Health",
        "description": "Application health check endpoints",
    },
]

THUMBNAIL_SIZE: tuple[int, int] = (300, 300)
THUMBNAIL_QUALITY: int = 90
THUMBNAIL_DIR: Path = SETTINGS.image_upload_dir / "thumbnails"
THUMBNAIL_DIR.mkdir(parents=True, exist_ok=True)

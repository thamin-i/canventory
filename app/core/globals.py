"""Global variables."""

from fastapi.templating import Jinja2Templates

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

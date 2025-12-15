"""Routers package."""

from app.routers.api import ROUTER as api_router
from app.routers.web import ROUTER as web_router

__all__ = ["api_router", "web_router"]

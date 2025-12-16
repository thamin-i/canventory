"""API routes package."""

from fastapi import APIRouter

from app.routers.api import auth, categories, items, notifications

# Create main API router with /api prefix
ROUTER = APIRouter(prefix="/api")

# Include all sub-routers
ROUTER.include_router(auth.ROUTER)
ROUTER.include_router(categories.ROUTER)
ROUTER.include_router(items.ROUTER)
ROUTER.include_router(notifications.ROUTER)

__all__ = ["ROUTER", "auth", "categories", "items", "notifications"]

"""API routes package."""

from fastapi import APIRouter

from app.routers.api import (
    auth,
    categories,
    homes,
    items,
    locations,
    notifications,
)

# Create main API router with /api prefix
ROUTER = APIRouter(prefix="/api")

# Include all sub-routers
ROUTER.include_router(auth.ROUTER)
ROUTER.include_router(categories.ROUTER)
ROUTER.include_router(homes.ROUTER)
ROUTER.include_router(items.ROUTER)
ROUTER.include_router(locations.ROUTER)
ROUTER.include_router(notifications.ROUTER)

__all__ = [
    "auth",
    "categories",
    "homes",
    "items",
    "locations",
    "notifications",
    "ROUTER",
]

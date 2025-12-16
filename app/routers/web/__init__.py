"""Web frontend routes package."""

from fastapi import APIRouter

from app.routers.web import admin, auth, dashboard, items, settings

# Create main router
ROUTER: APIRouter = APIRouter(prefix="/web", include_in_schema=False)

# Include all sub-routers
ROUTER.include_router(auth.ROUTER)
ROUTER.include_router(dashboard.ROUTER)
ROUTER.include_router(items.ROUTER)
ROUTER.include_router(admin.ROUTER)
ROUTER.include_router(settings.ROUTER)

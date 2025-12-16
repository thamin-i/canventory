"""FastAPI application entry point."""

import logging
import typing as t
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import SETTINGS
from app.core.database import ASYNC_SESSION_MAKER, close_db, init_db
from app.core.globals import OPENAPI_TAGS
from app.routers import api_router, web_router
from app.services.expiration_checker import check_expiring_items_task
from app.services.init_service import initialize_database

logging.basicConfig(
    level=logging.DEBUG if SETTINGS.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
LOGGER: logging.Logger = logging.getLogger(__name__)

SCHEDULER: AsyncIOScheduler = AsyncIOScheduler()

STATIC_DIR: Path = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI) -> t.AsyncGenerator[None, None]:
    """Application lifespan events.

    args:
        _ (FastAPI): The FastAPI application instance.
    """
    LOGGER.info("Starting Canventory API...")
    await init_db()
    LOGGER.info("Database tables initialized")

    async with ASYNC_SESSION_MAKER() as session:
        await initialize_database(session)

    SCHEDULER.add_job(
        check_expiring_items_task,
        trigger=IntervalTrigger(hours=SETTINGS.check_expiration_interval_hours),
        id="expiration_check",
        name="Check for expiring items",
        replace_existing=True,
    )
    SCHEDULER.start()
    LOGGER.info(
        "Expiration checker scheduled to run every %d hours",
        SETTINGS.check_expiration_interval_hours,
    )

    await check_expiring_items_task()

    yield

    LOGGER.info("Shutting down Canventory...")
    SCHEDULER.shutdown(wait=False)
    await close_db()
    LOGGER.info("Cleanup complete")


APPLICATION: FastAPI = FastAPI(
    title=SETTINGS.app_name,
    description="Canventory - Track and manage your food inventory",
    version=SETTINGS.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=OPENAPI_TAGS,
)

APPLICATION.add_middleware(
    CORSMiddleware,
    allow_origins=SETTINGS.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    APPLICATION.mount(
        "/static", StaticFiles(directory=STATIC_DIR), name="static"
    )

APPLICATION.include_router(api_router)
APPLICATION.include_router(web_router)


@APPLICATION.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Root endpoint - redirect to web interface.

    Returns:
        RedirectResponse: A redirect response to the web login page.
    """
    return RedirectResponse(url="/web/login", status_code=303)


@APPLICATION.get("/health", tags=["Health"])
async def health_check() -> t.Dict[str, str]:
    """Health check endpoint for monitoring.

    Returns:
        t.Dict[str, str]: A dictionary indicating the health status.
    """
    return {"status": "healthy"}


@APPLICATION.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    """Serve favicon from root path for browser compatibility.

    Returns:
        FileResponse: The favicon file response.
    """
    return FileResponse(STATIC_DIR / "icons/icon.svg")

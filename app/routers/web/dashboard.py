"""Web dashboard routes (home-scoped)."""

import typing as t

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_web_user
from app.core.database import get_db
from app.core.globals import TEMPLATES
from app.core.models import Home, User
from app.schemas.home import HomeSimple
from app.services import HomeService
from app.services.item_service import (
    CanventoryStats,
    ExpirationAlertSummary,
    FoodItemListResponse,
    ItemService,
)
from app.utils.categories import get_categories, get_category_icons
from app.utils.locations import get_locations

ROUTER: APIRouter = APIRouter()


@ROUTER.get("/dashboard", response_class=HTMLResponse, response_model=None)
async def dashboard(  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals,line-too-long  # noqa: E501
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    search: str | None = None,
    category: str | None = None,
    location: str | None = None,
    status: str | None = None,
    sort: str = "expiration_asc",
    page: int = Query(1, ge=1),
) -> RedirectResponse | HTMLResponse:
    """Render main dashboard.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.
        search (str | None): Optional search term to filter items by name.
        category (str | None): Optional category to filter items.
        location (str | None): Optional location filter ('none' or location ID).
        status (str | None): Optional expiration status to filter items.
        sort (str): Sorting option for items.
        page (int): Page number for pagination.

    Returns:
        RedirectResponse | HTMLResponse:
            The rendered dashboard page or a redirect to login.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    home_service: HomeService = HomeService(db)
    user_homes: t.List[HomeSimple] = await home_service.list_user_homes(user)

    if not user_homes:
        return RedirectResponse(
            url=(
                "/web/homes?message="
                "Welcome! Create your first home to get started."
            ),
            status_code=303,
        )

    if user.current_home_id is None:
        user.current_home_id = user_homes[0].id
        await db.flush()

    home_id: int = user.current_home_id
    current_home: Home | None = await home_service.get_user_current_home(user)

    search = search or None
    category = category or None
    status = status or None

    location_id: int | None = None
    location_filter: str | None = None
    if location == "none":
        location_filter = "none"
    elif location:
        try:
            location_id = int(location)
        except ValueError:
            pass

    service: ItemService = ItemService(db, home_id)

    result: FoodItemListResponse = await service.list_items(
        name=search,
        category=category,
        location_id=location_id,
        location_filter=location_filter,
        page=page,
        page_size=12,
        sort=sort,
    )

    items_data: t.List[t.Dict[str, t.Any]] = [
        item.model_dump() for item in result.items
    ]

    if status is not None:
        items_data = [
            i for i in items_data if i["expiration_status"].value == status
        ]
        total_items = len(items_data)
        total_pages = max(1, (total_items + 12 - 1) // 12)
    else:
        total_pages = result.total_pages

    stats_data: CanventoryStats = await service.get_statistics()
    alerts_data: ExpirationAlertSummary = await service.get_expiration_alerts()

    stats: t.Dict[str, t.Any] = {
        "total_items": stats_data.total_items,
        "total_quantity": stats_data.total_quantity,
        "expiration_summary": stats_data.expiration_summary,
    }

    alerts: t.Dict[str, t.Any] = {
        "warning_count": alerts_data.warning_count,
        "critical_count": alerts_data.critical_count,
        "expired_count": alerts_data.expired_count,
    }

    return TEMPLATES.TemplateResponse(
        "pages/dashboard.html",
        {
            "request": request,
            "user": user,
            "items": items_data,
            "stats": stats,
            "alerts": alerts,
            "categories": await get_categories(db, home_id),
            "category_icons": await get_category_icons(db, home_id),
            "locations": await get_locations(db, home_id),
            "search": search,
            "category": category,
            "location": location,
            "status": status,
            "sort": sort,
            "page": page,
            "total_pages": total_pages,
            "current_home": current_home,
            "user_homes": user_homes,
        },
    )

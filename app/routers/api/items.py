"""Food items CRUD endpoints (home-scoped)."""

import typing as t

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_active_user
from app.core.database import get_db
from app.core.models import ExpirationStatus, User
from app.schemas.alert import ExpirationAlertSummary
from app.schemas.food_item import (
    FoodItemCreate,
    FoodItemListResponse,
    FoodItemResponse,
    FoodItemUpdate,
)
from app.schemas.statistics import CanventoryStats
from app.services import (
    ImageTooLargeError,
    InvalidImageError,
    ItemNotFoundError,
    ItemService,
)
from app.utils.home_membership import get_home_id_and_check_membership
from app.utils.images import get_food_item_image

ROUTER = APIRouter(prefix="/items", tags=["Food Items"])


@ROUTER.get("", response_model=FoodItemListResponse)
async def list_items(  # pylint: disable=too-many-arguments,too-many-positional-arguments,line-too-long  # noqa: E501
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
    name: str | None = Query(
        None, description="Filter by name (partial match)"
    ),
    category: str | None = Query(None, description="Filter by category value"),
    location_id: int | None = Query(
        None, description="Filter by storage location ID"
    ),
    location_filter: str | None = Query(
        None, description="Special filter: 'none' for items without a location"
    ),
    expiration_status: ExpirationStatus | None = Query(
        None, description="Filter by expiration status"
    ),
    expiring_within_days: int | None = Query(
        None, ge=0, description="Filter items expiring within N days"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
) -> FoodItemListResponse:
    """List all food items in the current home with optional filters.

    Args:
        db (AsyncSession):
            The database session.
        current_user (User):
            The currently authenticated user.
        name (str | None):
            Filter by name (partial match).
        category (str | None):
            Filter by category value.
        location_id (int | None):
            Filter by storage location ID.
        location_filter (str | None):
            Special filter: 'none' for items without a location.
        expiration_status (ExpirationStatus | None):
            Filter by expiration status.
        expiring_within_days (int | None):
            Filter items expiring within N days.
        page (int):
            Page number for pagination.
        page_size (int):
            Number of items per page.

    Returns:
        FoodItemListResponse: Paginated list of food items.
    """
    home_id: int = await get_home_id_and_check_membership(db, current_user)

    return await ItemService(db, home_id).list_items(
        name=name,
        category=category,
        location_id=location_id,
        location_filter=location_filter,
        expiration_status=expiration_status,
        expiring_within_days=expiring_within_days,
        page=page,
        page_size=page_size,
    )


@ROUTER.get("/alerts", response_model=ExpirationAlertSummary)
async def get_expiration_alerts(
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> ExpirationAlertSummary:
    """Get a summary of items with expiration alerts in the current home.

    Args:
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        ExpirationAlertSummary: Summary of expiration alerts.
    """
    home_id: int = await get_home_id_and_check_membership(db, current_user)

    return await ItemService(db, home_id).get_expiration_alerts()


@ROUTER.get("/stats", response_model=CanventoryStats)
async def get_statistics(
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> CanventoryStats:
    """Get overall statistics for the current home.

    Args:
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        CanventoryStats: The food closet statistics.
    """
    home_id: int = await get_home_id_and_check_membership(db, current_user)

    return await ItemService(db, home_id).get_statistics()


@ROUTER.get("/{item_id}", response_model=FoodItemResponse)
async def get_item(
    item_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> FoodItemResponse:
    """Get a specific food item by ID.

    Args:
        item_id (int): The ID of the food item.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        FoodItemResponse: The food item data.
    """
    home_id: int = await get_home_id_and_check_membership(db, current_user)

    try:
        return await ItemService(db, home_id).get_item(item_id)
    except ItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@ROUTER.get("/{item_id}/image", response_model=None)
async def get_item_image(
    item_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
    thumbnail: bool = False,
) -> FileResponse | Response:
    """Get the image for a food item.

    Args:
        item_id (int): The ID of the food item.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.
        thumbnail (bool): Whether to return a smaller thumbnail version.

    Returns:
        FileResponse | Response: The image file response or empty response.
    """
    home_id: int = await get_home_id_and_check_membership(db, current_user)

    return await get_food_item_image(
        item_id, db, home_id=home_id, thumbnail=thumbnail
    )


@ROUTER.post(
    "", response_model=FoodItemResponse, status_code=status.HTTP_201_CREATED
)
async def create_item(
    item_data: FoodItemCreate,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> FoodItemResponse:
    """Create a new food item in the current home.

    Args:
        item_data (FoodItemCreate): The food item data.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        FoodItemResponse: The created food item data.
    """
    home_id: int = await get_home_id_and_check_membership(db, current_user)

    try:
        return await ItemService(db, home_id).create_item(
            name=item_data.name,
            quantity=item_data.quantity,
            expiration_date=item_data.expiration_date,
            user_id=current_user.id,
            category=item_data.category,
            location_id=item_data.location_id,
            description=item_data.description,
            image_base64=item_data.image_base64,
        )
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image size exceeds maximum of {exc.max_size_mb}MB",
        ) from exc
    except InvalidImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@ROUTER.put("/{item_id}", response_model=FoodItemResponse)
async def update_item(
    item_id: int,
    item_data: FoodItemUpdate,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> FoodItemResponse:
    """Update an existing food item.

    Args:
        item_id (int): The ID of the food item.
        item_data (FoodItemUpdate): The updated food item data.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        FoodItemResponse: The updated food item data.
    """
    home_id: int = await get_home_id_and_check_membership(db, current_user)

    try:
        return await ItemService(db, home_id).update_item(
            item_id=item_id,
            name=item_data.name,
            quantity=item_data.quantity,
            expiration_date=item_data.expiration_date,
            category=item_data.category,
            location_id=item_data.location_id,
            clear_location=item_data.clear_location or False,
            description=item_data.description,
            image_base64=item_data.image_base64,
            remove_image=item_data.remove_image or False,
        )
    except ItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ImageTooLargeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image size exceeds maximum of {exc.max_size_mb}MB",
        ) from exc
    except InvalidImageError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@ROUTER.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Delete a food item.

    Args:
        item_id (int): The ID of the food item.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.
    """
    try:
        await ItemService(
            db,
            await get_home_id_and_check_membership(db, current_user),
        ).delete_item(item_id)
    except ItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

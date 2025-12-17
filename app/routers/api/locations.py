"""Storage locations CRUD endpoints (home-scoped)."""

import typing as t

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_active_user
from app.core.database import get_db
from app.core.models import StorageLocation, User
from app.schemas.location import (
    LocationCreate,
    LocationListResponse,
    LocationResponse,
)
from app.services import (
    LocationInUseError,
    LocationNameExistsError,
    LocationNotFoundError,
    LocationService,
)
from app.utils.home_membership import get_home_id_and_check_membership

ROUTER = APIRouter(prefix="/locations", tags=["Storage Locations"])


@ROUTER.get("", response_model=LocationListResponse)
async def list_locations(
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> LocationListResponse:
    """List all storage locations in the current home.

    Args:
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        LocationListResponse: List of storage locations.
    """
    home_id: int = await get_home_id_and_check_membership(db, current_user)

    locations: t.List[StorageLocation] = await LocationService(
        db, home_id
    ).list_locations()
    return LocationListResponse(
        locations=[
            LocationResponse(
                id=loc.id,
                name=loc.name,
                created_at=loc.created_at,
            )
            for loc in locations
        ],
        total=len(locations),
    )


@ROUTER.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> LocationResponse:
    """Get a specific storage location by ID.

    Args:
        location_id (int): The ID of the location.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        LocationResponse: The storage location data.
    """
    home_id: int = await get_home_id_and_check_membership(db, current_user)

    try:
        location: StorageLocation = await LocationService(
            db, home_id
        ).get_location(location_id)
        return LocationResponse(
            id=location.id,
            name=location.name,
            created_at=location.created_at,
        )
    except LocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@ROUTER.post(
    "", response_model=LocationResponse, status_code=status.HTTP_201_CREATED
)
async def create_location(
    location_data: LocationCreate,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> LocationResponse:
    """Create a new storage location in the current home.

    Args:
        location_data (LocationCreate): The location data.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        LocationResponse: The created location data.
    """
    home_id: int = await get_home_id_and_check_membership(db, current_user)

    try:
        location: StorageLocation = await LocationService(
            db, home_id
        ).create_location(name=location_data.name)
        return LocationResponse(
            id=location.id,
            name=location.name,
            created_at=location.created_at,
        )
    except LocationNameExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@ROUTER.put("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: int,
    location_data: LocationCreate,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> LocationResponse:
    """Update an existing storage location.

    Args:
        location_id (int): The ID of the location.
        location_data (LocationCreate): The updated location data.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        LocationResponse: The updated location data.
    """
    try:
        location: StorageLocation = await LocationService(
            db,
            await get_home_id_and_check_membership(db, current_user),
        ).update_location(
            location_id=location_id,
            name=location_data.name,
        )
        return LocationResponse(
            id=location.id,
            name=location.name,
            created_at=location.created_at,
        )
    except LocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LocationNameExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@ROUTER.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
    force: bool = False,
) -> None:
    """Delete a storage location.

    Args:
        location_id (int): The ID of the location.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.
        force (bool): If True, remove location from items and delete.
    """
    try:
        await LocationService(
            db,
            await get_home_id_and_check_membership(db, current_user),
        ).delete_location(location_id, force=force)
    except LocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LocationInUseError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

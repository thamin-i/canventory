"""Categories CRUD API endpoints."""

import typing as t

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_active_user
from app.core.database import get_db
from app.core.models import Category, User
from app.schemas.category import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdate,
)
from app.services import (
    CategoryInUseError,
    CategoryNotFoundError,
    CategoryService,
    CategoryValueExistsError,
)

ROUTER = APIRouter(prefix="/categories", tags=["Categories"])


@ROUTER.post(
    "", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED
)
async def create_category(
    category_data: CategoryCreate,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> CategoryResponse:
    """Create a new category.

    Args:
        category_data (CategoryCreate): The category data.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        CategoryResponse: The created category data.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create categories",
        )

    try:
        category: Category = await CategoryService(db).create_category(
            value=category_data.value,
            label=category_data.label,
            icon=category_data.icon,
            sort_order=category_data.sort_order,
        )
        return CategoryResponse.model_validate(category)
    except CategoryValueExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@ROUTER.get("/{category_id}", response_model=CategoryResponse)
async def get_category(
    category_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[  # pylint: disable=unused-argument
        User, Depends(get_current_active_user)
    ],
) -> CategoryResponse:
    """Get a specific category by ID.

    Args:
        category_id (int): The ID of the category.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        CategoryResponse: The category data.
    """
    try:
        category: Category = await CategoryService(db).get_category(category_id)
        return CategoryResponse.model_validate(category)
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@ROUTER.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: int,
    category_data: CategoryUpdate,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> CategoryResponse:
    """Update an existing category.

    Args:
        category_id (int): The ID of the category.
        category_data (CategoryUpdate): The updated category data.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        CategoryResponse: The updated category data.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update categories",
        )

    try:
        category: Category = await CategoryService(db).update_category(
            category_id=category_id,
            label=category_data.label,
            icon=category_data.icon,
            sort_order=category_data.sort_order,
        )
        return CategoryResponse.model_validate(category)
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@ROUTER.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
    force: bool = Query(
        False,
        description="Force delete and reassign items to 'other' category",
    ),
) -> None:
    """Delete a category.

    Args:
        category_id (int): The ID of the category.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.
        force (bool): If True, reassign items to 'other' before deletion.
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete categories",
        )

    try:
        await CategoryService(db).delete_category(category_id, force=force)
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except CategoryInUseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@ROUTER.get("", response_model=CategoryListResponse)
async def list_categories(
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[  # pylint: disable=unused-argument
        User, Depends(get_current_active_user)
    ],
) -> CategoryListResponse:
    """List all categories.

    Args:
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        CategoryListResponse: List of all categories.
    """
    categories: list[Category] = await CategoryService(db).list_categories()
    return CategoryListResponse(
        categories=[CategoryResponse.model_validate(cat) for cat in categories],
        total=len(categories),
    )


@ROUTER.get("/{category_id}/item-count", response_model=int)
async def get_category_item_count(
    category_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[  # pylint: disable=unused-argument
        User, Depends(get_current_active_user)
    ],
) -> int:
    """Get the number of items using a category.

    Args:
        category_id (int): The ID of the category.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        int: The number of items using this category.
    """
    try:
        return await CategoryService(db).get_category_item_count(category_id)
    except CategoryNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

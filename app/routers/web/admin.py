"""Web admin routes."""

import os
import typing as t

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    get_current_web_user,
    get_password_hash,
    get_user_by_email,
    get_user_by_username,
    is_registration_enabled,
    set_registration_enabled,
)
from app.core.database import get_db
from app.core.globals import TEMPLATES
from app.core.models import Category, FoodItem, User
from app.services import (
    CategoryInUseError,
    CategoryNotFoundError,
    CategoryService,
    CategoryValueExistsError,
)

ROUTER: APIRouter = APIRouter()


@ROUTER.get("/admin", response_class=HTMLResponse, response_model=None)
async def admin_page(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    message: str | None = None,
    error: str | None = None,
) -> RedirectResponse | HTMLResponse:
    """Render admin panel.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.
        message (str | None): Optional success message.
        error (str | None): Optional error message.

    Returns:
        RedirectResponse | HTMLResponse:
            The admin page or a redirect if unauthorized.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)
    if not user.is_admin:
        return RedirectResponse(url="/web/dashboard", status_code=303)

    users: t.Sequence[User] = (
        (await db.execute(select(User).order_by(User.id))).scalars().all()
    )

    categories: t.List[Category] = await CategoryService(db).list_categories()

    item_counts_result: t.Sequence[Row[t.Tuple[str, int]]] = (
        await db.execute(
            select(
                FoodItem.category,
                func.count(FoodItem.id),  # pylint: disable=not-callable
            ).group_by(FoodItem.category)
        )
    ).fetchall()
    category_item_counts: t.Dict[str, int] = {
        row[0]: row[1] for row in item_counts_result
    }

    registration_enabled: bool = await is_registration_enabled(db)

    return TEMPLATES.TemplateResponse(
        "pages/admin.html",
        {
            "request": request,
            "user": user,
            "users": users,
            "categories": categories,
            "category_item_counts": category_item_counts,
            "message": message,
            "error": error,
            "registration_enabled": registration_enabled,
        },
    )


@ROUTER.post("/admin/users/create")
async def admin_create_user(  # pylint: disable=too-many-arguments,too-many-positional-arguments,line-too-long  # noqa: E501
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    is_admin: str = Form("0"),
) -> RedirectResponse:
    """Create a new user (admin only).

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.
        username (str): The new user's username.
        email (str): The new user's email.
        password (str): The new user's password.
        is_admin (str): "1" if the user should be an admin, else "0".

    Returns:
        RedirectResponse: Redirect to admin page with status message.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None or not user.is_admin:
        return RedirectResponse(url="/web/login", status_code=303)

    if await get_user_by_username(db, username):
        return RedirectResponse(
            url="/web/admin?error=Username already exists", status_code=303
        )

    if await get_user_by_email(db, email):
        return RedirectResponse(
            url="/web/admin?error=Email already exists", status_code=303
        )

    db.add(
        User(
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            is_admin=(is_admin == "1"),
        )
    )
    await db.flush()

    return RedirectResponse(
        url=f"/web/admin?message=User {username} created successfully",
        status_code=303,
    )


@ROUTER.post("/admin/users/{user_id}/activate")
async def admin_activate_user(
    request: Request,
    user_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Activate a user.

    Args:
        request (Request): The incoming request.
        user_id (int): The ID of the user to activate.
        db (AsyncSession): The database session.

    Returns:
        RedirectResponse: Redirect to admin page with status message.
    """
    admin: User | None = await get_current_web_user(request, db)
    if admin is None or not admin.is_admin:
        return RedirectResponse(url="/web/login", status_code=303)

    target_user: User | None = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()

    if target_user is not None:
        target_user.is_active = True
        await db.flush()

    return RedirectResponse(
        url="/web/admin?message=User activated", status_code=303
    )


@ROUTER.post("/admin/users/{user_id}/deactivate")
async def admin_deactivate_user(
    request: Request,
    user_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Deactivate a user.

    Args:
        request (Request): The incoming request.
        user_id (int): The ID of the user to deactivate.
        db (AsyncSession): The database session.

    Returns:
        RedirectResponse: Redirect to admin page with status message.
    """
    admin: User | None = await get_current_web_user(request, db)
    if admin is None or not admin.is_admin:
        return RedirectResponse(url="/web/login", status_code=303)

    if user_id == admin.id:
        return RedirectResponse(
            url="/web/admin?error=Cannot deactivate yourself", status_code=303
        )

    target_user: User | None = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()

    if target_user is not None:
        target_user.is_active = False
        await db.flush()

    return RedirectResponse(
        url="/web/admin?message=User deactivated", status_code=303
    )


@ROUTER.post("/admin/users/{user_id}/promote")
async def admin_promote_user(
    request: Request,
    user_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Promote a user to admin.

    Args:
        request (Request): The incoming request.
        user_id (int): The ID of the user to promote.
        db (AsyncSession): The database session.

    Returns:
        RedirectResponse: Redirect to admin page with status message.
    """
    admin: User | None = await get_current_web_user(request, db)
    if admin is None or not admin.is_admin:
        return RedirectResponse(url="/web/login", status_code=303)

    target_user: User | None = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()

    if target_user is not None:
        target_user.is_admin = True
        await db.flush()

    return RedirectResponse(
        url="/web/admin?message=User promoted to admin", status_code=303
    )


@ROUTER.post("/admin/users/{user_id}/demote")
async def admin_demote_user(
    request: Request,
    user_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Remove admin rights from a user.

    Args:
        request (Request): The incoming request.
        user_id (int): The ID of the user to demote.
        db (AsyncSession): The database session.

    Returns:
        RedirectResponse: Redirect to admin page with status message.
    """
    admin: User | None = await get_current_web_user(request, db)
    if admin is None or not admin.is_admin:
        return RedirectResponse(url="/web/login", status_code=303)

    if user_id == admin.id:
        return RedirectResponse(
            url="/web/admin?error=Cannot demote yourself", status_code=303
        )

    target_user: User | None = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()

    if target_user is not None:
        target_user.is_admin = False
        await db.flush()

    return RedirectResponse(
        url="/web/admin?message=Admin rights removed", status_code=303
    )


@ROUTER.post("/admin/users/{user_id}/delete")
async def admin_delete_user(
    request: Request,
    user_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Delete a user.

    Args:
        request (Request): The incoming request.
        user_id (int): The ID of the user to delete.
        db (AsyncSession): The database session.

    Returns:
        RedirectResponse: Redirect to admin page with status message.
    """
    admin: User | None = await get_current_web_user(request, db)
    if admin is None or not admin.is_admin:
        return RedirectResponse(url="/web/login", status_code=303)

    if user_id == admin.id:
        return RedirectResponse(
            url="/web/admin?error=Cannot delete yourself", status_code=303
        )

    target_user: User | None = (
        await db.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()

    if target_user is not None:
        items_result: t.Sequence[FoodItem] = (
            (
                await db.execute(
                    select(FoodItem).where(FoodItem.created_by == user_id)
                )
            )
            .scalars()
            .all()
        )
        for item in items_result:
            if item.image_path and os.path.exists(item.image_path):
                os.remove(item.image_path)
            await db.delete(item)

        await db.delete(target_user)
        await db.flush()

    return RedirectResponse(
        url="/web/admin?message=User deleted", status_code=303
    )


@ROUTER.post("/admin/settings/registration/toggle")
async def admin_toggle_registration(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Toggle user registration on/off.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.

    Returns:
        RedirectResponse: Redirect to admin page with status message.
    """
    admin: User | None = await get_current_web_user(request, db)
    if admin is None or not admin.is_admin:
        return RedirectResponse(url="/web/login", status_code=303)

    current_state: bool = await is_registration_enabled(db)
    await set_registration_enabled(db, not current_state)

    status_text: str = "enabled" if not current_state else "disabled"
    return RedirectResponse(
        url=f"/web/admin?message=User registration {status_text}",
        status_code=303,
    )


@ROUTER.post("/admin/categories/create")
async def admin_create_category(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    value: str = Form(...),
    label: str = Form(...),
    icon: str = Form(...),
) -> RedirectResponse:
    """Create a new category (admin only).

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.
        value (str): The unique value identifier.
        label (str): The display label.
        icon (str): The emoji icon.

    Returns:
        RedirectResponse: Redirect to admin page with status message.
    """
    admin: User | None = await get_current_web_user(request, db)
    if admin is None or not admin.is_admin:
        return RedirectResponse(url="/web/login", status_code=303)

    # Get the next sort order (add at the end)
    max_sort_result = await db.execute(
        select(func.coalesce(func.max(Category.sort_order), -1))
    )
    next_sort_order = (max_sort_result.scalar() or -1) + 1

    try:
        await CategoryService(db).create_category(
            value=value.lower().replace(" ", "_"),
            label=label,
            icon=icon,
            sort_order=next_sort_order,
        )
        return RedirectResponse(
            url=f"/web/admin?message=Category '{label}' created successfully",
            status_code=303,
        )
    except CategoryValueExistsError:
        return RedirectResponse(
            url=f"/web/admin?error=Category value '{value}' already exists",
            status_code=303,
        )


@ROUTER.post("/admin/categories/{category_id}/update")
async def admin_update_category(
    request: Request,
    category_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    label: str = Form(...),
    icon: str = Form(...),
) -> RedirectResponse:
    """Update an existing category (admin only).

    Args:
        request (Request): The incoming request.
        category_id (int): The ID of the category to update.
        db (AsyncSession): The database session.
        label (str): The new display label.
        icon (str): The new emoji icon.

    Returns:
        RedirectResponse: Redirect to admin page with status message.
    """
    admin: User | None = await get_current_web_user(request, db)
    if admin is None or not admin.is_admin:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        await CategoryService(db).update_category(
            category_id=category_id,
            label=label,
            icon=icon,
        )
        return RedirectResponse(
            url=f"/web/admin?message=Category '{label}' updated successfully",
            status_code=303,
        )
    except CategoryNotFoundError:
        return RedirectResponse(
            url="/web/admin?error=Category not found",
            status_code=303,
        )


@ROUTER.post("/admin/categories/{category_id}/delete")
async def admin_delete_category(
    request: Request,
    category_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    force: str = Form("0"),
) -> RedirectResponse:
    """Delete a category (admin only).

    Args:
        request (Request): The incoming request.
        category_id (int): The ID of the category to delete.
        db (AsyncSession): The database session.
        force (str): "1" to force delete and reassign items.

    Returns:
        RedirectResponse: Redirect to admin page with status message.
    """
    admin: User | None = await get_current_web_user(request, db)
    if admin is None or not admin.is_admin:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        await CategoryService(db).delete_category(
            category_id, force=(force == "1")
        )
        return RedirectResponse(
            url="/web/admin?message=Category deleted successfully",
            status_code=303,
        )
    except CategoryNotFoundError:
        return RedirectResponse(
            url="/web/admin?error=Category not found",
            status_code=303,
        )
    except CategoryInUseError as exc:
        return RedirectResponse(
            url=f"/web/admin?error={exc}. Use force delete to reassign items.",
            status_code=303,
        )


@ROUTER.post("/admin/categories/reorder")
async def admin_reorder_categories(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Reorder categories via drag-and-drop (admin only).

    Args:
        request (Request): The incoming request containing JSON body.
        db (AsyncSession): The database session.

    Returns:
        JSONResponse: Success or error response.
    """
    admin: User | None = await get_current_web_user(request, db)
    if admin is None or not admin.is_admin:
        return JSONResponse(
            status_code=403,
            content={"error": "Unauthorized"},
        )

    try:
        body = await request.json()
        categories_order = body.get("categories", [])

        service = CategoryService(db)
        for item in categories_order:
            category_id = item.get("id")
            sort_order = item.get("sort_order")
            if category_id is not None and sort_order is not None:
                await service.update_category(
                    category_id=category_id,
                    sort_order=sort_order,
                )

        await db.commit()
        return JSONResponse(content={"success": True})

    except Exception as exc:  # pylint: disable=broad-except
        return JSONResponse(
            status_code=500,
            content={"error": str(exc)},
        )

"""Web home management routes."""

import typing as t

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import Row, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_web_user
from app.core.database import get_db
from app.core.globals import TEMPLATES
from app.core.models import Category, FoodItem, User
from app.schemas.home import (
    HomeDetailResponse,
    HomeMemberResponse,
    HomeSimple,
    PendingInvitationResponse,
)
from app.services import (
    CannotLeaveOwnedHomeError,
    CannotRemoveOwnerError,
    CategoryInUseError,
    CategoryNotFoundError,
    CategoryService,
    CategoryValueExistsError,
    HomeAlreadyExistsError,
    HomeNotFoundError,
    HomeService,
    InvitationAlreadyProcessedError,
    InvitationNotFoundError,
    NotHomeMemberError,
    NotHomeOwnerError,
    UserAlreadyMemberError,
    UserNotFoundError,
)

ROUTER: APIRouter = APIRouter()


@ROUTER.get("/homes", response_class=HTMLResponse, response_model=None)
async def homes_page(  # pylint: disable=too-many-locals
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    message: str | None = None,
    error: str | None = None,
) -> RedirectResponse | HTMLResponse:
    """Render homes management page.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.
        message (str | None): Optional success message.
        error (str | None): Optional error message.

    Returns:
        RedirectResponse | HTMLResponse:
            The homes page or a redirect if not authenticated.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    home_service: HomeService = HomeService(db)
    homes: t.List[HomeSimple] = await home_service.list_user_homes(user)

    pending_invitations: t.List[PendingInvitationResponse] = (
        await home_service.list_pending_invitations(user)
    )

    current_home: HomeDetailResponse | None = None
    current_home_members: t.List[HomeMemberResponse] = []
    current_home_categories: t.List[Category] = []
    category_item_counts: t.Dict[int, int] = {}
    is_current_home_owner: bool = False
    if user.current_home_id:
        try:
            current_home_detail: HomeDetailResponse = (
                await home_service.get_home_detail(user.current_home_id, user)
            )
            current_home = current_home_detail
            current_home_members = current_home_detail.members
            is_current_home_owner = await home_service.is_owner(
                user.current_home_id, user.id
            )

            current_home_categories = list(
                (
                    await db.execute(
                        select(Category)
                        .where(Category.home_id == user.current_home_id)
                        .order_by(Category.sort_order)
                    )
                )
                .scalars()
                .all()
            )
            item_counts_result: t.Sequence[Row[t.Tuple[str, int]]] = (
                await db.execute(
                    select(
                        FoodItem.category,
                        func.count(FoodItem.id),  # pylint: disable=not-callable
                    )
                    .where(FoodItem.home_id == user.current_home_id)
                    .group_by(FoodItem.category)
                )
            ).fetchall()
            category_item_counts = {
                row[0]: row[1] for row in item_counts_result
            }
        except (HomeNotFoundError, NotHomeMemberError):
            user.current_home_id = None
            await db.flush()

    return TEMPLATES.TemplateResponse(
        "pages/homes.html",
        {
            "request": request,
            "user": user,
            "homes": homes,
            "pending_invitations": pending_invitations,
            "current_home": current_home,
            "current_home_members": current_home_members,
            "current_home_categories": current_home_categories,
            "category_item_counts": category_item_counts,
            "is_current_home_owner": is_current_home_owner,
            "message": message,
            "error": error,
        },
    )


@ROUTER.post("/homes/create")
async def create_home(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    name: str = Form(...),
) -> RedirectResponse:
    """Create a new home.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.
        name (str): The home name.

    Returns:
        RedirectResponse: Redirect to homes page with status message.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        await HomeService(db).create_home(name=name, owner=user)
        return RedirectResponse(
            url=f"/web/homes?message=Home '{name}' created successfully",
            status_code=303,
        )
    except HomeAlreadyExistsError:
        return RedirectResponse(
            url="/web/homes?error=You already own a home",
            status_code=303,
        )


@ROUTER.post("/homes/{home_id}/switch")
async def switch_home(
    request: Request,
    home_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Switch to a different home.

    Args:
        request (Request): The incoming request.
        home_id (int): The ID of the home to switch to.
        db (AsyncSession): The database session.

    Returns:
        RedirectResponse: Redirect to dashboard.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        await HomeService(db).switch_home(user, home_id)
        return RedirectResponse(url="/web/dashboard", status_code=303)
    except (HomeNotFoundError, NotHomeMemberError):
        return RedirectResponse(
            url="/web/homes?error=Cannot switch to that home",
            status_code=303,
        )


@ROUTER.post("/homes/{home_id}/update")
async def update_home(
    request: Request,
    home_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    name: str = Form(...),
) -> RedirectResponse:
    """Update home name.

    Args:
        request (Request): The incoming request.
        home_id (int): The ID of the home to update.
        db (AsyncSession): The database session.
        name (str): The new home name.

    Returns:
        RedirectResponse: Redirect to homes page with status message.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        await HomeService(db).update_home(home_id, user, name=name)
        return RedirectResponse(
            url="/web/homes?message=Home updated successfully",
            status_code=303,
        )
    except HomeNotFoundError:
        return RedirectResponse(
            url="/web/homes?error=Home not found",
            status_code=303,
        )
    except NotHomeOwnerError:
        return RedirectResponse(
            url="/web/homes?error=Only the owner can update the home",
            status_code=303,
        )


@ROUTER.post("/homes/{home_id}/delete")
async def delete_home(
    request: Request,
    home_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Delete a home.

    Args:
        request (Request): The incoming request.
        home_id (int): The ID of the home to delete.
        db (AsyncSession): The database session.

    Returns:
        RedirectResponse: Redirect to homes page with status message.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        await HomeService(db).delete_home(home_id, user)
        return RedirectResponse(
            url="/web/homes?message=Home deleted successfully",
            status_code=303,
        )
    except HomeNotFoundError:
        return RedirectResponse(
            url="/web/homes?error=Home not found",
            status_code=303,
        )
    except NotHomeOwnerError:
        return RedirectResponse(
            url="/web/homes?error=Only the owner can delete the home",
            status_code=303,
        )


@ROUTER.post("/homes/{home_id}/invite")
async def invite_member(
    request: Request,
    home_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    username_or_email: str = Form(...),
) -> RedirectResponse:
    """Invite a user to a home.

    Args:
        request (Request): The incoming request.
        home_id (int): The ID of the home.
        db (AsyncSession): The database session.
        username_or_email (str): The username or email to invite.

    Returns:
        RedirectResponse: Redirect to homes page with status message.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        await HomeService(db).invite_member(home_id, user, username_or_email)
        return RedirectResponse(
            url="/web/homes?message=Member invited successfully",
            status_code=303,
        )
    except HomeNotFoundError:
        return RedirectResponse(
            url="/web/homes?error=Home not found",
            status_code=303,
        )
    except NotHomeOwnerError:
        return RedirectResponse(
            url="/web/homes?error=Only the owner can invite members",
            status_code=303,
        )
    except UserNotFoundError:
        return RedirectResponse(
            url=f"/web/homes?error=User '{username_or_email}' not found",
            status_code=303,
        )
    except UserAlreadyMemberError:
        return RedirectResponse(
            url="/web/homes?error=User is already a member",
            status_code=303,
        )


@ROUTER.post("/homes/{home_id}/members/{user_id}/remove")
async def remove_member(
    request: Request,
    home_id: int,
    user_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Remove a member from a home.

    Args:
        request (Request): The incoming request.
        home_id (int): The ID of the home.
        user_id (int): The ID of the user to remove.
        db (AsyncSession): The database session.

    Returns:
        RedirectResponse: Redirect to homes page with status message.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        await HomeService(db).remove_member(home_id, user, user_id)
        return RedirectResponse(
            url="/web/homes?message=Member removed successfully",
            status_code=303,
        )
    except HomeNotFoundError:
        return RedirectResponse(
            url="/web/homes?error=Home not found",
            status_code=303,
        )
    except NotHomeOwnerError:
        return RedirectResponse(
            url="/web/homes?error=Only the owner can remove members",
            status_code=303,
        )
    except CannotRemoveOwnerError:
        return RedirectResponse(
            url="/web/homes?error=Cannot remove the owner",
            status_code=303,
        )
    except NotHomeMemberError:
        return RedirectResponse(
            url="/web/homes?error=User is not a member",
            status_code=303,
        )


@ROUTER.post("/homes/{home_id}/leave")
async def leave_home(
    request: Request,
    home_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Leave a home.

    Args:
        request (Request): The incoming request.
        home_id (int): The ID of the home to leave.
        db (AsyncSession): The database session.

    Returns:
        RedirectResponse: Redirect to homes page with status message.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        await HomeService(db).leave_home(home_id, user)
        return RedirectResponse(
            url="/web/homes?message=You have left the home",
            status_code=303,
        )
    except HomeNotFoundError:
        return RedirectResponse(
            url="/web/homes?error=Home not found",
            status_code=303,
        )
    except CannotLeaveOwnedHomeError:
        return RedirectResponse(
            url="/web/homes?error=Cannot leave a home you own. "
            "Transfer ownership or delete the home.",
            status_code=303,
        )
    except NotHomeMemberError:
        return RedirectResponse(
            url="/web/homes?error=You are not a member of this home",
            status_code=303,
        )


@ROUTER.post("/homes/invitations/{invitation_id}/accept")
async def accept_invitation(
    request: Request,
    invitation_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Accept a pending home invitation.

    Args:
        request (Request): The incoming request.
        invitation_id (int): The ID of the invitation to accept.
        db (AsyncSession): The database session.

    Returns:
        RedirectResponse: Redirect to homes page with status message.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        home: HomeSimple = await HomeService(db).accept_invitation(
            user, invitation_id
        )
        return RedirectResponse(
            url=f"/web/homes?message=You have joined '{home.name}'",
            status_code=303,
        )
    except InvitationNotFoundError:
        return RedirectResponse(
            url="/web/homes?error=Invitation not found",
            status_code=303,
        )
    except InvitationAlreadyProcessedError:
        return RedirectResponse(
            url="/web/homes?error=This invitation has already been processed",
            status_code=303,
        )


@ROUTER.post("/homes/invitations/{invitation_id}/decline")
async def decline_invitation(
    request: Request,
    invitation_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> RedirectResponse:
    """Decline a pending home invitation.

    Args:
        request (Request): The incoming request.
        invitation_id (int): The ID of the invitation to decline.
        db (AsyncSession): The database session.

    Returns:
        RedirectResponse: Redirect to homes page with status message.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    try:
        await HomeService(db).decline_invitation(user, invitation_id)
        return RedirectResponse(
            url="/web/homes?message=Invitation declined",
            status_code=303,
        )
    except InvitationNotFoundError:
        return RedirectResponse(
            url="/web/homes?error=Invitation not found",
            status_code=303,
        )
    except InvitationAlreadyProcessedError:
        return RedirectResponse(
            url="/web/homes?error=This invitation has already been processed",
            status_code=303,
        )


@ROUTER.post("/homes/categories/create")
async def create_category(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    value: str = Form(...),
    label: str = Form(...),
    icon: str = Form(...),
) -> RedirectResponse:
    """Create a new category in the current home.

    Args:
        request (Request): The incoming request.
        db (AsyncSession): The database session.
        value (str): The unique value identifier.
        label (str): The display label.
        icon (str): The emoji icon.

    Returns:
        RedirectResponse: Redirect to homes page with status message.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    if user.current_home_id is None:
        return RedirectResponse(
            url="/web/homes?error=No home selected",
            status_code=303,
        )

    home_service: HomeService = HomeService(db)
    if not await home_service.is_owner(user.current_home_id, user.id):
        return RedirectResponse(
            url="/web/homes?error=Only the owner can create categories",
            status_code=303,
        )

    next_sort_order: int = (
        (
            await db.execute(
                select(func.coalesce(func.max(Category.sort_order), -1)).where(
                    Category.home_id == user.current_home_id
                )
            )
        ).scalar()
        or -1
    ) + 1

    try:
        await CategoryService(db, user.current_home_id).create_category(
            value=value.lower().replace(" ", "_"),
            label=label,
            icon=icon,
            sort_order=next_sort_order,
        )
        return RedirectResponse(
            url=f"/web/homes?message=Category '{label}' created successfully",
            status_code=303,
        )
    except CategoryValueExistsError:
        return RedirectResponse(
            url=f"/web/homes?error=Category value '{value}' already exists",
            status_code=303,
        )


@ROUTER.post("/homes/categories/{category_id}/update")
async def update_category(
    request: Request,
    category_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    label: str = Form(...),
    icon: str = Form(...),
) -> RedirectResponse:
    """Update a category in the current home.

    Args:
        request (Request): The incoming request.
        category_id (int): The ID of the category to update.
        db (AsyncSession): The database session.
        label (str): The new display label.
        icon (str): The new emoji icon.

    Returns:
        RedirectResponse: Redirect to homes page with status message.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    if user.current_home_id is None:
        return RedirectResponse(
            url="/web/homes?error=No home selected",
            status_code=303,
        )

    home_service: HomeService = HomeService(db)
    if not await home_service.is_owner(user.current_home_id, user.id):
        return RedirectResponse(
            url="/web/homes?error=Only the owner can update categories",
            status_code=303,
        )

    try:
        await CategoryService(db, user.current_home_id).update_category(
            category_id=category_id,
            label=label,
            icon=icon,
        )
        return RedirectResponse(
            url=f"/web/homes?message=Category '{label}' updated successfully",
            status_code=303,
        )
    except CategoryNotFoundError:
        return RedirectResponse(
            url="/web/homes?error=Category not found",
            status_code=303,
        )


@ROUTER.post("/homes/categories/{category_id}/delete")
async def delete_category(
    request: Request,
    category_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    force: str = Form("0"),
) -> RedirectResponse:
    """Delete a category from the current home.

    Args:
        request (Request): The incoming request.
        category_id (int): The ID of the category to delete.
        db (AsyncSession): The database session.
        force (str): "1" to force delete and reassign items.

    Returns:
        RedirectResponse: Redirect to homes page with status message.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return RedirectResponse(url="/web/login", status_code=303)

    if user.current_home_id is None:
        return RedirectResponse(
            url="/web/homes?error=No home selected",
            status_code=303,
        )

    home_service: HomeService = HomeService(db)
    if not await home_service.is_owner(user.current_home_id, user.id):
        return RedirectResponse(
            url="/web/homes?error=Only the owner can delete categories",
            status_code=303,
        )

    try:
        await CategoryService(db, user.current_home_id).delete_category(
            category_id, force=(force == "1")
        )
        return RedirectResponse(
            url="/web/homes?message=Category deleted successfully",
            status_code=303,
        )
    except CategoryNotFoundError:
        return RedirectResponse(
            url="/web/homes?error=Category not found",
            status_code=303,
        )
    except CategoryInUseError as exc:
        return RedirectResponse(
            url=f"/web/homes?error={exc}. Use force delete to reassign items.",
            status_code=303,
        )


@ROUTER.post("/homes/categories/reorder")
async def reorder_categories(
    request: Request,
    db: t.Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    """Reorder categories via drag-and-drop.

    Args:
        request (Request): The incoming request containing JSON body.
        db (AsyncSession): The database session.

    Returns:
        JSONResponse: Success or error response.
    """
    user: User | None = await get_current_web_user(request, db)
    if user is None:
        return JSONResponse(
            status_code=401,
            content={"error": "Not authenticated"},
        )

    if user.current_home_id is None:
        return JSONResponse(
            status_code=400,
            content={"error": "No home selected"},
        )

    home_service: HomeService = HomeService(db)
    if not await home_service.is_owner(user.current_home_id, user.id):
        return JSONResponse(
            status_code=403,
            content={"error": "Only the owner can reorder categories"},
        )

    try:
        body: t.Dict[str, t.Any] = await request.json()
        categories_order = body.get("categories", [])

        service: CategoryService = CategoryService(db, user.current_home_id)
        for item in categories_order:
            category_id: int | None = item.get("id")
            sort_order: int | None = item.get("sort_order")
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

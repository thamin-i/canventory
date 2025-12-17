"""Homes CRUD API endpoints."""

import typing as t

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_active_user
from app.core.database import get_db
from app.core.models import Home, User
from app.schemas.home import (
    HomeCreate,
    HomeDetailResponse,
    HomeInviteRequest,
    HomeMemberResponse,
    HomeResponse,
    HomeSimple,
    HomeSwitchRequest,
    HomeUpdate,
    PendingInvitationResponse,
)
from app.services import (
    CannotLeaveOwnedHomeError,
    CannotRemoveOwnerError,
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

ROUTER = APIRouter(prefix="/homes", tags=["Homes"])


@ROUTER.post(
    "", response_model=HomeResponse, status_code=status.HTTP_201_CREATED
)
async def create_home(
    home_data: HomeCreate,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> HomeResponse:
    """Create a new home.

    Users can only own one home.

    Args:
        home_data (HomeCreate): The home data.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        HomeResponse: The created home data.
    """
    try:
        return await HomeService(db).create_home(
            name=home_data.name,
            owner=current_user,
        )
    except HomeAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@ROUTER.get("/mine", response_model=t.List[HomeSimple])
async def list_my_homes(
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> t.List[HomeSimple]:
    """List all homes the current user has access to.

    Args:
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        List[HomeSimple]: List of homes the user belongs to.
    """
    return await HomeService(db).list_user_homes(current_user)


@ROUTER.get("/current", response_model=HomeSimple | None)
async def get_current_home(
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> HomeSimple | None:
    """Get the user's currently selected home.

    Args:
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        HomeSimple | None: The current home or None.
    """
    service: HomeService = HomeService(db)
    home: Home | None = await service.get_user_current_home(current_user)
    if home is None:
        return None

    is_owner: bool = await service.is_owner(home.id, current_user.id)
    return HomeSimple(id=home.id, name=home.name, is_owner=is_owner)


@ROUTER.post("/switch", status_code=status.HTTP_204_NO_CONTENT)
async def switch_home(
    switch_data: HomeSwitchRequest,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Switch to a different home.

    Args:
        switch_data (HomeSwitchRequest): The home to switch to.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.
    """
    try:
        await HomeService(db).switch_home(current_user, switch_data.home_id)
    except HomeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NotHomeMemberError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@ROUTER.get("/{home_id}", response_model=HomeDetailResponse)
async def get_home(
    home_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> HomeDetailResponse:
    """Get detailed home information.

    Args:
        home_id (int): The ID of the home.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        HomeDetailResponse: The home details including members.
    """
    try:
        return await HomeService(db).get_home_detail(home_id, current_user)
    except HomeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NotHomeMemberError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@ROUTER.put("/{home_id}", response_model=HomeResponse)
async def update_home(
    home_id: int,
    home_data: HomeUpdate,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> HomeResponse:
    """Update a home (owner only).

    Args:
        home_id (int): The ID of the home.
        home_data (HomeUpdate): The updated home data.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        HomeResponse: The updated home data.
    """
    try:
        return await HomeService(db).update_home(
            home_id=home_id,
            user=current_user,
            name=home_data.name,
        )
    except HomeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NotHomeOwnerError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@ROUTER.delete("/{home_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_home(
    home_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Delete a home and all its data (owner only).

    Args:
        home_id (int): The ID of the home.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.
    """
    try:
        await HomeService(db).delete_home(home_id, current_user)
    except HomeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NotHomeOwnerError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@ROUTER.post("/{home_id}/members", response_model=HomeMemberResponse)
async def invite_member(
    home_id: int,
    invite_data: HomeInviteRequest,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> HomeMemberResponse:
    """Invite a user to join the home (owner only).

    Args:
        home_id (int): The ID of the home.
        invite_data (HomeInviteRequest): The user to invite.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        HomeMemberResponse: The new member data.
    """
    try:
        return await HomeService(db).invite_member(
            home_id=home_id,
            owner=current_user,
            username_or_email=invite_data.username_or_email,
        )
    except HomeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NotHomeOwnerError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except UserAlreadyMemberError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@ROUTER.delete(
    "/{home_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_member(
    home_id: int,
    user_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Remove a member from the home (owner only).

    Args:
        home_id (int): The ID of the home.
        user_id (int): The ID of the user to remove.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.
    """
    try:
        await HomeService(db).remove_member(home_id, current_user, user_id)
    except HomeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except NotHomeOwnerError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except CannotRemoveOwnerError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except NotHomeMemberError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@ROUTER.post("/{home_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_home(
    home_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Leave a home (for non-owners).

    Args:
        home_id (int): The ID of the home.
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.
    """
    try:
        await HomeService(db).leave_home(home_id, current_user)
    except HomeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except CannotLeaveOwnedHomeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except NotHomeMemberError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@ROUTER.get(
    "/invitations/pending", response_model=t.List[PendingInvitationResponse]
)
async def list_pending_invitations(
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> t.List[PendingInvitationResponse]:
    """List all pending invitations for the current user.

    Args:
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        List[PendingInvitationResponse]: List of pending invitations.
    """
    return await HomeService(db).list_pending_invitations(current_user)


@ROUTER.post("/invitations/{invitation_id}/accept", response_model=HomeSimple)
async def accept_invitation(
    invitation_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> HomeSimple:
    """Accept a pending invitation.

    Args:
        invitation_id (int): The ID of the invitation (membership).
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.

    Returns:
        HomeSimple: The home the user joined.
    """
    try:
        return await HomeService(db).accept_invitation(
            current_user, invitation_id
        )
    except InvitationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvitationAlreadyProcessedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@ROUTER.post(
    "/invitations/{invitation_id}/decline",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def decline_invitation(
    invitation_id: int,
    db: t.Annotated[AsyncSession, Depends(get_db)],
    current_user: t.Annotated[User, Depends(get_current_active_user)],
) -> None:
    """Decline a pending invitation.

    Args:
        invitation_id (int): The ID of the invitation (membership).
        db (AsyncSession): The database session.
        current_user (User): The currently authenticated user.
    """
    try:
        await HomeService(db).decline_invitation(current_user, invitation_id)
    except InvitationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except InvitationAlreadyProcessedError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

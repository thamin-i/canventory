"""Home membership verification utilities."""

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models import User
from app.services import HomeService


async def get_home_id_and_check_membership(
    db: AsyncSession, user: User, require_owner: bool = False
) -> int:
    """Get user's current home and verify membership.

    Args:
        db (AsyncSession): Database session.
        user (User): The user object.
        require_owner (bool): If True, verify the user is the home owner.

    Returns:
        int: The current home ID.
    """
    if user.current_home_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No home selected. Please select or create a home first.",
        )

    home_service: HomeService = HomeService(db)

    if not await home_service.is_member(user.current_home_id, user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this home.",
        )

    if require_owner and not await home_service.is_owner(
        user.current_home_id, user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the home owner can perform this action.",
        )

    return user.current_home_id

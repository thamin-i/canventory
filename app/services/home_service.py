"""Home service for CRUD operations."""

import logging
import typing as t

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.models import (
    Category,
    FoodItem,
    Home,
    HomeMemberRole,
    HomeMembership,
    HomeMembershipStatus,
    User,
)
from app.schemas.home import (
    HomeDetailResponse,
    HomeMemberResponse,
    HomeResponse,
    HomeSimple,
    PendingInvitationResponse,
)

LOGGER: logging.Logger = logging.getLogger(__name__)

# Default categories to create for new homes
DEFAULT_CATEGORIES: t.List[t.Dict[str, t.Any]] = [
    # Grains & Starches
    {"value": "grains", "label": "Grains", "icon": "🌾", "sort_order": 0},
    {"value": "pasta", "label": "Pasta", "icon": "🍝", "sort_order": 1},
    {"value": "rice", "label": "Rice", "icon": "🍚", "sort_order": 2},
    {"value": "cereals", "label": "Cereals", "icon": "🥣", "sort_order": 3},
    # Proteins & Legumes
    {"value": "beans", "label": "Beans", "icon": "🫘", "sort_order": 4},
    {"value": "nuts", "label": "Nuts", "icon": "🥜", "sort_order": 5},
    # Canned & Preserved
    {"value": "canned", "label": "Canned Goods", "icon": "🥫", "sort_order": 6},
    {"value": "soups", "label": "Soups", "icon": "🍲", "sort_order": 7},
    # Dairy
    {"value": "dairy", "label": "Dairy", "icon": "🧀", "sort_order": 8},
    # Cooking & Condiments
    {"value": "oils", "label": "Oils", "icon": "🫒", "sort_order": 9},
    {
        "value": "condiments",
        "label": "Condiments",
        "icon": "🧂",
        "sort_order": 10,
    },
    {"value": "baking", "label": "Baking", "icon": "🧁", "sort_order": 11},
    # Snacks & Sweets
    {"value": "snacks", "label": "Snacks", "icon": "🍿", "sort_order": 12},
    {
        "value": "dried_fruits",
        "label": "Dried Fruits",
        "icon": "🍇",
        "sort_order": 13,
    },
    # Beverages
    {
        "value": "beverages",
        "label": "Beverages",
        "icon": "🧃",
        "sort_order": 14,
    },
    # Special
    {
        "value": "baby_food",
        "label": "Baby Food",
        "icon": "🍼",
        "sort_order": 15,
    },
    {"value": "other", "label": "Other", "icon": "📦", "sort_order": 16},
]


class HomeNotFoundError(Exception):
    """Exception raised when a home is not found."""

    home_id: int

    def __init__(self, home_id: int) -> None:
        """Initialize the exception.

        Args:
            home_id: The ID of the home that was not found.
        """
        self.home_id = home_id
        super().__init__(f"Home with ID {home_id} not found")


class HomeAlreadyExistsError(Exception):
    """Exception raised when user already owns a home."""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__("User already owns a home")


class NotHomeOwnerError(Exception):
    """Exception raised when user is not the owner of a home."""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__("User is not the owner of this home")


class NotHomeMemberError(Exception):
    """Exception raised when user is not a member of a home."""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__("User is not a member of this home")


class UserNotFoundError(Exception):
    """Exception raised when a user to invite is not found."""

    def __init__(self, identifier: str) -> None:
        """Initialize the exception.

        Args:
            identifier: The username or email that was not found.
        """
        self.identifier = identifier
        super().__init__(f"User '{identifier}' not found")


class UserAlreadyMemberError(Exception):
    """Exception raised when user is already a member of the home."""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__("User is already a member of this home")


class CannotRemoveOwnerError(Exception):
    """Exception raised when trying to remove the owner from a home."""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__("Cannot remove the owner from the home")


class CannotLeaveOwnedHomeError(Exception):
    """Exception raised when owner tries to leave their own home."""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__(
            "Cannot leave a home you own. "
            "Transfer ownership or delete the home."
        )


class InvitationNotFoundError(Exception):
    """Exception raised when an invitation is not found."""

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__("Invitation not found")


class InvitationAlreadyProcessedError(Exception):
    """Exception raised when trying to
    process an already processed invitation.
    """

    def __init__(self) -> None:
        """Initialize the exception."""
        super().__init__("This invitation has already been processed")


class HomeService:
    """Service class for home operations."""

    db: AsyncSession

    def __init__(self, db: AsyncSession) -> None:
        """Initialize the service.

        Args:
            db: The async database session.
        """
        self.db = db

    async def _get_home_response(self, home: Home) -> HomeResponse:
        """Convert Home model to HomeResponse schema.

        Args:
            home: The home model.

        Returns:
            HomeResponse schema.
        """
        # Get member count
        member_count: int = (
            await self.db.execute(
                select(
                    func.count(  # pylint: disable=not-callable
                        HomeMembership.id
                    )
                ).where(HomeMembership.home_id == home.id)
            )
        ).scalar() or 0

        # Get item count
        item_count: int = (
            await self.db.execute(
                select(
                    func.count(FoodItem.id)  # pylint: disable=not-callable
                ).where(FoodItem.home_id == home.id)
            )
        ).scalar() or 0

        # Get owner username
        owner: User | None = (
            await self.db.execute(select(User).where(User.id == home.owner_id))
        ).scalar_one_or_none()

        return HomeResponse(
            id=home.id,
            name=home.name,
            owner_id=home.owner_id,
            owner_username=owner.username if owner else "Unknown",
            member_count=member_count,
            item_count=item_count,
            created_at=home.created_at,
            updated_at=home.updated_at,
        )

    async def create_home(self, name: str, owner: User) -> HomeResponse:
        """Create a new home.

        Args:
            name: The name of the home.
            owner: The user who will own the home.

        Returns:
            The created home response.
        """
        # Check if user already owns a home
        existing_home: Home | None = (
            await self.db.execute(select(Home).where(Home.owner_id == owner.id))
        ).scalar_one_or_none()

        if existing_home is not None:
            raise HomeAlreadyExistsError()

        # Create the home
        home: Home = Home(name=name, owner_id=owner.id)
        self.db.add(home)
        await self.db.flush()

        # Add owner as a member with owner role (already accepted)
        membership: HomeMembership = HomeMembership(
            home_id=home.id,
            user_id=owner.id,
            role=HomeMemberRole.OWNER,
            status=HomeMembershipStatus.ACCEPTED,
            joined_at=func.now(),  # pylint: disable=not-callable
        )
        self.db.add(membership)

        # Create default categories for the home
        for cat_data in DEFAULT_CATEGORIES:
            category: Category = Category(
                home_id=home.id,
                value=cat_data["value"],
                label=cat_data["label"],
                icon=cat_data["icon"],
                sort_order=cat_data["sort_order"],
            )
            self.db.add(category)

        # Set as current home for the owner
        owner.current_home_id = home.id

        await self.db.flush()
        await self.db.refresh(home)

        LOGGER.info("Created home '%s' for user %s", name, owner.username)
        return await self._get_home_response(home)

    async def get_home(self, home_id: int) -> Home:
        """Get a home by ID.

        Args:
            home_id: The ID of the home.

        Returns:
            The home model.
        """
        home: Home | None = (
            await self.db.execute(select(Home).where(Home.id == home_id))
        ).scalar_one_or_none()

        if home is None:
            raise HomeNotFoundError(home_id)

        return home

    async def get_home_detail(
        self, home_id: int, user: User
    ) -> HomeDetailResponse:
        """Get detailed home info including members.

        Args:
            home_id: The ID of the home.
            user: The requesting user.

        Returns:
            Detailed home response.
        """
        home: Home = await self.get_home(home_id)

        # Check if user is a member
        if not await self.is_member(home_id, user.id):
            raise NotHomeMemberError()

        # Get members with user info
        memberships: t.Sequence[HomeMembership] = (
            (
                await self.db.execute(
                    select(HomeMembership)
                    .options(selectinload(HomeMembership.user))
                    .where(HomeMembership.home_id == home_id)
                )
            )
            .scalars()
            .all()
        )

        members: t.List[HomeMemberResponse] = []
        for membership in memberships:
            members.append(
                HomeMemberResponse(
                    id=membership.id,
                    user_id=membership.user_id,
                    username=membership.user.username,
                    email=membership.user.email,
                    role=membership.role,
                    status=membership.status,
                    invited_at=membership.invited_at,
                    joined_at=membership.joined_at,
                )
            )

        base_response: HomeResponse = await self._get_home_response(home)

        return HomeDetailResponse(
            **base_response.model_dump(),
            members=members,
        )

    async def list_user_homes(self, user: User) -> t.List[HomeSimple]:
        """List all homes the user has accepted membership to.

        Args:
            user: The user.

        Returns:
            List of simplified home info (only accepted memberships).
        """
        memberships: t.Sequence[HomeMembership] = (
            (
                await self.db.execute(
                    select(HomeMembership)
                    .options(selectinload(HomeMembership.home))
                    .where(
                        HomeMembership.user_id == user.id,
                        HomeMembership.status == HomeMembershipStatus.ACCEPTED,
                    )
                )
            )
            .scalars()
            .all()
        )

        return [
            HomeSimple(
                id=m.home.id,
                name=m.home.name,
                is_owner=m.role == HomeMemberRole.OWNER,
            )
            for m in memberships
        ]

    async def is_member(self, home_id: int, user_id: int) -> bool:
        """Check if a user is an accepted member of a home.

        Args:
            home_id: The ID of the home.
            user_id: The ID of the user.

        Returns:
            True if user is an accepted member, False otherwise.
        """
        membership: HomeMembership | None = (
            await self.db.execute(
                select(HomeMembership).where(
                    HomeMembership.home_id == home_id,
                    HomeMembership.user_id == user_id,
                    HomeMembership.status == HomeMembershipStatus.ACCEPTED,
                )
            )
        ).scalar_one_or_none()

        return membership is not None

    async def has_pending_or_accepted_membership(
        self, home_id: int, user_id: int
    ) -> bool:
        """Check if a user has any membership (pending or accepted) in a home.

        Args:
            home_id: The ID of the home.
            user_id: The ID of the user.

        Returns:
            True if user has a membership, False otherwise.
        """
        membership: HomeMembership | None = (
            await self.db.execute(
                select(HomeMembership).where(
                    HomeMembership.home_id == home_id,
                    HomeMembership.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

        return membership is not None

    async def is_owner(self, home_id: int, user_id: int) -> bool:
        """Check if a user is the owner of a home.

        Args:
            home_id: The ID of the home.
            user_id: The ID of the user.

        Returns:
            True if user is the owner, False otherwise.
        """
        home: Home | None = (
            await self.db.execute(
                select(Home).where(Home.id == home_id, Home.owner_id == user_id)
            )
        ).scalar_one_or_none()

        return home is not None

    async def update_home(
        self, home_id: int, user: User, name: str | None = None
    ) -> HomeResponse:
        """Update a home.

        Args:
            home_id: The ID of the home.
            user: The requesting user.
            name: The new name (optional).

        Returns:
            Updated home response.
        """
        home: Home = await self.get_home(home_id)

        if home.owner_id != user.id:
            raise NotHomeOwnerError()

        if name is not None:
            home.name = name

        await self.db.flush()
        await self.db.refresh(home)

        LOGGER.info("Updated home '%s' (ID: %d)", home.name, home_id)
        return await self._get_home_response(home)

    async def invite_member(
        self, home_id: int, owner: User, username_or_email: str
    ) -> HomeMemberResponse:
        """Invite a user to join a home (creates pending invitation).

        Args:
            home_id: The ID of the home.
            owner: The home owner.
            username_or_email: The username or email of the user to invite.

        Returns:
            The new member response (with pending status).
        """
        home: Home = await self.get_home(home_id)

        if home.owner_id != owner.id:
            raise NotHomeOwnerError()

        # Find the user to invite
        invited_user: User | None = (
            await self.db.execute(
                select(User).where(
                    (User.username == username_or_email)
                    | (User.email == username_or_email)
                )
            )
        ).scalar_one_or_none()

        if invited_user is None:
            raise UserNotFoundError(username_or_email)

        # Check if already has a membership (pending or accepted)
        if await self.has_pending_or_accepted_membership(
            home_id, invited_user.id
        ):
            raise UserAlreadyMemberError()

        # Add membership with PENDING status
        membership: HomeMembership = HomeMembership(
            home_id=home_id,
            user_id=invited_user.id,
            role=HomeMemberRole.MEMBER,
            status=HomeMembershipStatus.PENDING,
        )
        self.db.add(membership)

        await self.db.flush()
        await self.db.refresh(membership)

        LOGGER.info(
            "User %s invited to home '%s' (pending)",
            invited_user.username,
            home.name,
        )

        return HomeMemberResponse(
            id=membership.id,
            user_id=invited_user.id,
            username=invited_user.username,
            email=invited_user.email,
            role=membership.role,
            status=membership.status,
            invited_at=membership.invited_at,
            joined_at=membership.joined_at,
        )

    async def remove_member(
        self, home_id: int, owner: User, user_id: int
    ) -> None:
        """Remove a member from a home.

        Args:
            home_id: The ID of the home.
            owner: The home owner.
            user_id: The ID of the user to remove.
        """
        home: Home = await self.get_home(home_id)

        if home.owner_id != owner.id:
            raise NotHomeOwnerError()

        if user_id == owner.id:
            raise CannotRemoveOwnerError()

        membership: HomeMembership | None = (
            await self.db.execute(
                select(HomeMembership).where(
                    HomeMembership.home_id == home_id,
                    HomeMembership.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

        if membership is None:
            raise NotHomeMemberError()

        # If this was the user's current home, clear it
        removed_user: User | None = (
            await self.db.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()

        if removed_user and removed_user.current_home_id == home_id:
            # Find another home for the user
            other_membership: HomeMembership | None = (
                await self.db.execute(
                    select(HomeMembership).where(
                        HomeMembership.user_id == user_id,
                        HomeMembership.home_id != home_id,
                    )
                )
            ).scalar_one_or_none()

            removed_user.current_home_id = (
                other_membership.home_id if other_membership else None
            )

        await self.db.delete(membership)
        await self.db.flush()

        LOGGER.info("User ID %d removed from home '%s'", user_id, home.name)

    async def leave_home(self, home_id: int, user: User) -> None:
        """Leave a home (for non-owners).

        Args:
            home_id: The ID of the home.
            user: The user leaving.
        """
        home: Home = await self.get_home(home_id)

        if home.owner_id == user.id:
            raise CannotLeaveOwnedHomeError()

        membership: HomeMembership | None = (
            await self.db.execute(
                select(HomeMembership).where(
                    HomeMembership.home_id == home_id,
                    HomeMembership.user_id == user.id,
                )
            )
        ).scalar_one_or_none()

        if membership is None:
            raise NotHomeMemberError()

        # If this was the user's current home, find another
        if user.current_home_id == home_id:
            other_membership: HomeMembership | None = (
                await self.db.execute(
                    select(HomeMembership).where(
                        HomeMembership.user_id == user.id,
                        HomeMembership.home_id != home_id,
                    )
                )
            ).scalar_one_or_none()

            user.current_home_id = (
                other_membership.home_id if other_membership else None
            )

        await self.db.delete(membership)
        await self.db.flush()

        LOGGER.info("User %s left home '%s'", user.username, home.name)

    async def delete_home(self, home_id: int, user: User) -> None:
        """Delete a home and all its data.

        Args:
            home_id: The ID of the home.
            user: The requesting user.
        """
        home: Home = await self.get_home(home_id)

        if home.owner_id != user.id:
            raise NotHomeOwnerError()

        # Clear current_home_id for all members
        members: t.Sequence[HomeMembership] = (
            (
                await self.db.execute(
                    select(HomeMembership).where(
                        HomeMembership.home_id == home_id
                    )
                )
            )
            .scalars()
            .all()
        )

        for membership in members:
            member_user: User | None = (
                await self.db.execute(
                    select(User).where(User.id == membership.user_id)
                )
            ).scalar_one_or_none()

            if member_user and member_user.current_home_id == home_id:
                # Find another home
                other_membership: HomeMembership | None = (
                    await self.db.execute(
                        select(HomeMembership).where(
                            HomeMembership.user_id == membership.user_id,
                            HomeMembership.home_id != home_id,
                        )
                    )
                ).scalar_one_or_none()

                member_user.current_home_id = (
                    other_membership.home_id if other_membership else None
                )

        # Delete the home (cascades to memberships, categories, items)
        await self.db.delete(home)
        await self.db.flush()

        LOGGER.info("Deleted home '%s' (ID: %d)", home.name, home_id)

    async def switch_home(self, user: User, home_id: int) -> None:
        """Switch the user's current home.

        Args:
            user: The user.
            home_id: The ID of the home to switch to.
        """
        await self.get_home(home_id)

        if not await self.is_member(home_id, user.id):
            raise NotHomeMemberError()

        user.current_home_id = home_id
        await self.db.flush()

        LOGGER.info("User %s switched to home ID %d", user.username, home_id)

    async def get_user_current_home(self, user: User) -> Home | None:
        """Get the user's current home.

        Args:
            user: The user.

        Returns:
            The current home or None.
        """
        if user.current_home_id is None:
            return None

        return (
            await self.db.execute(
                select(Home).where(Home.id == user.current_home_id)
            )
        ).scalar_one_or_none()

    async def list_pending_invitations(
        self, user: User
    ) -> t.List[PendingInvitationResponse]:
        """List all pending invitations for a user.

        Args:
            user: The user.

        Returns:
            List of pending invitations.
        """
        memberships: t.Sequence[HomeMembership] = (
            (
                await self.db.execute(
                    select(HomeMembership)
                    .options(selectinload(HomeMembership.home))
                    .where(
                        HomeMembership.user_id == user.id,
                        HomeMembership.status == HomeMembershipStatus.PENDING,
                    )
                )
            )
            .scalars()
            .all()
        )

        invitations: t.List[PendingInvitationResponse] = []
        for membership in memberships:
            # Get owner username
            owner: User | None = (
                await self.db.execute(
                    select(User).where(User.id == membership.home.owner_id)
                )
            ).scalar_one_or_none()

            invitations.append(
                PendingInvitationResponse(
                    id=membership.id,
                    home_id=membership.home.id,
                    home_name=membership.home.name,
                    owner_username=owner.username if owner else "Unknown",
                    invited_at=membership.invited_at,
                )
            )

        return invitations

    async def accept_invitation(
        self, user: User, invitation_id: int
    ) -> HomeSimple:
        """Accept a pending invitation.

        Args:
            user: The user accepting the invitation.
            invitation_id: The ID of the membership/invitation.

        Returns:
            The home the user joined.
        """
        membership: HomeMembership | None = (
            await self.db.execute(
                select(HomeMembership)
                .options(selectinload(HomeMembership.home))
                .where(
                    HomeMembership.id == invitation_id,
                    HomeMembership.user_id == user.id,
                )
            )
        ).scalar_one_or_none()

        if membership is None:
            raise InvitationNotFoundError()

        if membership.status != HomeMembershipStatus.PENDING:
            raise InvitationAlreadyProcessedError()

        # Accept the invitation
        membership.status = HomeMembershipStatus.ACCEPTED
        membership.joined_at = func.now()  # pylint: disable=not-callable

        # Set as current home if user doesn't have one
        if user.current_home_id is None:
            user.current_home_id = membership.home_id

        await self.db.flush()

        LOGGER.info(
            "User %s accepted invitation to home '%s'",
            user.username,
            membership.home.name,
        )

        return HomeSimple(
            id=membership.home.id,
            name=membership.home.name,
            is_owner=False,
        )

    async def decline_invitation(self, user: User, invitation_id: int) -> None:
        """Decline a pending invitation.

        Args:
            user: The user declining the invitation.
            invitation_id: The ID of the membership/invitation.
        """
        membership: HomeMembership | None = (
            await self.db.execute(
                select(HomeMembership)
                .options(selectinload(HomeMembership.home))
                .where(
                    HomeMembership.id == invitation_id,
                    HomeMembership.user_id == user.id,
                )
            )
        ).scalar_one_or_none()

        if membership is None:
            raise InvitationNotFoundError()

        if membership.status != HomeMembershipStatus.PENDING:
            raise InvitationAlreadyProcessedError()

        home_name: str = membership.home.name

        # Delete the membership record
        await self.db.delete(membership)
        await self.db.flush()

        LOGGER.info(
            "User %s declined invitation to home '%s'", user.username, home_name
        )

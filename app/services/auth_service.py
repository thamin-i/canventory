"""Authentication service - business logic for auth operations."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    authenticate_user,
    create_access_token,
    get_password_hash,
    get_user_by_email,
    get_user_by_username,
    is_registration_enabled,
    verify_password,
)
from app.core.config import SETTINGS
from app.core.models import User
from app.schemas.auth import (
    LoginResult,
    RegistrationResult,
    Token,
    UserResponse,
)


class RegistrationDisabledError(Exception):
    """Raised when registration is disabled."""

    def __init__(self) -> None:
        super().__init__("New registrations are currently disabled")


class UsernameExistsError(Exception):
    """Raised when username already exists."""

    username: str

    def __init__(self, username: str) -> None:
        """Initialize UsernameExistsError

        Args:
            username (str): The existing username
        """
        self.username = username
        super().__init__("Username already registered")


class EmailExistsError(Exception):
    """Raised when email already exists."""

    email: str

    def __init__(self, email: str) -> None:
        """Initialize EmailExistsError

        Args:
            email (str): The existing email
        """
        self.email = email
        super().__init__("Email already registered")


class InvalidCredentialsError(Exception):
    """Raised when credentials are invalid."""

    def __init__(self) -> None:
        super().__init__("Incorrect username or password")


class InvalidCurrentPasswordError(Exception):
    """Raised when current password is incorrect during password change."""

    def __init__(self) -> None:
        super().__init__("Current password is incorrect")


class AuthService:
    """Service class for authentication operations."""

    db: AsyncSession

    def __init__(self, db: AsyncSession) -> None:
        """Initialize AuthService

        Args:
            db (AsyncSession): Database session
        """
        self.db = db

    @staticmethod
    def _user_to_response(user: User) -> UserResponse:
        """Convert User model to UserResponse schema

        Args:
            user (User): User model instance

        Returns:
            UserResponse: Corresponding UserResponse schema
        """
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            is_admin=user.is_admin,
            is_active=user.is_active,
            created_at=user.created_at,
        )

    async def register_user(
        self,
        username: str,
        email: str,
        password: str,
    ) -> RegistrationResult:
        """Register a new user

        Args:
            username (str): Username
            email (str): Email
            password (str): Plain text password

        Returns:
            RegistrationResult: Result of the registration
        """
        if not await is_registration_enabled(self.db):
            raise RegistrationDisabledError()

        existing_username: User | None = await get_user_by_username(
            self.db, username
        )
        if existing_username is not None:
            raise UsernameExistsError(username)

        existing_email: User | None = await get_user_by_email(self.db, email)
        if existing_email is not None:
            raise EmailExistsError(email)

        hashed_password: str = get_password_hash(password)
        new_user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            is_admin=False,
        )
        self.db.add(new_user)
        await self.db.flush()
        await self.db.refresh(new_user)

        return RegistrationResult(
            user=self._user_to_response(new_user),
            is_first_user=False,
        )

    async def login(self, username: str, password: str) -> LoginResult:
        """
        Authenticate user and create access token.

        Args:
            username (str): Username
            password (str): Plain text password

        Returns:
            LoginResult: Result of the login operation
        """
        user: User | None = await authenticate_user(self.db, username, password)
        if user is None:
            raise InvalidCredentialsError()

        access_token_expires: timedelta = timedelta(
            minutes=SETTINGS.access_token_expire_minutes
        )
        access_token: str = create_access_token(
            data={"sub": user.username, "user_id": user.id},
            expires_delta=access_token_expires,
        )

        return LoginResult(
            token=Token(access_token=access_token, token_type="bearer"),
            user=self._user_to_response(user),
        )

    async def authenticate(self, username: str, password: str) -> User | None:
        """Authenticate user without creating token.

        Args:
            username (str): Username
            password (str): Plain text password

        Returns:
            User | None:
                The User model if credentials are valid,
                None otherwise.
        """
        return await authenticate_user(self.db, username, password)

    async def check_registration_enabled(self) -> bool:
        """Check if new user registration is enabled.

        Returns:
            bool: True if registration is enabled, False otherwise.
        """
        return await is_registration_enabled(self.db)

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str,
    ) -> bool:
        """Change a user's password.

        Args:
            user (User): The user whose password to change.
            current_password (str): The current password for verification.
            new_password (str): The new password to set.

        Returns:
            bool: True if password was changed successfully.

        Raises:
            InvalidCurrentPasswordError: If the current password is incorrect.
        """
        if not verify_password(current_password, user.hashed_password):
            raise InvalidCurrentPasswordError()

        user.hashed_password = get_password_hash(new_password)
        await self.db.flush()
        return True

    async def change_email(
        self,
        user: User,
        new_email: str,
        password: str,
    ) -> str:
        """Change a user's email address.

        Args:
            user (User): The user whose email to change.
            new_email (str): The new email address.
            password (str): The current password for verification.

        Returns:
            str: The new email address.

        Raises:
            InvalidCurrentPasswordError: If the password is incorrect.
            EmailExistsError: If the new email is already in use.
        """
        if not verify_password(password, user.hashed_password):
            raise InvalidCurrentPasswordError()

        existing_email: User | None = await get_user_by_email(
            self.db, new_email
        )
        if existing_email is not None and existing_email.id != user.id:
            raise EmailExistsError(new_email)

        user.email = new_email
        await self.db.flush()
        return new_email

"""Schemas package."""

from app.schemas.alert import ExpirationAlertSummary
from app.schemas.auth import (
    EmailChange,
    EmailChangeResult,
    LoginResult,
    PasswordChange,
    PasswordChangeResult,
    RegistrationResult,
    Token,
    TokenData,
    UserCreate,
    UserResponse,
)
from app.schemas.category import (
    CategoryCreate,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdate,
)
from app.schemas.food_item import (
    FoodItemCreate,
    FoodItemListResponse,
    FoodItemResponse,
    FoodItemUpdate,
)
from app.schemas.home import (
    HomeCreate,
    HomeDetailResponse,
    HomeInviteRequest,
    HomeListResponse,
    HomeMemberResponse,
    HomeResponse,
    HomeSimple,
    HomeSwitchRequest,
    HomeUpdate,
    PendingInvitationResponse,
)
from app.schemas.notifications import (
    EmailNotificationResponse,
    EmailNotificationSettings,
)
from app.schemas.statistics import CanventoryStats

__all__ = [
    "CanventoryStats",
    "CategoryCreate",
    "CategoryListResponse",
    "CategoryResponse",
    "CategoryUpdate",
    "EmailChange",
    "EmailChangeResult",
    "EmailNotificationResponse",
    "EmailNotificationSettings",
    "ExpirationAlertSummary",
    "FoodItemCreate",
    "FoodItemListResponse",
    "FoodItemResponse",
    "FoodItemUpdate",
    "HomeCreate",
    "HomeDetailResponse",
    "HomeInviteRequest",
    "HomeListResponse",
    "HomeMemberResponse",
    "HomeResponse",
    "HomeSimple",
    "HomeSwitchRequest",
    "HomeUpdate",
    "LoginResult",
    "PasswordChange",
    "PasswordChangeResult",
    "PendingInvitationResponse",
    "RegistrationResult",
    "Token",
    "TokenData",
    "UserCreate",
    "UserResponse",
]

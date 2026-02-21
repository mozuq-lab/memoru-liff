"""User models for Memoru LIFF application."""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LinkLineRequest(BaseModel):
    """Request model for linking LINE account."""

    id_token: str = Field(..., min_length=1, description="LIFF ID Token for server-side verification")


class LinkLineResponse(BaseModel):
    """Response model for linking LINE account."""

    success: bool
    message: str


class UserSettingsRequest(BaseModel):
    """Request model for updating user settings."""

    notification_time: Optional[str] = Field(None, description="Notification time in HH:MM format")
    timezone: Optional[str] = Field(None, description="IANA timezone string")

    @field_validator("notification_time")
    @classmethod
    def validate_notification_time(cls, v: Optional[str]) -> Optional[str]:
        """Validate notification time format (HH:MM)."""
        if v is None:
            return v
        if not re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", v):
            raise ValueError("Invalid notification time format. Must be HH:MM (00:00-23:59).")
        return v

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        """Validate IANA timezone string."""
        if v is None:
            return v
        # Common valid timezones
        valid_timezones = {
            "Asia/Tokyo",
            "America/New_York",
            "America/Los_Angeles",
            "Europe/London",
            "Europe/Paris",
            "UTC",
        }
        # For production, use pytz or zoneinfo to validate
        # Here we do a basic check
        if not re.match(r"^[A-Za-z_]+/[A-Za-z_]+$", v) and v != "UTC":
            raise ValueError("Invalid timezone format.")
        return v


class UserSettingsResponse(BaseModel):
    """Response model for user settings update."""

    success: bool
    settings: dict


class UserResponse(BaseModel):
    """Response model for user information."""

    user_id: str
    display_name: Optional[str] = None
    picture_url: Optional[str] = None
    line_linked: bool = False
    notification_time: Optional[str] = None
    timezone: str = "Asia/Tokyo"
    created_at: datetime
    updated_at: Optional[datetime] = None


class User(BaseModel):
    """User domain model."""

    user_id: str
    line_user_id: Optional[str] = None
    display_name: Optional[str] = None
    picture_url: Optional[str] = None
    settings: dict = Field(default_factory=lambda: {"notification_time": "09:00", "timezone": "Asia/Tokyo"})
    last_notified_date: Optional[str] = None  # YYYY-MM-DD format
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    def to_response(self) -> UserResponse:
        """Convert to API response model."""
        return UserResponse(
            user_id=self.user_id,
            display_name=self.display_name,
            picture_url=self.picture_url,
            line_linked=self.line_user_id is not None,
            notification_time=self.settings.get("notification_time"),
            timezone=self.settings.get("timezone", "Asia/Tokyo"),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item."""
        item = {
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
            "settings": self.settings,
        }
        if self.line_user_id:
            item["line_user_id"] = self.line_user_id
        if self.display_name:
            item["display_name"] = self.display_name
        if self.picture_url:
            item["picture_url"] = self.picture_url
        if self.last_notified_date:
            item["last_notified_date"] = self.last_notified_date
        if self.updated_at:
            item["updated_at"] = self.updated_at.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "User":
        """Create User from DynamoDB item."""
        return cls(
            user_id=item["user_id"],
            line_user_id=item.get("line_user_id"),
            display_name=item.get("display_name"),
            picture_url=item.get("picture_url"),
            settings=item.get("settings", {"notification_time": "09:00", "timezone": "Asia/Tokyo"}),
            last_notified_date=item.get("last_notified_date"),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]) if item.get("updated_at") else None,
        )

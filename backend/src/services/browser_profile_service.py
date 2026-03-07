"""Browser profile management service for authenticated page access."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

import boto3
from boto3.dynamodb.conditions import Key


class BrowserProfileError(Exception):
    """Raised when browser profile operation fails."""

    pass


@dataclass
class BrowserProfile:
    """Browser profile for authenticated page access."""

    profile_id: str
    user_id: str
    name: str
    created_at: str


class BrowserProfileService:
    """Service for managing browser profiles.

    Browser profiles store authentication sessions for AgentCore Browser,
    enabling access to login-required pages.
    """

    def __init__(self, table_name: str | None = None) -> None:
        self._table_name = table_name or os.getenv(
            "BROWSER_PROFILES_TABLE", "memoru-browser-profiles"
        )
        dynamodb = boto3.resource("dynamodb")
        self._table = dynamodb.Table(self._table_name)

    def create_profile(
        self,
        user_id: str,
        name: str,
    ) -> BrowserProfile:
        """Create a new browser profile.

        Args:
            user_id: System user ID.
            name: Display name for the profile.

        Returns:
            Created BrowserProfile.

        Raises:
            BrowserProfileError: If creation fails.
        """
        profile_id = f"bp-{uuid.uuid4().hex[:12]}"
        created_at = datetime.now(timezone.utc).isoformat()

        item = {
            "profile_id": profile_id,
            "user_id": user_id,
            "name": name,
            "created_at": created_at,
        }

        try:
            self._table.put_item(Item=item)
        except Exception as e:
            raise BrowserProfileError(f"Failed to create profile: {e}") from e

        return BrowserProfile(
            profile_id=profile_id,
            user_id=user_id,
            name=name,
            created_at=created_at,
        )

    def list_profiles(self, user_id: str) -> List[BrowserProfile]:
        """List all profiles for a user.

        Args:
            user_id: System user ID.

        Returns:
            List of BrowserProfile objects.
        """
        try:
            response = self._table.query(
                KeyConditionExpression=Key("user_id").eq(user_id),
            )
        except Exception as e:
            raise BrowserProfileError(f"Failed to list profiles: {e}") from e

        return [
            BrowserProfile(
                profile_id=item["profile_id"],
                user_id=item["user_id"],
                name=item["name"],
                created_at=item["created_at"],
            )
            for item in response.get("Items", [])
        ]

    def get_profile(
        self,
        user_id: str,
        profile_id: str,
    ) -> Optional[BrowserProfile]:
        """Get a specific profile.

        Args:
            user_id: System user ID (for ownership check).
            profile_id: Profile ID.

        Returns:
            BrowserProfile if found and owned by user, None otherwise.
        """
        try:
            response = self._table.get_item(
                Key={"user_id": user_id, "profile_id": profile_id},
            )
        except Exception as e:
            raise BrowserProfileError(f"Failed to get profile: {e}") from e

        item = response.get("Item")
        if not item:
            return None

        return BrowserProfile(
            profile_id=item["profile_id"],
            user_id=item["user_id"],
            name=item["name"],
            created_at=item["created_at"],
        )

    def delete_profile(self, user_id: str, profile_id: str) -> bool:
        """Delete a profile.

        Args:
            user_id: System user ID (for ownership check).
            profile_id: Profile ID.

        Returns:
            True if deleted, False if not found.
        """
        profile = self.get_profile(user_id, profile_id)
        if not profile:
            return False

        try:
            self._table.delete_item(
                Key={"user_id": user_id, "profile_id": profile_id},
            )
        except Exception as e:
            raise BrowserProfileError(f"Failed to delete profile: {e}") from e

        return True

    def validate_profile(self, user_id: str, profile_id: str) -> bool:
        """Check if a profile exists and is owned by the user.

        Args:
            user_id: System user ID.
            profile_id: Profile ID.

        Returns:
            True if profile exists and belongs to user.
        """
        return self.get_profile(user_id, profile_id) is not None

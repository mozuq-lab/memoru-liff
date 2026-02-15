"""User service for DynamoDB operations."""

import os
from datetime import datetime
from datetime import timezone as dt_timezone
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

from ..models.user import User


class UserServiceError(Exception):
    """Base exception for user service errors."""

    pass


class UserNotFoundError(UserServiceError):
    """Raised when user is not found."""

    pass


class UserAlreadyLinkedError(UserServiceError):
    """Raised when user is already linked to LINE."""

    pass


class LineUserIdAlreadyUsedError(UserServiceError):
    """Raised when LINE user ID is already used by another user."""

    pass


class LineNotLinkedError(UserServiceError):
    """Raised when user has no LINE account to unlink."""

    pass


class UserService:
    """Service for user-related DynamoDB operations."""

    def __init__(self, table_name: Optional[str] = None, dynamodb_resource=None):
        """Initialize UserService.

        Args:
            table_name: DynamoDB table name. Defaults to USERS_TABLE env var.
            dynamodb_resource: Optional boto3 DynamoDB resource for testing.
        """
        self.table_name = table_name or os.environ.get("USERS_TABLE", "memoru-users-dev")

        if dynamodb_resource:
            self.dynamodb = dynamodb_resource
        else:
            endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
            if endpoint_url:
                self.dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)
            else:
                self.dynamodb = boto3.resource("dynamodb")

        self.table = self.dynamodb.Table(self.table_name)

    def get_user(self, user_id: str) -> User:
        """Get user by user_id.

        Args:
            user_id: The user's unique identifier.

        Returns:
            User object.

        Raises:
            UserNotFoundError: If user does not exist.
        """
        try:
            response = self.table.get_item(Key={"user_id": user_id})
            if "Item" not in response:
                raise UserNotFoundError(f"User not found: {user_id}")
            return User.from_dynamodb_item(response["Item"])
        except ClientError as e:
            raise UserServiceError(f"Failed to get user: {e}")

    def create_user(self, user_id: str, display_name: Optional[str] = None, picture_url: Optional[str] = None) -> User:
        """Create a new user.

        Args:
            user_id: The user's unique identifier.
            display_name: Optional display name.
            picture_url: Optional profile picture URL.

        Returns:
            Created User object.
        """
        user = User(
            user_id=user_id,
            display_name=display_name,
            picture_url=picture_url,
            created_at=datetime.now(dt_timezone.utc),
        )
        try:
            self.table.put_item(
                Item=user.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(user_id)",
            )
            return user
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # User already exists, return existing user
                return self.get_user(user_id)
            raise UserServiceError(f"Failed to create user: {e}")

    def get_or_create_user(
        self, user_id: str, display_name: Optional[str] = None, picture_url: Optional[str] = None
    ) -> User:
        """Get existing user or create new one.

        Args:
            user_id: The user's unique identifier.
            display_name: Optional display name for new user.
            picture_url: Optional profile picture URL for new user.

        Returns:
            User object.
        """
        try:
            return self.get_user(user_id)
        except UserNotFoundError:
            return self.create_user(user_id, display_name, picture_url)

    def link_line(self, user_id: str, line_user_id: str) -> User:
        """Link LINE account to user.

        Args:
            user_id: The user's unique identifier.
            line_user_id: LINE User ID to link.

        Returns:
            Updated User object.

        Raises:
            UserNotFoundError: If user does not exist.
            UserAlreadyLinkedError: If user is already linked to LINE.
            LineUserIdAlreadyUsedError: If LINE user ID is already used.
        """
        # Check if LINE user ID is already used by another user
        existing_user = self.get_user_by_line_id(line_user_id)
        if existing_user and existing_user.user_id != user_id:
            raise LineUserIdAlreadyUsedError(f"LINE user ID is already linked to another account")

        # Get current user
        user = self.get_user(user_id)

        # Check if user is already linked to a different LINE account
        if user.line_user_id and user.line_user_id != line_user_id:
            raise UserAlreadyLinkedError("User is already linked to a LINE account")

        # Update user with LINE user ID
        try:
            now = datetime.now(dt_timezone.utc)
            self.table.update_item(
                Key={"user_id": user_id},
                UpdateExpression="SET line_user_id = :line_id, updated_at = :updated_at",
                ExpressionAttributeValues={
                    ":line_id": line_user_id,
                    ":updated_at": now.isoformat(),
                },
            )
            user.line_user_id = line_user_id
            user.updated_at = now
            return user
        except ClientError as e:
            raise UserServiceError(f"Failed to link LINE account: {e}")

    def get_user_by_line_id(self, line_user_id: str) -> Optional[User]:
        """Get user by LINE user ID.

        Args:
            line_user_id: LINE User ID.

        Returns:
            User object if found, None otherwise.
        """
        try:
            response = self.table.query(
                IndexName="line_user_id-index",
                KeyConditionExpression="line_user_id = :line_id",
                ExpressionAttributeValues={":line_id": line_user_id},
            )
            items = response.get("Items", [])
            if not items:
                return None
            return User.from_dynamodb_item(items[0])
        except ClientError as e:
            raise UserServiceError(f"Failed to query user by LINE ID: {e}")

    def get_linked_users(self, limit: int = 100) -> List[User]:
        """Get all users with LINE account linked.

        Args:
            limit: Maximum number of users to return per scan.

        Returns:
            List of users with LINE account linked.
        """
        users = []
        try:
            # Scan the table for users with line_user_id
            scan_kwargs = {
                "FilterExpression": "attribute_exists(line_user_id)",
                "Limit": limit,
            }

            while True:
                response = self.table.scan(**scan_kwargs)
                for item in response.get("Items", []):
                    users.append(User.from_dynamodb_item(item))

                # Check for more pages
                if "LastEvaluatedKey" not in response:
                    break
                scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

            return users
        except ClientError as e:
            raise UserServiceError(f"Failed to get linked users: {e}")

    def update_last_notified_date(self, user_id: str, date_str: str) -> None:
        """Update user's last notification date.

        Args:
            user_id: The user's unique identifier.
            date_str: Date string in YYYY-MM-DD format.
        """
        try:
            self.table.update_item(
                Key={"user_id": user_id},
                UpdateExpression="SET last_notified_date = :date, updated_at = :updated_at",
                ExpressionAttributeValues={
                    ":date": date_str,
                    ":updated_at": datetime.now(dt_timezone.utc).isoformat(),
                },
            )
        except ClientError as e:
            raise UserServiceError(f"Failed to update last notified date: {e}")

    def update_settings(self, user_id: str, notification_time: Optional[str] = None, timezone: Optional[str] = None) -> User:
        """Update user settings.

        Args:
            user_id: The user's unique identifier.
            notification_time: Optional notification time in HH:MM format.
            timezone: Optional IANA timezone string.

        Returns:
            Updated User object.

        Raises:
            UserNotFoundError: If user does not exist.
        """
        # Verify user exists
        user = self.get_user(user_id)

        # Build update expression
        update_parts = []
        expression_values = {}
        expression_names = {}

        if notification_time is not None:
            update_parts.append("settings.notification_time = :notification_time")
            expression_values[":notification_time"] = notification_time

        if timezone is not None:
            # 'timezone' is a reserved keyword in DynamoDB
            update_parts.append("settings.#tz = :timezone")
            expression_values[":timezone"] = timezone
            expression_names["#tz"] = "timezone"

        if not update_parts:
            return user

        now = datetime.now(dt_timezone.utc)
        update_parts.append("updated_at = :updated_at")
        expression_values[":updated_at"] = now.isoformat()

        try:
            update_kwargs = {
                "Key": {"user_id": user_id},
                "UpdateExpression": "SET " + ", ".join(update_parts),
                "ExpressionAttributeValues": expression_values,
            }
            if expression_names:
                update_kwargs["ExpressionAttributeNames"] = expression_names

            self.table.update_item(**update_kwargs)

            # Update local user object
            if notification_time is not None:
                user.settings["notification_time"] = notification_time
            if timezone is not None:
                user.settings["timezone"] = timezone
            user.updated_at = now

            return user
        except ClientError as e:
            raise UserServiceError(f"Failed to update settings: {e}")

    def unlink_line(self, user_id: str) -> dict:
        """Unlink LINE account from user.

        Args:
            user_id: The user's unique identifier.

        Returns:
            Dictionary with user_id and unlinked_at timestamp.

        Raises:
            LineNotLinkedError: If user has no LINE account linked.
        """
        now = datetime.now(dt_timezone.utc)

        try:
            self.table.update_item(
                Key={"user_id": user_id},
                UpdateExpression="REMOVE line_user_id SET updated_at = :now",
                ConditionExpression="attribute_exists(line_user_id)",
                ExpressionAttributeValues={":now": now.isoformat()},
            )
            return {"user_id": user_id, "unlinked_at": now.isoformat()}
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise LineNotLinkedError("LINE account not linked to this user")
            raise UserServiceError(f"Failed to unlink LINE account: {e}")

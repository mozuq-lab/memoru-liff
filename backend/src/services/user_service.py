"""User service for DynamoDB operations."""

import os
from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError

from models.user import User
from utils.dynamodb_client import get_dynamodb_client, get_dynamodb_resource


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

        self.dynamodb = get_dynamodb_resource(dynamodb_resource)

        self.table = self.dynamodb.Table(self.table_name)

        # 低レベルクライアント: transact_write_items 用 (C-6 link/unlink ロック)。
        # boto3.resource().meta.client はリソース層の型変換イベントハンドラーを含むため、
        # 低レベル DynamoDB JSON ({"S": ...}) を二重シリアライズしてしまう。
        # 直接 boto3.client() を使うことで回避する (card_service.py と同一パターン)。
        self._client = get_dynamodb_client()

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

    @staticmethod
    def _link_lock_id(line_user_id: str) -> str:
        """Build the lock-item user_id for a line_user_id.

        C-6: GSI は一意制約ではないため、同一 line_user_id を別ユーザーが
        同時に link すると両方成功してしまう。これを防ぐため、Users テーブル内に
        `LINELINK#{line_user_id}` をキーとするロックアイテムを置き、
        TransactWriteItems でユーザー行更新とアトミックに排他制御する。
        """
        return f"LINELINK#{line_user_id}"

    def link_line(self, user_id: str, line_user_id: str) -> User:
        """Link LINE account to user.

        C-6: Uses TransactWriteItems with a per-line_user_id lock item to enforce
        a true uniqueness constraint that the GSI cannot provide.

        Args:
            user_id: The user's unique identifier.
            line_user_id: LINE User ID to link.

        Returns:
            Updated User object.

        Raises:
            UserNotFoundError: If user does not exist.
            UserAlreadyLinkedError: If user is already linked to a different LINE account.
            LineUserIdAlreadyUsedError: If LINE user ID is already used by another user.
        """
        # Check if LINE user ID is already used by another user (via GSI).
        # GSI 事前チェックはレガシーデータ（ロックアイテム無しで line_user_id だけ
        # 持つ既存ユーザー）への対応 + 早期エラーのために残す。一意性の最終保証は
        # 下の TransactWriteItems が担う。
        existing_user = self.get_user_by_line_id(line_user_id)
        if existing_user and existing_user.user_id != user_id:
            raise LineUserIdAlreadyUsedError("LINE user ID is already linked to another account")

        # Verify user exists
        user = self.get_user(user_id)

        now = datetime.now(dt_timezone.utc)
        lock_id = self._link_lock_id(line_user_id)
        client = self._client
        try:
            # 低レベル client API のため属性値は {"S": ...} 形式を使う。
            client.transact_write_items(
                TransactItems=[
                    {
                        # ロックアイテム: 同一 line_user_id を所有できるのは 1 ユーザーのみ。
                        # 同一ユーザーの再リンク（linked_user_id == :uid）は許容する。
                        # NOTE: line_user_id 属性は持たせない。get_linked_users の Scan
                        # FilterExpression (attribute_exists(line_user_id)) に
                        # 誤ってヒットさせないため。
                        "Put": {
                            "TableName": self.table.name,
                            "Item": {
                                "user_id": {"S": lock_id},
                                "linked_user_id": {"S": user_id},
                                "created_at": {"S": now.isoformat()},
                            },
                            "ConditionExpression": (
                                "attribute_not_exists(user_id) OR linked_user_id = :uid"
                            ),
                            "ExpressionAttributeValues": {":uid": {"S": user_id}},
                        }
                    },
                    {
                        # ユーザー行: 既存 ConditionExpression と同一。
                        # 別 line_user_id への上書きを禁止し、再リンクは許容する。
                        "Update": {
                            "TableName": self.table.name,
                            "Key": {"user_id": {"S": user_id}},
                            "UpdateExpression": (
                                "SET line_user_id = :line_id, updated_at = :updated_at"
                            ),
                            "ConditionExpression": (
                                "attribute_not_exists(line_user_id) OR line_user_id = :line_id"
                            ),
                            "ExpressionAttributeValues": {
                                ":line_id": {"S": line_user_id},
                                ":updated_at": {"S": now.isoformat()},
                            },
                        }
                    },
                ]
            )
            user.line_user_id = line_user_id
            user.updated_at = now
            return user
        except ClientError as e:
            if e.response["Error"]["Code"] == "TransactionCanceledException":
                reasons = e.response.get("CancellationReasons", [])
                # Index 0 = ロックアイテム Put: 別ユーザーが先に line_user_id を取得済み
                if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
                    raise LineUserIdAlreadyUsedError(
                        "LINE user ID is already linked to another account"
                    )
                # Index 1 = ユーザー行 Update: 別 line_user_id に既に連携済み
                if len(reasons) > 1 and reasons[1].get("Code") == "ConditionalCheckFailed":
                    raise UserAlreadyLinkedError("User is already linked to a LINE account")
                raise UserServiceError(f"Failed to link LINE account: {e}")
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

    def get_linked_users(self) -> List[User]:
        """Get all users with LINE account linked.

        Note: This method uses a full table Scan with FilterExpression.
        The FilterExpression reduces data transfer but does not reduce read capacity consumption.

        Returns:
            List of users with LINE account linked.

        .. todo::
            GSI (例: line_user_id-index を Scan するか、linked_status-index を新設) に
            移行してスキャンコストを削減する。ユーザー数増加に伴い Scan のコストが
            線形に増大するため、本番運用前に対応が必要。
        """
        users = []
        try:
            # TODO: GSI 導入後は Query に置き換えてスキャンコストを削減する
            # Scan the table for users with line_user_id
            #
            # M-8: LINELINK#<line_user_id> ロックアイテム（C-6）を明示的に除外する。
            # 通常ロックアイテムは line_user_id 属性を持たない設計だが、将来のコード変更や
            # 既存データ破損で line_user_id を持ったロックアイテムが Scan にヒットすると、
            # User.from_dynamodb_item に LINELINK# プレフィックスの user_id が渡され、
            # 通知ジョブ等の下流処理で誤動作する。NOT begins_with で多重防御する。
            scan_kwargs = {
                "FilterExpression": (
                    "attribute_exists(line_user_id) "
                    "AND NOT begins_with(user_id, :link_prefix)"
                ),
                "ExpressionAttributeValues": {":link_prefix": "LINELINK#"},
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

    def update_last_notified_date(self, user_id: str, date_str: str) -> bool:
        """Update user's last notification date with idempotency guard.

        Uses ConditionExpression to skip the update if last_notified_date is
        already set to date_str, ensuring idempotent execution when the due-push
        job is retried or invoked concurrently.

        Args:
            user_id: The user's unique identifier.
            date_str: Date string in YYYY-MM-DD format.

        Returns:
            True if the update was applied, False if already up-to-date (idempotent skip).
        """
        try:
            self.table.update_item(
                Key={"user_id": user_id},
                UpdateExpression="SET last_notified_date = :date, updated_at = :updated_at",
                ConditionExpression="attribute_not_exists(last_notified_date) OR last_notified_date <> :date",
                ExpressionAttributeValues={
                    ":date": date_str,
                    ":updated_at": datetime.now(dt_timezone.utc).isoformat(),
                },
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # Already notified today — idempotent skip
                return False
            raise UserServiceError(f"Failed to update last notified date: {e}")

    def update_settings(
        self,
        user_id: str,
        notification_time: Optional[str] = None,
        timezone: Optional[str] = None,
        day_start_hour: Optional[int] = None,
    ) -> User:
        """Update user settings.

        Args:
            user_id: The user's unique identifier.
            notification_time: Optional notification time in HH:MM format.
            timezone: Optional IANA timezone string.
            day_start_hour: Optional hour when user's day starts (0-23).

        Returns:
            Updated User object.

        Raises:
            UserNotFoundError: If user does not exist.
        """
        # Verify user exists
        user = self.get_user(user_id)

        # Build update expression
        update_parts = []
        expression_values: Dict[str, Any] = {}
        expression_names = {}

        if notification_time is not None:
            update_parts.append("settings.notification_time = :notification_time")
            expression_values[":notification_time"] = notification_time

        if timezone is not None:
            # 'timezone' is a reserved keyword in DynamoDB
            update_parts.append("settings.#tz = :timezone")
            expression_values[":timezone"] = timezone
            expression_names["#tz"] = "timezone"

        if day_start_hour is not None:
            update_parts.append("settings.day_start_hour = :day_start_hour")
            expression_values[":day_start_hour"] = day_start_hour

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
            if day_start_hour is not None:
                user.settings["day_start_hour"] = day_start_hour
            user.updated_at = now

            return user
        except ClientError as e:
            raise UserServiceError(f"Failed to update settings: {e}")

    def unlink_line(self, user_id: str) -> User:
        """Unlink LINE account from user.

        Args:
            user_id: The user's unique identifier.

        Returns:
            Updated User object with line_user_id cleared.

        Raises:
            LineNotLinkedError: If user has no LINE account linked.
        """
        now = datetime.now(dt_timezone.utc)

        # 現在の line_user_id を取得（ロックアイテムのキー導出に必要）。
        # get_user は user_id 直接指定のため LINELINK# アイテムを誤って読むことはない。
        # 存在しないユーザーは「LINE 未連携」と同義として LineNotLinkedError に変換する
        # （旧実装の ConditionExpression attribute_exists(line_user_id) 失敗時と同じ挙動）。
        try:
            user = self.get_user(user_id)
        except UserNotFoundError:
            raise LineNotLinkedError("LINE account not linked to this user")
        if not user.line_user_id:
            raise LineNotLinkedError("LINE account not linked to this user")

        lock_id = self._link_lock_id(user.line_user_id)
        client = self._client
        try:
            client.transact_write_items(
                TransactItems=[
                    {
                        # ユーザー行から line_user_id を REMOVE。
                        "Update": {
                            "TableName": self.table.name,
                            "Key": {"user_id": {"S": user_id}},
                            "UpdateExpression": "REMOVE line_user_id SET updated_at = :now",
                            "ConditionExpression": "attribute_exists(line_user_id)",
                            "ExpressionAttributeValues": {":now": {"S": now.isoformat()}},
                        }
                    },
                    {
                        # ロックアイテムを削除。
                        # レガシー（ロックアイテム無し）でも成功するよう、
                        # attribute_not_exists(user_id) を許容条件に含める。
                        "Delete": {
                            "TableName": self.table.name,
                            "Key": {"user_id": {"S": lock_id}},
                            "ConditionExpression": (
                                "attribute_not_exists(user_id) OR linked_user_id = :uid"
                            ),
                            "ExpressionAttributeValues": {":uid": {"S": user_id}},
                        }
                    },
                ]
            )
            return self.get_user(user_id)
        except ClientError as e:
            if e.response["Error"]["Code"] == "TransactionCanceledException":
                reasons = e.response.get("CancellationReasons", [])
                # Index 0 = ユーザー行 Update: line_user_id が存在しない
                if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
                    raise LineNotLinkedError("LINE account not linked to this user")
                raise UserServiceError(f"Failed to unlink LINE account: {e}")
            raise UserServiceError(f"Failed to unlink LINE account: {e}")

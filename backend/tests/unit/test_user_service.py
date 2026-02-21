"""Unit tests for user service."""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from moto import mock_aws
import boto3

from src.services.user_service import (
    UserService,
    UserNotFoundError,
    UserAlreadyLinkedError,
    LineUserIdAlreadyUsedError,
)


@pytest.fixture
def dynamodb_table():
    """Create a mock DynamoDB table."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        table = dynamodb.create_table(
            TableName="memoru-users-test",
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "line_user_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "line_user_id-index",
                    "KeySchema": [{"AttributeName": "line_user_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield dynamodb


@pytest.fixture
def user_service(dynamodb_table):
    """Create UserService with mock DynamoDB."""
    return UserService(table_name="memoru-users-test", dynamodb_resource=dynamodb_table)


class TestUserServiceGetUser:
    """Tests for UserService.get_user method."""

    def test_get_user_success(self, user_service, dynamodb_table):
        """Test getting an existing user."""
        # Setup: create a user in the table
        table = dynamodb_table.Table("memoru-users-test")
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "display_name": "Test User",
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                "created_at": "2024-01-01T00:00:00",
            }
        )

        # Execute
        user = user_service.get_user("test-user-id")

        # Assert
        assert user.user_id == "test-user-id"
        assert user.display_name == "Test User"
        assert user.settings["notification_time"] == "09:00"

    def test_get_user_not_found(self, user_service):
        """Test getting a non-existent user."""
        with pytest.raises(UserNotFoundError):
            user_service.get_user("non-existent-user")


class TestUserServiceCreateUser:
    """Tests for UserService.create_user method."""

    def test_create_user_success(self, user_service):
        """Test creating a new user."""
        user = user_service.create_user("new-user-id", display_name="New User")

        assert user.user_id == "new-user-id"
        assert user.display_name == "New User"
        assert user.settings["notification_time"] == "09:00"
        assert user.settings["timezone"] == "Asia/Tokyo"

    def test_create_user_already_exists(self, user_service, dynamodb_table):
        """Test creating a user that already exists."""
        # Setup: create a user
        table = dynamodb_table.Table("memoru-users-test")
        table.put_item(
            Item={
                "user_id": "existing-user-id",
                "display_name": "Existing User",
                "settings": {"notification_time": "10:00", "timezone": "UTC"},
                "created_at": "2024-01-01T00:00:00",
            }
        )

        # Execute: try to create user with same ID
        user = user_service.create_user("existing-user-id", display_name="New Name")

        # Assert: should return existing user, not overwrite
        assert user.user_id == "existing-user-id"
        assert user.display_name == "Existing User"


class TestUserServiceLinkLine:
    """Tests for UserService.link_line method."""

    def test_link_line_success(self, user_service, dynamodb_table):
        """Test linking LINE account successfully."""
        # Setup: create a user
        table = dynamodb_table.Table("memoru-users-test")
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                "created_at": "2024-01-01T00:00:00",
            }
        )

        # Execute
        line_user_id = "U1234567890abcdef1234567890abcdef"
        user = user_service.link_line("test-user-id", line_user_id)

        # Assert
        assert user.line_user_id == line_user_id
        assert user.updated_at is not None

    def test_link_line_user_not_found(self, user_service):
        """Test linking LINE when user doesn't exist."""
        with pytest.raises(UserNotFoundError):
            user_service.link_line("non-existent-user", "U1234567890abcdef1234567890abcdef")

    def test_link_line_already_linked_to_different_line(self, user_service, dynamodb_table):
        """Test linking when user is already linked to different LINE account."""
        # Setup: create a user with LINE linked
        table = dynamodb_table.Table("memoru-users-test")
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "line_user_id": "Uaaaabbbbccccddddeeeeffffgggghhh",
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                "created_at": "2024-01-01T00:00:00",
            }
        )

        # Execute & Assert
        with pytest.raises(UserAlreadyLinkedError):
            user_service.link_line("test-user-id", "U1234567890abcdef1234567890abcdef")

    def test_link_line_id_already_used_by_another_user(self, user_service, dynamodb_table):
        """Test linking LINE ID that's already used by another user."""
        # Setup: create two users, one with LINE linked
        table = dynamodb_table.Table("memoru-users-test")
        line_user_id = "U1234567890abcdef1234567890abcdef"
        table.put_item(
            Item={
                "user_id": "user-1",
                "line_user_id": line_user_id,
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                "created_at": "2024-01-01T00:00:00",
            }
        )
        table.put_item(
            Item={
                "user_id": "user-2",
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                "created_at": "2024-01-01T00:00:00",
            }
        )

        # Execute & Assert: user-2 tries to use the same LINE ID
        with pytest.raises(LineUserIdAlreadyUsedError):
            user_service.link_line("user-2", line_user_id)


class TestUserServiceUpdateSettings:
    """Tests for UserService.update_settings method."""

    def test_update_notification_time(self, user_service, dynamodb_table):
        """Test updating notification time."""
        # Setup: create a user
        table = dynamodb_table.Table("memoru-users-test")
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                "created_at": "2024-01-01T00:00:00",
            }
        )

        # Execute
        user = user_service.update_settings("test-user-id", notification_time="10:00")

        # Assert
        assert user.settings["notification_time"] == "10:00"
        assert user.settings["timezone"] == "Asia/Tokyo"  # Unchanged
        assert user.updated_at is not None

    def test_update_timezone(self, user_service, dynamodb_table):
        """Test updating timezone."""
        # Setup: create a user
        table = dynamodb_table.Table("memoru-users-test")
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                "created_at": "2024-01-01T00:00:00",
            }
        )

        # Execute
        user = user_service.update_settings("test-user-id", timezone="UTC")

        # Assert
        assert user.settings["timezone"] == "UTC"
        assert user.settings["notification_time"] == "09:00"  # Unchanged

    def test_update_both_settings(self, user_service, dynamodb_table):
        """Test updating both notification time and timezone."""
        # Setup: create a user
        table = dynamodb_table.Table("memoru-users-test")
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                "created_at": "2024-01-01T00:00:00",
            }
        )

        # Execute
        user = user_service.update_settings("test-user-id", notification_time="18:00", timezone="America/New_York")

        # Assert
        assert user.settings["notification_time"] == "18:00"
        assert user.settings["timezone"] == "America/New_York"

    def test_update_settings_user_not_found(self, user_service):
        """Test updating settings for non-existent user."""
        with pytest.raises(UserNotFoundError):
            user_service.update_settings("non-existent-user", notification_time="10:00")


class TestUserServiceGetUserByLineId:
    """Tests for UserService.get_user_by_line_id method."""

    def test_get_user_by_line_id_success(self, user_service, dynamodb_table):
        """Test getting user by LINE ID."""
        # Setup: create a user with LINE linked
        table = dynamodb_table.Table("memoru-users-test")
        line_user_id = "U1234567890abcdef1234567890abcdef"
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "line_user_id": line_user_id,
                "display_name": "Test User",
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                "created_at": "2024-01-01T00:00:00",
            }
        )

        # Execute
        user = user_service.get_user_by_line_id(line_user_id)

        # Assert
        assert user is not None
        assert user.user_id == "test-user-id"
        assert user.line_user_id == line_user_id

    def test_get_user_by_line_id_not_found(self, user_service):
        """Test getting user by non-existent LINE ID."""
        user = user_service.get_user_by_line_id("U0000000000000000000000000000000")
        assert user is None


# =============================================================================
# TASK-0043: card_count Transaction Fixes - Fix 4 Tests
# =============================================================================


class TestGetOrCreateUser:
    """Tests for get_or_create_user idempotency (Fix 4).

    【テストクラス目的】: get_or_create_user が冪等であることを検証する。
    既存ユーザーの場合は変更なしに返し、新規ユーザーの場合は新規作成する。
    POST /cards ハンドラで card_service.create_card() の前に呼び出す必要がある。
    """

    def test_get_or_create_user_existing(self, user_service, dynamodb_table):
        """TC-07: 既存ユーザーの場合、get_or_create_user は変更なしにユーザーを返す。

        【テスト目的】: 既存ユーザーレコードが存在する場合に
        get_or_create_user がユーザーを変更せずに返すことを検証する。
        🔵 信頼性レベル: 青信号 - user_service.py L116-132 で実装済みの動作を確認する。

        Given: card_count = 5 のユーザーレコードが存在する
        When: get_or_create_user を呼び出す
        Then: 既存ユーザーがcard_countを変更せずに返される

        Maps to: AC-019, AC-020, EARS-016
        """
        # 【テストデータ準備】: card_count = 5 の既存ユーザーをセットアップする
        table = dynamodb_table.Table("memoru-users-test")
        table.put_item(
            Item={
                "user_id": "existing-user-id",
                "card_count": 5,
                "created_at": "2024-01-01T00:00:00+00:00",
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
            }
        )

        # 【実際の処理実行】: 既存ユーザーに対してget_or_create_userを呼び出す
        user = user_service.get_or_create_user("existing-user-id")

        # 【結果検証】: 既存ユーザーが変更なしに返されることを確認する
        assert user.user_id == "existing-user-id"  # 【確認内容】: 正しいuser_idが返されている 🔵
        assert user.settings["notification_time"] == "09:00"  # 【確認内容】: 設定が変更されていない 🔵

        # 【結果検証】: データベースのcard_countが変更されていないことを確認する
        stored = table.get_item(Key={"user_id": "existing-user-id"})["Item"]
        assert stored["card_count"] == 5  # 【確認内容】: card_countが5のままで変更されていない 🔵

    def test_get_or_create_user_new(self, user_service, dynamodb_table):
        """TC-08: 新規ユーザーの場合、get_or_create_user は新規ユーザーレコードを作成する。

        【テスト目的】: 存在しないユーザーIDに対して get_or_create_user が
        新規ユーザーレコードを作成することを検証する。
        NOTE: User モデルの to_dynamodb_item() は card_count を含まない。
        これは意図的な設計であり、Fix 1 (if_not_exists) がこの問題を解決する。
        🔵 信頼性レベル: 青信号 - user_service.py L116-132 の動作を確認する。

        Given: 'new-user-id' のユーザーレコードが存在しない
        When: get_or_create_user を呼び出す
        Then: 新規ユーザーレコードが作成されデフォルト設定を持つ

        NOTE: User.to_dynamodb_item() は card_count を含まない (L114-131 参照)。
              これは期待される動作であり、Fix 1 (if_not_exists) がcard_count欠如を安全に処理する。

        Maps to: AC-017, AC-018, EARS-015, EARS-016
        """
        # 【実際の処理実行】: 存在しないユーザーに対してget_or_create_userを呼び出す
        user = user_service.get_or_create_user("new-user-id")

        # 【結果検証】: 新規ユーザーが作成されたことを確認する
        assert user.user_id == "new-user-id"  # 【確認内容】: 正しいuser_idが設定されている 🔵
        assert user.settings["notification_time"] == "09:00"  # 【確認内容】: デフォルト通知時間が設定されている 🔵
        assert user.settings["timezone"] == "Asia/Tokyo"  # 【確認内容】: デフォルトタイムゾーンが設定されている 🔵

        # 【結果検証】: データベースにユーザーレコードが作成されたことを確認する
        table = dynamodb_table.Table("memoru-users-test")
        stored = table.get_item(Key={"user_id": "new-user-id"})["Item"]
        assert stored["user_id"] == "new-user-id"  # 【確認内容】: DynamoDBにユーザーが保存されている 🔵
        assert "created_at" in stored  # 【確認内容】: created_atが設定されている 🔵
        # NOTE: card_count は to_dynamodb_item() に含まれないため、DynamoDBには存在しない
        # Fix 1 (if_not_exists) がcard_count欠如を安全に処理する
        assert "card_count" not in stored  # 【確認内容】: to_dynamodb_item()はcard_countを含まない 🔵

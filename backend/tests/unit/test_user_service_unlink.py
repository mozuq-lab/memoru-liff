"""Unit tests for user_service.unlink_line return type.

TASK-0045: レスポンスDTO統一 + unlinkLine API使用
対象テストケース: TC-06b

RED フェーズ: 現在の user_service.unlink_line() が dict を返却しているため、
              User 型を期待するテストが FAIL することを確認する。
"""

import os
import pytest
import boto3
from moto import mock_aws


USERS_TABLE = os.environ.get("USERS_TABLE", "memoru-users-test")


@pytest.fixture
def dynamodb_resource_moto():
    """Create a mocked DynamoDB resource using moto."""
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="ap-northeast-1")

        # テスト用テーブルを作成
        resource.create_table(
            TableName=USERS_TABLE,
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "line_user_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "line_user_id-index",
                    "KeySchema": [
                        {"AttributeName": "line_user_id", "KeyType": "HASH"}
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield resource


@pytest.fixture
def user_service_moto(dynamodb_resource_moto):
    """Create a UserService instance with mocked DynamoDB."""
    from src.services.user_service import UserService
    return UserService(table_name=USERS_TABLE, dynamodb_resource=dynamodb_resource_moto)


class TestUnlinkLineServiceReturn:
    """TC-06b: user_service.unlink_line が User 型を返却する."""

    def test_unlink_line_returns_user_not_dict(self, user_service_moto):
        """unlink_line がUser型オブジェクトを返すことを検証する.

        【テスト目的】: 戻り値が dict ではなく User 型であることを検証
        【期待される動作】: User インスタンスが返り、line_user_id が None
        青 信頼性レベル: EARS-045-006

        RED フェーズ失敗理由:
            user_service.py L332 が {"user_id": ..., "unlinked_at": ...} という dict を返却しており、
            User インスタンスではないため isinstance(result, User) が False になる。
        """
        from src.models.user import User

        # Given: LINE連携済みユーザーを作成
        user_service_moto.create_user(user_id="test-user-id")
        user_service_moto.link_line(user_id="test-user-id", line_user_id="U1234567890abcdef")

        # When: unlink_line を呼び出す
        result = user_service_moto.unlink_line("test-user-id")

        # Then: 戻り値が User 型であること
        assert isinstance(result, User), (
            f"Expected User instance, got {type(result)}. Value: {result}"
        )
        assert result.user_id == "test-user-id"
        assert result.line_user_id is None, (
            f"Expected line_user_id=None after unlink, got: {result.line_user_id}"
        )

    def test_unlink_line_returns_user_with_correct_fields(self, user_service_moto):
        """unlink_line の戻り値 User が全フィールドを持つことを検証する.

        【テスト目的】: 戻り値の User オブジェクトが DynamoDB から取得した最新状態を持つことを検証
        【期待される動作】: user_id, settings, created_at などが正しく設定されている
        青 信頼性レベル: EARS-045-006 (派生)
        """
        from src.models.user import User

        # Given: 通知設定付きのLINE連携済みユーザーを作成
        user_service_moto.create_user(user_id="test-user-id")
        user_service_moto.update_settings(
            user_id="test-user-id",
            notification_time="20:00",
            timezone="Asia/Tokyo",
        )
        user_service_moto.link_line(user_id="test-user-id", line_user_id="U1234567890abcdef")

        # When: unlink_line を呼び出す
        result = user_service_moto.unlink_line("test-user-id")

        # Then: User 型であり、各フィールドが正しいこと
        assert isinstance(result, User), (
            f"Expected User instance, got {type(result)}"
        )
        assert result.user_id == "test-user-id"
        assert result.line_user_id is None
        # settings が保持されていること
        assert result.settings is not None
        # updated_at が設定されていること
        assert result.updated_at is not None

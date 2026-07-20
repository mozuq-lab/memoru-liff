"""Unit tests for auth/pre_signup.py (signup-allowlist)。

設計 (docs/design/signup-allowlist/architecture.md) の「テスト方針」に列挙された
backend (pytest + moto) ケースを網羅する。
"""

import os
from unittest.mock import patch

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

import services.allowlist_service as allowlist_service
from auth.pre_signup import REJECT_MESSAGE, SignupNotAllowedError, handler
from services.allowlist_service import STATUS_APPROVED, STATUS_PENDING

TABLE_NAME = "memoru-signup-allowlist-test"


@pytest.fixture
def allowlist_table():
    """moto で許可リストテーブルを作成し、handler が参照するテーブルとして配線する。"""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "identifier", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "identifier", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        allowlist_service._resource = None
        with patch.dict(os.environ, {"ALLOWLIST_TABLE": TABLE_NAME}):
            yield table
        allowlist_service._resource = None


def _sign_up_event(email: str = "user@example.com") -> dict:
    """PreSignUp_SignUp (native メールセルフサインアップ) イベント。"""
    return {
        "version": "1",
        "region": "ap-northeast-1",
        "userPoolId": "ap-northeast-1_test",
        "userName": email,
        "triggerSource": "PreSignUp_SignUp",
        "request": {
            "userAttributes": {"email": email},
            "validationData": None,
        },
        "response": {
            "autoConfirmUser": False,
            "autoVerifyEmail": False,
            "autoVerifyPhone": False,
        },
    }


def _external_provider_event(
    user_name: str = "LINE_U1234abcd", name: str = "太郎"
) -> dict:
    """PreSignUp_ExternalProvider (LINE federation 初回サインイン) イベント。"""
    return {
        "version": "1",
        "region": "ap-northeast-1",
        "userPoolId": "ap-northeast-1_test",
        "userName": user_name,
        "triggerSource": "PreSignUp_ExternalProvider",
        "request": {
            "userAttributes": {"name": name},
            "validationData": None,
        },
        "response": {
            "autoConfirmUser": False,
            "autoVerifyEmail": False,
            "autoVerifyPhone": False,
        },
    }


def _admin_create_user_event(email: str = "admin-invited@example.com") -> dict:
    """PreSignUp_AdminCreateUser イベント。"""
    return {
        "version": "1",
        "region": "ap-northeast-1",
        "userPoolId": "ap-northeast-1_test",
        "userName": email,
        "triggerSource": "PreSignUp_AdminCreateUser",
        "request": {
            "userAttributes": {"email": email},
            "validationData": None,
        },
        "response": {
            "autoConfirmUser": False,
            "autoVerifyEmail": False,
            "autoVerifyPhone": False,
        },
    }


class TestNativeSignUp:
    def test_approved_email_allowed(self, allowlist_table, lambda_context):
        allowlist_table.put_item(
            Item={"identifier": "email#user@example.com", "status": STATUS_APPROVED}
        )
        event = _sign_up_event(email="user@example.com")

        result = handler(event, lambda_context)

        assert result is event

    def test_unregistered_email_rejected_and_not_recorded(
        self, allowlist_table, lambda_context
    ):
        event = _sign_up_event(email="stranger@example.com")

        with pytest.raises(Exception) as exc_info:
            handler(event, lambda_context)

        assert str(exc_info.value) == REJECT_MESSAGE
        # native 経路の未登録試行は記録しない（probe によるテーブル汚染防止）。
        item = allowlist_table.get_item(
            Key={"identifier": "email#stranger@example.com"}
        ).get("Item")
        assert item is None

    def test_email_normalized_before_lookup(self, allowlist_table, lambda_context):
        """大文字・前後空白を trim + 小文字化してから照合する。"""
        allowlist_table.put_item(
            Item={"identifier": "email#user@example.com", "status": STATUS_APPROVED}
        )
        event = _sign_up_event(email="  User@Example.com  ")

        result = handler(event, lambda_context)

        assert result is event

    def test_missing_email_attribute_rejected(self, allowlist_table, lambda_context):
        """userAttributes.email が欠落している場合も未登録扱いで拒否される。"""
        event = _sign_up_event()
        event["request"]["userAttributes"] = {}

        with pytest.raises(SignupNotAllowedError) as exc_info:
            handler(event, lambda_context)

        assert str(exc_info.value) == REJECT_MESSAGE


class TestExternalProvider:
    def test_approved_line_allowed(self, allowlist_table, lambda_context):
        allowlist_table.put_item(
            Item={"identifier": "idp#line_u1234abcd", "status": STATUS_APPROVED}
        )
        event = _external_provider_event(user_name="LINE_U1234abcd")

        result = handler(event, lambda_context)

        assert result is event

    def test_unregistered_line_records_pending_and_rejects(
        self, allowlist_table, lambda_context
    ):
        event = _external_provider_event(user_name="LINE_Unew5678", name="花子")

        with pytest.raises(Exception) as exc_info:
            handler(event, lambda_context)

        assert str(exc_info.value) == REJECT_MESSAGE
        item = allowlist_table.get_item(Key={"identifier": "idp#line_unew5678"}).get(
            "Item"
        )
        assert item is not None
        assert item["status"] == STATUS_PENDING
        assert item["display_name"] == "花子"

    def test_existing_pending_retry_not_overwritten_and_rejected(
        self, allowlist_table, lambda_context
    ):
        first_event = _external_provider_event(
            user_name="LINE_Uretry", name="first-attempt"
        )
        with pytest.raises(Exception):
            handler(first_event, lambda_context)

        retry_event = _external_provider_event(
            user_name="LINE_Uretry", name="second-attempt"
        )
        with pytest.raises(Exception) as exc_info:
            handler(retry_event, lambda_context)

        assert str(exc_info.value) == REJECT_MESSAGE
        item = allowlist_table.get_item(Key={"identifier": "idp#line_uretry"})["Item"]
        assert item["display_name"] == "first-attempt"

    def test_pending_display_name_is_sanitized(self, allowlist_table, lambda_context):
        malicious_name = "A\x00\x1fB" + "x" * 200
        event = _external_provider_event(
            user_name="LINE_Usanitize", name=malicious_name
        )

        with pytest.raises(Exception):
            handler(event, lambda_context)

        item = allowlist_table.get_item(Key={"identifier": "idp#line_usanitize"})[
            "Item"
        ]
        assert len(item["display_name"]) == 100
        assert "\x00" not in item["display_name"]
        assert item["display_name"].startswith("AB")

    def test_username_case_insensitive_lookup(self, allowlist_table, lambda_context):
        """userName は小文字化して照合する（signInCaseSensitive: false と整合）。"""
        allowlist_table.put_item(
            Item={"identifier": "idp#line_umixedcase", "status": STATUS_APPROVED}
        )
        event = _external_provider_event(user_name="LINE_UMixedCase")

        result = handler(event, lambda_context)

        assert result is event


class TestAdminCreateUser:
    def test_admin_create_user_always_allowed(self, allowlist_table, lambda_context):
        event = _admin_create_user_event()

        result = handler(event, lambda_context)

        assert result is event
        item = allowlist_table.get_item(
            Key={"identifier": "email#admin-invited@example.com"}
        ).get("Item")
        assert item is None


class TestUnknownTriggerSource:
    def test_unknown_trigger_source_rejected(self, allowlist_table, lambda_context):
        event = {"triggerSource": "PreSignUp_Unknown", "userName": "whoever"}

        with pytest.raises(Exception) as exc_info:
            handler(event, lambda_context)

        assert str(exc_info.value) == REJECT_MESSAGE

    def test_missing_trigger_source_rejected(self, allowlist_table, lambda_context):
        event = {"userName": "whoever"}

        with pytest.raises(Exception) as exc_info:
            handler(event, lambda_context)

        assert str(exc_info.value) == REJECT_MESSAGE


class TestFailClosed:
    def test_dynamodb_exception_becomes_generic_signup_not_allowed_error(
        self, lambda_context
    ):
        """DynamoDB 例外は一般文言の SignupNotAllowedError に変換される（フェイルクローズ
        は維持しつつ、生の内部エラーメッセージは Cognito 側に露出しない）。"""
        with (
            mock_aws(),
            patch.dict(os.environ, {"ALLOWLIST_TABLE": "nonexistent-table"}),
        ):
            allowlist_service._resource = None
            event = _sign_up_event(email="user@example.com")

            with pytest.raises(SignupNotAllowedError) as exc_info:
                handler(event, lambda_context)

            assert str(exc_info.value) == REJECT_MESSAGE
            # ClientError の生メッセージ（呼び出した API 名・エラーコード等）が
            # 含まれていないこと。
            assert "ResourceNotFoundException" not in str(exc_info.value)
            assert "GetItem" not in str(exc_info.value)
            assert "nonexistent-table" not in str(exc_info.value)

            allowlist_service._resource = None

    def test_dynamodb_exception_still_raised_internally(self, lambda_context):
        """内部関数レベルでは元の ClientError が送出される（handler が変換前提のため）。"""
        with (
            mock_aws(),
            patch.dict(os.environ, {"ALLOWLIST_TABLE": "nonexistent-table"}),
        ):
            allowlist_service._resource = None
            event = _sign_up_event(email="user@example.com")

            from auth.pre_signup import _handle

            with pytest.raises(ClientError):
                _handle(event, lambda_context)

            allowlist_service._resource = None

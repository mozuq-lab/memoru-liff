"""Unit tests for utils/rate_limiter.py（AI エンドポイントのユーザー単位レート制限）。"""

import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

import utils.rate_limiter as rate_limiter
from utils.rate_limiter import RateLimitExceededError, enforce_rate_limit

TABLE_NAME = "memoru-rate-limits-test"


@pytest.fixture
def rate_limit_table():
    """moto でレート制限テーブルを作成し、モジュールキャッシュをリセットする。"""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "pk", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "pk", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        rate_limiter._table = None
        rate_limiter._table_name = None
        yield dynamodb
        rate_limiter._table = None
        rate_limiter._table_name = None


@pytest.fixture
def rate_limit_env(rate_limit_table):
    """レート制限を有効化する環境変数（上限 3 回 / 300 秒）。"""
    with patch.dict(
        os.environ,
        {
            "RATE_LIMITS_TABLE": TABLE_NAME,
            "AI_RATE_LIMIT_PER_WINDOW": "3",
            "AI_RATE_LIMIT_WINDOW_SECONDS": "300",
        },
    ):
        yield


class TestEnforceRateLimit:
    def test_under_limit_passes(self, rate_limit_env):
        for _ in range(3):
            enforce_rate_limit("user-1")  # 例外なし

    def test_over_limit_raises(self, rate_limit_env):
        for _ in range(3):
            enforce_rate_limit("user-1")

        with pytest.raises(RateLimitExceededError) as exc_info:
            enforce_rate_limit("user-1")

        # Retry-After はウィンドウ残り秒数（1〜300 の範囲）
        assert 1 <= exc_info.value.retry_after_seconds <= 300

    def test_users_are_independent(self, rate_limit_env):
        for _ in range(3):
            enforce_rate_limit("user-1")

        # 別ユーザーは影響を受けない
        enforce_rate_limit("user-2")

        with pytest.raises(RateLimitExceededError):
            enforce_rate_limit("user-1")

    def test_categories_are_independent(self, rate_limit_env):
        for _ in range(3):
            enforce_rate_limit("user-1", category="ai")

        # 別カテゴリは別バケット
        enforce_rate_limit("user-1", category="other")

    def test_noop_when_table_env_unset(self):
        """RATE_LIMITS_TABLE 未設定（ローカル・テスト既定）では制限しない。"""
        env = {k: v for k, v in os.environ.items() if k != "RATE_LIMITS_TABLE"}
        with patch.dict(os.environ, env, clear=True):
            for _ in range(100):
                enforce_rate_limit("user-1")  # テーブル不要・例外なし

    def test_noop_when_disabled(self, rate_limit_env):
        with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "false"}):
            for _ in range(10):
                enforce_rate_limit("user-1")

    def test_fail_open_on_dynamodb_error(self, rate_limit_table):
        """テーブルが存在しない等の DynamoDB エラー時は fail-open で通す。"""
        with patch.dict(
            os.environ, {"RATE_LIMITS_TABLE": "nonexistent-table"}
        ):
            rate_limiter._table = None
            rate_limiter._table_name = None
            enforce_rate_limit("user-1")  # 例外なし（警告ログのみ）

    def test_invalid_limit_env_falls_back_to_default(self, rate_limit_env):
        """不正な上限値設定時は既定値で動作する（例外を出さない）。"""
        with patch.dict(os.environ, {"AI_RATE_LIMIT_PER_WINDOW": "abc"}):
            enforce_rate_limit("user-1")


class TestHandlerIntegration:
    """AI 系エンドポイントで 429 が返ることの確認（enforce をパッチ）。"""

    def _raise_rate_limited(self, *args, **kwargs):
        raise RateLimitExceededError(120)

    def test_generate_cards_returns_429(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="POST",
            path="/cards/generate",
            body={
                "input_text": "テスト用の学習テキストです。十分な長さが必要です。",
                "card_count": 3,
                "difficulty": "medium",
                "language": "ja",
            },
        )

        with patch("api.shared.enforce_rate_limit", side_effect=self._raise_rate_limited):
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 429
        assert response["headers"].get("Retry-After") == "120"
        import json

        body = json.loads(response["body"])
        assert body["code"] == "rate_limited"

    def test_grade_ai_returns_429(self, lambda_context):
        import json

        event = {
            "pathParameters": {"cardId": "card-1"},
            "body": json.dumps({"user_answer": "answer"}),
            "queryStringParameters": {"language": "ja"},
            "requestContext": {
                "authorizer": {"jwt": {"claims": {"sub": "user-1"}}},
            },
            "headers": {},
        }

        with patch("api.shared.enforce_rate_limit", side_effect=self._raise_rate_limited):
            from api.handler import grade_ai_handler

            response = grade_ai_handler(event, MagicMock())

        assert response["statusCode"] == 429
        assert response["headers"]["Retry-After"] == "120"

    def test_tutor_send_message_returns_429(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions/session-1/messages",
            body={"content": "教えて"},
            path_parameters={"session_id": "session-1"},
        )

        with patch("api.shared.enforce_rate_limit", side_effect=self._raise_rate_limited):
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 429

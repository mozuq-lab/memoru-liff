"""POST /cards/refine ハンドラーテスト."""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.ai_service import (
    AIParseError,
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIProviderError,
    RefineResult,
)


def _make_refine_event(
    body: dict | None = None,
    user_id: str = "test-user-id",
) -> dict:
    """POST /cards/refine 用の API Gateway HTTP API v2 イベントを構築."""
    if body is None:
        body = {"front": "クロージャとは？", "back": "変数を覚えてる関数"}
    return {
        "version": "2.0",
        "routeKey": "POST /cards/refine",
        "rawPath": "/cards/refine",
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api-id",
            "authorizer": {
                "jwt": {
                    "claims": {"sub": user_id},
                    "scopes": ["openid", "profile"],
                }
            },
            "http": {"method": "POST"},
            "requestId": "test-request-id",
            "routeKey": "POST /cards/refine",
            "stage": "$default",
        },
        "pathParameters": {},
        "isBase64Encoded": False,
    }


def _make_refine_event_no_auth(body: dict | None = None) -> dict:
    """認証なしの POST /cards/refine イベント."""
    if body is None:
        body = {"front": "テスト", "back": "テスト"}
    return {
        "version": "2.0",
        "routeKey": "POST /cards/refine",
        "rawPath": "/cards/refine",
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api-id",
            "authorizer": {},
            "http": {"method": "POST"},
            "requestId": "test-request-id",
            "routeKey": "POST /cards/refine",
            "stage": "$default",
        },
        "pathParameters": {},
        "isBase64Encoded": False,
    }


class TestRefineCardSuccess:
    """正常系テスト."""

    def test_refine_card_success(self, lambda_context):
        """認証済みユーザーが front と back を送信し結果が返ること."""
        event = _make_refine_event()

        with patch("api.handlers.ai_handler.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.refine_card.return_value = RefineResult(
                refined_front="クロージャとは何か？",
                refined_back="外部スコープの変数を参照し続ける関数。",
                model_used="strands_bedrock",
                processing_time_ms=1200,
            )
            mock_service.model_used = "strands_bedrock"
            mock_factory.return_value = mock_service

            from api.handler import handler
            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["refined_front"] == "クロージャとは何か？"
        assert body["refined_back"] == "外部スコープの変数を参照し続ける関数。"
        assert body["model_used"] == "strands_bedrock"
        assert body["processing_time_ms"] == 1200

    def test_refine_card_front_only(self, lambda_context):
        """表面のみ送信でも成功すること."""
        event = _make_refine_event(body={"front": "クロージャ"})

        with patch("api.handlers.ai_handler.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.refine_card.return_value = RefineResult(
                refined_front="クロージャとは何か？",
                refined_back="",
                model_used="strands_bedrock",
                processing_time_ms=800,
            )
            mock_service.model_used = "strands_bedrock"
            mock_factory.return_value = mock_service

            from api.handler import handler
            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["refined_front"] == "クロージャとは何か？"
        assert body["refined_back"] == ""


class TestRefineCardValidation:
    """バリデーションエラーテスト."""

    def test_both_empty_returns_400(self, lambda_context):
        """front と back の両方が空の場合 400 が返ること."""
        event = _make_refine_event(body={"front": "", "back": ""})

        from api.handler import handler
        response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    def test_front_exceeds_max_length_returns_400(self, lambda_context):
        """front が 1000 文字を超える場合 400 が返ること."""
        event = _make_refine_event(body={"front": "あ" * 1001})

        from api.handler import handler
        response = handler(event, lambda_context)

        assert response["statusCode"] == 400


class TestRefineCardAuth:
    """認証エラーテスト."""

    def test_no_auth_returns_401(self, lambda_context):
        """未認証リクエストで 401 が返ること."""
        event = _make_refine_event_no_auth()

        from api.handler import handler
        response = handler(event, lambda_context)

        assert response["statusCode"] == 401


class TestRefineCardAIErrors:
    """AI サービスエラーテスト."""

    def test_timeout_returns_504(self, lambda_context):
        """AI タイムアウト時に 504 が返ること."""
        event = _make_refine_event()

        with patch("api.handlers.ai_handler.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.refine_card.side_effect = AITimeoutError("timeout")
            mock_factory.return_value = mock_service

            from api.handler import handler
            response = handler(event, lambda_context)

        assert response["statusCode"] == 504

    def test_parse_error_returns_500(self, lambda_context):
        """AI パースエラー時に 500 が返ること."""
        event = _make_refine_event()

        with patch("api.handlers.ai_handler.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.refine_card.side_effect = AIParseError("parse failed")
            mock_factory.return_value = mock_service

            from api.handler import handler
            response = handler(event, lambda_context)

        assert response["statusCode"] == 500

    def test_rate_limit_returns_429(self, lambda_context):
        """レート制限時に 429 が返ること."""
        event = _make_refine_event()

        with patch("api.handlers.ai_handler.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.refine_card.side_effect = AIRateLimitError("rate limit")
            mock_factory.return_value = mock_service

            from api.handler import handler
            response = handler(event, lambda_context)

        assert response["statusCode"] == 429

    def test_provider_error_returns_503(self, lambda_context):
        """AI プロバイダーエラー時に 503 が返ること."""
        event = _make_refine_event()

        with patch("api.handlers.ai_handler.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.refine_card.side_effect = AIProviderError("unavailable")
            mock_factory.return_value = mock_service

            from api.handler import handler
            response = handler(event, lambda_context)

        assert response["statusCode"] == 503

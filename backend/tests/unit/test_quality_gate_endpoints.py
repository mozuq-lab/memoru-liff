"""TASK-0065: 品質ゲート - エンドポイント動作検証.

カテゴリ 7: 全エンドポイント動作検証 (TC-QG-007)
カテゴリ 8: レスポンスフォーマット検証 (TC-QG-008)
カテゴリ 9: クロスエンドポイントエラーマッピング (TC-QG-010)

🔵 信頼性: 既存 test_quality_gate.py から分割。ロジック変更なし。
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from services.ai_service import (
    AIInternalError,
    AIParseError,
    AIProviderError,
    AIRateLimitError,
    AIServiceError,
    AITimeoutError,
)
from tests.unit.conftest import (
    make_advice_event,
    make_generate_event,
    make_grade_ai_event,
    make_mock_ai_service,
    make_mock_card,
    make_mock_review_summary,
)


# =============================================================================
# カテゴリ 7: 全エンドポイント動作検証 (TestEndpointFunctionalFinal)
# =============================================================================


class TestEndpointFunctionalFinal:
    """USE_STRANDS 環境変数の各状態で全 3 AI エンドポイントが HTTP 200 を返すことを最終確認.

    TC-QG-007-001 ~ TC-QG-007-007

    【テスト方針】: create_ai_service() をモックして AI 呼び出しをスタブし、
    ハンドラーのルーティングと環境変数フラグの動作のみを検証する。
    """

    @patch("api.handler.create_ai_service")
    def test_use_strands_true_generate_returns_200(self, mock_factory):
        """TC-QG-007-001: USE_STRANDS=true で POST /cards/generate が HTTP 200 を返す."""
        from api.handler import handler
        mock_factory.return_value = make_mock_ai_service()

        with patch.dict("os.environ", {"USE_STRANDS": "true"}):
            response = handler(make_generate_event(), MagicMock())

        assert response["statusCode"] == 200

    @patch("api.handler.card_service")
    @patch("api.handler.create_ai_service")
    def test_use_strands_true_grade_ai_returns_200(self, mock_factory, mock_card_service):
        """TC-QG-007-002: USE_STRANDS=true で POST /reviews/{cardId}/grade-ai が HTTP 200 を返す."""
        from api.handler import grade_ai_handler
        mock_factory.return_value = make_mock_ai_service()
        mock_card_service.get_card.return_value = make_mock_card()

        with patch.dict("os.environ", {"USE_STRANDS": "true"}):
            response = grade_ai_handler(make_grade_ai_event(), MagicMock())

        assert response["statusCode"] == 200

    @patch("api.handler.review_service")
    @patch("api.handler.create_ai_service")
    def test_use_strands_true_advice_returns_200(self, mock_factory, mock_review_service):
        """TC-QG-007-003: USE_STRANDS=true で GET /advice が HTTP 200 を返す."""
        from api.handler import advice_handler
        mock_factory.return_value = make_mock_ai_service()
        mock_review_service.get_review_summary.return_value = make_mock_review_summary()

        with patch.dict("os.environ", {"USE_STRANDS": "true"}):
            response = advice_handler(make_advice_event(), MagicMock())

        assert response["statusCode"] == 200

    @patch("api.handler.create_ai_service")
    def test_use_strands_false_generate_returns_200(self, mock_factory):
        """TC-QG-007-004: USE_STRANDS=false で POST /cards/generate が HTTP 200 を返す."""
        from api.handler import handler
        mock_factory.return_value = make_mock_ai_service()

        with patch.dict("os.environ", {"USE_STRANDS": "false"}):
            response = handler(make_generate_event(), MagicMock())

        assert response["statusCode"] == 200

    @patch("api.handler.card_service")
    @patch("api.handler.create_ai_service")
    def test_use_strands_false_grade_ai_returns_200(self, mock_factory, mock_card_service):
        """TC-QG-007-005: USE_STRANDS=false で POST /reviews/{cardId}/grade-ai が HTTP 200 を返す."""
        from api.handler import grade_ai_handler
        mock_factory.return_value = make_mock_ai_service()
        mock_card_service.get_card.return_value = make_mock_card()

        with patch.dict("os.environ", {"USE_STRANDS": "false"}):
            response = grade_ai_handler(make_grade_ai_event(), MagicMock())

        assert response["statusCode"] == 200

    @patch("api.handler.review_service")
    @patch("api.handler.create_ai_service")
    def test_use_strands_false_advice_returns_200(self, mock_factory, mock_review_service):
        """TC-QG-007-006: USE_STRANDS=false で GET /advice が HTTP 200 を返す."""
        from api.handler import advice_handler
        mock_factory.return_value = make_mock_ai_service()
        mock_review_service.get_review_summary.return_value = make_mock_review_summary()

        with patch.dict("os.environ", {"USE_STRANDS": "false"}):
            response = advice_handler(make_advice_event(), MagicMock())

        assert response["statusCode"] == 200

    @patch("api.handler.review_service")
    @patch("api.handler.card_service")
    @patch("api.handler.create_ai_service")
    def test_use_strands_unset_all_endpoints_return_200(
        self, mock_factory, mock_card_service, mock_review_service
    ):
        """TC-QG-007-007: USE_STRANDS 未設定で全 3 エンドポイントがデフォルト動作 (HTTP 200)."""
        from api.handler import handler, grade_ai_handler, advice_handler
        mock_factory.return_value = make_mock_ai_service()
        mock_card_service.get_card.return_value = make_mock_card()
        mock_review_service.get_review_summary.return_value = make_mock_review_summary()

        # 【検証】: USE_STRANDS を環境から除去してデフォルト動作（BedrockService）を確認
        env = {k: v for k, v in os.environ.items() if k != "USE_STRANDS"}
        with patch.dict("os.environ", env, clear=True):
            resp1 = handler(make_generate_event(), MagicMock())
            resp2 = grade_ai_handler(make_grade_ai_event(), MagicMock())
            resp3 = advice_handler(make_advice_event(), MagicMock())

        assert resp1["statusCode"] == 200
        assert resp2["statusCode"] == 200
        assert resp3["statusCode"] == 200


# =============================================================================
# カテゴリ 8: レスポンスフォーマット検証 (TestResponseFormatFinal)
# =============================================================================


class TestResponseFormatFinal:
    """各エンドポイントのレスポンス構造が API 仕様に準拠していることを最終確認.

    TC-QG-008-001 ~ TC-QG-008-007

    【テスト方針】: make_mock_ai_service() を使い、レスポンス body の JSON 構造を検証する。
    """

    @patch("api.handler.create_ai_service")
    def test_generate_response_has_generated_cards_and_generation_info(self, mock_factory):
        """TC-QG-008-001: POST /cards/generate レスポンスに generated_cards 配列 + generation_info が含まれる."""
        from api.handler import handler
        mock_factory.return_value = make_mock_ai_service()

        response = handler(make_generate_event(), MagicMock())
        body = json.loads(response["body"])

        assert "generated_cards" in body
        assert isinstance(body["generated_cards"], list)
        assert "generation_info" in body
        assert isinstance(body["generation_info"], dict)

    @patch("api.handler.create_ai_service")
    def test_generate_cards_have_required_fields(self, mock_factory):
        """TC-QG-008-002: POST /cards/generate の generated_cards[].front, back, suggested_tags が存在."""
        from api.handler import handler
        mock_factory.return_value = make_mock_ai_service()

        response = handler(make_generate_event(), MagicMock())
        body = json.loads(response["body"])
        card = body["generated_cards"][0]

        assert "front" in card
        assert "back" in card
        assert "suggested_tags" in card

    @patch("api.handler.create_ai_service")
    def test_generate_info_has_required_fields(self, mock_factory):
        """TC-QG-008-003: POST /cards/generate の generation_info に input_length, model_used, processing_time_ms が存在."""
        from api.handler import handler
        mock_factory.return_value = make_mock_ai_service()

        response = handler(make_generate_event(), MagicMock())
        body = json.loads(response["body"])
        info = body["generation_info"]

        assert "input_length" in info
        assert "model_used" in info
        assert "processing_time_ms" in info

    @patch("api.handler.card_service")
    @patch("api.handler.create_ai_service")
    def test_grade_ai_response_has_required_fields(self, mock_factory, mock_card_service):
        """TC-QG-008-004: POST /reviews/{cardId}/grade-ai レスポンスに grade, reasoning, card_front, card_back, grading_info が含まれる."""
        from api.handler import grade_ai_handler
        mock_factory.return_value = make_mock_ai_service()
        mock_card_service.get_card.return_value = make_mock_card()

        response = grade_ai_handler(make_grade_ai_event(), MagicMock())
        body = json.loads(response["body"])

        assert "grade" in body
        assert "reasoning" in body
        assert "card_front" in body
        assert "card_back" in body
        assert "grading_info" in body

    @patch("api.handler.card_service")
    @patch("api.handler.create_ai_service")
    def test_grade_ai_grade_is_int_in_range(self, mock_factory, mock_card_service):
        """TC-QG-008-005: POST /reviews/{cardId}/grade-ai の grade が int 型で 0-5 範囲."""
        from api.handler import grade_ai_handler
        mock_factory.return_value = make_mock_ai_service()
        mock_card_service.get_card.return_value = make_mock_card()

        response = grade_ai_handler(make_grade_ai_event(), MagicMock())
        body = json.loads(response["body"])

        assert isinstance(body["grade"], int)
        assert 0 <= body["grade"] <= 5

    @patch("api.handler.review_service")
    @patch("api.handler.create_ai_service")
    def test_advice_response_has_required_fields(self, mock_factory, mock_review_service):
        """TC-QG-008-006: GET /advice レスポンスに advice_text, weak_areas, recommendations, study_stats, advice_info が含まれる."""
        from api.handler import advice_handler
        mock_factory.return_value = make_mock_ai_service()
        mock_review_service.get_review_summary.return_value = make_mock_review_summary()

        response = advice_handler(make_advice_event(), MagicMock())
        body = json.loads(response["body"])

        assert "advice_text" in body
        assert "weak_areas" in body
        assert "recommendations" in body
        assert "study_stats" in body
        assert "advice_info" in body

    @patch("api.handler.review_service")
    @patch("api.handler.create_ai_service")
    def test_advice_info_has_required_fields(self, mock_factory, mock_review_service):
        """TC-QG-008-007: GET /advice の advice_info に model_used, processing_time_ms が存在."""
        from api.handler import advice_handler
        mock_factory.return_value = make_mock_ai_service()
        mock_review_service.get_review_summary.return_value = make_mock_review_summary()

        response = advice_handler(make_advice_event(), MagicMock())
        body = json.loads(response["body"])
        info = body["advice_info"]

        assert "model_used" in info
        assert "processing_time_ms" in info


# =============================================================================
# カテゴリ 9: クロスエンドポイントエラーマッピング (TestCrossEndpointErrorMappingFinal)
# =============================================================================


class TestCrossEndpointErrorMappingFinal:
    """AI サービスの各例外タイプが全 3 エンドポイントで同一の HTTP ステータスコードにマッピングされることを最終確認.

    TC-QG-010-001 ~ TC-QG-010-007

    【テスト方針】: _get_responses() で全 3 エンドポイントのレスポンスをまとめて取得し、
    同一エラーに対して同一ステータスコードが返ることを確認する。
    """

    def _make_error_service(self, error: Exception) -> MagicMock:
        """指定した例外を全メソッドで raise するモックサービスを作成する."""
        mock_service = MagicMock()
        mock_service.generate_cards.side_effect = error
        mock_service.grade_answer.side_effect = error
        mock_service.get_learning_advice.side_effect = error
        return mock_service

    def _get_responses(self, mock_factory, error: Exception) -> tuple:
        """全 3 エンドポイントのレスポンスをまとめて取得するヘルパー."""
        from api.handler import handler, grade_ai_handler, advice_handler

        mock_factory.return_value = self._make_error_service(error)

        with patch("api.handler.card_service") as mock_card_service, \
             patch("api.handler.review_service") as mock_review_service:
            mock_card_service.get_card.return_value = make_mock_card()
            mock_review_service.get_review_summary.return_value = make_mock_review_summary()

            resp1 = handler(make_generate_event(), MagicMock())
            resp2 = grade_ai_handler(make_grade_ai_event(), MagicMock())
            resp3 = advice_handler(make_advice_event(), MagicMock())

        return resp1, resp2, resp3

    @patch("api.handler.create_ai_service")
    def test_timeout_error_maps_to_504_all_endpoints(self, mock_factory):
        """TC-QG-010-001: AITimeoutError -> 全 3 エンドポイントで HTTP 504."""
        resp1, resp2, resp3 = self._get_responses(mock_factory, AITimeoutError("timeout"))

        assert resp1["statusCode"] == 504
        assert resp2["statusCode"] == 504
        assert resp3["statusCode"] == 504
        assert json.loads(resp1["body"])["error"] == "AI service timeout"
        assert json.loads(resp2["body"])["error"] == "AI service timeout"
        assert json.loads(resp3["body"])["error"] == "AI service timeout"

    @patch("api.handler.create_ai_service")
    def test_rate_limit_error_maps_to_429_all_endpoints(self, mock_factory):
        """TC-QG-010-002: AIRateLimitError -> 全 3 エンドポイントで HTTP 429."""
        resp1, resp2, resp3 = self._get_responses(mock_factory, AIRateLimitError("rate limit"))

        assert resp1["statusCode"] == 429
        assert resp2["statusCode"] == 429
        assert resp3["statusCode"] == 429
        assert json.loads(resp1["body"])["error"] == "AI service rate limit exceeded"

    @patch("api.handler.create_ai_service")
    def test_provider_error_maps_to_503_all_endpoints(self, mock_factory):
        """TC-QG-010-003: AIProviderError -> 全 3 エンドポイントで HTTP 503."""
        resp1, resp2, resp3 = self._get_responses(mock_factory, AIProviderError("provider down"))

        assert resp1["statusCode"] == 503
        assert resp2["statusCode"] == 503
        assert resp3["statusCode"] == 503
        assert json.loads(resp1["body"])["error"] == "AI service unavailable"

    @patch("api.handler.create_ai_service")
    def test_parse_error_maps_to_500_all_endpoints(self, mock_factory):
        """TC-QG-010-004: AIParseError -> 全 3 エンドポイントで HTTP 500."""
        resp1, resp2, resp3 = self._get_responses(mock_factory, AIParseError("invalid json"))

        assert resp1["statusCode"] == 500
        assert resp2["statusCode"] == 500
        assert resp3["statusCode"] == 500
        assert json.loads(resp1["body"])["error"] == "AI service response parse error"

    @patch("api.handler.create_ai_service")
    def test_internal_error_maps_to_500_all_endpoints(self, mock_factory):
        """TC-QG-010-005: AIInternalError -> 全 3 エンドポイントで HTTP 500."""
        resp1, resp2, resp3 = self._get_responses(mock_factory, AIInternalError("internal failure"))

        assert resp1["statusCode"] == 500
        assert resp2["statusCode"] == 500
        assert resp3["statusCode"] == 500
        assert json.loads(resp1["body"])["error"] == "AI service error"

    @patch("api.handler.create_ai_service")
    def test_base_ai_service_error_maps_to_500_all_endpoints(self, mock_factory):
        """TC-QG-010-006: AIServiceError (基底) -> 全 3 エンドポイントで HTTP 500."""
        resp1, resp2, resp3 = self._get_responses(mock_factory, AIServiceError("generic error"))

        assert resp1["statusCode"] == 500
        assert resp2["statusCode"] == 500
        assert resp3["statusCode"] == 500
        assert json.loads(resp1["body"])["error"] == "AI service error"

    def test_factory_init_failure_maps_to_503_all_endpoints(self):
        """TC-QG-010-007: create_ai_service() 初期化失敗 -> 全 3 エンドポイントで HTTP 503."""
        from api.handler import handler, grade_ai_handler, advice_handler

        with patch("api.handler.create_ai_service") as mock_factory, \
             patch("api.handler.card_service") as mock_card_service, \
             patch("api.handler.review_service") as mock_review_service:

            mock_factory.side_effect = AIProviderError("Failed to initialize")
            mock_card_service.get_card.return_value = make_mock_card()
            mock_review_service.get_review_summary.return_value = make_mock_review_summary()

            resp1 = handler(make_generate_event(), MagicMock())
            resp2 = grade_ai_handler(make_grade_ai_event(), MagicMock())
            resp3 = advice_handler(make_advice_event(), MagicMock())

        assert resp1["statusCode"] == 503
        assert resp2["statusCode"] == 503
        assert resp3["statusCode"] == 503


# =============================================================================
# カバレッジ補完: ハンドラー補助パス (TestHandlerCoveragePaths)
# =============================================================================


class TestHandlerCoveragePaths:
    """handler.py の未カバーパスを補完するテスト群.

    AI エンドポイントに隣接する補助関数・エラーパスの動作を確認する。
    目的: 全体カバレッジを 80% 以上に到達させる。
    """

    def test_get_user_id_from_event_rest_api_cognito_path(self):
        """_get_user_id_from_event が REST API Cognito Authorizer 形式 (claims.claims.sub) を処理できる."""
        from api.handler import _get_user_id_from_event

        event = {
            "requestContext": {
                "authorizer": {
                    "claims": {"sub": "cognito-user-id"}
                }
            }
        }
        result = _get_user_id_from_event(event)
        assert result == "cognito-user-id"

    def test_get_user_id_from_event_direct_sub_path(self):
        """_get_user_id_from_event が直接 sub フィールドを持つ authorizer 形式を処理できる."""
        from api.handler import _get_user_id_from_event

        event = {
            "requestContext": {
                "authorizer": {
                    "sub": "direct-sub-user-id"
                }
            }
        }
        result = _get_user_id_from_event(event)
        assert result == "direct-sub-user-id"

    def test_get_user_id_from_event_dev_jwt_fallback(self):
        """_get_user_id_from_event が ENVIRONMENT=dev 時に Authorization ヘッダーの JWT を解析できる."""
        import base64
        import json as _json
        from api.handler import _get_user_id_from_event

        # Build a minimal JWT with sub claim
        header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
        payload_data = _json.dumps({"sub": "jwt-header-user-id"}).encode()
        payload = base64.urlsafe_b64encode(payload_data).rstrip(b"=").decode()
        token = f"{header}.{payload}.signature"

        event = {
            "requestContext": {"authorizer": {}},
            "headers": {"authorization": f"Bearer {token}"},
        }

        with patch.dict("os.environ", {"ENVIRONMENT": "dev"}):
            result = _get_user_id_from_event(event)

        assert result == "jwt-header-user-id"

    @patch("api.handler.create_ai_service")
    def test_generate_cards_json_decode_error_returns_400(self, mock_factory):
        """generate_cards エンドポイントが無効な JSON ボディに対して HTTP 400 を返す."""
        from api.handler import handler

        event = {
            "version": "2.0",
            "routeKey": "POST /cards/generate",
            "rawPath": "/cards/generate",
            "rawQueryString": "",
            "headers": {"content-type": "application/json"},
            "body": "not-valid-json{{{",
            "requestContext": {
                "accountId": "123456789012",
                "apiId": "api-id",
                "authorizer": {
                    "jwt": {
                        "claims": {"sub": "test-user"},
                        "scopes": ["openid"],
                    }
                },
                "http": {"method": "POST"},
                "requestId": "req-id",
                "routeKey": "POST /cards/generate",
                "stage": "$default",
            },
            "isBase64Encoded": False,
        }

        response = handler(event, MagicMock())
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    @patch("api.handler.create_ai_service")
    def test_handler_stage_prefix_injection(self, mock_factory):
        """main handler() が stage != $default 時に rawPath にステージプレフィックスを付与する."""
        from api.handler import handler
        mock_factory.return_value = make_mock_ai_service()

        event = {
            "version": "2.0",
            "routeKey": "POST /cards/generate",
            "rawPath": "/cards/generate",
            "rawQueryString": "",
            "headers": {"content-type": "application/json"},
            "body": json.dumps({"input_text": "テスト用テキストです。" * 5}),
            "requestContext": {
                "accountId": "123456789012",
                "apiId": "api-id",
                "authorizer": {
                    "jwt": {
                        "claims": {"sub": "test-user"},
                        "scopes": ["openid"],
                    }
                },
                "http": {"method": "POST"},
                "requestId": "req-id",
                "routeKey": "POST /cards/generate",
                "stage": "dev",
            },
            "isBase64Encoded": False,
        }

        # The handler should prepend "/dev" to rawPath before resolving
        response = handler(event, MagicMock())
        # rawPath should now have been modified by handler()
        assert event["rawPath"] == "/dev/cards/generate"

    def test_get_user_id_from_event_dev_jwt_fallback_exception(self):
        """_get_user_id_from_event が ENVIRONMENT=dev で JWT デコード失敗時に None を返す."""
        from api.handler import _get_user_id_from_event

        # Provide a malformed token that will fail base64 decoding
        event = {
            "requestContext": {"authorizer": {}},
            "headers": {"authorization": "Bearer bad.not-base64!@#.sig"},
        }

        with patch.dict("os.environ", {"ENVIRONMENT": "dev"}):
            result = _get_user_id_from_event(event)

        assert result is None

    @patch("api.handler.card_service")
    @patch("api.handler.create_ai_service")
    def test_grade_ai_generic_exception_returns_500(self, mock_factory, mock_card_service):
        """grade_ai_handler の汎用例外ハンドラーが予期しない例外に対して HTTP 500 を返す."""
        from api.handler import grade_ai_handler

        mock_card_service.get_card.side_effect = RuntimeError("unexpected db error")

        response = grade_ai_handler(make_grade_ai_event(), MagicMock())

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "Internal Server Error"

    @patch("api.handler.create_ai_service")
    def test_generate_cards_generic_exception_raises(self, mock_factory):
        """generate_cards エンドポイントが非 AIServiceError 例外をログして re-raise する."""
        import pytest
        from api.handler import handler

        mock_factory.side_effect = RuntimeError("unexpected infrastructure error")

        # The except Exception branch logs the error and re-raises
        # Powertools propagates the raise as a 500 or re-raises it through the stack
        with pytest.raises((RuntimeError, Exception)):
            handler(make_generate_event(), MagicMock())

    def test_generate_cards_request_whitespace_only_raises_validation_error(self):
        """GenerateCardsRequest が空白のみのテキストで ValueError を raise する."""
        import pytest
        from pydantic import ValidationError
        from models.generate import GenerateCardsRequest

        with pytest.raises(ValidationError):
            GenerateCardsRequest(input_text="          ")

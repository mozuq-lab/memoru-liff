"""TASK-0065: 品質ゲート - エンドポイント動作検証（ai-async-jobs 版）.

カテゴリ 7: 全 submit エンドポイント動作検証（旧: 全エンドポイント 200 → 202）
カテゴリ 8: レスポンスフォーマット検証（executor result の薄い確認。
            厳密な形状は tests/unit/test_ai_job_executors.py に移設）
カテゴリ 9/10: クロスエンドポイントエラーマッピング（executor +
            classify_ai_job_error の組で旧ステータスとの一致を検証）

ai-async-jobs: AI 系 7 エンドポイントは submit（202 + job_id）に変換されたため、
- 「全エンドポイント 200」→「全 submit エンドポイント 202」
- 「レスポンス形状」→ executor の result dict 検証
- 「エラーマッピング」→ executor 例外 + classify_ai_job_error の status 検証
に書き換えた。USE_STRANDS フラグによるサービス選択は submit 経路に影響しない
（executor 内の create_ai_service で解決される。test_migration_compat.py の
TestFeatureFlagBehavior が担保）。
"""

import json
from unittest.mock import MagicMock, patch

import pytest


from services.ai_job_errors import classify_ai_job_error
from services.ai_job_executors import (
    execute_advice,
    execute_generate,
    execute_grade_ai,
)
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

GENERATE_PAYLOAD = {
    "input_text": "テスト用のテキストです。" * 5,
    "card_count": 3,
    "difficulty": "medium",
    "language": "ja",
}
GRADE_PAYLOAD = {"card_id": "card-123", "user_answer": "東京", "language": "ja"}
ADVICE_PAYLOAD = {"language": "ja"}


def _submit_result(job_type: str) -> dict:
    """submit_ai_job モックの戻り値（作成直後の queued ジョブレコード相当）."""
    return {"job_id": "aijob_qg", "job_type": job_type, "status": "queued"}


# =============================================================================
# カテゴリ 7: 全 submit エンドポイント動作検証 (TestSubmitEndpointsReturn202)
# =============================================================================


class TestSubmitEndpointsReturn202:
    """全 AI submit エンドポイントが HTTP 202 + ジョブ情報を返すことを最終確認.

    旧 TC-QG-007（全エンドポイント 200）の後継。
    【テスト方針】: submit_ai_job をモックして AI 実行・DynamoDB をスタブし、
    ルーティングと 202 変換のみを検証する。
    """

    def _assert_202(self, response, job_type):
        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body == {
            "job_id": "aijob_qg",
            "job_type": job_type,
            "status": "queued",
        }

    def test_generate_returns_202(self):
        """POST /cards/generate が 202 を返す."""
        from api.handler import handler

        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            mock_submit.return_value = _submit_result("generate")
            response = handler(make_generate_event(), MagicMock())

        self._assert_202(response, "generate")

    def test_generate_from_url_returns_202(self, api_gateway_event):
        """POST /cards/generate-from-url が 202 を返す."""
        from api.handler import handler

        event = api_gateway_event(
            method="POST",
            path="/cards/generate-from-url",
            body={"url": "https://example.com/page"},
        )
        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            mock_submit.return_value = _submit_result("generate_from_url")
            response = handler(event, MagicMock())

        self._assert_202(response, "generate_from_url")

    def test_refine_returns_202(self, api_gateway_event):
        """POST /cards/refine が 202 を返す."""
        from api.handler import handler

        event = api_gateway_event(
            method="POST",
            path="/cards/refine",
            body={"front": "クロージャとは？", "back": "変数を覚えてる関数"},
        )
        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            mock_submit.return_value = _submit_result("refine")
            response = handler(event, MagicMock())

        self._assert_202(response, "refine")

    def test_grade_ai_returns_202(self):
        """POST /reviews/{cardId}/grade-ai が 202 を返す."""
        from api.handler import grade_ai_handler

        with patch("api.handler.submit_ai_job") as mock_submit, patch(
            "api.handler.card_service"
        ) as mock_card_service:
            mock_submit.return_value = _submit_result("grade_ai")
            mock_card_service.get_card.return_value = make_mock_card()
            response = grade_ai_handler(make_grade_ai_event(), MagicMock())

        self._assert_202(response, "grade_ai")

    def test_advice_returns_202(self):
        """POST /advice が 202 を返す."""
        from api.handler import advice_handler

        with patch("api.handler.submit_ai_job") as mock_submit:
            mock_submit.return_value = _submit_result("advice")
            response = advice_handler(make_advice_event(), MagicMock())

        self._assert_202(response, "advice")

    def test_tutor_start_returns_202(self, api_gateway_event):
        """POST /tutor/sessions が 202 を返す."""
        from api.handler import handler

        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions",
            body={"deck_id": "deck_001", "mode": "free_talk"},
        )
        with patch("api.handlers.tutor_handler.tutor_service"), patch(
            "api.handlers.tutor_handler.submit_ai_job"
        ) as mock_submit:
            mock_submit.return_value = _submit_result("tutor_start")
            response = handler(event, MagicMock())

        self._assert_202(response, "tutor_start")

    def test_tutor_message_returns_202(self, api_gateway_event):
        """POST /tutor/sessions/{sessionId}/messages が 202 を返す."""
        from api.handler import handler

        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions/tutor_test-id/messages",
            body={"content": "hello"},
            path_parameters={"sessionId": "tutor_test-id"},
        )
        with patch("api.handlers.tutor_handler.tutor_service"), patch(
            "api.handlers.tutor_handler.submit_ai_job"
        ) as mock_submit:
            mock_submit.return_value = _submit_result("tutor_message")
            response = handler(event, MagicMock())

        self._assert_202(response, "tutor_message")


# =============================================================================
# カテゴリ 8: レスポンスフォーマット検証 (TestResponseFormatFinal)
# =============================================================================


class TestResponseFormatFinal:
    """各 executor の result が API 仕様（旧同期レスポンス）に準拠していることを最終確認.

    旧 TC-QG-008 の後継。厳密なフィールド値の検証は
    tests/unit/test_ai_job_executors.py に移設したため、ここでは executor を
    inline で通した result の必須トップレベル構造のみを薄く確認する。
    """

    def _run_generate(self):
        with patch("services.ai_job_executors.create_ai_service") as mock_factory:
            mock_factory.return_value = make_mock_ai_service()
            return execute_generate("test-user-id", dict(GENERATE_PAYLOAD))

    def _run_grade_ai(self):
        with patch("services.ai_job_executors.CardService") as mock_card_cls, patch(
            "services.ai_job_executors.create_ai_service"
        ) as mock_factory:
            mock_card_cls.return_value.get_card.return_value = make_mock_card()
            mock_factory.return_value = make_mock_ai_service()
            return execute_grade_ai("test-user-id", dict(GRADE_PAYLOAD))

    def _run_advice(self):
        with patch("services.ai_job_executors.UserService") as mock_user_cls, patch(
            "services.ai_job_executors.ReviewService"
        ) as mock_review_cls, patch(
            "services.ai_job_executors.create_ai_service"
        ) as mock_factory:
            mock_user_cls.return_value.get_or_create_user.return_value.settings = {}
            mock_review_cls.return_value.get_review_summary.return_value = (
                make_mock_review_summary()
            )
            mock_factory.return_value = make_mock_ai_service()
            return execute_advice("test-user-id", dict(ADVICE_PAYLOAD))

    def test_generate_result_has_generated_cards_and_generation_info(self):
        """TC-QG-008-001: generate result に generated_cards 配列 + generation_info が含まれる."""
        result = self._run_generate()

        assert "generated_cards" in result
        assert isinstance(result["generated_cards"], list)
        assert "generation_info" in result
        assert isinstance(result["generation_info"], dict)

    def test_generate_cards_have_required_fields(self):
        """TC-QG-008-002: generated_cards[].front, back, suggested_tags が存在."""
        result = self._run_generate()
        card = result["generated_cards"][0]

        assert "front" in card
        assert "back" in card
        assert "suggested_tags" in card

    def test_generate_info_has_required_fields(self):
        """TC-QG-008-003: generation_info に input_length, model_used, processing_time_ms が存在."""
        result = self._run_generate()
        info = result["generation_info"]

        assert "input_length" in info
        assert "model_used" in info
        assert "processing_time_ms" in info

    def test_grade_ai_result_has_required_fields(self):
        """TC-QG-008-004: grade_ai result に grade, reasoning, card_front, card_back, grading_info が含まれる."""
        result = self._run_grade_ai()

        assert "grade" in result
        assert "reasoning" in result
        assert "card_front" in result
        assert "card_back" in result
        assert "grading_info" in result

    def test_grade_ai_grade_is_int_in_range(self):
        """TC-QG-008-005: grade_ai result の grade が int 型で 0-5 範囲."""
        result = self._run_grade_ai()

        assert isinstance(result["grade"], int)
        assert 0 <= result["grade"] <= 5

    def test_advice_result_has_required_fields(self):
        """TC-QG-008-006: advice result に advice_text, weak_areas, recommendations, study_stats, advice_info が含まれる."""
        result = self._run_advice()

        assert "advice_text" in result
        assert "weak_areas" in result
        assert "recommendations" in result
        assert "study_stats" in result
        assert "advice_info" in result

    def test_advice_info_has_required_fields(self):
        """TC-QG-008-007: advice result の advice_info に model_used, processing_time_ms が存在."""
        result = self._run_advice()
        info = result["advice_info"]

        assert "model_used" in info
        assert "processing_time_ms" in info


# =============================================================================
# カテゴリ 9/10: クロスエンドポイントエラーマッピング (TestCrossEndpointErrorMappingFinal)
# =============================================================================


class TestCrossEndpointErrorMappingFinal:
    """AI 例外が全 executor で同一の旧 HTTP ステータスに分類されることを最終確認.

    旧 TC-QG-010 の後継。旧同期実装では map_ai_error_to_http が全エンドポイント
    共通のステータス・文言を返していた。現在は executor から素の例外が伝播し、
    classify_ai_job_error が failed ジョブの error {status, code, message} に
    分類するため、「executor + classify」の組で同一の status / message になる
    ことを横断検証する。
    """

    def _collect_job_errors(self, error: Exception) -> list:
        """全 3 executor を同一の AI 例外で実行し、classify 結果を集める."""
        error_service = MagicMock()
        error_service.generate_cards.side_effect = error
        error_service.grade_answer.side_effect = error
        error_service.get_learning_advice.side_effect = error

        job_errors = []

        with patch(
            "services.ai_job_executors.create_ai_service", return_value=error_service
        ), patch("services.ai_job_executors.CardService") as mock_card_cls, patch(
            "services.ai_job_executors.UserService"
        ) as mock_user_cls, patch(
            "services.ai_job_executors.ReviewService"
        ) as mock_review_cls:
            mock_card_cls.return_value.get_card.return_value = make_mock_card()
            mock_user_cls.return_value.get_or_create_user.return_value.settings = {}
            mock_review_cls.return_value.get_review_summary.return_value = (
                make_mock_review_summary()
            )

            for executor, payload in [
                (execute_generate, GENERATE_PAYLOAD),
                (execute_grade_ai, GRADE_PAYLOAD),
                (execute_advice, ADVICE_PAYLOAD),
            ]:
                with pytest.raises(type(error)) as exc_info:
                    executor("test-user-id", dict(payload))
                job_errors.append(classify_ai_job_error(exc_info.value))

        return job_errors

    def _assert_uniform(self, job_errors, status, code, message):
        for job_error in job_errors:
            assert job_error.status == status
            assert job_error.code == code
            assert job_error.message == message

    def test_timeout_error_maps_to_504_all_executors(self):
        """TC-QG-010-001: AITimeoutError -> 全 executor で failed(504) + 旧文言."""
        job_errors = self._collect_job_errors(AITimeoutError("timeout"))
        self._assert_uniform(job_errors, 504, "ai_timeout", "AI service timeout")

    def test_rate_limit_error_maps_to_429_all_executors(self):
        """TC-QG-010-002: AIRateLimitError -> 全 executor で failed(429) + 旧文言."""
        job_errors = self._collect_job_errors(AIRateLimitError("rate limit"))
        self._assert_uniform(
            job_errors, 429, "ai_rate_limit", "AI service rate limit exceeded"
        )

    def test_provider_error_maps_to_503_all_executors(self):
        """TC-QG-010-003: AIProviderError -> 全 executor で failed(503) + 旧文言."""
        job_errors = self._collect_job_errors(AIProviderError("provider down"))
        self._assert_uniform(
            job_errors, 503, "ai_unavailable", "AI service unavailable"
        )

    def test_parse_error_maps_to_500_all_executors(self):
        """TC-QG-010-004: AIParseError -> 全 executor で failed(500) + 旧文言."""
        job_errors = self._collect_job_errors(AIParseError("invalid json"))
        self._assert_uniform(
            job_errors, 500, "ai_error", "AI service response parse error"
        )

    def test_internal_error_maps_to_500_all_executors(self):
        """TC-QG-010-005: AIInternalError -> 全 executor で failed(500) + 旧文言."""
        job_errors = self._collect_job_errors(AIInternalError("internal failure"))
        self._assert_uniform(job_errors, 500, "ai_error", "AI service error")

    def test_base_ai_service_error_maps_to_500_all_executors(self):
        """TC-QG-010-006: AIServiceError (基底) -> 全 executor で failed(500) + 旧文言."""
        job_errors = self._collect_job_errors(AIServiceError("generic error"))
        self._assert_uniform(job_errors, 500, "ai_error", "AI service error")

    def test_factory_init_failure_maps_to_503_all_executors(self):
        """TC-QG-010-007: create_ai_service() 初期化失敗 -> 全 executor で failed(503)."""
        job_errors = []

        with patch(
            "services.ai_job_executors.create_ai_service",
            side_effect=AIProviderError("Failed to initialize"),
        ), patch("services.ai_job_executors.CardService") as mock_card_cls, patch(
            "services.ai_job_executors.UserService"
        ) as mock_user_cls, patch(
            "services.ai_job_executors.ReviewService"
        ) as mock_review_cls:
            mock_card_cls.return_value.get_card.return_value = make_mock_card()
            mock_user_cls.return_value.get_or_create_user.return_value.settings = {}
            mock_review_cls.return_value.get_review_summary.return_value = (
                make_mock_review_summary()
            )

            for executor, payload in [
                (execute_generate, GENERATE_PAYLOAD),
                (execute_grade_ai, GRADE_PAYLOAD),
                (execute_advice, ADVICE_PAYLOAD),
            ]:
                with pytest.raises(AIProviderError) as exc_info:
                    executor("test-user-id", dict(payload))
                job_errors.append(classify_ai_job_error(exc_info.value))

        self._assert_uniform(
            job_errors, 503, "ai_unavailable", "AI service unavailable"
        )


# =============================================================================
# カバレッジ補完: ハンドラー補助パス (TestHandlerCoveragePaths)
# =============================================================================


class TestHandlerCoveragePaths:
    """handler.py / shared.py の未カバーパスを補完するテスト群.

    AI エンドポイントに隣接する補助関数・エラーパスの動作を確認する。
    目的: 全体カバレッジを 80% 以上に到達させる。
    """

    def test_get_user_id_from_event_rest_api_cognito_path(self):
        """get_user_id_from_event が REST API Cognito Authorizer 形式 (claims.claims.sub) を処理できる."""
        from api.shared import get_user_id_from_event

        event = {
            "requestContext": {
                "authorizer": {
                    "claims": {"sub": "cognito-user-id"}
                }
            }
        }
        result = get_user_id_from_event(event)
        assert result == "cognito-user-id"

    def test_get_user_id_from_event_direct_sub_path(self):
        """get_user_id_from_event が直接 sub フィールドを持つ authorizer 形式を処理できる."""
        from api.shared import get_user_id_from_event

        event = {
            "requestContext": {
                "authorizer": {
                    "sub": "direct-sub-user-id"
                }
            }
        }
        result = get_user_id_from_event(event)
        assert result == "direct-sub-user-id"

    def test_get_user_id_from_event_dev_jwt_fallback(self):
        """get_user_id_from_event が ENVIRONMENT=dev + AWS_SAM_LOCAL=true 時に JWT を解析できる."""
        import base64
        import json as _json
        from api.shared import get_user_id_from_event

        # Build a minimal JWT with sub claim
        header = base64.urlsafe_b64encode(b'{"alg":"RS256"}').rstrip(b"=").decode()
        payload_data = _json.dumps({"sub": "jwt-header-user-id"}).encode()
        payload = base64.urlsafe_b64encode(payload_data).rstrip(b"=").decode()
        token = f"{header}.{payload}.signature"

        event = {
            "requestContext": {"authorizer": {}},
            "headers": {"authorization": f"Bearer {token}"},
        }

        with patch.dict("os.environ", {"ENVIRONMENT": "dev", "AWS_SAM_LOCAL": "true"}):
            result = get_user_id_from_event(event)

        assert result == "jwt-header-user-id"

    def test_generate_cards_json_decode_error_returns_400(self):
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

        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            response = handler(event, MagicMock())

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        mock_submit.assert_not_called()

    def test_handler_stage_prefix_injection(self):
        """main handler() が stage != $default 時に rawPath にステージプレフィックスを付与する."""
        from api.handler import handler

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
        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            mock_submit.return_value = _submit_result("generate")
            handler(event, MagicMock())

        # rawPath should now have been modified by handler()
        assert event["rawPath"] == "/dev/cards/generate"

    def test_get_user_id_from_event_dev_jwt_fallback_exception(self):
        """get_user_id_from_event が ENVIRONMENT=dev + AWS_SAM_LOCAL=true で JWT デコード失敗時に None を返す."""
        from api.shared import get_user_id_from_event

        # Provide a malformed token that will fail base64 decoding
        event = {
            "requestContext": {"authorizer": {}},
            "headers": {"authorization": "Bearer bad.not-base64!@#.sig"},
        }

        with patch.dict("os.environ", {"ENVIRONMENT": "dev", "AWS_SAM_LOCAL": "true"}):
            result = get_user_id_from_event(event)

        assert result is None

    @patch("api.handler.card_service")
    def test_grade_ai_generic_exception_returns_500(self, mock_card_service):
        """grade_ai_handler の汎用例外ハンドラーが予期しない例外に対して HTTP 500 を返す."""
        from api.handler import grade_ai_handler

        mock_card_service.get_card.side_effect = RuntimeError("unexpected db error")

        response = grade_ai_handler(make_grade_ai_event(), MagicMock())

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "Internal Server Error"

    def test_generate_cards_generic_exception_raises(self):
        """generate_cards エンドポイントが submit 時の非 AIServiceError 例外を re-raise する."""
        from api.handler import handler

        # The unhandled exception propagates through the resolver stack
        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            mock_submit.side_effect = RuntimeError("unexpected infrastructure error")

            with pytest.raises((RuntimeError, Exception)):
                handler(make_generate_event(), MagicMock())

    def test_generate_cards_request_whitespace_only_raises_validation_error(self):
        """GenerateCardsRequest が空白のみのテキストで ValueError を raise する."""
        from pydantic import ValidationError
        from models.generate import GenerateCardsRequest

        with pytest.raises(ValidationError):
            GenerateCardsRequest(input_text="          ")

    def test_generate_cards_request_default_card_count_is_3(self):
        """card_count 未指定時の既定値が 3 枚であること（テキスト生成の既定）."""
        from models.generate import GenerateCardsRequest

        request = GenerateCardsRequest(input_text="十分な長さのテキスト")
        assert request.card_count == 3

    def test_generate_cards_request_card_count_range_1_to_10(self):
        """card_count は 1〜10 を受け付け、範囲外は ValidationError になること."""
        from pydantic import ValidationError
        from models.generate import GenerateCardsRequest

        text = "十分な長さのテキスト"
        assert GenerateCardsRequest(input_text=text, card_count=1).card_count == 1
        assert GenerateCardsRequest(input_text=text, card_count=10).card_count == 10
        with pytest.raises(ValidationError):
            GenerateCardsRequest(input_text=text, card_count=0)
        with pytest.raises(ValidationError):
            GenerateCardsRequest(input_text=text, card_count=11)

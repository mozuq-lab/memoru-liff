"""TASK-0062: GET /advice エンドポイントのテスト。

advice_handler Lambda ハンドラーの本実装に対するテストケース。
構造的前提:
- advice_handler は独立 Lambda 関数（app/APIGatewayHttpResolver 経由ではない）
- 生の API Gateway HTTP API v2 イベントを直接受け取る
- レスポンスは Lambda プロキシ統合形式の dict（statusCode, headers, body）
- GET リクエストのためリクエストボディのパースは不要
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from api.handler import advice_handler
from services.ai_service import (
    AIInternalError,
    AIParseError,
    AIProviderError,
    AIRateLimitError,
    AIServiceError,
    AITimeoutError,
    LearningAdvice,
    ReviewSummary,
)


# =============================================================================
# テスト共通ヘルパー
# =============================================================================


def _make_advice_event(
    user_id: str = "test-user-id",
    query_params: dict | None = None,
    authorizer: dict | None = None,
) -> dict:
    """advice_handler 用の API Gateway HTTP API v2 イベントを構築する。

    Args:
        user_id: JWT claims の sub クレーム。
        query_params: クエリストリングパラメータ（language 等）。
        authorizer: リクエストコンテキストの authorizer。None の場合は標準 JWT 形式。

    Returns:
        API Gateway HTTP API v2 形式のイベント辞書。
    """
    if authorizer is None:
        authorizer = {
            "jwt": {
                "claims": {"sub": user_id},
                "scopes": ["openid", "profile"],
            }
        }
    event = {
        "version": "2.0",
        "routeKey": "GET /advice",
        "rawPath": "/advice",
        "rawQueryString": "",
        "pathParameters": None,
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api-id",
            "authorizer": authorizer,
            "http": {"method": "GET"},
            "requestId": "test-request-id",
            "routeKey": "GET /advice",
            "stage": "$default",
        },
        "headers": {"content-type": "application/json"},
        "isBase64Encoded": False,
    }
    if query_params:
        event["queryStringParameters"] = query_params
    return event


# =============================================================================
# 共通フィクスチャ
# =============================================================================


@pytest.fixture
def mock_review_service():
    """ReviewService のモック。ReviewSummary を返す。

    パッチ対象: api.handler.review_service（モジュールレベルグローバル変数）
    """
    with patch("api.handler.review_service") as mock:
        mock.get_review_summary.return_value = ReviewSummary(
            total_reviews=100,
            average_grade=3.5,
            total_cards=50,
            cards_due_today=10,
            streak_days=5,
            tag_performance={"math": 0.8, "science": 0.6},
            recent_review_dates=["2026-02-24", "2026-02-23"],
        )
        yield mock


@pytest.fixture
def mock_ai_service():
    """create_ai_service のモック。LearningAdvice を返す。

    パッチ対象: api.handler.create_ai_service（インポートされた関数）

    Yields:
        tuple: (mock_factory, mock_service)
    """
    with patch("api.handler.create_ai_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.get_learning_advice.return_value = LearningAdvice(
            advice_text="数学の復習頻度を上げましょう。",
            weak_areas=["数学", "物理"],
            recommendations=["毎日10枚のカードを復習する", "弱点タグを重点的に復習"],
            model_used="test-model",
            processing_time_ms=800,
        )
        mock_factory.return_value = mock_service
        yield mock_factory, mock_service


# =============================================================================
# カテゴリ A: 認証テスト（TestAdviceHandlerAuth）
# =============================================================================


class TestAdviceHandlerAuth:
    """認証関連テスト（TC-062-AUTH-001 ~ 003）。"""

    def test_advice_returns_401_when_no_authorizer(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-AUTH-001: authorizer が空の場合に HTTP 401 を返すことを確認."""
        event = _make_advice_event(authorizer={})

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert body["error"] == "Unauthorized"

    def test_advice_returns_401_when_no_sub_claim(self, lambda_context):
        """TC-062-AUTH-002: JWT claims に sub がない場合に HTTP 401 を返すことを確認."""
        authorizer = {"jwt": {"claims": {"iss": "https://keycloak.example.com"}}}
        event = _make_advice_event(authorizer=authorizer)

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert body["error"] == "Unauthorized"

    def test_advice_extracts_user_id_from_jwt_claims(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-AUTH-003: JWT claims.sub から user_id を正しく抽出することを確認."""
        event = _make_advice_event(user_id="user-abc-123")

        advice_handler(event, lambda_context)

        mock_review_service.get_review_summary.assert_called_once_with("user-abc-123")


# =============================================================================
# カテゴリ B: データフローテスト（TestAdviceHandlerFlow）
# =============================================================================


class TestAdviceHandlerFlow:
    """データフロー関連テスト（TC-062-FLOW-001 ~ 005）。"""

    def test_advice_calls_get_review_summary(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-FLOW-001: review_service.get_review_summary が呼ばれることを確認."""
        event = _make_advice_event()

        advice_handler(event, lambda_context)

        mock_review_service.get_review_summary.assert_called_once_with("test-user-id")

    def test_advice_calls_create_ai_service_factory(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-FLOW-002: create_ai_service() ファクトリーが 1 回呼ばれることを確認."""
        mock_factory, _ = mock_ai_service
        event = _make_advice_event()

        advice_handler(event, lambda_context)

        mock_factory.assert_called_once()

    def test_advice_passes_review_summary_dict_to_ai_service(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-FLOW-003: ReviewSummary が dict に変換されて AI サービスに渡されることを確認."""
        _, mock_service = mock_ai_service
        event = _make_advice_event()

        advice_handler(event, lambda_context)

        # get_learning_advice が呼ばれたことを確認
        mock_service.get_learning_advice.assert_called_once()
        call_kwargs = mock_service.get_learning_advice.call_args.kwargs
        # review_summary は dict であること
        assert isinstance(call_kwargs["review_summary"], dict)
        # 元の ReviewSummary のフィールドが含まれること
        assert call_kwargs["review_summary"]["total_reviews"] == 100
        assert call_kwargs["review_summary"]["average_grade"] == 3.5

    def test_advice_passes_language_param_to_ai_service(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-FLOW-004: language=en が AI サービスに渡されることを確認."""
        _, mock_service = mock_ai_service
        event = _make_advice_event(query_params={"language": "en"})

        advice_handler(event, lambda_context)

        call_kwargs = mock_service.get_learning_advice.call_args.kwargs
        assert call_kwargs["language"] == "en"

    def test_advice_uses_default_language_ja(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-FLOW-005: queryStringParameters なしでデフォルト language=ja を確認."""
        _, mock_service = mock_ai_service
        event = _make_advice_event()  # query_params なし

        advice_handler(event, lambda_context)

        call_kwargs = mock_service.get_learning_advice.call_args.kwargs
        assert call_kwargs["language"] == "ja"


# =============================================================================
# カテゴリ C: 正常系レスポンステスト（TestAdviceHandlerSuccess）
# =============================================================================


class TestAdviceHandlerSuccess:
    """正常系レスポンステスト（TC-062-RES-001 ~ 008）。"""

    def test_advice_success_returns_200(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-RES-001: 正常系で HTTP 200 が返ることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 200

    def test_advice_success_response_contains_advice_text(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-RES-002: レスポンスに advice_text が正しく含まれることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        body = json.loads(response["body"])
        assert body["advice_text"] == "数学の復習頻度を上げましょう。"

    def test_advice_success_response_contains_weak_areas(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-RES-003: レスポンスに weak_areas が正しく含まれることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        body = json.loads(response["body"])
        assert body["weak_areas"] == ["数学", "物理"]

    def test_advice_success_response_contains_recommendations(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-RES-004: レスポンスに recommendations が正しく含まれることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        body = json.loads(response["body"])
        assert len(body["recommendations"]) == 2
        assert "毎日10枚のカードを復習する" in body["recommendations"]

    def test_advice_success_response_contains_study_stats(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-RES-005: レスポンスに study_stats が正しく含まれることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        body = json.loads(response["body"])
        assert "study_stats" in body
        stats = body["study_stats"]
        assert stats["total_reviews"] == 100
        assert stats["average_grade"] == 3.5
        assert stats["total_cards"] == 50
        assert stats["cards_due_today"] == 10
        assert stats["streak_days"] == 5

    def test_advice_success_response_contains_advice_info(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-RES-006: レスポンスに advice_info が正しく含まれることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        body = json.loads(response["body"])
        assert "advice_info" in body
        assert body["advice_info"]["model_used"] == "test-model"
        assert body["advice_info"]["processing_time_ms"] == 800

    def test_advice_success_response_is_json(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-RES-007: Content-Type が application/json であることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 200
        assert response["headers"]["Content-Type"] == "application/json"

    def test_advice_success_full_e2e_flow(self, lambda_context):
        """TC-062-RES-008: 認証 -> ReviewSummary -> AI -> レスポンスの一連 E2E フロー."""
        with patch("api.handler.review_service") as mock_rs, \
             patch("api.handler.create_ai_service") as mock_factory:
            # カスタム ReviewSummary
            mock_rs.get_review_summary.return_value = ReviewSummary(
                total_reviews=200,
                average_grade=4.0,
                total_cards=80,
                cards_due_today=15,
                streak_days=10,
                tag_performance={"english": 0.9},
                recent_review_dates=["2026-02-24"],
            )
            # カスタム AI 結果
            mock_service = MagicMock()
            mock_service.get_learning_advice.return_value = LearningAdvice(
                advice_text="英語の学習は順調です。",
                weak_areas=["英語リスニング"],
                recommendations=["リスニング教材を追加する"],
                model_used="claude-3-haiku",
                processing_time_ms=600,
            )
            mock_factory.return_value = mock_service

            event = _make_advice_event(
                user_id="e2e-user",
                query_params={"language": "ja"},
            )

            response = advice_handler(event, lambda_context)

        # 全フィールドを検証
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["advice_text"] == "英語の学習は順調です。"
        assert body["weak_areas"] == ["英語リスニング"]
        assert body["recommendations"] == ["リスニング教材を追加する"]
        assert body["study_stats"]["total_reviews"] == 200
        assert body["study_stats"]["average_grade"] == 4.0
        assert body["study_stats"]["total_cards"] == 80
        assert body["study_stats"]["cards_due_today"] == 15
        assert body["study_stats"]["streak_days"] == 10
        assert body["advice_info"]["model_used"] == "claude-3-haiku"
        assert body["advice_info"]["processing_time_ms"] == 600

        # コール引数を検証
        mock_rs.get_review_summary.assert_called_once_with("e2e-user")
        mock_factory.assert_called_once()
        call_kwargs = mock_service.get_learning_advice.call_args.kwargs
        assert call_kwargs["review_summary"]["total_reviews"] == 200
        assert call_kwargs["language"] == "ja"


# =============================================================================
# カテゴリ D: AI エラーハンドリングテスト（TestAdviceHandlerAIErrors）
# =============================================================================


class TestAdviceHandlerAIErrors:
    """AI エラーハンドリングテスト（TC-062-ERR-001 ~ 007）。

    _map_ai_error_to_http() を使用した AI 例外の HTTP マッピングを検証。
    """

    def test_advice_returns_504_on_ai_timeout(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-ERR-001: AITimeoutError が HTTP 504 にマッピングされることを確認."""
        _, mock_service = mock_ai_service
        mock_service.get_learning_advice.side_effect = AITimeoutError("timeout")
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 504
        body = json.loads(response["body"])
        assert body["error"] == "AI service timeout"

    def test_advice_returns_429_on_ai_rate_limit(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-ERR-002: AIRateLimitError が HTTP 429 にマッピングされることを確認."""
        _, mock_service = mock_ai_service
        mock_service.get_learning_advice.side_effect = AIRateLimitError("rate limit")
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 429
        body = json.loads(response["body"])
        assert body["error"] == "AI service rate limit exceeded"

    def test_advice_returns_503_on_ai_provider_error(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-ERR-003: AIProviderError が HTTP 503 にマッピングされることを確認."""
        _, mock_service = mock_ai_service
        mock_service.get_learning_advice.side_effect = AIProviderError("provider down")
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 503
        body = json.loads(response["body"])
        assert body["error"] == "AI service unavailable"

    def test_advice_returns_500_on_ai_parse_error(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-ERR-004: AIParseError が HTTP 500 にマッピングされることを確認."""
        _, mock_service = mock_ai_service
        mock_service.get_learning_advice.side_effect = AIParseError("invalid json")
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "AI service response parse error"

    def test_advice_returns_500_on_ai_internal_error(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-ERR-005: AIInternalError が HTTP 500 にマッピングされることを確認."""
        _, mock_service = mock_ai_service
        mock_service.get_learning_advice.side_effect = AIInternalError("internal failure")
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "AI service error"

    def test_advice_returns_503_on_factory_init_failure(
        self, lambda_context, mock_review_service
    ):
        """TC-062-ERR-006: ファクトリー初期化失敗で HTTP 503 を返すことを確認."""
        with patch("api.handler.create_ai_service") as mock_factory:
            mock_factory.side_effect = AIProviderError(
                "Failed to initialize AI service"
            )
            event = _make_advice_event()

            response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 503
        body = json.loads(response["body"])
        assert body["error"] == "AI service unavailable"

    def test_advice_returns_500_on_unexpected_exception(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-ERR-007: 予期しない例外が HTTP 500 にマッピングされることを確認."""
        _, mock_service = mock_ai_service
        mock_service.get_learning_advice.side_effect = RuntimeError("unexpected")
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "Internal Server Error"


# =============================================================================
# カテゴリ E: DB/ReviewService エラーテスト（TestAdviceHandlerDBErrors）
# =============================================================================


class TestAdviceHandlerDBErrors:
    """DB/ReviewService エラーテスト（TC-062-DB-001 ~ 002）。"""

    def test_advice_handles_review_service_exception(
        self, lambda_context, mock_ai_service
    ):
        """TC-062-DB-001: ReviewService 例外で HTTP 500 を返すことを確認."""
        with patch("api.handler.review_service") as mock_rs:
            mock_rs.get_review_summary.side_effect = Exception("DB connection error")
            event = _make_advice_event()

            response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "Internal Server Error"

    def test_advice_works_with_empty_review_summary(
        self, lambda_context, mock_ai_service
    ):
        """TC-062-DB-002: 全ゼロの ReviewSummary でも HTTP 200 が返ることを確認."""
        with patch("api.handler.review_service") as mock_rs:
            mock_rs.get_review_summary.return_value = ReviewSummary(
                total_reviews=0,
                average_grade=0.0,
                total_cards=0,
                cards_due_today=0,
                streak_days=0,
            )
            event = _make_advice_event()

            response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 200


# =============================================================================
# カテゴリ F: ロギングテスト（TestAdviceHandlerLogging）
# =============================================================================


class TestAdviceHandlerLogging:
    """ロギング関連テスト（TC-062-LOG-001 ~ 003）。"""

    def test_advice_logs_request_info(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-LOG-001: リクエスト受信時のロギングを確認."""
        event = _make_advice_event(user_id="log-test-user")

        with patch("api.handler.logger") as mock_logger:
            advice_handler(event, lambda_context)

        info_calls_str = str(mock_logger.info.call_args_list)
        assert "log-test-user" in info_calls_str

    def test_advice_logs_success_info(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-LOG-002: 成功時のロギングを確認."""
        event = _make_advice_event()

        with patch("api.handler.logger") as mock_logger:
            advice_handler(event, lambda_context)

        # logger.info が少なくとも 1 回呼ばれていること（リクエスト + 成功ログ）
        assert mock_logger.info.call_count >= 2

    def test_advice_logs_ai_error(
        self, lambda_context, mock_review_service, mock_ai_service
    ):
        """TC-062-LOG-003: AI エラー時のロギングを確認."""
        _, mock_service = mock_ai_service
        mock_service.get_learning_advice.side_effect = AITimeoutError("timeout")
        event = _make_advice_event()

        with patch("api.handler.logger") as mock_logger:
            advice_handler(event, lambda_context)

        assert mock_logger.warning.called or mock_logger.error.called

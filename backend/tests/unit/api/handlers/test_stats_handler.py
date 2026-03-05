"""Unit tests for stats API endpoints."""

import json
from unittest.mock import patch, MagicMock

import pytest

from models.stats import (
    ForecastDay,
    ForecastResponse,
    StatsResponse,
    WeakCard,
    WeakCardsResponse,
)
from services.stats_service import StatsServiceError  # noqa: F401


# =============================================================================
# テスト共通ヘルパー
# =============================================================================


def _make_stats_response(**kwargs) -> StatsResponse:
    """テスト用 StatsResponse インスタンスを作成."""
    defaults = {
        "total_cards": 50,
        "learned_cards": 30,
        "unlearned_cards": 20,
        "cards_due_today": 10,
        "total_reviews": 200,
        "average_grade": 3.5,
        "streak_days": 7,
        "tag_performance": {"english": 0.8, "math": 0.6},
    }
    defaults.update(kwargs)
    return StatsResponse(**defaults)


def _make_weak_cards_response(**kwargs) -> WeakCardsResponse:
    """テスト用 WeakCardsResponse インスタンスを作成."""
    defaults = {
        "weak_cards": [
            WeakCard(
                card_id="card-1",
                front="Question 1",
                back="Answer 1",
                ease_factor=1.3,
                repetitions=3,
                deck_id="deck-1",
            ),
            WeakCard(
                card_id="card-2",
                front="Question 2",
                back="Answer 2",
                ease_factor=1.5,
                repetitions=2,
                deck_id=None,
            ),
        ],
        "total_count": 5,
    }
    defaults.update(kwargs)
    return WeakCardsResponse(**defaults)


def _make_forecast_response(**kwargs) -> ForecastResponse:
    """テスト用 ForecastResponse インスタンスを作成."""
    defaults = {
        "forecast": [
            ForecastDay(date="2026-03-05", due_count=10),
            ForecastDay(date="2026-03-06", due_count=5),
            ForecastDay(date="2026-03-07", due_count=3),
        ],
    }
    defaults.update(kwargs)
    return ForecastResponse(**defaults)


# =============================================================================
# GET /stats テスト
# =============================================================================


class TestGetStatsEndpoint:
    """GET /stats エンドポイントテスト."""

    def test_get_stats_success(self, api_gateway_event, lambda_context):
        """正常に学習統計が返る (200)."""
        event = api_gateway_event(
            method="GET",
            path="/stats",
        )

        mock_response = _make_stats_response()

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_stats.return_value = mock_response
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["total_cards"] == 50
        assert body["learned_cards"] == 30
        assert body["unlearned_cards"] == 20
        assert body["cards_due_today"] == 10
        assert body["total_reviews"] == 200
        assert body["average_grade"] == 3.5
        assert body["streak_days"] == 7
        assert body["tag_performance"] == {"english": 0.8, "math": 0.6}

    def test_get_stats_empty_data(self, api_gateway_event, lambda_context):
        """データがない場合はゼロ値で返る."""
        event = api_gateway_event(
            method="GET",
            path="/stats",
        )

        mock_response = _make_stats_response(
            total_cards=0,
            learned_cards=0,
            unlearned_cards=0,
            cards_due_today=0,
            total_reviews=0,
            average_grade=0.0,
            streak_days=0,
            tag_performance={},
        )

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_stats.return_value = mock_response
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["total_cards"] == 0
        assert body["total_reviews"] == 0

    def test_get_stats_calls_service_with_user_id(self, api_gateway_event, lambda_context):
        """StatsService.get_stats が正しい user_id で呼ばれること."""
        event = api_gateway_event(
            method="GET",
            path="/stats",
            user_id="specific-user-123",
        )

        mock_response = _make_stats_response()

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_stats.return_value = mock_response
            from api.handler import handler

            handler(event, lambda_context)

        mock_service.get_stats.assert_called_once_with("specific-user-123")

    def test_get_stats_service_error(self, api_gateway_event, lambda_context):
        """サービス層でエラーが発生した場合は例外が伝播する."""
        event = api_gateway_event(
            method="GET",
            path="/stats",
        )

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_stats.side_effect = Exception("DynamoDB error")
            from api.handler import handler

            with pytest.raises(Exception, match="DynamoDB error"):
                handler(event, lambda_context)

    def test_get_stats_unauthorized(self, api_gateway_event, lambda_context):
        """認証なしリクエストで 401."""
        event = api_gateway_event(
            method="GET",
            path="/stats",
        )
        # Remove authorizer to simulate unauthorized request
        event["requestContext"]["authorizer"] = {}

        with patch("api.handlers.stats_handler.stats_service"):
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 401


# =============================================================================
# GET /stats/weak-cards テスト
# =============================================================================


class TestGetWeakCardsEndpoint:
    """GET /stats/weak-cards エンドポイントテスト."""

    def test_get_weak_cards_success(self, api_gateway_event, lambda_context):
        """正常に弱点カードが返る (200)."""
        event = api_gateway_event(
            method="GET",
            path="/stats/weak-cards",
        )

        mock_response = _make_weak_cards_response()

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_weak_cards.return_value = mock_response
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "weak_cards" in body
        assert body["total_count"] == 5
        assert len(body["weak_cards"]) == 2
        assert body["weak_cards"][0]["card_id"] == "card-1"
        assert body["weak_cards"][0]["ease_factor"] == 1.3

    def test_get_weak_cards_with_limit(self, api_gateway_event, lambda_context):
        """limit クエリパラメータが正しく処理されること."""
        event = api_gateway_event(
            method="GET",
            path="/stats/weak-cards",
            query_string_parameters={"limit": "5"},
        )

        mock_response = _make_weak_cards_response()

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_weak_cards.return_value = mock_response
            from api.handler import handler

            handler(event, lambda_context)

        mock_service.get_weak_cards.assert_called_once_with("test-user-id", limit=5)

    def test_get_weak_cards_limit_capped_at_50(self, api_gateway_event, lambda_context):
        """limit が 50 を超える場合は 50 に制限されること."""
        event = api_gateway_event(
            method="GET",
            path="/stats/weak-cards",
            query_string_parameters={"limit": "100"},
        )

        mock_response = _make_weak_cards_response()

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_weak_cards.return_value = mock_response
            from api.handler import handler

            handler(event, lambda_context)

        mock_service.get_weak_cards.assert_called_once_with("test-user-id", limit=50)

    def test_get_weak_cards_default_limit(self, api_gateway_event, lambda_context):
        """limit 未指定時はデフォルト 10."""
        event = api_gateway_event(
            method="GET",
            path="/stats/weak-cards",
        )

        mock_response = _make_weak_cards_response()

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_weak_cards.return_value = mock_response
            from api.handler import handler

            handler(event, lambda_context)

        mock_service.get_weak_cards.assert_called_once_with("test-user-id", limit=10)

    def test_get_weak_cards_empty(self, api_gateway_event, lambda_context):
        """弱点カードがない場合は空のリスト."""
        event = api_gateway_event(
            method="GET",
            path="/stats/weak-cards",
        )

        mock_response = WeakCardsResponse(weak_cards=[], total_count=0)

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_weak_cards.return_value = mock_response
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["weak_cards"] == []
        assert body["total_count"] == 0

    def test_get_weak_cards_invalid_limit(self, api_gateway_event, lambda_context):
        """limit が数値でない場合は 400."""
        event = api_gateway_event(
            method="GET",
            path="/stats/weak-cards",
            query_string_parameters={"limit": "abc"},
        )

        with patch("api.handlers.stats_handler.stats_service"):
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "limit" in body["message"]

    def test_get_weak_cards_negative_limit_clamped(self, api_gateway_event, lambda_context):
        """負の limit は 1 にクランプされること."""
        event = api_gateway_event(
            method="GET",
            path="/stats/weak-cards",
            query_string_parameters={"limit": "-5"},
        )

        mock_response = _make_weak_cards_response()

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_weak_cards.return_value = mock_response
            from api.handler import handler

            handler(event, lambda_context)

        mock_service.get_weak_cards.assert_called_once_with("test-user-id", limit=1)

    def test_get_weak_cards_service_error(self, api_gateway_event, lambda_context):
        """サービス層でエラーが発生した場合は例外が伝播する."""
        event = api_gateway_event(
            method="GET",
            path="/stats/weak-cards",
        )

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_weak_cards.side_effect = Exception("DynamoDB error")
            from api.handler import handler

            with pytest.raises(Exception, match="DynamoDB error"):
                handler(event, lambda_context)


# =============================================================================
# GET /stats/forecast テスト
# =============================================================================


class TestGetForecastEndpoint:
    """GET /stats/forecast エンドポイントテスト."""

    def test_get_forecast_success(self, api_gateway_event, lambda_context):
        """正常に予測データが返る (200)."""
        event = api_gateway_event(
            method="GET",
            path="/stats/forecast",
        )

        mock_response = _make_forecast_response()

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_forecast.return_value = mock_response
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "forecast" in body
        assert len(body["forecast"]) == 3
        assert body["forecast"][0]["date"] == "2026-03-05"
        assert body["forecast"][0]["due_count"] == 10

    def test_get_forecast_with_days(self, api_gateway_event, lambda_context):
        """days クエリパラメータが正しく処理されること."""
        event = api_gateway_event(
            method="GET",
            path="/stats/forecast",
            query_string_parameters={"days": "14"},
        )

        mock_response = _make_forecast_response()

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_forecast.return_value = mock_response
            from api.handler import handler

            handler(event, lambda_context)

        mock_service.get_forecast.assert_called_once_with("test-user-id", days=14)

    def test_get_forecast_days_capped_at_30(self, api_gateway_event, lambda_context):
        """days が 30 を超える場合は 30 に制限されること."""
        event = api_gateway_event(
            method="GET",
            path="/stats/forecast",
            query_string_parameters={"days": "60"},
        )

        mock_response = _make_forecast_response()

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_forecast.return_value = mock_response
            from api.handler import handler

            handler(event, lambda_context)

        mock_service.get_forecast.assert_called_once_with("test-user-id", days=30)

    def test_get_forecast_default_days(self, api_gateway_event, lambda_context):
        """days 未指定時はデフォルト 7."""
        event = api_gateway_event(
            method="GET",
            path="/stats/forecast",
        )

        mock_response = _make_forecast_response()

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_forecast.return_value = mock_response
            from api.handler import handler

            handler(event, lambda_context)

        mock_service.get_forecast.assert_called_once_with("test-user-id", days=7)

    def test_get_forecast_empty(self, api_gateway_event, lambda_context):
        """予測データがない場合は空のリスト."""
        event = api_gateway_event(
            method="GET",
            path="/stats/forecast",
        )

        mock_response = ForecastResponse(forecast=[])

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_forecast.return_value = mock_response
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["forecast"] == []

    def test_get_forecast_invalid_days(self, api_gateway_event, lambda_context):
        """days が数値でない場合は 400."""
        event = api_gateway_event(
            method="GET",
            path="/stats/forecast",
            query_string_parameters={"days": "abc"},
        )

        with patch("api.handlers.stats_handler.stats_service"):
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "days" in body["message"]

    def test_get_forecast_negative_days_clamped(self, api_gateway_event, lambda_context):
        """負の days は 1 にクランプされること."""
        event = api_gateway_event(
            method="GET",
            path="/stats/forecast",
            query_string_parameters={"days": "-3"},
        )

        mock_response = _make_forecast_response()

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_forecast.return_value = mock_response
            from api.handler import handler

            handler(event, lambda_context)

        mock_service.get_forecast.assert_called_once_with("test-user-id", days=1)

    def test_get_forecast_service_error(self, api_gateway_event, lambda_context):
        """サービス層でエラーが発生した場合は例外が伝播する."""
        event = api_gateway_event(
            method="GET",
            path="/stats/forecast",
        )

        with patch("api.handlers.stats_handler.stats_service") as mock_service:
            mock_service.get_forecast.side_effect = Exception("DynamoDB error")
            from api.handler import handler

            with pytest.raises(Exception, match="DynamoDB error"):
                handler(event, lambda_context)

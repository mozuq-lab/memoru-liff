"""Unit tests for the `limit` query-parameter lower-bound validation (B-3).

`?limit=0` or a negative value would otherwise be passed straight to DynamoDB's
Limit, which raises a ValidationException -> unhandled 500. The handlers now clamp
the value to [1, 100] via ``max(1, min(int(...), 100))``, so out-of-range lower
values fall back to the safe minimum of 1.
"""

import json
from unittest.mock import patch

from models.review import DueCardsResponse
from services.review_service import ConcurrentReviewError


class TestListCardsLimitValidation:
    """GET /cards limit clamping (B-3)."""

    def test_limit_zero_clamped_to_one(self, api_gateway_event, lambda_context):
        """limit=0 is clamped to 1 instead of reaching DynamoDB with Limit<=0."""
        event = api_gateway_event(
            method="GET",
            path="/cards",
            query_string_parameters={"limit": "0"},
        )

        with patch("api.handlers.cards_handler.card_service") as mock_service:
            mock_service.list_cards.return_value = ([], None)
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        assert mock_service.list_cards.call_args.kwargs["limit"] == 1

    def test_limit_negative_clamped_to_one(self, api_gateway_event, lambda_context):
        """A negative limit is clamped to 1."""
        event = api_gateway_event(
            method="GET",
            path="/cards",
            query_string_parameters={"limit": "-5"},
        )

        with patch("api.handlers.cards_handler.card_service") as mock_service:
            mock_service.list_cards.return_value = ([], None)
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        assert mock_service.list_cards.call_args.kwargs["limit"] == 1

    def test_limit_above_max_clamped_to_100(self, api_gateway_event, lambda_context):
        """The existing upper bound (100) still holds."""
        event = api_gateway_event(
            method="GET",
            path="/cards",
            query_string_parameters={"limit": "500"},
        )

        with patch("api.handlers.cards_handler.card_service") as mock_service:
            mock_service.list_cards.return_value = ([], None)
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        assert mock_service.list_cards.call_args.kwargs["limit"] == 100

    def test_limit_non_integer_returns_400(self, api_gateway_event, lambda_context):
        """A non-integer limit still returns 400."""
        event = api_gateway_event(
            method="GET",
            path="/cards",
            query_string_parameters={"limit": "abc"},
        )

        with patch("api.handlers.cards_handler.card_service") as mock_service:
            mock_service.list_cards.return_value = ([], None)
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        assert "limit" in json.loads(response["body"])["error"]


class TestUndoReviewConflictMapping:
    """POST /reviews/<id>/undo maps ConcurrentReviewError -> 409 (B-2)."""

    def test_undo_concurrent_review_returns_409(self, api_gateway_event, lambda_context):
        """Optimistic-lock failure on undo surfaces as HTTP 409."""
        event = api_gateway_event(
            method="POST",
            path="/reviews/test-card-id/undo",
            path_parameters={"card_id": "test-card-id"},
        )

        with patch("api.handlers.review_handler.review_service") as mock_service:
            mock_service.undo_review.side_effect = ConcurrentReviewError("conflict")
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 409
        body = json.loads(response["body"])
        assert body["code"] == "review_conflict"


class TestDueCardsLimitValidation:
    """GET /cards/due limit clamping (B-3)."""

    def _empty_due_response(self):
        return DueCardsResponse(due_cards=[], total_due_count=0, next_due_date=None)

    def test_limit_zero_clamped_to_one(self, api_gateway_event, lambda_context):
        """limit=0 is clamped to 1 instead of reaching DynamoDB with Limit<=0."""
        event = api_gateway_event(
            method="GET",
            path="/cards/due",
            query_string_parameters={"limit": "0"},
        )

        with patch("api.handlers.review_handler.review_service") as mock_service:
            mock_service.get_due_cards.return_value = self._empty_due_response()
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        assert mock_service.get_due_cards.call_args.kwargs["limit"] == 1

    def test_limit_negative_clamped_to_one(self, api_gateway_event, lambda_context):
        """A negative limit is clamped to 1."""
        event = api_gateway_event(
            method="GET",
            path="/cards/due",
            query_string_parameters={"limit": "-10"},
        )

        with patch("api.handlers.review_handler.review_service") as mock_service:
            mock_service.get_due_cards.return_value = self._empty_due_response()
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        assert mock_service.get_due_cards.call_args.kwargs["limit"] == 1

    def test_limit_non_integer_returns_400(self, api_gateway_event, lambda_context):
        """A non-integer limit still returns 400."""
        event = api_gateway_event(
            method="GET",
            path="/cards/due",
            query_string_parameters={"limit": "xyz"},
        )

        with patch("api.handlers.review_handler.review_service") as mock_service:
            mock_service.get_due_cards.return_value = self._empty_due_response()
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        assert "limit" in json.loads(response["body"])["error"]

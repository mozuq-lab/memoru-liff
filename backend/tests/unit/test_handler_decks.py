"""Unit tests for deck CRUD endpoints in handler.py."""

import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

import pytest

from models.deck import Deck, DeckResponse, DeckListResponse
from services.deck_service import (
    DeckNotFoundError,
    DeckLimitExceededError,
    DeckServiceError,
)


# =============================================================================
# テスト共通ヘルパー
# =============================================================================


def _make_deck(**kwargs) -> Deck:
    """テスト用 Deck インスタンスを作成."""
    defaults = {
        "deck_id": "deck-123",
        "user_id": "test-user-id",
        "name": "テストデッキ",
        "description": "テスト説明",
        "color": "#FF5733",
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }
    defaults.update(kwargs)
    return Deck(**defaults)


# =============================================================================
# POST /decks テスト
# =============================================================================


class TestCreateDeckEndpoint:
    """POST /decks エンドポイントテスト."""

    def test_create_deck_success(self, api_gateway_event, lambda_context):
        """正常にデッキが作成される (201)."""
        event = api_gateway_event(
            method="POST",
            path="/decks",
            body={"name": "新しいデッキ", "description": "説明", "color": "#FF5733"},
        )

        mock_deck = _make_deck(name="新しいデッキ", description="説明", color="#FF5733")

        with patch("api.handler.deck_service") as mock_service:
            mock_service.create_deck.return_value = mock_deck
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["name"] == "新しいデッキ"
        assert body["deck_id"] == "deck-123"

    def test_create_deck_validation_error(self, api_gateway_event, lambda_context):
        """名前なしで 400 エラー."""
        event = api_gateway_event(
            method="POST",
            path="/decks",
            body={"description": "名前なし"},
        )

        with patch("api.handler.deck_service"):
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 400

    def test_create_deck_empty_name(self, api_gateway_event, lambda_context):
        """空の名前で 400 エラー."""
        event = api_gateway_event(
            method="POST",
            path="/decks",
            body={"name": ""},
        )

        with patch("api.handler.deck_service"):
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 400

    def test_create_deck_limit_exceeded(self, api_gateway_event, lambda_context):
        """デッキ数上限超過で 400 エラー."""
        event = api_gateway_event(
            method="POST",
            path="/decks",
            body={"name": "超過デッキ"},
        )

        with patch("api.handler.deck_service") as mock_service:
            mock_service.create_deck.side_effect = DeckLimitExceededError("Limit exceeded")
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "limit" in body["error"].lower() or "Deck limit exceeded" in body["error"]

    def test_create_deck_invalid_color(self, api_gateway_event, lambda_context):
        """不正なカラーコードで 400 エラー."""
        event = api_gateway_event(
            method="POST",
            path="/decks",
            body={"name": "テスト", "color": "invalid"},
        )

        with patch("api.handler.deck_service"):
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 400


# =============================================================================
# GET /decks テスト
# =============================================================================


class TestListDecksEndpoint:
    """GET /decks エンドポイントテスト."""

    def test_list_decks_success(self, api_gateway_event, lambda_context):
        """デッキ一覧が正常に返る."""
        event = api_gateway_event(
            method="GET",
            path="/decks",
        )

        mock_deck = _make_deck()

        with patch("api.handler.deck_service") as mock_service, \
             patch("api.handler.card_service") as mock_card_service:
            mock_service.list_decks.return_value = [mock_deck]
            mock_service.get_deck_card_counts.return_value = {"deck-123": 5}
            mock_service.get_deck_due_counts.return_value = {"deck-123": 2}
            mock_card_service.list_cards.return_value = ([], None)
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "decks" in body
        assert "total" in body

    def test_list_decks_empty(self, api_gateway_event, lambda_context):
        """デッキがない場合は空の一覧."""
        event = api_gateway_event(
            method="GET",
            path="/decks",
        )

        with patch("api.handler.deck_service") as mock_service, \
             patch("api.handler.card_service") as mock_card_service:
            mock_service.list_decks.return_value = []
            mock_service.get_deck_card_counts.return_value = {}
            mock_service.get_deck_due_counts.return_value = {}
            mock_card_service.list_cards.return_value = ([], None)
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["decks"] == []


# =============================================================================
# PUT /decks/<deck_id> テスト
# =============================================================================


class TestUpdateDeckEndpoint:
    """PUT /decks/<deck_id> エンドポイントテスト."""

    def test_update_deck_success(self, api_gateway_event, lambda_context):
        """デッキが正常に更新される."""
        event = api_gateway_event(
            method="PUT",
            path="/decks/deck-123",
            body={"name": "更新後の名前"},
            path_parameters={"deck_id": "deck-123"},
        )

        mock_deck = _make_deck(name="更新後の名前")

        with patch("api.handler.deck_service") as mock_service:
            mock_service.update_deck.return_value = mock_deck
            mock_service.get_deck_card_counts.return_value = {"deck-123": 5}
            mock_service.get_deck_due_counts.return_value = {"deck-123": 2}
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["name"] == "更新後の名前"

    def test_update_deck_not_found(self, api_gateway_event, lambda_context):
        """存在しないデッキの更新で 404."""
        event = api_gateway_event(
            method="PUT",
            path="/decks/nonexistent",
            body={"name": "更新"},
            path_parameters={"deck_id": "nonexistent"},
        )

        with patch("api.handler.deck_service") as mock_service:
            mock_service.update_deck.side_effect = DeckNotFoundError("Not found")
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 404

    def test_update_deck_validation_error(self, api_gateway_event, lambda_context):
        """不正な更新データで 400."""
        event = api_gateway_event(
            method="PUT",
            path="/decks/deck-123",
            body={"color": "invalid-color"},
            path_parameters={"deck_id": "deck-123"},
        )

        with patch("api.handler.deck_service"):
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 400


# =============================================================================
# DELETE /decks/<deck_id> テスト
# =============================================================================


class TestDeleteDeckEndpoint:
    """DELETE /decks/<deck_id> エンドポイントテスト."""

    def test_delete_deck_success(self, api_gateway_event, lambda_context):
        """デッキが正常に削除される (204)."""
        event = api_gateway_event(
            method="DELETE",
            path="/decks/deck-123",
            path_parameters={"deck_id": "deck-123"},
        )

        with patch("api.handler.deck_service") as mock_service:
            mock_service.delete_deck.return_value = None
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 204

    def test_delete_deck_not_found(self, api_gateway_event, lambda_context):
        """存在しないデッキの削除で 404."""
        event = api_gateway_event(
            method="DELETE",
            path="/decks/nonexistent",
            path_parameters={"deck_id": "nonexistent"},
        )

        with patch("api.handler.deck_service") as mock_service:
            mock_service.delete_deck.side_effect = DeckNotFoundError("Not found")
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 404


# =============================================================================
# GET /cards/due?deck_id=xxx テスト
# =============================================================================


class TestGetDueCardsWithDeckId:
    """GET /cards/due with deck_id パラメータテスト."""

    def test_get_due_cards_with_deck_id(self, api_gateway_event, lambda_context):
        """deck_id パラメータ付きで due cards が取得される."""
        event = api_gateway_event(
            method="GET",
            path="/cards/due",
            query_string_parameters={"deck_id": "deck-123"},
        )

        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "due_cards": [],
            "total_due_count": 0,
            "next_due_date": None,
        }

        with patch("api.handler.review_service") as mock_service:
            mock_service.get_due_cards.return_value = mock_response
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        # deck_id が review_service.get_due_cards に渡されていることを確認
        mock_service.get_due_cards.assert_called_once()
        call_kwargs = mock_service.get_due_cards.call_args
        assert call_kwargs.kwargs.get("deck_id") == "deck-123" or \
               (len(call_kwargs.args) > 0 and "deck-123" in str(call_kwargs))

    def test_get_due_cards_without_deck_id(self, api_gateway_event, lambda_context):
        """deck_id パラメータなしでも正常動作."""
        event = api_gateway_event(
            method="GET",
            path="/cards/due",
        )

        mock_response = MagicMock()
        mock_response.model_dump.return_value = {
            "due_cards": [],
            "total_due_count": 0,
            "next_due_date": None,
        }

        with patch("api.handler.review_service") as mock_service:
            mock_service.get_due_cards.return_value = mock_response
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200

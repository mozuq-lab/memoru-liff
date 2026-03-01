"""Unit tests for deck models (Pydantic validation)."""

import pytest
from datetime import datetime, timezone

from models.deck import (
    CreateDeckRequest,
    UpdateDeckRequest,
    Deck,
    DeckResponse,
    DeckListResponse,
)
from pydantic import ValidationError


class TestCreateDeckRequest:
    """CreateDeckRequest Pydantic バリデーションテスト."""

    def test_valid_request_name_only(self):
        """名前のみで作成リクエストが有効."""
        req = CreateDeckRequest(name="テストデッキ")
        assert req.name == "テストデッキ"
        assert req.description is None
        assert req.color is None

    def test_valid_request_all_fields(self):
        """全フィールド指定で作成リクエストが有効."""
        req = CreateDeckRequest(
            name="テストデッキ",
            description="テスト用の説明",
            color="#FF5733",
        )
        assert req.name == "テストデッキ"
        assert req.description == "テスト用の説明"
        assert req.color == "#FF5733"

    def test_name_empty_raises_error(self):
        """名前が空の場合バリデーションエラー."""
        with pytest.raises(ValidationError):
            CreateDeckRequest(name="")

    def test_name_too_long_raises_error(self):
        """名前が100文字超の場合バリデーションエラー."""
        with pytest.raises(ValidationError):
            CreateDeckRequest(name="a" * 101)

    def test_name_max_length(self):
        """名前が100文字ちょうどは有効."""
        req = CreateDeckRequest(name="a" * 100)
        assert len(req.name) == 100

    def test_description_too_long_raises_error(self):
        """説明が500文字超の場合バリデーションエラー."""
        with pytest.raises(ValidationError):
            CreateDeckRequest(name="test", description="a" * 501)

    def test_description_max_length(self):
        """説明が500文字ちょうどは有効."""
        req = CreateDeckRequest(name="test", description="a" * 500)
        assert len(req.description) == 500

    def test_valid_color_lowercase(self):
        """小文字16進カラーコードが大文字に正規化される."""
        req = CreateDeckRequest(name="test", color="#ff5733")
        assert req.color == "#FF5733"

    def test_invalid_color_format(self):
        """不正なカラーコード形式でバリデーションエラー."""
        with pytest.raises(ValidationError):
            CreateDeckRequest(name="test", color="red")

    def test_invalid_color_without_hash(self):
        """#なしのカラーコードでバリデーションエラー."""
        with pytest.raises(ValidationError):
            CreateDeckRequest(name="test", color="FF5733")

    def test_invalid_color_short(self):
        """短いカラーコードでバリデーションエラー."""
        with pytest.raises(ValidationError):
            CreateDeckRequest(name="test", color="#FFF")

    def test_color_none_is_valid(self):
        """colorがNoneは有効."""
        req = CreateDeckRequest(name="test", color=None)
        assert req.color is None


class TestUpdateDeckRequest:
    """UpdateDeckRequest Pydantic バリデーションテスト."""

    def test_empty_update_is_valid(self):
        """空の更新リクエストは有効."""
        req = UpdateDeckRequest()
        assert req.name is None
        assert req.description is None
        assert req.color is None

    def test_name_only_update(self):
        """名前のみの更新リクエストが有効."""
        req = UpdateDeckRequest(name="新しい名前")
        assert req.name == "新しい名前"

    def test_name_too_long_raises_error(self):
        """更新時にも名前100文字超でバリデーションエラー."""
        with pytest.raises(ValidationError):
            UpdateDeckRequest(name="a" * 101)

    def test_invalid_color_raises_error(self):
        """更新時にも不正カラーコードでバリデーションエラー."""
        with pytest.raises(ValidationError):
            UpdateDeckRequest(color="invalid")

    def test_valid_color_update(self):
        """カラーコードの更新が有効."""
        req = UpdateDeckRequest(color="#abcdef")
        assert req.color == "#ABCDEF"


class TestDeck:
    """Deck ドメインモデルテスト."""

    def test_auto_generated_deck_id(self):
        """deck_id が UUID v4 で自動生成される."""
        deck = Deck(user_id="user-1", name="テスト")
        assert deck.deck_id is not None
        assert len(deck.deck_id) == 36  # UUID format

    def test_auto_generated_created_at(self):
        """created_at が自動生成される."""
        deck = Deck(user_id="user-1", name="テスト")
        assert deck.created_at is not None
        assert deck.created_at.tzinfo == timezone.utc

    def test_to_dynamodb_item_minimal(self):
        """最小フィールドで to_dynamodb_item が正しく動作する."""
        deck = Deck(
            deck_id="deck-123",
            user_id="user-1",
            name="テスト",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        item = deck.to_dynamodb_item()
        assert item["user_id"] == "user-1"
        assert item["deck_id"] == "deck-123"
        assert item["name"] == "テスト"
        assert item["created_at"] == "2024-01-01T00:00:00+00:00"
        assert "description" not in item
        assert "color" not in item
        assert "updated_at" not in item

    def test_to_dynamodb_item_full(self):
        """全フィールドで to_dynamodb_item が正しく動作する."""
        deck = Deck(
            deck_id="deck-123",
            user_id="user-1",
            name="テスト",
            description="説明",
            color="#FF0000",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            updated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )
        item = deck.to_dynamodb_item()
        assert item["description"] == "説明"
        assert item["color"] == "#FF0000"
        assert item["updated_at"] == "2024-01-02T00:00:00+00:00"

    def test_from_dynamodb_item_minimal(self):
        """最小DynamoDBアイテムから Deck を復元できる."""
        item = {
            "user_id": "user-1",
            "deck_id": "deck-123",
            "name": "テスト",
            "created_at": "2024-01-01T00:00:00+00:00",
        }
        deck = Deck.from_dynamodb_item(item)
        assert deck.user_id == "user-1"
        assert deck.deck_id == "deck-123"
        assert deck.name == "テスト"
        assert deck.description is None
        assert deck.color is None
        assert deck.updated_at is None

    def test_from_dynamodb_item_full(self):
        """全フィールドDynamoDBアイテムから Deck を復元できる."""
        item = {
            "user_id": "user-1",
            "deck_id": "deck-123",
            "name": "テスト",
            "description": "説明",
            "color": "#FF0000",
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-02T00:00:00+00:00",
        }
        deck = Deck.from_dynamodb_item(item)
        assert deck.description == "説明"
        assert deck.color == "#FF0000"
        assert deck.updated_at == datetime(2024, 1, 2, tzinfo=timezone.utc)

    def test_to_response(self):
        """to_response がカウントを含めた DeckResponse を返す."""
        deck = Deck(
            deck_id="deck-123",
            user_id="user-1",
            name="テスト",
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        response = deck.to_response(card_count=10, due_count=3)
        assert isinstance(response, DeckResponse)
        assert response.deck_id == "deck-123"
        assert response.card_count == 10
        assert response.due_count == 3

    def test_to_response_default_counts(self):
        """to_response でカウントのデフォルト値は 0."""
        deck = Deck(user_id="user-1", name="テスト")
        response = deck.to_response()
        assert response.card_count == 0
        assert response.due_count == 0

    def test_roundtrip(self):
        """DynamoDB item の往復変換で情報が保持される."""
        original = Deck(
            user_id="user-1",
            name="テスト",
            description="説明文",
            color="#ABCDEF",
        )
        item = original.to_dynamodb_item()
        restored = Deck.from_dynamodb_item(item)
        assert restored.deck_id == original.deck_id
        assert restored.user_id == original.user_id
        assert restored.name == original.name
        assert restored.description == original.description
        assert restored.color == original.color


class TestDeckListResponse:
    """DeckListResponse テスト."""

    def test_deck_list_response(self):
        """DeckListResponse が正しく構築される."""
        deck_resp = DeckResponse(
            deck_id="deck-1",
            user_id="user-1",
            name="テスト",
            card_count=5,
            due_count=2,
            created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        list_resp = DeckListResponse(decks=[deck_resp], total=1)
        assert len(list_resp.decks) == 1
        assert list_resp.total == 1
        assert list_resp.decks[0].name == "テスト"

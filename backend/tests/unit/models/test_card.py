"""Unit tests for Reference model and Card model references extension.

TASK-0157: Reference Pydantic モデルのバリデーション、Card モデルの references フィールド、
DynamoDB シリアライズ/デシリアライズ、後方互換性をテストする。
"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from models.card import (
    Card,
    CardResponse,
    CreateCardRequest,
    Reference,
    UpdateCardRequest,
)


class TestReferenceModel:
    """Tests for Reference Pydantic model validation."""

    # =========================================================================
    # 正常系: 各 type での生成
    # =========================================================================

    def test_reference_type_url(self):
        """type='url' で正しく Reference が生成される。"""
        ref = Reference(type="url", value="https://example.com")
        assert ref.type == "url"
        assert ref.value == "https://example.com"

    def test_reference_type_book(self):
        """type='book' で正しく Reference が生成される。"""
        ref = Reference(type="book", value="入門Python p.42")
        assert ref.type == "book"
        assert ref.value == "入門Python p.42"

    def test_reference_type_note(self):
        """type='note' で正しく Reference が生成される。"""
        ref = Reference(type="note", value="授業ノート 第3回")
        assert ref.type == "note"
        assert ref.value == "授業ノート 第3回"

    # =========================================================================
    # 正常系: value 境界値
    # =========================================================================

    def test_reference_value_min_length(self):
        """value が 1 文字（最小値）で正しく生成される。"""
        ref = Reference(type="note", value="a")
        assert ref.value == "a"

    def test_reference_value_max_length(self):
        """value が 500 文字（最大値）で正しく生成される。"""
        value = "a" * 500
        ref = Reference(type="note", value=value)
        assert len(ref.value) == 500

    # =========================================================================
    # 異常系: type バリデーション
    # =========================================================================

    def test_reference_invalid_type_raises_error(self):
        """不正な type で ValidationError が発生する。"""
        with pytest.raises(ValidationError) as exc_info:
            Reference(type="invalid", value="test")
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("type",) for error in errors)

    # =========================================================================
    # 異常系: value バリデーション
    # =========================================================================

    def test_reference_empty_value_raises_error(self):
        """value が空文字列で ValidationError が発生する。"""
        with pytest.raises(ValidationError) as exc_info:
            Reference(type="url", value="")
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("value",) for error in errors)

    def test_reference_value_too_long_raises_error(self):
        """value が 501 文字で ValidationError が発生する。"""
        with pytest.raises(ValidationError) as exc_info:
            Reference(type="url", value="a" * 501)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("value",) for error in errors)


class TestCardWithReferences:
    """Tests for Card model with references field."""

    def _make_card(self, **kwargs):
        """テスト用 Card を生成するヘルパー。"""
        defaults = {
            "card_id": "test-card-id",
            "user_id": "test-user-id",
            "front": "Question",
            "back": "Answer",
            "created_at": datetime(2026, 1, 1, 0, 0, 0),
        }
        defaults.update(kwargs)
        return Card(**defaults)

    # =========================================================================
    # Card 生成
    # =========================================================================

    def test_card_default_references_empty_list(self):
        """Card の references デフォルトは空リスト。"""
        card = self._make_card()
        assert card.references == []

    def test_card_with_references(self):
        """Card に references を設定して生成できる。"""
        refs = [
            Reference(type="url", value="https://example.com"),
            Reference(type="book", value="入門Python"),
        ]
        card = self._make_card(references=refs)
        assert len(card.references) == 2
        assert card.references[0].type == "url"
        assert card.references[1].type == "book"

    # =========================================================================
    # to_dynamodb_item
    # =========================================================================

    def test_to_dynamodb_item_with_references(self):
        """references が to_dynamodb_item で正しくシリアライズされる。"""
        refs = [
            Reference(type="url", value="https://example.com"),
            Reference(type="note", value="メモ"),
        ]
        card = self._make_card(references=refs)
        item = card.to_dynamodb_item()

        assert "references" in item
        assert len(item["references"]) == 2
        assert item["references"][0] == {"type": "url", "value": "https://example.com"}
        assert item["references"][1] == {"type": "note", "value": "メモ"}

    def test_to_dynamodb_item_empty_references_not_included(self):
        """references が空の場合、DynamoDB アイテムに含まれない。"""
        card = self._make_card(references=[])
        item = card.to_dynamodb_item()
        assert "references" not in item

    # =========================================================================
    # from_dynamodb_item
    # =========================================================================

    def test_from_dynamodb_item_with_references(self):
        """references を含む DynamoDB アイテムから Card を復元できる。"""
        item = {
            "card_id": "test-card-id",
            "user_id": "test-user-id",
            "front": "Question",
            "back": "Answer",
            "created_at": "2026-01-01T00:00:00",
            "references": [
                {"type": "url", "value": "https://example.com"},
                {"type": "book", "value": "入門Python p.42"},
            ],
        }
        card = Card.from_dynamodb_item(item)

        assert len(card.references) == 2
        assert card.references[0].type == "url"
        assert card.references[0].value == "https://example.com"
        assert card.references[1].type == "book"
        assert card.references[1].value == "入門Python p.42"

    def test_from_dynamodb_item_without_references_backward_compat(self):
        """references フィールドがない既存データから復元すると空リストになる（後方互換性）。"""
        item = {
            "card_id": "test-card-id",
            "user_id": "test-user-id",
            "front": "Question",
            "back": "Answer",
            "created_at": "2026-01-01T00:00:00",
        }
        card = Card.from_dynamodb_item(item)
        assert card.references == []

    # =========================================================================
    # to_response
    # =========================================================================

    def test_to_response_includes_references(self):
        """to_response で references が CardResponse に含まれる。"""
        refs = [Reference(type="url", value="https://example.com")]
        card = self._make_card(references=refs)
        response = card.to_response()

        assert isinstance(response, CardResponse)
        assert len(response.references) == 1
        assert response.references[0].type == "url"
        assert response.references[0].value == "https://example.com"

    def test_to_response_empty_references(self):
        """to_response で references が空の場合は空リスト。"""
        card = self._make_card()
        response = card.to_response()
        assert response.references == []


class TestCreateCardRequestReferences:
    """Tests for CreateCardRequest references field."""

    def test_create_request_default_references_empty(self):
        """CreateCardRequest で references 省略時は空リスト。"""
        request = CreateCardRequest(front="Q", back="A")
        assert request.references == []

    def test_create_request_with_references(self):
        """CreateCardRequest に references を設定できる。"""
        refs = [
            Reference(type="url", value="https://example.com"),
        ]
        request = CreateCardRequest(front="Q", back="A", references=refs)
        assert len(request.references) == 1

    def test_create_request_max_5_references_valid(self):
        """CreateCardRequest で 5 件の references は許可される。"""
        refs = [Reference(type="note", value=f"ref{i}") for i in range(5)]
        request = CreateCardRequest(front="Q", back="A", references=refs)
        assert len(request.references) == 5

    def test_create_request_6_references_raises_error(self):
        """CreateCardRequest で 6 件の references は ValidationError。"""
        refs = [Reference(type="note", value=f"ref{i}") for i in range(6)]
        with pytest.raises(ValidationError) as exc_info:
            CreateCardRequest(front="Q", back="A", references=refs)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("references",) for error in errors)


class TestUpdateCardRequestReferences:
    """Tests for UpdateCardRequest references field."""

    def test_update_request_default_references_none(self):
        """UpdateCardRequest で references 省略時は None。"""
        request = UpdateCardRequest(front="Q")
        assert request.references is None

    def test_update_request_with_references(self):
        """UpdateCardRequest に references を設定できる。"""
        refs = [Reference(type="book", value="入門Python")]
        request = UpdateCardRequest(references=refs)
        assert len(request.references) == 1

    def test_update_request_explicit_none_references(self):
        """UpdateCardRequest で references=None を明示的に指定できる。"""
        request = UpdateCardRequest(references=None)
        assert request.references is None

    def test_update_request_empty_list_references(self):
        """UpdateCardRequest で references=[] を指定できる（参考情報クリア）。"""
        request = UpdateCardRequest(references=[])
        assert request.references == []

    def test_update_request_max_5_references_valid(self):
        """UpdateCardRequest で 5 件の references は許可される。"""
        refs = [Reference(type="note", value=f"ref{i}") for i in range(5)]
        request = UpdateCardRequest(references=refs)
        assert len(request.references) == 5

    def test_update_request_6_references_raises_error(self):
        """UpdateCardRequest で 6 件の references は ValidationError。"""
        refs = [Reference(type="note", value=f"ref{i}") for i in range(6)]
        with pytest.raises(ValidationError) as exc_info:
            UpdateCardRequest(references=refs)
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("references",) for error in errors)

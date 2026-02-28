"""Unit tests for DeckService (moto DynamoDB mock)."""

import pytest
from moto import mock_aws
import boto3
from datetime import datetime, timezone

from services.deck_service import (
    DeckService,
    DeckNotFoundError,
    DeckLimitExceededError,
    DeckServiceError,
)


@pytest.fixture
def dynamodb_tables():
    """Create mock DynamoDB tables (decks, cards)."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

        # Create decks table
        decks_table = dynamodb.create_table(
            TableName="memoru-decks-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "deck_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "deck_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        decks_table.wait_until_exists()

        # Create cards table
        cards_table = dynamodb.create_table(
            TableName="memoru-cards-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "card_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "card_id", "AttributeType": "S"},
                {"AttributeName": "next_review_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user_id-due-index",
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "next_review_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        cards_table.wait_until_exists()

        yield dynamodb


@pytest.fixture
def deck_service(dynamodb_tables):
    """Create DeckService with mock DynamoDB."""
    return DeckService(
        table_name="memoru-decks-test",
        cards_table_name="memoru-cards-test",
        dynamodb_resource=dynamodb_tables,
    )


class TestCreateDeck:
    """DeckService.create_deck テスト."""

    def test_create_deck_success(self, deck_service):
        """デッキが正常に作成される."""
        deck = deck_service.create_deck(
            user_id="user-1",
            name="テストデッキ",
            description="テスト用の説明",
            color="#FF5733",
        )
        assert deck.user_id == "user-1"
        assert deck.name == "テストデッキ"
        assert deck.description == "テスト用の説明"
        assert deck.color == "#FF5733"
        assert deck.deck_id is not None
        assert deck.created_at is not None

    def test_create_deck_name_only(self, deck_service):
        """名前のみでデッキが作成される."""
        deck = deck_service.create_deck(user_id="user-1", name="シンプルデッキ")
        assert deck.name == "シンプルデッキ"
        assert deck.description is None
        assert deck.color is None

    def test_create_deck_persisted(self, deck_service):
        """作成したデッキがDBに保存されている."""
        deck = deck_service.create_deck(user_id="user-1", name="保存テスト")
        retrieved = deck_service.get_deck("user-1", deck.deck_id)
        assert retrieved.name == "保存テスト"

    def test_create_deck_limit_exceeded(self, deck_service):
        """デッキ数上限（50）を超えると DeckLimitExceededError."""
        # 50個のデッキを作成
        for i in range(50):
            deck_service.create_deck(user_id="user-1", name=f"デッキ{i}")

        # 51個目でエラー
        with pytest.raises(DeckLimitExceededError):
            deck_service.create_deck(user_id="user-1", name="超過デッキ")

    def test_create_deck_different_users(self, deck_service):
        """異なるユーザーのデッキは独立."""
        deck1 = deck_service.create_deck(user_id="user-1", name="ユーザー1のデッキ")
        deck2 = deck_service.create_deck(user_id="user-2", name="ユーザー2のデッキ")

        decks_user1 = deck_service.list_decks("user-1")
        decks_user2 = deck_service.list_decks("user-2")
        assert len(decks_user1) == 1
        assert len(decks_user2) == 1


class TestGetDeck:
    """DeckService.get_deck テスト."""

    def test_get_deck_success(self, deck_service):
        """存在するデッキを取得できる."""
        created = deck_service.create_deck(user_id="user-1", name="取得テスト")
        deck = deck_service.get_deck("user-1", created.deck_id)
        assert deck.name == "取得テスト"
        assert deck.deck_id == created.deck_id

    def test_get_deck_not_found(self, deck_service):
        """存在しないデッキで DeckNotFoundError."""
        with pytest.raises(DeckNotFoundError):
            deck_service.get_deck("user-1", "nonexistent-id")

    def test_get_deck_wrong_user(self, deck_service):
        """別ユーザーのデッキは取得できない."""
        created = deck_service.create_deck(user_id="user-1", name="ユーザー1のデッキ")
        with pytest.raises(DeckNotFoundError):
            deck_service.get_deck("user-2", created.deck_id)


class TestListDecks:
    """DeckService.list_decks テスト."""

    def test_list_decks_empty(self, deck_service):
        """デッキがない場合は空リスト."""
        decks = deck_service.list_decks("user-1")
        assert decks == []

    def test_list_decks_multiple(self, deck_service):
        """複数デッキが一覧で取得される."""
        deck_service.create_deck(user_id="user-1", name="デッキA")
        deck_service.create_deck(user_id="user-1", name="デッキB")
        deck_service.create_deck(user_id="user-1", name="デッキC")

        decks = deck_service.list_decks("user-1")
        assert len(decks) == 3
        names = {d.name for d in decks}
        assert names == {"デッキA", "デッキB", "デッキC"}

    def test_list_decks_user_isolation(self, deck_service):
        """異なるユーザーのデッキは含まれない."""
        deck_service.create_deck(user_id="user-1", name="ユーザー1")
        deck_service.create_deck(user_id="user-2", name="ユーザー2")

        decks = deck_service.list_decks("user-1")
        assert len(decks) == 1
        assert decks[0].name == "ユーザー1"


class TestUpdateDeck:
    """DeckService.update_deck テスト."""

    def test_update_name(self, deck_service):
        """デッキ名を更新できる."""
        created = deck_service.create_deck(user_id="user-1", name="旧名前")
        updated = deck_service.update_deck("user-1", created.deck_id, name="新名前")
        assert updated.name == "新名前"
        assert updated.updated_at is not None

    def test_update_description(self, deck_service):
        """デッキ説明を更新できる."""
        created = deck_service.create_deck(user_id="user-1", name="テスト")
        updated = deck_service.update_deck(
            "user-1", created.deck_id, description="新しい説明"
        )
        assert updated.description == "新しい説明"

    def test_update_color(self, deck_service):
        """デッキカラーを更新できる."""
        created = deck_service.create_deck(user_id="user-1", name="テスト")
        updated = deck_service.update_deck("user-1", created.deck_id, color="#00FF00")
        assert updated.color == "#00FF00"

    def test_update_multiple_fields(self, deck_service):
        """複数フィールドを同時に更新できる."""
        created = deck_service.create_deck(user_id="user-1", name="旧名前")
        updated = deck_service.update_deck(
            "user-1",
            created.deck_id,
            name="新名前",
            description="新説明",
            color="#0000FF",
        )
        assert updated.name == "新名前"
        assert updated.description == "新説明"
        assert updated.color == "#0000FF"

    def test_update_no_changes(self, deck_service):
        """変更なしの更新はそのまま返す."""
        created = deck_service.create_deck(user_id="user-1", name="テスト")
        result = deck_service.update_deck("user-1", created.deck_id)
        assert result.name == "テスト"

    def test_update_not_found(self, deck_service):
        """存在しないデッキの更新で DeckNotFoundError."""
        with pytest.raises(DeckNotFoundError):
            deck_service.update_deck("user-1", "nonexistent", name="新名前")

    def test_update_persisted(self, deck_service):
        """更新がDBに反映されている."""
        created = deck_service.create_deck(user_id="user-1", name="旧名前")
        deck_service.update_deck("user-1", created.deck_id, name="新名前")
        retrieved = deck_service.get_deck("user-1", created.deck_id)
        assert retrieved.name == "新名前"


class TestDeleteDeck:
    """DeckService.delete_deck テスト."""

    def test_delete_deck_success(self, deck_service):
        """デッキが正常に削除される."""
        created = deck_service.create_deck(user_id="user-1", name="削除テスト")
        deck_service.delete_deck("user-1", created.deck_id)

        with pytest.raises(DeckNotFoundError):
            deck_service.get_deck("user-1", created.deck_id)

    def test_delete_deck_not_found(self, deck_service):
        """存在しないデッキの削除で DeckNotFoundError."""
        with pytest.raises(DeckNotFoundError):
            deck_service.delete_deck("user-1", "nonexistent")

    def test_delete_deck_resets_card_deck_id(self, deck_service, dynamodb_tables):
        """デッキ削除時にカードの deck_id がリセットされる."""
        # デッキを作成
        deck = deck_service.create_deck(user_id="user-1", name="削除テスト")

        # カードを作成してデッキに紐付け
        cards_table = dynamodb_tables.Table("memoru-cards-test")
        cards_table.put_item(
            Item={
                "user_id": "user-1",
                "card_id": "card-1",
                "front": "Q1",
                "back": "A1",
                "deck_id": deck.deck_id,
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        cards_table.put_item(
            Item={
                "user_id": "user-1",
                "card_id": "card-2",
                "front": "Q2",
                "back": "A2",
                "deck_id": deck.deck_id,
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        # デッキを削除
        deck_service.delete_deck("user-1", deck.deck_id)

        # カードの deck_id がリセットされているか確認
        card1 = cards_table.get_item(Key={"user_id": "user-1", "card_id": "card-1"})
        card2 = cards_table.get_item(Key={"user_id": "user-1", "card_id": "card-2"})
        assert "deck_id" not in card1["Item"]
        assert "deck_id" not in card2["Item"]


class TestGetDeckCardCounts:
    """DeckService.get_deck_card_counts テスト."""

    def test_card_counts_empty(self, deck_service):
        """カードがない場合は 0."""
        counts = deck_service.get_deck_card_counts("user-1", ["deck-1", "deck-2"])
        assert counts == {"deck-1": 0, "deck-2": 0}

    def test_card_counts_with_cards(self, deck_service, dynamodb_tables):
        """カードが存在する場合は正しいカウント."""
        cards_table = dynamodb_tables.Table("memoru-cards-test")

        # デッキ1に2枚、デッキ2に1枚
        for i, deck_id in enumerate(["deck-1", "deck-1", "deck-2"]):
            cards_table.put_item(
                Item={
                    "user_id": "user-1",
                    "card_id": f"card-{i}",
                    "front": f"Q{i}",
                    "back": f"A{i}",
                    "deck_id": deck_id,
                    "interval": 1,
                    "ease_factor": "2.5",
                    "repetitions": 0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        counts = deck_service.get_deck_card_counts("user-1", ["deck-1", "deck-2"])
        assert counts["deck-1"] == 2
        assert counts["deck-2"] == 1


class TestGetDeckDueCounts:
    """DeckService.get_deck_due_counts テスト."""

    def test_due_counts_no_due_cards(self, deck_service, dynamodb_tables):
        """due カードがない場合は 0."""
        counts = deck_service.get_deck_due_counts("user-1", ["deck-1"])
        assert counts == {"deck-1": 0}

    def test_due_counts_with_due_cards(self, deck_service, dynamodb_tables):
        """due カードが存在する場合は正しいカウント."""
        cards_table = dynamodb_tables.Table("memoru-cards-test")
        now = datetime.now(timezone.utc)
        past = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # deck-1: 1枚 due、deck-2: 0枚 due
        cards_table.put_item(
            Item={
                "user_id": "user-1",
                "card_id": "card-due",
                "front": "Q",
                "back": "A",
                "deck_id": "deck-1",
                "next_review_at": past.isoformat(),
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "created_at": past.isoformat(),
            }
        )
        cards_table.put_item(
            Item={
                "user_id": "user-1",
                "card_id": "card-future",
                "front": "Q2",
                "back": "A2",
                "deck_id": "deck-2",
                "next_review_at": "2099-12-31T00:00:00+00:00",
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "created_at": past.isoformat(),
            }
        )

        counts = deck_service.get_deck_due_counts("user-1", ["deck-1", "deck-2"])
        assert counts["deck-1"] == 1
        assert counts["deck-2"] == 0

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


# =============================================================================
# TASK-0089: Sentinel パターン update_deck (description/color REMOVE 対応)
# =============================================================================



@pytest.fixture
def dynamodb_tables_with_deck():
    """moto DynamoDB テーブルとデッキ・サービスをセットアップするフィクスチャ."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

        decks_table = dynamodb.create_table(
            TableName="test-decks-sentinel",
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

        cards_table = dynamodb.create_table(
            TableName="test-cards-sentinel",
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

        service = DeckService(
            table_name="test-decks-sentinel",
            cards_table_name="test-cards-sentinel",
            dynamodb_resource=dynamodb,
        )

        yield service, decks_table


class TestUpdateDeckSentinelPattern:
    """TASK-0089: update_deck の Sentinel パターン (description/color REMOVE 対応) テスト."""

    def test_tc001_description_unset_no_change(self, dynamodb_tables_with_deck):
        """TC-001: description 未送信時は既存値が保持される."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(
            user_id="user-1",
            name="元の名前",
            description="元の説明",
            color="#FF5733",
        )

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            name="新しい名前",
        )

        assert updated.description == "元の説明"

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["description"] == "元の説明"

    def test_tc002_description_none_removes_attribute(self, dynamodb_tables_with_deck):
        """TC-002: description=None で DynamoDB から属性が REMOVE される."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(
            user_id="user-1",
            name="テストデッキ",
            description="テスト用の説明",
        )

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description=None,
        )

        assert updated.description is None

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert "description" not in item

    def test_tc003_description_value_sets_attribute(self, dynamodb_tables_with_deck):
        """TC-003: description に値を渡すと SET される."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(user_id="user-1", name="テストデッキ")

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description="新しい説明",
        )

        assert updated.description == "新しい説明"

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["description"] == "新しい説明"

    def test_tc004_color_unset_no_change(self, dynamodb_tables_with_deck):
        """TC-004: color 未送信時は既存値が保持される."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(
            user_id="user-1",
            name="元の名前",
            color="#FF5733",
        )

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            name="新しい名前",
        )

        assert updated.color == "#FF5733"

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["color"] == "#FF5733"

    def test_tc005_color_none_removes_attribute(self, dynamodb_tables_with_deck):
        """TC-005: color=None で DynamoDB から属性が REMOVE される."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(
            user_id="user-1",
            name="テストデッキ",
            color="#FF5733",
        )

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            color=None,
        )

        assert updated.color is None

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert "color" not in item

    def test_tc006_color_value_sets_attribute(self, dynamodb_tables_with_deck):
        """TC-006: color に値を渡すと SET される."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(user_id="user-1", name="テストデッキ")

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            color="#00FF00",
        )

        assert updated.color == "#00FF00"

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["color"] == "#00FF00"

    def test_tc007_description_and_color_none_both_removed(self, dynamodb_tables_with_deck):
        """TC-007: description と color を同時に null で REMOVE される."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(
            user_id="user-1",
            name="テストデッキ",
            description="削除される説明",
            color="#FF5733",
        )

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description=None,
            color=None,
        )

        assert updated.description is None
        assert updated.color is None

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert "description" not in item
        assert "color" not in item

    def test_tc008_mixed_set_and_remove(self, dynamodb_tables_with_deck):
        """TC-008: SET と REMOVE の混合 UpdateExpression が正しく実行される."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(
            user_id="user-1",
            name="旧名前",
            description="削除される説明",
            color="#FF0000",
        )

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            name="更新名",
            description=None,
            color="#00FF00",
        )

        assert updated.name == "更新名"
        assert updated.description is None
        assert updated.color == "#00FF00"

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["name"] == "更新名"
        assert "description" not in item
        assert item["color"] == "#00FF00"

    def test_tc009_all_unset_returns_existing_deck(self, dynamodb_tables_with_deck):
        """TC-009: 全フィールド未送信時は既存デッキがそのまま返却される."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(
            user_id="user-1",
            name="元の名前",
            description="元の説明",
            color="#FF5733",
        )

        result = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
        )

        assert result.name == "元の名前"
        assert result.description == "元の説明"
        assert result.color == "#FF5733"

    def test_tc010_name_unset_preserves_existing_name(self, dynamodb_tables_with_deck):
        """TC-010: name 省略時は既存名が維持され、description のみ SET される."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(
            user_id="user-1",
            name="元の名前",
        )

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description="新しい説明",
        )

        assert updated.name == "元の名前"
        assert updated.description == "新しい説明"

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["name"] == "元の名前"
        assert item["description"] == "新しい説明"

    def test_tc011_description_remove_then_set(self, dynamodb_tables_with_deck):
        """TC-011: description を REMOVE してから再度 SET できる."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(
            user_id="user-1",
            name="テストデッキ",
            description="最初の説明",
        )

        service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description=None,
        )

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert "description" not in item

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description="復活した説明",
        )

        assert updated.description == "復活した説明"

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["description"] == "復活した説明"

    def test_tc012_color_remove_then_set(self, dynamodb_tables_with_deck):
        """TC-012: color を REMOVE してから再度 SET できる."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(
            user_id="user-1",
            name="テストデッキ",
            color="#FF0000",
        )

        service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            color=None,
        )

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert "color" not in item

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            color="#0000FF",
        )

        assert updated.color == "#0000FF"

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["color"] == "#0000FF"

    def test_tc013_unset_is_not_none(self):
        """TC-013: _UNSET sentinel は None とは異なるオブジェクト."""
        from services.deck_service import _UNSET as deck_unset  # noqa: PLC0415

        assert deck_unset is not None
        assert deck_unset != None  # noqa: E711

    def test_tc014_not_found_with_sentinel_args(self, dynamodb_tables_with_deck):
        """TC-014: 存在しないデッキの更新で DeckNotFoundError."""
        service, table = dynamodb_tables_with_deck

        with pytest.raises(DeckNotFoundError):
            service.update_deck(
                user_id="user-1",
                deck_id="nonexistent",
                description=None,
            )

    def test_tc015_description_none_on_deck_without_description(self, dynamodb_tables_with_deck):
        """TC-015: description が存在しないデッキへの REMOVE は冪等に正常完了する."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(user_id="user-1", name="説明なしデッキ")

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert "description" not in item

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description=None,
        )

        assert updated.description is None

    def test_tc016_remove_only_updates_updated_at(self, dynamodb_tables_with_deck):
        """TC-016: REMOVE のみでも updated_at が更新される."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(
            user_id="user-1",
            name="テストデッキ",
            description="削除される説明",
        )

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description=None,
        )

        assert updated.updated_at is not None

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert "updated_at" in item
        assert "description" not in item

    def test_tc017_name_unset_description_set(self, dynamodb_tables_with_deck):
        """TC-017: name 省略 + description SET の組み合わせ."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(user_id="user-1", name="必須フィールドテスト")

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description="新しい説明",
        )

        assert updated.name == "必須フィールドテスト"
        assert updated.description == "新しい説明"

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["name"] == "必須フィールドテスト"
        assert item["description"] == "新しい説明"

    def test_tc018_all_fields_set_backward_compat(self, dynamodb_tables_with_deck):
        """TC-018: 全フィールド SET で従来動作との互換性を確認."""
        service, table = dynamodb_tables_with_deck

        created = service.create_deck(
            user_id="user-1",
            name="旧名前",
            description="旧説明",
            color="#FF0000",
        )

        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            name="新名前",
            description="新説明",
            color="#0000FF",
        )

        assert updated.name == "新名前"
        assert updated.description == "新説明"
        assert updated.color == "#0000FF"

        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["name"] == "新名前"
        assert item["description"] == "新説明"
        assert item["color"] == "#0000FF"

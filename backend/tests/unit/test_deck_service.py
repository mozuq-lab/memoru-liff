"""Unit tests for DeckService (moto DynamoDB mock)."""

import pytest
from moto import mock_aws
import boto3
from datetime import datetime, timezone

from services.deck_service import (
    DeckService,
    DeckNotFoundError,
    DeckLimitExceededError,
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
                {"AttributeName": "deck_index_key", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user_id-due-index",
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "next_review_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "deck-cards-index",
                    "KeySchema": [
                        {"AttributeName": "deck_index_key", "KeyType": "HASH"},
                        {"AttributeName": "next_review_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "KEYS_ONLY"},
                },
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
        deck_service.create_deck(user_id="user-1", name="ユーザー1のデッキ")
        deck_service.create_deck(user_id="user-2", name="ユーザー2のデッキ")

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
                "deck_index_key": f"user-1#{deck.deck_id}",
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
                "deck_index_key": f"user-1#{deck.deck_id}",
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
        # GSI 用派生キーも併せて削除される (PR #47 [P2])。
        assert "deck_index_key" not in card1["Item"]
        assert "deck_index_key" not in card2["Item"]

    def test_delete_deck_skips_card_moved_to_another_deck_after_collection(
        self, deck_service, dynamodb_tables, monkeypatch
    ):
        """Medium-5: 収集後に別デッキへ移動されたカードの deck_id は保護される。

        【テスト目的】: _reset_cards_deck_id が対象カードを Query で収集した後、
        UpdateItem を発行するまでの間に別リクエストがそのカードを別デッキへ
        移動した場合、ConditionExpression (deck_id = :deleted_deck_id) により
        更新がスキップされ、移動先の deck_id が誤って剥がされないことを検証する。
        🔵 信頼性レベル: 青信号 - _reset_cards_deck_id に付与した ConditionExpression の直接検証。

        Given: カードがデッキ A に属し、削除処理の収集クエリ完了直後に
               デッキ B へ移動される (レースコンディション)
        When: デッキ A を削除する
        Then: カードの deck_id はデッキ B のまま保持される
        """
        deck_a = deck_service.create_deck(user_id="user-1", name="Deck A")
        deck_b = deck_service.create_deck(user_id="user-1", name="Deck B")

        # 【重要】: DeckService が内部で保持する cards_table (deck_service.cards_table)
        # を直接パッチする。dynamodb_tables.Table(...) で改めて取得したオブジェクトは
        # 同じテーブルを指していても別の Python オブジェクトになり、
        # deck_service 内部の呼び出しには反映されない。
        cards_table = deck_service.cards_table
        cards_table.put_item(
            Item={
                "user_id": "user-1",
                "card_id": "card-moved",
                "front": "Q",
                "back": "A",
                "deck_id": deck_a.deck_id,
                "deck_index_key": f"user-1#{deck_a.deck_id}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        real_query = cards_table.query

        def query_then_move(*args, **kwargs):
            # 収集クエリ完了直後、reset の UpdateItem が発行される前に
            # 別リクエストがカードを別デッキへ移動したことを模擬する。
            response = real_query(*args, **kwargs)
            cards_table.update_item(
                Key={"user_id": "user-1", "card_id": "card-moved"},
                UpdateExpression="SET deck_id = :new_deck, deck_index_key = :new_key",
                ExpressionAttributeValues={
                    ":new_deck": deck_b.deck_id,
                    ":new_key": f"user-1#{deck_b.deck_id}",
                },
            )
            return response

        monkeypatch.setattr(cards_table, "query", query_then_move)

        deck_service.delete_deck("user-1", deck_a.deck_id)

        card = cards_table.get_item(
            Key={"user_id": "user-1", "card_id": "card-moved"}
        )["Item"]
        assert card["deck_id"] == deck_b.deck_id
        assert card["deck_index_key"] == f"user-1#{deck_b.deck_id}"

    def test_delete_deck_does_not_recreate_deleted_card(
        self, deck_service, dynamodb_tables, monkeypatch
    ):
        """Medium-5: 収集後に削除されたカードはゴーストとして再作成されない。

        【テスト目的】: _reset_cards_deck_id の収集後にカード自体が削除された場合、
        ConditionExpression なしの UpdateItem は upsert としてゴーストアイテムを
        再作成してしまう (High-1 と同型の欠陥)。ConditionExpression
        (deck_id = :deleted_deck_id) はアイテム不存在時も偽になるため、
        ゴースト再作成が防止されることを検証する。
        🔵 信頼性レベル: 青信号 - _reset_cards_deck_id に付与した ConditionExpression の直接検証。

        Given: カードがデッキに属し、削除処理の収集クエリ完了直後に
               カード自体が削除される (レースコンディション)
        When: デッキを削除する
        Then: 削除済みカードが再作成されない
        """
        deck = deck_service.create_deck(user_id="user-1", name="Deck")

        # 【重要】: deck_service.cards_table を直接パッチする（上のテストと同じ理由）。
        cards_table = deck_service.cards_table
        cards_table.put_item(
            Item={
                "user_id": "user-1",
                "card_id": "card-deleted",
                "front": "Q",
                "back": "A",
                "deck_id": deck.deck_id,
                "deck_index_key": f"user-1#{deck.deck_id}",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        real_query = cards_table.query

        def query_then_delete(*args, **kwargs):
            # 収集クエリ完了直後、reset の UpdateItem が発行される前に
            # 別リクエストがカード自体を削除したことを模擬する。
            response = real_query(*args, **kwargs)
            cards_table.delete_item(
                Key={"user_id": "user-1", "card_id": "card-deleted"}
            )
            return response

        monkeypatch.setattr(cards_table, "query", query_then_delete)

        deck_service.delete_deck("user-1", deck.deck_id)

        response = cards_table.get_item(
            Key={"user_id": "user-1", "card_id": "card-deleted"}
        )
        assert "Item" not in response


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
                    # GSI 用複合キー (PR #47 [P2])。card_service 経由なら自動付与される。
                    "deck_index_key": f"user-1#{deck_id}",
                    # 実カードは常に next_review_at を持つ (card_service が作成時に設定)。
                    # deck-cards-index は next_review_at を RANGE キーとするため必須。
                    "next_review_at": datetime.now(timezone.utc).isoformat(),
                    "interval": 1,
                    "ease_factor": "2.5",
                    "repetitions": 0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        counts = deck_service.get_deck_card_counts("user-1", ["deck-1", "deck-2"])
        assert counts["deck-1"] == 2
        assert counts["deck-2"] == 1

    def test_card_counts_excludes_cards_without_deck_id(
        self, deck_service, dynamodb_tables
    ):
        """deck_id を持たない (未分類) カードは集計に含まれない (スパースインデックス)."""
        cards_table = dynamodb_tables.Table("memoru-cards-test")

        # deck-1 に紐付くカード 1 枚
        cards_table.put_item(
            Item={
                "user_id": "user-1",
                "card_id": "card-with-deck",
                "front": "Q",
                "back": "A",
                "deck_id": "deck-1",
                "deck_index_key": "user-1#deck-1",
                "next_review_at": datetime.now(timezone.utc).isoformat(),
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        # deck_id を持たないカード (GSI に投影されない)
        cards_table.put_item(
            Item={
                "user_id": "user-1",
                "card_id": "card-no-deck",
                "front": "Q2",
                "back": "A2",
                "next_review_at": datetime.now(timezone.utc).isoformat(),
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        counts = deck_service.get_deck_card_counts("user-1", ["deck-1"])
        assert counts["deck-1"] == 1

    def test_card_counts_empty_deck_ids(self, deck_service):
        """deck_ids が空の場合は空 dict を返す."""
        assert deck_service.get_deck_card_counts("user-1", []) == {}

    def test_card_counts_isolated_by_user(self, deck_service, dynamodb_tables):
        """[P2 回帰] 異なるユーザーが同一 deck_id を持っても自分のカードのみ集計される.

        user-1 と user-2 が同じ deck_id のカードを 1 枚ずつ持つとき、
        user-1 のカウントは自分の 1 枚のみ (= 1) であること。
        deck_index_key (= "<user_id>#<deck_id>") により集計が混ざらないことを検証する。
        """
        cards_table = dynamodb_tables.Table("memoru-cards-test")
        shared_deck_id = "deck-shared"

        for user_id, card_id in [("user-1", "card-u1"), ("user-2", "card-u2")]:
            cards_table.put_item(
                Item={
                    "user_id": user_id,
                    "card_id": card_id,
                    "front": "Q",
                    "back": "A",
                    "deck_id": shared_deck_id,
                    "deck_index_key": f"{user_id}#{shared_deck_id}",
                    "next_review_at": datetime.now(timezone.utc).isoformat(),
                    "interval": 1,
                    "ease_factor": "2.5",
                    "repetitions": 0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        counts_u1 = deck_service.get_deck_card_counts("user-1", [shared_deck_id])
        counts_u2 = deck_service.get_deck_card_counts("user-2", [shared_deck_id])
        assert counts_u1[shared_deck_id] == 1
        assert counts_u2[shared_deck_id] == 1


class TestGetDeckDueCounts:
    """DeckService.get_deck_due_counts テスト."""

    def test_due_counts_no_due_cards(self, deck_service, dynamodb_tables):
        """due カードがない場合は 0."""
        counts = deck_service.get_deck_due_counts("user-1", ["deck-1"])
        assert counts == {"deck-1": 0}

    def test_due_counts_with_due_cards(self, deck_service, dynamodb_tables):
        """due カードが存在する場合は正しいカウント."""
        cards_table = dynamodb_tables.Table("memoru-cards-test")
        past = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # deck-1: 1枚 due、deck-2: 0枚 due
        cards_table.put_item(
            Item={
                "user_id": "user-1",
                "card_id": "card-due",
                "front": "Q",
                "back": "A",
                "deck_id": "deck-1",
                "deck_index_key": "user-1#deck-1",
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
                "deck_index_key": "user-1#deck-2",
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

    def test_due_counts_boundary_inclusive(self, deck_service, dynamodb_tables):
        """next_review_at <= now の境界は包含 (<=)。過去/現在は due、未来は非 due."""
        cards_table = dynamodb_tables.Table("memoru-cards-test")

        # 過去 (due)
        cards_table.put_item(
            Item={
                "user_id": "user-1",
                "card_id": "card-past",
                "front": "Q",
                "back": "A",
                "deck_id": "deck-1",
                "deck_index_key": "user-1#deck-1",
                "next_review_at": "2000-01-01T00:00:00+00:00",
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "created_at": "2000-01-01T00:00:00+00:00",
            }
        )
        # 遠い未来 (非 due)
        cards_table.put_item(
            Item={
                "user_id": "user-1",
                "card_id": "card-future",
                "front": "Q",
                "back": "A",
                "deck_id": "deck-1",
                "deck_index_key": "user-1#deck-1",
                "next_review_at": "2999-01-01T00:00:00+00:00",
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "created_at": "2000-01-01T00:00:00+00:00",
            }
        )

        counts = deck_service.get_deck_due_counts("user-1", ["deck-1"])
        # 過去の 1 枚のみ due
        assert counts["deck-1"] == 1

    def test_due_counts_empty_deck_ids(self, deck_service):
        """deck_ids が空の場合は空 dict を返す."""
        assert deck_service.get_deck_due_counts("user-1", []) == {}

    def test_due_counts_isolated_by_user(self, deck_service, dynamodb_tables):
        """[P2 回帰] 同一 deck_id でも due 集計が他ユーザーと混ざらない."""
        cards_table = dynamodb_tables.Table("memoru-cards-test")
        shared_deck_id = "deck-shared"
        past = datetime(2024, 1, 1, tzinfo=timezone.utc)

        for user_id, card_id in [("user-1", "card-u1"), ("user-2", "card-u2")]:
            cards_table.put_item(
                Item={
                    "user_id": user_id,
                    "card_id": card_id,
                    "front": "Q",
                    "back": "A",
                    "deck_id": shared_deck_id,
                    "deck_index_key": f"{user_id}#{shared_deck_id}",
                    "next_review_at": past.isoformat(),
                    "interval": 1,
                    "ease_factor": "2.5",
                    "repetitions": 0,
                    "created_at": past.isoformat(),
                }
            )

        counts_u1 = deck_service.get_deck_due_counts("user-1", [shared_deck_id])
        assert counts_u1[shared_deck_id] == 1


class TestDeckCountsPagination:
    """LastEvaluatedKey ループでの Count 合算テスト (COUNT クエリのページング)."""

    def test_card_counts_sums_count_across_pages(
        self, deck_service, dynamodb_tables, monkeypatch
    ):
        """複数ページにまたがる COUNT クエリの Count が合算される."""
        # cards_table.query をモックして 2 ページ分の COUNT 応答を返す。
        calls = {"n": 0}

        def fake_query(**kwargs):
            assert kwargs.get("Select") == "COUNT"
            calls["n"] += 1
            if "ExclusiveStartKey" not in kwargs:
                # 1 ページ目: Count=2, 続きあり
                return {"Count": 2, "LastEvaluatedKey": {"deck_index_key": "user-1#deck-1"}}
            # 2 ページ目: Count=3, 続きなし
            return {"Count": 3}

        monkeypatch.setattr(deck_service.cards_table, "query", fake_query)

        counts = deck_service.get_deck_card_counts("user-1", ["deck-1"])
        assert counts["deck-1"] == 5
        assert calls["n"] == 2

    def test_due_counts_sums_count_across_pages(
        self, deck_service, dynamodb_tables, monkeypatch
    ):
        """due COUNT クエリも複数ページの Count を合算する."""
        def fake_query(**kwargs):
            assert kwargs.get("Select") == "COUNT"
            assert ":now" in kwargs["ExpressionAttributeValues"]
            if "ExclusiveStartKey" not in kwargs:
                return {"Count": 1, "LastEvaluatedKey": {"deck_index_key": "user-1#deck-1"}}
            return {"Count": 4}

        monkeypatch.setattr(deck_service.cards_table, "query", fake_query)

        counts = deck_service.get_deck_due_counts("user-1", ["deck-1"])
        assert counts["deck-1"] == 5


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
                {"AttributeName": "deck_index_key", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user_id-due-index",
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "next_review_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "deck-cards-index",
                    "KeySchema": [
                        {"AttributeName": "deck_index_key", "KeyType": "HASH"},
                        {"AttributeName": "next_review_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "KEYS_ONLY"},
                },
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

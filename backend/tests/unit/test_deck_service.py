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
        # 【テスト前準備】: moto で DynamoDB テーブルをモック作成
        # 【環境初期化】: decks / cards テーブルを PAY_PER_REQUEST で作成
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
        """TC-001: description 未送信時は変更なし.

        # 【テスト目的】: description パラメータを渡さない場合（デフォルト _UNSET）に
        #               既存の description が保持されること
        # 【テスト内容】: update_deck を description 引数なしで呼び出す
        # 【期待される動作】: DynamoDB 上の description は変更されない
        # 🔵 信頼性レベル: 青信号 - REQ-105 の裏条件 + card_service.py の参照実装と同一パターン
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: description 付きのデッキを作成
        # 【初期条件設定】: description="元の説明" で create_deck を呼び出し
        created = service.create_deck(
            user_id="user-1",
            name="元の名前",
            description="元の説明",
            color="#FF5733",
        )

        # 【実際の処理実行】: update_deck に description を渡さず（デフォルト _UNSET）呼び出す
        # 【処理内容】: Sentinel パターンにより description の変更なしが実行される
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            name="新しい名前",
            # description は渡さない → _UNSET のまま
        )

        # 【結果検証】: 返却された deck オブジェクトの description が元の値であること
        # 【期待値確認】: description は "元の説明" が維持されること
        assert updated.description == "元の説明"  # 【確認内容】: description が変更されていないこと 🔵

        # 【DynamoDB 確認】: DynamoDB アイテムに description 属性が残存していること
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["description"] == "元の説明"  # 【確認内容】: DynamoDB 上でも description が維持されていること 🔵

    def test_tc002_description_none_removes_attribute(self, dynamodb_tables_with_deck):
        """TC-002: description を null 送信すると REMOVE される.

        # 【テスト目的】: description=None を明示的に渡した場合に DynamoDB から
        #               description 属性が削除されること
        # 【テスト内容】: update_deck に description=None を渡して呼び出す
        # 【期待される動作】: UpdateExpression に REMOVE description が含まれ、
        #                   DynamoDB アイテムから属性が消える
        # 🔵 信頼性レベル: 青信号 - REQ-105 より
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: description 付きのデッキを作成
        # 【初期条件設定】: description="テスト用の説明" で create_deck を呼び出し
        created = service.create_deck(
            user_id="user-1",
            name="テストデッキ",
            description="テスト用の説明",
        )

        # 【実際の処理実行】: update_deck に description=None を渡して呼び出す
        # 【処理内容】: Sentinel パターンにより description の REMOVE が実行される
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description=None,  # 明示的 null → REMOVE
        )

        # 【結果検証】: 返却された deck オブジェクトの description が None であること
        assert updated.description is None  # 【確認内容】: deck.description が None であること 🔵

        # 【DynamoDB 確認】: DynamoDB アイテムから description 属性が削除されていること
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert "description" not in item  # 【確認内容】: DynamoDB アイテムから description が消えていること 🔵

    def test_tc003_description_value_sets_attribute(self, dynamodb_tables_with_deck):
        """TC-003: description に値を渡すと SET される.

        # 【テスト目的】: description="新しい説明" を渡した場合に DynamoDB で
        #               description が更新されること
        # 【テスト内容】: update_deck に description 値を渡して呼び出す
        # 【期待される動作】: UpdateExpression に SET description = :description が含まれる
        # 🔵 信頼性レベル: 青信号 - architecture.md セクション2 より
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: description なしのデッキを作成
        # 【初期条件設定】: description を持たないデッキを用意
        created = service.create_deck(user_id="user-1", name="テストデッキ")

        # 【実際の処理実行】: update_deck に description="新しい説明" を渡して呼び出す
        # 【処理内容】: Sentinel パターンにより description の SET が実行される
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description="新しい説明",
        )

        # 【結果検証】: 返却された deck オブジェクトの description が更新されていること
        assert updated.description == "新しい説明"  # 【確認内容】: deck.description が "新しい説明" であること 🔵

        # 【DynamoDB 確認】: DynamoDB アイテムの description が更新されていること
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["description"] == "新しい説明"  # 【確認内容】: DynamoDB 上でも description が SET されていること 🔵

    def test_tc004_color_unset_no_change(self, dynamodb_tables_with_deck):
        """TC-004: color 未送信時は変更なし.

        # 【テスト目的】: color パラメータを渡さない場合（デフォルト _UNSET）に
        #               既存の color が保持されること
        # 【テスト内容】: update_deck を color 引数なしで呼び出す
        # 【期待される動作】: DynamoDB 上の color は変更されない
        # 🔵 信頼性レベル: 青信号 - REQ-106 の裏条件 + card_service.py の参照実装と同一パターン
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: color 付きのデッキを作成
        # 【初期条件設定】: color="#FF5733" で create_deck を呼び出し
        created = service.create_deck(
            user_id="user-1",
            name="元の名前",
            color="#FF5733",
        )

        # 【実際の処理実行】: update_deck に color を渡さず（デフォルト _UNSET）呼び出す
        # 【処理内容】: Sentinel パターンにより color の変更なしが実行される
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            name="新しい名前",
            # color は渡さない → _UNSET のまま
        )

        # 【結果検証】: 返却された deck オブジェクトの color が元の値であること
        assert updated.color == "#FF5733"  # 【確認内容】: color が変更されていないこと 🔵

        # 【DynamoDB 確認】: DynamoDB アイテムに color 属性が残存していること
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["color"] == "#FF5733"  # 【確認内容】: DynamoDB 上でも color が維持されていること 🔵

    def test_tc005_color_none_removes_attribute(self, dynamodb_tables_with_deck):
        """TC-005: color を null 送信すると REMOVE される.

        # 【テスト目的】: color=None を明示的に渡した場合に DynamoDB から
        #               color 属性が削除されること
        # 【テスト内容】: update_deck に color=None を渡して呼び出す
        # 【期待される動作】: UpdateExpression に REMOVE color が含まれ、
        #                   DynamoDB アイテムから属性が消える
        # 🔵 信頼性レベル: 青信号 - REQ-106 より
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: color 付きのデッキを作成
        # 【初期条件設定】: color="#FF5733" で create_deck を呼び出し
        created = service.create_deck(
            user_id="user-1",
            name="テストデッキ",
            color="#FF5733",
        )

        # 【実際の処理実行】: update_deck に color=None を渡して呼び出す
        # 【処理内容】: Sentinel パターンにより color の REMOVE が実行される
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            color=None,  # 明示的 null → REMOVE
        )

        # 【結果検証】: 返却された deck オブジェクトの color が None であること
        assert updated.color is None  # 【確認内容】: deck.color が None であること 🔵

        # 【DynamoDB 確認】: DynamoDB アイテムから color 属性が削除されていること
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert "color" not in item  # 【確認内容】: DynamoDB アイテムから color が消えていること 🔵

    def test_tc006_color_value_sets_attribute(self, dynamodb_tables_with_deck):
        """TC-006: color に値を渡すと SET される.

        # 【テスト目的】: color="#00FF00" を渡した場合に DynamoDB で color が更新されること
        # 【テスト内容】: update_deck に color 値を渡して呼び出す
        # 【期待される動作】: UpdateExpression に SET color = :color が含まれる
        # 🔵 信頼性レベル: 青信号 - architecture.md セクション2 より
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: color なしのデッキを作成
        # 【初期条件設定】: color を持たないデッキを用意
        created = service.create_deck(user_id="user-1", name="テストデッキ")

        # 【実際の処理実行】: update_deck に color="#00FF00" を渡して呼び出す
        # 【処理内容】: Sentinel パターンにより color の SET が実行される
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            color="#00FF00",
        )

        # 【結果検証】: 返却された deck オブジェクトの color が更新されていること
        assert updated.color == "#00FF00"  # 【確認内容】: deck.color が "#00FF00" であること 🔵

        # 【DynamoDB 確認】: DynamoDB アイテムの color が更新されていること
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["color"] == "#00FF00"  # 【確認内容】: DynamoDB 上でも color が SET されていること 🔵

    def test_tc007_description_and_color_none_both_removed(self, dynamodb_tables_with_deck):
        """TC-007: description と color を同時に null で REMOVE (EDGE-102).

        # 【テスト目的】: 両方のオプショナルフィールドを同時に null にした場合に
        #               両方が REMOVE されること
        # 【テスト内容】: update_deck に description=None, color=None を渡して呼び出す
        # 【期待される動作】: UpdateExpression に REMOVE description, color が含まれる
        # 🔵 信頼性レベル: 青信号 - EDGE-102 より
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: description と color の両方を持つデッキを作成
        # 【初期条件設定】: description と color を持つデッキを用意
        created = service.create_deck(
            user_id="user-1",
            name="テストデッキ",
            description="削除される説明",
            color="#FF5733",
        )

        # 【実際の処理実行】: update_deck に description=None, color=None を渡して呼び出す
        # 【処理内容】: Sentinel パターンにより description と color の両方の REMOVE が実行される
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description=None,  # 明示的 null → REMOVE
            color=None,         # 明示的 null → REMOVE
        )

        # 【結果検証】: 返却された deck オブジェクトの両フィールドが None であること
        assert updated.description is None  # 【確認内容】: deck.description が None であること 🔵
        assert updated.color is None         # 【確認内容】: deck.color が None であること 🔵

        # 【DynamoDB 確認】: DynamoDB アイテムから両属性が削除されていること
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert "description" not in item  # 【確認内容】: DynamoDB アイテムから description が消えていること 🔵
        assert "color" not in item         # 【確認内容】: DynamoDB アイテムから color が消えていること 🔵

    def test_tc008_mixed_set_and_remove(self, dynamodb_tables_with_deck):
        """TC-008: SET と REMOVE の混合 UpdateExpression (name SET + description REMOVE + color SET).

        # 【テスト目的】: SET と REMOVE を組み合わせた UpdateExpression が正しく
        #               構築・実行されること
        # 【テスト内容】: update_deck に name 値, description=None, color 値を渡して呼び出す
        # 【期待される動作】: SET #name, color + REMOVE description が1回の update_item で実行される
        # 🔵 信頼性レベル: 青信号 - architecture.md セクション2 使用例 4.7 より
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: description と color を持つデッキを作成
        # 【初期条件設定】: 全フィールドを持つデッキを用意
        created = service.create_deck(
            user_id="user-1",
            name="旧名前",
            description="削除される説明",
            color="#FF0000",
        )

        # 【実際の処理実行】: SET + REMOVE 混合の update_deck を呼び出す
        # 【処理内容】: 名前変更 + 説明クリア + カラー変更を1回のリクエストで実行
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            name="更新名",
            description=None,   # REMOVE
            color="#00FF00",    # SET
        )

        # 【結果検証】: 各フィールドの状態を個別に検証
        assert updated.name == "更新名"          # 【確認内容】: name が "更新名" に SET されていること 🔵
        assert updated.description is None       # 【確認内容】: description が REMOVE されて None であること 🔵
        assert updated.color == "#00FF00"        # 【確認内容】: color が "#00FF00" に SET されていること 🔵

        # 【DynamoDB 確認】: DynamoDB 上での各フィールドの状態を確認
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["name"] == "更新名"           # 【確認内容】: DynamoDB 上で name が SET されていること 🔵
        assert "description" not in item          # 【確認内容】: DynamoDB 上で description が削除されていること 🔵
        assert item["color"] == "#00FF00"         # 【確認内容】: DynamoDB 上で color が SET されていること 🔵

    def test_tc009_all_unset_returns_existing_deck(self, dynamodb_tables_with_deck):
        """TC-009: 全フィールド未送信時はそのまま返却.

        # 【テスト目的】: 全パラメータがデフォルト _UNSET の場合にデッキが変更されずに返却されること
        # 【テスト内容】: update_deck を全パラメータなしで呼び出す
        # 【期待される動作】: DynamoDB 操作は行われず、既存 deck がそのまま返される
        # 🟡 信頼性レベル: 黄信号 - 既存 update_deck の動作から妥当な推測（使用例 4.6）
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: 全フィールドを持つデッキを作成
        # 【初期条件設定】: description と color を持つデッキを用意
        created = service.create_deck(
            user_id="user-1",
            name="元の名前",
            description="元の説明",
            color="#FF5733",
        )

        # 【実際の処理実行】: update_deck に全パラメータなしで呼び出す
        # 【処理内容】: 全フィールドが _UNSET のため、変更なしでデッキをそのまま返す
        result = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            # 全パラメータなし → 全フィールド _UNSET
        )

        # 【結果検証】: 既存のデッキオブジェクトがそのまま返される
        assert result.name == "元の名前"        # 【確認内容】: name が変更されていないこと 🟡
        assert result.description == "元の説明"  # 【確認内容】: description が変更されていないこと 🟡
        assert result.color == "#FF5733"        # 【確認内容】: color が変更されていないこと 🟡

    def test_tc010_name_unset_preserves_existing_name(self, dynamodb_tables_with_deck):
        """TC-010: name は _UNSET で変更なし、値で SET.

        # 【テスト目的】: name=_UNSET（省略）でデフォルトの場合に既存名が維持されること
        # 【テスト内容】: update_deck を name 引数なしで、description のみ更新する呼び出す
        # 【期待される動作】: name は変更されず、description のみ SET される
        # 🔵 信頼性レベル: 青信号 - 要件定義 3.2 name フィールドの制約より
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: デッキを作成
        # 【初期条件設定】: name を持つデッキを用意
        created = service.create_deck(
            user_id="user-1",
            name="元の名前",
        )

        # 【実際の処理実行】: update_deck に name を渡さず、description のみ更新する
        # 【処理内容】: name は _UNSET のため変更なし、description のみ SET される
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            # name は渡さない → _UNSET のまま
            description="新しい説明",
        )

        # 【結果検証】: name が変更されず、description のみ SET されていること
        assert updated.name == "元の名前"         # 【確認内容】: name が変更されていないこと 🔵
        assert updated.description == "新しい説明"  # 【確認内容】: description が "新しい説明" に SET されていること 🔵

        # 【DynamoDB 確認】: DynamoDB 上での状態を確認
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["name"] == "元の名前"          # 【確認内容】: DynamoDB 上で name が変更されていないこと 🔵
        assert item["description"] == "新しい説明"   # 【確認内容】: DynamoDB 上で description が SET されていること 🔵

    def test_tc011_description_remove_then_set(self, dynamodb_tables_with_deck):
        """TC-011: description を REMOVE してから SET できる.

        # 【テスト目的】: description を一度 REMOVE した後に、新しい値で SET できること
        # 【テスト内容】: REMOVE → SET の2ステップ操作を実行
        # 【期待される動作】: REMOVE 後のアイテムに新しい description を SET すると正しく追加される
        # 🔵 信頼性レベル: 青信号 - card_service.py test_deck_id_remove_then_set と同一パターン
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: description 付きのデッキを作成
        # 【初期条件設定】: description を持つデッキを用意
        created = service.create_deck(
            user_id="user-1",
            name="テストデッキ",
            description="最初の説明",
        )

        # 【実際の処理実行（REMOVE）】: description=None で REMOVE する
        # 【処理内容】: description が DynamoDB から削除される
        service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description=None,
        )

        # 【中間状態確認】: description が削除されていること
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert "description" not in item  # 【確認内容】: REMOVE 後に description が存在しないこと 🔵

        # 【実際の処理実行（SET）】: description="復活した説明" で SET する
        # 【処理内容】: REMOVE 後のアイテムに description を再度 SET する
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description="復活した説明",
        )

        # 【最終状態確認】: description が新しい値で SET されていること
        assert updated.description == "復活した説明"  # 【確認内容】: deck.description が "復活した説明" であること 🔵

        # 【DynamoDB 確認】: DynamoDB 上でも description が再 SET されていること
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["description"] == "復活した説明"  # 【確認内容】: DynamoDB 上でも description が復活していること 🔵

    def test_tc012_color_remove_then_set(self, dynamodb_tables_with_deck):
        """TC-012: color を REMOVE してから SET できる.

        # 【テスト目的】: color を一度 REMOVE した後に、新しい値で SET できること
        # 【テスト内容】: REMOVE → SET の2ステップ操作を実行
        # 【期待される動作】: REMOVE 後のアイテムに新しい color を SET すると正しく追加される
        # 🔵 信頼性レベル: 青信号 - card_service.py test_deck_id_remove_then_set と同一パターン
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: color 付きのデッキを作成
        # 【初期条件設定】: color を持つデッキを用意
        created = service.create_deck(
            user_id="user-1",
            name="テストデッキ",
            color="#FF0000",
        )

        # 【実際の処理実行（REMOVE）】: color=None で REMOVE する
        # 【処理内容】: color が DynamoDB から削除される
        service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            color=None,
        )

        # 【中間状態確認】: color が削除されていること
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert "color" not in item  # 【確認内容】: REMOVE 後に color が存在しないこと 🔵

        # 【実際の処理実行（SET）】: color="#0000FF" で SET する
        # 【処理内容】: REMOVE 後のアイテムに color を再度 SET する
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            color="#0000FF",
        )

        # 【最終状態確認】: color が新しい値で SET されていること
        assert updated.color == "#0000FF"  # 【確認内容】: deck.color が "#0000FF" であること 🔵

        # 【DynamoDB 確認】: DynamoDB 上でも color が再 SET されていること
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["color"] == "#0000FF"  # 【確認内容】: DynamoDB 上でも color が復活していること 🔵

    def test_tc013_unset_is_not_none(self):
        """TC-013: _UNSET sentinel は None とは異なるオブジェクト.

        # 【テスト目的】: _UNSET sentinel が None とは異なるオブジェクトであること
        # 【テスト内容】: _UNSET と None の同一性・等価性を確認
        # 【期待される動作】: _UNSET is not None が True
        # 🔵 信頼性レベル: 青信号 - card_service.py test_sentinel_is_not_none と同一パターン
        """
        # 【インポート】: TASK-0089 で追加予定の _UNSET を遅延インポート
        # 【期待される失敗】: _UNSET が deck_service.py に存在しないため ImportError が発生する（Red フェーズ）
        from services.deck_service import _UNSET as deck_unset  # noqa: PLC0415

        # 【実際の処理実行】: _UNSET と None の比較
        # 【処理内容】: Sentinel パターンの基盤となる _UNSET 定数の正しさを確認
        assert deck_unset is not None          # 【確認内容】: is 演算子で None と異なることを確認 🔵
        assert deck_unset != None              # noqa: E711  # 【確認内容】: == 演算子で None と異なることを確認 🔵

    def test_tc014_not_found_with_sentinel_args(self, dynamodb_tables_with_deck):
        """TC-014: 存在しないデッキの更新で DeckNotFoundError (Sentinel 引数付き).

        # 【テスト目的】: 存在しない deck_id を指定して update_deck を呼んだ場合のエラー処理
        # 【テスト内容】: 存在しない deck_id に description=None を渡して update_deck を呼び出す
        # 【期待される動作】: DeckNotFoundError が発生
        # 🔵 信頼性レベル: 青信号 - 既存テスト test_update_not_found と同一パターン
        """
        service, table = dynamodb_tables_with_deck

        # 【実際の処理実行】: 存在しない deck_id に Sentinel 引数を渡して update_deck を呼び出す
        # 【処理内容】: デッキ存在チェックで DeckNotFoundError が発生すること
        with pytest.raises(DeckNotFoundError):
            service.update_deck(
                user_id="user-1",
                deck_id="nonexistent",
                description=None,  # Sentinel 引数付き
            )

    def test_tc015_description_none_on_deck_without_description(self, dynamodb_tables_with_deck):
        """TC-015: 既に description がないデッキに description=None を送信しても正常完了.

        # 【テスト目的】: description 属性がもともと存在しないデッキに対して REMOVE を実行するケース
        # 【テスト内容】: description なしデッキ作成後、description=None で update_deck を呼び出す
        # 【期待される動作】: エラーなく正常に完了し、deck.description is None が返される
        # 🟡 信頼性レベル: 黄信号 - DynamoDB REMOVE の冪等性は AWS ドキュメントより妥当な推測
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: description なしのデッキを作成
        # 【初期条件設定】: description を持たないデッキを用意
        created = service.create_deck(user_id="user-1", name="説明なしデッキ")

        # 【初期状態確認】: description が存在しないことを確認
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert "description" not in item  # 【確認内容】: 初期状態で description が存在しないこと 🟡

        # 【実際の処理実行】: description=None を渡して update_deck を呼び出す
        # 【処理内容】: 存在しない属性に対する REMOVE は DynamoDB では冪等に動作する
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description=None,  # 存在しない属性を REMOVE
        )

        # 【結果検証】: エラーなく正常に完了し、deck.description は None であること
        assert updated.description is None  # 【確認内容】: 正常完了し description が None であること 🟡

    def test_tc016_remove_only_updates_updated_at(self, dynamodb_tables_with_deck):
        """TC-016: REMOVE のみでも updated_at が更新される.

        # 【テスト目的】: update_parts が空で remove_parts のみある場合、
        #               updated_at は SET として追加される必要がある
        # 【テスト内容】: description=None のみ渡して update_deck を呼び出す
        # 【期待される動作】: description が REMOVE され、updated_at が更新される
        # 🔵 信頼性レベル: 青信号 - architecture.md セクション2 使用例 4.1, 4.2 より
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: description 付きのデッキを作成
        # 【初期条件設定】: description="削除される説明" で create_deck を呼び出し
        created = service.create_deck(
            user_id="user-1",
            name="テストデッキ",
            description="削除される説明",
        )
        original_updated_at = created.updated_at

        # 【実際の処理実行】: description=None のみ渡して update_deck を呼び出す
        # 【処理内容】: REMOVE のみの UpdateExpression + SET updated_at の組み合わせ
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            description=None,  # REMOVE のみ
        )

        # 【結果検証】: updated_at が更新されていること
        assert updated.updated_at is not None  # 【確認内容】: updated_at が None でないこと 🔵

        # 【DynamoDB 確認】: DynamoDB 上での updated_at を確認
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert "updated_at" in item            # 【確認内容】: DynamoDB 上に updated_at が存在すること 🔵
        assert "description" not in item       # 【確認内容】: description が REMOVE されていること 🔵

    def test_tc017_name_unset_description_set(self, dynamodb_tables_with_deck):
        """TC-017: name 省略 + description SET の組み合わせ.

        # 【テスト目的】: name は必須フィールドだが _UNSET で省略可能、description は SET するケース
        # 【テスト内容】: name なし、description="新しい説明" で update_deck を呼び出す
        # 【期待される動作】: name は変更されず、description のみ SET される
        # 🔵 信頼性レベル: 青信号 - 要件定義 3.2 + card_service.py パターンより
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: デッキを作成
        # 【初期条件設定】: name "必須フィールドテスト" でデッキを作成
        created = service.create_deck(user_id="user-1", name="必須フィールドテスト")

        # 【実際の処理実行】: name を省略して description のみ SET する
        # 【処理内容】: name は _UNSET のため ExpressionAttributeNames に #name が含まれない
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            # name は渡さない → _UNSET
            description="新しい説明",
        )

        # 【結果検証】: name が変更されず、description が SET されていること
        assert updated.name == "必須フィールドテスト"  # 【確認内容】: name が変更されていないこと 🔵
        assert updated.description == "新しい説明"    # 【確認内容】: description が SET されていること 🔵

        # 【DynamoDB 確認】: DynamoDB 上での状態を確認
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["name"] == "必須フィールドテスト"   # 【確認内容】: DynamoDB 上で name が変更されていないこと 🔵
        assert item["description"] == "新しい説明"     # 【確認内容】: DynamoDB 上で description が SET されていること 🔵

    def test_tc018_all_fields_set_backward_compat(self, dynamodb_tables_with_deck):
        """TC-018: name + description + color 全フィールド SET（従来動作の互換性確認）.

        # 【テスト目的】: 全フィールドに値を渡す「最大構成」のケース（後方互換性確認）
        # 【テスト内容】: name, description, color 全て値を渡して update_deck を呼び出す
        # 【期待される動作】: 全フィールドが更新され、REMOVE は含まれない（従来動作と同等）
        # 🔵 信頼性レベル: 青信号 - 既存テスト test_update_multiple_fields と同一パターン
        """
        service, table = dynamodb_tables_with_deck

        # 【テストデータ準備】: デッキを作成
        # 【初期条件設定】: 全フィールドを持つデッキを用意
        created = service.create_deck(
            user_id="user-1",
            name="旧名前",
            description="旧説明",
            color="#FF0000",
        )

        # 【実際の処理実行】: 全フィールドに値を渡して update_deck を呼び出す
        # 【処理内容】: Sentinel 導入前と同じ呼び出しパターン（SET のみ、REMOVE なし）
        updated = service.update_deck(
            user_id="user-1",
            deck_id=created.deck_id,
            name="新名前",
            description="新説明",
            color="#0000FF",
        )

        # 【結果検証】: 全フィールドが更新されていること
        assert updated.name == "新名前"        # 【確認内容】: name が "新名前" に SET されていること 🔵
        assert updated.description == "新説明"  # 【確認内容】: description が "新説明" に SET されていること 🔵
        assert updated.color == "#0000FF"      # 【確認内容】: color が "#0000FF" に SET されていること 🔵

        # 【DynamoDB 確認】: DynamoDB 上での全フィールドを確認
        item = table.get_item(Key={"user_id": "user-1", "deck_id": created.deck_id})["Item"]
        assert item["name"] == "新名前"         # 【確認内容】: DynamoDB 上で name が SET されていること 🔵
        assert item["description"] == "新説明"   # 【確認内容】: DynamoDB 上で description が SET されていること 🔵
        assert item["color"] == "#0000FF"       # 【確認内容】: DynamoDB 上で color が SET されていること 🔵

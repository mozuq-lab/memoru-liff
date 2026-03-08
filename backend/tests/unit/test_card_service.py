"""Unit tests for card service."""

import pytest
from moto import mock_aws
import boto3
from datetime import datetime, timedelta, timezone

from services.card_service import (
    CardService,
    CardNotFoundError,
    CardLimitExceededError,
    CardServiceError,
)
from models.card import Reference


@pytest.fixture
def dynamodb_table():
    """Create mock DynamoDB tables (cards, users, reviews)."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

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

        # Create users table
        users_table = dynamodb.create_table(
            TableName="memoru-users-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        users_table.wait_until_exists()

        # Create reviews table (needed for TC-05 transactional delete)
        reviews_table = dynamodb.create_table(
            TableName="memoru-reviews-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "card_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "card_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        reviews_table.wait_until_exists()

        yield dynamodb


@pytest.fixture
def card_service(dynamodb_table):
    """Create CardService with mock DynamoDB.

    moto 5.x の transact_write_items は基本的な Put/Delete をサポートするが、
    ConditionExpression 内の if_not_exists() を正しく評価できないバグがある
    (ValueError: Bad comparison で失敗する)。
    そのため create_card のカード数上限チェック等を含むトランザクションは
    カスタムモックでシミュレートしている。

    Risk: このモックは DynamoDB のトランザクション分離レベルやコンフリクト検知を
    再現できないため、並行書き込みの競合条件はテストできない。

    TODO: DynamoDB Local への移行を検討する。DynamoDB Local は完全な
    transact_write_items をサポートしており、ConditionExpression の評価も正確に行える。
    """
    service = CardService(
        table_name="memoru-cards-test",
        users_table_name="memoru-users-test",
        reviews_table_name="memoru-reviews-test",
        dynamodb_resource=dynamodb_table,
    )

    # Mock transact_write_items since moto has bugs with it
    # This simulates the transaction behavior for tests
    users_table = dynamodb_table.Table("memoru-users-test")
    cards_table = dynamodb_table.Table("memoru-cards-test")
    reviews_table = dynamodb_table.Table("memoru-reviews-test")

    def mock_transact_write_items(TransactItems, **kwargs):
        from boto3.dynamodb.types import TypeDeserializer
        from botocore.exceptions import ClientError

        deserializer = TypeDeserializer()

        # Process each transaction item
        for item in TransactItems:
            if 'Update' in item:
                update = item['Update']
                table_name = update['TableName']
                table = users_table if 'users' in table_name else cards_table

                # Get key dict first
                key_dict = {k: deserializer.deserialize(v) for k, v in update['Key'].items()}

                # Ensure user exists with card_count initialized
                if 'users' in table_name:
                    try:
                        response = table.get_item(Key=key_dict)
                        if 'Item' not in response:
                            # Initialize user with card_count = 0
                            table.put_item(Item={**key_dict, 'card_count': 0})
                    except Exception:
                        pass

                # Check condition if present
                if 'ConditionExpression' in update:
                    # Get current item
                    response = table.get_item(Key=key_dict)
                    current_item = response.get('Item', {})
                    expr_values = update.get('ExpressionAttributeValues', {})
                    card_count = int(current_item.get('card_count', 0))

                    # Simulate if_not_exists(card_count, :zero) < :limit
                    if ':limit' in expr_values:
                        limit = int(expr_values[':limit']['N'])
                        if not (card_count < limit):
                            raise ClientError(
                                {
                                    "Error": {
                                        "Code": "TransactionCanceledException",
                                        "Message": "Transaction cancelled",
                                    },
                                    "CancellationReasons": [{"Code": "ConditionalCheckFailed"}],
                                },
                                "TransactWriteItems",
                            )

                # Perform update
                # Build expression values, excluding unused ones
                all_expr_values = {k: deserializer.deserialize(v) for k, v in update.get('ExpressionAttributeValues', {}).items()}
                update_expr = update['UpdateExpression']

                # Only include expression values that are used in UpdateExpression
                used_values = {}
                for key in all_expr_values:
                    if key in update_expr:
                        used_values[key] = all_expr_values[key]

                if used_values:
                    table.update_item(
                        Key=key_dict,
                        UpdateExpression=update_expr,
                        ExpressionAttributeValues=used_values,
                    )
                else:
                    table.update_item(
                        Key=key_dict,
                        UpdateExpression=update_expr,
                    )

            elif 'Put' in item:
                put = item['Put']
                table_name = put['TableName']
                table = cards_table if 'cards' in table_name else users_table

                # Deserialize and put item
                item_dict = {k: deserializer.deserialize(v) for k, v in put['Item'].items()}
                table.put_item(Item=item_dict)

            elif 'Delete' in item:
                # TC-05/TC-09: delete_card トランザクションの Delete 操作をサポート
                delete = item['Delete']
                table_name = delete['TableName']
                if 'cards' in table_name:
                    table = cards_table
                elif 'reviews' in table_name:
                    table = reviews_table
                else:
                    table = users_table

                key_dict = {k: deserializer.deserialize(v) for k, v in delete['Key'].items()}

                # ConditionExpression がある場合は条件チェック
                if 'ConditionExpression' in delete:
                    response = table.get_item(Key=key_dict)
                    if 'Item' not in response:
                        raise ClientError(
                            {
                                "Error": {
                                    "Code": "TransactionCanceledException",
                                    "Message": "Transaction cancelled",
                                },
                                "CancellationReasons": [
                                    {"Code": "ConditionalCheckFailed"}
                                ],
                            },
                            "TransactWriteItems",
                        )

                # Delete 実行
                table.delete_item(Key=key_dict)

        return {}

    service._client.transact_write_items = mock_transact_write_items
    return service


class TestCardServiceCreate:
    """Tests for CardService.create_card method."""

    def test_create_card_success(self, card_service):
        """Test creating a new card."""
        card = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
            tags=["test", "example"],
        )

        assert card.user_id == "test-user-id"
        assert card.front == "Question"
        assert card.back == "Answer"
        assert card.tags == ["test", "example"]
        assert card.card_id is not None
        assert card.next_review_at is not None

    def test_create_card_with_deck(self, card_service):
        """Test creating a card with deck_id."""
        card = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
            deck_id="deck-123",
        )

        assert card.deck_id == "deck-123"

    def test_create_card_default_values(self, card_service):
        """Test that default SRS values are set."""
        card = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
        )

        assert card.interval == 0
        assert card.ease_factor == 2.5
        assert card.repetitions == 0


class TestCardServiceGet:
    """Tests for CardService.get_card method."""

    def test_get_card_success(self, card_service):
        """Test getting an existing card."""
        # Create a card first
        created = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
        )

        # Get the card
        card = card_service.get_card("test-user-id", created.card_id)

        assert card.card_id == created.card_id
        assert card.front == "Question"
        assert card.back == "Answer"

    def test_get_card_not_found(self, card_service):
        """Test getting a non-existent card."""
        with pytest.raises(CardNotFoundError):
            card_service.get_card("test-user-id", "non-existent-card")


class TestCardServiceUpdate:
    """Tests for CardService.update_card method."""

    def test_update_card_front(self, card_service):
        """Test updating card front text."""
        created = card_service.create_card(
            user_id="test-user-id",
            front="Old Question",
            back="Answer",
        )

        updated = card_service.update_card(
            user_id="test-user-id",
            card_id=created.card_id,
            front="New Question",
        )

        assert updated.front == "New Question"
        assert updated.back == "Answer"  # Unchanged
        assert updated.updated_at is not None

    def test_update_card_back(self, card_service):
        """Test updating card back text."""
        created = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Old Answer",
        )

        updated = card_service.update_card(
            user_id="test-user-id",
            card_id=created.card_id,
            back="New Answer",
        )

        assert updated.back == "New Answer"
        assert updated.front == "Question"  # Unchanged

    def test_update_card_tags(self, card_service):
        """Test updating card tags."""
        created = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
            tags=["old-tag"],
        )

        updated = card_service.update_card(
            user_id="test-user-id",
            card_id=created.card_id,
            tags=["new-tag-1", "new-tag-2"],
        )

        assert updated.tags == ["new-tag-1", "new-tag-2"]

    def test_update_card_not_found(self, card_service):
        """Test updating a non-existent card."""
        with pytest.raises(CardNotFoundError):
            card_service.update_card(
                user_id="test-user-id",
                card_id="non-existent-card",
                front="New Question",
            )


class TestCardServiceDelete:
    """Tests for CardService.delete_card method."""

    def test_delete_card_success(self, card_service):
        """Test deleting an existing card."""
        created = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
        )

        card_service.delete_card("test-user-id", created.card_id)

        # Verify card is deleted
        with pytest.raises(CardNotFoundError):
            card_service.get_card("test-user-id", created.card_id)

    def test_delete_card_not_found(self, card_service):
        """Test deleting a non-existent card."""
        with pytest.raises(CardNotFoundError):
            card_service.delete_card("test-user-id", "non-existent-card")


class TestCardServiceList:
    """Tests for CardService.list_cards method."""

    def test_list_cards_empty(self, card_service):
        """Test listing cards when none exist."""
        cards, cursor = card_service.list_cards("test-user-id")

        assert cards == []
        assert cursor is None

    def test_list_cards_with_cards(self, card_service):
        """Test listing cards when cards exist."""
        # Create some cards
        for i in range(3):
            card_service.create_card(
                user_id="test-user-id",
                front=f"Question {i}",
                back=f"Answer {i}",
            )

        cards, cursor = card_service.list_cards("test-user-id")

        assert len(cards) == 3

    def test_list_cards_with_limit(self, card_service):
        """Test listing cards with limit."""
        # Create 5 cards
        for i in range(5):
            card_service.create_card(
                user_id="test-user-id",
                front=f"Question {i}",
                back=f"Answer {i}",
            )

        cards, cursor = card_service.list_cards("test-user-id", limit=2)

        assert len(cards) == 2
        assert cursor is not None

    def test_list_cards_by_deck(self, card_service):
        """Test listing cards filtered by deck."""
        # Create cards in different decks
        card_service.create_card(
            user_id="test-user-id",
            front="Q1",
            back="A1",
            deck_id="deck-1",
        )
        card_service.create_card(
            user_id="test-user-id",
            front="Q2",
            back="A2",
            deck_id="deck-2",
        )
        card_service.create_card(
            user_id="test-user-id",
            front="Q3",
            back="A3",
            deck_id="deck-1",
        )

        cards, _ = card_service.list_cards("test-user-id", deck_id="deck-1")

        assert len(cards) == 2
        for card in cards:
            assert card.deck_id == "deck-1"


class TestCardServiceDueCards:
    """Tests for CardService.get_due_cards method."""

    def test_get_due_cards(self, card_service, dynamodb_table):
        """Test getting cards due for review."""
        # Create a card that's due now
        now = datetime.now(timezone.utc)
        table = dynamodb_table.Table("memoru-cards-test")
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_id": "card-due",
                "front": "Due Question",
                "back": "Due Answer",
                "next_review_at": (now - timedelta(hours=1)).isoformat(),
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 1,
                "tags": [],
                "created_at": now.isoformat(),
            }
        )
        # Create a card that's not due yet
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_id": "card-not-due",
                "front": "Not Due Question",
                "back": "Not Due Answer",
                "next_review_at": (now + timedelta(days=1)).isoformat(),
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 1,
                "tags": [],
                "created_at": now.isoformat(),
            }
        )

        due_cards = card_service.get_due_cards("test-user-id")

        assert len(due_cards) == 1
        assert due_cards[0].card_id == "card-due"


class TestCardServiceUpdateReviewData:
    """Tests for CardService.update_review_data method."""

    def test_update_review_data(self, card_service):
        """Test updating review data after a review."""
        created = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
        )

        next_review = datetime.now(timezone.utc) + timedelta(days=3)
        updated = card_service.update_review_data(
            user_id="test-user-id",
            card_id=created.card_id,
            next_review_at=next_review,
            interval=3,
            ease_factor=2.6,
            repetitions=1,
        )

        assert updated.interval == 3
        assert updated.ease_factor == 2.6
        assert updated.repetitions == 1


class TestCardServiceRaceConditionPrevention:
    """Tests for race condition prevention in card creation (TASK-0035)."""

    def test_create_card_below_limit_succeeds(self, card_service, dynamodb_table, monkeypatch):
        """Test that card creation succeeds when card_count < 2000."""
        # Setup: Create user with card_count = 1999
        users_table = dynamodb_table.Table("memoru-users-test")
        users_table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_count": 1999,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
            }
        )

        # Mock transact_write_items to simulate successful transaction
        # (moto has bugs with transact_write_items, so we mock it)
        original_client = card_service._client

        def mock_transact_write_items(*args, **kwargs):
            # Simulate the transaction: update card_count and create card
            users_table.update_item(
                Key={"user_id": "test-user-id"},
                UpdateExpression="SET card_count = card_count + :inc",
                ExpressionAttributeValues={":inc": 1},
            )
            return {}

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact_write_items)

        # Should succeed (1999 < 2000)
        card = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
        )

        assert card.user_id == "test-user-id"
        assert card.front == "Question"
        assert card.back == "Answer"

        # Verify card_count was incremented
        user_item = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
        assert user_item["card_count"] == 2000

    def test_create_card_at_limit_fails(self, card_service, dynamodb_table, monkeypatch):
        """Test that card creation fails when card_count >= 2000."""
        from botocore.exceptions import ClientError

        # Setup: Create user with card_count = 2000 (at limit)
        users_table = dynamodb_table.Table("memoru-users-test")
        users_table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_count": 2000,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
            }
        )

        # Mock transact_write_items to raise TransactionCanceledException (condition failed)
        original_client = card_service._client

        def mock_transact_write_items(*args, **kwargs):
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    "CancellationReasons": [
                        {"Code": "ConditionalCheckFailed"}
                    ],
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact_write_items)

        # Should fail (2000 >= 2000)
        with pytest.raises(CardLimitExceededError) as exc_info:
            card_service.create_card(
                user_id="test-user-id",
                front="Question",
                back="Answer",
            )

        assert "2000" in str(exc_info.value)

        # Verify card_count was NOT incremented
        user_item = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
        assert user_item["card_count"] == 2000

    def test_create_card_over_limit_fails(self, card_service, dynamodb_table, monkeypatch):
        """Test that card creation fails when card_count > 2000."""
        from botocore.exceptions import ClientError

        # Setup: Create user with card_count = 2500 (over limit)
        users_table = dynamodb_table.Table("memoru-users-test")
        users_table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_count": 2500,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
            }
        )

        # Mock transact_write_items to raise TransactionCanceledException
        original_client = card_service._client

        def mock_transact_write_items(*args, **kwargs):
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    "CancellationReasons": [
                        {"Code": "ConditionalCheckFailed"}
                    ],
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact_write_items)

        # Should fail
        with pytest.raises(CardLimitExceededError):
            card_service.create_card(
                user_id="test-user-id",
                front="Question",
                back="Answer",
            )

    def test_transaction_canceled_exception_handling(self, card_service, dynamodb_table, monkeypatch):
        """Test that TransactionCanceledException is properly handled and converted to CardLimitExceededError."""
        from botocore.exceptions import ClientError

        # Setup: Create user with card_count = 1999
        users_table = dynamodb_table.Table("memoru-users-test")
        users_table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_count": 1999,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
            }
        )

        # Mock transact_write_items to raise TransactionCanceledException
        original_client = card_service._client

        def mock_transact_write_items(*args, **kwargs):
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled, please refer cancellation reasons for specific reasons",
                    },
                    "CancellationReasons": [
                        {"Code": "ConditionalCheckFailed", "Message": "The conditional request failed"}
                    ],
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact_write_items)

        # Should convert TransactionCanceledException to CardLimitExceededError
        with pytest.raises(CardLimitExceededError) as exc_info:
            card_service.create_card(
                user_id="test-user-id",
                front="Question",
                back="Answer",
            )

        assert "limit" in str(exc_info.value).lower()


# =============================================================================
# TASK-0043: card_count Transaction Fixes - Red Phase Tests
# =============================================================================


class TestCardCountIfNotExists:
    """Tests for if_not_exists safety in card creation (Fix 1).

    【テストクラス目的】: card_countアトリビュートが存在しないユーザーレコードに対して
    カード作成が成功することを検証する。
    現在の実装では 'SET card_count = card_count + :inc' を使用しているが、
    'SET card_count = if_not_exists(card_count, :zero) + :inc' に修正が必要。
    """

    def test_create_card_with_missing_card_count(self, card_service, dynamodb_table):
        """TC-01: card_count属性がないユーザーレコードでカード作成が成功することを確認する。

        【テスト目的】: card_count属性が存在しないユーザーレコードでも
        if_not_exists を使用してカード作成が成功することを検証する。
        🔵 信頼性レベル: 青信号 - CR-02で card_service.py L112 の問題が特定されている。

        Given: card_count属性を持たないユーザーレコードが存在する
        When: そのユーザーでcard_service.create_card()を呼び出す
        Then: カードが作成され、card_count が 1 に初期化される

        Maps to: AC-001, AC-002, EARS-001, EARS-002, EARS-003, EARS-004
        """
        # 【テストデータ準備】: card_count属性のないユーザーレコードをDynamoDBに作成する
        # 新規ユーザーはget_or_create_userで作成されるが、to_dynamodb_item()はcard_countを含まない
        users_table = dynamodb_table.Table("memoru-users-test")
        users_table.put_item(
            Item={
                "user_id": "test-user-no-count",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                # NOTE: card_count属性は意図的に省略している
            }
        )

        # 【実際の処理実行】: card_count属性がないユーザーでカードを作成する
        card = card_service.create_card(
            user_id="test-user-no-count",
            front="Question 1",
            back="Answer 1",
        )

        # 【結果検証】: カードが正常に作成されたことを確認する
        assert card.card_id is not None  # 【確認内容】: card_idが割り当てられている 🔵
        assert card.user_id == "test-user-no-count"  # 【確認内容】: 正しいuser_idが設定されている 🔵
        assert card.front == "Question 1"  # 【確認内容】: frontテキストが正しく保存されている 🔵
        assert card.back == "Answer 1"  # 【確認内容】: backテキストが正しく保存されている 🔵

        # 【結果検証】: card_countが1に初期化されたことを確認する
        # 現在の実装では 'card_count + :inc' がcard_countなしで失敗するため、このアサーションは失敗する
        user = users_table.get_item(Key={"user_id": "test-user-no-count"})["Item"]
        assert user["card_count"] == 1  # 【確認内容】: if_not_existsで0として扱われ1にインクリメントされる 🔵


class TestTransactionErrorClassification:
    """Tests for TransactionCanceledException error classification (Fix 2).

    【テストクラス目的】: TransactionCanceledExceptionのCancellationReasonsを正しく解析し、
    CardLimitExceededError と InternalError を適切に区別することを検証する。
    現在の実装は全てのTransactionCanceledExceptionをCardLimitExceededErrorとして扱う問題がある。
    """

    def test_conditional_check_failed_raises_limit_error(self, card_service, monkeypatch):
        """TC-02: CancellationReasons[0].Code == 'ConditionalCheckFailed' で CardLimitExceededError が発生する。

        【テスト目的】: TransactionCanceledExceptionのCancellationReasons[0]が
        'ConditionalCheckFailed'の場合にCardLimitExceededErrorが発生することを検証する。
        🔵 信頼性レベル: 青信号 - TransactItems[0]はUsers テーブルのUpdateでcard_count条件チェックを行う。

        Given: transact_write_itemsがCancellationReasons[0].Code == 'ConditionalCheckFailed'の
               TransactionCanceledExceptionを発生させる
        When: create_card を呼び出す
        Then: CardLimitExceededError が発生する

        Maps to: AC-006, EARS-006
        """
        from botocore.exceptions import ClientError

        # 【テストデータ準備】: CardLimit超過を模擬するモックを設定する
        original_client = card_service._client

        def mock_transact(*args, **kwargs):
            # 【処理内容】: card_count >= 2000 のConditionalCheckFailed を模擬する
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    "CancellationReasons": [
                        {"Code": "ConditionalCheckFailed", "Message": "The conditional request failed"},
                    ],
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

        # 【実際の処理実行】: CardLimit超過状態でcreate_cardを呼び出す
        with pytest.raises(CardLimitExceededError) as exc_info:
            card_service.create_card(
                user_id="test-user-id",
                front="Question",
                back="Answer",
            )

        # 【結果検証】: エラーメッセージにカード上限数が含まれていることを確認する
        assert "2000" in str(exc_info.value)  # 【確認内容】: エラーメッセージに上限数2000が含まれる 🔵

    def test_non_conditional_raises_internal_error(self, card_service, monkeypatch):
        """TC-03: CancellationReasons[0].Code が 'ConditionalCheckFailed' 以外の場合 InternalError が発生する。

        【テスト目的】: TransactionCanceledExceptionのCancellationReasons[0]が
        'ConditionalCheckFailed'以外のコードの場合にInternalErrorが発生することを検証する。
        🔵 信頼性レベル: 青信号 - 他のエラーコードはカード上限超過として報告されるべきでない。

        Given: transact_write_itemsがCancellationReasons[0].Code == 'ValidationError'の
               TransactionCanceledExceptionを発生させる
        When: create_card を呼び出す
        Then: InternalError が発生する (CardLimitExceededError ではない)

        Maps to: AC-007, AC-010, EARS-007, EARS-009
        """
        from botocore.exceptions import ClientError

        # NOTE: InternalError クラスは現在の card_service.py に存在しない
        # このテストは InternalError が追加されるまで ImportError で失敗する
        from services.card_service import InternalError  # noqa: F401

        original_client = card_service._client

        def mock_transact(*args, **kwargs):
            # 【処理内容】: ValidationError (非ConditionalCheckFailed) を模擬する
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    "CancellationReasons": [
                        {"Code": "ValidationError", "Message": "Validation error on expression"},
                    ],
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

        # 【実際の処理実行】: 非ConditionalCheckFailedエラーでcreate_cardを呼び出す
        # 【期待される動作】: InternalError が発生し、CardLimitExceededError は発生しない
        with pytest.raises(InternalError):  # 【確認内容】: CardLimitExceededErrorではなくInternalErrorが発生 🔵
            card_service.create_card(
                user_id="test-user-id",
                front="Question",
                back="Answer",
            )

    def test_missing_cancellation_reasons_raises_internal(self, card_service, monkeypatch):
        """TC-04a: CancellationReasons キーが存在しない場合 InternalError が発生する。

        【テスト目的】: TransactionCanceledExceptionにCancellationReasons キーが全くない場合に
        InternalErrorが発生することを検証する。
        🟡 信頼性レベル: 黄信号 - DynamoDB APIドキュメントに基づく推測。

        Given: transact_write_itemsがCancellationReasons キーなしの
               TransactionCanceledExceptionを発生させる
        When: create_card を呼び出す
        Then: InternalError が発生する

        Maps to: AC-008, EARS-008
        """
        from botocore.exceptions import ClientError
        from services.card_service import InternalError  # noqa: F401

        original_client = card_service._client

        def mock_transact(*args, **kwargs):
            # 【処理内容】: CancellationReasons キーなしのTransactionCanceledExceptionを模擬する
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    # NOTE: CancellationReasons キーが意図的に省略されている
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

        # 【実際の処理実行】: CancellationReasons なしのエラーでcreate_cardを呼び出す
        with pytest.raises(InternalError):  # 【確認内容】: CancellationReasons欠如でInternalErrorが発生 🟡
            card_service.create_card(
                user_id="test-user-id",
                front="Question",
                back="Answer",
            )

    def test_empty_cancellation_reasons_raises_internal(self, card_service, monkeypatch):
        """TC-04b: CancellationReasons が空リストの場合 InternalError が発生する。

        【テスト目的】: TransactionCanceledExceptionのCancellationReasons が空リスト []
        の場合にInternalErrorが発生することを検証する。
        空リストはfalsyであり、TC-04aと同じコードパスを通る。
        🟡 信頼性レベル: 黄信号 - 空リストの処理は実装依存。

        Given: transact_write_itemsがCancellationReasons = [] の
               TransactionCanceledExceptionを発生させる
        When: create_card を呼び出す
        Then: InternalError が発生する

        Maps to: AC-008, EARS-008
        """
        from botocore.exceptions import ClientError
        from services.card_service import InternalError  # noqa: F401

        original_client = card_service._client

        def mock_transact(*args, **kwargs):
            # 【処理内容】: CancellationReasons が空リストのTransactionCanceledExceptionを模擬する
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    "CancellationReasons": [],  # 【初期条件設定】: 空リスト (falsy)
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

        # 【実際の処理実行】: CancellationReasons が空リストのエラーでcreate_cardを呼び出す
        with pytest.raises(InternalError):  # 【確認内容】: 空リストのCancellationReasonsでInternalErrorが発生 🟡
            card_service.create_card(
                user_id="test-user-id",
                front="Question",
                back="Answer",
            )


class TestDeleteCardTransaction:
    """Tests for transactional card deletion with card_count decrement (Fix 3).

    【テストクラス目的】: delete_card が transact_write_items を使って
    Cards削除・Reviews削除・card_countデクリメントをアトミックに実行することを検証する。
    現在の実装は単純な delete_item を使用しており、card_count が更新されない問題がある。
    """

    def test_delete_card_decrements_card_count(self, card_service, dynamodb_table):
        """TC-05: カードを削除するとcard_countがアトミックにデクリメントされる。

        【テスト目的】: delete_card が transact_write_items を使って
        card_count を 1 デクリメントすることを検証する。
        🔵 信頼性レベル: 青信号 - CR-02で delete_card の非トランザクション実装が確認されている。

        Given: card_count = 5 のユーザーが存在し、1枚のカードがある
        When: カードを削除する
        Then: card_count が 1 デクリメントされる

        Maps to: AC-011, AC-012, EARS-010
        """
        users_table = dynamodb_table.Table("memoru-users-test")

        # 【テストデータ準備】: card_count = 5 のユーザーをセットアップする
        users_table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_count": 5,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
            }
        )

        # 【初期条件設定】: カードを作成する (card_count が 5 → 6 になる)
        card = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
        )

        # カード作成後のcard_count確認
        user_before = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
        assert user_before["card_count"] == 6  # 【確認内容】: カード作成でcard_countが6になっている 🔵

        # 【実際の処理実行】: カードを削除する
        card_service.delete_card("test-user-id", card.card_id)

        # 【結果検証】: card_count が 5 (= 6 - 1) になったことを確認する
        # 現在の実装では delete_card が transact_write_items を使わないため、このアサーションは失敗する
        user_after = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
        assert user_after["card_count"] == 5  # 【確認内容】: デクリメントでcard_countが5に戻っている 🔵

        # 【結果検証】: カードが削除されたことを確認する
        with pytest.raises(CardNotFoundError):
            card_service.get_card("test-user-id", card.card_id)  # 【確認内容】: カードが削除されている 🔵

    def test_delete_card_race_condition_not_found(self, card_service, monkeypatch):
        """TC-06a: 並行削除のレースコンディションで CardNotFoundError が発生する。

        【テスト目的】: 別リクエストによるカード削除後に delete_card を呼び出した場合、
        CancellationReasons[0].Code == 'ConditionalCheckFailed' により
        CardNotFoundError が発生することを検証する。
        🔵 信頼性レベル: 青信号 - TransactItems[0]でattribute_exists(card_id)条件チェックを行う。

        Given: カードは確認時点では存在するが、トランザクション前に削除される (レースコンディション)
        When: delete_card を呼び出す
        Then: CardNotFoundError が発生する

        Maps to: AC-016, EARS-012
        """
        from botocore.exceptions import ClientError
        from models.card import Card

        # 【テストデータ準備】: カードが存在することを模擬する (get_card成功)
        mock_card = Card(
            user_id="test-user-id",
            front="Q",
            back="A",
            created_at=datetime.now(timezone.utc),
            next_review_at=datetime.now(timezone.utc),
        )
        monkeypatch.setattr(card_service, "get_card", lambda uid, cid: mock_card)

        # 【初期条件設定】: transact_write_items がカードが既に削除された状態を模擬する
        original_client = card_service._client

        def mock_transact(*args, **kwargs):
            # 【処理内容】: Index 0 (Cards Delete) でConditionalCheckFailed (レースコンディション)
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    "CancellationReasons": [
                        {"Code": "ConditionalCheckFailed", "Message": "Card does not exist"},  # Index 0: Cards Delete
                        {"Code": "None"},   # Index 1: Users Update
                    ],
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

        # 【実際の処理実行】: 既に削除されたカードに対してdelete_cardを呼び出す
        # 現在の実装では transact_write_items を使わないため、このテストは失敗する
        with pytest.raises(CardNotFoundError):  # 【確認内容】: レースコンディションでCardNotFoundError 🔵
            card_service.delete_card("test-user-id", "card-already-deleted")

    def test_delete_card_prevents_negative_count(self, card_service, monkeypatch):
        """TC-06b: card_count = 0 でのカード削除はCardServiceErrorを発生させる。

        【テスト目的】: card_count が既に 0 の状態でカード削除を試みた場合、
        CancellationReasons[2].Code == 'ConditionalCheckFailed' により
        CardServiceError が発生することを検証する。
        🟡 信頼性レベル: 黄信号 - データ整合性のドリフトにより発生するエッジケース。

        Given: ユーザーのcard_count = 0 だが、カードは存在する (データ整合性のドリフト)
        When: delete_card を呼び出す
        Then: CardServiceError が発生し、card_countが0を下回らない

        Maps to: AC-013, EARS-013, EARS-014
        """
        from botocore.exceptions import ClientError
        from models.card import Card

        # 【テストデータ準備】: カードが存在することを模擬する
        mock_card = Card(
            user_id="test-user-id",
            front="Q",
            back="A",
            created_at=datetime.now(timezone.utc),
            next_review_at=datetime.now(timezone.utc),
        )
        monkeypatch.setattr(card_service, "get_card", lambda uid, cid: mock_card)

        # 【初期条件設定】: card_count = 0 の条件チェック失敗を模擬する
        original_client = card_service._client

        def mock_transact(*args, **kwargs):
            # 【処理内容】: Index 1 (Users Update) でConditionalCheckFailed (card_count > 0 が偽)
            raise ClientError(
                {
                    "Error": {
                        "Code": "TransactionCanceledException",
                        "Message": "Transaction cancelled",
                    },
                    "CancellationReasons": [
                        {"Code": "None"},                       # Index 0: Cards Delete OK
                        {"Code": "ConditionalCheckFailed"},     # Index 1: card_count > :zero 条件失敗
                    ],
                },
                "TransactWriteItems",
            )

        monkeypatch.setattr(original_client, "transact_write_items", mock_transact)

        # 【実際の処理実行】: card_count = 0 の状態でdelete_cardを呼び出す
        # 現在の実装では transact_write_items を使わないため、このテストは失敗する
        with pytest.raises(CardServiceError) as exc_info:  # 【確認内容】: CardServiceErrorが発生する 🟡
            card_service.delete_card("test-user-id", "card-with-zero-count")

        # 【結果検証】: エラーメッセージにcard_countが含まれることを確認する
        assert "card_count" in str(exc_info.value).lower()  # 【確認内容】: エラーメッセージにcard_countが含まれる 🟡


class TestCardCountEndToEnd:
    """Integration tests for card_count consistency (Fix 1 + Fix 3).

    【テストクラス目的】: カード作成と削除のライフサイクルを通じてcard_countが
    正確に管理されることを統合的に検証する。
    """

    def test_create_delete_card_count_consistency(self, card_service, dynamodb_table):
        """TC-09: カードの作成と削除を通じてcard_countが一貫して管理される。

        【テスト目的】: 3枚のカード作成後に2枚削除した場合に
        card_count が正確に管理されることを検証する統合テスト。
        🔵 信頼性レベル: 青信号 - Fix 1 (if_not_exists) と Fix 3 (トランザクション削除) の組み合わせ。

        Given: card_count属性のないユーザー (新規ユーザーを模擬)
        When: 3枚のカードを作成し、2枚を削除する
        Then: 各ステップでcard_countが正確に反映されている

        Steps:
          1. 3枚のカード作成 → card_count == 3
          2. 1枚目のカード削除 → card_count == 2
          3. 2枚目のカード削除 → card_count == 1

        Maps to: AC-021, AC-022, AC-023
        """
        users_table = dynamodb_table.Table("memoru-users-test")

        # 【テストデータ準備】: 3枚のカードを作成する (card_count属性なしから始まる)
        cards = []
        for i in range(3):
            card = card_service.create_card(
                user_id="test-user-id",
                front=f"Question {i}",
                back=f"Answer {i}",
            )
            cards.append(card)

        # 【結果検証】: 3枚作成後 card_count == 3
        user = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
        assert user["card_count"] == 3  # 【確認内容】: 3枚作成後card_countが3になっている 🔵

        # 【実際の処理実行】: 1枚目のカードを削除する
        # 現在の実装では card_count がデクリメントされないため以降のアサーションが失敗する
        card_service.delete_card("test-user-id", cards[0].card_id)

        # 【結果検証】: 1枚削除後 card_count == 2
        user = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
        assert user["card_count"] == 2  # 【確認内容】: 1枚削除後card_countが2になっている 🔵

        # 【実際の処理実行】: 2枚目のカードを削除する
        card_service.delete_card("test-user-id", cards[1].card_id)

        # 【結果検証】: 2枚削除後 card_count == 1
        user = users_table.get_item(Key={"user_id": "test-user-id"})["Item"]
        assert user["card_count"] == 1  # 【確認内容】: 2枚削除後card_countが1になっている 🔵

        # 【結果検証】: 残りのカードがまだアクセス可能であることを確認する
        remaining = card_service.get_card("test-user-id", cards[2].card_id)
        assert remaining.card_id == cards[2].card_id  # 【確認内容】: 3枚目のカードがまだ存在する 🔵


class TestGetDueCardsPagination:
    """Tests for get_due_cards pagination when limit=None (TASK-0109)."""

    def test_pagination_collects_all_pages(self, card_service, monkeypatch):
        """limit=None の場合、LastEvaluatedKey を追って全ページを収集する。"""
        from models.card import Card

        now = datetime.now(timezone.utc)
        item1 = {
            "user_id": "u1", "card_id": "c1", "front": "Q1", "back": "A1",
            "next_review_at": now.isoformat(), "interval": 1, "ease_factor": "2.5",
            "repetitions": 0, "tags": [], "created_at": now.isoformat(),
        }
        item2 = {
            "user_id": "u1", "card_id": "c2", "front": "Q2", "back": "A2",
            "next_review_at": now.isoformat(), "interval": 1, "ease_factor": "2.5",
            "repetitions": 0, "tags": [], "created_at": now.isoformat(),
        }

        call_count = 0

        def mock_query(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"Items": [item1], "LastEvaluatedKey": {"pk": "dummy"}}
            else:
                return {"Items": [item2]}

        monkeypatch.setattr(card_service.table, "query", mock_query)

        result = card_service.get_due_cards("u1", limit=None)

        assert call_count == 2
        assert len(result) == 2
        assert result[0].card_id == "c1"
        assert result[1].card_id == "c2"

    def test_pagination_passes_exclusive_start_key(self, card_service, monkeypatch):
        """2 ページ目のクエリに ExclusiveStartKey が含まれることを確認する。"""
        captured_kwargs = []

        now = datetime.now(timezone.utc)
        item = {
            "user_id": "u1", "card_id": "c1", "front": "Q", "back": "A",
            "next_review_at": now.isoformat(), "interval": 1, "ease_factor": "2.5",
            "repetitions": 0, "tags": [], "created_at": now.isoformat(),
        }
        call_count = 0

        def mock_query(**kwargs):
            nonlocal call_count
            captured_kwargs.append(kwargs)
            call_count += 1
            if call_count == 1:
                return {"Items": [item], "LastEvaluatedKey": {"pk": "key1"}}
            else:
                return {"Items": []}

        monkeypatch.setattr(card_service.table, "query", mock_query)

        card_service.get_due_cards("u1", limit=None)

        assert "ExclusiveStartKey" not in captured_kwargs[0]
        assert captured_kwargs[1]["ExclusiveStartKey"] == {"pk": "key1"}

    def test_limit_specified_does_not_paginate(self, card_service, monkeypatch):
        """limit が指定されている場合、ページネーションせず 1 回のクエリで返す。"""
        now = datetime.now(timezone.utc)
        item = {
            "user_id": "u1", "card_id": "c1", "front": "Q", "back": "A",
            "next_review_at": now.isoformat(), "interval": 1, "ease_factor": "2.5",
            "repetitions": 0, "tags": [], "created_at": now.isoformat(),
        }
        call_count = 0

        def mock_query(**kwargs):
            nonlocal call_count
            call_count += 1
            # Return LastEvaluatedKey even though limit is set
            return {"Items": [item], "LastEvaluatedKey": {"pk": "dummy"}}

        monkeypatch.setattr(card_service.table, "query", mock_query)

        result = card_service.get_due_cards("u1", limit=5)

        assert call_count == 1
        assert len(result) == 1


class TestDeleteCardReviewCleanup:
    """Tests for review deletion pagination and logging in delete_card (TASK-0109)."""

    def test_review_deletion_paginates(self, card_service, dynamodb_table, monkeypatch):
        """レビュー削除がページネーションで全件削除することを確認する。"""
        from models.card import Card

        mock_card = Card(
            user_id="test-user-id", front="Q", back="A",
            created_at=datetime.now(timezone.utc),
            next_review_at=datetime.now(timezone.utc),
        )
        monkeypatch.setattr(card_service, "get_card", lambda uid, cid: mock_card)

        # Mock transact_write_items to succeed (card deletion transaction)
        monkeypatch.setattr(card_service._client, "transact_write_items", lambda **kw: None)

        reviews_table = dynamodb_table.Table("memoru-reviews-test")
        deleted_keys = []
        query_call_count = 0

        def mock_reviews_query(**kwargs):
            nonlocal query_call_count
            query_call_count += 1
            if query_call_count == 1:
                return {
                    "Items": [
                        {"card_id": "c1", "reviewed_at": "2024-01-01T00:00:00"},
                        {"card_id": "c1", "reviewed_at": "2024-01-02T00:00:00"},
                    ],
                    "LastEvaluatedKey": {"card_id": "c1", "reviewed_at": "2024-01-02T00:00:00"},
                }
            else:
                return {
                    "Items": [
                        {"card_id": "c1", "reviewed_at": "2024-01-03T00:00:00"},
                    ],
                }

        monkeypatch.setattr(reviews_table, "query", mock_reviews_query)

        class MockBatchWriter:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def delete_item(self, Key):
                deleted_keys.append(Key)

        monkeypatch.setattr(reviews_table, "batch_writer", lambda: MockBatchWriter())

        # Override dynamodb.Table to return our patched reviews_table
        original_table_fn = card_service.dynamodb.Table

        def patched_table(name):
            if name == card_service.reviews_table_name:
                return reviews_table
            return original_table_fn(name)

        monkeypatch.setattr(card_service.dynamodb, "Table", patched_table)

        card_service.delete_card("test-user-id", "c1")

        assert query_call_count == 2
        assert len(deleted_keys) == 3

    def test_review_deletion_failure_logs_warning(self, card_service, monkeypatch):
        """レビュー削除失敗時に logger.warning が呼ばれることを確認する。"""
        from unittest.mock import patch
        from models.card import Card

        mock_card = Card(
            user_id="test-user-id", front="Q", back="A",
            created_at=datetime.now(timezone.utc),
            next_review_at=datetime.now(timezone.utc),
        )
        monkeypatch.setattr(card_service, "get_card", lambda uid, cid: mock_card)

        # Mock transact_write_items to succeed (card deletion transaction)
        monkeypatch.setattr(card_service._client, "transact_write_items", lambda **kw: None)

        # Make Table() raise for reviews table
        original_table_fn = card_service.dynamodb.Table

        def exploding_table(name):
            if name == card_service.reviews_table_name:
                raise RuntimeError("DynamoDB connection error")
            return original_table_fn(name)

        monkeypatch.setattr(card_service.dynamodb, "Table", exploding_table)

        with patch("services.card_service.logger") as mock_logger:
            card_service.delete_card("test-user-id", "some-card")

            # C-5: エラーハンドリング強化により、レビュー削除失敗は logger.error で記録される
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert "orphaned" in call_args[0][0].lower() or "failed" in call_args[0][0].lower()
            assert call_args[1]["extra"]["card_id"] == "some-card"


class TestCardServiceReferences:
    """Tests for CardService references support."""

    def test_create_card_with_references(self, card_service):
        """Test creating a card with references."""
        refs = [
            Reference(type="url", value="https://example.com"),
            Reference(type="book", value="Test Book p.42"),
        ]
        card = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
            references=refs,
        )

        assert len(card.references) == 2
        assert card.references[0].type == "url"
        assert card.references[0].value == "https://example.com"
        assert card.references[1].type == "book"
        assert card.references[1].value == "Test Book p.42"

        # Verify persisted to DynamoDB
        fetched = card_service.get_card("test-user-id", card.card_id)
        assert len(fetched.references) == 2
        assert fetched.references[0].type == "url"
        assert fetched.references[0].value == "https://example.com"

    def test_create_card_without_references(self, card_service):
        """Test creating a card without references defaults to empty list."""
        card = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
        )

        assert card.references == []

        # Verify persisted
        fetched = card_service.get_card("test-user-id", card.card_id)
        assert fetched.references == []

    def test_update_card_add_references(self, card_service):
        """Test adding references to a card that has none."""
        created = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
        )
        assert created.references == []

        refs = [Reference(type="url", value="https://example.com")]
        updated = card_service.update_card(
            user_id="test-user-id",
            card_id=created.card_id,
            references=refs,
        )

        assert len(updated.references) == 1
        assert updated.references[0].type == "url"
        assert updated.references[0].value == "https://example.com"

        # Verify persisted
        fetched = card_service.get_card("test-user-id", created.card_id)
        assert len(fetched.references) == 1
        assert fetched.references[0].value == "https://example.com"

    def test_update_card_replace_references(self, card_service):
        """Test replacing existing references."""
        refs_v1 = [Reference(type="url", value="https://old.com")]
        created = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
            references=refs_v1,
        )

        refs_v2 = [
            Reference(type="book", value="New Book"),
            Reference(type="note", value="My note"),
        ]
        updated = card_service.update_card(
            user_id="test-user-id",
            card_id=created.card_id,
            references=refs_v2,
        )

        assert len(updated.references) == 2
        assert updated.references[0].type == "book"
        assert updated.references[1].type == "note"

        # Verify persisted
        fetched = card_service.get_card("test-user-id", created.card_id)
        assert len(fetched.references) == 2

    def test_update_card_clear_references(self, card_service):
        """Test clearing references by passing empty list."""
        refs = [Reference(type="url", value="https://example.com")]
        created = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
            references=refs,
        )

        updated = card_service.update_card(
            user_id="test-user-id",
            card_id=created.card_id,
            references=[],
        )

        assert updated.references == []

        # Verify persisted
        fetched = card_service.get_card("test-user-id", created.card_id)
        assert fetched.references == []

    def test_update_card_references_none_preserves_existing(self, card_service):
        """Test that references=None (not provided) preserves existing references."""
        refs = [Reference(type="url", value="https://example.com")]
        created = card_service.create_card(
            user_id="test-user-id",
            front="Question",
            back="Answer",
            references=refs,
        )

        # Update only front, references not provided (None)
        updated = card_service.update_card(
            user_id="test-user-id",
            card_id=created.card_id,
            front="New Question",
        )

        assert updated.front == "New Question"
        assert len(updated.references) == 1
        assert updated.references[0].value == "https://example.com"

    def test_get_card_backward_compat_no_references_field(self, card_service):
        """Test that cards without references field in DynamoDB return empty list."""
        # Directly insert a card item without references field (simulating old data)
        cards_table = card_service.dynamodb.Table("memoru-cards-test")
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        cards_table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_id": "legacy-card-001",
                "front": "Old Question",
                "back": "Old Answer",
                "tags": [],
                "interval": 0,
                "ease_factor": "2.5",
                "repetitions": 0,
                "next_review_at": now.isoformat(),
                "created_at": now.isoformat(),
            }
        )

        card = card_service.get_card("test-user-id", "legacy-card-001")
        assert card.references == []
        assert card.front == "Old Question"

        # Verify to_response also returns empty list
        response = card.to_response()
        assert response.references == []

"""Unit tests for card service."""

import pytest
from moto import mock_aws
import boto3
from datetime import datetime, timedelta, timezone

from src.services.card_service import (
    CardService,
    CardNotFoundError,
    CardLimitExceededError,
)


@pytest.fixture
def dynamodb_table():
    """Create mock DynamoDB tables (cards and users)."""
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

        yield dynamodb


@pytest.fixture
def card_service(dynamodb_table):
    """Create CardService with mock DynamoDB."""
    service = CardService(
        table_name="memoru-cards-test",
        users_table_name="memoru-users-test",
        dynamodb_resource=dynamodb_table
    )

    # Mock transact_write_items since moto has bugs with it
    # This simulates the transaction behavior for tests
    original_method = service.dynamodb.meta.client.transact_write_items
    users_table = dynamodb_table.Table("memoru-users-test")
    cards_table = dynamodb_table.Table("memoru-cards-test")

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
                    try:
                        response = table.get_item(Key=key_dict)
                        current_item = response.get('Item', {})

                        # Evaluate condition (simplified for card_count < :limit)
                        if 'card_count' in current_item:
                            limit = int(update['ExpressionAttributeValues'][':limit']['N'])
                            if not (current_item['card_count'] < limit):
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
                    except KeyError:
                        pass  # Item doesn't exist yet

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

        return {}

    service.dynamodb.meta.client.transact_write_items = mock_transact_write_items
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
        original_client = card_service.dynamodb.meta.client

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
        original_client = card_service.dynamodb.meta.client

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
        original_client = card_service.dynamodb.meta.client

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
        original_client = card_service.dynamodb.meta.client

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

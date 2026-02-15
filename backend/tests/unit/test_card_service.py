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
    """Create a mock DynamoDB table."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        table = dynamodb.create_table(
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
        table.wait_until_exists()
        yield dynamodb


@pytest.fixture
def card_service(dynamodb_table):
    """Create CardService with mock DynamoDB."""
    return CardService(table_name="memoru-cards-test", dynamodb_resource=dynamodb_table)


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

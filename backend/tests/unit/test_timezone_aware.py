"""Tests for timezone-aware datetime usage."""

import pytest
from datetime import datetime, timezone
from moto import mock_aws
import boto3

from src.services.card_service import CardService
from src.services.user_service import UserService


@pytest.fixture
def dynamodb_resource():
    """Create a mock DynamoDB resource."""
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

        # Create users table
        users_table = dynamodb.create_table(
            TableName="memoru-users-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "line_user_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "line-user-index",
                    "KeySchema": [
                        {"AttributeName": "line_user_id", "KeyType": "HASH"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        cards_table.wait_until_exists()
        users_table.wait_until_exists()
        yield dynamodb


@pytest.fixture
def card_service(dynamodb_resource):
    """Create CardService with mock DynamoDB."""
    return CardService(table_name="memoru-cards-test", dynamodb_resource=dynamodb_resource)


@pytest.fixture
def user_service(dynamodb_resource):
    """Create UserService with mock DynamoDB."""
    return UserService(table_name="memoru-users-test", dynamodb_resource=dynamodb_resource)


class TestTimezoneAware:
    """Test that all datetime objects are timezone-aware."""

    def test_card_created_at_is_timezone_aware(self, card_service):
        """Test that created_at in Card is timezone-aware."""
        card = card_service.create_card(
            user_id="test-user",
            front="Front",
            back="Back",
        )

        # Assert that created_at has timezone info
        assert card.created_at.tzinfo is not None, "created_at should be timezone-aware"
        assert card.created_at.tzinfo == timezone.utc, "created_at should be in UTC"

    def test_card_next_review_at_is_timezone_aware(self, card_service):
        """Test that next_review_at in Card is timezone-aware."""
        card = card_service.create_card(
            user_id="test-user",
            front="Front",
            back="Back",
        )

        # Assert that next_review_at has timezone info
        assert card.next_review_at.tzinfo is not None, "next_review_at should be timezone-aware"
        assert card.next_review_at.tzinfo == timezone.utc, "next_review_at should be in UTC"

    def test_user_created_at_is_timezone_aware(self, user_service):
        """Test that created_at in User is timezone-aware."""
        user = user_service.create_user(
            user_id="test-user",
            display_name="Test User",
        )

        # Assert that created_at has timezone info
        assert user.created_at.tzinfo is not None, "created_at should be timezone-aware"
        assert user.created_at.tzinfo == timezone.utc, "created_at should be in UTC"

    def test_card_update_uses_timezone_aware(self, card_service):
        """Test that card updates use timezone-aware datetime."""
        card = card_service.create_card(
            user_id="test-user",
            front="Front",
            back="Back",
        )

        # Update the card
        updated_card = card_service.update_card(
            user_id=card.user_id,
            card_id=card.card_id,
            front="Updated Front",
        )

        # Assert that updated_at has timezone info (if set)
        if updated_card.updated_at is not None:
            assert updated_card.updated_at.tzinfo is not None
            assert updated_card.updated_at.tzinfo == timezone.utc

    def test_user_operations_use_timezone_aware(self, user_service):
        """Test that user operations use timezone-aware datetime."""
        # Create user
        user = user_service.create_user(user_id="test-user", display_name="Test User")

        # Retrieve user to verify operations work correctly
        retrieved_user = user_service.get_user("test-user")

        # User operations should work without timezone errors
        assert retrieved_user.user_id == "test-user"
        assert retrieved_user.created_at.tzinfo is not None
        assert retrieved_user.created_at.tzinfo == timezone.utc

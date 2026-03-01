"""Tests for Sentinel pattern in card_service.update_card deck_id handling."""

import os
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
import boto3
from moto import mock_aws

from services.card_service import CardService, _UNSET


@pytest.fixture
def dynamodb_setup():
    """Set up DynamoDB tables for testing."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

        # Create cards table
        dynamodb.create_table(
            TableName="test-cards",
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

        # Create users table
        dynamodb.create_table(
            TableName="test-users",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Create reviews table
        dynamodb.create_table(
            TableName="test-reviews",
            KeySchema=[
                {"AttributeName": "card_id", "KeyType": "HASH"},
                {"AttributeName": "reviewed_at", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "card_id", "AttributeType": "S"},
                {"AttributeName": "reviewed_at", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        service = CardService(
            table_name="test-cards",
            dynamodb_resource=dynamodb,
            users_table_name="test-users",
            reviews_table_name="test-reviews",
        )

        # Create a test user with card_count
        users_table = dynamodb.Table("test-users")
        users_table.put_item(Item={"user_id": "user-1", "card_count": 1})

        # Seed a card with deck_id
        cards_table = dynamodb.Table("test-cards")
        now = datetime.now(timezone.utc).isoformat()
        cards_table.put_item(
            Item={
                "user_id": "user-1",
                "card_id": "card-1",
                "front": "Q",
                "back": "A",
                "deck_id": "deck-old",
                "tags": [],
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "next_review_at": now,
                "created_at": now,
            }
        )

        yield service, cards_table


class TestSentinelPattern:
    """Sentinel パターンによる deck_id 処理テスト."""

    def test_deck_id_unset_no_change(self, dynamodb_setup):
        """deck_id が _UNSET（未送信）の場合、deck_id は変更されない."""
        service, table = dynamodb_setup

        # Update without providing deck_id (default _UNSET)
        card = service.update_card(
            user_id="user-1",
            card_id="card-1",
            front="Updated Q",
        )

        assert card.front == "Updated Q"
        assert card.deck_id == "deck-old"  # unchanged

        # Verify in DynamoDB
        item = table.get_item(Key={"user_id": "user-1", "card_id": "card-1"})["Item"]
        assert item["deck_id"] == "deck-old"

    def test_deck_id_none_removes_attribute(self, dynamodb_setup):
        """deck_id=None（明示的 null）の場合、DynamoDB から deck_id が REMOVE される."""
        service, table = dynamodb_setup

        card = service.update_card(
            user_id="user-1",
            card_id="card-1",
            deck_id=None,
        )

        assert card.deck_id is None

        # Verify deck_id is removed from DynamoDB
        item = table.get_item(Key={"user_id": "user-1", "card_id": "card-1"})["Item"]
        assert "deck_id" not in item

    def test_deck_id_value_sets_attribute(self, dynamodb_setup):
        """deck_id="new-deck"（値指定）の場合、deck_id が SET される."""
        service, table = dynamodb_setup

        card = service.update_card(
            user_id="user-1",
            card_id="card-1",
            deck_id="new-deck",
        )

        assert card.deck_id == "new-deck"

        # Verify in DynamoDB
        item = table.get_item(Key={"user_id": "user-1", "card_id": "card-1"})["Item"]
        assert item["deck_id"] == "new-deck"

    def test_deck_id_none_with_other_updates(self, dynamodb_setup):
        """deck_id=None + 他フィールド更新で SET + REMOVE が正しく組み合わされる."""
        service, table = dynamodb_setup

        card = service.update_card(
            user_id="user-1",
            card_id="card-1",
            front="New Front",
            deck_id=None,
        )

        assert card.front == "New Front"
        assert card.deck_id is None

        item = table.get_item(Key={"user_id": "user-1", "card_id": "card-1"})["Item"]
        assert item["front"] == "New Front"
        assert "deck_id" not in item

    def test_sentinel_is_not_none(self):
        """_UNSET sentinel は None とは異なるオブジェクト."""
        assert _UNSET is not None
        assert _UNSET != None  # noqa: E711

    def test_deck_id_remove_then_set(self, dynamodb_setup):
        """deck_id を REMOVE してから SET できること."""
        service, table = dynamodb_setup

        # Remove
        service.update_card(user_id="user-1", card_id="card-1", deck_id=None)
        item = table.get_item(Key={"user_id": "user-1", "card_id": "card-1"})["Item"]
        assert "deck_id" not in item

        # Set again
        service.update_card(user_id="user-1", card_id="card-1", deck_id="new-deck")
        item = table.get_item(Key={"user_id": "user-1", "card_id": "card-1"})["Item"]
        assert item["deck_id"] == "new-deck"

"""Tests for atomic deck limit verification in DeckService.create_deck.

Tests the 3-step atomic pattern:
1. Optimistic check (Query COUNT >= 50 → reject)
2. PutItem with ConditionExpression (prevent duplicate deck_id)
3. Post-creation count verification (> 50 → rollback + reject)
"""

import pytest
from unittest.mock import patch, MagicMock
from moto import mock_aws
import boto3
from botocore.exceptions import ClientError

from services.deck_service import (
    DeckService,
    DeckLimitExceededError,
    DeckServiceError,
)


@pytest.fixture
def dynamodb_tables():
    """Create mock DynamoDB tables (decks, cards)."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

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


class TestAtomicDeckLimit:
    """アトミックデッキ数制限テスト."""

    def test_create_deck_at_49_succeeds(self, deck_service):
        """49件 → 50件目の作成が成功する（上限ちょうど）."""
        for i in range(49):
            deck_service.create_deck(user_id="user-1", name=f"Deck {i}")

        # 50th deck should succeed
        deck = deck_service.create_deck(user_id="user-1", name="Deck 50th")
        assert deck.name == "Deck 50th"
        assert deck.deck_id is not None

    def test_create_deck_at_50_rejected(self, deck_service):
        """50件 → 51件目の作成が DeckLimitExceededError で拒否される."""
        for i in range(50):
            deck_service.create_deck(user_id="user-1", name=f"Deck {i}")

        with pytest.raises(DeckLimitExceededError):
            deck_service.create_deck(user_id="user-1", name="Deck 51st")

    def test_step1_optimistic_check_rejects_early(self, deck_service):
        """Step 1: 楽観的チェックで上限超過を早期に拒否する."""
        with patch.object(deck_service, "_get_deck_count", return_value=50):
            with pytest.raises(DeckLimitExceededError):
                deck_service.create_deck(user_id="user-1", name="Rejected")

            # PutItem should not have been called
            # (verified by the fact that _get_deck_count was called only once)
            deck_service._get_deck_count.assert_called_once_with("user-1")

    def test_step2_condition_expression_prevents_duplicate(self, deck_service):
        """Step 2: ConditionExpression が重複 deck_id を防止する."""
        # Create a deck
        deck = deck_service.create_deck(user_id="user-1", name="Original")

        # Try to insert with the same key should fail via ConditionExpression
        error_response = {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "Condition not met",
            }
        }
        with patch.object(
            deck_service.table,
            "put_item",
            side_effect=ClientError(error_response, "PutItem"),
        ):
            with pytest.raises(DeckLimitExceededError):
                deck_service.create_deck(user_id="user-1", name="Duplicate")

    def test_step3_race_detection_rollback(self, deck_service):
        """Step 3: レースコンディション検出時にロールバックが実行される."""
        # Mock _get_deck_count to return:
        # - 49 on first call (step 1: optimistic check passes)
        # - 51 on second call (step 3: race detected, over limit)
        call_count = [0]
        original_get_count = deck_service._get_deck_count

        def mock_get_count(user_id):
            call_count[0] += 1
            if call_count[0] == 1:
                return 49  # Step 1: under limit
            else:
                return 51  # Step 3: race detected

        with patch.object(
            deck_service, "_get_deck_count", side_effect=mock_get_count
        ):
            with patch.object(deck_service.table, "delete_item") as mock_delete:
                with pytest.raises(DeckLimitExceededError):
                    deck_service.create_deck(user_id="user-1", name="Race Deck")

                # Verify rollback (delete_item was called)
                mock_delete.assert_called_once()
                delete_key = mock_delete.call_args[1]["Key"]
                assert delete_key["user_id"] == "user-1"
                assert "deck_id" in delete_key

    def test_step3_race_rollback_failure_still_raises(self, deck_service):
        """Step 3: ロールバック失敗時でも DeckLimitExceededError を返す."""
        call_count = [0]

        def mock_get_count(user_id):
            call_count[0] += 1
            if call_count[0] == 1:
                return 49
            else:
                return 51

        with patch.object(
            deck_service, "_get_deck_count", side_effect=mock_get_count
        ):
            with patch.object(
                deck_service.table,
                "delete_item",
                side_effect=ClientError(
                    {"Error": {"Code": "InternalError", "Message": "fail"}},
                    "DeleteItem",
                ),
            ):
                with pytest.raises(DeckLimitExceededError):
                    deck_service.create_deck(user_id="user-1", name="Race Deck")

    def test_put_item_uses_condition_expression(self, deck_service):
        """PutItem が ConditionExpression 付きで呼ばれる."""
        with patch.object(deck_service.table, "put_item") as mock_put:
            deck_service.create_deck(user_id="user-1", name="Conditional")

            mock_put.assert_called_once()
            call_kwargs = mock_put.call_args[1]
            assert "ConditionExpression" in call_kwargs
            assert "attribute_not_exists" in call_kwargs["ConditionExpression"]

    def test_normal_create_calls_get_count_twice(self, deck_service):
        """正常作成時、_get_deck_count が2回呼ばれる（step1 + step3）."""
        with patch.object(
            deck_service, "_get_deck_count", return_value=0
        ) as mock_count:
            deck_service.create_deck(user_id="user-1", name="Normal")
            assert mock_count.call_count == 2

    def test_other_users_not_affected(self, deck_service):
        """他ユーザーのデッキ数は影響しない."""
        # user-1 has 50 decks (at limit)
        for i in range(50):
            deck_service.create_deck(user_id="user-1", name=f"Deck {i}")

        # user-2 can still create
        deck = deck_service.create_deck(user_id="user-2", name="User2 Deck")
        assert deck.user_id == "user-2"

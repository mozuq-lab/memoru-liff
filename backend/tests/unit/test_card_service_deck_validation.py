"""C-7: Unit tests for deck_id existence/ownership validation in CardService."""

import pytest
import boto3
from moto import mock_aws

from services.card_service import CardService
from services.deck_service import DeckService, DeckNotFoundError


@pytest.fixture
def dynamodb_table():
    """Create mock DynamoDB tables (cards, users, reviews, decks)."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

        dynamodb.create_table(
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
        ).wait_until_exists()

        dynamodb.create_table(
            TableName="memoru-users-test",
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "user_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        ).wait_until_exists()

        dynamodb.create_table(
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
        ).wait_until_exists()

        yield dynamodb


@pytest.fixture
def deck_service(dynamodb_table):
    return DeckService(
        table_name="memoru-decks-test",
        cards_table_name="memoru-cards-test",
        dynamodb_resource=dynamodb_table,
    )


@pytest.fixture
def card_service(dynamodb_table, deck_service):
    """CardService with a real DeckService for deck validation.

    transact_write_items は moto の if_not_exists バグを避けるため簡易モックする
    （test_card_service.py と同方針）。本テストは deck 検証のみが対象。
    """
    from boto3.dynamodb.types import TypeDeserializer

    service = CardService(
        table_name="memoru-cards-test",
        users_table_name="memoru-users-test",
        reviews_table_name="memoru-reviews-test",
        dynamodb_resource=dynamodb_table,
        deck_service=deck_service,
    )

    cards_table = dynamodb_table.Table("memoru-cards-test")
    users_table = dynamodb_table.Table("memoru-users-test")

    def mock_transact_write_items(TransactItems, **kwargs):
        deserializer = TypeDeserializer()
        for item in TransactItems:
            if "Update" in item:
                update = item["Update"]
                table = users_table if "users" in update["TableName"] else cards_table
                key_dict = {k: deserializer.deserialize(v) for k, v in update["Key"].items()}
                response = table.get_item(Key=key_dict)
                if "Item" not in response:
                    table.put_item(Item={**key_dict, "card_count": 0})
            elif "Put" in item:
                put = item["Put"]
                table = cards_table if "cards" in put["TableName"] else users_table
                item_dict = {k: deserializer.deserialize(v) for k, v in put["Item"].items()}
                table.put_item(Item=item_dict)
        return {}

    service._client.transact_write_items = mock_transact_write_items
    return service


class TestCreateCardDeckValidation:
    def test_create_card_with_nonexistent_deck_raises(self, card_service):
        """存在しない deck_id → DeckNotFoundError。"""
        with pytest.raises(DeckNotFoundError):
            card_service.create_card(
                user_id="user-1",
                front="Q",
                back="A",
                deck_id="missing-deck",
            )

    def test_create_card_with_other_users_deck_raises(self, card_service, deck_service):
        """他人の deck_id → DeckNotFoundError（所有検証）。"""
        other_deck = deck_service.create_deck(user_id="user-2", name="Other")
        with pytest.raises(DeckNotFoundError):
            card_service.create_card(
                user_id="user-1",
                front="Q",
                back="A",
                deck_id=other_deck.deck_id,
            )

    def test_create_card_with_owned_deck_succeeds(self, card_service, deck_service):
        """所有する deck_id → 成功。"""
        deck = deck_service.create_deck(user_id="user-1", name="Mine")
        card = card_service.create_card(
            user_id="user-1", front="Q", back="A", deck_id=deck.deck_id
        )
        assert card.deck_id == deck.deck_id

    def test_create_card_without_deck_skips_validation(self, card_service):
        """deck_id=None → 検証スキップして成功。"""
        card = card_service.create_card(user_id="user-1", front="Q", back="A")
        assert card.deck_id is None


class TestUpdateCardDeckValidation:
    def _seed_card(self, card_service, deck_service):
        card = card_service.create_card(user_id="user-1", front="Q", back="A")
        return card

    def test_update_card_to_nonexistent_deck_raises(self, card_service, deck_service):
        """存在しない deck への変更 → DeckNotFoundError。"""
        card = self._seed_card(card_service, deck_service)
        with pytest.raises(DeckNotFoundError):
            card_service.update_card(
                user_id="user-1", card_id=card.card_id, deck_id="missing-deck"
            )

    def test_update_card_to_owned_deck_succeeds(self, card_service, deck_service):
        """所有する deck への変更 → 成功。"""
        card = self._seed_card(card_service, deck_service)
        deck = deck_service.create_deck(user_id="user-1", name="Mine")
        updated = card_service.update_card(
            user_id="user-1", card_id=card.card_id, deck_id=deck.deck_id
        )
        assert updated.deck_id == deck.deck_id

    def test_update_card_clear_deck_skips_validation(self, card_service, deck_service):
        """deck_id=None（デッキ解除）は検証不要。"""
        card = self._seed_card(card_service, deck_service)
        updated = card_service.update_card(
            user_id="user-1", card_id=card.card_id, deck_id=None
        )
        assert updated.deck_id is None

    def test_update_card_unset_deck_skips_validation(self, card_service, deck_service):
        """deck_id 省略（_UNSET）は検証不要・変更なし。"""
        card = self._seed_card(card_service, deck_service)
        updated = card_service.update_card(
            user_id="user-1", card_id=card.card_id, front="Q2"
        )
        assert updated.front == "Q2"

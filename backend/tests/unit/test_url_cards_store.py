"""Unit tests for UrlCardsStore (C-3 reference-key flow)."""

import boto3
import pytest
from moto import mock_aws

from services.url_cards_store import UrlCardsStore, _TTL_SECONDS


@pytest.fixture
def processed_events_table():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        table = dynamodb.create_table(
            TableName="memoru-processed-events-test",
            KeySchema=[{"AttributeName": "webhook_event_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "webhook_event_id", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield dynamodb


@pytest.fixture
def store(processed_events_table):
    return UrlCardsStore(
        table_name="memoru-processed-events-test",
        dynamodb_resource=processed_events_table,
    )


SAMPLE_CARDS = [
    {"front": "Q1", "back": "A1", "suggested_tags": ["AI生成"]},
    {"front": "Q2", "back": "A2", "suggested_tags": []},
]


class TestStoreAndGet:
    def test_round_trip(self, store):
        ref_key = store.store_pending_cards(
            cards=SAMPLE_CARDS,
            page_url="https://example.com/page",
            page_title="Title",
        )
        assert ref_key.startswith("URLCARDS#")

        pending = store.get_pending_cards(ref_key)
        assert pending is not None
        assert pending["page_url"] == "https://example.com/page"
        assert pending["page_title"] == "Title"
        assert pending["saved"] is False
        assert pending["cards"] == SAMPLE_CARDS

    def test_ref_key_does_not_collide_with_idempotency_namespace(self, store):
        ref_key = store.store_pending_cards(
            cards=SAMPLE_CARDS, page_url="https://e.com", page_title="t"
        )
        # Idempotency records use raw LINE event ids; ours are namespaced.
        assert ref_key.startswith("URLCARDS#")

    def test_missing_returns_none(self, store):
        assert store.get_pending_cards("URLCARDS#nope") is None

    def test_empty_ref_key_returns_none(self, store):
        assert store.get_pending_cards("") is None

    def test_expired_record_returns_none(self, store):
        # Store with a timestamp far in the past so expires_at is already passed.
        ref_key = store.store_pending_cards(
            cards=SAMPLE_CARDS,
            page_url="https://e.com",
            page_title="t",
            now=0,  # expires_at = 0 + TTL, well in the past
        )
        assert ref_key  # stored
        # _TTL_SECONDS ago + TTL is still < now, so it is logically expired.
        assert _TTL_SECONDS > 0
        assert store.get_pending_cards(ref_key) is None


class TestMarkSaved:
    def test_first_mark_succeeds_second_fails(self, store):
        ref_key = store.store_pending_cards(
            cards=SAMPLE_CARDS, page_url="https://e.com", page_title="t"
        )
        assert store.mark_saved(ref_key) is True
        # Double-tap: second attempt must be rejected.
        assert store.mark_saved(ref_key) is False

    def test_mark_missing_returns_false(self, store):
        assert store.mark_saved("URLCARDS#missing") is False

    def test_saved_flag_reflected_in_get(self, store):
        ref_key = store.store_pending_cards(
            cards=SAMPLE_CARDS, page_url="https://e.com", page_title="t"
        )
        store.mark_saved(ref_key)
        pending = store.get_pending_cards(ref_key)
        assert pending is not None
        assert pending["saved"] is True

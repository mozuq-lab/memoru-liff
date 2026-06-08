"""Unit tests for WebhookIdempotencyService (N-6)."""

from unittest.mock import MagicMock

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from services.webhook_idempotency import (
    WebhookIdempotencyService,
    _STALE_SECONDS,
    _TTL_SECONDS,
)


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
def service(processed_events_table):
    return WebhookIdempotencyService(
        table_name="memoru-processed-events-test",
        dynamodb_resource=processed_events_table,
    )


class TestTryAcquire:
    def test_first_call_returns_true(self, service):
        assert service.try_acquire("evt-1") is True

    def test_in_flight_duplicate_returns_false(self, service):
        # Second call while first is still in-progress (not stale) is rejected.
        assert service.try_acquire("evt-1", now=1000) is True
        assert service.try_acquire("evt-1", now=1001) is False

    def test_distinct_events_each_acquire(self, service):
        assert service.try_acquire("evt-1") is True
        assert service.try_acquire("evt-2") is True

    def test_empty_or_none_event_id_processes(self, service):
        # No id to dedupe on → process (True)
        assert service.try_acquire("") is True
        assert service.try_acquire(None) is True

    def test_processed_event_is_not_reacquired(self, service):
        assert service.try_acquire("evt-done", now=1000) is True
        service.mark_processed("evt-done", now=1000)
        # Even far in the future (past stale window) a processed event is skipped.
        assert service.try_acquire("evt-done", now=1000 + _STALE_SECONDS + 10) is False

    def test_stale_in_progress_can_be_reacquired(self, service):
        # First attempt claims but never completes (crash) ...
        assert service.try_acquire("evt-stale", now=1000) is True
        # ... a fresh redelivery within the stale window is still blocked ...
        assert service.try_acquire("evt-stale", now=1000 + _STALE_SECONDS - 1) is False
        # ... but once the claim is stale it can be re-acquired and retried.
        assert service.try_acquire("evt-stale", now=1000 + _STALE_SECONDS + 1) is True

    def test_released_claim_can_be_reacquired(self, service):
        assert service.try_acquire("evt-rel", now=1000) is True
        service.release("evt-rel")
        # After release (failure path) a redelivery can immediately retry.
        assert service.try_acquire("evt-rel", now=1001) is True

    def test_sets_in_progress_with_ttl_and_claimed_at(self, service, processed_events_table):
        service.try_acquire("evt-ttl", now=1_000_000.0)
        item = processed_events_table.Table("memoru-processed-events-test").get_item(
            Key={"webhook_event_id": "evt-ttl"}
        )["Item"]
        assert item["status"] == "in_progress"
        assert int(item["claimed_at"]) == 1_000_000
        assert int(item["expires_at"]) == 1_000_000 + _TTL_SECONDS

    def test_fail_open_on_unexpected_error(self):
        # Unexpected ClientError → fail open (True) so real events aren't dropped.
        svc = WebhookIdempotencyService.__new__(WebhookIdempotencyService)
        svc.table = MagicMock()
        svc.table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException"}}, "PutItem"
        )
        assert svc.try_acquire("evt-x") is True


class TestMarkProcessed:
    def test_marks_status_processed(self, service, processed_events_table):
        service.try_acquire("evt-p", now=1000)
        service.mark_processed("evt-p", now=2000)
        item = processed_events_table.Table("memoru-processed-events-test").get_item(
            Key={"webhook_event_id": "evt-p"}
        )["Item"]
        assert item["status"] == "processed"
        assert int(item["expires_at"]) == 2000 + _TTL_SECONDS

    def test_noop_on_empty_id(self, service):
        # Should not raise.
        service.mark_processed("")
        service.mark_processed(None)


class TestRelease:
    def test_release_deletes_in_progress_claim(self, service, processed_events_table):
        service.try_acquire("evt-r", now=1000)
        service.release("evt-r")
        resp = processed_events_table.Table("memoru-processed-events-test").get_item(
            Key={"webhook_event_id": "evt-r"}
        )
        assert "Item" not in resp

    def test_release_does_not_delete_processed(self, service, processed_events_table):
        service.try_acquire("evt-rp", now=1000)
        service.mark_processed("evt-rp", now=1000)
        service.release("evt-rp")  # conditional: must not remove a processed record
        item = processed_events_table.Table("memoru-processed-events-test").get_item(
            Key={"webhook_event_id": "evt-rp"}
        )["Item"]
        assert item["status"] == "processed"

    def test_noop_on_empty_id(self, service):
        service.release("")
        service.release(None)

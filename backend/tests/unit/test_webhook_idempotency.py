"""Unit tests for WebhookIdempotencyService (N-6)."""

from unittest.mock import MagicMock

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

from services.webhook_idempotency import WebhookIdempotencyService


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

    def test_duplicate_call_returns_false(self, service):
        assert service.try_acquire("evt-1") is True
        assert service.try_acquire("evt-1") is False  # redelivery

    def test_distinct_events_each_acquire(self, service):
        assert service.try_acquire("evt-1") is True
        assert service.try_acquire("evt-2") is True

    def test_empty_or_none_event_id_processes(self, service):
        # No id to dedupe on → process (True)
        assert service.try_acquire("") is True
        assert service.try_acquire(None) is True

    def test_sets_ttl_expires_at(self, service, processed_events_table):
        service.try_acquire("evt-ttl", now=1_000_000.0)
        item = processed_events_table.Table("memoru-processed-events-test").get_item(
            Key={"webhook_event_id": "evt-ttl"}
        )["Item"]
        assert int(item["expires_at"]) == 1_000_000 + 24 * 60 * 60

    def test_fail_open_on_unexpected_error(self):
        # Unexpected ClientError → fail open (True) so real events aren't dropped.
        svc = WebhookIdempotencyService.__new__(WebhookIdempotencyService)
        svc.table = MagicMock()
        svc.table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException"}}, "PutItem"
        )
        assert svc.try_acquire("evt-x") is True

"""Unit tests for the SQS URL card generation worker (N-5)."""

import json
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

import jobs.url_generate_worker_handler as worker
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
def worker_with_table(processed_events_table):
    """worker の冪等サービスを moto テーブルに差し替える。"""
    svc = WebhookIdempotencyService(
        table_name="memoru-processed-events-test",
        dynamodb_resource=processed_events_table,
    )
    with patch.object(worker, "idempotency_service", svc):
        yield svc


def _record(message_id: str, body: dict) -> dict:
    return {"messageId": message_id, "body": json.dumps(body)}


def _event(*records) -> dict:
    return {"Records": list(records)}


class TestWorkerHappyPath:
    @patch("jobs.url_generate_worker_handler.generate_and_push_url_cards")
    def test_processes_and_no_failures(self, mock_generate, worker_with_table):
        event = _event(
            _record(
                "m1",
                {
                    "user_id": "user-1",
                    "line_user_id": "line-1",
                    "url": "https://example.com/a",
                    "webhook_event_id": "evt-1",
                },
            )
        )
        result = worker.handler(event, MagicMock())

        mock_generate.assert_called_once_with(
            user_id="user-1",
            line_user_id="line-1",
            url="https://example.com/a",
        )
        assert result == {"batchItemFailures": []}

    @patch("jobs.url_generate_worker_handler.generate_and_push_url_cards")
    def test_claim_marked_processed_on_success(
        self, mock_generate, worker_with_table, processed_events_table
    ):
        worker.handler(
            _event(
                _record(
                    "m1",
                    {
                        "user_id": "user-1",
                        "line_user_id": "line-1",
                        "url": "https://example.com/a",
                        "webhook_event_id": "evt-1",
                    },
                )
            ),
            MagicMock(),
        )
        item = processed_events_table.Table("memoru-processed-events-test").get_item(
            Key={"webhook_event_id": "URLGENWORK#evt-1"}
        )["Item"]
        assert item["status"] == "processed"


class TestWorkerIdempotency:
    @patch("jobs.url_generate_worker_handler.generate_and_push_url_cards")
    def test_duplicate_event_is_skipped(self, mock_generate, worker_with_table):
        rec = _record(
            "m1",
            {
                "user_id": "user-1",
                "line_user_id": "line-1",
                "url": "https://example.com/a",
                "webhook_event_id": "evt-dup",
            },
        )
        worker.handler(_event(rec), MagicMock())
        # 2 回目（別 messageId、同 event_id）は claim 済みでスキップ。
        rec2 = _record("m2", json.loads(rec["body"]))
        result = worker.handler(_event(rec2), MagicMock())

        assert mock_generate.call_count == 1
        assert result == {"batchItemFailures": []}


class TestWorkerFailure:
    @patch("jobs.url_generate_worker_handler.generate_and_push_url_cards")
    def test_failure_reports_batch_item_and_releases_claim(
        self, mock_generate, worker_with_table, processed_events_table
    ):
        mock_generate.side_effect = RuntimeError("bedrock down")
        result = worker.handler(
            _event(
                _record(
                    "m1",
                    {
                        "user_id": "user-1",
                        "line_user_id": "line-1",
                        "url": "https://example.com/a",
                        "webhook_event_id": "evt-fail",
                    },
                )
            ),
            MagicMock(),
        )
        assert result == {"batchItemFailures": [{"itemIdentifier": "m1"}]}
        # claim は release され、再配信での再 claim が可能になっている。
        resp = processed_events_table.Table("memoru-processed-events-test").get_item(
            Key={"webhook_event_id": "URLGENWORK#evt-fail"}
        )
        assert "Item" not in resp

    @patch("jobs.url_generate_worker_handler.generate_and_push_url_cards")
    def test_partial_failure_across_multiple_records(
        self, mock_generate, worker_with_table
    ):
        # m1 成功、m2 失敗。
        def side_effect(user_id, line_user_id, url):
            if url.endswith("/bad"):
                raise RuntimeError("boom")

        mock_generate.side_effect = side_effect
        result = worker.handler(
            _event(
                _record(
                    "m1",
                    {
                        "user_id": "u",
                        "line_user_id": "l",
                        "url": "https://example.com/ok",
                        "webhook_event_id": "evt-ok",
                    },
                ),
                _record(
                    "m2",
                    {
                        "user_id": "u",
                        "line_user_id": "l",
                        "url": "https://example.com/bad",
                        "webhook_event_id": "evt-bad",
                    },
                ),
            ),
            MagicMock(),
        )
        assert result == {"batchItemFailures": [{"itemIdentifier": "m2"}]}
        assert mock_generate.call_count == 2


class TestWorkerMalformed:
    @patch("jobs.url_generate_worker_handler.generate_and_push_url_cards")
    def test_unparseable_body_is_dropped(self, mock_generate, worker_with_table):
        event = {"Records": [{"messageId": "m1", "body": "not-json{"}]}
        result = worker.handler(event, MagicMock())
        mock_generate.assert_not_called()
        # リトライ不要 → 失敗に積まれない（成功扱いで削除）。
        assert result == {"batchItemFailures": []}

    @patch("jobs.url_generate_worker_handler.generate_and_push_url_cards")
    def test_missing_fields_dropped(self, mock_generate, worker_with_table):
        event = _event(_record("m1", {"user_id": "u"}))  # url/line_user_id 欠落
        result = worker.handler(event, MagicMock())
        mock_generate.assert_not_called()
        assert result == {"batchItemFailures": []}

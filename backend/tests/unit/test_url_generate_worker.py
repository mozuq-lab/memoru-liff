"""Unit tests for the SQS URL card generation worker (N-5).

通知とリトライ判定の分離（R-2）も検証する:
  - permanent → ユーザー通知 + mark_processed + リトライなし。
  - transient（非最終試行）→ 通知なし + release + batchItemFailures。
  - transient（最終試行 ApproximateReceiveCount=3）→ 通知あり + batchItemFailures。
  - 通知失敗でもリトライ判定は不変。
"""

import json
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

import jobs.url_generate_worker_handler as worker
from services.webhook_idempotency import WebhookIdempotencyService
from services.url_generation_service import (
    UrlGenerationPermanentError,
    UrlGenerationTransientError,
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
def worker_with_table(processed_events_table):
    """worker の冪等サービスを moto テーブルに差し替える。"""
    svc = WebhookIdempotencyService(
        table_name="memoru-processed-events-test",
        dynamodb_resource=processed_events_table,
    )
    with patch.object(worker, "idempotency_service", svc):
        yield svc


def _record(message_id: str, body: dict, receive_count: int = 1) -> dict:
    return {
        "messageId": message_id,
        "body": json.dumps(body),
        "attributes": {"ApproximateReceiveCount": str(receive_count)},
    }


def _event(*records) -> dict:
    return {"Records": list(records)}


_BODY = {
    "user_id": "user-1",
    "line_user_id": "line-1",
    "url": "https://example.com/a",
    "webhook_event_id": "evt-1",
}


class TestWorkerHappyPath:
    @patch("jobs.url_generate_worker_handler.generate_url_cards_core")
    def test_processes_and_no_failures(self, mock_core, worker_with_table):
        result = worker.handler(_event(_record("m1", _BODY)), MagicMock())

        mock_core.assert_called_once_with(
            user_id="user-1",
            line_user_id="line-1",
            url="https://example.com/a",
        )
        assert result == {"batchItemFailures": []}

    @patch("jobs.url_generate_worker_handler.generate_url_cards_core")
    def test_claim_marked_processed_on_success(
        self, mock_core, worker_with_table, processed_events_table
    ):
        worker.handler(_event(_record("m1", _BODY)), MagicMock())
        item = processed_events_table.Table("memoru-processed-events-test").get_item(
            Key={"webhook_event_id": "URLGENWORK#evt-1"}
        )["Item"]
        assert item["status"] == "processed"


class TestWorkerIdempotency:
    @patch("jobs.url_generate_worker_handler.generate_url_cards_core")
    def test_duplicate_event_is_skipped(self, mock_core, worker_with_table):
        body = {**_BODY, "webhook_event_id": "evt-dup"}
        worker.handler(_event(_record("m1", body)), MagicMock())
        # 2 回目（別 messageId、同 event_id）は claim 済みでスキップ。
        result = worker.handler(_event(_record("m2", body)), MagicMock())

        assert mock_core.call_count == 1
        assert result == {"batchItemFailures": []}


class TestWorkerPermanentFailure:
    @patch("jobs.url_generate_worker_handler.notify_generation_failure")
    @patch("jobs.url_generate_worker_handler.generate_url_cards_core")
    def test_permanent_notifies_and_marks_processed_no_retry(
        self, mock_core, mock_notify, worker_with_table, processed_events_table
    ):
        mock_core.side_effect = UrlGenerationPermanentError(
            "no text", user_message="ページからテキストを抽出できませんでした。"
        )
        result = worker.handler(_event(_record("m1", _BODY)), MagicMock())

        # ユーザーに通知される。
        mock_notify.assert_called_once_with(
            "line-1", "ページからテキストを抽出できませんでした。"
        )
        # リトライしない（batchItemFailures は空）。
        assert result == {"batchItemFailures": []}
        # 成功扱いで claim は processed に確定。
        item = processed_events_table.Table("memoru-processed-events-test").get_item(
            Key={"webhook_event_id": "URLGENWORK#evt-1"}
        )["Item"]
        assert item["status"] == "processed"


class TestWorkerTransientFailure:
    @patch("jobs.url_generate_worker_handler.notify_generation_failure")
    @patch("jobs.url_generate_worker_handler.generate_url_cards_core")
    def test_transient_non_final_silent_retry_releases_claim(
        self, mock_core, mock_notify, worker_with_table, processed_events_table
    ):
        mock_core.side_effect = UrlGenerationTransientError(
            "ai down", user_message="AI処理中にエラーが発生しました。"
        )
        # ApproximateReceiveCount=1 (< maxReceiveCount=3) → 非最終試行。
        result = worker.handler(
            _event(_record("m1", _BODY, receive_count=1)), MagicMock()
        )

        # 通知しない（サイレントリトライ）。
        mock_notify.assert_not_called()
        # batchItemFailures に積む。
        assert result == {"batchItemFailures": [{"itemIdentifier": "m1"}]}
        # claim は release（再 claim 可能）。
        resp = processed_events_table.Table("memoru-processed-events-test").get_item(
            Key={"webhook_event_id": "URLGENWORK#evt-1"}
        )
        assert "Item" not in resp

    @patch("jobs.url_generate_worker_handler.notify_generation_failure")
    @patch("jobs.url_generate_worker_handler.generate_url_cards_core")
    def test_transient_final_attempt_notifies_and_reports(
        self, mock_core, mock_notify, worker_with_table, processed_events_table
    ):
        mock_core.side_effect = UrlGenerationTransientError(
            "ai down", user_message="AI処理中にエラーが発生しました。"
        )
        # ApproximateReceiveCount=3 (>= maxReceiveCount=3) → 最終試行 → DLQ 行き。
        result = worker.handler(
            _event(_record("m1", _BODY, receive_count=3)), MagicMock()
        )

        # 最終試行のみユーザーに通知。
        mock_notify.assert_called_once_with(
            "line-1", "AI処理中にエラーが発生しました。"
        )
        assert result == {"batchItemFailures": [{"itemIdentifier": "m1"}]}
        # claim は release。
        resp = processed_events_table.Table("memoru-processed-events-test").get_item(
            Key={"webhook_event_id": "URLGENWORK#evt-1"}
        )
        assert "Item" not in resp

    @patch("jobs.url_generate_worker_handler.notify_generation_failure")
    @patch("jobs.url_generate_worker_handler.generate_url_cards_core")
    def test_unexpected_exception_treated_as_transient(
        self, mock_core, mock_notify, worker_with_table
    ):
        # 想定外例外（user_message を持たない）も transient 扱い。
        mock_core.side_effect = RuntimeError("boom")
        result = worker.handler(
            _event(_record("m1", _BODY, receive_count=1)), MagicMock()
        )
        mock_notify.assert_not_called()
        assert result == {"batchItemFailures": [{"itemIdentifier": "m1"}]}

    @patch("jobs.url_generate_worker_handler.notify_generation_failure")
    @patch("jobs.url_generate_worker_handler.generate_url_cards_core")
    def test_notification_failure_does_not_change_retry_decision(
        self, mock_core, mock_notify, worker_with_table
    ):
        # 通知が失敗してもリトライ判定（batchItemFailures）は不変。
        mock_core.side_effect = UrlGenerationTransientError(
            "ai down", user_message="AI処理中にエラーが発生しました。"
        )
        mock_notify.side_effect = RuntimeError("push failed")
        # 最終試行で通知失敗 → それでも batchItemFailures は積まれる。
        result = worker.handler(
            _event(_record("m1", _BODY, receive_count=3)), MagicMock()
        )
        assert result == {"batchItemFailures": [{"itemIdentifier": "m1"}]}

    @patch("jobs.url_generate_worker_handler.generate_url_cards_core")
    def test_partial_failure_across_multiple_records(
        self, mock_core, worker_with_table
    ):
        # m1 成功、m2 transient 失敗。
        def side_effect(user_id, line_user_id, url):
            if url.endswith("/bad"):
                raise UrlGenerationTransientError("boom", user_message="x")

        mock_core.side_effect = side_effect
        result = worker.handler(
            _event(
                _record(
                    "m1",
                    {**_BODY, "url": "https://example.com/ok", "webhook_event_id": "evt-ok"},
                ),
                _record(
                    "m2",
                    {**_BODY, "url": "https://example.com/bad", "webhook_event_id": "evt-bad"},
                ),
            ),
            MagicMock(),
        )
        assert result == {"batchItemFailures": [{"itemIdentifier": "m2"}]}
        assert mock_core.call_count == 2


class TestWorkerMalformed:
    @patch("jobs.url_generate_worker_handler.generate_url_cards_core")
    def test_unparseable_body_is_dropped(self, mock_core, worker_with_table):
        event = {"Records": [{"messageId": "m1", "body": "not-json{"}]}
        result = worker.handler(event, MagicMock())
        mock_core.assert_not_called()
        # リトライ不要 → 失敗に積まれない（成功扱いで削除）。
        assert result == {"batchItemFailures": []}

    @patch("jobs.url_generate_worker_handler.generate_url_cards_core")
    def test_missing_fields_dropped(self, mock_core, worker_with_table):
        event = _event(_record("m1", {"user_id": "u"}))  # url/line_user_id 欠落
        result = worker.handler(event, MagicMock())
        mock_core.assert_not_called()
        assert result == {"batchItemFailures": []}


class TestReceiveCountConstant:
    def test_max_receive_count_matches_template(self):
        """MAX_RECEIVE_COUNT は template の maxReceiveCount=3 と一致する。"""
        assert worker.MAX_RECEIVE_COUNT == 3

"""Unit tests for services/ai_job_service.py と jobs/ai_job_worker_handler.py."""

import os
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

import services.ai_job_service as svc
from services.ai_job_store import AiJobStore
from services.ai_service import AITimeoutError

TABLE_NAME = "memoru-ai-jobs-test"


@pytest.fixture
def store():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield AiJobStore(table_name=TABLE_NAME, dynamodb_resource=dynamodb)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """キュー設定の環境変数をテストごとにリセットする。"""
    for name in ("AI_JOB_QUEUE_URL", "AI_JOB_HEAVY_QUEUE_URL", "AI_JOB_WORKER_MODE"):
        monkeypatch.delenv(name, raising=False)


class TestSubmitInline:
    """キュー URL 未設定（ローカル既定）→ inline 同期実行。"""

    def test_inline_executes_and_completes(self, store):
        with patch.object(svc, "execute_job", return_value={"ok": True}) as mock_exec:
            job = svc.submit_ai_job("user-1", "generate", {"input_text": "x"}, store=store)

        assert job["status"] == "queued"  # 返却は作成時点のレコード
        stored = store.get_job(job["job_id"])
        assert stored["status"] == "completed"
        assert stored["result"] == {"ok": True}
        executed_job = mock_exec.call_args.args[0]
        assert executed_job["user_id"] == "user-1"
        assert executed_job["payload"] == {"input_text": "x"}

    def test_inline_ai_error_records_failed(self, store):
        with patch.object(svc, "execute_job", side_effect=AITimeoutError("slow")):
            job = svc.submit_ai_job("user-1", "generate", {}, store=store)

        stored = store.get_job(job["job_id"])
        assert stored["status"] == "failed"
        assert stored["error"] == {
            "status": 504,
            "code": "ai_timeout",
            "message": "AI service timeout",
        }

    def test_worker_mode_inline_overrides_queue(self, store, monkeypatch):
        """AI_JOB_WORKER_MODE=inline はキュー URL があっても inline 実行する。"""
        monkeypatch.setenv("AI_JOB_QUEUE_URL", "https://sqs.example/queue")
        monkeypatch.setenv("AI_JOB_WORKER_MODE", "inline")

        with patch.object(svc, "execute_job", return_value={}) as mock_exec, patch.object(
            svc, "_get_sqs_client"
        ) as mock_sqs:
            svc.submit_ai_job("user-1", "generate", {}, store=store)

        mock_exec.assert_called_once()
        mock_sqs.assert_not_called()


class TestSubmitEnqueue:
    def test_enqueue_sends_job_id_and_keeps_queued(self, store, monkeypatch):
        monkeypatch.setenv("AI_JOB_QUEUE_URL", "https://sqs.example/interactive")

        mock_client = MagicMock()
        with patch.object(svc, "_get_sqs_client", return_value=mock_client), patch.object(
            svc, "execute_job"
        ) as mock_exec:
            job = svc.submit_ai_job("user-1", "generate", {}, store=store)

        mock_exec.assert_not_called()
        assert store.get_job(job["job_id"])["status"] == "queued"
        kwargs = mock_client.send_message.call_args.kwargs
        assert kwargs["QueueUrl"] == "https://sqs.example/interactive"
        assert job["job_id"] in kwargs["MessageBody"]

    def test_heavy_job_routes_to_heavy_queue(self, store, monkeypatch):
        monkeypatch.setenv("AI_JOB_QUEUE_URL", "https://sqs.example/interactive")
        monkeypatch.setenv("AI_JOB_HEAVY_QUEUE_URL", "https://sqs.example/heavy")

        mock_client = MagicMock()
        with patch.object(svc, "_get_sqs_client", return_value=mock_client):
            svc.submit_ai_job("user-1", "generate_from_url", {"url": "https://a"}, store=store)

        kwargs = mock_client.send_message.call_args.kwargs
        assert kwargs["QueueUrl"] == "https://sqs.example/heavy"

    def test_heavy_queue_unset_falls_back_to_inline(self, store, monkeypatch):
        """heavy キューだけ未設定なら generate_from_url は inline になる。"""
        monkeypatch.setenv("AI_JOB_QUEUE_URL", "https://sqs.example/interactive")

        with patch.object(svc, "execute_job", return_value={}) as mock_exec:
            svc.submit_ai_job("user-1", "generate_from_url", {"url": "https://a"}, store=store)

        mock_exec.assert_called_once()


class TestRunJobInline:
    def test_skips_when_already_claimed(self, store):
        job = store.create_job("user-1", "generate", {})
        store.claim(job["job_id"])  # フレッシュな processing

        with patch.object(svc, "execute_job") as mock_exec:
            svc.run_job_inline(store, job["job_id"])

        mock_exec.assert_not_called()

    def test_unknown_schema_version_fails_internal(self, store):
        job = store.create_job("user-1", "generate", {})
        store.table.update_item(
            Key={"job_id": job["job_id"]},
            UpdateExpression="SET schema_version = :v",
            ExpressionAttributeValues={":v": 999},
        )

        with patch.object(svc, "execute_job") as mock_exec:
            svc.run_job_inline(store, job["job_id"])

        mock_exec.assert_not_called()
        stored = store.get_job(job["job_id"])
        assert stored["status"] == "failed"
        assert stored["error"]["code"] == "internal"

    def test_record_failure_does_not_release(self, store, monkeypatch):
        """Phase C の記録失敗では release しない（processing のまま朽ちる。レビュー C-2）。"""
        monkeypatch.setattr(svc, "RECORD_RESULT_BACKOFF_SECONDS", 0)
        job = store.create_job("user-1", "generate", {})

        with patch.object(svc, "execute_job", return_value={"ok": True}), patch.object(
            store, "complete", side_effect=ClientError(
                {"Error": {"Code": "InternalServerError", "Message": "boom"}}, "UpdateItem"
            )
        ):
            svc.run_job_inline(store, job["job_id"])  # 例外は送出されない

        stored = store.get_job(job["job_id"])
        assert stored["status"] == "processing"  # queued に戻さない・failed にもしない


class TestRecordResultWithRetry:
    def test_retries_then_succeeds(self, store, monkeypatch):
        monkeypatch.setattr(svc, "RECORD_RESULT_BACKOFF_SECONDS", 0)
        job = store.create_job("user-1", "generate", {})
        store.claim(job["job_id"])

        real_complete = store.complete
        calls = {"n": 0}

        def flaky_complete(job_id, result):
            calls["n"] += 1
            if calls["n"] < 3:
                raise ClientError(
                    {"Error": {"Code": "ThrottlingException", "Message": "slow down"}},
                    "UpdateItem",
                )
            return real_complete(job_id, result)

        with patch.object(store, "complete", side_effect=flaky_complete):
            ok = svc.record_result_with_retry(store, job["job_id"], result={"ok": 1})

        assert ok is True
        assert store.get_job(job["job_id"])["status"] == "completed"

    def test_gives_up_after_max_attempts(self, store, monkeypatch):
        monkeypatch.setattr(svc, "RECORD_RESULT_BACKOFF_SECONDS", 0)
        job = store.create_job("user-1", "generate", {})

        with patch.object(
            store, "fail", side_effect=RuntimeError("persistent failure")
        ) as mock_fail:
            ok = svc.record_result_with_retry(
                store, job["job_id"], error={"status": 500, "code": "internal", "message": "x"}
            )

        assert ok is False
        assert mock_fail.call_count == svc.RECORD_RESULT_ATTEMPTS


class TestWorkerHandler:
    def _sqs_event(self, *bodies):
        return {
            "Records": [
                {"messageId": f"msg-{i}", "body": body}
                for i, body in enumerate(bodies)
            ]
        }

    def test_success_returns_no_failures(self, store):
        import jobs.ai_job_worker_handler as worker

        job = store.create_job("user-1", "generate", {})
        with patch.object(worker, "ai_job_store", store), patch.object(
            svc, "execute_job", return_value={"ok": True}
        ):
            result = worker.handler(
                self._sqs_event(f'{{"job_id": "{job["job_id"]}"}}'), MagicMock()
            )

        assert result == {"batchItemFailures": []}
        assert store.get_job(job["job_id"])["status"] == "completed"

    def test_claim_infra_error_reports_batch_failure(self, store):
        """claim 前の DynamoDB エラー（executor 未実行）は SQS リトライに委ねる。"""
        import jobs.ai_job_worker_handler as worker

        with patch.object(worker, "ai_job_store", store), patch.object(
            worker,
            "run_job_inline",
            side_effect=ClientError(
                {"Error": {"Code": "InternalServerError", "Message": "boom"}}, "UpdateItem"
            ),
        ):
            result = worker.handler(self._sqs_event('{"job_id": "aijob_x"}'), MagicMock())

        assert result == {"batchItemFailures": [{"itemIdentifier": "msg-0"}]}

    def test_ai_error_does_not_report_batch_failure(self, store):
        """AI エラーは failed 記録のみで SQS リトライしない（3×課金の防止）。"""
        import jobs.ai_job_worker_handler as worker

        job = store.create_job("user-1", "generate", {})
        with patch.object(worker, "ai_job_store", store), patch.object(
            svc, "execute_job", side_effect=AITimeoutError("slow")
        ):
            result = worker.handler(
                self._sqs_event(f'{{"job_id": "{job["job_id"]}"}}'), MagicMock()
            )

        assert result == {"batchItemFailures": []}
        assert store.get_job(job["job_id"])["status"] == "failed"

    def test_malformed_messages_are_skipped(self, store):
        import jobs.ai_job_worker_handler as worker

        with patch.object(worker, "ai_job_store", store):
            result = worker.handler(
                self._sqs_event("not-json", '{"no_job_id": true}'), MagicMock()
            )

        assert result == {"batchItemFailures": []}

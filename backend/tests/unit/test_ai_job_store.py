"""Unit tests for services/ai_job_store.py (ai-async-jobs)."""

from datetime import datetime, timedelta, timezone

import boto3
import pytest
from moto import mock_aws

from services.ai_job_store import (
    STALE_PROCESSING_SECONDS,
    AiJobStore,
    from_dynamodb_safe,
    to_dynamodb_safe,
)

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


class TestCreateAndGet:
    def test_create_job_returns_queued_record(self, store):
        job = store.create_job("user-1", "generate", {"input_text": "hello"})

        assert job["job_id"].startswith("aijob_")
        assert job["user_id"] == "user-1"
        assert job["job_type"] == "generate"
        assert job["status"] == "queued"
        assert job["schema_version"] == 1
        assert job["payload"] == {"input_text": "hello"}
        assert job["ttl"] > int(datetime.now(timezone.utc).timestamp())

    def test_get_job_roundtrip(self, store):
        created = store.create_job("user-1", "refine", {"front": "Q"})
        fetched = store.get_job(created["job_id"])
        assert fetched == created

    def test_get_job_missing_returns_none(self, store):
        assert store.get_job("aijob_nonexistent") is None


class TestDecimalConversion:
    """float 混入（advice の average_grade 等）の回帰防止（設計レビュー C-1）。"""

    def test_float_result_roundtrip(self, store):
        job = store.create_job("user-1", "advice", {"language": "ja"})

        result = {
            "study_stats": {"average_grade": 3.5, "total_reviews": 10},
            "advice_text": "がんばりましょう",
        }
        # boto3 は float を受け付けないため、変換なしだと TypeError になるケース
        store.complete(job["job_id"], result)

        fetched = store.get_job(job["job_id"])
        assert fetched["status"] == "completed"
        assert fetched["result"]["study_stats"]["average_grade"] == 3.5
        assert isinstance(fetched["result"]["study_stats"]["average_grade"], float)
        # 整数値は int に戻る（Decimal のまま返さない = JSON シリアライズ可能）
        assert fetched["result"]["study_stats"]["total_reviews"] == 10
        assert isinstance(fetched["result"]["study_stats"]["total_reviews"], int)

    def test_float_payload_roundtrip(self, store):
        job = store.create_job("user-1", "generate", {"weight": 0.75})
        fetched = store.get_job(job["job_id"])
        assert fetched["payload"]["weight"] == 0.75

    def test_helpers_roundtrip_nested(self):
        original = {"a": [1.5, {"b": 2, "c": [0.25]}], "d": "text"}
        assert from_dynamodb_safe(to_dynamodb_safe(original)) == original


class TestClaim:
    def test_claim_queued_job(self, store):
        job = store.create_job("user-1", "generate", {})
        claimed = store.claim(job["job_id"])

        assert claimed is not None
        assert claimed["status"] == "processing"
        assert claimed["payload"] == {}

    def test_duplicate_claim_returns_none(self, store):
        """SQS 重複配信の吸収: 2 回目の claim は None。"""
        job = store.create_job("user-1", "generate", {})
        assert store.claim(job["job_id"]) is not None
        assert store.claim(job["job_id"]) is None

    def test_claim_completed_job_returns_none(self, store):
        job = store.create_job("user-1", "generate", {})
        store.claim(job["job_id"])
        store.complete(job["job_id"], {"ok": True})
        assert store.claim(job["job_id"]) is None

    def test_claim_failed_job_returns_none(self, store):
        job = store.create_job("user-1", "generate", {})
        store.claim(job["job_id"])
        store.fail(job["job_id"], {"status": 500, "code": "internal", "message": "x"})
        assert store.claim(job["job_id"]) is None

    def test_stale_processing_can_be_reclaimed(self, store):
        """ワーカー強制終了の残骸（stale processing）は再 claim できる。"""
        job = store.create_job("user-1", "generate", {})
        store.claim(job["job_id"])

        # updated_at を stale 閾値より古く書き換える
        stale_time = datetime.now(timezone.utc) - timedelta(
            seconds=STALE_PROCESSING_SECONDS + 10
        )
        store.table.update_item(
            Key={"job_id": job["job_id"]},
            UpdateExpression="SET updated_at = :old",
            ExpressionAttributeValues={":old": stale_time.isoformat()},
        )

        assert store.claim(job["job_id"]) is not None

    def test_fresh_processing_cannot_be_reclaimed(self, store):
        """フレッシュな processing（生きている実行）は再 claim できない。"""
        job = store.create_job("user-1", "generate", {})
        store.claim(job["job_id"])
        assert store.claim(job["job_id"]) is None


class TestCompleteAndFail:
    def test_complete_sets_status_and_result(self, store):
        job = store.create_job("user-1", "generate", {})
        store.claim(job["job_id"])
        store.complete(job["job_id"], {"generated_cards": []})

        fetched = store.get_job(job["job_id"])
        assert fetched["status"] == "completed"
        assert fetched["result"] == {"generated_cards": []}
        assert "error" not in fetched

    def test_fail_sets_status_and_error(self, store):
        job = store.create_job("user-1", "generate", {})
        store.claim(job["job_id"])
        store.fail(
            job["job_id"],
            {"status": 504, "code": "ai_timeout", "message": "AI service timeout"},
        )

        fetched = store.get_job(job["job_id"])
        assert fetched["status"] == "failed"
        assert fetched["error"]["status"] == 504
        assert fetched["error"]["code"] == "ai_timeout"
        assert "result" not in fetched

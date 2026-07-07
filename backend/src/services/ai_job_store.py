"""AI 非同期ジョブの永続化層 (ai-async-jobs)。

AiJobsTable への CRUD と、ワーカーの claim（queued→processing の条件付き更新）を担う。
ジョブレコード自体が SQS at-least-once 配信に対する冪等 claim を兼ねる
（webhook_idempotency の完了マーカー方式と同思想。設計 architecture.md §4）。

Decimal 変換（設計レビュー C-1）:
    result / payload には float が混入する（例: advice の study_stats.average_grade）。
    boto3 の DynamoDB リソースは float を受け付けないため、書き込み時に
    ``json.loads(json.dumps(x), parse_float=Decimal)`` で再帰変換し、読み出し時に
    Decimal → int/float へ逆変換して JSON シリアライズ可能な形で返す。
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from utils.dynamodb_client import get_dynamodb_resource

logger = Logger()

JOB_ID_PREFIX = "aijob_"

# payload スキーマ版。互換性のない変更時にインクリメントし、ワーカーは未知版を
# failed(internal) にする（設計レビュー SM-2）。
SCHEMA_VERSION = 1

# ジョブレコードの保持期間（結果の参照可能期間）。
JOB_TTL_HOURS = 24

# processing のままのジョブを再 claim 可能とみなす閾値（秒）。
# ワーカー Lambda の Timeout (180s) より長くすること（生きている遅い実行を
# 二重処理しないため。webhook_idempotency と同じ原則。設計レビュー H-1）。
STALE_PROCESSING_SECONDS = 240

STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


def to_dynamodb_safe(value: Any) -> Any:
    """float を Decimal に再帰変換して DynamoDB に書き込める形にする。"""
    return json.loads(json.dumps(value), parse_float=Decimal)


def from_dynamodb_safe(value: Any) -> Any:
    """DynamoDB の Decimal を int/float に再帰変換して JSON 化可能な形にする。"""
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {k: from_dynamodb_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [from_dynamodb_safe(v) for v in value]
    return value


class AiJobStore:
    """AiJobsTable の永続化層。"""

    def __init__(
        self,
        table_name: Optional[str] = None,
        dynamodb_resource: Optional[Any] = None,
    ) -> None:
        self.table_name = table_name or os.environ.get(
            "AI_JOBS_TABLE", "memoru-ai-jobs-dev"
        )
        self.dynamodb = get_dynamodb_resource(dynamodb_resource)
        self.table = self.dynamodb.Table(self.table_name)

    def create_job(self, user_id: str, job_type: str, payload: dict) -> dict:
        """ジョブレコードを queued で作成して返す。"""
        now = datetime.now(timezone.utc)
        item = {
            "job_id": f"{JOB_ID_PREFIX}{uuid.uuid4()}",
            "user_id": user_id,
            "job_type": job_type,
            "status": STATUS_QUEUED,
            "schema_version": SCHEMA_VERSION,
            "payload": to_dynamodb_safe(payload),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "ttl": int((now + timedelta(hours=JOB_TTL_HOURS)).timestamp()),
        }
        self.table.put_item(Item=item)
        return from_dynamodb_safe(item)

    def get_job(self, job_id: str) -> Optional[dict]:
        """ジョブレコードを取得する（存在しない場合は None）。"""
        response = self.table.get_item(Key={"job_id": job_id})
        item = response.get("Item")
        if not item:
            return None
        return from_dynamodb_safe(item)

    def claim(self, job_id: str) -> Optional[dict]:
        """queued → processing の条件付き更新でジョブを claim する。

        SQS の重複配信・stale な processing（ワーカー強制終了の残骸）を吸収する。

        Returns:
            claim に成功した場合は更新後のジョブレコード。
            条件不成立（completed/failed/フレッシュな processing）の場合は None。

        Raises:
            ClientError: ConditionalCheckFailed 以外の DynamoDB エラー
                （executor 未実行のため呼び出し側は SQS リトライに委ねてよい）。
        """
        now = datetime.now(timezone.utc)
        stale_threshold = (
            now - timedelta(seconds=STALE_PROCESSING_SECONDS)
        ).isoformat()
        try:
            response = self.table.update_item(
                Key={"job_id": job_id},
                UpdateExpression="SET #st = :processing, updated_at = :now",
                ConditionExpression=(
                    "#st = :queued OR (#st = :processing AND updated_at < :stale)"
                ),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":processing": STATUS_PROCESSING,
                    ":queued": STATUS_QUEUED,
                    ":now": now.isoformat(),
                    ":stale": stale_threshold,
                },
                ReturnValues="ALL_NEW",
            )
        except ClientError as e:
            if (
                e.response.get("Error", {}).get("Code")
                == "ConditionalCheckFailedException"
            ):
                return None
            raise
        return from_dynamodb_safe(response.get("Attributes", {}))

    def complete(self, job_id: str, result: dict) -> None:
        """ジョブを completed にして結果を記録する。"""
        self.table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #st = :completed, #res = :result, updated_at = :now",
            ExpressionAttributeNames={"#st": "status", "#res": "result"},
            ExpressionAttributeValues={
                ":completed": STATUS_COMPLETED,
                ":result": to_dynamodb_safe(result),
                ":now": datetime.now(timezone.utc).isoformat(),
            },
        )

    def fail(self, job_id: str, error: dict) -> None:
        """ジョブを failed にしてエラーを記録する。"""
        self.table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #st = :failed, #err = :error, updated_at = :now",
            ExpressionAttributeNames={"#st": "status", "#err": "error"},
            ExpressionAttributeValues={
                ":failed": STATUS_FAILED,
                ":error": to_dynamodb_safe(error),
                ":now": datetime.now(timezone.utc).isoformat(),
            },
        )

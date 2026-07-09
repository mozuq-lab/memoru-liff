"""AI 非同期ジョブの submit サービス (ai-async-jobs)。

ジョブ登録 + SQS enqueue（または inline 同期実行）を担う。
inline 判定は既存 `webhook/line_actions._should_enqueue` と同じ規約:
``AI_JOB_WORKER_MODE == "inline"`` または対象キューの URL 未設定 → inline。

enqueue 失敗時は inline へフォールバックせず例外を伝播する（既存 N-5 と同方針。
ジョブレコードは queued のまま残るが TTL 24h で自動削除される）。
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Optional

from aws_lambda_powertools import Logger

from services.ai_job_errors import classify_ai_job_error
from services.ai_job_executors import HEAVY_JOB_TYPES, execute_job
from services.ai_job_store import AiJobStore
from utils.sqs_client import get_sqs_client

logger = Logger()

_sqs_client: Any = None

# 結果記録（Phase C）の再試行回数とバックオフ（秒）。
RECORD_RESULT_ATTEMPTS = 3
RECORD_RESULT_BACKOFF_SECONDS = 0.5


def _get_sqs_client() -> Any:
    """SQS クライアントを遅延生成して返す。"""
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = get_sqs_client()
    return _sqs_client


def _queue_url_for(job_type: str) -> str:
    """job_type の振り分け先キュー URL を返す（未設定なら空文字）。"""
    if job_type in HEAVY_JOB_TYPES:
        return os.environ.get("AI_JOB_HEAVY_QUEUE_URL", "")
    return os.environ.get("AI_JOB_QUEUE_URL", "")


def _should_enqueue(job_type: str) -> bool:
    """SQS ワーカーへ非同期ディスパッチすべきか判定する。"""
    worker_mode = os.environ.get("AI_JOB_WORKER_MODE", "")
    return bool(_queue_url_for(job_type)) and worker_mode != "inline"


def record_result_with_retry(
    store: AiJobStore,
    job_id: str,
    *,
    result: Optional[dict] = None,
    error: Optional[dict] = None,
) -> bool:
    """ジョブ結果を短いバックオフ付きで記録する（Phase C）。

    executor 実行後の記録であり、失敗しても release / SQS リトライは行わない
    （再実行は tutor の履歴二重追加・二重課金を招くため。設計レビュー C-2）。

    Returns:
        記録に成功したら True。全試行失敗で False（ジョブは processing のまま
        TTL で朽ちる。フロントはタイムアウト表示になる）。
    """
    for attempt in range(1, RECORD_RESULT_ATTEMPTS + 1):
        try:
            if error is not None:
                store.fail(job_id, error)
            else:
                store.complete(job_id, result or {})
            return True
        except Exception as e:
            logger.warning(
                "Failed to record AI job result",
                extra={"job_id": job_id, "attempt": attempt, "error": str(e)},
            )
            if attempt < RECORD_RESULT_ATTEMPTS:
                time.sleep(RECORD_RESULT_BACKOFF_SECONDS * attempt)
    logger.error(
        "Giving up recording AI job result; job will expire as processing",
        extra={"job_id": job_id},
    )
    return False


def run_job_inline(store: AiJobStore, job_id: str) -> None:
    """ジョブをその場で claim → 実行 → 記録する（inline モード / ワーカー共通の実行部）。

    例外は送出しない（結果は必ずジョブレコードに記録される）。
    claim できなかった場合（重複実行等）は何もしない。
    """
    job = store.claim(job_id)
    if job is None:
        logger.info("AI job already claimed or finished", extra={"job_id": job_id})
        return

    from services.ai_job_executors import is_supported_schema

    if not is_supported_schema(job):
        record_result_with_retry(
            store,
            job_id,
            error={
                "status": 500,
                "code": "internal",
                "message": "Unsupported job schema version",
            },
        )
        return

    try:
        result = execute_job(job)
    except Exception as exc:
        job_error = classify_ai_job_error(exc)
        # 想定内の AI/ドメインエラーは warning、分類不能な internal（実装バグの
        # 可能性が高い）は error で記録し、ERROR ベースの監視で検知可能にする。
        log_method = logger.error if job_error.code == "internal" else logger.warning
        log_method(
            "AI job failed",
            extra={
                "job_id": job_id,
                "job_type": job.get("job_type"),
                "error_type": type(exc).__name__,
                "error_code": job_error.code,
                "error": str(exc),
            },
        )
        record_result_with_retry(store, job_id, error=job_error.to_dict())
        return

    record_result_with_retry(store, job_id, result=result)


def submit_ai_job(
    user_id: str,
    job_type: str,
    payload: dict,
    store: Optional[AiJobStore] = None,
) -> dict:
    """ジョブを登録し、SQS enqueue または inline 実行する。

    Returns:
        作成直後のジョブレコード（202 レスポンスの元。inline の場合も
        作成時点の queued レコードを返す。フロントはポーリングで結果を得る）。
    """
    store = store or AiJobStore()
    job = store.create_job(user_id=user_id, job_type=job_type, payload=payload)
    job_id = job["job_id"]

    if _should_enqueue(job_type):
        _get_sqs_client().send_message(
            QueueUrl=_queue_url_for(job_type),
            MessageBody=json.dumps({"job_id": job_id}, ensure_ascii=False),
        )
        logger.info(
            "Enqueued AI job",
            extra={"job_id": job_id, "job_type": job_type, "user_id": user_id},
        )
    else:
        # inline モード（ローカル開発 / キュー未設定）: その場で同期実行する。
        # フロントは常にポーリングするため、1 回目の GET で completed が返る。
        logger.info(
            "Executing AI job inline",
            extra={"job_id": job_id, "job_type": job_type, "user_id": user_id},
        )
        run_job_inline(store, job_id)

    return job

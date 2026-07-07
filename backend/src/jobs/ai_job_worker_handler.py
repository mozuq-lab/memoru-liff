"""SQS worker for asynchronous AI jobs (ai-async-jobs).

AI 系 REST エンドポイントの重い処理（Bedrock 呼び出し 30〜120 秒）を API Gateway の
30 秒統合タイムアウト外で実行するワーカー。interactive / heavy の 2 キューの
イベントソースを本関数に張る（template.yaml）。

再試行の設計（設計 dataflow.md「Phase A/B/C」参照）:

- Phase A (claim): ジョブレコードの queued→processing 条件付き更新。
  条件不成立はスキップ（SQS 重複配信の吸収）。DynamoDB エラーは executor 未実行
  なので batchItemFailures に積んで SQS リトライに委ねる（安全）。
- Phase B (executor): AI/ドメインエラーは classify_ai_job_error で failed ジョブに
  記録し、SQS 上は成功扱い（リトライしない。ユーザーはフロントのタイムアウト内で
  待機しており、自動再試行は間に合わないうえ Bedrock 課金を最大 3 倍にするため）。
- Phase C (記録): executor 実行後の記録失敗は release せず batchItemFailures にも
  積まない（再実行は tutor の履歴二重追加・二重課金を招く。processing のまま
  TTL で朽ちるのを許容する）。

Phase B/C は ai_job_service.run_job_inline に集約されており、inline モード
（ローカル開発）と完全に同一のコードパスで実行される。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from services.ai_job_service import run_job_inline
from services.ai_job_store import AiJobStore

logger = Logger()
tracer = Tracer()

ai_job_store = AiJobStore()


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """SQS イベントソースのワーカーハンドラ（ReportBatchItemFailures）。

    BatchSize は 1 に設定しているが（template.yaml。バッチ内タイムアウトの
    巻き込み防止）、SQS の仕様上 Records は複数になり得るため部分バッチ失敗で
    処理する。

    Returns:
        ``{"batchItemFailures": [{"itemIdentifier": <messageId>}, ...]}``
    """
    records: List[Dict[str, Any]] = event.get("Records", [])
    logger.info(f"AI job worker received {len(records)} record(s)")

    batch_item_failures: List[Dict[str, str]] = []

    for record in records:
        message_id = record.get("messageId", "")
        raw_body = record.get("body", "")
        try:
            body = json.loads(raw_body) if isinstance(raw_body, str) else (raw_body or {})
        except (json.JSONDecodeError, TypeError) as e:
            # パース不能なメッセージはリトライ不要 → 成功扱いで削除（積まない）。
            logger.warning(
                "Skipping unparseable AI job message body",
                extra={"message_id": message_id, "error": str(e)},
            )
            continue

        job_id = body.get("job_id", "")
        if not job_id:
            logger.warning(
                "Skipping malformed AI job message (no job_id)",
                extra={"message_id": message_id},
            )
            continue

        try:
            # run_job_inline 内で claim（Phase A）→ 実行（B）→ 記録（C）まで完結する。
            # AI エラー・記録失敗は内部で処理され例外にならない。ここに届く例外は
            # claim の DynamoDB エラー等 executor 未実行のものだけであり、
            # SQS リトライに委ねて安全（設計 dataflow.md Phase A）。
            run_job_inline(ai_job_store, job_id)
        except Exception as e:
            logger.error(
                "AI job worker failed before execution; reporting batch item failure",
                extra={"message_id": message_id, "job_id": job_id, "error": str(e)},
            )
            batch_item_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_item_failures}

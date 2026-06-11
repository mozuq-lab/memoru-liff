"""SQS worker for asynchronous URL card generation (N-5).

LINE Webhook は API Gateway の 30 秒上限内に 200 を返す必要があるため、URL からの
カード生成という重い処理（最大 8 chunk × Bedrock 呼び出し）を本ワーカーに切り出し、
SQS 経由で非同期実行する。受付側（webhook Lambda）は進捗 reply を返して即 return し、
LINE 側のタイムアウト観測を解消する。

冪等の設計判断（claim タイミングと二重 push 窓）:
  SQS standard キューは at-least-once 配信のため、同一メッセージが複数回届きうる。
  本ワーカーでは「処理開始」ではなく webhook_event_id 単位の claim を取り、
  ``generate_and_push_url_cards`` 全体を try で包む。

    - claim 成功 → 本処理を実行。
    - 本処理が例外で失敗 → claim を release し、その messageId を batchItemFailures
      に入れて SQS のリトライ（maxReceiveCount 3）に委ねる。release により再配信が
      即座に再 claim できる。
    - 本処理が成功 → mark_processed で claim を ``processed`` に確定。以降の重複配信は
      try_acquire が False を返しスキップ（成功扱い）する。

  二重 push が起こりうる唯一の窓は「push は成功したが直後の mark_processed が失敗した」
  場合のみ（その後 claim が _STALE_SECONDS 経過で再 claim 可能になり再処理されると
  二度目の push が起こる）。push は本処理の最後のステップであり、この窓は極めて狭い。
  逆に push 前に失敗したケースは release により安全に再試行される（push 重複なし）。
  ＝「at-least-once で稀に二重 push、ただしカード喪失は防ぐ」という安全側の設計。
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from services.webhook_idempotency import WebhookIdempotencyService
from services.url_generation_service import generate_and_push_url_cards

logger = Logger()
tracer = Tracer()

# webhook 冪等レコードと衝突しないワーカー専用のキー名前空間。
# （受付側は webhook_event_id をそのまま、URL カードストアは URLCARDS#、本ワーカーは
#  URLGENWORK# を使うことで同一 PROCESSED_EVENTS_TABLE 上で名前空間を分離する。）
_WORKER_KEY_PREFIX = "URLGENWORK#"

# 冪等サービスを worker でも流用（同一 PROCESSED_EVENTS_TABLE / TTL 付きクレーム）。
idempotency_service = WebhookIdempotencyService()


def _worker_claim_key(webhook_event_id: str) -> str:
    """webhook_event_id をワーカー名前空間のクレームキーに変換する。"""
    return f"{_WORKER_KEY_PREFIX}{webhook_event_id}"


def _process_record(body: Dict[str, Any]) -> None:
    """1 件の SQS メッセージ本文を処理する（冪等 claim 付き）。

    Args:
        body: enqueue 時の JSON（user_id / line_user_id / url / webhook_event_id）。

    Raises:
        Exception: 本処理が失敗した場合（呼び出し側で batchItemFailures に積む）。
    """
    user_id = body.get("user_id", "")
    line_user_id = body.get("line_user_id", "")
    url = body.get("url", "")
    webhook_event_id = body.get("webhook_event_id", "")

    if not user_id or not line_user_id or not url:
        # 不正なメッセージはリトライしても解決しないので成功扱いで捨てる
        # （batchItemFailures に積まない → SQS から削除される）。
        logger.warning(
            "Skipping malformed URL-generate message",
            extra={"body": body},
        )
        return

    claim_key = _worker_claim_key(webhook_event_id) if webhook_event_id else None

    # ワーカー側冪等: 完了マーカー方式。claim 済み（processed）or 別ワーカー処理中なら
    # スキップ（成功扱い）。webhook_event_id が無い場合は dedupe 不能なので処理する。
    if claim_key and not idempotency_service.try_acquire(claim_key):
        logger.info(
            "Skipping duplicate URL-generate worker message",
            extra={"webhook_event_id": webhook_event_id},
        )
        return

    try:
        generate_and_push_url_cards(
            user_id=user_id,
            line_user_id=line_user_id,
            url=url,
        )
    except Exception:
        # 失敗時は claim を release して再配信での再 claim を許可し、例外を再送出して
        # 呼び出し側で batchItemFailures に積ませる（SQS リトライへ委譲）。
        if claim_key:
            idempotency_service.release(claim_key)
        raise

    # 本処理成功 → claim を processed に確定（以降の重複配信はスキップされる）。
    if claim_key:
        idempotency_service.mark_processed(claim_key)


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """SQS イベントソースのワーカーハンドラ（ReportBatchItemFailures）。

    SQS バッチ（Records）を 1 件ずつ処理し、失敗した messageId のみを
    ``batchItemFailures`` で返すことで、成功分は削除しつつ失敗分だけを SQS に
    リトライさせる（部分失敗）。

    Args:
        event: SQS イベント（``Records`` に複数メッセージ）。
        context: Lambda コンテキスト。

    Returns:
        ``{"batchItemFailures": [{"itemIdentifier": <messageId>}, ...]}``。
    """
    records: List[Dict[str, Any]] = event.get("Records", [])
    logger.info(f"URL-generate worker received {len(records)} record(s)")

    batch_item_failures: List[Dict[str, str]] = []

    for record in records:
        message_id = record.get("messageId", "")
        raw_body = record.get("body", "")
        try:
            body = json.loads(raw_body) if isinstance(raw_body, str) else (raw_body or {})
        except (json.JSONDecodeError, TypeError) as e:
            # パース不能なメッセージはリトライ不要 → 成功扱いで削除（積まない）。
            logger.warning(
                "Skipping unparseable SQS message body",
                extra={"message_id": message_id, "error": str(e)},
            )
            continue

        try:
            _process_record(body)
        except Exception as e:
            logger.error(
                "URL-generate worker failed; reporting batch item failure",
                extra={"message_id": message_id, "error": str(e)},
            )
            batch_item_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_item_failures}

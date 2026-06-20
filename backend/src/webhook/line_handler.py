"""LINE Webhook handler for Memoru LIFF application.

Lambda 入口（署名検証 + 冪等ループ）とイベントルーティング（message / postback）を担う。
個々のアクションの実処理は ``webhook.line_actions`` に切り出されており、本モジュールからは
後方互換のため再エクスポートする（``from webhook.line_handler import handle_save_url_cards``
や ``patch("webhook.line_handler.handle_postback")`` を維持）。
サービス singleton は ``webhook.dependencies`` 経由で参照する。
"""

import base64
import json
import os
import re
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from services.flex_messages import (
    create_error_message,
    create_link_required_message,
)
from services.line_service import (
    LineEvent,
    SignatureVerificationError,
    LineApiError,
)
from webhook import dependencies as deps
from webhook.line_actions import (
    handle_grade_action,
    handle_reveal_action,
    handle_save_url_cards,
    handle_save_url_cards_legacy,
    handle_start_action,
    handle_url_card_generation,
)

logger = Logger()
tracer = Tracer()

# 後方互換のための再エクスポート (ruff の未使用 import 検出を回避)
__all__ = [
    "handler",
    "handle_message",
    "handle_postback",
    "detect_url_in_message",
    "parse_postback_data",
    "handle_start_action",
    "handle_reveal_action",
    "handle_grade_action",
    "handle_url_card_generation",
    "handle_save_url_cards",
    "handle_save_url_cards_legacy",
]

# LIFF URL for account linking
LIFF_URL = os.environ.get("LIFF_URL", "https://liff.line.me/your-liff-id")

# URL detection pattern
_URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+",
    re.IGNORECASE,
)

# L-21: URL 末尾に紛れ込みやすい句読点・閉じ括弧（ASCII / 全角）。
# 例:「https://example.com/path).」→ 抽出 URL から末尾の ).等を除去する。
_URL_TRAILING_CHARS = ".,;:!?)]}'\"。、）｝】」』！？"


def detect_url_in_message(text: str) -> Optional[str]:
    """Detect and extract URL from message text.

    Args:
        text: Message text.

    Returns:
        Extracted URL if found, None otherwise.
        URL validation (including scheme check) is handled by validate_url().
    """
    if not text:
        return None
    match = _URL_PATTERN.search(text)
    if not match:
        return None
    # L-21: 末尾の句読点・閉じ括弧を除去し、抽出 URL と実フェッチ URL の乖離を防ぐ。
    return match.group(0).rstrip(_URL_TRAILING_CHARS)


def parse_postback_data(data: str) -> Dict[str, str]:
    """Parse postback data string into dictionary.

    Args:
        data: Postback data string like "action=start&card_id=xxx".

    Returns:
        Dictionary of parsed key-value pairs.
    """
    parsed = parse_qs(data)
    return {k: v[0] if v else "" for k, v in parsed.items()}


@tracer.capture_method
def handle_message(event: LineEvent) -> None:
    """Handle message event from LINE.

    Detects URLs in messages and triggers card generation.

    Args:
        event: Parsed LINE event with message_text attribute.
    """
    message_text = getattr(event, "message_text", None) or ""
    if not message_text or not event.reply_token:
        return

    # Check for URL
    url = detect_url_in_message(message_text)
    if not url:
        return

    # Get user ID from LINE user ID
    user_id = deps.line_service.get_user_id_from_line(event.source_user_id)

    if not user_id:
        logger.info(f"User not linked: {event.source_user_id}")
        message = create_link_required_message(LIFF_URL)
        deps.line_service.reply_message(event.reply_token, [message])
        return

    # Trigger URL card generation (受付 → ディスパッチ)。
    # webhook_event_id はワーカー側冪等のために enqueue 時に同梱する。
    handle_url_card_generation(
        user_id=user_id,
        line_user_id=event.source_user_id,
        url=url,
        reply_token=event.reply_token,
        webhook_event_id=event.webhook_event_id,
    )


@tracer.capture_method
def handle_postback(event: LineEvent) -> None:
    """Handle postback event from LINE.

    Args:
        event: Parsed LINE event.
    """
    if not event.postback_data or not event.reply_token:
        logger.warning("Missing postback data or reply token")
        return

    # Parse postback data
    data = parse_postback_data(event.postback_data)
    action = data.get("action", "")

    logger.info(f"Processing postback action: {action}")

    # Get user ID from LINE user ID
    user_id = deps.line_service.get_user_id_from_line(event.source_user_id)

    if not user_id:
        # User not linked - send link required message
        logger.info(f"User not linked: {event.source_user_id}")
        message = create_link_required_message(LIFF_URL)
        deps.line_service.reply_message(event.reply_token, [message])
        return

    # Route to appropriate handler
    try:
        if action == "start":
            handle_start_action(user_id, event.source_user_id, event.reply_token)
        elif action == "reveal":
            card_id = data.get("card_id", "")
            if card_id:
                handle_reveal_action(user_id, card_id, event.reply_token)
            else:
                logger.warning("Missing card_id in reveal action")
                deps.line_service.reply_message(event.reply_token, [create_error_message()])
        elif action == "grade":
            card_id = data.get("card_id", "")
            grade_str = data.get("grade", "")
            if card_id and grade_str.isdigit():
                grade = int(grade_str)
                if 0 <= grade <= 5:
                    handle_grade_action(user_id, card_id, grade, event.reply_token)
                else:
                    logger.warning(f"Invalid grade value: {grade}")
                    deps.line_service.reply_message(event.reply_token, [create_error_message()])
            else:
                logger.warning(f"Invalid grade action data: {data}")
                deps.line_service.reply_message(event.reply_token, [create_error_message()])
        elif action == "save_url_cards":
            ref_key = data.get("ref", "")
            if ref_key:
                # C-3: new reference-key flow (no re-generation).
                handle_save_url_cards(
                    user_id, event.source_user_id, ref_key, event.reply_token
                )
            else:
                # Backward-compat: old-format postbacks still carry url=.
                url = unquote(data.get("url", ""))
                count_str = data.get("count", "10")
                # M-22: postback の count は外部入力。上限・下限で clamp して
                # 想定外の target_count（巨大値や 0）が下流の生成処理に渡るのを防ぐ。
                count = int(count_str) if count_str.isdigit() else 10
                count = max(1, min(count, 50))
                if url:
                    handle_save_url_cards_legacy(
                        user_id, event.source_user_id, url, count, event.reply_token
                    )
                else:
                    logger.warning("Missing ref/url in save_url_cards action")
                    deps.line_service.reply_message(
                        event.reply_token, [create_error_message()]
                    )
        else:
            logger.warning(f"Unknown action: {action}")
            deps.line_service.reply_message(
                event.reply_token,
                [{"type": "text", "text": "不明なアクションです。"}],
            )
    except LineApiError as e:
        # L-18: LINE API エラー（reply 失敗・rate limit 等）はここで握りつぶし、
        # 呼び出し元の handler ループでは成功扱い（mark_processed）とする。
        # これは意図的な設計判断:
        #   - reply token の有効期限は数秒と短く、LINE が再配信しても同じ token は
        #     既に失効しているため再 reply は成功しない（release しても無駄）。
        #   - grade アクションは submit_review（非冪等な SRS 更新）を先に実行済みで、
        #     reply だけが失敗するケースがある。ここで release して LINE に再配信
        #     させると submit_review が二重実行され、SRS 状態が壊れる方が有害。
        # よって「reply 失敗 = アクション本体は完了済み」とみなし mark_processed
        # に倒す。本当にアクション本体まで失敗するケースは LineApiError ではなく
        # 個別の例外（CardNotFoundError 等）として各ハンドラ内で処理される。
        logger.error(f"LINE API error: {e}")


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler for LINE webhook.

    Args:
        event: API Gateway event.
        context: Lambda context.

    Returns:
        API Gateway response.
    """
    logger.info("Received LINE webhook")

    # Get request body and signature
    body = event.get("body", "")

    # C-1: Handle base64-encoded body from API Gateway
    if event.get("isBase64Encoded", False) and body:
        try:
            body = base64.b64decode(body).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to decode base64 body: {e}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid request body encoding"}),
            }

    headers = event.get("headers", {})

    # Normalize header names (case-insensitive)
    signature = headers.get("x-line-signature") or headers.get("X-Line-Signature", "")

    if not signature:
        logger.warning("Missing X-Line-Signature header")
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Missing signature"}),
        }

    # Verify signature
    try:
        if not deps.line_service.verify_request(body, signature):
            logger.warning("Signature verification failed")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid signature"}),
            }
    except SignatureVerificationError as e:
        # L-20: channel_secret 未設定など設定ミス時は fail-closed で 500 を返すが、
        # レスポンスボディには内部のエラー名称を載せず汎用文言に留める
        # （攻撃者にサービス設定ミスを示唆しない）。詳細はログにのみ残す。
        logger.error(f"Signature verification error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal server error"}),
        }

    # Parse and process events
    events = deps.line_service.parse_events(body)

    for line_event in events:
        event_id = line_event.webhook_event_id
        # Idempotency guard (N-6): LINE delivers at-least-once and may redeliver
        # events (incl. after a failed attempt). Claim before processing, confirm
        # `processed` only on success, and release the claim on failure so LINE's
        # redelivery can retry instead of being silently skipped.
        if not deps.idempotency_service.try_acquire(event_id):
            logger.info("Skipping duplicate webhook event", extra={"event_id": event_id})
            continue

        logger.info(f"Processing event: {line_event.event_type}")
        try:
            if line_event.event_type == "postback":
                handle_postback(line_event)
            elif line_event.event_type == "message":
                handle_message(line_event)
            else:
                logger.info(f"Ignoring event type: {line_event.event_type}")
            deps.idempotency_service.mark_processed(event_id)
        except Exception as e:
            logger.error(f"Error handling event: {e}")
            deps.idempotency_service.release(event_id)

    # LINE expects 200 response
    return {
        "statusCode": 200,
        "body": "",
    }

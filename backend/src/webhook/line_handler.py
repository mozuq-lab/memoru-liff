"""LINE Webhook handler for Memoru LIFF application."""

import base64
import json
import os
import re
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote

import boto3
from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from services.line_service import (
    LineService,
    LineEvent,
    SignatureVerificationError,
    LineApiError,
)
from services.flex_messages import (
    create_question_message,
    create_answer_message,
    create_no_cards_message,
    create_link_required_message,
    create_error_message,
    create_url_generation_progress_message,
    create_url_generation_error_message,
)
from models.card import Reference
from services.card_service import CardService, CardNotFoundError
from services.review_service import ReviewService
from services.url_content_service import UrlContentService
from services.content_chunker import chunk_content
from services.ai_service import create_ai_service
from services.webhook_idempotency import WebhookIdempotencyService
from services.url_cards_store import UrlCardsStore
from services.url_generation_service import generate_and_push_url_cards
from utils.url_validator import validate_url, UrlValidationError

logger = Logger()
tracer = Tracer()

# Initialize services
line_service = LineService()
card_service = CardService()
review_service = ReviewService()
idempotency_service = WebhookIdempotencyService()
url_cards_store = UrlCardsStore()

# LIFF URL for account linking
LIFF_URL = os.environ.get("LIFF_URL", "https://liff.line.me/your-liff-id")

# N-5: URL カード生成の非同期化。
# 受付（本 webhook Lambda）は進捗 reply まで行い、重い生成本体は SQS へ enqueue して
# 即 return することで API Gateway の 30 秒上限による LINE 側タイムアウトを解消する。
# URL_GENERATE_QUEUE_URL が設定され、かつ URL_WORKER_MODE != "inline" のときのみ enqueue。
# それ以外（ローカル開発・テスト・enqueue 失敗時のフォールバック）は従来どおりその場で
# 同期実行する（インラインフォールバック。動作は現行と同一）。
# NOTE(ローカル): sam local は SQS → Lambda トリガーを再現できないため、env.json で
# URL_WORKER_MODE="inline" を設定し、ローカルは常に同期実行する。
URL_GENERATE_QUEUE_URL = os.environ.get("URL_GENERATE_QUEUE_URL", "")
URL_WORKER_MODE = os.environ.get("URL_WORKER_MODE", "")

# Lazy 初期化（インラインのみの環境では SQS クライアントを生成しない）。
_sqs_client = None


def _get_sqs_client() -> Any:
    """SQS クライアントを遅延生成して返す。"""
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs")
    return _sqs_client


def _should_enqueue() -> bool:
    """URL カード生成を SQS ワーカーへ非同期ディスパッチすべきか判定する。

    Returns:
        True  — キュー URL があり、かつ inline モードでない（→ enqueue）。
        False — それ以外（→ その場で同期実行＝インラインフォールバック）。
    """
    return bool(URL_GENERATE_QUEUE_URL) and URL_WORKER_MODE != "inline"

# URL detection pattern
_URL_PATTERN = re.compile(
    r"https?://[^\s<>\"']+",
    re.IGNORECASE,
)


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
    return match.group(0)


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
def handle_start_action(
    user_id: str,
    line_user_id: str,
    reply_token: str,
) -> None:
    """Handle 'start' postback action - begin review session.

    Args:
        user_id: System user ID.
        line_user_id: LINE user ID.
        reply_token: Reply token for response.
    """
    logger.info(f"Starting review session for user: {user_id}")

    # Get due cards
    due_response = review_service.get_due_cards(user_id, limit=1)

    if not due_response.due_cards:
        # No cards due
        line_service.reply_message(reply_token, [create_no_cards_message()])
        return

    # Send first card
    card = due_response.due_cards[0]
    message = create_question_message(card.card_id, card.front)
    line_service.reply_message(reply_token, [message])


@tracer.capture_method
def handle_reveal_action(
    user_id: str,
    card_id: str,
    reply_token: str,
) -> None:
    """Handle 'reveal' postback action - show answer.

    Args:
        user_id: System user ID.
        card_id: Card ID to reveal.
        reply_token: Reply token for response.
    """
    logger.info(f"Revealing answer for card: {card_id}")

    try:
        card = card_service.get_card(user_id, card_id)
        message = create_answer_message(card.card_id, card.front, card.back)
        line_service.reply_message(reply_token, [message])
    except CardNotFoundError:
        logger.warning(f"Card not found: {card_id}")
        line_service.reply_message(reply_token, [create_error_message()])


@tracer.capture_method
def handle_grade_action(
    user_id: str,
    card_id: str,
    grade: int,
    reply_token: str,
) -> None:
    """Handle 'grade' postback action - record review result.

    Args:
        user_id: System user ID.
        card_id: Card ID being reviewed.
        grade: Review grade (0-5).
        reply_token: Reply token for response.
    """
    logger.info(f"Recording grade {grade} for card: {card_id}")

    try:
        # Submit review
        review_service.submit_review(user_id, card_id, grade)

        # Get next due card
        due_response = review_service.get_due_cards(user_id, limit=1)

        if due_response.due_cards:
            # Send next card
            next_card = due_response.due_cards[0]
            message = create_question_message(next_card.card_id, next_card.front)
            line_service.reply_message(reply_token, [message])
        else:
            # No more cards - session complete
            # Use due_response.total_due_count as a proxy for reviewed count
            # since we don't track session-level review count
            line_service.reply_message(
                reply_token,
                [{"type": "text", "text": "🎊 本日の復習が完了しました！お疲れさまです！"}],
            )

    except CardNotFoundError:
        logger.warning(f"Card not found: {card_id}")
        line_service.reply_message(reply_token, [create_error_message()])
    except Exception as e:
        logger.error(f"Error processing grade: {e}")
        line_service.reply_message(reply_token, [create_error_message()])


@tracer.capture_method
def handle_url_card_generation(
    user_id: str,
    line_user_id: str,
    url: str,
    reply_token: str,
    webhook_event_id: Optional[str] = None,
) -> None:
    """Handle URL card generation from LINE chat (N-5: receive + dispatch).

    受付側の責務はバリデーション → 進捗 reply → ディスパッチに簡素化されている。
    重い生成本体（取得 → chunk → Bedrock → 保存 → push）は
    ``services.url_generation_service.generate_and_push_url_cards`` に切り出され、
    SQS ワーカーで非同期実行される（インラインフォールバックも可能）。

    Args:
        user_id: System user ID.
        line_user_id: LINE user ID.
        url: URL to generate cards from.
        reply_token: Reply token for response (進捗メッセージでここで消費する)。
        webhook_event_id: ワーカー側冪等に使う LINE webhookEventId（enqueue 時に同梱）。
    """
    logger.info(f"Dispatching URL card generation for user: {user_id}, url: {url}")

    # Validate URL before processing (M-1: SSRF prevention)
    try:
        url = validate_url(url)
    except UrlValidationError as e:
        logger.warning(f"URL validation failed: {e}")
        line_service.reply_message(
            reply_token,
            [create_url_generation_error_message(
                f"無効なURLです: {e}"
            )],
        )
        return

    # Send progress message first (reply token はここで消費される)。
    try:
        line_service.reply_message(
            reply_token,
            [create_url_generation_progress_message(url)],
        )
    except LineApiError:
        logger.warning("Failed to send progress message")

    # ディスパッチ: 非同期（SQS）かインライン（同期）か。
    if _should_enqueue():
        try:
            _enqueue_url_generation(
                user_id=user_id,
                line_user_id=line_user_id,
                url=url,
                webhook_event_id=webhook_event_id or "",
            )
            return
        except Exception as e:
            # enqueue 失敗時はインラインへフォールバック（受付は決して落とさない）。
            logger.warning(
                f"Failed to enqueue URL generation; falling back to inline: {e}"
            )

    # インラインフォールバック（ローカル・テスト・enqueue 失敗）: その場で同期実行。
    generate_and_push_url_cards(
        user_id=user_id,
        line_user_id=line_user_id,
        url=url,
    )


def _enqueue_url_generation(
    user_id: str,
    line_user_id: str,
    url: str,
    webhook_event_id: str,
) -> None:
    """URL カード生成リクエストを SQS ワーカーキューへ送信する。

    Args:
        user_id: System user ID.
        line_user_id: LINE user ID.
        url: 生成元 URL（バリデーション済み）。
        webhook_event_id: ワーカー側冪等用の LINE webhookEventId。
    """
    payload = {
        "user_id": user_id,
        "line_user_id": line_user_id,
        "url": url,
        "webhook_event_id": webhook_event_id,
    }
    _get_sqs_client().send_message(
        QueueUrl=URL_GENERATE_QUEUE_URL,
        MessageBody=json.dumps(payload, ensure_ascii=False),
    )
    logger.info(
        "Enqueued URL card generation",
        extra={"user_id": user_id, "webhook_event_id": webhook_event_id},
    )


@tracer.capture_method
def handle_save_url_cards(
    user_id: str,
    line_user_id: str,
    ref_key: str,
    reply_token: str,
) -> None:
    """Handle save URL cards postback action (C-3 reference-key flow).

    Loads the previously-generated cards from UrlCardsStore by ref_key and
    saves them as-is — WITHOUT re-fetching the URL or re-invoking Bedrock.
    This keeps the saved cards identical to the preview and avoids double
    AI cost. user_id is resolved from the webhook event, not the postback.

    Args:
        user_id: System user ID (resolved from the LINE user in handle_postback).
        line_user_id: LINE user ID.
        ref_key: Reference key into UrlCardsStore.
        reply_token: Reply token for response.
    """
    logger.info(f"Saving URL cards for user: {user_id}, ref_key: {ref_key}")

    pending = url_cards_store.get_pending_cards(ref_key)
    if not pending or not pending.get("cards"):
        # Record missing or TTL-expired.
        line_service.reply_message(
            reply_token,
            [{
                "type": "text",
                "text": "有効期限が切れました。もう一度 URL を送信してください。",
            }],
        )
        return

    # Two-tap / double-save guard: only the first tap proceeds.
    if not url_cards_store.mark_saved(ref_key):
        logger.info(f"URL cards already saved for ref_key: {ref_key}")
        line_service.reply_message(
            reply_token,
            [{"type": "text", "text": "このカードは既に保存済みです。"}],
        )
        return

    page_url = pending.get("page_url", "")
    cards = pending.get("cards", [])

    references = [Reference(type="url", value=page_url)] if page_url else []

    saved_count = 0
    for card in cards:
        front = str(card.get("front", "")).strip()
        back = str(card.get("back", "")).strip()
        if not front or not back:
            continue
        tags = card.get("suggested_tags") or card.get("tags") or []
        try:
            card_service.create_card(
                user_id=user_id,
                front=front,
                back=back,
                tags=tags,
                references=references,
            )
            saved_count += 1
        except Exception as e:
            logger.warning(f"Failed to save card: {e}")

    line_service.reply_message(
        reply_token,
        [{"type": "text", "text": f"✅ {saved_count}枚のカードを保存しました！"}],
    )


@tracer.capture_method
def handle_save_url_cards_legacy(
    user_id: str,
    line_user_id: str,
    url: str,
    count: int,
    reply_token: str,
) -> None:
    """Legacy save flow for old-format postbacks (``url=`` param).

    Pre-C-3 carousels embedded the URL in the postback and re-generated cards
    on save. Such postbacks may still arrive across a deploy boundary, so this
    fallback re-fetches + re-generates as before.

    Args:
        user_id: System user ID.
        line_user_id: LINE user ID.
        url: Source URL.
        count: Number of cards to save.
        reply_token: Reply token for response.
    """
    logger.info(f"Saving URL cards (legacy) for user: {user_id}, url: {url}")

    # Validate URL before processing (C-2: SSRF prevention)
    try:
        url = validate_url(url)
    except UrlValidationError as e:
        logger.warning(f"URL validation failed in save_url_cards: {e}")
        line_service.reply_message(
            reply_token,
            [create_url_generation_error_message(f"無効なURLです: {e}")],
        )
        return

    try:
        # Re-fetch and generate
        content_service = UrlContentService()
        page = content_service.fetch_content(url)

        chunks = chunk_content(page.text_content, page_title=page.title)
        chunk_texts = [c.text for c in chunks]

        if not chunk_texts:
            line_service.reply_message(
                reply_token,
                [create_url_generation_error_message("テキストを抽出できませんでした。")],
            )
            return

        ai_service = create_ai_service()
        result = ai_service.generate_cards_from_chunks(
            chunks=chunk_texts,
            card_type="qa",
            target_count=count,
            difficulty="medium",
            language="ja",
            page_title=page.title,
        )

        # Save each card
        saved_count = 0
        for card in result.cards[:count]:
            try:
                card_service.create_card(
                    user_id=user_id,
                    front=card.front,
                    back=card.back,
                    tags=card.suggested_tags,
                    references=[Reference(type="url", value=page.url)],
                )
                saved_count += 1
            except Exception as e:
                logger.warning(f"Failed to save card: {e}")

        line_service.reply_message(
            reply_token,
            [{"type": "text", "text": f"✅ {saved_count}枚のカードを保存しました！"}],
        )

    except Exception as e:
        logger.error(f"Error saving URL cards: {e}")
        line_service.reply_message(
            reply_token,
            [create_error_message()],
        )


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
    user_id = line_service.get_user_id_from_line(event.source_user_id)

    if not user_id:
        logger.info(f"User not linked: {event.source_user_id}")
        message = create_link_required_message(LIFF_URL)
        line_service.reply_message(event.reply_token, [message])
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
    user_id = line_service.get_user_id_from_line(event.source_user_id)

    if not user_id:
        # User not linked - send link required message
        logger.info(f"User not linked: {event.source_user_id}")
        message = create_link_required_message(LIFF_URL)
        line_service.reply_message(event.reply_token, [message])
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
                line_service.reply_message(event.reply_token, [create_error_message()])
        elif action == "grade":
            card_id = data.get("card_id", "")
            grade_str = data.get("grade", "")
            if card_id and grade_str.isdigit():
                grade = int(grade_str)
                if 0 <= grade <= 5:
                    handle_grade_action(user_id, card_id, grade, event.reply_token)
                else:
                    logger.warning(f"Invalid grade value: {grade}")
                    line_service.reply_message(event.reply_token, [create_error_message()])
            else:
                logger.warning(f"Invalid grade action data: {data}")
                line_service.reply_message(event.reply_token, [create_error_message()])
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
                count = int(count_str) if count_str.isdigit() else 10
                if url:
                    handle_save_url_cards_legacy(
                        user_id, event.source_user_id, url, count, event.reply_token
                    )
                else:
                    logger.warning("Missing ref/url in save_url_cards action")
                    line_service.reply_message(
                        event.reply_token, [create_error_message()]
                    )
        else:
            logger.warning(f"Unknown action: {action}")
            line_service.reply_message(
                event.reply_token,
                [{"type": "text", "text": "不明なアクションです。"}],
            )
    except LineApiError as e:
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
        if not line_service.verify_request(body, signature):
            logger.warning("Signature verification failed")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid signature"}),
            }
    except SignatureVerificationError as e:
        logger.error(f"Signature verification error: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Signature verification error"}),
        }

    # Parse and process events
    events = line_service.parse_events(body)

    for line_event in events:
        event_id = line_event.webhook_event_id
        # Idempotency guard (N-6): LINE delivers at-least-once and may redeliver
        # events (incl. after a failed attempt). Claim before processing, confirm
        # `processed` only on success, and release the claim on failure so LINE's
        # redelivery can retry instead of being silently skipped.
        if not idempotency_service.try_acquire(event_id):
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
            idempotency_service.mark_processed(event_id)
        except Exception as e:
            logger.error(f"Error handling event: {e}")
            idempotency_service.release(event_id)

    # LINE expects 200 response
    return {
        "statusCode": 200,
        "body": "",
    }

"""LINE Webhook handler for Memoru LIFF application."""

import base64
import json
import os
import re
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, unquote

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
    create_card_preview_carousel,
    create_url_generation_error_message,
)
from models.card import Reference
from services.card_service import CardService, CardNotFoundError
from services.review_service import ReviewService
from services.url_content_service import UrlContentService, ContentFetchError
from services.content_chunker import chunk_content
from services.ai_service import create_ai_service, AIServiceError
from utils.url_validator import validate_url, UrlValidationError

logger = Logger()
tracer = Tracer()

# Initialize services
line_service = LineService()
card_service = CardService()
review_service = ReviewService()

# LIFF URL for account linking
LIFF_URL = os.environ.get("LIFF_URL", "https://liff.line.me/your-liff-id")

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
) -> None:
    """Handle URL card generation from LINE chat.

    Fetches content → generates cards → sends carousel preview.

    Args:
        user_id: System user ID.
        line_user_id: LINE user ID.
        url: URL to generate cards from.
        reply_token: Reply token for response.
    """
    logger.info(f"Generating cards from URL for user: {user_id}, url: {url}")

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

    # Send progress message first
    try:
        line_service.reply_message(
            reply_token,
            [create_url_generation_progress_message(url)],
        )
    except LineApiError:
        logger.warning("Failed to send progress message")

    try:
        # Fetch content
        content_service = UrlContentService()
        page = content_service.fetch_content(url)

        # Chunk content
        chunks = chunk_content(page.text_content, page_title=page.title)
        chunk_texts = [c.text for c in chunks]

        if not chunk_texts:
            line_service.push_message(
                line_user_id,
                [create_url_generation_error_message(
                    "ページからテキストを抽出できませんでした。"
                )],
            )
            return

        # Generate cards
        ai_service = create_ai_service()
        result = ai_service.generate_cards_from_chunks(
            chunks=chunk_texts,
            card_type="qa",
            target_count=10,
            difficulty="medium",
            language="ja",
            page_title=page.title,
        )

        if not result.cards:
            line_service.push_message(
                line_user_id,
                [create_url_generation_error_message(
                    "カードを生成できませんでした。"
                )],
            )
            return

        # Build card data for carousel
        cards_data = [
            {
                "front": card.front,
                "back": card.back,
                "tags": card.suggested_tags,
            }
            for card in result.cards
        ]

        # Send carousel with card previews
        carousel = create_card_preview_carousel(
            cards=cards_data,
            page_title=page.title,
            page_url=page.url,
            user_id=user_id,
        )
        line_service.push_message(line_user_id, [carousel])

        logger.info(
            f"URL card generation complete: {len(result.cards)} cards, "
            f"url={url}"
        )

    except ContentFetchError as e:
        logger.warning(f"Content fetch error: {e}")
        line_service.push_message(
            line_user_id,
            [create_url_generation_error_message(str(e))],
        )
    except AIServiceError as e:
        logger.error(f"AI service error: {e}")
        line_service.push_message(
            line_user_id,
            [create_url_generation_error_message(
                "AI処理中にエラーが発生しました。"
            )],
        )
    except Exception as e:
        logger.error(f"Unexpected error in URL card generation: {e}")
        line_service.push_message(
            line_user_id,
            [create_error_message()],
        )


@tracer.capture_method
def handle_save_url_cards(
    user_id: str,
    line_user_id: str,
    url: str,
    count: int,
    reply_token: str,
) -> None:
    """Handle save URL cards postback action.

    Re-generates and saves cards from the URL.

    Args:
        user_id: System user ID.
        line_user_id: LINE user ID.
        url: Source URL.
        count: Number of cards to save.
        reply_token: Reply token for response.
    """
    logger.info(f"Saving URL cards for user: {user_id}, url: {url}")

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

    # Trigger URL card generation
    handle_url_card_generation(
        user_id=user_id,
        line_user_id=event.source_user_id,
        url=url,
        reply_token=event.reply_token,
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
            url = unquote(data.get("url", ""))
            count_str = data.get("count", "10")
            count = int(count_str) if count_str.isdigit() else 10
            if url:
                handle_save_url_cards(
                    user_id, event.source_user_id, url, count, event.reply_token
                )
            else:
                logger.warning("Missing url in save_url_cards action")
                line_service.reply_message(event.reply_token, [create_error_message()])
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
        logger.info(f"Processing event: {line_event.event_type}")

        if line_event.event_type == "postback":
            try:
                handle_postback(line_event)
            except Exception as e:
                logger.error(f"Error handling postback: {e}")
        elif line_event.event_type == "message":
            try:
                handle_message(line_event)
            except Exception as e:
                logger.error(f"Error handling message: {e}")
        else:
            logger.info(f"Ignoring event type: {line_event.event_type}")

    # LINE expects 200 response
    return {
        "statusCode": 200,
        "body": "",
    }

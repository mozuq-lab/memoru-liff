"""LINE Webhook handler for Memoru LIFF application."""

import json
import os
from typing import Any, Dict, Optional
from urllib.parse import parse_qs

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from ..services.line_service import (
    LineService,
    LineEvent,
    SignatureVerificationError,
    LineApiError,
)
from ..services.flex_messages import (
    create_question_message,
    create_answer_message,
    create_no_cards_message,
    create_completion_message,
    create_link_required_message,
    create_error_message,
)
from ..services.card_service import CardService, CardNotFoundError
from ..services.review_service import ReviewService

logger = Logger()
tracer = Tracer()

# Initialize services
line_service = LineService()
card_service = CardService()
review_service = ReviewService()

# LIFF URL for account linking
LIFF_URL = os.environ.get("LIFF_URL", "https://liff.line.me/your-liff-id")


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
            # Count is approximate since we don't track session
            message = create_completion_message(1)
            line_service.reply_message(reply_token, [message])

    except CardNotFoundError:
        logger.warning(f"Card not found: {card_id}")
        line_service.reply_message(reply_token, [create_error_message()])
    except Exception as e:
        logger.error(f"Error processing grade: {e}")
        line_service.reply_message(reply_token, [create_error_message()])


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
        else:
            logger.info(f"Ignoring event type: {line_event.event_type}")

    # LINE expects 200 response
    return {
        "statusCode": 200,
        "body": "",
    }

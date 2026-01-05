"""Lambda handler for scheduled review reminder push notifications."""

import json
from datetime import datetime, timezone
from typing import Any, Dict

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.utilities.typing import LambdaContext

from ..services.notification_service import NotificationService

logger = Logger()
tracer = Tracer()

# Initialize service
notification_service = NotificationService()


@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Lambda handler for due push notifications.

    This handler is triggered by EventBridge Scheduler (daily at 9:00 AM JST)
    to send review reminders to users with due cards.

    Args:
        event: EventBridge event (typically empty for scheduled events).
        context: Lambda context.

    Returns:
        Response with processing statistics.
    """
    logger.info("Starting due push job")

    # Use current UTC time
    current_time = datetime.now(timezone.utc)
    logger.info(f"Processing for time: {current_time.isoformat()}")

    # Process notifications
    result = notification_service.process_notifications(current_time)

    # Prepare response
    response_body = {
        "processed_users": result.processed,
        "sent_notifications": result.sent,
        "skipped_users": result.skipped,
        "error_count": len(result.errors),
    }

    # Log errors summary if any
    if result.errors:
        logger.warning(f"Notification errors: {json.dumps(result.errors)}")

    logger.info(f"Due push job complete: {json.dumps(response_body)}")

    return {
        "statusCode": 200,
        "body": json.dumps(response_body),
    }

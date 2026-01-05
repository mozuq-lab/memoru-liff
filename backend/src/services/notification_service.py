"""Notification service for sending review reminders."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from aws_lambda_powertools import Logger

from .user_service import UserService
from .card_service import CardService
from .line_service import LineService, LineApiError
from .flex_messages import create_reminder_message

logger = Logger()


@dataclass
class NotificationResult:
    """Result of notification processing."""

    processed: int = 0
    sent: int = 0
    skipped: int = 0
    errors: List[dict] = field(default_factory=list)


class NotificationService:
    """Service for sending review reminder notifications."""

    def __init__(
        self,
        user_service: Optional[UserService] = None,
        card_service: Optional[CardService] = None,
        line_service: Optional[LineService] = None,
    ):
        """Initialize NotificationService.

        Args:
            user_service: UserService instance.
            card_service: CardService instance.
            line_service: LineService instance.
        """
        self.user_service = user_service or UserService()
        self.card_service = card_service or CardService()
        self.line_service = line_service or LineService()

    def process_notifications(self, current_time: datetime) -> NotificationResult:
        """Process and send notifications to all eligible users.

        Args:
            current_time: Current time for determining due cards.

        Returns:
            NotificationResult with processing statistics.
        """
        result = NotificationResult()
        today_str = current_time.strftime("%Y-%m-%d")

        logger.info(f"Starting notification processing for {today_str}")

        # Get all LINE-linked users
        try:
            linked_users = self.user_service.get_linked_users()
            logger.info(f"Found {len(linked_users)} linked users")
        except Exception as e:
            logger.error(f"Failed to get linked users: {e}")
            result.errors.append({
                "type": "get_users_failed",
                "error": str(e),
            })
            return result

        # Process each user
        for user in linked_users:
            result.processed += 1

            try:
                # Check if already notified today
                if user.last_notified_date == today_str:
                    logger.debug(f"User {user.user_id} already notified today")
                    result.skipped += 1
                    continue

                # Check if user has due cards
                due_count = self.card_service.get_due_card_count(
                    user.user_id, before=current_time
                )

                if due_count == 0:
                    logger.debug(f"User {user.user_id} has no due cards")
                    result.skipped += 1
                    continue

                # Send push message
                message = create_reminder_message(due_count)
                self.line_service.push_message(user.line_user_id, [message])

                # Update last notified date
                self.user_service.update_last_notified_date(user.user_id, today_str)

                result.sent += 1
                logger.info(
                    f"Sent notification to user {user.user_id}: {due_count} cards due"
                )

            except LineApiError as e:
                # LINE API error (e.g., user blocked the bot)
                logger.warning(f"Failed to send to user {user.user_id}: {e}")
                result.errors.append({
                    "user_id": user.user_id,
                    "line_user_id": user.line_user_id[:8] + "..." if user.line_user_id else None,
                    "error_type": "line_api_error",
                    "error": str(e),
                })
            except Exception as e:
                # Other errors
                logger.error(f"Error processing user {user.user_id}: {e}")
                result.errors.append({
                    "user_id": user.user_id,
                    "error_type": type(e).__name__,
                    "error": str(e),
                })

        logger.info(
            f"Notification processing complete: "
            f"processed={result.processed}, sent={result.sent}, "
            f"skipped={result.skipped}, errors={len(result.errors)}"
        )

        return result

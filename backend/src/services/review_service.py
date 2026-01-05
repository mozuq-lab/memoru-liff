"""Review service for managing card reviews."""

import os
from datetime import datetime, timezone
from typing import List, Optional

import boto3
from botocore.exceptions import ClientError

from ..models.card import Card
from ..models.review import (
    DueCardInfo,
    DueCardsResponse,
    ReviewPreviousState,
    ReviewResponse,
    ReviewUpdatedState,
)
from .card_service import CardNotFoundError, CardService, CardServiceError
from .srs import ReviewHistoryEntry, SM2Result, add_review_history, calculate_sm2


class ReviewServiceError(Exception):
    """Base exception for review service errors."""

    pass


class InvalidGradeError(ReviewServiceError):
    """Raised when grade is invalid."""

    pass


class ReviewService:
    """Service for managing card reviews and SRS calculations."""

    def __init__(
        self,
        cards_table_name: Optional[str] = None,
        reviews_table_name: Optional[str] = None,
        dynamodb_resource=None,
    ):
        """Initialize ReviewService.

        Args:
            cards_table_name: DynamoDB cards table name.
            reviews_table_name: DynamoDB reviews table name.
            dynamodb_resource: Optional boto3 DynamoDB resource for testing.
        """
        self.cards_table_name = cards_table_name or os.environ.get(
            "CARDS_TABLE", "memoru-cards-dev"
        )
        self.reviews_table_name = reviews_table_name or os.environ.get(
            "REVIEWS_TABLE", "memoru-reviews-dev"
        )

        if dynamodb_resource:
            self.dynamodb = dynamodb_resource
        else:
            endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
            if endpoint_url:
                self.dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)
            else:
                self.dynamodb = boto3.resource("dynamodb")

        self.cards_table = self.dynamodb.Table(self.cards_table_name)
        self.reviews_table = self.dynamodb.Table(self.reviews_table_name)
        self.card_service = CardService(
            table_name=self.cards_table_name,
            dynamodb_resource=dynamodb_resource,
        )

    def submit_review(
        self,
        user_id: str,
        card_id: str,
        grade: int,
    ) -> ReviewResponse:
        """Submit a review for a card and update SRS parameters.

        Args:
            user_id: The user's ID.
            card_id: The card's ID.
            grade: Review grade (0-5).

        Returns:
            ReviewResponse with previous and updated states.

        Raises:
            CardNotFoundError: If card does not exist or belongs to another user.
            InvalidGradeError: If grade is not in range 0-5.
        """
        if not 0 <= grade <= 5:
            raise InvalidGradeError(f"Grade must be between 0 and 5, got {grade}")

        # Get the card (also verifies ownership)
        card = self.card_service.get_card(user_id, card_id)

        # Store previous state
        previous = ReviewPreviousState(
            ease_factor=card.ease_factor,
            interval=card.interval,
            repetitions=card.repetitions,
            due_date=card.next_review_at.date().isoformat() if card.next_review_at else None,
        )

        # Calculate new SRS parameters
        result = calculate_sm2(
            grade=grade,
            repetitions=card.repetitions,
            ease_factor=card.ease_factor,
            interval=card.interval,
        )

        # Update card with new parameters
        now = datetime.now(timezone.utc)
        self._update_card_review_data(
            user_id=user_id,
            card_id=card_id,
            result=result,
            grade=grade,
            previous_ease_factor=card.ease_factor,
            previous_interval=card.interval,
        )

        # Record review in reviews table
        self._record_review(
            user_id=user_id,
            card_id=card_id,
            grade=grade,
            reviewed_at=now,
            ease_factor_before=card.ease_factor,
            ease_factor_after=result.ease_factor,
            interval_before=card.interval,
            interval_after=result.interval,
        )

        updated = ReviewUpdatedState(
            ease_factor=result.ease_factor,
            interval=result.interval,
            repetitions=result.repetitions,
            due_date=result.next_review_at.date().isoformat(),
        )

        return ReviewResponse(
            card_id=card_id,
            grade=grade,
            previous=previous,
            updated=updated,
            reviewed_at=now,
        )

    def _update_card_review_data(
        self,
        user_id: str,
        card_id: str,
        result: SM2Result,
        grade: int,
        previous_ease_factor: float,
        previous_interval: int,
    ) -> None:
        """Update card's SRS data and review history.

        Args:
            user_id: The user's ID.
            card_id: The card's ID.
            result: SM2 calculation result.
            grade: Review grade.
            previous_ease_factor: Ease factor before review.
            previous_interval: Interval before review.
        """
        now = datetime.now(timezone.utc)

        # Get existing review history
        try:
            response = self.cards_table.get_item(
                Key={"user_id": user_id, "card_id": card_id},
                ProjectionExpression="review_history",
            )
            existing_history = response.get("Item", {}).get("review_history", [])
        except ClientError:
            existing_history = []

        # Add new history entry
        history_entry = ReviewHistoryEntry(
            reviewed_at=now,
            grade=grade,
            ease_factor_before=previous_ease_factor,
            ease_factor_after=result.ease_factor,
            interval_before=previous_interval,
            interval_after=result.interval,
        )
        updated_history = add_review_history(existing_history, history_entry)

        try:
            self.cards_table.update_item(
                Key={"user_id": user_id, "card_id": card_id},
                UpdateExpression=(
                    "SET next_review_at = :next_review, "
                    "#interval = :interval, "
                    "ease_factor = :ease_factor, "
                    "repetitions = :repetitions, "
                    "updated_at = :updated_at, "
                    "review_history = :review_history"
                ),
                ExpressionAttributeNames={"#interval": "interval"},
                ExpressionAttributeValues={
                    ":next_review": result.next_review_at.isoformat(),
                    ":interval": result.interval,
                    ":ease_factor": str(result.ease_factor),
                    ":repetitions": result.repetitions,
                    ":updated_at": now.isoformat(),
                    ":review_history": updated_history,
                },
            )
        except ClientError as e:
            raise CardServiceError(f"Failed to update card review data: {e}")

    def _record_review(
        self,
        user_id: str,
        card_id: str,
        grade: int,
        reviewed_at: datetime,
        ease_factor_before: float,
        ease_factor_after: float,
        interval_before: int,
        interval_after: int,
    ) -> None:
        """Record review in reviews table.

        Args:
            user_id: The user's ID.
            card_id: The card's ID.
            grade: Review grade.
            reviewed_at: Review timestamp.
            ease_factor_before: Ease factor before review.
            ease_factor_after: Ease factor after review.
            interval_before: Interval before review.
            interval_after: Interval after review.
        """
        try:
            self.reviews_table.put_item(
                Item={
                    "user_id": user_id,
                    "reviewed_at": reviewed_at.isoformat(),
                    "card_id": card_id,
                    "grade": grade,
                    "ease_factor_before": str(ease_factor_before),
                    "ease_factor_after": str(ease_factor_after),
                    "interval_before": interval_before,
                    "interval_after": interval_after,
                }
            )
        except ClientError as e:
            # Log error but don't fail the review
            # Reviews table is for analytics, not critical
            pass

    def get_due_cards(
        self,
        user_id: str,
        limit: int = 20,
        include_future: bool = False,
    ) -> DueCardsResponse:
        """Get cards due for review.

        Args:
            user_id: The user's ID.
            limit: Maximum number of cards to return.
            include_future: Include cards with future due dates.

        Returns:
            DueCardsResponse with due cards and metadata.
        """
        now = datetime.now(timezone.utc)

        # Get due cards using card service
        due_cards = self.card_service.get_due_cards(
            user_id=user_id,
            limit=limit,
            before=now if not include_future else None,
        )

        # Convert to response format
        due_card_infos: List[DueCardInfo] = []
        for card in due_cards:
            overdue_days = 0
            if card.next_review_at:
                delta = now - card.next_review_at
                overdue_days = max(0, delta.days)

            due_card_infos.append(
                DueCardInfo(
                    card_id=card.card_id,
                    front=card.front,
                    back=card.back,
                    deck_id=card.deck_id,
                    due_date=card.next_review_at.date().isoformat() if card.next_review_at else None,
                    overdue_days=overdue_days,
                )
            )

        # Get next due date if no cards are due now
        next_due_date = None
        if not due_card_infos:
            next_due_date = self._get_next_due_date(user_id)

        return DueCardsResponse(
            due_cards=due_card_infos,
            total_due_count=len(due_card_infos),
            next_due_date=next_due_date,
        )

    def _get_next_due_date(self, user_id: str) -> Optional[str]:
        """Get the next due date for a user's cards.

        Args:
            user_id: The user's ID.

        Returns:
            ISO format date string of next due date, or None.
        """
        try:
            response = self.cards_table.query(
                IndexName="user_id-due-index",
                KeyConditionExpression="user_id = :user_id",
                ExpressionAttributeValues={":user_id": user_id},
                Limit=1,
                ScanIndexForward=True,
            )
            items = response.get("Items", [])
            if items and "next_review_at" in items[0]:
                next_review = datetime.fromisoformat(items[0]["next_review_at"])
                return next_review.date().isoformat()
        except ClientError:
            pass
        return None

"""Review service for managing card reviews."""

import os
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from models.card import Card
from models.review import (
    DueCardInfo,
    DueCardsResponse,
    ReviewPreviousState,
    ReviewResponse,
    ReviewUpdatedState,
    UndoRestoredState,
    UndoReviewResponse,
)
from .ai_service import ReviewSummary
from .card_service import CardNotFoundError, CardService, CardServiceError
from .srs import ReviewHistoryEntry, SM2Result, add_review_history, calculate_sm2


class ReviewServiceError(Exception):
    """Base exception for review service errors."""

    pass


class InvalidGradeError(ReviewServiceError):
    """Raised when grade is invalid."""

    pass


class NoReviewHistoryError(ReviewServiceError):
    """Raised when there is no review history to undo."""

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
            endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL") or os.environ.get("AWS_ENDPOINT_URL")
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
            previous_repetitions=card.repetitions,
            previous_next_review_at=card.next_review_at.isoformat() if card.next_review_at else None,
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

    def undo_review(
        self,
        user_id: str,
        card_id: str,
    ) -> UndoReviewResponse:
        """Undo the latest review for a card and restore SRS parameters.

        Args:
            user_id: The user's ID.
            card_id: The card's ID.

        Returns:
            UndoReviewResponse with restored state.

        Raises:
            CardNotFoundError: If card does not exist or belongs to another user.
            NoReviewHistoryError: If card has no review history to undo.
        """
        # Get the card (also verifies ownership)
        card = self.card_service.get_card(user_id, card_id)

        # Get existing review history
        try:
            response = self.cards_table.get_item(
                Key={"user_id": user_id, "card_id": card_id},
                ProjectionExpression="review_history",
            )
            review_history = response.get("Item", {}).get("review_history", [])
        except ClientError:
            review_history = []

        if not review_history:
            raise NoReviewHistoryError("No review history to undo")

        # Get latest entry
        latest_entry = review_history[-1]

        # Extract before values for restoration
        restored_ease_factor = float(latest_entry.get("ease_factor_before", card.ease_factor))
        restored_interval = int(latest_entry.get("interval_before", card.interval))
        restored_repetitions = latest_entry.get("repetitions_before")
        if restored_repetitions is not None:
            restored_repetitions = int(restored_repetitions)
        else:
            restored_repetitions = card.repetitions
        restored_next_review_at = latest_entry.get("next_review_at_before")
        if restored_next_review_at is None:
            restored_next_review_at = card.next_review_at.isoformat() if card.next_review_at else datetime.now(timezone.utc).isoformat()

        # Remove latest entry from history
        updated_history = review_history[:-1]

        # Update card with restored parameters
        now = datetime.now(timezone.utc)
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
                    ":next_review": restored_next_review_at,
                    ":interval": restored_interval,
                    ":ease_factor": str(restored_ease_factor),
                    ":repetitions": restored_repetitions,
                    ":updated_at": now.isoformat(),
                    ":review_history": updated_history,
                },
            )
        except ClientError as e:
            raise CardServiceError(f"Failed to undo review: {e}")

        # Parse due_date from restored_next_review_at
        try:
            due_date = datetime.fromisoformat(restored_next_review_at).date().isoformat()
        except (ValueError, TypeError):
            due_date = restored_next_review_at

        restored = UndoRestoredState(
            ease_factor=restored_ease_factor,
            interval=restored_interval,
            repetitions=restored_repetitions,
            due_date=due_date,
        )

        return UndoReviewResponse(
            card_id=card_id,
            restored=restored,
            undone_at=now,
        )

    def _update_card_review_data(
        self,
        user_id: str,
        card_id: str,
        result: SM2Result,
        grade: int,
        previous_ease_factor: float,
        previous_interval: int,
        previous_repetitions: Optional[int] = None,
        previous_next_review_at: Optional[str] = None,
    ) -> None:
        """Update card's SRS data and review history.

        Args:
            user_id: The user's ID.
            card_id: The card's ID.
            result: SM2 calculation result.
            grade: Review grade.
            previous_ease_factor: Ease factor before review.
            previous_interval: Interval before review.
            previous_repetitions: Repetitions before review (for undo support).
            previous_next_review_at: Next review at before review (for undo support).
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
            repetitions_before=previous_repetitions,
            repetitions_after=result.repetitions,
            next_review_at_before=previous_next_review_at,
            next_review_at_after=result.next_review_at.isoformat(),
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
        deck_id: Optional[str] = None,
    ) -> DueCardsResponse:
        """Get cards due for review.

        【設計方針】: 全復習対象カードを取得してから limit を適用する。
        これにより total_due_count が limit に影響されず正確な総数を返すことができる。
        deck_id フィルタはアプリケーション層で適用し、DynamoDB クエリは全件取得する。
        🔵 REQ-005: total_due_count は limit パラメータに影響されない正確な総数を返す

        Args:
            user_id: The user's ID.
            limit: Maximum number of cards to return in due_cards.
                   total_due_count はこの値に影響されず、フィルタ後の全件数を返す。
            include_future: Include cards with future due dates.
            deck_id: Optional filter by deck ID.
                     指定した場合、total_due_count はそのデッキ内の復習対象カード総数を返す。

        Returns:
            DueCardsResponse with due cards and metadata.
            - due_cards: limit で制限されたカードリスト
            - total_due_count: deck_id フィルタ後・limit 適用前の全件数（REQ-005）
            - next_due_date: due_cards が空の場合に次の復習予定日を返す
        """
        now = datetime.now(timezone.utc)

        # 【全件取得】: limit を渡さず全復習対象カードを取得する
        # deck_id フィルタはアプリケーション層で適用されるため、
        # DynamoDB Query レベルで limit を適用すると deck_id フィルタ前にカードが失われる。
        # limit=None により全件を取得し、アプリケーション層で deck_id フィルタと limit を適用する。 🔵
        all_due_cards = self.card_service.get_due_cards(
            user_id=user_id,
            limit=None,  # 【全件取得】: DynamoDB Query レベルの切り詰めを防ぎ、正確な総数を計算する 🔵
            before=now if not include_future else None,
        )

        # 【deck_id フィルタ】: deck_id が指定された場合はアプリケーション層でフィルタを適用 🔵
        # DynamoDB の FilterExpression ではなくアプリケーション層で処理することで、
        # クエリコスト（読み取りキャパシティ）を最小化しつつ正確なフィルタを実現する。
        if deck_id is not None:
            all_due_cards = [c for c in all_due_cards if c.deck_id == deck_id]

        # 【total_due_count 計算】: limit 適用前に全件数を記録する（REQ-005）🔵
        # deck_id フィルタ後・limit 適用前のリスト長が正確な復習対象カード総数となる。
        total_due_count = len(all_due_cards)

        # 【limit 適用】: 返却カードのみ limit で制限する（total_due_count には影響しない）🔵
        limited_cards = all_due_cards[:limit]

        # 【レスポンス形式変換】: Card モデルから DueCardInfo に変換する
        due_card_infos: List[DueCardInfo] = []
        for card in limited_cards:
            # 【超過日数計算】: next_review_at から現在までの経過日数（0以上）を計算する
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

        # 【次回復習日取得】: 復習対象カードがない場合に次の復習予定日を返す
        # due_cards が空（全カード復習済み or カードなし）の場合のみクエリを実行する。
        next_due_date = None
        if not due_card_infos:
            next_due_date = self._get_next_due_date(user_id)

        return DueCardsResponse(
            due_cards=due_card_infos,
            total_due_count=total_due_count,
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

    def get_review_summary(self, user_id: str) -> ReviewSummary:
        """Get a summary of review statistics for a user.

        Args:
            user_id: The user's ID.

        Returns:
            ReviewSummary dataclass with aggregated statistics.
            Returns a default (all-zeros) ReviewSummary on error.
        """
        default = ReviewSummary(
            total_reviews=0,
            average_grade=0.0,
            total_cards=0,
            cards_due_today=0,
            streak_days=0,
            tag_performance={},
            recent_review_dates=[],
        )

        try:
            # Fetch all reviews for the user via the GSI
            reviews: List[Dict] = []
            paginator_kwargs = {
                "IndexName": "user_id-reviewed_at-index",
                "KeyConditionExpression": Key("user_id").eq(user_id),
            }
            while True:
                response = self.reviews_table.query(**paginator_kwargs)
                reviews.extend(response.get("Items", []))
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                paginator_kwargs["ExclusiveStartKey"] = last_key

            # Fetch all cards for the user
            cards: List[Dict] = []
            card_kwargs = {
                "KeyConditionExpression": Key("user_id").eq(user_id),
            }
            while True:
                response = self.cards_table.query(**card_kwargs)
                cards.extend(response.get("Items", []))
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                card_kwargs["ExclusiveStartKey"] = last_key

            total_reviews = len(reviews)
            average_grade = (
                sum(int(r["grade"]) for r in reviews) / total_reviews
                if reviews
                else 0.0
            )
            total_cards = len(cards)

            now_iso = datetime.now(timezone.utc).isoformat()
            cards_due_today = sum(
                1 for c in cards if c.get("next_review_at", "") <= now_iso
            )

            # Unique review dates, newest first
            unique_dates = sorted(
                {r["reviewed_at"][:10] for r in reviews},
                reverse=True,
            )
            streak_days = self._calculate_streak(unique_dates)

            # Build tag_performance: tag -> fraction of reviews with grade >= 3
            card_tags: Dict[str, List[str]] = {
                c["card_id"]: c.get("tags") or [] for c in cards
            }
            tag_grades: Dict[str, List[int]] = {}
            for review in reviews:
                card_id = review.get("card_id", "")
                grade = int(review["grade"])
                for tag in card_tags.get(card_id, []):
                    tag_grades.setdefault(tag, []).append(grade)

            tag_performance: Dict[str, float] = {
                tag: sum(1 for g in grades if g >= 3) / len(grades)
                for tag, grades in tag_grades.items()
                if grades
            }

            return ReviewSummary(
                total_reviews=total_reviews,
                average_grade=average_grade,
                total_cards=total_cards,
                cards_due_today=cards_due_today,
                streak_days=streak_days,
                tag_performance=tag_performance,
                recent_review_dates=unique_dates,
            )

        except ClientError:
            return default

    @staticmethod
    def _calculate_streak(sorted_dates_desc: List[str]) -> int:
        """Calculate consecutive study streak days ending at today or yesterday.

        Args:
            sorted_dates_desc: Unique review dates as YYYY-MM-DD strings, newest first.

        Returns:
            Number of consecutive days studied.
        """
        if not sorted_dates_desc:
            return 0

        today = date.today()
        # Streak must end at today or yesterday
        latest = date.fromisoformat(sorted_dates_desc[0])
        if latest < today - timedelta(days=1):
            return 0

        streak = 0
        expected = latest
        for date_str in sorted_dates_desc:
            d = date.fromisoformat(date_str)
            if d == expected:
                streak += 1
                expected = expected - timedelta(days=1)
            elif d < expected:
                break

        return streak

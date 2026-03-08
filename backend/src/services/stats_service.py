"""Stats service for learning statistics dashboard.

集計ロジック（tag_performance, streak, review 統計）の正（single source of truth）。
review_service.get_review_summary はこのモジュールのヘルパー関数に委譲する。
"""

import os
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

import boto3
from aws_lambda_powertools import Logger
from boto3.dynamodb.conditions import Key
from models.stats import (
    ForecastDay,
    ForecastResponse,
    StatsResponse,
    WeakCard,
    WeakCardsResponse,
)

logger = Logger()


# ---------------------------------------------------------------------------
# 共通集計ヘルパー関数（M-7: review_service との重複を解消）
# ---------------------------------------------------------------------------


def calculate_tag_performance(
    cards: List[Dict],
    reviews: List[Dict],
) -> Dict[str, float]:
    """タグごとの正答率を計算する。

    Args:
        cards: DynamoDB カードアイテムのリスト。
        reviews: DynamoDB レビューアイテムのリスト。

    Returns:
        tag -> grade >= 3 の割合 の辞書。
    """
    card_tags: Dict[str, List[str]] = {
        c["card_id"]: c.get("tags") or [] for c in cards
    }
    tag_grades: Dict[str, List[int]] = {}
    for review in reviews:
        card_id = review.get("card_id", "")
        grade = int(review["grade"])
        for tag in card_tags.get(card_id, []):
            tag_grades.setdefault(tag, []).append(grade)

    return {
        tag: sum(1 for g in grades if g >= 3) / len(grades)
        for tag, grades in tag_grades.items()
        if grades
    }


def calculate_streak(
    sorted_dates_desc: List[str],
    user_timezone: str = "UTC",
) -> int:
    """連続学習日数（streak）を計算する。

    m-6: date.today() ではなく user_timezone を考慮した「今日」を使用する。

    Args:
        sorted_dates_desc: ユニークなレビュー日（YYYY-MM-DD）の降順リスト。
        user_timezone: ユーザーの IANA タイムゾーン文字列。デフォルトは "UTC"。

    Returns:
        連続学習日数。
    """
    if not sorted_dates_desc:
        return 0

    today = datetime.now(ZoneInfo(user_timezone)).date()
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


class StatsServiceError(Exception):
    """Base exception for stats service errors."""

    pass


class StatsService:
    """Service for computing learning statistics."""

    def __init__(
        self,
        cards_table_name: Optional[str] = None,
        reviews_table_name: Optional[str] = None,
        dynamodb_resource=None,
    ):
        """Initialize StatsService.

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

    def _fetch_all_cards(self, user_id: str) -> List[Dict]:
        """Fetch all cards for a user with pagination.

        Args:
            user_id: The user's ID.

        Returns:
            List of card items from DynamoDB.
        """
        cards: List[Dict] = []
        query_kwargs = {
            "KeyConditionExpression": Key("user_id").eq(user_id),
        }
        while True:
            response = self.cards_table.query(**query_kwargs)
            cards.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key
        return cards

    def _fetch_all_reviews(self, user_id: str) -> List[Dict]:
        """Fetch all reviews for a user with pagination.

        Args:
            user_id: The user's ID.

        Returns:
            List of review items from DynamoDB.
        """
        reviews: List[Dict] = []
        query_kwargs = {
            "IndexName": "user_id-reviewed_at-index",
            "KeyConditionExpression": Key("user_id").eq(user_id),
        }
        while True:
            response = self.reviews_table.query(**query_kwargs)
            reviews.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            query_kwargs["ExclusiveStartKey"] = last_key
        return reviews

    def get_stats(self, user_id: str) -> StatsResponse:
        """Get learning statistics for a user.

        Args:
            user_id: The user's ID.

        Returns:
            StatsResponse with aggregated statistics.
        """
        cards = self._fetch_all_cards(user_id)
        reviews = self._fetch_all_reviews(user_id)

        total_cards = len(cards)
        learned_cards = sum(1 for c in cards if int(c.get("repetitions", 0)) >= 1)
        unlearned_cards = total_cards - learned_cards

        # Cards due today: next_review_at <= now
        now = datetime.now(timezone.utc)
        cards_due_today = 0
        for c in cards:
            raw = c.get("next_review_at")
            if not raw:
                continue
            try:
                dt = datetime.fromisoformat(str(raw))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt <= now:
                    cards_due_today += 1
            except (ValueError, TypeError):
                continue

        # Review stats
        total_reviews = len(reviews)
        average_grade = (
            sum(int(r["grade"]) for r in reviews) / total_reviews
            if reviews
            else 0.0
        )

        # Streak calculation（共通ヘルパー使用）
        unique_dates = sorted(
            {r["reviewed_at"][:10] for r in reviews},
            reverse=True,
        )
        streak_days = calculate_streak(unique_dates)

        # Tag performance（共通ヘルパー使用）
        tag_performance = calculate_tag_performance(cards, reviews)

        return StatsResponse(
            total_cards=total_cards,
            learned_cards=learned_cards,
            unlearned_cards=unlearned_cards,
            cards_due_today=cards_due_today,
            total_reviews=total_reviews,
            average_grade=average_grade,
            streak_days=streak_days,
            tag_performance=tag_performance,
        )

    def get_weak_cards(self, user_id: str, limit: int = 10) -> WeakCardsResponse:
        """Get weak cards (lowest ease factor) for a user.

        Only includes cards with repetitions >= 1 (i.e., cards that have been
        reviewed at least once). Sorted by ease_factor ascending.

        Args:
            user_id: The user's ID.
            limit: Maximum number of weak cards to return.

        Returns:
            WeakCardsResponse with weak cards list.
        """
        cards = self._fetch_all_cards(user_id)

        # Filter to cards with at least one review
        reviewed_cards = [
            c for c in cards if int(c.get("repetitions", 0)) >= 1
        ]

        # Sort by ease_factor ascending (weakest first)
        reviewed_cards.sort(key=lambda c: float(c.get("ease_factor", 2.5)))

        total_count = len(reviewed_cards)
        limited = reviewed_cards[:limit]

        weak_cards = [
            WeakCard(
                card_id=c["card_id"],
                front=c["front"],
                back=c["back"],
                ease_factor=float(c.get("ease_factor", 2.5)),
                repetitions=int(c.get("repetitions", 0)),
                deck_id=c.get("deck_id"),
            )
            for c in limited
        ]

        return WeakCardsResponse(
            weak_cards=weak_cards,
            total_count=total_count,
        )

    def get_forecast(self, user_id: str, days: int = 7) -> ForecastResponse:
        """Get review forecast for the next N days.

        Groups cards by their next_review_at date. Cards with past due dates
        are counted as today.

        Args:
            user_id: The user's ID.
            days: Number of days to forecast.

        Returns:
            ForecastResponse with daily forecast.
        """
        cards = self._fetch_all_cards(user_id)

        today = date.today()
        end_date = today + timedelta(days=days - 1)

        # Initialize counts for each day
        day_counts: Dict[str, int] = {}
        for i in range(days):
            d = today + timedelta(days=i)
            day_counts[d.isoformat()] = 0

        # Group cards by next_review_at date
        for card in cards:
            next_review_at = card.get("next_review_at")
            if not next_review_at:
                continue

            try:
                review_date = datetime.fromisoformat(next_review_at).date()
            except (ValueError, TypeError):
                continue

            # Past due dates count as today
            if review_date <= today:
                day_counts[today.isoformat()] = day_counts.get(today.isoformat(), 0) + 1
            elif review_date <= end_date:
                date_key = review_date.isoformat()
                day_counts[date_key] = day_counts.get(date_key, 0) + 1

        # Build sorted forecast
        forecast = [
            ForecastDay(date=d, due_count=count)
            for d, count in sorted(day_counts.items())
        ]

        return ForecastResponse(forecast=forecast)

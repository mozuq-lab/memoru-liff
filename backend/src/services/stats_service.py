"""Stats service for learning statistics dashboard.

集計ロジック（tag_performance, streak, review 統計）の正（single source of truth）。
review_service.get_review_summary はこのモジュールのヘルパー関数に委譲する。
"""

import os
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from aws_lambda_powertools import Logger
from models.stats import (
    ForecastDay,
    ForecastResponse,
    StatsResponse,
    WeakCard,
    WeakCardsResponse,
)
from .card_repository import CardRepository
from .review_repository import ReviewRepository

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


def unique_local_review_dates_desc(
    reviews: List[Dict],
    user_timezone: str = "UTC",
) -> List[str]:
    """reviewed_at (UTC ISO 8601) をユーザーローカル日付に変換し、ユニーク日付の降順リストを返す。

    従来は `reviewed_at[:10]`（UTC 日付）をそのまま streak 計算に使っていたため、
    UTC+9 のユーザーが同じローカル日の深夜（例: 00:30 JST）と日中（10:00 JST）に
    レビューすると UTC では前日/当日の 2 日に分裂し、streak が過大になっていた。
    calculate_streak の「今日」判定と同じタイムゾーンで日付を作ることで一致させる。

    無効な timezone は calculate_streak と同じく UTC にフォールバックする（L-6 と同方針）。
    パース不能な reviewed_at は従来どおり先頭 10 文字（UTC 日付）にフォールバックする。
    """
    try:
        tz = ZoneInfo(user_timezone)
    except Exception:
        logger.warning(
            "Invalid timezone for review dates; falling back to UTC",
            extra={"user_timezone": user_timezone},
        )
        tz = ZoneInfo("UTC")

    dates: set[str] = set()
    for review in reviews:
        raw = review.get("reviewed_at")
        if not raw:
            continue
        try:
            dt = datetime.fromisoformat(str(raw))
        except (ValueError, TypeError):
            fallback = str(raw)[:10]
            if fallback:
                dates.add(fallback)
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dates.add(dt.astimezone(tz).date().isoformat())

    return sorted(dates, reverse=True)


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

    # L-6: 無効なタイムゾーン文字列 (ZoneInfoNotFoundError / KeyError) でも
    # 例外を呼び出し元へバブルアップさせず UTC にフォールバックする。
    # srs.calculate_next_review_boundary と同じ防御方針。
    try:
        tz = ZoneInfo(user_timezone)
    except Exception:
        logger.warning(
            "Invalid timezone for streak calculation; falling back to UTC",
            extra={"user_timezone": user_timezone},
        )
        tz = ZoneInfo("UTC")

    today = datetime.now(tz).date()
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

        # L-7 集約: 全件取得は Repository に委譲し、stats_service は集計に専念する
        # （DynamoDB 直アクセス＋ページネーションループの二重実装を解消）。
        self._card_repo = CardRepository(
            table_name=self.cards_table_name,
            dynamodb_resource=dynamodb_resource,
            reviews_table_name=self.reviews_table_name,
        )
        self._review_repo = ReviewRepository(
            table_name=self.reviews_table_name,
            dynamodb_resource=dynamodb_resource,
        )

    def _fetch_all_cards(self, user_id: str) -> List[Dict]:
        """Fetch all cards for a user (CardRepository へ委譲)."""
        return self._card_repo.scan_all_cards(user_id)

    def _fetch_all_reviews(self, user_id: str) -> List[Dict]:
        """Fetch all reviews for a user (ReviewRepository へ委譲)."""
        return self._review_repo.query_all_reviews(user_id)

    def get_stats(self, user_id: str, user_timezone: str = "UTC") -> StatsResponse:
        """Get learning statistics for a user.

        Args:
            user_id: The user's ID.
            user_timezone: ユーザーの IANA タイムゾーン文字列（streak 計算用）。
                M-7: サーバーのローカル時刻（UTC）固定だと、UTC+9 ユーザーが
                日本時間の深夜にレビューした場合にストリークが誤って 0 にリセット
                されるため、呼び出し元はユーザー設定の timezone を渡すこと。
                デフォルトは後方互換のため "UTC"。

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
        # reviewed_at はユーザーローカル日付へ変換してから streak を計算する
        unique_dates = unique_local_review_dates_desc(reviews, user_timezone)
        streak_days = calculate_streak(unique_dates, user_timezone=user_timezone)

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

    def get_forecast(
        self, user_id: str, days: int = 7, user_timezone: str = "UTC"
    ) -> ForecastResponse:
        """Get review forecast for the next N days.

        Groups cards by their next_review_at date. Cards with past due dates
        are counted as today.

        Args:
            user_id: The user's ID.
            days: Number of days to forecast.
            user_timezone: ユーザーの IANA タイムゾーン文字列。
                M-7: 旧実装は date.today()（Lambda 実行環境＝通常 UTC のローカル時刻）
                を「今日」としていたため、ユーザーにとっての今日が 1 日ずれる問題が
                あった。ユーザーの timezone で「今日」を判定する。
                デフォルトは後方互換のため "UTC"。

        Returns:
            ForecastResponse with daily forecast.
        """
        cards = self._fetch_all_cards(user_id)

        # M-7: ユーザータイムゾーンで「今日」を判定する。無効な timezone は
        # UTC へフォールバックして例外を呼び出し元へ伝播させない（L-6 と同方針）。
        try:
            tz = ZoneInfo(user_timezone)
        except Exception:
            logger.warning(
                "Invalid timezone for forecast; falling back to UTC",
                extra={"user_timezone": user_timezone},
            )
            tz = ZoneInfo("UTC")
        today = datetime.now(tz).date()
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
                review_dt = datetime.fromisoformat(next_review_at)
            except (ValueError, TypeError):
                continue

            # next_review_at は UTC で保存されている（day_start_hour 正規化により
            # 例: JST 04:00 → 前日 19:00 UTC）。UTC のまま date() を取るとローカル
            # 日付より 1 日早いバケットに計上されるため、ユーザーの timezone に
            # 変換してから日付を取る。naive な旧データは UTC とみなす。
            if review_dt.tzinfo is None:
                review_dt = review_dt.replace(tzinfo=timezone.utc)
            review_date = review_dt.astimezone(tz).date()

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

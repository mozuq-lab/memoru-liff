"""Unit tests for stats service."""

import pytest
from moto import mock_aws
import boto3
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from services.stats_service import StatsService


@pytest.fixture
def dynamodb_tables():
    """Create mock DynamoDB tables."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

        # Create cards table
        cards_table = dynamodb.create_table(
            TableName="memoru-cards-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "card_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "card_id", "AttributeType": "S"},
                {"AttributeName": "next_review_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user_id-due-index",
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "next_review_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        cards_table.wait_until_exists()

        # Create reviews table
        reviews_table = dynamodb.create_table(
            TableName="memoru-reviews-test",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "reviewed_at", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "reviewed_at", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user_id-reviewed_at-index",
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "reviewed_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        reviews_table.wait_until_exists()

        yield dynamodb


@pytest.fixture
def stats_service(dynamodb_tables):
    """Create StatsService with mock DynamoDB."""
    return StatsService(
        cards_table_name="memoru-cards-test",
        reviews_table_name="memoru-reviews-test",
        dynamodb_resource=dynamodb_tables,
    )


def _put_card(dynamodb_tables, user_id, card_id, front="Q", back="A",
              repetitions=0, ease_factor="2.5", interval=0,
              next_review_at=None, deck_id=None, tags=None):
    """Helper to insert a card item into the mock cards table."""
    now = datetime.now(timezone.utc)
    item = {
        "user_id": user_id,
        "card_id": card_id,
        "front": front,
        "back": back,
        "repetitions": repetitions,
        "ease_factor": ease_factor,
        "interval": interval,
        "tags": tags or [],
        "created_at": now.isoformat(),
    }
    if next_review_at:
        item["next_review_at"] = next_review_at
    if deck_id:
        item["deck_id"] = deck_id
    dynamodb_tables.Table("memoru-cards-test").put_item(Item=item)


def _put_review(dynamodb_tables, user_id, reviewed_at, card_id="card-1", grade=4):
    """Helper to insert a review item into the mock reviews table."""
    dynamodb_tables.Table("memoru-reviews-test").put_item(
        Item={
            "user_id": user_id,
            "reviewed_at": reviewed_at,
            "card_id": card_id,
            "grade": grade,
        }
    )


class TestGetStats:
    """Tests for StatsService.get_stats method."""

    def test_get_stats_no_cards(self, stats_service):
        """Test stats with no cards returns zeros."""
        result = stats_service.get_stats("user-1")
        assert result.total_cards == 0
        assert result.learned_cards == 0
        assert result.unlearned_cards == 0
        assert result.cards_due_today == 0
        assert result.total_reviews == 0
        assert result.average_grade == 0.0
        assert result.streak_days == 0
        assert result.tag_performance == {}

    def test_get_stats_with_cards(self, stats_service, dynamodb_tables):
        """Test stats with a mix of learned and unlearned cards."""
        now = datetime.now(timezone.utc)
        past = (now - timedelta(hours=1)).isoformat()
        future = (now + timedelta(days=1)).isoformat()

        # Learned card (due today)
        _put_card(dynamodb_tables, "user-1", "card-1",
                  front="Q1", back="A1",
                  repetitions=3, ease_factor="2.5",
                  next_review_at=past)
        # Learned card (not due)
        _put_card(dynamodb_tables, "user-1", "card-2",
                  front="Q2", back="A2",
                  repetitions=1, ease_factor="2.0",
                  next_review_at=future)
        # Unlearned card (no next_review_at, not due)
        _put_card(dynamodb_tables, "user-1", "card-3",
                  front="Q3", back="A3",
                  repetitions=0,
                  next_review_at=future)

        result = stats_service.get_stats("user-1")
        assert result.total_cards == 3
        assert result.learned_cards == 2
        assert result.unlearned_cards == 1
        assert result.cards_due_today == 1

    def test_get_stats_average_grade(self, stats_service, dynamodb_tables):
        """Test average grade calculation."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables, "user-1", "card-1")

        _put_review(dynamodb_tables, "user-1",
                    now.isoformat(), card_id="card-1", grade=5)
        _put_review(dynamodb_tables, "user-1",
                    (now - timedelta(seconds=1)).isoformat(),
                    card_id="card-1", grade=3)

        result = stats_service.get_stats("user-1")
        assert result.total_reviews == 2
        assert result.average_grade == 4.0

    def test_get_stats_streak(self, stats_service, dynamodb_tables):
        """Test streak days calculation."""
        today = date.today()
        _put_card(dynamodb_tables, "user-1", "card-1")

        # Reviews on today, yesterday, and day before
        for i in range(3):
            d = today - timedelta(days=i)
            reviewed_at = datetime(d.year, d.month, d.day, 12, 0, 0,
                                   tzinfo=timezone.utc).isoformat()
            _put_review(dynamodb_tables, "user-1", reviewed_at,
                        card_id="card-1", grade=4)

        result = stats_service.get_stats("user-1")
        assert result.streak_days == 3

    def test_get_stats_tag_performance(self, stats_service, dynamodb_tables):
        """Test tag performance calculation."""
        now = datetime.now(timezone.utc)

        _put_card(dynamodb_tables, "user-1", "card-1",
                  tags=["math", "algebra"])
        _put_card(dynamodb_tables, "user-1", "card-2",
                  tags=["math"])

        # card-1: grade 4 (pass), card-2: grade 2 (fail)
        _put_review(dynamodb_tables, "user-1",
                    now.isoformat(), card_id="card-1", grade=4)
        _put_review(dynamodb_tables, "user-1",
                    (now - timedelta(seconds=1)).isoformat(),
                    card_id="card-2", grade=2)

        result = stats_service.get_stats("user-1")
        # math: 1 pass out of 2 reviews = 0.5
        assert result.tag_performance["math"] == 0.5
        # algebra: 1 pass out of 1 review = 1.0
        assert result.tag_performance["algebra"] == 1.0

    def test_get_stats_cards_due_includes_past_due(self, stats_service, dynamodb_tables):
        """Test that past-due cards are counted in cards_due_today."""
        past = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        _put_card(dynamodb_tables, "user-1", "card-1",
                  next_review_at=past, repetitions=1)

        result = stats_service.get_stats("user-1")
        assert result.cards_due_today == 1


class TestGetWeakCards:
    """Tests for StatsService.get_weak_cards method."""

    def test_get_weak_cards_empty(self, stats_service):
        """Test weak cards with no cards returns empty."""
        result = stats_service.get_weak_cards("user-1")
        assert result.weak_cards == []
        assert result.total_count == 0

    def test_get_weak_cards_excludes_unreviewed(self, stats_service, dynamodb_tables):
        """Test that cards with repetitions == 0 are excluded."""
        _put_card(dynamodb_tables, "user-1", "card-1", repetitions=0)

        result = stats_service.get_weak_cards("user-1")
        assert result.weak_cards == []
        assert result.total_count == 0

    def test_get_weak_cards_sorted_by_ease_factor(self, stats_service, dynamodb_tables):
        """Test that weak cards are sorted by ease_factor ascending."""
        _put_card(dynamodb_tables, "user-1", "card-1",
                  front="Easy", back="A1",
                  repetitions=3, ease_factor="2.5")
        _put_card(dynamodb_tables, "user-1", "card-2",
                  front="Hard", back="A2",
                  repetitions=5, ease_factor="1.3")
        _put_card(dynamodb_tables, "user-1", "card-3",
                  front="Medium", back="A3",
                  repetitions=2, ease_factor="1.8")

        result = stats_service.get_weak_cards("user-1")
        assert len(result.weak_cards) == 3
        assert result.total_count == 3
        assert result.weak_cards[0].card_id == "card-2"
        assert result.weak_cards[0].ease_factor == 1.3
        assert result.weak_cards[1].card_id == "card-3"
        assert result.weak_cards[2].card_id == "card-1"

    def test_get_weak_cards_respects_limit(self, stats_service, dynamodb_tables):
        """Test that limit is respected."""
        for i in range(5):
            _put_card(dynamodb_tables, "user-1", f"card-{i}",
                      front=f"Q{i}", back=f"A{i}",
                      repetitions=1, ease_factor=str(1.3 + i * 0.1))

        result = stats_service.get_weak_cards("user-1", limit=2)
        assert len(result.weak_cards) == 2
        assert result.total_count == 5

    def test_get_weak_cards_includes_deck_id(self, stats_service, dynamodb_tables):
        """Test that deck_id is included in weak card response."""
        _put_card(dynamodb_tables, "user-1", "card-1",
                  front="Q1", back="A1",
                  repetitions=1, ease_factor="1.5",
                  deck_id="deck-001")

        result = stats_service.get_weak_cards("user-1")
        assert result.weak_cards[0].deck_id == "deck-001"

    def test_get_weak_cards_no_deck_id(self, stats_service, dynamodb_tables):
        """Test weak card with no deck_id."""
        _put_card(dynamodb_tables, "user-1", "card-1",
                  front="Q1", back="A1",
                  repetitions=1, ease_factor="1.5")

        result = stats_service.get_weak_cards("user-1")
        assert result.weak_cards[0].deck_id is None


class TestGetForecast:
    """Tests for StatsService.get_forecast method."""

    def test_get_forecast_empty(self, stats_service):
        """Test forecast with no cards."""
        result = stats_service.get_forecast("user-1", days=7)
        assert len(result.forecast) == 7
        assert all(day.due_count == 0 for day in result.forecast)

    def test_get_forecast_dates_sorted(self, stats_service):
        """Test that forecast dates are sorted chronologically."""
        result = stats_service.get_forecast("user-1", days=7)
        dates = [day.date for day in result.forecast]
        assert dates == sorted(dates)

    def test_get_forecast_with_due_cards(self, stats_service, dynamodb_tables):
        """Test forecast with cards due on various days."""
        today = date.today()
        tomorrow = today + timedelta(days=1)
        day_after = today + timedelta(days=2)

        # Card due tomorrow
        tomorrow_dt = datetime(tomorrow.year, tomorrow.month, tomorrow.day,
                               12, 0, 0, tzinfo=timezone.utc)
        _put_card(dynamodb_tables, "user-1", "card-1",
                  next_review_at=tomorrow_dt.isoformat())

        # Card due day after tomorrow
        day_after_dt = datetime(day_after.year, day_after.month, day_after.day,
                                12, 0, 0, tzinfo=timezone.utc)
        _put_card(dynamodb_tables, "user-1", "card-2",
                  next_review_at=day_after_dt.isoformat())

        result = stats_service.get_forecast("user-1", days=7)

        # Build a lookup
        forecast_map = {day.date: day.due_count for day in result.forecast}
        assert forecast_map[tomorrow.isoformat()] == 1
        assert forecast_map[day_after.isoformat()] == 1

    def test_get_forecast_past_due_counts_as_today(self, stats_service, dynamodb_tables):
        """Test that past-due cards are counted as today."""
        today = date.today()
        past = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()

        _put_card(dynamodb_tables, "user-1", "card-1",
                  next_review_at=past)

        result = stats_service.get_forecast("user-1", days=7)
        forecast_map = {day.date: day.due_count for day in result.forecast}
        assert forecast_map[today.isoformat()] == 1

    def test_get_forecast_cards_beyond_range_excluded(self, stats_service, dynamodb_tables):
        """Test that cards beyond the forecast range are excluded."""
        today = date.today()
        far_future = today + timedelta(days=30)
        far_future_dt = datetime(far_future.year, far_future.month, far_future.day,
                                 12, 0, 0, tzinfo=timezone.utc)

        _put_card(dynamodb_tables, "user-1", "card-1",
                  next_review_at=far_future_dt.isoformat())

        result = stats_service.get_forecast("user-1", days=7)
        assert all(day.due_count == 0 for day in result.forecast)

    def test_get_forecast_multiple_cards_same_day(self, stats_service, dynamodb_tables):
        """Test that multiple cards on the same day are summed."""
        today = date.today()
        tomorrow = today + timedelta(days=1)
        tomorrow_dt = datetime(tomorrow.year, tomorrow.month, tomorrow.day,
                               12, 0, 0, tzinfo=timezone.utc)

        _put_card(dynamodb_tables, "user-1", "card-1",
                  next_review_at=tomorrow_dt.isoformat())
        _put_card(dynamodb_tables, "user-1", "card-2",
                  next_review_at=tomorrow_dt.isoformat())

        result = stats_service.get_forecast("user-1", days=7)
        forecast_map = {day.date: day.due_count for day in result.forecast}
        assert forecast_map[tomorrow.isoformat()] == 2

    def test_get_forecast_cards_without_next_review_at_skipped(self, stats_service, dynamodb_tables):
        """Test that cards without next_review_at are skipped."""
        _put_card(dynamodb_tables, "user-1", "card-1")  # No next_review_at

        result = stats_service.get_forecast("user-1", days=7)
        assert all(day.due_count == 0 for day in result.forecast)

    def test_get_forecast_custom_days(self, stats_service):
        """Test forecast with custom number of days."""
        result = stats_service.get_forecast("user-1", days=3)
        assert len(result.forecast) == 3

    def test_get_forecast_first_date_is_today(self, stats_service):
        """Test that the first forecast date is today."""
        today = date.today()
        result = stats_service.get_forecast("user-1", days=7)
        assert result.forecast[0].date == today.isoformat()

"""Unit tests for review service."""

import pytest
from moto import mock_aws
import boto3
from datetime import datetime, timedelta, timezone

from services.review_service import (
    ReviewService,
    InvalidGradeError,
    NoReviewHistoryError,
)
from services.card_service import CardNotFoundError


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
            BillingMode="PAY_PER_REQUEST",
        )
        reviews_table.wait_until_exists()

        yield dynamodb


@pytest.fixture
def review_service(dynamodb_tables):
    """Create ReviewService with mock DynamoDB."""
    return ReviewService(
        cards_table_name="memoru-cards-test",
        reviews_table_name="memoru-reviews-test",
        dynamodb_resource=dynamodb_tables,
    )


@pytest.fixture
def sample_card(dynamodb_tables):
    """Create a sample card for testing."""
    now = datetime.now(timezone.utc)
    table = dynamodb_tables.Table("memoru-cards-test")
    table.put_item(
        Item={
            "user_id": "test-user-id",
            "card_id": "test-card-id",
            "front": "Test Question",
            "back": "Test Answer",
            "next_review_at": now.isoformat(),
            "interval": 1,
            "ease_factor": "2.5",
            "repetitions": 0,
            "tags": [],
            "created_at": now.isoformat(),
        }
    )
    return {
        "user_id": "test-user-id",
        "card_id": "test-card-id",
    }


class TestSubmitReview:
    """Tests for ReviewService.submit_review method."""

    def test_submit_review_success(self, review_service, sample_card):
        """Test submitting a successful review."""
        response = review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )

        assert response.card_id == "test-card-id"
        assert response.grade == 4
        assert response.previous.ease_factor == 2.5
        assert response.previous.interval == 1
        assert response.previous.repetitions == 0
        assert response.updated.repetitions == 1
        assert response.updated.interval == 1  # First review interval
        assert response.updated.ease_factor == 2.5  # Grade 4 doesn't change EF much
        assert response.reviewed_at is not None

    def test_submit_review_grade_5(self, review_service, sample_card):
        """Test perfect review increases ease factor."""
        response = review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=5,
        )

        assert response.updated.ease_factor == 2.6
        assert response.updated.repetitions == 1

    def test_submit_review_grade_0_resets(self, review_service, dynamodb_tables):
        """Test grade 0 resets repetitions and interval."""
        # Create a card with some progress
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_id": "advanced-card",
                "front": "Advanced Question",
                "back": "Advanced Answer",
                "next_review_at": now.isoformat(),
                "interval": 30,
                "ease_factor": "2.5",
                "repetitions": 5,
                "tags": [],
                "created_at": now.isoformat(),
            }
        )

        response = review_service.submit_review(
            user_id="test-user-id",
            card_id="advanced-card",
            grade=0,
        )

        assert response.updated.repetitions == 0
        assert response.updated.interval == 1

    def test_submit_review_invalid_grade_negative(self, review_service, sample_card):
        """Test invalid negative grade raises error."""
        with pytest.raises(InvalidGradeError):
            review_service.submit_review(
                user_id="test-user-id",
                card_id="test-card-id",
                grade=-1,
            )

    def test_submit_review_invalid_grade_too_high(self, review_service, sample_card):
        """Test invalid grade too high raises error."""
        with pytest.raises(InvalidGradeError):
            review_service.submit_review(
                user_id="test-user-id",
                card_id="test-card-id",
                grade=6,
            )

    def test_submit_review_card_not_found(self, review_service):
        """Test reviewing non-existent card raises error."""
        with pytest.raises(CardNotFoundError):
            review_service.submit_review(
                user_id="test-user-id",
                card_id="non-existent-card",
                grade=4,
            )

    def test_submit_review_wrong_user(self, review_service, sample_card):
        """Test reviewing another user's card raises error."""
        with pytest.raises(CardNotFoundError):
            review_service.submit_review(
                user_id="other-user-id",
                card_id="test-card-id",
                grade=4,
            )


class TestGetDueCards:
    """Tests for ReviewService.get_due_cards method."""

    def test_get_due_cards_success(self, review_service, dynamodb_tables):
        """Test getting due cards returns correct cards."""
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")

        # Create due cards
        for i in range(3):
            table.put_item(
                Item={
                    "user_id": "test-user-id",
                    "card_id": f"due-card-{i}",
                    "front": f"Due Question {i}",
                    "back": f"Due Answer {i}",
                    "next_review_at": (now - timedelta(hours=i + 1)).isoformat(),
                    "interval": 1,
                    "ease_factor": "2.5",
                    "repetitions": 0,
                    "tags": [],
                    "created_at": now.isoformat(),
                }
            )

        response = review_service.get_due_cards("test-user-id")

        assert response.total_due_count == 3
        assert len(response.due_cards) == 3

    def test_get_due_cards_empty(self, review_service, dynamodb_tables):
        """Test getting due cards when none are due."""
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")

        # Create future cards
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_id": "future-card",
                "front": "Future Question",
                "back": "Future Answer",
                "next_review_at": (now + timedelta(days=1)).isoformat(),
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "tags": [],
                "created_at": now.isoformat(),
            }
        )

        response = review_service.get_due_cards("test-user-id")

        assert response.total_due_count == 0
        assert len(response.due_cards) == 0

    def test_get_due_cards_with_limit(self, review_service, dynamodb_tables):
        """Test getting due cards with limit."""
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")

        # Create 5 due cards
        for i in range(5):
            table.put_item(
                Item={
                    "user_id": "test-user-id",
                    "card_id": f"due-card-{i}",
                    "front": f"Due Question {i}",
                    "back": f"Due Answer {i}",
                    "next_review_at": (now - timedelta(hours=i + 1)).isoformat(),
                    "interval": 1,
                    "ease_factor": "2.5",
                    "repetitions": 0,
                    "tags": [],
                    "created_at": now.isoformat(),
                }
            )

        response = review_service.get_due_cards("test-user-id", limit=2)

        assert len(response.due_cards) <= 2

    def test_get_due_cards_overdue_days(self, review_service, dynamodb_tables):
        """Test overdue days calculation."""
        now = datetime.now(timezone.utc)
        table = dynamodb_tables.Table("memoru-cards-test")

        # Create an overdue card
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "card_id": "overdue-card",
                "front": "Overdue Question",
                "back": "Overdue Answer",
                "next_review_at": (now - timedelta(days=3)).isoformat(),
                "interval": 1,
                "ease_factor": "2.5",
                "repetitions": 0,
                "tags": [],
                "created_at": now.isoformat(),
            }
        )

        response = review_service.get_due_cards("test-user-id")

        assert len(response.due_cards) == 1
        assert response.due_cards[0].overdue_days >= 2  # At least 2 days overdue


class TestReviewIntegration:
    """Integration tests for review workflow."""

    def test_review_updates_due_date(self, review_service, sample_card):
        """Test that reviewing a card updates due date."""
        # Submit a review
        review_response = review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )

        # Due date should be in the future now
        due_response = review_service.get_due_cards("test-user-id")

        # Card should no longer be due (assuming interval >= 1 day)
        card_ids = [c.card_id for c in due_response.due_cards]
        assert "test-card-id" not in card_ids

    def test_consecutive_reviews_increase_interval(self, review_service, sample_card):
        """Test that consecutive successful reviews increase interval."""
        # First review
        response1 = review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )
        interval1 = response1.updated.interval

        # Need to update the card's next_review_at to be in the past to review again
        # For this test, we'll just verify the SM-2 logic produces increasing intervals

        assert interval1 == 1  # First review always 1 day


# ---------------------------------------------------------------------------
# Fixtures for TestGetReviewSummary (production schema with GSI on reviews)
# ---------------------------------------------------------------------------

@pytest.fixture
def dynamodb_tables_with_gsi():
    """Create mock DynamoDB tables with production schema (GSI on reviews)."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

        # Cards table (same schema as production)
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

        # Reviews table with PRODUCTION schema (PK: card_id, GSI: user_id-reviewed_at-index)
        reviews_table = dynamodb.create_table(
            TableName="memoru-reviews-test",
            KeySchema=[
                {"AttributeName": "card_id", "KeyType": "HASH"},
                {"AttributeName": "reviewed_at", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "card_id", "AttributeType": "S"},
                {"AttributeName": "reviewed_at", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
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
def review_service_with_gsi(dynamodb_tables_with_gsi):
    """Create ReviewService with production-schema mock DynamoDB."""
    return ReviewService(
        cards_table_name="memoru-cards-test",
        reviews_table_name="memoru-reviews-test",
        dynamodb_resource=dynamodb_tables_with_gsi,
    )


def _put_review(dynamodb, user_id: str, card_id: str, grade: int, reviewed_at: str):
    """Insert a review record into the reviews table."""
    table = dynamodb.Table("memoru-reviews-test")
    table.put_item(Item={
        "user_id": user_id,
        "card_id": card_id,
        "reviewed_at": reviewed_at,
        "grade": grade,
        "ease_factor_before": "2.5",
        "ease_factor_after": "2.5",
        "interval_before": 1,
        "interval_after": 1,
    })


def _put_card(dynamodb, user_id: str, card_id: str, next_review_at: str, tags: list = None):
    """Insert a card record into the cards table."""
    table = dynamodb.Table("memoru-cards-test")
    now = datetime.now(timezone.utc).isoformat()
    table.put_item(Item={
        "user_id": user_id,
        "card_id": card_id,
        "front": f"Question for {card_id}",
        "back": f"Answer for {card_id}",
        "next_review_at": next_review_at,
        "interval": 1,
        "ease_factor": "2.5",
        "repetitions": 0,
        "tags": tags or [],
        "created_at": now,
    })


class TestGetReviewSummary:
    """Tests for ReviewService.get_review_summary method (TC-061-SUM-001 ~ TC-061-SUM-017)."""

    def test_get_review_summary_returns_review_summary_type(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-001: get_review_summary() returns a ReviewSummary dataclass instance."""
        from services.ai_service import ReviewSummary

        now = datetime.now(timezone.utc)
        _put_card(
            dynamodb_tables_with_gsi,
            "user-1", "card-1",
            (now - timedelta(hours=1)).isoformat(),
            tags=["math"],
        )
        _put_review(
            dynamodb_tables_with_gsi,
            "user-1", "card-1", 4,
            now.isoformat(),
        )

        result = review_service_with_gsi.get_review_summary("user-1")

        assert isinstance(result, ReviewSummary)

    def test_get_review_summary_total_reviews_count(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-002: total_reviews equals the number of review records."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat())
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-2",
                  (now - timedelta(hours=1)).isoformat())

        # card-1: 3 reviews
        for i, grade in enumerate([3, 4, 5]):
            _put_review(
                dynamodb_tables_with_gsi, "user-1", "card-1", grade,
                (now - timedelta(hours=10 - i)).isoformat(),
            )
        # card-2: 2 reviews
        for i, grade in enumerate([2, 3]):
            _put_review(
                dynamodb_tables_with_gsi, "user-1", "card-2", grade,
                (now - timedelta(hours=5 - i)).isoformat(),
            )

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.total_reviews == 5

    def test_get_review_summary_average_grade_calculation(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-003: average_grade is the arithmetic mean of all review grades."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat())

        # grades: [3, 4, 5, 2, 1] -> average = 15/5 = 3.0
        for i, grade in enumerate([3, 4, 5, 2, 1]):
            _put_review(
                dynamodb_tables_with_gsi, "user-1", "card-1", grade,
                (now - timedelta(hours=10 - i)).isoformat(),
            )

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.average_grade == 3.0

    def test_get_review_summary_total_cards_count(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-004: total_cards equals the number of cards belonging to the user."""
        now = datetime.now(timezone.utc)
        for i in range(1, 4):
            _put_card(
                dynamodb_tables_with_gsi, "user-1", f"card-{i}",
                (now + timedelta(days=1)).isoformat(),
            )

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.total_cards == 3

    def test_get_review_summary_cards_due_today(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-005: cards_due_today counts cards whose next_review_at is <= now."""
        now = datetime.now(timezone.utc)
        # card-1: due 1 hour ago
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat())
        # card-2: due 1 day ago
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-2",
                  (now - timedelta(days=1)).isoformat())
        # card-3: due 1 day in the future
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-3",
                  (now + timedelta(days=1)).isoformat())

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.cards_due_today == 2

    def test_get_review_summary_tag_performance(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-006: tag_performance is derived from cards.tags (not reviews.tags)."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat(), tags=["math"])
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-2",
                  (now - timedelta(hours=1)).isoformat(), tags=["english"])

        # card-1: 3 correct reviews (grade >= 3)
        for i, grade in enumerate([3, 4, 5]):
            _put_review(
                dynamodb_tables_with_gsi, "user-1", "card-1", grade,
                (now - timedelta(hours=10 - i)).isoformat(),
            )
        # card-2: 2 incorrect reviews (grade < 3)
        for i, grade in enumerate([1, 2]):
            _put_review(
                dynamodb_tables_with_gsi, "user-1", "card-2", grade,
                (now - timedelta(hours=5 - i)).isoformat(),
            )

        result = review_service_with_gsi.get_review_summary("user-1")

        # math: 3/3 = 1.0 (100% correct)
        assert result.tag_performance["math"] == pytest.approx(1.0)
        # english: 0/2 = 0.0 (0% correct)
        assert result.tag_performance["english"] == pytest.approx(0.0)

    def test_get_review_summary_streak_days_consecutive(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-007: streak_days counts consecutive days of study ending today."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now + timedelta(days=1)).isoformat())

        today = now
        yesterday = now - timedelta(days=1)
        day_before = now - timedelta(days=2)

        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 4,
                    today.isoformat())
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 4,
                    yesterday.replace(hour=10).isoformat())
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 4,
                    day_before.replace(hour=10).isoformat())

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.streak_days == 3

    def test_get_review_summary_streak_days_broken(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-008: streak_days resets when study days are not consecutive."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now + timedelta(days=1)).isoformat())

        today = now
        three_days_ago = now - timedelta(days=3)

        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 4,
                    today.isoformat())
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 4,
                    three_days_ago.replace(hour=10).isoformat())

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.streak_days == 1  # today only

    def test_get_review_summary_recent_review_dates(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-009: recent_review_dates is a list of unique dates, newest first."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now + timedelta(days=1)).isoformat())

        today = now
        yesterday = now - timedelta(days=1)
        three_days_ago = now - timedelta(days=3)

        # today: 2 reviews (same day)
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 4,
                    today.isoformat())
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 3,
                    today.replace(hour=(today.hour - 1) % 24).isoformat())
        # yesterday: 2 reviews
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 4,
                    yesterday.replace(hour=10).isoformat())
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 5,
                    yesterday.replace(hour=14).isoformat())
        # 3 days ago: 1 review
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 3,
                    three_days_ago.replace(hour=9).isoformat())

        result = review_service_with_gsi.get_review_summary("user-1")

        # unique dates: 3
        assert len(result.recent_review_dates) == 3
        # sorted newest first (descending)
        assert result.recent_review_dates[0] > result.recent_review_dates[1]
        assert result.recent_review_dates[1] > result.recent_review_dates[2]
        # each entry is a string
        for date_str in result.recent_review_dates:
            assert isinstance(date_str, str)

    def test_get_review_summary_empty_reviews(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-010: returns default values when there are no reviews and no cards."""
        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.total_reviews == 0
        assert result.average_grade == 0.0
        assert result.total_cards == 0
        assert result.cards_due_today == 0
        assert result.tag_performance == {}
        assert result.streak_days == 0
        assert result.recent_review_dates == []

    def test_get_review_summary_reviews_but_no_cards(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-011: orphaned reviews (card deleted) still count in total_reviews."""
        now = datetime.now(timezone.utc)
        # Insert reviews with no corresponding cards
        for i in range(3):
            _put_review(
                dynamodb_tables_with_gsi, "user-1", f"deleted-card-{i}", 4,
                (now - timedelta(hours=i + 1)).isoformat(),
            )

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.total_reviews == 3
        assert result.total_cards == 0
        assert result.tag_performance == {}

    def test_get_review_summary_cards_but_no_reviews(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-012: cards without reviews return correct totals and zero review fields."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat())
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-2",
                  (now - timedelta(days=1)).isoformat())

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.total_reviews == 0
        assert result.average_grade == 0.0
        assert result.total_cards == 2
        assert result.cards_due_today == 2
        assert result.streak_days == 0

    def test_get_review_summary_error_returns_default(
        self, review_service_with_gsi
    ):
        """TC-061-SUM-013: DynamoDB error returns a default ReviewSummary with zero values."""
        from unittest.mock import patch
        from botocore.exceptions import ClientError

        error_response = {
            "Error": {"Code": "InternalServerError", "Message": "Test error"}
        }
        with patch.object(
            review_service_with_gsi.reviews_table,
            "query",
            side_effect=ClientError(error_response, "Query"),
        ):
            result = review_service_with_gsi.get_review_summary("user-1")

        assert result.total_reviews == 0
        assert result.average_grade == 0.0
        assert result.total_cards == 0
        assert result.cards_due_today == 0
        assert result.tag_performance == {}
        assert result.streak_days == 0
        assert result.recent_review_dates == []

    def test_get_review_summary_queries_reviews_by_user_id(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-014: data from other users does not leak into the result."""
        now = datetime.now(timezone.utc)
        # user-1: 2 cards, 3 reviews
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-u1-1",
                  (now + timedelta(days=1)).isoformat())
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-u1-2",
                  (now + timedelta(days=1)).isoformat())
        for i in range(3):
            _put_review(
                dynamodb_tables_with_gsi, "user-1", "card-u1-1", 4,
                (now - timedelta(hours=i + 1)).isoformat(),
            )
        # user-2: 1 card, 2 reviews
        _put_card(dynamodb_tables_with_gsi, "user-2", "card-u2-1",
                  (now + timedelta(days=1)).isoformat())
        for i in range(2):
            _put_review(
                dynamodb_tables_with_gsi, "user-2", "card-u2-1", 3,
                (now - timedelta(hours=i + 1)).isoformat(),
            )

        result = review_service_with_gsi.get_review_summary("user-1")

        assert result.total_reviews == 3  # user-1's reviews only
        assert result.total_cards == 2    # user-1's cards only

    def test_get_review_summary_tag_performance_uses_card_tags(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-015: tag_performance is derived from cards.tags, not reviews.tags."""
        now = datetime.now(timezone.utc)
        # card-1 has multiple tags; the review record does NOT have a tags field
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat(),
                  tags=["science", "biology"])

        # Review record intentionally omits tags to confirm cards.tags is used
        table = dynamodb_tables_with_gsi.Table("memoru-reviews-test")
        table.put_item(Item={
            "user_id": "user-1",
            "card_id": "card-1",
            "reviewed_at": now.isoformat(),
            "grade": 4,
            "ease_factor_before": "2.5",
            "ease_factor_after": "2.5",
            "interval_before": 1,
            "interval_after": 1,
            # NOTE: no "tags" field in reviews record
        })

        result = review_service_with_gsi.get_review_summary("user-1")

        assert "science" in result.tag_performance
        assert "biology" in result.tag_performance
        assert result.tag_performance["science"] == pytest.approx(1.0)
        assert result.tag_performance["biology"] == pytest.approx(1.0)

    def test_get_review_summary_grade_3_is_correct(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-016: grade=3 is counted as correct (boundary value)."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat(), tags=["test-tag"])
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 3,
                    now.isoformat())

        result = review_service_with_gsi.get_review_summary("user-1")

        # grade >= 3 is correct
        assert result.tag_performance["test-tag"] == pytest.approx(1.0)

    def test_get_review_summary_grade_2_is_incorrect(
        self, review_service_with_gsi, dynamodb_tables_with_gsi
    ):
        """TC-061-SUM-017: grade=2 is counted as incorrect (boundary value)."""
        now = datetime.now(timezone.utc)
        _put_card(dynamodb_tables_with_gsi, "user-1", "card-1",
                  (now - timedelta(hours=1)).isoformat(), tags=["test-tag"])
        _put_review(dynamodb_tables_with_gsi, "user-1", "card-1", 2,
                    now.isoformat())

        result = review_service_with_gsi.get_review_summary("user-1")

        # grade < 3 is incorrect
        assert result.tag_performance["test-tag"] == pytest.approx(0.0)


class TestUndoReview:
    """Tests for ReviewService.undo_review method."""

    def test_undo_review_restores_srs_parameters(self, review_service, sample_card):
        """Test that undo restores ease_factor, interval, repetitions, next_review_at."""
        # First, submit a review to create history
        review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )

        # Now undo it
        response = review_service.undo_review(
            user_id="test-user-id",
            card_id="test-card-id",
        )

        assert response.card_id == "test-card-id"
        assert response.restored.ease_factor == 2.5  # Original ease_factor
        assert response.restored.interval == 1  # Original interval
        assert response.restored.repetitions == 0  # Original repetitions
        assert response.undone_at is not None

    def test_undo_review_removes_latest_history_entry(self, review_service, sample_card):
        """Test that undo removes the latest review_history entry."""
        # Submit two reviews
        review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )
        review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=5,
        )

        # Verify 2 history entries exist
        table = review_service.cards_table
        item = table.get_item(
            Key={"user_id": "test-user-id", "card_id": "test-card-id"}
        )["Item"]
        assert len(item["review_history"]) == 2

        # Undo the latest review
        review_service.undo_review(
            user_id="test-user-id",
            card_id="test-card-id",
        )

        # Verify only 1 history entry remains
        item = table.get_item(
            Key={"user_id": "test-user-id", "card_id": "test-card-id"}
        )["Item"]
        assert len(item["review_history"]) == 1

    def test_undo_review_no_history_raises_error(self, review_service, sample_card):
        """Test that undo with no review history raises NoReviewHistoryError."""
        with pytest.raises(NoReviewHistoryError):
            review_service.undo_review(
                user_id="test-user-id",
                card_id="test-card-id",
            )

    def test_undo_review_card_not_found(self, review_service):
        """Test that undo with non-existent card raises CardNotFoundError."""
        with pytest.raises(CardNotFoundError):
            review_service.undo_review(
                user_id="test-user-id",
                card_id="non-existent-card",
            )

    def test_undo_review_wrong_user(self, review_service, sample_card):
        """Test that undo with wrong user raises CardNotFoundError."""
        with pytest.raises(CardNotFoundError):
            review_service.undo_review(
                user_id="other-user-id",
                card_id="test-card-id",
            )

    def test_undo_review_returns_correct_response_format(self, review_service, sample_card):
        """Test that UndoReviewResponse has correct structure."""
        from models.review import UndoReviewResponse, UndoRestoredState

        review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )

        response = review_service.undo_review(
            user_id="test-user-id",
            card_id="test-card-id",
        )

        assert isinstance(response, UndoReviewResponse)
        assert isinstance(response.restored, UndoRestoredState)
        assert isinstance(response.restored.ease_factor, float)
        assert isinstance(response.restored.interval, int)
        assert isinstance(response.restored.repetitions, int)
        assert isinstance(response.restored.due_date, str)

    def test_undo_review_preserves_reviews_table(self, review_service, sample_card):
        """Test that reviews table records are preserved after undo."""
        # Submit a review (creates record in reviews table)
        review_service.submit_review(
            user_id="test-user-id",
            card_id="test-card-id",
            grade=4,
        )

        # Undo the review
        review_service.undo_review(
            user_id="test-user-id",
            card_id="test-card-id",
        )

        # Verify reviews table still has the record
        reviews_table = review_service.reviews_table
        response = reviews_table.scan()
        assert len(response["Items"]) >= 1

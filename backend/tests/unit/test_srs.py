"""Unit tests for SM-2 algorithm."""

import pytest
from datetime import datetime, timezone, timedelta

from src.services.srs import (
    calculate_sm2,
    add_review_history,
    ReviewHistoryEntry,
    SM2Result,
    EASE_FACTOR_MINIMUM,
)


class TestSM2Algorithm:
    """Tests for SM-2 algorithm calculation."""

    def test_grade_5_first_review(self):
        """Test perfect response on first review."""
        result = calculate_sm2(
            grade=5,
            repetitions=0,
            ease_factor=2.5,
            interval=1,
        )

        assert result.repetitions == 1
        assert result.ease_factor == 2.6
        assert result.interval == 1

    def test_grade_4_second_review(self):
        """Test correct with hesitation on second review.

        Note: SM-2 algorithm defines:
        - 1st correct review: interval = 1
        - 2nd correct review: interval = 6
        - 3rd+ correct review: interval = round(prev_interval * ease_factor)
        """
        result = calculate_sm2(
            grade=4,
            repetitions=1,
            ease_factor=2.5,
            interval=6,
        )

        assert result.repetitions == 2
        assert result.ease_factor == 2.5
        assert result.interval == 6  # Second review always gives interval=6

    def test_grade_3_first_review(self):
        """Test correct with difficulty on first review."""
        result = calculate_sm2(
            grade=3,
            repetitions=0,
            ease_factor=2.5,
            interval=1,
        )

        assert result.repetitions == 1
        assert result.ease_factor == 2.36  # 2.5 + 0.1 - 2*0.08 - 2*0.02*2 = 2.36
        assert result.interval == 1

    def test_grade_2_reset(self):
        """Test incorrect response resets progress."""
        result = calculate_sm2(
            grade=2,
            repetitions=3,
            ease_factor=2.5,
            interval=15,
        )

        assert result.repetitions == 0
        assert result.interval == 1

    def test_grade_1_reset(self):
        """Test incorrect response resets progress."""
        result = calculate_sm2(
            grade=1,
            repetitions=5,
            ease_factor=2.5,
            interval=30,
        )

        assert result.repetitions == 0
        assert result.interval == 1

    def test_grade_0_complete_blackout(self):
        """Test complete blackout resets progress."""
        result = calculate_sm2(
            grade=0,
            repetitions=5,
            ease_factor=2.5,
            interval=30,
        )

        assert result.repetitions == 0
        assert result.interval == 1

    def test_ease_factor_minimum_boundary(self):
        """Test ease factor doesn't go below minimum."""
        # Grade 0 reduces ease factor significantly
        result = calculate_sm2(
            grade=0,
            repetitions=0,
            ease_factor=1.3,  # Already at minimum
            interval=1,
        )

        # Ease factor should stay at minimum
        assert result.ease_factor == EASE_FACTOR_MINIMUM

    def test_ease_factor_goes_to_minimum(self):
        """Test ease factor is clamped to minimum when calculation goes below."""
        # With grade=0, ease_factor change = 0.1 - 5*0.08 - 5*0.02*5 = 0.1 - 0.4 - 0.5 = -0.8
        result = calculate_sm2(
            grade=0,
            repetitions=0,
            ease_factor=1.5,  # 1.5 - 0.8 = 0.7, should be clamped to 1.3
            interval=1,
        )

        assert result.ease_factor == EASE_FACTOR_MINIMUM

    def test_interval_calculation_third_review(self):
        """Test interval increases correctly on third and subsequent reviews."""
        result = calculate_sm2(
            grade=4,
            repetitions=2,
            ease_factor=2.5,
            interval=15,
        )

        assert result.repetitions == 3
        assert result.interval == 38  # round(15 * 2.5) = 38 (rounded from 37.5)

    def test_next_review_at_is_set(self):
        """Test next_review_at is calculated correctly."""
        before = datetime.now(timezone.utc)
        result = calculate_sm2(
            grade=4,
            repetitions=1,
            ease_factor=2.5,
            interval=6,
        )
        after = datetime.now(timezone.utc)

        # Next review should be interval days from now
        expected_min = before + timedelta(days=result.interval)
        expected_max = after + timedelta(days=result.interval)

        assert expected_min <= result.next_review_at <= expected_max

    def test_invalid_grade_negative(self):
        """Test invalid grade raises ValueError."""
        with pytest.raises(ValueError, match="Grade must be between 0 and 5"):
            calculate_sm2(grade=-1, repetitions=0, ease_factor=2.5, interval=1)

    def test_invalid_grade_too_high(self):
        """Test invalid grade raises ValueError."""
        with pytest.raises(ValueError, match="Grade must be between 0 and 5"):
            calculate_sm2(grade=6, repetitions=0, ease_factor=2.5, interval=1)


class TestReviewHistory:
    """Tests for review history management."""

    def test_add_first_entry(self):
        """Test adding first history entry."""
        entry = ReviewHistoryEntry(
            reviewed_at=datetime.now(timezone.utc),
            grade=4,
            ease_factor_before=2.5,
            ease_factor_after=2.5,
            interval_before=1,
            interval_after=6,
        )

        history = add_review_history(None, entry)

        assert len(history) == 1
        assert history[0]["grade"] == 4
        # Ease factors stored as strings for DynamoDB compatibility
        assert history[0]["ease_factor_before"] == "2.5"
        assert history[0]["ease_factor_after"] == "2.5"

    def test_add_to_existing_history(self):
        """Test adding to existing history."""
        existing = [
            {
                "reviewed_at": "2024-01-01T12:00:00+00:00",
                "grade": 3,
                "ease_factor_before": 2.5,
                "ease_factor_after": 2.36,
                "interval_before": 1,
                "interval_after": 1,
            }
        ]

        entry = ReviewHistoryEntry(
            reviewed_at=datetime.now(timezone.utc),
            grade=4,
            ease_factor_before=2.36,
            ease_factor_after=2.36,
            interval_before=1,
            interval_after=6,
        )

        history = add_review_history(existing, entry)

        assert len(history) == 2
        assert history[1]["grade"] == 4

    def test_max_entries_limit(self):
        """Test that history is limited to max entries."""
        existing = [{"reviewed_at": f"2024-01-{i:02d}T12:00:00+00:00", "grade": 4} for i in range(1, 101)]

        entry = ReviewHistoryEntry(
            reviewed_at=datetime.now(timezone.utc),
            grade=5,
            ease_factor_before=2.5,
            ease_factor_after=2.6,
            interval_before=15,
            interval_after=38,
        )

        history = add_review_history(existing, entry, max_entries=100)

        assert len(history) == 100
        # Newest entry should be last
        assert history[-1]["grade"] == 5
        # Oldest entry should have been removed
        assert history[0]["reviewed_at"] != "2024-01-01T12:00:00+00:00"

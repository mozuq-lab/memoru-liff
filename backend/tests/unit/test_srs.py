"""Unit tests for SM-2 algorithm."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from services.srs import (
    calculate_sm2,
    calculate_next_review_boundary,
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


class TestCalculateNextReviewBoundary:
    """Tests for day-boundary normalization of next_review_at."""

    def test_after_boundary_sets_next_day(self):
        """REQ-001: 境界時刻以降の復習で翌日境界に設定される。
        10:00 JST に復習、interval=1 → 翌日 04:00 JST。"""
        # 2026-03-01 10:00 JST = 2026-03-01 01:00 UTC
        mock_now = datetime(2026, 3, 1, 1, 0, 0, tzinfo=timezone.utc)
        with patch("services.srs.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = calculate_next_review_boundary(
                interval=1,
                user_timezone="Asia/Tokyo",
                day_start_hour=4,
            )

        # 翌日 04:00 JST = 2026-03-01 19:00 UTC
        expected = datetime(2026, 3, 1, 19, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_before_boundary_treats_as_previous_day(self):
        """REQ-001: 境界時刻以前の復習（前日扱い）で当日境界に設定される。
        01:00 JST に復習（境界前=前日扱い）、interval=1 → 当日 04:00 JST。"""
        # 2026-03-01 01:00 JST = 2026-02-28 16:00 UTC
        mock_now = datetime(2026, 2, 28, 16, 0, 0, tzinfo=timezone.utc)
        with patch("services.srs.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = calculate_next_review_boundary(
                interval=1,
                user_timezone="Asia/Tokyo",
                day_start_hour=4,
            )

        # 当日 04:00 JST = 2026-02-28 19:00 UTC
        expected = datetime(2026, 2, 28, 19, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_interval_greater_than_one(self):
        """REQ-001: interval > 1 の場合に正しい日数後の境界に設定される。
        14:00 JST に復習、interval=6 → 6日後 04:00 JST。"""
        # 2026-03-01 14:00 JST = 2026-03-01 05:00 UTC
        mock_now = datetime(2026, 3, 1, 5, 0, 0, tzinfo=timezone.utc)
        with patch("services.srs.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = calculate_next_review_boundary(
                interval=6,
                user_timezone="Asia/Tokyo",
                day_start_hour=4,
            )

        # 2026-03-07 04:00 JST = 2026-03-06 19:00 UTC
        expected = datetime(2026, 3, 6, 19, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_default_parameters(self):
        """デフォルト値 (Asia/Tokyo, day_start_hour=4) で正しく動作する。"""
        mock_now = datetime(2026, 3, 1, 1, 0, 0, tzinfo=timezone.utc)  # 10:00 JST
        with patch("services.srs.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = calculate_next_review_boundary(interval=1)

        expected = datetime(2026, 3, 1, 19, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_day_start_hour_14_night_shift(self):
        """REQ-002: day_start_hour=14 での夜勤ユーザー向け設定テスト。
        23:00 JST に復習 (14以降)、interval=1 → 翌日 14:00 JST。"""
        # 2026-03-01 23:00 JST = 2026-03-01 14:00 UTC
        mock_now = datetime(2026, 3, 1, 14, 0, 0, tzinfo=timezone.utc)
        with patch("services.srs.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = calculate_next_review_boundary(
                interval=1,
                user_timezone="Asia/Tokyo",
                day_start_hour=14,
            )

        # 2026-03-02 14:00 JST = 2026-03-02 05:00 UTC
        expected = datetime(2026, 3, 2, 5, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_day_start_hour_0_midnight(self):
        """day_start_hour=0 (深夜0時) でも正しく動作する。"""
        # 2026-03-01 15:00 JST = 2026-03-01 06:00 UTC
        mock_now = datetime(2026, 3, 1, 6, 0, 0, tzinfo=timezone.utc)
        with patch("services.srs.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = calculate_next_review_boundary(
                interval=1,
                user_timezone="Asia/Tokyo",
                day_start_hour=0,
            )

        # 2026-03-02 00:00 JST = 2026-03-01 15:00 UTC
        expected = datetime(2026, 3, 1, 15, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_decimal_day_start_hour(self):
        """REQ-001: Decimal(4) を渡しても int(4) と同じ結果になること。"""
        from decimal import Decimal

        mock_now = datetime(2026, 3, 1, 1, 0, 0, tzinfo=timezone.utc)  # 10:00 JST
        with patch("services.srs.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = calculate_next_review_boundary(
                interval=Decimal(1),
                user_timezone="Asia/Tokyo",
                day_start_hour=Decimal(4),
            )

        expected = datetime(2026, 3, 1, 19, 0, 0, tzinfo=timezone.utc)
        assert result == expected

    def test_decimal_boundary_values(self):
        """REQ-001: Decimal(0) / Decimal(23) の境界値テスト。"""
        from decimal import Decimal

        mock_now = datetime(2026, 3, 1, 6, 0, 0, tzinfo=timezone.utc)  # 15:00 JST
        with patch("services.srs.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            # day_start_hour=0
            result_0 = calculate_next_review_boundary(
                interval=Decimal(1),
                user_timezone="Asia/Tokyo",
                day_start_hour=Decimal(0),
            )
            expected_0 = datetime(2026, 3, 1, 15, 0, 0, tzinfo=timezone.utc)
            assert result_0 == expected_0

            # day_start_hour=23
            result_23 = calculate_next_review_boundary(
                interval=Decimal(1),
                user_timezone="Asia/Tokyo",
                day_start_hour=Decimal(23),
            )
            # 15:00 JST < 23, so effective_date = previous day (2026-02-28)
            # target_date = 2026-03-01, boundary = 2026-03-01 23:00 JST = 2026-03-01 14:00 UTC
            expected_23 = datetime(2026, 3, 1, 14, 0, 0, tzinfo=timezone.utc)
            assert result_23 == expected_23

    def test_invalid_day_start_hour_range(self):
        """REQ-001: 範囲外の day_start_hour で ValueError が発生すること。"""
        from decimal import Decimal

        with pytest.raises(ValueError, match="day_start_hour must be 0-23"):
            calculate_next_review_boundary(
                interval=1,
                user_timezone="Asia/Tokyo",
                day_start_hour=Decimal(24),
            )

        with pytest.raises(ValueError, match="day_start_hour must be 0-23"):
            calculate_next_review_boundary(
                interval=1,
                user_timezone="Asia/Tokyo",
                day_start_hour=Decimal(-1),
            )

    def test_utc_timezone(self):
        """異なるタイムゾーン (UTC) での正規化テスト。"""
        # 2026-03-01 10:00 UTC
        mock_now = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)
        with patch("services.srs.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            result = calculate_next_review_boundary(
                interval=1,
                user_timezone="UTC",
                day_start_hour=4,
            )

        # 2026-03-02 04:00 UTC
        expected = datetime(2026, 3, 2, 4, 0, 0, tzinfo=timezone.utc)
        assert result == expected


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

    def test_add_entry_with_repetitions_and_next_review_at(self):
        """Test adding entry with repetitions_before/after and next_review_at_before/after."""
        entry = ReviewHistoryEntry(
            reviewed_at=datetime.now(timezone.utc),
            grade=4,
            ease_factor_before=2.5,
            ease_factor_after=2.5,
            interval_before=6,
            interval_after=15,
            repetitions_before=2,
            repetitions_after=3,
            next_review_at_before="2026-02-20T10:00:00+00:00",
            next_review_at_after="2026-03-07T10:00:00+00:00",
        )

        history = add_review_history(None, entry)

        assert len(history) == 1
        assert history[0]["repetitions_before"] == 2
        assert history[0]["repetitions_after"] == 3
        assert history[0]["next_review_at_before"] == "2026-02-20T10:00:00+00:00"
        assert history[0]["next_review_at_after"] == "2026-03-07T10:00:00+00:00"

    def test_add_entry_without_optional_fields(self):
        """Test that optional fields are omitted when None (backward compat)."""
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
        assert "repetitions_before" not in history[0]
        assert "repetitions_after" not in history[0]
        assert "next_review_at_before" not in history[0]
        assert "next_review_at_after" not in history[0]

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

"""Unit tests for stats models."""

import pytest
from pydantic import ValidationError

from models.stats import (
    ForecastDay,
    ForecastResponse,
    StatsResponse,
    WeakCard,
    WeakCardsResponse,
)


class TestStatsResponse:
    """Tests for StatsResponse model."""

    def test_valid_stats_response(self):
        """Test creating a valid StatsResponse."""
        response = StatsResponse(
            total_cards=50,
            learned_cards=30,
            unlearned_cards=20,
            cards_due_today=10,
            total_reviews=100,
            average_grade=3.5,
            streak_days=7,
            tag_performance={"math": 0.8, "science": 0.6},
        )
        assert response.total_cards == 50
        assert response.learned_cards == 30
        assert response.unlearned_cards == 20
        assert response.cards_due_today == 10
        assert response.total_reviews == 100
        assert response.average_grade == 3.5
        assert response.streak_days == 7
        assert response.tag_performance == {"math": 0.8, "science": 0.6}

    def test_stats_response_default_tag_performance(self):
        """Test StatsResponse with default empty tag_performance."""
        response = StatsResponse(
            total_cards=0,
            learned_cards=0,
            unlearned_cards=0,
            cards_due_today=0,
            total_reviews=0,
            average_grade=0.0,
            streak_days=0,
        )
        assert response.tag_performance == {}

    def test_stats_response_missing_required_field(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            StatsResponse(
                total_cards=10,
                # missing other required fields
            )

    def test_stats_response_serialization(self):
        """Test StatsResponse serialization to dict."""
        response = StatsResponse(
            total_cards=5,
            learned_cards=3,
            unlearned_cards=2,
            cards_due_today=1,
            total_reviews=10,
            average_grade=4.0,
            streak_days=3,
            tag_performance={"english": 0.9},
        )
        data = response.model_dump()
        assert data["total_cards"] == 5
        assert data["tag_performance"] == {"english": 0.9}


class TestWeakCard:
    """Tests for WeakCard model."""

    def test_valid_weak_card(self):
        """Test creating a valid WeakCard."""
        card = WeakCard(
            card_id="card-001",
            front="Question",
            back="Answer",
            ease_factor=1.3,
            repetitions=5,
            deck_id="deck-001",
        )
        assert card.card_id == "card-001"
        assert card.ease_factor == 1.3
        assert card.repetitions == 5
        assert card.deck_id == "deck-001"

    def test_weak_card_optional_deck_id(self):
        """Test WeakCard with no deck_id."""
        card = WeakCard(
            card_id="card-001",
            front="Question",
            back="Answer",
            ease_factor=1.5,
            repetitions=3,
        )
        assert card.deck_id is None

    def test_weak_card_missing_required_field(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            WeakCard(
                card_id="card-001",
                front="Question",
                # missing back, ease_factor, repetitions
            )


class TestWeakCardsResponse:
    """Tests for WeakCardsResponse model."""

    def test_valid_weak_cards_response(self):
        """Test creating a valid WeakCardsResponse."""
        cards = [
            WeakCard(
                card_id="card-001",
                front="Q1",
                back="A1",
                ease_factor=1.3,
                repetitions=5,
            ),
            WeakCard(
                card_id="card-002",
                front="Q2",
                back="A2",
                ease_factor=1.5,
                repetitions=3,
            ),
        ]
        response = WeakCardsResponse(weak_cards=cards, total_count=10)
        assert len(response.weak_cards) == 2
        assert response.total_count == 10

    def test_empty_weak_cards_response(self):
        """Test WeakCardsResponse with empty list."""
        response = WeakCardsResponse(weak_cards=[], total_count=0)
        assert response.weak_cards == []
        assert response.total_count == 0


class TestForecastDay:
    """Tests for ForecastDay model."""

    def test_valid_forecast_day(self):
        """Test creating a valid ForecastDay."""
        day = ForecastDay(date="2026-03-05", due_count=5)
        assert day.date == "2026-03-05"
        assert day.due_count == 5

    def test_forecast_day_missing_field(self):
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            ForecastDay(date="2026-03-05")


class TestForecastResponse:
    """Tests for ForecastResponse model."""

    def test_valid_forecast_response(self):
        """Test creating a valid ForecastResponse."""
        forecast = [
            ForecastDay(date="2026-03-05", due_count=3),
            ForecastDay(date="2026-03-06", due_count=5),
        ]
        response = ForecastResponse(forecast=forecast)
        assert len(response.forecast) == 2
        assert response.forecast[0].date == "2026-03-05"

    def test_empty_forecast_response(self):
        """Test ForecastResponse with empty list."""
        response = ForecastResponse(forecast=[])
        assert response.forecast == []

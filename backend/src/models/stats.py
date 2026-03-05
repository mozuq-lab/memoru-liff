"""Stats models for Memoru LIFF application."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class StatsResponse(BaseModel):
    """Response model for learning statistics summary."""

    total_cards: int = Field(..., description="Total number of cards")
    learned_cards: int = Field(..., description="Cards with repetitions >= 1")
    unlearned_cards: int = Field(..., description="Cards with repetitions == 0")
    cards_due_today: int = Field(..., description="Cards due for review today")
    total_reviews: int = Field(..., description="Total number of reviews")
    average_grade: float = Field(..., description="Average review grade")
    streak_days: int = Field(..., description="Consecutive study days")
    tag_performance: Dict[str, float] = Field(
        default_factory=dict,
        description="Tag -> fraction of reviews with grade >= 3",
    )


class WeakCard(BaseModel):
    """Information about a weak card (low ease factor)."""

    card_id: str
    front: str
    back: str
    ease_factor: float
    repetitions: int
    deck_id: Optional[str] = None


class WeakCardsResponse(BaseModel):
    """Response model for weak cards list."""

    weak_cards: List[WeakCard]
    total_count: int


class ForecastDay(BaseModel):
    """Forecast for a single day."""

    date: str = Field(..., description="Date in YYYY-MM-DD format")
    due_count: int = Field(..., description="Number of cards due on this date")


class ForecastResponse(BaseModel):
    """Response model for review forecast."""

    forecast: List[ForecastDay]

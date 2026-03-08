"""Review models for Memoru LIFF application."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from models.card import Reference


class ReviewRequest(BaseModel):
    """Request model for submitting a review."""

    grade: int = Field(..., ge=0, le=5, description="Review grade (0-5)")


class ReviewPreviousState(BaseModel):
    """Previous state before review."""

    ease_factor: float
    interval: int
    repetitions: int
    due_date: Optional[str] = None


class ReviewUpdatedState(BaseModel):
    """Updated state after review."""

    ease_factor: float
    interval: int
    repetitions: int
    due_date: str


class ReviewResponse(BaseModel):
    """Response model for a completed review."""

    card_id: str
    grade: int
    previous: ReviewPreviousState
    updated: ReviewUpdatedState
    reviewed_at: datetime


class UndoRestoredState(BaseModel):
    """Restored state after undo."""

    ease_factor: float
    interval: int
    repetitions: int
    due_date: str


class UndoReviewResponse(BaseModel):
    """Response model for undo review."""

    card_id: str
    restored: UndoRestoredState
    undone_at: datetime


class DueCardInfo(BaseModel):
    """Information about a card due for review."""

    card_id: str
    front: str
    back: str
    deck_id: Optional[str] = None
    due_date: Optional[str] = None
    overdue_days: int = 0
    references: List[Reference] = Field(default_factory=list)


class DueCardsResponse(BaseModel):
    """Response model for due cards list."""

    due_cards: List[DueCardInfo]
    total_due_count: int
    next_due_date: Optional[str] = None

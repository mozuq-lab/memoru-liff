"""SM-2 Spaced Repetition System algorithm implementation."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional


@dataclass
class SM2Result:
    """Result of SM-2 algorithm calculation."""

    repetitions: int
    ease_factor: float
    interval: int
    next_review_at: datetime


# Ease factor lower bound
EASE_FACTOR_MINIMUM = 1.3


def calculate_sm2(
    grade: int,
    repetitions: int,
    ease_factor: float,
    interval: int,
) -> SM2Result:
    """
    Calculate next review parameters using SM-2 algorithm.

    The SuperMemo 2 algorithm calculates the optimal time interval
    for reviewing a flashcard based on the user's performance.

    Args:
        grade: Review grade (0-5)
            - 0: Complete blackout
            - 1: Incorrect response; correct answer remembered
            - 2: Incorrect; correct answer seemed easy to recall
            - 3: Correct with serious difficulty
            - 4: Correct with some hesitation
            - 5: Perfect response
        repetitions: Current number of successful reviews
        ease_factor: Current difficulty factor (>= 1.3)
        interval: Current review interval in days

    Returns:
        SM2Result with updated parameters

    Raises:
        ValueError: If grade is not in range 0-5
    """
    if not 0 <= grade <= 5:
        raise ValueError(f"Grade must be between 0 and 5, got {grade}")

    # Grade 0-2: Incorrect response - reset
    if grade < 3:
        new_repetitions = 0
        new_interval = 1
    else:
        # Grade 3-5: Correct response
        if repetitions == 0:
            new_interval = 1
        elif repetitions == 1:
            new_interval = 6
        else:
            new_interval = round(interval * ease_factor)
        new_repetitions = repetitions + 1

    # Update ease factor (applies to all grades)
    new_ease_factor = ease_factor + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))

    # Enforce ease factor minimum
    if new_ease_factor < EASE_FACTOR_MINIMUM:
        new_ease_factor = EASE_FACTOR_MINIMUM

    # Calculate next review date
    now = datetime.now(timezone.utc)
    next_review_at = now + timedelta(days=new_interval)

    return SM2Result(
        repetitions=new_repetitions,
        ease_factor=round(new_ease_factor, 2),
        interval=new_interval,
        next_review_at=next_review_at,
    )


@dataclass
class ReviewHistoryEntry:
    """Single entry in review history."""

    reviewed_at: datetime
    grade: int
    ease_factor_before: float
    ease_factor_after: float
    interval_before: int
    interval_after: int


def add_review_history(
    history: Optional[List[dict]],
    entry: ReviewHistoryEntry,
    max_entries: int = 100,
) -> List[dict]:
    """
    Add a new entry to review history, maintaining max size.

    Args:
        history: Existing history list or None
        entry: New history entry
        max_entries: Maximum number of entries to keep

    Returns:
        Updated history list with newest entry added
    """
    if history is None:
        history = []

    # Convert floats to strings for DynamoDB compatibility
    new_entry = {
        "reviewed_at": entry.reviewed_at.isoformat(),
        "grade": entry.grade,
        "ease_factor_before": str(entry.ease_factor_before),
        "ease_factor_after": str(entry.ease_factor_after),
        "interval_before": entry.interval_before,
        "interval_after": entry.interval_after,
    }

    history.append(new_entry)

    # Keep only the most recent entries
    if len(history) > max_entries:
        history = history[-max_entries:]

    return history

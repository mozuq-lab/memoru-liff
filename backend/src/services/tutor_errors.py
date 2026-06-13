"""Tutor feature domain exceptions.

TutorService と TutorSessionRepository の双方から参照されるため、循環 import を避けるべく
独立モジュールに切り出す。後方互換のため tutor_service から再エクスポートする
（``from services.tutor_service import SessionNotFoundError`` を維持）。
"""


class TutorServiceError(Exception):
    """Base exception for TutorService errors."""


class SessionNotFoundError(TutorServiceError):
    """Raised when a session cannot be found."""


class SessionEndedError(TutorServiceError):
    """Raised when trying to interact with an ended/timed_out session."""


class MessageLimitError(TutorServiceError):
    """Raised when session message limit is reached."""


class ConcurrentSendError(TutorServiceError):
    """Raised when concurrent send_message is detected (optimistic lock failed)."""


class DeckNotFoundError(TutorServiceError):
    """Raised when a deck cannot be found."""


class EmptyDeckError(TutorServiceError):
    """Raised when a deck has no cards."""


class InsufficientReviewDataError(TutorServiceError):
    """Raised when weak_point mode is requested but no review history exists."""

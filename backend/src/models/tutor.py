"""Pydantic models for AI Tutor feature."""

from typing import Literal

from pydantic import BaseModel, Field


class TutorMessage(BaseModel):
    """Individual message within a tutor session."""

    role: Literal["user", "assistant"]
    content: str
    related_cards: list[str] = Field(default_factory=list)
    timestamp: str


class TutorSessionResponse(BaseModel):
    """Session data returned to the client."""

    session_id: str
    deck_id: str
    mode: Literal["free_talk", "quiz", "weak_point"]
    status: Literal["active", "ended", "timed_out"]
    messages: list[TutorMessage]
    message_count: int
    created_at: str
    updated_at: str
    ended_at: str | None = None


class StartSessionRequest(BaseModel):
    """Request to start a new tutor session."""

    deck_id: str = Field(..., min_length=1)
    mode: Literal["free_talk", "quiz", "weak_point"]


class SendMessageRequest(BaseModel):
    """Request to send a message in a tutor session."""

    content: str = Field(..., min_length=1, max_length=2000)


class SendMessageResponse(BaseModel):
    """Response after sending a message."""

    message: TutorMessage
    session_id: str
    message_count: int
    is_limit_reached: bool


class SessionListResponse(BaseModel):
    """List of tutor sessions."""

    sessions: list[TutorSessionResponse]


LearningMode = Literal["free_talk", "quiz", "weak_point"]

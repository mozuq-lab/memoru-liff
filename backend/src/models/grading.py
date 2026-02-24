"""Grading models for Memoru LIFF application.

TASK-0059: 回答採点モデル・プロンプト・AI実装

GradeAnswerRequest / GradeAnswerResponse Pydantic モデルを提供する。
"""

from typing import Any, Dict

from pydantic import BaseModel, Field, field_validator


class GradeAnswerRequest(BaseModel):
    """Request model for AI answer grading."""

    user_answer: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User's answer text to be graded",
    )

    @field_validator("user_answer")
    @classmethod
    def validate_user_answer(cls, v: str) -> str:
        """Validate user_answer is not just whitespace."""
        if not v.strip():
            raise ValueError("user_answer cannot be empty or whitespace only")
        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_answer": "東京",
                }
            ]
        }
    }


class GradeAnswerResponse(BaseModel):
    """Response model for AI answer grading."""

    grade: int = Field(
        ...,
        ge=0,
        le=5,
        description="SM-2 grade (0-5)",
    )
    reasoning: str = Field(
        ...,
        description="AI grading reasoning",
    )
    card_front: str = Field(
        ...,
        description="Card question (for reference display)",
    )
    card_back: str = Field(
        ...,
        description="Card correct answer (for reference display)",
    )
    grading_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Metadata (model_used, processing_time_ms, etc.)",
    )

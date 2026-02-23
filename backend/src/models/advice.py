"""Advice models for Memoru LIFF application."""

from typing import Any, Dict, List

from pydantic import BaseModel, Field


class LearningAdviceResponse(BaseModel):
    """Response model for AI learning advice."""

    advice_text: str = Field(
        ...,
        description="AI-generated learning advice text",
    )
    weak_areas: List[str] = Field(
        default_factory=list,
        description="List of weak areas identified by AI",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="List of specific study recommendations",
    )
    study_stats: Dict[str, Any] = Field(
        ...,
        description="Summary statistics from ReviewSummary for display",
    )
    advice_info: Dict[str, Any] = Field(
        ...,
        description="Metadata such as model_used and processing_time_ms",
    )

"""URL-based card generation models for Memoru LIFF application."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class GenerateFromUrlRequest(BaseModel):
    """Request model for URL-based card generation."""

    url: str = Field(
        ...,
        max_length=2048,
        description="Target page URL (https only)",
    )
    card_type: Literal["qa", "definition", "cloze"] = Field(
        default="qa",
        description="Type of cards to generate",
    )
    target_count: int = Field(
        default=10,
        ge=5,
        le=30,
        description="Target number of cards to generate",
    )
    difficulty: Literal["easy", "medium", "hard"] = Field(
        default="medium",
        description="Difficulty level of generated cards",
    )
    language: Literal["ja", "en"] = Field(
        default="ja",
        description="Output language for cards",
    )
    deck_id: Optional[str] = Field(
        default=None,
        description="Deck ID to save cards to",
    )
    profile_id: Optional[str] = Field(
        default=None,
        description="Browser profile ID for authenticated page access",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL format (detailed validation in url_validator)."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("URL cannot be empty")
        if not stripped.startswith("https://"):
            raise ValueError("URL must use https scheme")
        return stripped


class UrlGenerationInfoResponse(BaseModel):
    """Information about the URL generation process."""

    model_used: str
    processing_time_ms: int
    fetch_method: Literal["http", "browser"]
    chunk_count: int
    content_length: int


class PageInfoResponse(BaseModel):
    """Information about the fetched page."""

    url: str
    title: str
    fetched_at: str


class GenerateFromUrlResponse(BaseModel):
    """Response model for URL-based card generation."""

    generated_cards: List["GeneratedCardResponse"]
    generation_info: UrlGenerationInfoResponse
    page_info: PageInfoResponse
    warning: Optional[str] = None


# Import here to avoid circular dependency
from .generate import GeneratedCardResponse  # noqa: E402

GenerateFromUrlResponse.model_rebuild()

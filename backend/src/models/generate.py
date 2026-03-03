"""Card generation models for Memoru LIFF application."""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class GenerateCardsRequest(BaseModel):
    """Request model for AI card generation."""

    input_text: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        description="Source text to generate cards from",
    )
    card_count: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Number of cards to generate",
    )
    difficulty: Literal["easy", "medium", "hard"] = Field(
        default="medium",
        description="Difficulty level of generated cards",
    )
    language: Literal["ja", "en"] = Field(
        default="ja",
        description="Output language for cards",
    )

    @field_validator("input_text")
    @classmethod
    def validate_input_text(cls, v: str) -> str:
        """Validate input text is not just whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Input text cannot be empty or whitespace only")
        if len(stripped) < 5:
            raise ValueError("Input text must be at least 5 characters")
        return v


class GeneratedCardResponse(BaseModel):
    """Response model for a single generated card."""

    front: str
    back: str
    suggested_tags: List[str] = Field(default_factory=list)


class GenerationInfoResponse(BaseModel):
    """Information about the generation process."""

    input_length: int
    model_used: str
    processing_time_ms: int


class GenerateCardsResponse(BaseModel):
    """Response model for card generation."""

    generated_cards: List[GeneratedCardResponse]
    generation_info: GenerationInfoResponse


class RefineCardRequest(BaseModel):
    """Request model for AI card refinement."""

    front: str = Field(
        default="",
        max_length=1000,
        description="Card front text (question)",
    )
    back: str = Field(
        default="",
        max_length=2000,
        description="Card back text (answer)",
    )
    language: Literal["ja", "en"] = Field(
        default="ja",
        description="Output language for refinement",
    )

    @model_validator(mode="after")
    def validate_at_least_one(self) -> "RefineCardRequest":
        """Validate that at least one of front or back is provided."""
        if not self.front.strip() and not self.back.strip():
            raise ValueError("At least one of front or back must be provided")
        return self


class RefineCardResponse(BaseModel):
    """Response model for card refinement."""

    refined_front: str
    refined_back: str
    model_used: str
    processing_time_ms: int

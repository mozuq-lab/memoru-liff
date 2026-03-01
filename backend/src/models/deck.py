"""Deck models for Memoru LIFF application."""

import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class CreateDeckRequest(BaseModel):
    """Request model for creating a deck."""

    name: str = Field(..., min_length=1, max_length=100, description="Deck name")
    description: Optional[str] = Field(None, max_length=500, description="Deck description")
    color: Optional[str] = Field(None, max_length=7, description="Hex color code (e.g. #FF5733)")

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        """Validate hex color code format."""
        if v is None:
            return v
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Color must be a valid hex color code (e.g. #FF5733)")
        return v.upper()


class UpdateDeckRequest(BaseModel):
    """Request model for updating a deck."""

    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Deck name")
    description: Optional[str] = Field(None, max_length=500, description="Deck description")
    color: Optional[str] = Field(None, max_length=7, description="Hex color code (e.g. #FF5733)")

    @field_validator("color")
    @classmethod
    def validate_color(cls, v: Optional[str]) -> Optional[str]:
        """Validate hex color code format."""
        if v is None:
            return v
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError("Color must be a valid hex color code (e.g. #FF5733)")
        return v.upper()


class DeckResponse(BaseModel):
    """Response model for a deck."""

    deck_id: str
    user_id: str
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    card_count: int = 0
    due_count: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None


class DeckListResponse(BaseModel):
    """Response model for deck list."""

    decks: list[DeckResponse]
    total: int


class Deck(BaseModel):
    """Deck domain model."""

    deck_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    def to_response(self, card_count: int = 0, due_count: int = 0) -> DeckResponse:
        """Convert to API response model.

        Args:
            card_count: Number of cards in this deck.
            due_count: Number of due cards in this deck.

        Returns:
            DeckResponse object.
        """
        return DeckResponse(
            deck_id=self.deck_id,
            user_id=self.user_id,
            name=self.name,
            description=self.description,
            color=self.color,
            card_count=card_count,
            due_count=due_count,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item."""
        item: dict = {
            "user_id": self.user_id,
            "deck_id": self.deck_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
        }
        if self.description:
            item["description"] = self.description
        if self.color:
            item["color"] = self.color
        if self.updated_at:
            item["updated_at"] = self.updated_at.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "Deck":
        """Create Deck from DynamoDB item.

        Args:
            item: DynamoDB item dictionary.

        Returns:
            Deck instance.
        """
        return cls(
            deck_id=item["deck_id"],
            user_id=item["user_id"],
            name=item["name"],
            description=item.get("description"),
            color=item.get("color"),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]) if item.get("updated_at") else None,
        )

"""Card models for Memoru LIFF application."""

import uuid
from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Reference(BaseModel):
    """参考情報モデル。"""

    type: Literal["url", "book", "note"]
    value: str = Field(..., min_length=1, max_length=500)


class CreateCardRequest(BaseModel):
    """Request model for creating a card."""

    front: str = Field(..., min_length=1, max_length=1000, description="Front side text")
    back: str = Field(..., min_length=1, max_length=2000, description="Back side text")
    deck_id: Optional[str] = Field(None, description="Optional deck ID")
    tags: List[str] = Field(default_factory=list, description="Optional tags")
    references: List[Reference] = Field(default_factory=list, description="Optional references")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Validate tags."""
        if len(v) > 10:
            raise ValueError("Maximum 10 tags allowed")
        return [tag.strip()[:50] for tag in v if tag.strip()]

    @field_validator("references")
    @classmethod
    def validate_references(cls, v: List[Reference]) -> List[Reference]:
        """Validate references."""
        if len(v) > 5:
            raise ValueError("Maximum 5 references allowed")
        return v


class UpdateCardRequest(BaseModel):
    """Request model for updating a card."""

    front: Optional[str] = Field(None, min_length=1, max_length=1000)
    back: Optional[str] = Field(None, min_length=1, max_length=2000)
    deck_id: Optional[str] = None
    tags: Optional[List[str]] = None
    # 【interval フィールド】: 手動で復習間隔（日数）を設定するオプションフィールド
    # 【バリデーション】: ge=1（最小1日）, le=365（最大1年）の制約を適用
    # 【Optional の理由】: 未指定時は既存の interval/next_review_at を変更しない（後方互換性）
    # 🔵 信頼性レベル: 要件定義 REQ-101, REQ-102 より
    interval: Optional[int] = Field(None, ge=1, le=365, description="Review interval in days (1-365)")
    references: Optional[List[Reference]] = None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate tags."""
        if v is None:
            return v
        if len(v) > 10:
            raise ValueError("Maximum 10 tags allowed")
        return [tag.strip()[:50] for tag in v if tag.strip()]

    @field_validator("references")
    @classmethod
    def validate_references(cls, v: Optional[List[Reference]]) -> Optional[List[Reference]]:
        """Validate references."""
        if v is None:
            return v
        if len(v) > 5:
            raise ValueError("Maximum 5 references allowed")
        return v


class CardResponse(BaseModel):
    """Response model for a card."""

    card_id: str
    user_id: str
    front: str
    back: str
    deck_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    next_review_at: Optional[datetime] = None
    interval: int = 0
    ease_factor: float = 2.5
    repetitions: int = 0
    references: List[Reference] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime] = None


class CardListResponse(BaseModel):
    """Response model for card list."""

    cards: List[CardResponse]
    total: int
    next_cursor: Optional[str] = None


class Card(BaseModel):
    """Card domain model."""

    card_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    front: str
    back: str
    deck_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    references: List[Reference] = Field(default_factory=list)
    next_review_at: Optional[datetime] = None
    interval: int = 0  # Days until next review
    ease_factor: float = 2.5  # SM-2 ease factor
    repetitions: int = 0  # Number of successful reviews
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None

    def to_response(self) -> CardResponse:
        """Convert to API response model."""
        return CardResponse(
            card_id=self.card_id,
            user_id=self.user_id,
            front=self.front,
            back=self.back,
            deck_id=self.deck_id,
            tags=self.tags,
            references=self.references,
            next_review_at=self.next_review_at,
            interval=self.interval,
            ease_factor=self.ease_factor,
            repetitions=self.repetitions,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    def to_dynamodb_item(self) -> dict:
        """Convert to DynamoDB item."""
        item = {
            "user_id": self.user_id,
            "card_id": self.card_id,
            "front": self.front,
            "back": self.back,
            "tags": self.tags,
            "interval": self.interval,
            "ease_factor": str(self.ease_factor),  # DynamoDB doesn't support float directly
            "repetitions": self.repetitions,
            "created_at": self.created_at.isoformat(),
        }
        if self.references:
            item["references"] = [ref.model_dump() for ref in self.references]
        if self.deck_id:
            item["deck_id"] = self.deck_id
        if self.next_review_at:
            item["next_review_at"] = self.next_review_at.isoformat()
        if self.updated_at:
            item["updated_at"] = self.updated_at.isoformat()
        return item

    @classmethod
    def from_dynamodb_item(cls, item: dict) -> "Card":
        """Create Card from DynamoDB item."""
        return cls(
            card_id=item["card_id"],
            user_id=item["user_id"],
            front=item["front"],
            back=item["back"],
            deck_id=item.get("deck_id"),
            tags=item.get("tags", []),
            references=[Reference(**ref) for ref in item.get("references", [])],
            next_review_at=datetime.fromisoformat(item["next_review_at"]) if item.get("next_review_at") else None,
            interval=int(item.get("interval", 0)),
            ease_factor=float(item.get("ease_factor", 2.5)),
            repetitions=int(item.get("repetitions", 0)),
            created_at=datetime.fromisoformat(item["created_at"]),
            updated_at=datetime.fromisoformat(item["updated_at"]) if item.get("updated_at") else None,
        )

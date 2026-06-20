"""Card models for Memoru LIFF application."""

import uuid
from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class Reference(BaseModel):
    """参考情報モデル。"""

    type: Literal["url", "book", "note"]
    value: str = Field(..., min_length=1, max_length=500)


# タグ・参考情報の制約値（Create / Update リクエストで共有）。
MAX_TAGS = 10
MAX_TAG_LENGTH = 50
MAX_REFERENCES = 5


def normalize_tags(v: List[str]) -> List[str]:
    """タグを検証・正規化する（最大件数チェック + 前後空白除去 + 長さ切り詰め）。"""
    if len(v) > MAX_TAGS:
        raise ValueError(f"Maximum {MAX_TAGS} tags allowed")
    return [tag.strip()[:MAX_TAG_LENGTH] for tag in v if tag.strip()]


def validate_references_limit(v: List[Reference]) -> List[Reference]:
    """参考情報の最大件数を検証する。"""
    if len(v) > MAX_REFERENCES:
        raise ValueError(f"Maximum {MAX_REFERENCES} references allowed")
    return v


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
        return normalize_tags(v)

    @field_validator("references")
    @classmethod
    def validate_references(cls, v: List[Reference]) -> List[Reference]:
        """Validate references."""
        return validate_references_limit(v)


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
        return normalize_tags(v)

    @field_validator("references")
    @classmethod
    def validate_references(cls, v: Optional[List[Reference]]) -> Optional[List[Reference]]:
        """Validate references."""
        if v is None:
            return v
        return validate_references_limit(v)


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
        """Convert to DynamoDB item.

        【deck_index_key（GSI 用複合キー）】: deck-cards-index GSI の HASH キーとして
        "<user_id>#<deck_id>" を派生属性に持たせ、ユーザー境界をキーに含める。
        異なるユーザーが同一 deck_id を持ち得ても集計が混ざらないようにするため
        (PR #47 [P2])。deck_id が無いカードは属性を書かないことでスパースインデックス
        を維持する（未分類カードは GSI に投影されない）。

        【マイグレーション注意】: 既存カードには deck_index_key 属性が無いため、
        当該カードは GSI に投影されない。再保存（create/update）時に属性が投影される。
        本番は現状デプロイ環境・既存データが無い前提のため移行スクリプトは不要。
        """
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
            # 【reference_url_key（GSI 用複合キー）】: reference-url-index GSI の HASH キーとして
            # 生成元 URL（先頭の type=="url" reference）を1件採用し "<user_id>#<url>" を持たせる。
            # URL からのカード生成時の重複検出（ai_handler.generate_from_url）を全件 scan から
            # Query へ置き換えるための派生属性（M-13）。url reference を持たないカードには
            # 属性を書かずスパースインデックスを維持する。
            source_url = next((ref.value for ref in self.references if ref.type == "url"), None)
            if source_url:
                item["reference_url_key"] = self.reference_url_key(self.user_id, source_url)
        if self.deck_id:
            item["deck_id"] = self.deck_id
            # GSI 用複合キー（永続化専用。CardResponse には出さない）。
            item["deck_index_key"] = self.deck_index_key(self.user_id, self.deck_id)
        if self.next_review_at:
            item["next_review_at"] = self.next_review_at.isoformat()
        if self.updated_at:
            item["updated_at"] = self.updated_at.isoformat()
        return item

    @staticmethod
    def deck_index_key(user_id: str, deck_id: str) -> str:
        """Build the deck-cards-index GSI HASH key from user_id and deck_id.

        ユーザー境界を含めた複合キー "<user_id>#<deck_id>" を生成する (PR #47 [P2])。
        """
        return f"{user_id}#{deck_id}"

    @staticmethod
    def reference_url_key(user_id: str, url: str) -> str:
        """Build the reference-url-index GSI HASH key from user_id and url.

        M-13: ユーザー境界を含めた複合キー "<user_id>#<url>" を生成する。
        deck_index_key と同方針で、異なるユーザーが同一 URL からカードを生成しても
        重複検出が混ざらないようにユーザー境界をキーに含める。url は保存済み reference の
        生値をそのまま用い、find_cards_by_reference_url の引数 url と同じ複合化で
        完全一致検索する（既存の references[].value == url 完全一致の意味論を維持）。
        """
        return f"{user_id}#{url}"

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

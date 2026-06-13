"""Card service: card 関連のビジネスロジック層。

DynamoDB アクセスは CardRepository に委譲し、本クラスは deck 検証・SRS 計算・
update 式の組み立てといったオーケストレーションに専念する。

例外クラス (CardServiceError 等) は card_repository に定義し、後方互換のため本モジュールから
再エクスポートする（``from services.card_service import CardNotFoundError`` を維持）。
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from models.card import Card, Reference
from utils.sentinel import UNSET as _UNSET
from .card_repository import (
    CardLimitExceededError,
    CardNotFoundError,
    CardRepository,
    CardServiceError,
    InternalError,
)
from .srs import calculate_next_review_boundary

# 後方互換のための再エクスポート (ruff の未使用 import 検出を回避)
__all__ = [
    "CardService",
    "CardServiceError",
    "CardNotFoundError",
    "CardLimitExceededError",
    "InternalError",
]


class CardService:
    """Service for card-related business logic."""

    MAX_CARDS_PER_USER = 2000

    def __init__(
        self,
        table_name: Optional[str] = None,
        dynamodb_resource=None,
        users_table_name: Optional[str] = None,
        reviews_table_name: Optional[str] = None,
        deck_service=None,
    ):
        """Initialize CardService.

        Args:
            table_name: DynamoDB table name. Defaults to CARDS_TABLE env var.
            dynamodb_resource: Optional boto3 DynamoDB resource for testing.
            users_table_name: DynamoDB users table name. Defaults to USERS_TABLE env var.
            reviews_table_name: DynamoDB reviews table name. Defaults to REVIEWS_TABLE env var.
            deck_service: Optional DeckService injected for deck_id validation (C-7).
        """
        self._repo = CardRepository(
            table_name=table_name,
            dynamodb_resource=dynamodb_resource,
            users_table_name=users_table_name,
            reviews_table_name=reviews_table_name,
        )
        self.table_name = self._repo.table_name

        # 【C-7: deck_id 存在・所有検証用】DeckService をオプション注入する。
        # 未注入時は使用時に遅延生成してキャッシュする（同一 dynamodb_resource を共有）。
        self._deck_service = deck_service
        self._dynamodb_resource_arg = dynamodb_resource

    def _get_deck_service(self):
        """Lazily construct (and cache) a DeckService for deck validation (C-7)."""
        if self._deck_service is None:
            from .deck_service import DeckService

            self._deck_service = DeckService(
                cards_table_name=self.table_name,
                dynamodb_resource=self._dynamodb_resource_arg,
            )
        return self._deck_service

    def create_card(
        self,
        user_id: str,
        front: str,
        back: str,
        deck_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        references: Optional[List[Reference]] = None,
    ) -> Card:
        """Create a new card.

        Args:
            user_id: The user's ID.
            front: Front side text.
            back: Back side text.
            deck_id: Optional deck ID.
            tags: Optional list of tags.
            references: Optional list of references.

        Returns:
            Created Card object.

        Raises:
            CardLimitExceededError: If user exceeds card limit.
            DeckNotFoundError: If deck_id is given but does not exist / is not owned.
        """
        # 【C-7: deck_id 存在・所有検証】指定された deck_id が実在し当該ユーザーの
        # 所有であることを確認する。dangling reference（集計/Tutor 対象から漏れる
        # カード）を防ぐ。DeckNotFoundError はそのまま呼び出し元へ伝播させる。
        if deck_id is not None:
            self._get_deck_service().get_deck(user_id, deck_id)

        now = datetime.now(timezone.utc)
        card = Card(
            user_id=user_id,
            front=front,
            back=back,
            deck_id=deck_id,
            tags=tags or [],
            references=references or [],
            next_review_at=now,  # Due immediately for new cards
            created_at=now,
        )

        # Use TransactWriteItems to atomically increment card_count (with limit
        # check) and create the card. 永続化とエラー変換は repository に委譲する。
        self._repo.create_card_atomic(card.to_dynamodb_item(), user_id, self.MAX_CARDS_PER_USER)
        return card

    def get_card(self, user_id: str, card_id: str) -> Card:
        """Get a card by ID.

        Args:
            user_id: The user's ID.
            card_id: The card's ID.

        Returns:
            Card object.

        Raises:
            CardNotFoundError: If card does not exist.
        """
        item = self._repo.get_item(user_id, card_id)
        if item is None:
            raise CardNotFoundError(f"Card not found: {card_id}")
        return Card.from_dynamodb_item(item)

    def update_card(
        self,
        user_id: str,
        card_id: str,
        front: Optional[str] = None,
        back: Optional[str] = None,
        deck_id=_UNSET,
        tags: Optional[List[str]] = None,
        references: Optional[List[Reference]] = None,
        interval: Optional[int] = None,
        user_timezone: Optional[str] = None,
        day_start_hour: Optional[int] = None,
    ) -> Card:
        """Update a card.

        Args:
            user_id: The user's ID.
            card_id: The card's ID.
            front: Optional new front text.
            back: Optional new back text.
            deck_id: Optional new deck ID.
            tags: Optional new tags.
            references: Optional new references.
            interval: Optional new review interval in days (1-365).
                      When specified, next_review_at is recalculated as now + interval days.

        Returns:
            Updated Card object.

        Raises:
            CardNotFoundError: If card does not exist.

        【interval 指定時の動作】:
          - interval と next_review_at を同一 UpdateExpression でまとめて更新する
          - next_review_at = 現在日時 (UTC) + interval 日 で自動再計算する
          - ease_factor, repetitions は変更しない（REQ-004）
          - review_history には記録しない（復習操作ではないため。REQ-403）
        🔵 信頼性レベル: 要件定義 REQ-002〜004, REQ-401〜403, architecture.md より
        """
        # Verify card exists
        card = self.get_card(user_id, card_id)

        # 【C-7: deck_id 存在・所有検証】実デッキへの変更時のみ検証する。
        # _UNSET（変更なし）と None（デッキ解除）は検証不要。
        if deck_id is not _UNSET and deck_id is not None:
            self._get_deck_service().get_deck(user_id, deck_id)

        # Build update expression
        update_parts = []
        remove_parts = []
        expression_values: Dict[str, Any] = {}
        expression_names = {}

        if front is not None:
            update_parts.append("#front = :front")
            expression_values[":front"] = front
            expression_names["#front"] = "front"
            card.front = front

        if back is not None:
            update_parts.append("#back = :back")
            expression_values[":back"] = back
            expression_names["#back"] = "back"
            card.back = back

        if deck_id is None:
            # Explicit null → REMOVE deck_id from DynamoDB
            # GSI 用の派生キー deck_index_key も併せて REMOVE し、
            # スパースインデックスから外す (PR #47 [P2])。
            remove_parts.append("deck_id")
            remove_parts.append("deck_index_key")
            card.deck_id = None
        elif deck_id is not _UNSET:
            # New value → SET deck_id
            # deck-cards-index GSI の HASH キー deck_index_key も "<user_id>#<deck_id>"
            # で更新する。ユーザー境界を含めることで他ユーザーのカードと混ざらない (PR #47 [P2])。
            update_parts.append("deck_id = :deck_id")
            expression_values[":deck_id"] = deck_id
            update_parts.append("deck_index_key = :deck_index_key")
            expression_values[":deck_index_key"] = Card.deck_index_key(user_id, deck_id)
            card.deck_id = deck_id
        # deck_id is _UNSET → no change

        if tags is not None:
            update_parts.append("tags = :tags")
            expression_values[":tags"] = tags
            card.tags = tags

        if references is not None:
            update_parts.append("#references = :references")
            expression_values[":references"] = [ref.model_dump() for ref in references]
            expression_names["#references"] = "references"
            card.references = references

        # 【interval 更新処理】: interval が指定された場合に interval と next_review_at を更新する
        # 【実装方針】: DynamoDB の予約語 interval を ExpressionAttributeNames でエスケープ
        # 【next_review_at 再計算】: 現在日時 + interval 日 で再計算する（REQ-003）
        # 【不変条件】: ease_factor, repetitions は更新しない（REQ-004）
        # 【review_history 非記録】: update_card は復習操作ではないため、review_history に記録しない（REQ-403）
        # 🔵 信頼性レベル: 要件定義 REQ-002〜004, REQ-402〜403, architecture.md 技術的制約セクションより
        if interval is not None:
            # 【予約語エスケープ】: DynamoDB で "interval" は予約語のため #interval としてエスケープする
            update_parts.append("#interval = :interval")
            expression_values[":interval"] = interval
            expression_names["#interval"] = "interval"
            card.interval = interval

            # 【next_review_at 再計算】: 日付境界時刻に正規化して計算する
            if user_timezone is not None and day_start_hour is not None:
                next_review_at = calculate_next_review_boundary(
                    interval=interval,
                    user_timezone=user_timezone,
                    day_start_hour=day_start_hour,
                )
            else:
                next_review_at = datetime.now(timezone.utc) + timedelta(days=interval)
            update_parts.append("next_review_at = :next_review_at")
            expression_values[":next_review_at"] = next_review_at.isoformat()
            card.next_review_at = next_review_at

        if not update_parts and not remove_parts:
            return card

        now = datetime.now(timezone.utc)
        update_parts.append("updated_at = :updated_at")
        expression_values[":updated_at"] = now.isoformat()
        card.updated_at = now

        # Build combined SET + REMOVE expression
        update_expression = ""
        if update_parts:
            update_expression += "SET " + ", ".join(update_parts)
        if remove_parts:
            update_expression += " REMOVE " + ", ".join(remove_parts)

        self._repo.update_item(
            user_id,
            card_id,
            update_expression,
            expression_values=expression_values,
            expression_names=expression_names,
        )
        return card

    def delete_card(self, user_id: str, card_id: str) -> None:
        """Delete a card atomically with card_count decrement.

        事前に get_card() でカードの存在を確認し、関連 Reviews を削除（ベストエフォート）後、
        TransactWriteItems で Cards 削除と card_count デクリメントをアトミックに実行する。

        Args:
            user_id: The user's ID.
            card_id: The card's ID.

        Raises:
            CardNotFoundError: カードが存在しない場合、またはトランザクション中の並行削除 (EARS-012)。
            CardServiceError: card_count が既に 0 (EARS-013)、その他の DynamoDB エラー時。
        """
        # 【カード存在確認】: 削除前にカードが存在することを確認する
        self.get_card(user_id, card_id)

        # 【C-5: レビュー削除はトランザクション外】ベストエフォートで先に削除する。
        self._repo.delete_reviews_for_card(card_id, user_id)

        # 【トランザクション実行】: Cards 削除 + card_count デクリメントをアトミックに実行
        self._repo.delete_card_atomic(user_id, card_id)

    def list_cards(
        self,
        user_id: str,
        limit: int = 50,
        cursor: Optional[str] = None,
        deck_id: Optional[str] = None,
    ) -> Tuple[List[Card], Optional[str]]:
        """List cards for a user.

        Args:
            user_id: The user's ID.
            limit: Maximum number of cards to return.
            cursor: Pagination cursor (card_id to start after).
            deck_id: Optional filter by deck ID.

        Returns:
            Tuple of (list of cards, next cursor).
        """
        items, next_cursor = self._repo.query_cards_page(user_id, limit, cursor, deck_id)
        return [Card.from_dynamodb_item(item) for item in items], next_cursor

    def find_cards_by_reference_url(self, user_id: str, url: str) -> List[Card]:
        """指定 URL を references に含むカードを全件検索する。

        C-5: list_cards の最初の50件のみで重複 URL を検出していた問題を解消するため、
        ページネーション対応で全カードを走査し references[].value を完全一致で判定する。

        references は List<Map>（{type, value}）構造のため DynamoDB の
        ``contains`` フィルタでは文字列一致できない。そのため全件を取得し、
        アプリケーション層で references[].value の完全一致を判定する。

        Args:
            user_id: ユーザー ID。
            url: 検索する参照 URL。

        Returns:
            指定 URL を references フィールドに含むカードのリスト。
        """
        matched_cards: List[Card] = []
        for item in self._repo.scan_all_cards(user_id):
            card = Card.from_dynamodb_item(item)
            refs = card.references or []
            for ref in refs:
                ref_val = ref.get("value", "") if isinstance(ref, dict) else getattr(ref, "value", "")
                if ref_val == url:
                    matched_cards.append(card)
                    break
        return matched_cards

    def get_card_count(self, user_id: str) -> int:
        """Get the number of cards for a user.

        Args:
            user_id: The user's ID.

        Returns:
            Number of cards.
        """
        return self._repo.count_cards(user_id)

    def get_due_cards(
        self,
        user_id: str,
        limit: Optional[int] = None,
        before: Optional[datetime] = None,
        include_future: bool = False,
    ) -> List[Card]:
        """Get cards due for review.

        【設計方針】: limit=None の場合は DynamoDB に Limit を渡さず全件取得する。
        呼び出し元（review_service）が deck_id フィルタ後に limit を適用するため、
        このメソッドは limit なしで全件返すことで正確な total_due_count を計算できる。 🔵

        Args:
            user_id: The user's ID.
            limit: Maximum number of cards to return.
                   None を指定した場合は全件取得する（デフォルト）。
                   deck_id フィルタを上位層で行う場合は None を渡すこと。
            before: Get cards due before this time (defaults to now).
            include_future: Return every scheduled card regardless of due date.
                            Cards without next_review_at are not part of the due-date GSI.

        Returns:
            List of cards due for review, oldest due first.
        """
        items = self._repo.query_due_cards(user_id, limit, before, include_future)
        return [Card.from_dynamodb_item(item) for item in items]

    def get_due_card_count(
        self,
        user_id: str,
        before: Optional[datetime] = None,
    ) -> int:
        """Get count of cards due for review.

        【用途】: 通知サービス（notification_service）でユーザーの復習対象カード数を確認する際に使用する。
        DynamoDB の SELECT COUNT を使用するため、全カードを取得するよりもコストが低い。
        deck_id フィルタは不要なシンプルな件数取得に適している。 🔵

        Args:
            user_id: The user's ID.
            before: Get cards due before this time (defaults to now).

        Returns:
            Number of cards due for review (deck_id フィルタなしの全件数).
        """
        return self._repo.count_due_cards(user_id, before)

    def update_review_data(
        self,
        user_id: str,
        card_id: str,
        next_review_at: datetime,
        interval: int,
        ease_factor: float,
        repetitions: int,
    ) -> Card:
        """Update card's review data after a review.

        Args:
            user_id: The user's ID.
            card_id: The card's ID.
            next_review_at: Next review date/time.
            interval: Days until next review.
            ease_factor: SM-2 ease factor.
            repetitions: Number of successful reviews.

        Returns:
            Updated Card object.
        """
        now = datetime.now(timezone.utc)
        self._repo.update_item(
            user_id,
            card_id,
            "SET next_review_at = :next_review, #interval = :interval, "
            "ease_factor = :ease_factor, repetitions = :repetitions, updated_at = :updated_at",
            expression_values={
                ":next_review": next_review_at.isoformat(),
                ":interval": interval,
                ":ease_factor": str(ease_factor),
                ":repetitions": repetitions,
                ":updated_at": now.isoformat(),
            },
            expression_names={"#interval": "interval"},
            error_message="Failed to update review data",
        )
        return self.get_card(user_id, card_id)

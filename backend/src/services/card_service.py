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
            # M-13: reference-url-index GSI の派生キー reference_url_key も references に
            # 同期する。to_dynamodb_item（作成時）と同じく先頭の type=="url" reference を
            # 生成元 URL として採用し、存在すれば SET、無ければ REMOVE してスパース
            # インデックスを維持する。これを欠くと URL 参照を後から追加・差し替え・クリア
            # した際に GSI が古いキーのまま残り、find_cards_by_reference_url の重複検出が
            # 取りこぼし・誤検知を起こす。
            source_url = next((ref.value for ref in references if ref.type == "url"), None)
            if source_url:
                update_parts.append("reference_url_key = :reference_url_key")
                expression_values[":reference_url_key"] = Card.reference_url_key(user_id, source_url)
            else:
                remove_parts.append("reference_url_key")

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
            # 【L-10: 既知の一貫性の懸念】:
            #   submit_review (review_service) は常に calculate_next_review_boundary
            #   を使い境界正規化するが、本メソッドは user_timezone/day_start_hour が
            #   両方与えられた時のみ正規化し、片方でも欠けると素朴な timedelta
            #   フォールバック（境界非正規化）になる。そのため呼び出し元が tz を
            #   渡し忘れると、カードによって due 判定の境界（day_start_hour）がズレる。
            #   理想は next_review_at 算出を srs モジュールの単一ヘルパーへ集約し、
            #   未指定時のデフォルト（Asia/Tokyo / 4 時）を
            #   calculate_next_review_boundary 内へ寄せて常に境界正規化を通すこと。
            #   ただし srs.py（担当外）の変更と、現行の timedelta フォールバックを
            #   前提とする interval テスト群への影響があるため据え置く。
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
        """指定 URL を生成元参照に持つカードを reference-url-index GSI で検索する。

        M-13: 旧実装は scan_all_cards でユーザーの全カードを取得し references[].value を
        Python 側で完全一致判定していたため、URL カード生成（ai_handler）のたびに
        コスト・レイテンシがユーザーの蓄積カード数に線形比例していた（最大 2000 件読み取り）。
        本実装は Card.to_dynamodb_item が付与する派生属性 reference_url_key
        （= "<user_id>#<url>"、生成元 = 先頭の type=="url" reference）を HASH キーとする
        reference-url-index GSI を Query し、コストを O(一致件数) にする。

        設計判断: references は最大 5 件だが、GSI に投影するのは生成元 URL（先頭の url
        reference）1 件のみ。URL からのカード生成では生成元 URL が単一の url reference として
        記録されるため、重複検出の用途を満たす。生成元以外の URL を非先頭 reference に持つ
        カードは対象外（許容済みの設計トレードオフ）。

        Args:
            user_id: ユーザー ID。
            url: 検索する生成元 URL。

        Returns:
            指定 URL を生成元参照に持つカードのリスト。
        """
        items = self._repo.query_cards_by_reference_url(user_id, url)
        return [Card.from_dynamodb_item(item) for item in items]

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
        include_future: bool = False,
    ) -> int:
        """Get count of cards due for review.

        【用途】: 通知サービス（notification_service）でユーザーの復習対象カード数を確認する際に使用する。
        review_service.get_due_cards も M-12 で total_due_count をこの COUNT 経由で求める。
        DynamoDB の SELECT COUNT を使用するため、全カードを取得するよりもコストが低い。
        deck_id フィルタは不要なシンプルな件数取得に適している。 🔵

        Args:
            user_id: The user's ID.
            before: Get cards due before this time (defaults to now).
            include_future: True なら将来分も含む全カードを集計する（total_due_count 用）。

        Returns:
            Number of cards due for review (deck_id フィルタなしの全件数).
        """
        return self._repo.count_due_cards(user_id, before, include_future)

    def get_deck_due_card_count(
        self,
        user_id: str,
        deck_id: str,
        before: Optional[datetime] = None,
        include_future: bool = False,
    ) -> int:
        """指定デッキの復習対象カード数を返す（M-12: total_due_count 用、本体非転送）。"""
        return self._repo.count_deck_due_cards(user_id, deck_id, before, include_future)

    def get_deck_due_cards(
        self,
        user_id: str,
        deck_id: str,
        limit: int,
        before: Optional[datetime] = None,
        include_future: bool = False,
    ) -> List[Card]:
        """指定デッキの復習対象カードを期限が古い順に最大 limit 件取得する（M-12）。

        deck_id フィルタを DynamoDB 側で適用し、全件メモリ展開を避けて limit 件のみを
        Card へ変換して返す。
        """
        items = self._repo.query_deck_due_cards(user_id, deck_id, limit, before, include_future)
        return [Card.from_dynamodb_item(item) for item in items]

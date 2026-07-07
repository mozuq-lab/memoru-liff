"""Review service for managing card reviews."""

import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from models.review import (
    DueCardInfo,
    DueCardsResponse,
    ReviewPreviousState,
    ReviewResponse,
    ReviewUpdatedState,
    UndoRestoredState,
    UndoReviewResponse,
)
from utils.dynamodb_client import get_dynamodb_resource
from .ai_service import ReviewSummary
from .card_repository import CardRepository, CardServiceError, OptimisticLockError
from .card_service import CardService
from .review_repository import ReviewRepository
from .srs import (
    ReviewHistoryEntry,
    SM2Result,
    add_review_history,
    calculate_next_review_boundary,
    calculate_sm2,
    to_user_local_date,
)
from .stats_service import (
    calculate_streak,
    calculate_tag_performance,
    unique_local_review_dates_desc,
)

logger = Logger()


def build_srs_optimistic_lock_condition(
    ease_placeholder: str,
    interval_placeholder: str,
    reps_placeholder: str,
    history_len_placeholder: Optional[str] = None,
) -> str:
    """SRS 状態の楽観ロック用 ConditionExpression を生成する。

    submit_review (C-1) と undo_review (B-2) で重複していた条件式を集約する。
    attribute_not_exists(...) はレガシーアイテム（属性欠落 / #37 follow-up）を許容するためのもの。
    `#interval` は予約語回避のため呼び出し側で ExpressionAttributeNames を渡す前提。

    Args:
        ease_placeholder: ease_factor 比較値のプレースホルダ（例: ":prev_ease"）。
        interval_placeholder: interval 比較値のプレースホルダ。
        reps_placeholder: repetitions 比較値のプレースホルダ。
        history_len_placeholder: 指定時は ``size(review_history) = ...`` 条件を追加する。

    Returns:
        ConditionExpression 文字列。
    """
    parts = [
        f"(attribute_not_exists(ease_factor) OR ease_factor = {ease_placeholder})",
        f"(attribute_not_exists(#interval) OR #interval = {interval_placeholder})",
        f"(attribute_not_exists(repetitions) OR repetitions = {reps_placeholder})",
    ]
    if history_len_placeholder is not None:
        parts.append(f"size(review_history) = {history_len_placeholder}")
    return " AND ".join(parts)


class ReviewServiceError(Exception):
    """Base exception for review service errors."""

    pass


class InvalidGradeError(ReviewServiceError):
    """Raised when grade is invalid."""

    pass


class NoReviewHistoryError(ReviewServiceError):
    """Raised when there is no review history to undo."""

    pass


class ConcurrentReviewError(ReviewServiceError):
    """Raised when a concurrent review update is detected (optimistic lock failed)."""

    pass


class ReviewPersistenceError(ReviewServiceError):
    """Raised when persisting a review (card SRS update / undo) fails.

    L-9: レビュー永続化の DynamoDB 失敗を card 層の例外 (CardServiceError) ではなく
    ReviewService 系の例外で表現し、例外階層を層ごとに揃える。get_card 由来の
    CardNotFoundError は引き続きそのまま伝播させる（呼び出し元が 404 にマップする）。
    """

    pass


class ReviewService:
    """Service for managing card reviews and SRS calculations."""

    def __init__(
        self,
        cards_table_name: Optional[str] = None,
        reviews_table_name: Optional[str] = None,
        dynamodb_resource=None,
    ):
        """Initialize ReviewService.

        Args:
            cards_table_name: DynamoDB cards table name.
            reviews_table_name: DynamoDB reviews table name.
            dynamodb_resource: Optional boto3 DynamoDB resource for testing.
        """
        self.cards_table_name = cards_table_name or os.environ.get(
            "CARDS_TABLE", "memoru-cards-dev"
        )
        self.reviews_table_name = reviews_table_name or os.environ.get(
            "REVIEWS_TABLE", "memoru-reviews-dev"
        )

        self.dynamodb = get_dynamodb_resource(dynamodb_resource)

        # L-7: Cards / Reviews テーブルへの DynamoDB アクセスは Repository 層へ集約する。
        # ReviewService は SRS 計算と更新式の組み立てに専念し、self.cards_table /
        # self.reviews_table を直接叩かない構造にする。
        self._card_repo = CardRepository(
            table_name=self.cards_table_name,
            dynamodb_resource=dynamodb_resource,
            reviews_table_name=self.reviews_table_name,
        )
        self._review_repo = ReviewRepository(
            table_name=self.reviews_table_name,
            dynamodb_resource=dynamodb_resource,
        )
        # 後方互換エイリアス: 既存テストが review_service.cards_table /
        # reviews_table を読み取り・patch するため、Repository が実際に使用する
        # boto3 Table と同一オブジェクトを公開し続ける（patch がそのまま効く）。
        self.cards_table = self._card_repo.table
        self.reviews_table = self._review_repo.table
        self.card_service = CardService(
            table_name=self.cards_table_name,
            dynamodb_resource=dynamodb_resource,
        )

    def submit_review(
        self,
        user_id: str,
        card_id: str,
        grade: int,
        user_timezone: str = "Asia/Tokyo",
        day_start_hour: int = 4,
    ) -> ReviewResponse:
        """Submit a review for a card and update SRS parameters.

        Args:
            user_id: The user's ID.
            card_id: The card's ID.
            grade: Review grade (0-5).
            user_timezone: User's IANA timezone string for day boundary normalization.
            day_start_hour: Hour when user's "day" starts (0-23).

        Returns:
            ReviewResponse with previous and updated states.

        Raises:
            CardNotFoundError: If card does not exist or belongs to another user.
            InvalidGradeError: If grade is not in range 0-5.
        """
        if not 0 <= grade <= 5:
            raise InvalidGradeError(f"Grade must be between 0 and 5, got {grade}")

        # Get the card (also verifies ownership)
        card = self.card_service.get_card(user_id, card_id)

        # Store previous state
        # due_date はユーザーローカル日付で返す（UTC のまま date() を取ると
        # day_start_hour 正規化により 1 日早い日付になる）。
        previous = ReviewPreviousState(
            ease_factor=card.ease_factor,
            interval=card.interval,
            repetitions=card.repetitions,
            due_date=to_user_local_date(card.next_review_at, user_timezone),
        )

        # Calculate new SRS parameters
        result = calculate_sm2(
            grade=grade,
            repetitions=card.repetitions,
            ease_factor=card.ease_factor,
            interval=card.interval,
        )

        # Normalize next_review_at to user's day boundary
        normalized_next_review_at = calculate_next_review_boundary(
            interval=result.interval,
            user_timezone=user_timezone,
            day_start_hour=day_start_hour,
        )
        result = SM2Result(
            repetitions=result.repetitions,
            ease_factor=result.ease_factor,
            interval=result.interval,
            next_review_at=normalized_next_review_at,
        )

        # Update card with new parameters
        now = datetime.now(timezone.utc)
        self._update_card_review_data(
            user_id=user_id,
            card_id=card_id,
            result=result,
            grade=grade,
            previous_ease_factor=card.ease_factor,
            previous_interval=card.interval,
            previous_repetitions=card.repetitions,
            previous_next_review_at=card.next_review_at.isoformat() if card.next_review_at else None,
        )

        # Record review in reviews table.
        # M-9: _update_card_review_data（カードの SRS 更新＋楽観ロック＋
        # review_history 追記）と本 _record_review（reviews 分析テーブルへの記録）は
        # 別々の DynamoDB 操作でありアトミックではない。これは意図的な設計:
        #   - カードの SRS 状態と review_history がレビューの「正」(source of truth)。
        #     undo_review もカード内 review_history を参照するため、reviews テーブルの
        #     欠落はアンドゥや SRS スケジューリングに一切影響しない。
        #   - reviews テーブルは集計/分析用（ストリーク・タグ別正答率等）であり
        #     ベストエフォート。_record_review は失敗してもログのみで送出しない。
        # よって _update_card_review_data 成功後に _record_review が失敗しても、
        # ユーザー体験上の不整合は生じない（分析値が 1 件欠ける程度）。
        # 将来 reviews テーブルの信頼性を要件化する場合は TransactWriteItems
        # （複数テーブル対応）か DynamoDB Streams での補完を検討すること。
        self._record_review(
            user_id=user_id,
            card_id=card_id,
            grade=grade,
            reviewed_at=now,
            ease_factor_before=card.ease_factor,
            ease_factor_after=result.ease_factor,
            interval_before=card.interval,
            interval_after=result.interval,
        )

        updated = ReviewUpdatedState(
            ease_factor=result.ease_factor,
            interval=result.interval,
            repetitions=result.repetitions,
            due_date=to_user_local_date(result.next_review_at, user_timezone),
        )

        return ReviewResponse(
            card_id=card_id,
            grade=grade,
            previous=previous,
            updated=updated,
            reviewed_at=now,
        )

    def undo_review(
        self,
        user_id: str,
        card_id: str,
        user_timezone: str = "Asia/Tokyo",
    ) -> UndoReviewResponse:
        """Undo the latest review for a card and restore SRS parameters.

        **Design note – why read-then-write instead of ``list_append``:**
        Undo removes the *last* entry from ``review_history`` (truncation).
        DynamoDB's ``REMOVE review_history[-1]`` syntax is not available for
        list manipulation, and ``list_append`` only supports appending.
        Therefore, the full list must be read, truncated in-memory, and
        written back.  ``_update_card_review_data`` *can* use ``list_append``
        for appends, but undo cannot.

        Args:
            user_id: The user's ID.
            card_id: The card's ID.
            user_timezone: User's IANA timezone string (restored due_date の表示用)。

        Returns:
            UndoReviewResponse with restored state.

        Raises:
            CardNotFoundError: If card does not exist or belongs to another user.
            NoReviewHistoryError: If card has no review history to undo.
        """
        # Get the card (also verifies ownership)
        card = self.card_service.get_card(user_id, card_id)

        # Get existing review history (L-7: Repository 経由で取得)
        review_history = self._card_repo.get_review_history(user_id, card_id)

        if not review_history:
            raise NoReviewHistoryError("No review history to undo")

        # Snapshot the current SRS state we are about to roll back. These values
        # form the optimistic-lock baseline (B-2): the conditional UpdateItem below
        # only applies if the card still matches this read, mirroring the CAS used
        # by submit_review (C-1). Prevents lost updates / history corruption when an
        # undo races with a concurrent submit/undo (double-click, webhook redelivery).
        expected_ease_factor = card.ease_factor
        expected_interval = card.interval
        expected_repetitions = card.repetitions
        expected_history_len = len(review_history)

        # Get latest entry
        latest_entry = review_history[-1]

        # Extract before values for restoration
        restored_ease_factor = float(latest_entry.get("ease_factor_before", card.ease_factor))
        restored_interval = int(latest_entry.get("interval_before", card.interval))
        restored_repetitions = latest_entry.get("repetitions_before")
        if restored_repetitions is not None:
            restored_repetitions = int(restored_repetitions)
        else:
            restored_repetitions = card.repetitions
        restored_next_review_at = latest_entry.get("next_review_at_before")
        if restored_next_review_at is None:
            restored_next_review_at = card.next_review_at.isoformat() if card.next_review_at else datetime.now(timezone.utc).isoformat()

        # Remove latest entry from history
        updated_history = review_history[:-1]

        # Update card with restored parameters (L-7: Repository 経由で楽観ロック更新)
        now = datetime.now(timezone.utc)
        try:
            self._card_repo.apply_review_update(
                user_id=user_id,
                card_id=card_id,
                update_expression=(
                    "SET next_review_at = :next_review, "
                    "#interval = :interval, "
                    "ease_factor = :ease_factor, "
                    "repetitions = :repetitions, "
                    "updated_at = :updated_at, "
                    "review_history = :review_history"
                ),
                # Optimistic lock (B-2): apply only if the card's SRS state and
                # review_history length still match what we read above. Mirrors the
                # CAS in submit_review (C-1) to prevent lost updates / history
                # corruption when an undo races with a concurrent submit/undo
                # (double-click, webhook redelivery). The history-length guard also
                # rejects the case where SRS fields happen to coincide but the list
                # has already been mutated by a concurrent operation.
                # attribute_not_exists(...) tolerates legacy items missing these
                # attributes (#37 follow-up), matching submit_review's behavior.
                condition_expression=build_srs_optimistic_lock_condition(
                    ":expected_ease",
                    ":expected_interval",
                    ":expected_reps",
                    ":expected_history_len",
                ),
                expression_names={"#interval": "interval"},
                expression_values={
                    ":next_review": restored_next_review_at,
                    ":interval": restored_interval,
                    ":ease_factor": str(restored_ease_factor),
                    ":repetitions": restored_repetitions,
                    ":updated_at": now.isoformat(),
                    ":review_history": updated_history,
                    ":expected_ease": str(expected_ease_factor),
                    ":expected_interval": expected_interval,
                    ":expected_reps": expected_repetitions,
                    ":expected_history_len": expected_history_len,
                },
            )
        except OptimisticLockError as e:
            logger.warning(
                "Concurrent undo update detected (optimistic lock failed)",
                extra={"user_id": user_id, "card_id": card_id},
            )
            raise ConcurrentReviewError(
                "Undo conflict: the card was modified concurrently. Please retry."
            ) from e
        except CardServiceError as e:
            raise ReviewPersistenceError(f"Failed to undo review: {e}") from e

        # Parse due_date from restored_next_review_at (ユーザーローカル日付に変換。
        # パース不能な場合は従来どおり元の文字列をそのまま返す)
        due_date = to_user_local_date(restored_next_review_at, user_timezone)
        if due_date is None:
            due_date = restored_next_review_at

        restored = UndoRestoredState(
            ease_factor=restored_ease_factor,
            interval=restored_interval,
            repetitions=restored_repetitions,
            due_date=due_date,
        )

        return UndoReviewResponse(
            card_id=card_id,
            restored=restored,
            undone_at=now,
        )

    def _update_card_review_data(
        self,
        user_id: str,
        card_id: str,
        result: SM2Result,
        grade: int,
        previous_ease_factor: float,
        previous_interval: int,
        previous_repetitions: Optional[int] = None,
        previous_next_review_at: Optional[str] = None,
    ) -> None:
        """Update card's SRS data and append a review history entry atomically.

        Uses DynamoDB ``list_append`` with ``if_not_exists`` to append the new
        history entry in a single UpdateItem call, eliminating the previous
        read-then-write pattern that was susceptible to race conditions.

        Args:
            user_id: The user's ID.
            card_id: The card's ID.
            result: SM2 calculation result.
            grade: Review grade.
            previous_ease_factor: Ease factor before review.
            previous_interval: Interval before review.
            previous_repetitions: Repetitions before review (for undo support).
            previous_next_review_at: Next review at before review (for undo support).
        """
        now = datetime.now(timezone.utc)

        # Build new history entry
        history_entry = ReviewHistoryEntry(
            reviewed_at=now,
            grade=grade,
            ease_factor_before=previous_ease_factor,
            ease_factor_after=result.ease_factor,
            interval_before=previous_interval,
            interval_after=result.interval,
            repetitions_before=previous_repetitions,
            repetitions_after=result.repetitions,
            next_review_at_before=previous_next_review_at,
            next_review_at_after=result.next_review_at.isoformat(),
        )
        # Convert to DynamoDB-compatible dict (same format as add_review_history)
        entry_dict = add_review_history([], history_entry)[0]

        try:
            # L-7: Repository 経由で楽観ロック付き SRS 更新を実行する。
            self._card_repo.apply_review_update(
                user_id=user_id,
                card_id=card_id,
                update_expression=(
                    "SET next_review_at = :next_review, "
                    "#interval = :interval, "
                    "ease_factor = :ease_factor, "
                    "repetitions = :repetitions, "
                    "updated_at = :updated_at, "
                    "review_history = list_append(if_not_exists(review_history, :empty_list), :new_entry)"
                ),
                # Optimistic lock (C-1): apply only if the card's SRS state still
                # matches what we read before computing the new values. Prevents
                # lost updates from concurrent submit_review calls (double-click /
                # webhook redelivery) where review_history grows but repetitions /
                # ease_factor would otherwise be overwritten from a stale base.
                # Tolerate legacy items missing these attributes (#37 follow-up):
                # Card.from_dynamodb_item back-fills defaults on read, but a real
                # missing attribute in DynamoDB would fail a plain equality check
                # and raise a spurious ConcurrentReviewError on a legitimate first
                # review. attribute_not_exists(...) lets such items through; once
                # written, subsequent updates are guarded normally.
                condition_expression=build_srs_optimistic_lock_condition(
                    ":prev_ease",
                    ":prev_interval",
                    ":prev_reps",
                ),
                expression_names={"#interval": "interval"},
                expression_values={
                    ":next_review": result.next_review_at.isoformat(),
                    ":interval": result.interval,
                    ":ease_factor": str(result.ease_factor),
                    ":repetitions": result.repetitions,
                    ":updated_at": now.isoformat(),
                    ":empty_list": [],
                    ":new_entry": [entry_dict],
                    ":prev_ease": str(previous_ease_factor),
                    ":prev_interval": previous_interval,
                    ":prev_reps": previous_repetitions,
                },
            )
        except OptimisticLockError as e:
            logger.warning(
                "Concurrent review update detected (optimistic lock failed)",
                extra={"user_id": user_id, "card_id": card_id},
            )
            raise ConcurrentReviewError(
                "Review update conflict: the card was modified concurrently. Please retry."
            ) from e
        except CardServiceError as e:
            raise ReviewPersistenceError(f"Failed to update card review data: {e}") from e

    def _record_review(
        self,
        user_id: str,
        card_id: str,
        grade: int,
        reviewed_at: datetime,
        ease_factor_before: float,
        ease_factor_after: float,
        interval_before: int,
        interval_after: int,
    ) -> None:
        """Record review in reviews table.

        【L-8: 役割境界 — reviews テーブルは分析専用、undo の正は card.review_history】:
        本メソッドが reviews テーブルへ保存するのは ease_factor / interval の
        before/after のみで、repetitions_before / next_review_at_before は保存しない。
        一方 _update_card_review_data はカード内 review_history にこれらも記録する。
        これは意図的な役割分担:
          - undo / SRS スケジューリングの「正」(source of truth) は
            card.review_history（undo_review はこちらを参照する）。
          - reviews テーブルはストリーク・タグ別正答率などの集計/分析専用であり、
            undo 相当や repetitions ベースの厳密な復元には用いない。
        したがって両者で保持カラムの粒度が異なるのは設計どおり。将来 reviews 側を
        信頼源（undo や repetitions 分析）に使いたくなった場合は、ここで
        repetitions_before/after・next_review_at_before/after を追加して
        review_history と粒度を揃えること。

        Args:
            user_id: The user's ID.
            card_id: The card's ID.
            grade: Review grade.
            reviewed_at: Review timestamp.
            ease_factor_before: Ease factor before review.
            ease_factor_after: Ease factor after review.
            interval_before: Interval before review.
            interval_after: Interval after review.
        """
        # L-7: reviews テーブルへの put_item は ReviewRepository に集約（ベストエフォート）。
        self._review_repo.record(
            {
                "user_id": user_id,
                "reviewed_at": reviewed_at.isoformat(),
                "card_id": card_id,
                "grade": grade,
                "ease_factor_before": str(ease_factor_before),
                "ease_factor_after": str(ease_factor_after),
                "interval_before": interval_before,
                "interval_after": interval_after,
            }
        )

    def get_due_cards(
        self,
        user_id: str,
        limit: int = 20,
        include_future: bool = False,
        deck_id: Optional[str] = None,
        user_timezone: str = "Asia/Tokyo",
    ) -> DueCardsResponse:
        """Get cards due for review.

        【設計方針 (M-12)】: total_due_count は Select=COUNT で求め、本体は limit 件のみ
        Query する形に分離し、全 due カードのメモリ展開を避ける。
        🔵 REQ-005: total_due_count は limit パラメータに影響されない正確な総数を返す

        - deck_id なし: user_id-due-index を Limit 付き Query で本体取得（O(limit)）、
          total_due_count は同 GSI の Select=COUNT で別取得（本体非転送）。
        - deck_id あり: user_id-due-index に FilterExpression(deck_id) を付け、本体は
          フィルタ後 limit 件に達するまでページング取得、total_due_count は
          Select=COUNT + FilterExpression で正確に集計（本体非転送）。
          deck-cards-index は KEYS_ONLY のため本体取得には使えず、本体は Projection=ALL の
          user_id-due-index を用いる。

        いずれの経路も total_due_count は limit に影響されないフィルタ後の正確な総数で、
        旧実装（card_service.get_due_cards(limit=None) で全件読み）のメモリ展開を解消する。

        Args:
            user_id: The user's ID.
            limit: Maximum number of cards to return in due_cards.
                   total_due_count はこの値に影響されず、フィルタ後の全件数を返す。
            include_future: Include scheduled cards with future due dates.
                            When true, total_due_count includes those future cards.
            deck_id: Optional filter by deck ID.
                     指定した場合、total_due_count はそのデッキ内の復習対象カード総数を返す。
            user_timezone: User's IANA timezone string（due_date / next_due_date の表示用）。

        Returns:
            DueCardsResponse with due cards and metadata.
            - due_cards: limit で制限されたカードリスト
            - total_due_count: deck_id フィルタ後・limit 適用前の全件数（REQ-005）
            - next_due_date: due_cards が空の場合に次の復習予定日を返す
        """
        now = datetime.now(timezone.utc)

        # 【総数と本体を分離取得】: total_due_count は COUNT（本体非転送）、本体は limit 件のみ。
        if deck_id is not None:
            total_due_count = self.card_service.get_deck_due_card_count(
                user_id=user_id,
                deck_id=deck_id,
                before=now,
                include_future=include_future,
            )
            limited_cards = self.card_service.get_deck_due_cards(
                user_id=user_id,
                deck_id=deck_id,
                limit=limit,
                before=now,
                include_future=include_future,
            )
        else:
            total_due_count = self.card_service.get_due_card_count(
                user_id=user_id,
                before=now,
                include_future=include_future,
            )
            limited_cards = self.card_service.get_due_cards(
                user_id=user_id,
                limit=limit,
                before=now,
                include_future=include_future,
            )

        # 【レスポンス形式変換】: Card モデルから DueCardInfo に変換する
        due_card_infos: List[DueCardInfo] = []
        for card in limited_cards:
            # 【超過日数計算】: next_review_at から現在までの経過日数（0以上）を計算する
            overdue_days = 0
            if card.next_review_at:
                delta = now - card.next_review_at
                overdue_days = max(0, delta.days)

            due_card_infos.append(
                DueCardInfo(
                    card_id=card.card_id,
                    front=card.front,
                    back=card.back,
                    deck_id=card.deck_id,
                    due_date=to_user_local_date(card.next_review_at, user_timezone),
                    overdue_days=overdue_days,
                    references=card.references,
                )
            )

        # 【次回復習日取得】: 復習対象カードがない場合に次の復習予定日を返す
        # due_cards が空（全カード復習済み or カードなし）の場合のみクエリを実行する。
        next_due_date = None
        if not due_card_infos:
            next_due_date = self._get_next_due_date(user_id, user_timezone)

        return DueCardsResponse(
            due_cards=due_card_infos,
            total_due_count=total_due_count,
            next_due_date=next_due_date,
        )

    def _get_next_due_date(
        self, user_id: str, user_timezone: str = "Asia/Tokyo"
    ) -> Optional[str]:
        """Get the next due date for a user's cards.

        Only returns future dates (next_review_at > now).  Past due dates are
        already included in the due cards list, so the "next" due date should
        always be in the future.

        Args:
            user_id: The user's ID.
            user_timezone: User's IANA timezone string（表示用日付の変換に使用）。

        Returns:
            ISO format date string of next due date, or None.
        """
        now = datetime.now(timezone.utc)
        # L-7: GSI クエリは Repository 経由。失敗時は None を返す。
        item = self._card_repo.query_next_due_after(user_id, now)
        if item and "next_review_at" in item:
            return to_user_local_date(item["next_review_at"], user_timezone)
        return None

    def get_review_summary(self, user_id: str, user_timezone: str = "UTC") -> ReviewSummary:
        """Get a summary of review statistics for a user.

        M-7: 集計ロジックは stats_service の共通ヘルパー関数に委譲する。
        DynamoDB クエリは StatsService._fetch_all_cards / _fetch_all_reviews と同等の
        ページネーション付きクエリを使用する。

        Args:
            user_id: The user's ID.
            user_timezone: ユーザーの IANA タイムゾーン文字列（streak 計算用）。
                           デフォルトは "UTC"。

        Returns:
            ReviewSummary dataclass with aggregated statistics.
            Returns a default (all-zeros) ReviewSummary on error.
        """
        default = ReviewSummary(
            total_reviews=0,
            average_grade=0.0,
            total_cards=0,
            cards_due_today=0,
            streak_days=0,
            tag_performance={},
            recent_review_dates=[],
        )

        try:
            # L-7: reviews / cards の全件取得は Repository 経由（ページネーション込み）。
            reviews: List[Dict] = self._review_repo.query_all_reviews(user_id)
            cards: List[Dict] = self._card_repo.scan_all_cards(user_id)

            total_reviews = len(reviews)
            average_grade = (
                sum(int(r["grade"]) for r in reviews) / total_reviews
                if reviews
                else 0.0
            )
            total_cards = len(cards)

            now_iso = datetime.now(timezone.utc).isoformat()
            cards_due_today = sum(
                1 for c in cards if c.get("next_review_at", "") <= now_iso
            )

            # Unique review dates, newest first
            # reviewed_at はユーザーローカル日付へ変換してから streak /
            # recent_review_dates を作る（UTC 日付のままだと JST の同一ローカル日が
            # 2 日に分裂して streak が過大になる）。
            unique_dates = unique_local_review_dates_desc(reviews, user_timezone)

            # M-7: 共通ヘルパー関数に委譲（m-6: user_timezone 対応済み）
            streak_days = calculate_streak(unique_dates, user_timezone=user_timezone)
            tag_performance = calculate_tag_performance(cards, reviews)

            return ReviewSummary(
                total_reviews=total_reviews,
                average_grade=average_grade,
                total_cards=total_cards,
                cards_due_today=cards_due_today,
                streak_days=streak_days,
                tag_performance=tag_performance,
                recent_review_dates=unique_dates,
            )

        except (ClientError, CardServiceError):
            # L-7: Repository は DynamoDB 失敗を CardServiceError へ変換するため、
            # 集計失敗時は既定の ReviewSummary を返す（従来の ClientError 同等挙動）。
            return default

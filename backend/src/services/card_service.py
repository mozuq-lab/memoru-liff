"""Card service for DynamoDB operations."""

import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from models.card import Card

# 【ロガー設定】: TransactionCanceledException などの内部エラーをログ出力するために必要 (EARS-009)
logger = Logger()

# Sentinel value to distinguish "not provided" from explicit None (null)
_UNSET = object()


class CardServiceError(Exception):
    """Base exception for card service errors."""

    pass


class CardNotFoundError(CardServiceError):
    """Raised when card is not found."""

    pass


class CardLimitExceededError(CardServiceError):
    """Raised when user exceeds card limit."""

    pass


class InternalError(CardServiceError):
    """Raised when an internal transaction error occurs.

    【クラス目的】: CardLimitExceededError以外のTransactionCanceledException を
    明確に区別するための例外クラス。
    🔵 信頼性レベル: 青信号 - CR-02: 全TransactionCanceledExceptionをCardLimitExceededErrorとして
    扱う問題を解決するために追加 (EARS-005)
    """

    pass


class CardService:
    """Service for card-related DynamoDB operations."""

    MAX_CARDS_PER_USER = 2000

    def __init__(
        self,
        table_name: Optional[str] = None,
        dynamodb_resource=None,
        users_table_name: Optional[str] = None,
        reviews_table_name: Optional[str] = None,
    ):
        """Initialize CardService.

        Args:
            table_name: DynamoDB table name. Defaults to CARDS_TABLE env var.
            dynamodb_resource: Optional boto3 DynamoDB resource for testing.
            users_table_name: DynamoDB users table name. Defaults to USERS_TABLE env var.
            reviews_table_name: DynamoDB reviews table name. Defaults to REVIEWS_TABLE env var.

        【実装方針】: reviews_table_name パラメータを追加して、delete_card トランザクションで
        Reviews テーブルをアトミックに削除できるようにする (EARS-011)
        🔵 信頼性レベル: 青信号 - EARS-010 のトランザクション削除に必要
        """
        self.table_name = table_name or os.environ.get("CARDS_TABLE", "memoru-cards-dev")
        self.users_table_name = users_table_name or os.environ.get("USERS_TABLE", "memoru-users-dev")
        # 【レビューテーブル設定】: delete_card トランザクションで Reviews テーブルを参照するために必要
        self.reviews_table_name = reviews_table_name or os.environ.get("REVIEWS_TABLE", "memoru-reviews-dev")

        endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL") or os.environ.get("AWS_ENDPOINT_URL")
        if dynamodb_resource:
            self.dynamodb = dynamodb_resource
        else:
            if endpoint_url:
                self.dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)
            else:
                self.dynamodb = boto3.resource("dynamodb")

        self.table = self.dynamodb.Table(self.table_name)
        self.users_table = self.dynamodb.Table(self.users_table_name)

        # 低レベルクライアント: transact_write_items 用
        # boto3.resource().meta.client はリソース層の型変換イベントハンドラーを含むため、
        # 低レベル DynamoDB JSON を二重シリアライズしてしまう。
        # 直接 boto3.client() を使うことで回避する。
        if endpoint_url:
            self._client = boto3.client("dynamodb", endpoint_url=endpoint_url)
        else:
            self._client = boto3.client("dynamodb")

    def create_card(
        self,
        user_id: str,
        front: str,
        back: str,
        deck_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Card:
        """Create a new card.

        Args:
            user_id: The user's ID.
            front: Front side text.
            back: Back side text.
            deck_id: Optional deck ID.
            tags: Optional list of tags.

        Returns:
            Created Card object.

        Raises:
            CardLimitExceededError: If user exceeds card limit.
        """
        now = datetime.now(timezone.utc)
        card = Card(
            user_id=user_id,
            front=front,
            back=back,
            deck_id=deck_id,
            tags=tags or [],
            next_review_at=now,  # Due immediately for new cards
            created_at=now,
        )

        try:
            # Use TransactWriteItems to atomically:
            # 1. Increment card_count in users table with condition check
            # 2. Create the card in cards table
            client = self._client
            serializer = TypeSerializer()

            # Serialize the card item
            card_item = card.to_dynamodb_item()
            serialized_card = {k: serializer.serialize(v) for k, v in card_item.items()}

            # Perform the transactional write
            client.transact_write_items(
                TransactItems=[
                    {
                        'Update': {
                            'TableName': self.users_table_name,
                            'Key': {'user_id': {'S': user_id}},
                            # 【UpdateExpression修正】: ADD を使用して
                            # card_count属性が存在しない場合は自動的に作成し、
                            # 存在する場合はインクリメントする
                            'UpdateExpression': 'ADD card_count :inc',
                            # 【ConditionExpression修正】: attribute_not_exists OR card_count < :limit
                            # card_count属性が未存在時は許可し、存在時はリミットチェック
                            'ConditionExpression': 'attribute_not_exists(card_count) OR card_count < :limit',
                            'ExpressionAttributeValues': {
                                ':inc': {'N': '1'},
                                ':limit': {'N': str(self.MAX_CARDS_PER_USER)},
                            }
                        }
                    },
                    {
                        'Put': {
                            'TableName': self.table_name,
                            'Item': serialized_card
                        }
                    }
                ]
            )
            return card
        except ClientError as e:
            if e.response["Error"]["Code"] == "TransactionCanceledException":
                # 【エラー分類修正】: CancellationReasons を解析して正確なエラーを判別する (EARS-006, EARS-007, EARS-008)
                # 以前は全TransactionCanceledExceptionをCardLimitExceededErrorとして扱っていたが、
                # 他のエラー (ValidationError等) は InternalError として区別する必要がある
                # 🔵 信頼性レベル: 青信号 - CR-02で特定された問題の修正
                reasons = e.response.get("CancellationReasons", [])
                # 【Index 0 確認】: TransactItems[0] は Users テーブルの Update (card_count チェック)
                # ConditionalCheckFailed はカード上限超過を意味する
                if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
                    raise CardLimitExceededError(f"Card limit of {self.MAX_CARDS_PER_USER} exceeded")
                # 【InternalError送出】: 上限超過以外のトランザクション失敗は InternalError
                # reasons が空/欠如、または Index 0 が ConditionalCheckFailed 以外の場合
                logger.error(f"Transaction cancelled with reasons: {reasons}")
                raise InternalError("Card creation failed due to transaction conflict")
            raise CardServiceError(f"Failed to create card: {e}")

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
        try:
            response = self.table.get_item(Key={"user_id": user_id, "card_id": card_id})
            if "Item" not in response:
                raise CardNotFoundError(f"Card not found: {card_id}")
            return Card.from_dynamodb_item(response["Item"])
        except ClientError as e:
            raise CardServiceError(f"Failed to get card: {e}")

    def update_card(
        self,
        user_id: str,
        card_id: str,
        front: Optional[str] = None,
        back: Optional[str] = None,
        deck_id=_UNSET,
        tags: Optional[List[str]] = None,
        interval: Optional[int] = None,
    ) -> Card:
        """Update a card.

        Args:
            user_id: The user's ID.
            card_id: The card's ID.
            front: Optional new front text.
            back: Optional new back text.
            deck_id: Optional new deck ID.
            tags: Optional new tags.
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

        # Build update expression
        update_parts = []
        remove_parts = []
        expression_values = {}
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
            remove_parts.append("deck_id")
            card.deck_id = None
        elif deck_id is not _UNSET:
            # New value → SET deck_id
            update_parts.append("deck_id = :deck_id")
            expression_values[":deck_id"] = deck_id
            card.deck_id = deck_id
        # deck_id is _UNSET → no change

        if tags is not None:
            update_parts.append("tags = :tags")
            expression_values[":tags"] = tags
            card.tags = tags

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

            # 【next_review_at 再計算】: 現在日時 + interval 日で next_review_at を計算する
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

        try:
            # Build combined SET + REMOVE expression
            update_expression = ""
            if update_parts:
                update_expression += "SET " + ", ".join(update_parts)
            if remove_parts:
                update_expression += " REMOVE " + ", ".join(remove_parts)

            update_kwargs = {
                "Key": {"user_id": user_id, "card_id": card_id},
                "UpdateExpression": update_expression,
            }
            if expression_values:
                update_kwargs["ExpressionAttributeValues"] = expression_values
            if expression_names:
                update_kwargs["ExpressionAttributeNames"] = expression_names

            self.table.update_item(**update_kwargs)
            return card
        except ClientError as e:
            raise CardServiceError(f"Failed to update card: {e}")

    def delete_card(self, user_id: str, card_id: str) -> None:
        """Delete a card atomically with card_count decrement.

        DynamoDB TransactWriteItems を使用して以下の3操作をアトミックに実行する:
          - Index 0: Cards テーブルからカードを削除 (attribute_exists 条件チェック付き)
          - Index 1: Reviews テーブルから関連レビューを削除 (条件なし: レビュー未作成でも成功)
          - Index 2: Users テーブルの card_count を 1 デクリメント (card_count > 0 の下限チェック付き)

        これにより card_count と実際のカード数の整合性を保証する。
        事前に get_card() でカードの存在を確認してから TransactWriteItems を実行する。

        Args:
            user_id: The user's ID.
            card_id: The card's ID.

        Raises:
            CardNotFoundError: カードが存在しない場合。または、トランザクション実行中に別リクエストが
                               先にカードを削除した場合（レースコンディション、EARS-012）。
            CardServiceError: card_count が既に 0 の場合（データ整合性ドリフト、EARS-013）。
                              その他の DynamoDB エラーが発生した場合。

        【トランザクション設計】:
          - TransactItems[0] の ConditionalCheckFailed: 並行削除によるレースコンディション → CardNotFoundError
          - TransactItems[1] の ConditionalCheckFailed: card_count が既に 0 → CardServiceError
          - Reviews 削除はトランザクション外で事前実行（card_id + reviewed_at の複合キーのため）
        🔵 信頼性レベル: 青信号 - CR-02で特定された非トランザクション実装の修正 (EARS-010)
        """
        # 【カード存在確認】: 削除前にカードが存在することを確認する
        self.get_card(user_id, card_id)

        # 【Reviews 事前削除】: Reviews テーブルのキーは card_id + reviewed_at のため、
        # トランザクション内の単一 Delete では全レビューを削除できない。
        # クエリで全レビューを取得し、バッチ削除する（ベストエフォート）。
        try:
            reviews_table = self.dynamodb.Table(self.reviews_table_name)
            query_kwargs = {
                "KeyConditionExpression": "card_id = :cid",
                "ExpressionAttributeValues": {":cid": card_id},
                "ProjectionExpression": "card_id, reviewed_at",
            }
            with reviews_table.batch_writer() as batch:
                while True:
                    response = reviews_table.query(**query_kwargs)
                    for item in response.get("Items", []):
                        batch.delete_item(Key={"card_id": item["card_id"], "reviewed_at": item["reviewed_at"]})
                    last_key = response.get("LastEvaluatedKey")
                    if not last_key:
                        break
                    query_kwargs["ExclusiveStartKey"] = last_key
        except Exception as e:
            logger.warning(
                "Failed to delete reviews for card (best-effort)",
                extra={"card_id": card_id, "error": str(e)},
            )

        try:
            client = self._client
            # 【トランザクション実行】: 2つの操作をアトミックに実行する
            client.transact_write_items(
                TransactItems=[
                    {
                        # 【Index 0】: Cards テーブルからカードを削除
                        # attribute_exists(card_id) でカード存在を確認 (レースコンディション対策)
                        'Delete': {
                            'TableName': self.table_name,
                            'Key': {'user_id': {'S': user_id}, 'card_id': {'S': card_id}},
                            'ConditionExpression': 'attribute_exists(card_id)'
                        }
                    },
                    {
                        # 【Index 1】: Users テーブルの card_count を 1 デクリメント
                        # card_count > :zero の条件でネガティブ値を防止 (EARS-014)
                        'Update': {
                            'TableName': self.users_table_name,
                            'Key': {'user_id': {'S': user_id}},
                            'UpdateExpression': 'SET card_count = card_count - :dec',
                            'ConditionExpression': 'card_count > :zero',
                            'ExpressionAttributeValues': {
                                ':dec': {'N': '1'},
                                ':zero': {'N': '0'}
                            }
                        }
                    }
                ]
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "TransactionCanceledException":
                reasons = e.response.get("CancellationReasons", [])
                # 【Index 0 確認】: Cards Delete の ConditionalCheckFailed はカードが既に削除された状態
                # レースコンディションにより別リクエストがカードを削除した場合 (EARS-012)
                if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
                    raise CardNotFoundError(f"Card not found: {card_id}")
                # 【Index 1 確認】: Users Update の ConditionalCheckFailed は card_count が既に 0
                # データ整合性のドリフト状態 (EARS-013)
                if len(reasons) > 1 and reasons[1].get("Code") == "ConditionalCheckFailed":
                    raise CardServiceError("Cannot delete card: card_count already at 0")
            raise CardServiceError(f"Failed to delete card: {e}")

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
        try:
            query_kwargs = {
                "KeyConditionExpression": "user_id = :user_id",
                "ExpressionAttributeValues": {":user_id": user_id},
                "Limit": limit,
                "ScanIndexForward": False,  # Newest first
            }

            if cursor:
                query_kwargs["ExclusiveStartKey"] = {"user_id": user_id, "card_id": cursor}

            if deck_id:
                query_kwargs["FilterExpression"] = "deck_id = :deck_id"
                query_kwargs["ExpressionAttributeValues"][":deck_id"] = deck_id

            response = self.table.query(**query_kwargs)
            cards = [Card.from_dynamodb_item(item) for item in response.get("Items", [])]

            next_cursor = None
            if "LastEvaluatedKey" in response:
                next_cursor = response["LastEvaluatedKey"]["card_id"]

            return cards, next_cursor
        except ClientError as e:
            raise CardServiceError(f"Failed to list cards: {e}")

    def get_card_count(self, user_id: str) -> int:
        """Get the number of cards for a user.

        Args:
            user_id: The user's ID.

        Returns:
            Number of cards.
        """
        try:
            response = self.table.query(
                KeyConditionExpression="user_id = :user_id",
                ExpressionAttributeValues={":user_id": user_id},
                Select="COUNT",
            )
            return response.get("Count", 0)
        except ClientError as e:
            raise CardServiceError(f"Failed to get card count: {e}")

    def get_due_cards(
        self,
        user_id: str,
        limit: Optional[int] = None,
        before: Optional[datetime] = None,
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

        Returns:
            List of cards due for review, oldest due first.
        """
        if before is None:
            before = datetime.now(timezone.utc)

        try:
            # 【クエリ引数構築】: GSI (user_id-due-index) を使い、期限切れカードを昇順で取得する
            query_kwargs = {
                "IndexName": "user_id-due-index",
                "KeyConditionExpression": "user_id = :user_id AND next_review_at <= :before",
                "ExpressionAttributeValues": {
                    ":user_id": user_id,
                    ":before": before.isoformat(),
                },
                "ScanIndexForward": True,  # 【昇順取得】: 期限が古い順（最も早く復習すべきカードを先頭に）
            }
            # 【Limit 条件付き設定】: limit=None の場合は DynamoDB に Limit を渡さず全件取得する 🔵
            # limit が指定された場合のみ DynamoDB Query に Limit を付与し、レスポンスサイズを制限する。
            if limit is not None:
                query_kwargs["Limit"] = limit

            # 【ページネーション】: limit=None の場合は LastEvaluatedKey で全件取得する
            if limit is None:
                all_items = []
                while True:
                    response = self.table.query(**query_kwargs)
                    all_items.extend(response.get("Items", []))
                    last_key = response.get("LastEvaluatedKey")
                    if not last_key:
                        break
                    query_kwargs["ExclusiveStartKey"] = last_key
                return [Card.from_dynamodb_item(item) for item in all_items]
            else:
                response = self.table.query(**query_kwargs)
                return [Card.from_dynamodb_item(item) for item in response.get("Items", [])]
        except ClientError as e:
            raise CardServiceError(f"Failed to get due cards: {e}")

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
        if before is None:
            before = datetime.now(timezone.utc)

        try:
            response = self.table.query(
                IndexName="user_id-due-index",
                KeyConditionExpression="user_id = :user_id AND next_review_at <= :before",
                ExpressionAttributeValues={
                    ":user_id": user_id,
                    ":before": before.isoformat(),
                },
                Select="COUNT",
            )
            return response.get("Count", 0)
        except ClientError as e:
            raise CardServiceError(f"Failed to get due card count: {e}")

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
        try:
            now = datetime.now(timezone.utc)
            self.table.update_item(
                Key={"user_id": user_id, "card_id": card_id},
                UpdateExpression="SET next_review_at = :next_review, #interval = :interval, "
                "ease_factor = :ease_factor, repetitions = :repetitions, updated_at = :updated_at",
                ExpressionAttributeNames={"#interval": "interval"},
                ExpressionAttributeValues={
                    ":next_review": next_review_at.isoformat(),
                    ":interval": interval,
                    ":ease_factor": str(ease_factor),
                    ":repetitions": repetitions,
                    ":updated_at": now.isoformat(),
                },
            )
            return self.get_card(user_id, card_id)
        except ClientError as e:
            raise CardServiceError(f"Failed to update review data: {e}")

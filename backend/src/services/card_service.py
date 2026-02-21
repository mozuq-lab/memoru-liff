"""Card service for DynamoDB operations."""

import os
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import boto3
from aws_lambda_powertools import Logger
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from ..models.card import Card

# 【ロガー設定】: TransactionCanceledException などの内部エラーをログ出力するために必要 (EARS-009)
logger = Logger()


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

        if dynamodb_resource:
            self.dynamodb = dynamodb_resource
        else:
            endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
            if endpoint_url:
                self.dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)
            else:
                self.dynamodb = boto3.resource("dynamodb")

        self.table = self.dynamodb.Table(self.table_name)
        self.users_table = self.dynamodb.Table(self.users_table_name)

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
            client = self.dynamodb.meta.client
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
                            # 【UpdateExpression修正】: if_not_exists(card_count, :zero) を使用して
                            # card_count属性が存在しない場合に安全に0として扱う (EARS-001)
                            # 🔵 信頼性レベル: 青信号 - CR-02で特定されたバグの修正
                            'UpdateExpression': 'SET card_count = if_not_exists(card_count, :zero) + :inc',
                            # 【ConditionExpression修正】: if_not_exists(card_count, :zero) を使用して
                            # card_count属性が存在しない場合のリミットチェックも安全に行う (EARS-002)
                            # 🔵 信頼性レベル: 青信号 - CR-02で特定されたバグの修正
                            'ConditionExpression': 'if_not_exists(card_count, :zero) < :limit',
                            'ExpressionAttributeValues': {
                                ':inc': {'N': '1'},
                                ':limit': {'N': str(self.MAX_CARDS_PER_USER)},
                                # 【:zero追加】: if_not_exists のフォールバック値として必要 (EARS-003)
                                ':zero': {'N': '0'}
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
        deck_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> Card:
        """Update a card.

        Args:
            user_id: The user's ID.
            card_id: The card's ID.
            front: Optional new front text.
            back: Optional new back text.
            deck_id: Optional new deck ID.
            tags: Optional new tags.

        Returns:
            Updated Card object.

        Raises:
            CardNotFoundError: If card does not exist.
        """
        # Verify card exists
        card = self.get_card(user_id, card_id)

        # Build update expression
        update_parts = []
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

        if deck_id is not None:
            update_parts.append("deck_id = :deck_id")
            expression_values[":deck_id"] = deck_id
            card.deck_id = deck_id

        if tags is not None:
            update_parts.append("tags = :tags")
            expression_values[":tags"] = tags
            card.tags = tags

        if not update_parts:
            return card

        now = datetime.now(timezone.utc)
        update_parts.append("updated_at = :updated_at")
        expression_values[":updated_at"] = now.isoformat()
        card.updated_at = now

        try:
            update_expression = "SET " + ", ".join(update_parts)
            update_kwargs = {
                "Key": {"user_id": user_id, "card_id": card_id},
                "UpdateExpression": update_expression,
                "ExpressionAttributeValues": expression_values,
            }
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
          - TransactItems[2] の ConditionalCheckFailed: card_count が既に 0 → CardServiceError
        🔵 信頼性レベル: 青信号 - CR-02で特定された非トランザクション実装の修正 (EARS-010)
        """
        # 【カード存在確認】: 削除前にカードが存在することを確認する
        self.get_card(user_id, card_id)

        try:
            client = self.dynamodb.meta.client
            # 【トランザクション実行】: 3つの操作をアトミックに実行する
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
                        # 【Index 1】: Reviews テーブルから関連レビューを削除
                        # 条件なし - レビューが存在しなくても成功する (EC-012対応)
                        'Delete': {
                            'TableName': self.reviews_table_name,
                            'Key': {'user_id': {'S': user_id}, 'card_id': {'S': card_id}}
                        }
                    },
                    {
                        # 【Index 2】: Users テーブルの card_count を 1 デクリメント
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
                # 【Index 2 確認】: Users Update の ConditionalCheckFailed は card_count が既に 0
                # データ整合性のドリフト状態 (EARS-013)
                if len(reasons) > 2 and reasons[2].get("Code") == "ConditionalCheckFailed":
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
        limit: int = 20,
        before: Optional[datetime] = None,
    ) -> List[Card]:
        """Get cards due for review.

        Args:
            user_id: The user's ID.
            limit: Maximum number of cards to return.
            before: Get cards due before this time (defaults to now).

        Returns:
            List of cards due for review.
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
                Limit=limit,
                ScanIndexForward=True,  # Oldest due first
            )
            return [Card.from_dynamodb_item(item) for item in response.get("Items", [])]
        except ClientError as e:
            raise CardServiceError(f"Failed to get due cards: {e}")

    def get_due_card_count(
        self,
        user_id: str,
        before: Optional[datetime] = None,
    ) -> int:
        """Get count of cards due for review.

        Args:
            user_id: The user's ID.
            before: Get cards due before this time (defaults to now).

        Returns:
            Number of cards due for review.
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

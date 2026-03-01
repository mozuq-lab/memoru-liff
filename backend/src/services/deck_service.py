"""Deck service for DynamoDB operations."""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from models.deck import Deck

logger = Logger()

# Sentinel value to distinguish "not provided" from explicit None (null).
# 【Sentinel 定数】: update_deck で description/color が省略された場合に「変更なし」を表現する。
# 🔵 card_service.py と同一パターン (TASK-0085 参照)
_UNSET = object()


class DeckServiceError(Exception):
    """Base exception for deck service errors."""

    pass


class DeckNotFoundError(DeckServiceError):
    """Raised when deck is not found."""

    pass


class DeckLimitExceededError(DeckServiceError):
    """Raised when user exceeds deck limit."""

    pass


class DeckService:
    """Service for deck-related DynamoDB operations."""

    MAX_DECKS_PER_USER = 50

    def __init__(
        self,
        table_name: Optional[str] = None,
        cards_table_name: Optional[str] = None,
        dynamodb_resource: Optional[Any] = None,
    ):
        """Initialize DeckService.

        Args:
            table_name: DynamoDB decks table name. Defaults to DECKS_TABLE env var.
            cards_table_name: DynamoDB cards table name. Defaults to CARDS_TABLE env var.
            dynamodb_resource: Optional boto3 DynamoDB resource for testing.
        """
        self.table_name = table_name or os.environ.get("DECKS_TABLE", "memoru-decks-dev")
        self.cards_table_name = cards_table_name or os.environ.get("CARDS_TABLE", "memoru-cards-dev")

        endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL") or os.environ.get("AWS_ENDPOINT_URL")
        if dynamodb_resource:
            self.dynamodb = dynamodb_resource
        else:
            if endpoint_url:
                self.dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)
            else:
                self.dynamodb = boto3.resource("dynamodb")

        self.table = self.dynamodb.Table(self.table_name)
        self.cards_table = self.dynamodb.Table(self.cards_table_name)

    def create_deck(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        color: Optional[str] = None,
    ) -> Deck:
        """Create a new deck with atomic limit verification.

        Uses a 3-step approach to prevent race conditions:
        1. Optimistic check: Query(COUNT) to reject obvious over-limit
        2. PutItem with ConditionExpression to prevent duplicate deck_id
        3. Post-creation count verification with rollback if limit exceeded

        Args:
            user_id: The user's ID.
            name: Deck name.
            description: Optional deck description.
            color: Optional hex color code.

        Returns:
            Created Deck object.

        Raises:
            DeckLimitExceededError: If user exceeds deck limit.
        """
        # Step 1: Optimistic check
        current_count = self._get_deck_count(user_id)
        if current_count >= self.MAX_DECKS_PER_USER:
            raise DeckLimitExceededError(
                f"Deck limit of {self.MAX_DECKS_PER_USER} exceeded"
            )

        now = datetime.now(timezone.utc)
        deck = Deck(
            user_id=user_id,
            name=name,
            description=description,
            color=color,
            created_at=now,
        )

        # Step 2: PutItem with ConditionExpression to prevent duplicate deck_id
        try:
            self.table.put_item(
                Item=deck.to_dynamodb_item(),
                ConditionExpression="attribute_not_exists(user_id) AND attribute_not_exists(deck_id)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise DeckLimitExceededError(
                    f"Deck limit of {self.MAX_DECKS_PER_USER} exceeded"
                )
            raise DeckServiceError(f"Failed to create deck: {e}")

        # Step 3: Post-creation count verification (race detection)
        post_count = self._get_deck_count(user_id)
        if post_count > self.MAX_DECKS_PER_USER:
            # Race detected: rollback by deleting the just-created deck
            try:
                self.table.delete_item(
                    Key={"user_id": user_id, "deck_id": deck.deck_id}
                )
            except ClientError:
                logger.warning(f"Failed to rollback deck {deck.deck_id} after race detection")
            raise DeckLimitExceededError(
                f"Deck limit of {self.MAX_DECKS_PER_USER} exceeded"
            )

        return deck

    def get_deck(self, user_id: str, deck_id: str) -> Deck:
        """Get a deck by ID.

        Args:
            user_id: The user's ID.
            deck_id: The deck's ID.

        Returns:
            Deck object.

        Raises:
            DeckNotFoundError: If deck does not exist.
        """
        try:
            response = self.table.get_item(
                Key={"user_id": user_id, "deck_id": deck_id}
            )
            if "Item" not in response:
                raise DeckNotFoundError(f"Deck not found: {deck_id}")
            return Deck.from_dynamodb_item(response["Item"])
        except DeckNotFoundError:
            raise
        except ClientError as e:
            raise DeckServiceError(f"Failed to get deck: {e}")

    def list_decks(self, user_id: str) -> List[Deck]:
        """List all decks for a user.

        Args:
            user_id: The user's ID.

        Returns:
            List of Deck objects.
        """
        try:
            decks: List[Deck] = []
            query_kwargs: Dict[str, Any] = {
                "KeyConditionExpression": "user_id = :user_id",
                "ExpressionAttributeValues": {":user_id": user_id},
            }

            while True:
                response = self.table.query(**query_kwargs)
                decks.extend(
                    Deck.from_dynamodb_item(item)
                    for item in response.get("Items", [])
                )
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key

            return decks
        except ClientError as e:
            raise DeckServiceError(f"Failed to list decks: {e}")

    def update_deck(
        self,
        user_id: str,
        deck_id: str,
        name: Any = _UNSET,
        description: Any = _UNSET,
        color: Any = _UNSET,
    ) -> Deck:
        """Update a deck.

        【Sentinel パターン】: 各フィールドは 3 状態を持つ:
          - _UNSET（省略）: 変更なし（DynamoDB 操作なし）
          - None（明示的 null）: DynamoDB から属性を REMOVE
          - 文字列値: DynamoDB に SET

        Args:
            user_id: The user's ID.
            deck_id: The deck's ID.
            name: _UNSET（省略）=変更なし, 文字列=SET。name は必須フィールドのため REMOVE 不可。
            description: _UNSET（省略）=変更なし, None=REMOVE（DynamoDB 属性削除）, 文字列=SET。
            color: _UNSET（省略）=変更なし, None=REMOVE（DynamoDB 属性削除）, 文字列=SET。

        Returns:
            Updated Deck object.

        Raises:
            DeckNotFoundError: If deck does not exist.

        🔵 信頼性レベル: 青信号 - card_service.py update_card の deck_id Sentinel パターンと同一設計
        """
        # 【デッキ存在確認】: 更新前にデッキが存在することを確認する
        deck = self.get_deck(user_id, deck_id)

        # 【UpdateExpression 構築準備】: SET パーツと REMOVE パーツを別々に収集する
        # 🔵 card_service.py の update_card と同一パターン
        update_parts = []
        remove_parts = []
        expression_values: Dict[str, Any] = {}
        expression_names: Dict[str, str] = {}

        # 【name 処理】: name は必須フィールドのため REMOVE はサポートしない
        # _UNSET（省略）→ 変更なし、値→ SET のみ
        # 🔵 信頼性レベル: 青信号 - 要件定義 REQ-101 より name は必須
        if name is not _UNSET:
            update_parts.append("#name = :name")
            expression_values[":name"] = name
            expression_names["#name"] = "name"
            deck.name = name

        # 【description 処理】: Sentinel パターンで 3 状態を判定
        # None → REMOVE（DynamoDB から属性削除）
        # _UNSET → 変更なし（何もしない）
        # 文字列値 → SET
        # 🔵 信頼性レベル: 青信号 - REQ-105 より description はオプショナル
        if description is None:
            # 【REMOVE 対象追加】: DynamoDB から description 属性を削除する
            remove_parts.append("description")
            deck.description = None
        elif description is not _UNSET:
            # 【SET 対象追加】: description を新しい値で更新する
            update_parts.append("description = :description")
            expression_values[":description"] = description
            deck.description = description
        # description is _UNSET → 変更なし（何もしない）

        # 【color 処理】: description と同一の Sentinel パターン
        # None → REMOVE（DynamoDB から属性削除）
        # _UNSET → 変更なし（何もしない）
        # 文字列値 → SET
        # 🔵 信頼性レベル: 青信号 - REQ-106 より color はオプショナル
        if color is None:
            # 【REMOVE 対象追加】: DynamoDB から color 属性を削除する
            remove_parts.append("color")
            deck.color = None
        elif color is not _UNSET:
            # 【SET 対象追加】: color を新しい値で更新する
            update_parts.append("color = :color")
            expression_values[":color"] = color
            deck.color = color
        # color is _UNSET → 変更なし（何もしない）

        # 【変更なし判定】: SET も REMOVE もない場合は DynamoDB 操作なしで返す
        if not update_parts and not remove_parts:
            return deck

        # 【updated_at 更新】: 変更があった場合は updated_at を SET に追加する
        # REMOVE のみの場合でも updated_at は SET 側に追加するため update_parts を使う
        # 🔵 信頼性レベル: 青信号 - TC-016 より REMOVE のみでも updated_at は更新が必要
        now = datetime.now(timezone.utc)
        update_parts.append("updated_at = :updated_at")
        expression_values[":updated_at"] = now.isoformat()
        deck.updated_at = now

        try:
            # 【UpdateExpression 構築】: SET句（値更新 + updated_at）と REMOVE句（属性削除）を結合する
            # 🔵 card_service.py update_card の SET + REMOVE 構築と同一パターン
            update_expression = ""
            if update_parts:
                update_expression += "SET " + ", ".join(update_parts)
            if remove_parts:
                update_expression += " REMOVE " + ", ".join(remove_parts)

            update_kwargs: Dict[str, Any] = {
                "Key": {"user_id": user_id, "deck_id": deck_id},
                "UpdateExpression": update_expression,
            }
            if expression_values:
                update_kwargs["ExpressionAttributeValues"] = expression_values
            if expression_names:
                update_kwargs["ExpressionAttributeNames"] = expression_names

            self.table.update_item(**update_kwargs)
            return deck
        except ClientError as e:
            raise DeckServiceError(f"Failed to update deck: {e}")

    def delete_deck(self, user_id: str, deck_id: str) -> None:
        """Delete a deck and reset deck_id on associated cards.

        1. Verify deck exists
        2. Delete the deck item
        3. Query cards with this deck_id and reset to null (best-effort)

        Args:
            user_id: The user's ID.
            deck_id: The deck's ID.

        Raises:
            DeckNotFoundError: If deck does not exist.
        """
        # Verify deck exists
        self.get_deck(user_id, deck_id)

        try:
            self.table.delete_item(
                Key={"user_id": user_id, "deck_id": deck_id}
            )
        except ClientError as e:
            raise DeckServiceError(f"Failed to delete deck: {e}")

        # Best-effort: reset deck_id on associated cards
        self._reset_cards_deck_id(user_id, deck_id)

    def get_deck_card_counts(
        self, user_id: str, deck_ids: List[str]
    ) -> Dict[str, int]:
        """Get card counts per deck.

        Queries the Cards table for the user and counts cards per deck_id.

        Args:
            user_id: The user's ID.
            deck_ids: List of deck IDs to count for.

        Returns:
            Dict mapping deck_id to card count.
        """
        if not deck_ids:
            return {}

        counts: Dict[str, int] = {deck_id: 0 for deck_id in deck_ids}

        try:
            # Query all cards for the user
            query_kwargs: Dict[str, Any] = {
                "KeyConditionExpression": "user_id = :user_id",
                "ExpressionAttributeValues": {":user_id": user_id},
                "ProjectionExpression": "deck_id",
            }

            while True:
                response = self.cards_table.query(**query_kwargs)
                for item in response.get("Items", []):
                    card_deck_id = item.get("deck_id")
                    if card_deck_id and card_deck_id in counts:
                        counts[card_deck_id] += 1
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key

            return counts
        except ClientError as e:
            logger.warning(f"Failed to get deck card counts: {e}")
            return counts

    def get_deck_due_counts(
        self, user_id: str, deck_ids: List[str]
    ) -> Dict[str, int]:
        """Get due card counts per deck.

        Queries the Cards table using the user_id-due-index GSI
        and counts due cards per deck_id.

        Args:
            user_id: The user's ID.
            deck_ids: List of deck IDs to count for.

        Returns:
            Dict mapping deck_id to due card count.
        """
        if not deck_ids:
            return {}

        counts: Dict[str, int] = {deck_id: 0 for deck_id in deck_ids}
        now = datetime.now(timezone.utc)

        try:
            query_kwargs: Dict[str, Any] = {
                "IndexName": "user_id-due-index",
                "KeyConditionExpression": "user_id = :user_id AND next_review_at <= :now",
                "ExpressionAttributeValues": {
                    ":user_id": user_id,
                    ":now": now.isoformat(),
                },
                "ProjectionExpression": "deck_id",
            }

            while True:
                response = self.cards_table.query(**query_kwargs)
                for item in response.get("Items", []):
                    card_deck_id = item.get("deck_id")
                    if card_deck_id and card_deck_id in counts:
                        counts[card_deck_id] += 1
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key

            return counts
        except ClientError as e:
            logger.warning(f"Failed to get deck due counts: {e}")
            return counts

    def _get_deck_count(self, user_id: str) -> int:
        """Get the number of decks for a user.

        Args:
            user_id: The user's ID.

        Returns:
            Number of decks.
        """
        try:
            response = self.table.query(
                KeyConditionExpression="user_id = :user_id",
                ExpressionAttributeValues={":user_id": user_id},
                Select="COUNT",
            )
            return response.get("Count", 0)
        except ClientError as e:
            raise DeckServiceError(f"Failed to get deck count: {e}")

    def _reset_cards_deck_id(self, user_id: str, deck_id: str) -> None:
        """Reset deck_id to null on cards that belong to the deleted deck.

        This is a best-effort operation — partial failures are logged but not raised.

        Args:
            user_id: The user's ID.
            deck_id: The deleted deck's ID.
        """
        try:
            # Query cards with this deck_id
            query_kwargs: Dict[str, Any] = {
                "KeyConditionExpression": "user_id = :user_id",
                "FilterExpression": "deck_id = :deck_id",
                "ExpressionAttributeValues": {
                    ":user_id": user_id,
                    ":deck_id": deck_id,
                },
                "ProjectionExpression": "user_id, card_id",
            }

            card_keys: List[Dict[str, str]] = []
            while True:
                response = self.cards_table.query(**query_kwargs)
                for item in response.get("Items", []):
                    card_keys.append(
                        {"user_id": item["user_id"], "card_id": item["card_id"]}
                    )
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key

            if not card_keys:
                return

            # Update each card to remove deck_id
            now = datetime.now(timezone.utc)
            for key in card_keys:
                try:
                    self.cards_table.update_item(
                        Key=key,
                        UpdateExpression="REMOVE deck_id SET updated_at = :updated_at",
                        ExpressionAttributeValues={
                            ":updated_at": now.isoformat(),
                        },
                    )
                except ClientError as e:
                    logger.warning(
                        f"Failed to reset deck_id on card {key['card_id']}: {e}"
                    )
        except ClientError as e:
            logger.warning(f"Failed to query cards for deck reset: {e}")

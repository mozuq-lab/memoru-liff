"""Card service for DynamoDB operations."""

import os
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from ..models.card import Card


class CardServiceError(Exception):
    """Base exception for card service errors."""

    pass


class CardNotFoundError(CardServiceError):
    """Raised when card is not found."""

    pass


class CardLimitExceededError(CardServiceError):
    """Raised when user exceeds card limit."""

    pass


class CardService:
    """Service for card-related DynamoDB operations."""

    MAX_CARDS_PER_USER = 2000

    def __init__(self, table_name: Optional[str] = None, dynamodb_resource=None):
        """Initialize CardService.

        Args:
            table_name: DynamoDB table name. Defaults to CARDS_TABLE env var.
            dynamodb_resource: Optional boto3 DynamoDB resource for testing.
        """
        self.table_name = table_name or os.environ.get("CARDS_TABLE", "memoru-cards-dev")

        if dynamodb_resource:
            self.dynamodb = dynamodb_resource
        else:
            endpoint_url = os.environ.get("AWS_ENDPOINT_URL")
            if endpoint_url:
                self.dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)
            else:
                self.dynamodb = boto3.resource("dynamodb")

        self.table = self.dynamodb.Table(self.table_name)

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
        # Check card count limit
        current_count = self.get_card_count(user_id)
        if current_count >= self.MAX_CARDS_PER_USER:
            raise CardLimitExceededError(f"Card limit of {self.MAX_CARDS_PER_USER} exceeded")

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
            self.table.put_item(Item=card.to_dynamodb_item())
            return card
        except ClientError as e:
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
        """Delete a card.

        Args:
            user_id: The user's ID.
            card_id: The card's ID.

        Raises:
            CardNotFoundError: If card does not exist.
        """
        # Verify card exists
        self.get_card(user_id, card_id)

        try:
            self.table.delete_item(Key={"user_id": user_id, "card_id": card_id})
        except ClientError as e:
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

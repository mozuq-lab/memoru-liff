"""TutorService — Session management for AI Tutor feature.

Handles session lifecycle: start, send_message, end, list, get.
Includes auto-end of existing active sessions, timeout checks,
message limit enforcement, and TTL calculation.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from models.tutor import (
    SendMessageResponse,
    TutorMessage,
    TutorSessionResponse,
)
from services.prompts.tutor import format_cards_context, get_system_prompt
from services.tutor_ai_service import create_tutor_ai_service
from services.tutor_session_factory import create_tutor_session_manager

logger = Logger()

# Exceptions
class TutorServiceError(Exception):
    """Base exception for TutorService errors."""


class SessionNotFoundError(TutorServiceError):
    """Raised when a session cannot be found."""


class SessionEndedError(TutorServiceError):
    """Raised when trying to interact with an ended/timed_out session."""


class MessageLimitError(TutorServiceError):
    """Raised when session message limit is reached."""


class DeckNotFoundError(TutorServiceError):
    """Raised when a deck cannot be found."""


class EmptyDeckError(TutorServiceError):
    """Raised when a deck has no cards."""


class InsufficientReviewDataError(TutorServiceError):
    """Raised when weak_point mode is requested but no review history exists."""


class TutorService:
    """Manages tutor session lifecycle and DynamoDB persistence."""

    MAX_ROUNDS = int(os.environ.get("TUTOR_MAX_ROUNDS", "20"))
    TIMEOUT_MINUTES = int(os.environ.get("TUTOR_TIMEOUT_MINUTES", "30"))
    TTL_DAYS = 7

    def __init__(
        self,
        table_name: str | None = None,
        dynamodb_resource: Any | None = None,
        ai_service: Any | None = None,
        session_manager_factory: Any | None = None,
    ):
        self.table_name = table_name or os.environ.get(
            "TUTOR_SESSIONS_TABLE", "memoru-tutor-sessions-dev"
        )

        endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL") or os.environ.get(
            "AWS_ENDPOINT_URL"
        )
        if dynamodb_resource:
            self.dynamodb = dynamodb_resource
        elif endpoint_url:
            self.dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)
        else:
            self.dynamodb = boto3.resource("dynamodb")

        self.table = self.dynamodb.Table(self.table_name)

        # Cards and decks tables for context loading
        self.cards_table_name = os.environ.get("CARDS_TABLE", "memoru-cards-dev")
        self.decks_table_name = os.environ.get("DECKS_TABLE", "memoru-decks-dev")
        self.cards_table = self.dynamodb.Table(self.cards_table_name)
        self.decks_table = self.dynamodb.Table(self.decks_table_name)

        self.ai_service = ai_service if ai_service is not None else create_tutor_ai_service()
        self.session_manager_factory = session_manager_factory or create_tutor_session_manager

    def start_session(
        self,
        user_id: str,
        deck_id: str,
        mode: str,
    ) -> TutorSessionResponse:
        """Start a new tutor session.

        Auto-ends any existing active session for the user.
        Loads deck cards, builds system prompt, calls AI for greeting.

        Args:
            user_id: The user's ID.
            deck_id: Target deck ID.
            mode: Learning mode (free_talk, quiz, weak_point).

        Returns:
            TutorSessionResponse with the new session data.
        """
        # Validate deck and cards BEFORE ending existing sessions (C-1 fix)
        deck = self._get_deck(user_id, deck_id)
        cards = self._get_deck_cards(user_id, deck_id)

        if not cards:
            raise EmptyDeckError(
                "このデッキにはカードがありません。カードを追加してからセッションを開始してください。"
            )

        # Build system prompt
        cards_context = format_cards_context(cards)

        # For weak_point mode, retrieve weak card data
        weak_cards_context = None
        if mode == "weak_point":
            weak_cards = self._get_weak_cards_for_deck(user_id, deck_id, cards)
            if not weak_cards:
                raise InsufficientReviewDataError(
                    "レビュー履歴が不足しています。Free Talk モードをお試しください。"
                )
            weak_cards_context = self._format_weak_cards_context(weak_cards)

        system_prompt = get_system_prompt(
            mode=mode,  # type: ignore[arg-type]
            deck_name=deck.get("name", ""),
            cards_context=cards_context,
            weak_cards_context=weak_cards_context,
        )

        # Generate session_id before AI call
        session_id = f"tutor_{uuid.uuid4()}"
        valid_card_ids = {c["card_id"] for c in cards}

        # All validation passed — now safe to end old sessions
        self._auto_end_active_sessions(user_id)

        now = datetime.now(timezone.utc)

        # Persist metadata to DynamoDB BEFORE SessionManager writes messages
        # (put_item replaces entire item, so it must run before append_message)
        item: dict[str, Any] = {
            "user_id": user_id,
            "session_id": session_id,
            "deck_id": deck_id,
            "mode": mode,
            "status": "active",
            "message_count": 0,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "system_prompt": system_prompt,
            "deck_card_ids": list(valid_card_ids),
        }
        self.table.put_item(Item=item)

        # Generate AI greeting via SessionManager-attached Agent
        sm = self.session_manager_factory(session_id=session_id, user_id=user_id)
        try:
            greeting_content, related_cards = self.ai_service.generate_response(
                system_prompt=system_prompt,
                messages="セッションを開始してください。デッキの内容を要約して挨拶してください。",
                session_manager=sm,
            )
        finally:
            sm.close()
        greeting_content = self.ai_service.clean_response_text(greeting_content)

        # Validate related_cards against deck's card IDs
        related_cards = [cid for cid in related_cards if cid in valid_card_ids]

        greeting_msg = TutorMessage(
            role="assistant",
            content=greeting_content,
            related_cards=related_cards,
            timestamp=now.isoformat(),
        )

        return TutorSessionResponse(
            session_id=session_id,
            deck_id=deck_id,
            mode=mode,  # type: ignore[arg-type]
            status="active",
            messages=[greeting_msg],
            message_count=0,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
        )

    def send_message(
        self,
        user_id: str,
        session_id: str,
        content: str,
    ) -> SendMessageResponse:
        """Send a user message and get AI response.

        Performs timeout check and message limit check before processing.

        Args:
            user_id: The user's ID.
            session_id: Target session ID.
            content: User's message content.

        Returns:
            SendMessageResponse with AI's reply.

        Raises:
            SessionNotFoundError: If session doesn't exist.
            SessionEndedError: If session is ended/timed_out.
            MessageLimitError: If message limit reached.
        """
        item = self._get_session_item(user_id, session_id)

        # Check status
        status = item["status"]
        if status in ("ended", "timed_out"):
            raise SessionEndedError(f"Session {session_id} is {status}")

        # Check timeout
        updated_at = datetime.fromisoformat(item["updated_at"])
        if datetime.now(timezone.utc) - updated_at > timedelta(minutes=self.TIMEOUT_MINUTES):
            self._mark_timed_out(user_id, session_id)
            raise SessionEndedError(f"Session {session_id} has timed out")

        # Check message limit
        current_count = int(item.get("message_count", 0))
        if current_count >= self.MAX_ROUNDS:
            raise MessageLimitError(f"Session {session_id} has reached message limit")

        # Get AI response via SessionManager
        system_prompt = item.get("system_prompt", "")
        sm = self.session_manager_factory(session_id=session_id, user_id=user_id)
        try:
            ai_content, related_cards = self.ai_service.generate_response(
                system_prompt=system_prompt,
                messages=content,
                session_manager=sm,
            )
        finally:
            sm.close()
        ai_content = self.ai_service.clean_response_text(ai_content)

        # Validate related_cards against deck's card IDs
        deck_card_ids = set(item.get("deck_card_ids", []))
        if deck_card_ids:
            related_cards = [cid for cid in related_cards if cid in deck_card_ids]

        ai_msg = TutorMessage(
            role="assistant",
            content=ai_content,
            related_cards=related_cards,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

        new_count = current_count + 1
        is_limit_reached = new_count >= self.MAX_ROUNDS

        # Update DynamoDB metadata (messages managed by SessionManager)
        update_expr = "SET message_count = :cnt, updated_at = :upd"
        expr_values: dict[str, Any] = {
            ":cnt": new_count,
            ":upd": datetime.now(timezone.utc).isoformat(),
        }

        # If limit reached, auto-end the session
        if is_limit_reached:
            ended_at = datetime.now(timezone.utc)
            ttl = int((ended_at + timedelta(days=self.TTL_DAYS)).timestamp())
            update_expr += ", #st = :status, ended_at = :ended, #ttl = :ttl"
            expr_values[":status"] = "ended"
            expr_values[":ended"] = ended_at.isoformat()
            expr_values[":ttl"] = ttl

            self.table.update_item(
                Key={"user_id": user_id, "session_id": session_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
                ExpressionAttributeNames={"#st": "status", "#ttl": "ttl"},
            )
        else:
            self.table.update_item(
                Key={"user_id": user_id, "session_id": session_id},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
            )

        return SendMessageResponse(
            message=ai_msg,
            session_id=session_id,
            message_count=new_count,
            is_limit_reached=is_limit_reached,
        )

    def end_session(
        self,
        user_id: str,
        session_id: str,
    ) -> TutorSessionResponse:
        """Explicitly end a tutor session.

        Args:
            user_id: The user's ID.
            session_id: Target session ID.

        Returns:
            Updated TutorSessionResponse.

        Raises:
            SessionNotFoundError: If session doesn't exist.
            SessionEndedError: If session is already ended.
        """
        item = self._get_session_item(user_id, session_id)

        if item["status"] in ("ended", "timed_out"):
            raise SessionEndedError(f"Session {session_id} is already {item['status']}")

        now = datetime.now(timezone.utc)
        ttl = int((now + timedelta(days=self.TTL_DAYS)).timestamp())

        self.table.update_item(
            Key={"user_id": user_id, "session_id": session_id},
            UpdateExpression="SET #st = :status, ended_at = :ended, updated_at = :upd, #ttl = :ttl",
            ExpressionAttributeValues={
                ":status": "ended",
                ":ended": now.isoformat(),
                ":upd": now.isoformat(),
                ":ttl": ttl,
            },
            ExpressionAttributeNames={"#st": "status", "#ttl": "ttl"},
        )

        messages = self._get_session_messages(user_id, session_id, item)
        return TutorSessionResponse(
            session_id=session_id,
            deck_id=item["deck_id"],
            mode=item["mode"],
            status="ended",
            messages=messages,
            message_count=int(item.get("message_count", 0)),
            created_at=item["created_at"],
            updated_at=now.isoformat(),
            ended_at=now.isoformat(),
        )

    def list_sessions(
        self,
        user_id: str,
        status: str | None = None,
        deck_id: str | None = None,
    ) -> list[TutorSessionResponse]:
        """List sessions for a user, optionally filtered.

        Args:
            user_id: The user's ID.
            status: Optional status filter.
            deck_id: Optional deck_id filter.

        Returns:
            List of TutorSessionResponse objects.
        """
        if status:
            # Use GSI for status filtering
            response = self.table.query(
                IndexName="user_id-status-index",
                KeyConditionExpression="user_id = :uid AND #st = :status",
                ExpressionAttributeValues={
                    ":uid": user_id,
                    ":status": status,
                },
                ExpressionAttributeNames={"#st": "status"},
            )
        else:
            response = self.table.query(
                KeyConditionExpression="user_id = :uid",
                ExpressionAttributeValues={":uid": user_id},
            )

        items = response.get("Items", [])

        if deck_id:
            items = [i for i in items if i.get("deck_id") == deck_id]

        sessions = []
        for item in items:
            item = self._check_and_mark_timeout(user_id, item)
            # Skip items that no longer match the requested status filter
            if status and item["status"] != status:
                continue
            # Return empty messages for list view (per API contract)
            sessions.append(
                TutorSessionResponse(
                    session_id=item["session_id"],
                    deck_id=item["deck_id"],
                    mode=item["mode"],
                    status=item["status"],
                    messages=[],
                    message_count=int(item.get("message_count", 0)),
                    created_at=item["created_at"],
                    updated_at=item["updated_at"],
                    ended_at=item.get("ended_at"),
                )
            )

        return sessions

    def get_session(
        self,
        user_id: str,
        session_id: str,
    ) -> TutorSessionResponse:
        """Get full session details including conversation history.

        Args:
            user_id: The user's ID.
            session_id: Target session ID.

        Returns:
            TutorSessionResponse with full messages.

        Raises:
            SessionNotFoundError: If session doesn't exist.
        """
        item = self._get_session_item(user_id, session_id)
        item = self._check_and_mark_timeout(user_id, item)

        # SessionManager 経由で会話履歴を取得
        messages = self._get_session_messages(user_id, session_id, item)

        return TutorSessionResponse(
            session_id=item["session_id"],
            deck_id=item["deck_id"],
            mode=item["mode"],
            status=item["status"],
            messages=messages,
            message_count=int(item.get("message_count", 0)),
            created_at=item["created_at"],
            updated_at=item["updated_at"],
            ended_at=item.get("ended_at"),
        )

    # ---- Private helpers ----

    def _get_session_messages(
        self, user_id: str, session_id: str, item: dict
    ) -> list[TutorMessage]:
        """Get conversation messages via SessionManager.

        Uses SessionManager.initialize() to restore messages from the backing
        store, then converts from Strands format to TutorMessage format.
        Falls back to DynamoDB item's messages field on any error.

        Args:
            user_id: The user's ID.
            session_id: Target session ID.
            item: Raw DynamoDB session item (for fallback).

        Returns:
            List of TutorMessage objects.
        """
        try:
            sm = self.session_manager_factory(session_id=session_id, user_id=user_id)

            # Use a lightweight holder to receive messages from initialize()
            class _MessageHolder:
                def __init__(self):
                    self.messages: list[dict] = []

            holder = _MessageHolder()
            sm.initialize(holder)
            sm.close()

            # Convert Strands format to TutorMessage format
            messages: list[TutorMessage] = []
            for msg in holder.messages:
                content = msg.get("content", [])
                if isinstance(content, list):
                    text_parts = [
                        block["text"] for block in content if "text" in block
                    ]
                    content_str = "\n".join(text_parts)
                else:
                    content_str = str(content)
                messages.append(
                    TutorMessage(
                        role=msg["role"],
                        content=content_str,
                        related_cards=[],
                        timestamp="",
                    )
                )
            return messages
        except Exception:
            # SessionManager failure: fall back to DynamoDB messages field
            logger.warning(
                "Failed to get messages via SessionManager, falling back to DynamoDB"
            )
            return [TutorMessage(**m) for m in item.get("messages", [])]

    def _get_session_item(self, user_id: str, session_id: str) -> dict:
        """Fetch raw session item from DynamoDB."""
        response = self.table.get_item(
            Key={"user_id": user_id, "session_id": session_id}
        )
        item = response.get("Item")
        if not item:
            raise SessionNotFoundError(f"Session {session_id} not found")
        return item

    def _check_and_mark_timeout(self, user_id: str, item: dict) -> dict:
        """Check if an active session has timed out and mark it if so.

        Returns the item with updated status/timestamps if timed out.
        """
        if item["status"] != "active":
            return item
        updated_at = datetime.fromisoformat(item["updated_at"])
        now = datetime.now(timezone.utc)
        if now - updated_at > timedelta(minutes=self.TIMEOUT_MINUTES):
            self._mark_timed_out(user_id, item["session_id"])
            item["status"] = "timed_out"
            item["ended_at"] = now.isoformat()
            item["updated_at"] = now.isoformat()
        return item

    def _auto_end_active_sessions(self, user_id: str) -> None:
        """End all active sessions for the user."""
        active_sessions = self.list_sessions(user_id, status="active")
        for session in active_sessions:
            try:
                self.end_session(user_id, session.session_id)
                logger.info(
                    "Auto-ended active session",
                    extra={"session_id": session.session_id, "user_id": user_id},
                )
            except (SessionEndedError, SessionNotFoundError):
                pass  # Already ended or deleted, safe to ignore

    def _mark_timed_out(self, user_id: str, session_id: str) -> None:
        """Mark a session as timed out (idempotent)."""
        now = datetime.now(timezone.utc)
        ttl = int((now + timedelta(days=self.TTL_DAYS)).timestamp())
        try:
            self.table.update_item(
                Key={"user_id": user_id, "session_id": session_id},
                UpdateExpression="SET #st = :status, ended_at = :ended, updated_at = :upd, #ttl = :ttl",
                ConditionExpression="#st = :active",
                ExpressionAttributeValues={
                    ":status": "timed_out",
                    ":active": "active",
                    ":ended": now.isoformat(),
                    ":upd": now.isoformat(),
                    ":ttl": ttl,
                },
                ExpressionAttributeNames={"#st": "status", "#ttl": "ttl"},
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                pass  # Already marked — idempotent
            else:
                raise

    def _get_deck(self, user_id: str, deck_id: str) -> dict:
        """Fetch deck info from DynamoDB."""
        response = self.decks_table.get_item(
            Key={"user_id": user_id, "deck_id": deck_id}
        )
        item = response.get("Item")
        if not item:
            raise DeckNotFoundError(f"Deck {deck_id} not found")
        return item

    def _get_deck_cards(self, user_id: str, deck_id: str) -> list[dict]:
        """Fetch all cards for a deck from DynamoDB."""
        cards: list[dict] = []
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": "user_id = :uid",
            "FilterExpression": "deck_id = :did",
            "ExpressionAttributeValues": {
                ":uid": user_id,
                ":did": deck_id,
            },
        }

        while True:
            response = self.cards_table.query(**query_kwargs)
            for item in response.get("Items", []):
                cards.append({
                    "card_id": item.get("card_id", ""),
                    "front": item.get("front", ""),
                    "back": item.get("back", ""),
                    "ease_factor": float(item.get("ease_factor", 2.5)),
                    "repetitions": int(item.get("repetitions", 0)),
                })
            if not response.get("LastEvaluatedKey"):
                break
            query_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]

        return cards

    def _get_weak_cards_for_deck(
        self, user_id: str, deck_id: str, cards: list[dict]
    ) -> list[dict]:
        """Identify weak cards from the deck based on review history.

        Weak cards = reviewed at least once (repetitions >= 1), sorted by
        ease_factor ascending (lowest = weakest). Returns top 10.

        Returns empty list if no reviewed cards exist.
        """
        reviewed = [c for c in cards if c.get("repetitions", 0) >= 1]
        if not reviewed:
            return []
        reviewed.sort(key=lambda c: c.get("ease_factor", 2.5))
        return reviewed[:10]

    @staticmethod
    def _format_weak_cards_context(weak_cards: list[dict]) -> str:
        """Format weak card data into a context string for the system prompt."""
        lines = []
        for i, card in enumerate(weak_cards, 1):
            card_id = card.get("card_id", "")
            front = card.get("front", "")
            back = card.get("back", "")
            ease = card.get("ease_factor", 2.5)
            reps = card.get("repetitions", 0)
            lines.append(
                f"{i}. Front: {front} | Back: {back} "
                f"(id: {card_id}, ease_factor: {ease:.2f}, repetitions: {reps})"
            )
        return "\n".join(lines)

"""TutorService — Session management for AI Tutor feature.

Handles session lifecycle: start, send_message, end, list, get.
Includes auto-end of existing active sessions, timeout checks,
message limit enforcement, and TTL calculation.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from models.tutor import (
    SendMessageResponse,
    TutorMessage,
    TutorSessionResponse,
)
from services.prompts.tutor import format_cards_context, get_system_prompt
from services.tutor_ai_service import clean_response_text, create_tutor_ai_service
from services.tutor_session_factory import create_tutor_session_manager
from utils.dynamodb_client import get_dynamodb_resource

logger = Logger()


def _close_quietly(sm: Any) -> None:
    """Close a SessionManager, logging (not raising) any error.

    Calling sm.close() inside a try/finally can mask the body's original
    exception if close() itself raises (#15). DynamoDBSessionManager.close is a
    no-op today, but AgentCore-backed managers may raise real errors. This helper
    swallows close errors (after logging) so the body exception always propagates.
    """
    try:
        sm.close()
    except Exception as exc:  # noqa: BLE001 - intentional: must not mask body error
        logger.warning(
            "SessionManager.close() raised; suppressing to preserve body exception",
            extra={"error": str(exc)},
        )


# Exceptions
class TutorServiceError(Exception):
    """Base exception for TutorService errors."""


class SessionNotFoundError(TutorServiceError):
    """Raised when a session cannot be found."""


class SessionEndedError(TutorServiceError):
    """Raised when trying to interact with an ended/timed_out session."""


class MessageLimitError(TutorServiceError):
    """Raised when session message limit is reached."""


class ConcurrentSendError(TutorServiceError):
    """Raised when concurrent send_message is detected (optimistic lock failed)."""


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

    # send_message の in-flight ロック上限。Lambda タイムアウト + バッファ。
    # この時間を超えた processing 状態は stale とみなし、新しい送信が引き継げる。
    LOCK_TIMEOUT_SECONDS = int(os.environ.get("TUTOR_LOCK_TIMEOUT_SECONDS", "150"))

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

        self.dynamodb = get_dynamodb_resource(dynamodb_resource)

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
            try:
                greeting_content, related_cards = self.ai_service.generate_response(
                    system_prompt=system_prompt,
                    messages="セッションを開始してください。デッキの内容を要約して挨拶してください。",
                    session_manager=sm,
                )
            except Exception:
                # Rollback: remove the incomplete session to avoid orphaned records
                try:
                    self.table.delete_item(
                        Key={"user_id": user_id, "session_id": session_id}
                    )
                except Exception:
                    logger.warning(
                        "Failed to cleanup session after AI error",
                        extra={"session_id": session_id},
                    )
                raise

            # Validate related_cards against deck's card IDs
            related_cards = [cid for cid in related_cards if cid in valid_card_ids]

            # Persist validated related_cards onto the greeting message that the
            # SessionManager just stored (#10). Strands' append path always writes
            # related_cards=[], so we patch the DynamoDB messages field here so that
            # history restoration returns the IDs instead of losing them.
            self._persist_related_cards(sm, related_cards)
        finally:
            _close_quietly(sm)

        greeting_content = self.ai_service.clean_response_text(greeting_content)

        greeting_msg = TutorMessage(
            role="assistant",
            content=greeting_content,
            related_cards=related_cards,
            timestamp=now,
        )

        return TutorSessionResponse(
            session_id=session_id,
            deck_id=deck_id,
            mode=mode,  # type: ignore[arg-type]
            status="active",
            messages=[greeting_msg],
            message_count=0,
            created_at=now,
            updated_at=now,
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
            ConcurrentSendError: If a concurrent send is detected (optimistic lock failed).
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

        # In-flight lock: processing_started_at の属性存在で in-flight 状態を表す。
        # AI 呼び出し中に到着した後続の send_message は ConditionExpression で弾く
        # (Bedrock 二重呼び出しと履歴破壊を防ぐ)。
        # message_count だけの楽観ロックでは「先行が count を進めた後に到着した
        # リクエスト」を弾けないため、in-flight 排他制御が必要。
        now = datetime.now(timezone.utc)
        stale_threshold = (
            now - timedelta(seconds=self.LOCK_TIMEOUT_SECONDS)
        ).isoformat()
        try:
            self.table.update_item(
                Key={"user_id": user_id, "session_id": session_id},
                UpdateExpression=(
                    "SET processing_started_at = :now, updated_at = :now"
                ),
                # status が active で、かつロックが取れていない or stale の場合のみ取得
                ConditionExpression=(
                    "#st = :active "
                    "AND (attribute_not_exists(processing_started_at) "
                    "OR processing_started_at < :stale)"
                ),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":active": "active",
                    ":now": now.isoformat(),
                    ":stale": stale_threshold,
                },
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                logger.warning(
                    "Concurrent send detected (in-flight lock held)",
                    extra={
                        "user_id": user_id,
                        "session_id": session_id,
                    },
                )
                raise ConcurrentSendError(
                    f"Session {session_id} has an in-flight send in progress"
                ) from e
            raise

        # Get AI response via SessionManager
        system_prompt = item.get("system_prompt", "")
        deck_card_ids = set(item.get("deck_card_ids", []))
        try:
            sm = self.session_manager_factory(session_id=session_id, user_id=user_id)
            try:
                ai_content, related_cards = self.ai_service.generate_response(
                    system_prompt=system_prompt,
                    messages=content,
                    session_manager=sm,
                )

                # Validate related_cards against deck's card IDs
                if deck_card_ids:
                    related_cards = [
                        cid for cid in related_cards if cid in deck_card_ids
                    ]

                # Persist validated related_cards onto the assistant message that
                # the SessionManager just stored (#10). Strands' append path always
                # writes related_cards=[], so we patch the DynamoDB messages field
                # here to survive history restoration.
                self._persist_related_cards(sm, related_cards)
            finally:
                _close_quietly(sm)
        except Exception:
            # AI error: ロックを解放する (count は進めない)。
            # 解放に失敗しても LOCK_TIMEOUT_SECONDS 後には他の送信が引き継げる。
            try:
                self.table.update_item(
                    Key={"user_id": user_id, "session_id": session_id},
                    UpdateExpression="REMOVE processing_started_at",
                    ConditionExpression="attribute_exists(processing_started_at)",
                )
            except ClientError as rb_err:
                logger.warning(
                    "Failed to release in-flight lock after AI error",
                    extra={
                        "user_id": user_id,
                        "session_id": session_id,
                        "error": str(rb_err),
                    },
                )
            raise

        ai_content = self.ai_service.clean_response_text(ai_content)

        new_count = current_count + 1
        is_limit_reached = new_count >= self.MAX_ROUNDS

        ai_msg = TutorMessage(
            role="assistant",
            content=ai_content,
            related_cards=related_cards,
            timestamp=datetime.now(timezone.utc),
        )

        # AI 成功後: ロック解放 (REMOVE processing_started_at) + count++ を
        # 同一 update_item で行う。limit reached なら session を ended に遷移。
        completion_now = datetime.now(timezone.utc)
        if is_limit_reached:
            ttl = int(
                (completion_now + timedelta(days=self.TTL_DAYS)).timestamp()
            )
            self.table.update_item(
                Key={"user_id": user_id, "session_id": session_id},
                UpdateExpression=(
                    "SET message_count = :cnt, "
                    "#st = :ended, "
                    "ended_at = :ended_at, "
                    "#ttl = :ttl, "
                    "updated_at = :upd "
                    "REMOVE processing_started_at"
                ),
                ConditionExpression="attribute_exists(processing_started_at)",
                ExpressionAttributeValues={
                    ":cnt": new_count,
                    ":ended": "ended",
                    ":ended_at": completion_now.isoformat(),
                    ":ttl": ttl,
                    ":upd": completion_now.isoformat(),
                },
                ExpressionAttributeNames={"#st": "status", "#ttl": "ttl"},
            )
        else:
            self.table.update_item(
                Key={"user_id": user_id, "session_id": session_id},
                UpdateExpression=(
                    "SET message_count = :cnt, "
                    "updated_at = :upd "
                    "REMOVE processing_started_at"
                ),
                ConditionExpression="attribute_exists(processing_started_at)",
                ExpressionAttributeValues={
                    ":cnt": new_count,
                    ":upd": completion_now.isoformat(),
                },
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
            updated_at=now,
            ended_at=now,
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

    def _persist_related_cards(self, sm: Any, related_cards: list[str]) -> None:
        """Persist validated related_cards onto the last stored message (#10).

        Only DynamoDB-backed SessionManagers expose
        update_last_message_related_cards. For other backends (e.g. AgentCore)
        the Strands/AgentCore session store has no related_cards concept, so this
        is skipped — the API response still carries related_cards, but they are
        not restored from history for those backends. Failures here must not break
        the request, so any error is logged and swallowed.
        """
        updater = getattr(sm, "update_last_message_related_cards", None)
        if not callable(updater):
            return
        try:
            updater(related_cards)
        except Exception as exc:  # noqa: BLE001 - persistence is best-effort
            logger.warning(
                "Failed to persist related_cards to session history",
                extra={"error": str(exc)},
            )

    def _get_session_messages(
        self, user_id: str, session_id: str, item: dict
    ) -> list[TutorMessage]:
        """Get conversation messages via SessionManager.

        Uses SessionManager.read_messages() (DynamoDB backend) or
        initialize() (other backends) to restore messages, then converts
        to TutorMessage format with clean_response_text applied.
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
            try:
                if hasattr(sm, "read_messages") and callable(sm.read_messages):
                    # DynamoDB backend: read raw messages preserving metadata
                    raw_messages = sm.read_messages()
                    messages: list[TutorMessage] = []
                    for msg in raw_messages:
                        content_str = clean_response_text(
                            msg.get("content", "")
                        )
                        messages.append(
                            TutorMessage(
                                role=msg["role"],
                                content=content_str,
                                related_cards=msg.get("related_cards", []),
                                timestamp=msg.get("timestamp", ""),
                            )
                        )
                    return messages

                # Other backends: use initialize() with lightweight holder
                class _Holder:
                    def __init__(self):
                        self.messages: list[dict] = []

                holder = _Holder()
                sm.initialize(holder)

                messages = []
                for msg in holder.messages:
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        text_parts = [
                            block["text"]
                            for block in content
                            if "text" in block
                        ]
                        content_str = "\n".join(text_parts)
                    else:
                        content_str = str(content)
                    content_str = clean_response_text(content_str)
                    # AgentCore 復元メッセージは元の timestamp を保持していないため
                    # epoch をセンチネルとして使う。従来の timestamp="" は Pydantic の
                    # ValidationError で常に except 節へフォールバックしており、
                    # SessionManager からの復元が実質機能していなかった (mypy で検出)。
                    messages.append(
                        TutorMessage(
                            role=msg["role"],
                            content=content_str,
                            related_cards=[],
                            timestamp=datetime.fromtimestamp(0, tz=timezone.utc),
                        )
                    )
                return messages
            finally:
                _close_quietly(sm)
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

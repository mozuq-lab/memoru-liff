"""TutorSessionRepository — DynamoDB persistence for the AI Tutor feature.

TutorService からセッション/デッキ/カードテーブルへの DynamoDB アクセスと
低レベルなエラー変換（ConditionalCheckFailed → ConcurrentSendError 等）を分離した永続化層。
セッションライフサイクル・AI 呼び出し・SessionManager の扱いは TutorService に残す。
"""

import os
from typing import Any

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from services.tutor_errors import (
    ConcurrentSendError,
    DeckNotFoundError,
    SessionNotFoundError,
)
from utils.dynamodb_client import get_dynamodb_resource

logger = Logger()


class TutorSessionRepository:
    """Tutor セッションの永続化層: DynamoDB アクセスを担う。"""

    def __init__(
        self,
        table_name: str | None = None,
        dynamodb_resource: Any | None = None,
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

    # ---- Session item access ----

    def get_session_item(self, user_id: str, session_id: str) -> dict:
        """Fetch raw session item from DynamoDB.

        Raises:
            SessionNotFoundError: If the session does not exist.
        """
        response = self.table.get_item(
            Key={"user_id": user_id, "session_id": session_id}
        )
        item = response.get("Item")
        if not item:
            raise SessionNotFoundError(f"Session {session_id} not found")
        return item

    def put_session(self, item: dict) -> None:
        """Persist a session item (full replace)."""
        self.table.put_item(Item=item)

    def delete_session(self, user_id: str, session_id: str) -> None:
        """Delete a session item by key (raw; caller handles best-effort semantics)."""
        self.table.delete_item(Key={"user_id": user_id, "session_id": session_id})

    def query_sessions(self, user_id: str, status: str | None = None) -> list[dict]:
        """Query a user's sessions, optionally filtered by status via GSI."""
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
        return response.get("Items", [])

    # ---- In-flight lock ----

    def acquire_inflight_lock(
        self, user_id: str, session_id: str, now_iso: str, stale_threshold: str
    ) -> None:
        """Acquire the send_message in-flight lock via a conditional update.

        status が active で、かつロック未取得または stale の場合のみ取得する。
        Bedrock 二重呼び出しと履歴破壊を防ぐ。

        Raises:
            ConcurrentSendError: If another send holds a fresh in-flight lock.
        """
        try:
            self.table.update_item(
                Key={"user_id": user_id, "session_id": session_id},
                UpdateExpression="SET processing_started_at = :now, updated_at = :now",
                ConditionExpression=(
                    "#st = :active "
                    "AND (attribute_not_exists(processing_started_at) "
                    "OR processing_started_at < :stale)"
                ),
                ExpressionAttributeNames={"#st": "status"},
                ExpressionAttributeValues={
                    ":active": "active",
                    ":now": now_iso,
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

    def release_inflight_lock(self, user_id: str, session_id: str) -> None:
        """Release the in-flight lock (best-effort).

        解放に失敗してもロックは LOCK_TIMEOUT 後に stale 化するため、例外は送出せずログのみ。
        """
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

    def complete_send(
        self,
        user_id: str,
        session_id: str,
        new_count: int,
        completion_iso: str,
        ttl: int | None = None,
    ) -> None:
        """Finalize a successful send: bump message_count and release the lock.

        AI 成功後にロック解放 (REMOVE processing_started_at) と count++ を同一 update_item で行う。
        ``ttl`` が与えられた場合 (limit reached) は session を ended に遷移させる。
        """
        if ttl is not None:
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
                    ":ended_at": completion_iso,
                    ":ttl": ttl,
                    ":upd": completion_iso,
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
                    ":upd": completion_iso,
                },
            )

    # ---- Status transitions ----

    def mark_ended(self, user_id: str, session_id: str, now_iso: str, ttl: int) -> None:
        """Mark a session as ended with TTL."""
        self.table.update_item(
            Key={"user_id": user_id, "session_id": session_id},
            UpdateExpression="SET #st = :status, ended_at = :ended, updated_at = :upd, #ttl = :ttl",
            ExpressionAttributeValues={
                ":status": "ended",
                ":ended": now_iso,
                ":upd": now_iso,
                ":ttl": ttl,
            },
            ExpressionAttributeNames={"#st": "status", "#ttl": "ttl"},
        )

    def mark_timed_out(self, user_id: str, session_id: str, now_iso: str, ttl: int) -> None:
        """Mark a session as timed out (idempotent).

        既に active でない場合 (ConditionalCheckFailed) は冪等に無視する。
        """
        try:
            self.table.update_item(
                Key={"user_id": user_id, "session_id": session_id},
                UpdateExpression="SET #st = :status, ended_at = :ended, updated_at = :upd, #ttl = :ttl",
                ConditionExpression="#st = :active",
                ExpressionAttributeValues={
                    ":status": "timed_out",
                    ":active": "active",
                    ":ended": now_iso,
                    ":upd": now_iso,
                    ":ttl": ttl,
                },
                ExpressionAttributeNames={"#st": "status", "#ttl": "ttl"},
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                pass  # Already marked — idempotent
            else:
                raise

    # ---- Deck / card reads ----

    def get_deck(self, user_id: str, deck_id: str) -> dict:
        """Fetch deck info from DynamoDB.

        Raises:
            DeckNotFoundError: If the deck does not exist.
        """
        response = self.decks_table.get_item(
            Key={"user_id": user_id, "deck_id": deck_id}
        )
        item = response.get("Item")
        if not item:
            raise DeckNotFoundError(f"Deck {deck_id} not found")
        return item

    def get_deck_cards(self, user_id: str, deck_id: str) -> list[dict]:
        """Fetch all cards for a deck from DynamoDB (paginated)."""
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

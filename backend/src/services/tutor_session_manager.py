"""DynamoDBSessionManager — DynamoDB-based SessionManager for Strands SDK.

Implements the Strands SDK SessionManager interface using DynamoDB as the
backing store. Reads and writes conversation history to the existing
tutor_sessions table's 'messages' field.

Handles bidirectional format conversion between:
- Strands format: {"role": "...", "content": [{"text": "..."}]}
- DynamoDB format: {"role": "...", "content": "...", "timestamp": "...", "related_cards": [...]}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError
from strands.session import SessionManager
from strands.types.content import Message

from utils.dynamodb_client import get_dynamodb_resource

logger = Logger()


class DynamoDBSessionManager(SessionManager):
    """DynamoDB-based SessionManager implementation.

    Conforms to the Strands SDK SessionManager interface and manages
    conversation history via the existing tutor_sessions DynamoDB table.

    Attributes:
        table_name: DynamoDB table name.
        session_id: Session ID.
        user_id: User ID (partition key).
    """

    def __init__(
        self,
        table_name: str,
        session_id: str,
        user_id: str,
        dynamodb_resource: Any | None = None,
    ) -> None:
        """Initialize DynamoDBSessionManager.

        Args:
            table_name: DynamoDB table name.
            session_id: Session ID.
            user_id: User ID (partition key).
            dynamodb_resource: Optional DynamoDB resource for testing.
        """
        super().__init__()
        self.table_name = table_name
        self.session_id = session_id
        self.user_id = user_id

        self.dynamodb = get_dynamodb_resource(dynamodb_resource)

        self.table = self.dynamodb.Table(self.table_name)

    def initialize(self, agent: Any, session_id: str | None = None, **kwargs: Any) -> None:
        """Initialize session and restore conversation history to Agent.

        Reads messages from DynamoDB and sets them on Agent.messages
        in Strands format.

        Args:
            agent: Strands Agent instance.
            session_id: Optional session ID override. Uses constructor value if None.
        """
        sid = session_id if session_id is not None else self.session_id

        response = self.table.get_item(
            Key={"user_id": self.user_id, "session_id": sid}
        )
        item = response.get("Item")
        if not item:
            agent.messages = []
            return

        dynamo_messages = item.get("messages", [])
        agent.messages = [
            self._dynamo_to_strands_message(msg) for msg in dynamo_messages
        ]

    def append_message(self, message: Message, agent: Any, **kwargs: Any) -> None:
        """Append a message to conversation history in DynamoDB.

        Converts from Strands format to DynamoDB format before storing.

        Args:
            message: Strands-format message {"role": "...", "content": [...]}.
            agent: Strands Agent instance.
        """
        dynamo_msg = self._strands_to_dynamo_message(message)

        self.table.update_item(
            Key={"user_id": self.user_id, "session_id": self.session_id},
            UpdateExpression="SET messages = list_append(if_not_exists(messages, :empty), :msg)",
            ExpressionAttributeValues={
                ":msg": [dynamo_msg],
                ":empty": [],
            },
        )

    def sync_agent(self, agent: Any, **kwargs: Any) -> None:
        """Sync all Agent.messages to DynamoDB.

        Converts all messages from Strands format to DynamoDB format
        and overwrites the messages field.

        Args:
            agent: Strands Agent instance.
        """
        dynamo_messages = [
            self._strands_to_dynamo_message(msg) for msg in agent.messages
        ]

        self.table.update_item(
            Key={"user_id": self.user_id, "session_id": self.session_id},
            UpdateExpression="SET messages = :msgs",
            ExpressionAttributeValues={":msgs": dynamo_messages},
        )

    def redact_latest_message(
        self, redact_message: Message, agent: Any, **kwargs: Any
    ) -> None:
        """Replace the most recently stored message with redacted content.

        Strands SessionManager の抽象メソッド。ガードレール等で直近メッセージが
        redact された際に呼ばれるため、DynamoDB 'messages' の末尾要素を redact 後の
        内容で上書きし、履歴復元時に redact 済みの内容が返るようにする。

        Args:
            redact_message: redact 後の Strands 形式メッセージ。
            agent: Strands Agent インスタンス。
            **kwargs: 将来拡張用。
        """
        dynamo_msg = self._strands_to_dynamo_message(redact_message)

        response = self.table.get_item(
            Key={"user_id": self.user_id, "session_id": self.session_id}
        )
        item = response.get("Item")
        messages = item.get("messages", []) if item else []
        if not messages:
            return

        last_index = len(messages) - 1
        self.table.update_item(
            Key={"user_id": self.user_id, "session_id": self.session_id},
            UpdateExpression=f"SET messages[{last_index}] = :msg",
            ExpressionAttributeValues={":msg": dynamo_msg},
        )

    def close(self) -> None:
        """Close the session manager (no-op for DynamoDB)."""
        pass

    def __enter__(self) -> "DynamoDBSessionManager":
        """Context Manager: enter."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context Manager: exit."""
        self.close()

    def update_last_message_related_cards(self, related_cards: list[str]) -> bool:
        """Persist related_cards onto the most recent stored message.

        The Strands SessionManager path (append_message/sync_agent) has no concept
        of related_cards, so it always stores them as an empty list (#10). After the
        Agent has written the assistant turn, TutorService calls this to attach the
        validated related_cards to the last message in the DynamoDB 'messages' field,
        so that history restoration (read_messages) returns them instead of always [].

        Scope: only the DynamoDB-backed messages field (the fallback/read source for
        get_session/end_session) is updated. AgentCore/Strands internal session
        storage is unaffected and has no related_cards concept.

        Args:
            related_cards: Validated related card IDs to store on the last message.

        Returns:
            True if a message was updated, False if there were no messages to update.
        """
        if not related_cards:
            # Nothing to persist; default stored value is already [].
            return False

        response = self.table.get_item(
            Key={"user_id": self.user_id, "session_id": self.session_id}
        )
        item = response.get("Item")
        if not item:
            return False
        messages = item.get("messages", [])
        if not messages:
            return False

        # M-16: GetItem で求めた last_index と UpdateItem の間に別の
        # append_message が割り込むと、誤ったインデックスのメッセージに
        # related_cards を書き込んでしまう (TOCTOU)。ConditionExpression で
        # 「last_index の次の要素が存在しない (= 末尾のまま)」ことを保証し、
        # メッセージが追加されていた場合は静かに書き込みをスキップする。
        last_index = len(messages) - 1
        next_index = last_index + 1
        try:
            self.table.update_item(
                Key={"user_id": self.user_id, "session_id": self.session_id},
                UpdateExpression=f"SET messages[{last_index}].related_cards = :rc",
                ConditionExpression=f"attribute_not_exists(messages[{next_index}])",
                ExpressionAttributeValues={":rc": related_cards},
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                # 別の append_message が割り込んで末尾位置がずれた。
                # 誤ったメッセージへの書き込みを避けるためスキップする。
                logger.warning(
                    "Skipped related_cards persistence: message list changed "
                    "between read and write (concurrent append)",
                    extra={
                        "user_id": self.user_id,
                        "session_id": self.session_id,
                    },
                )
                return False
            raise
        return True

    def read_messages(self) -> list[dict]:
        """Read raw DynamoDB-format messages for this session.

        Returns messages directly from DynamoDB without Strands format conversion.
        Each message dict contains: role, content, timestamp, related_cards.

        Returns:
            List of DynamoDB-format message dicts.
        """
        response = self.table.get_item(
            Key={"user_id": self.user_id, "session_id": self.session_id}
        )
        item = response.get("Item")
        if not item:
            return []
        return item.get("messages", [])

    # ---- Format conversion helpers ----

    @staticmethod
    def _dynamo_to_strands_message(dynamo_msg: dict) -> dict:
        """Convert a DynamoDB-format message to Strands format.

        DynamoDB: {"role": "user", "content": "hello", "timestamp": "...", ...}
        Strands:  {"role": "user", "content": [{"text": "hello"}]}

        Args:
            dynamo_msg: DynamoDB-format message dict.

        Returns:
            Strands-format message dict.
        """
        return {
            "role": dynamo_msg["role"],
            "content": [{"text": dynamo_msg["content"]}],
        }

    @staticmethod
    def _strands_to_dynamo_message(strands_msg: Message) -> dict:
        """Convert a Strands-format message to DynamoDB format.

        Strands:  {"role": "user", "content": [{"text": "hello"}]}
        DynamoDB: {"role": "user", "content": "hello", "timestamp": "...", "related_cards": []}

        Args:
            strands_msg: Strands-format message dict.

        Returns:
            DynamoDB-format message dict.
        """
        content_parts = strands_msg.get("content", [])
        text_parts = [
            block["text"] for block in content_parts if "text" in block
        ]
        content_str = "\n".join(text_parts)

        return {
            "role": strands_msg["role"],
            "content": content_str,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "related_cards": [],
        }

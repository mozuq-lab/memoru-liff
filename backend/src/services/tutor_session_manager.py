"""DynamoDBSessionManager — DynamoDB-based SessionManager for Strands SDK.

Implements the Strands SDK SessionManager interface using DynamoDB as the
backing store. Reads and writes conversation history to the existing
tutor_sessions table's 'messages' field.

Handles bidirectional format conversion between:
- Strands format: {"role": "...", "content": [{"text": "..."}]}
- DynamoDB format: {"role": "...", "content": "...", "timestamp": "...", "related_cards": [...]}
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import boto3
from aws_lambda_powertools import Logger

logger = Logger()


class DynamoDBSessionManager:
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
        self.table_name = table_name
        self.session_id = session_id
        self.user_id = user_id

        if dynamodb_resource:
            self.dynamodb = dynamodb_resource
        else:
            endpoint_url = os.environ.get("DYNAMODB_ENDPOINT_URL") or os.environ.get(
                "AWS_ENDPOINT_URL"
            )
            if endpoint_url:
                self.dynamodb = boto3.resource("dynamodb", endpoint_url=endpoint_url)
            else:
                self.dynamodb = boto3.resource("dynamodb")

        self.table = self.dynamodb.Table(self.table_name)

    def initialize(self, agent: Any, session_id: str | None = None) -> None:
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

    def append_message(self, message: dict, agent: Any) -> None:
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

    def sync_agent(self, agent: Any) -> None:
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

    def close(self) -> None:
        """Close the session manager (no-op for DynamoDB)."""
        pass

    def __enter__(self) -> "DynamoDBSessionManager":
        """Context Manager: enter."""
        return self

    def __exit__(self, *args: Any) -> None:
        """Context Manager: exit."""
        self.close()

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
    def _strands_to_dynamo_message(strands_msg: dict) -> dict:
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

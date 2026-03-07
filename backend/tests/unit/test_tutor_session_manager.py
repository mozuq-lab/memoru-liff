"""Unit tests for DynamoDBSessionManager.

Tests DynamoDB-based SessionManager that implements the Strands SDK
SessionManager interface for managing conversation history.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


# ===================================================================
# Helpers
# ===================================================================


def _make_mock_table(item=None):
    """Create a mock DynamoDB table with optional get_item response."""
    table = MagicMock()
    if item is not None:
        table.get_item.return_value = {"Item": item}
    else:
        # No item found
        table.get_item.return_value = {}
    return table


def _make_mock_dynamodb(table):
    """Create a mock DynamoDB resource returning the given table."""
    dynamodb = MagicMock()
    dynamodb.Table.return_value = table
    return dynamodb


def _make_mock_agent(messages=None):
    """Create a mock Strands Agent with a messages attribute."""
    agent = MagicMock()
    agent.messages = messages if messages is not None else []
    return agent


def _make_dynamo_message(role, content, timestamp=None, related_cards=None):
    """Create a DynamoDB-format message dict."""
    return {
        "role": role,
        "content": content,
        "timestamp": timestamp or datetime.now(timezone.utc).isoformat(),
        "related_cards": related_cards or [],
    }


def _make_strands_message(role, content):
    """Create a Strands-format message dict."""
    return {
        "role": role,
        "content": [{"text": content}],
    }


# ===================================================================
# Message format conversion tests
# ===================================================================


class TestMessageFormatConversion:
    """Tests for Strands <-> DynamoDB message format conversion."""

    def test_dynamo_to_strands_converts_string_content_to_list(self):
        """DynamoDB string content should become [{"text": ...}] for Strands."""
        from services.tutor_session_manager import DynamoDBSessionManager

        result = DynamoDBSessionManager._dynamo_to_strands_message(
            _make_dynamo_message("user", "hello")
        )
        assert result == {"role": "user", "content": [{"text": "hello"}]}

    def test_dynamo_to_strands_preserves_role(self):
        """Role should be preserved in conversion."""
        from services.tutor_session_manager import DynamoDBSessionManager

        result = DynamoDBSessionManager._dynamo_to_strands_message(
            _make_dynamo_message("assistant", "response")
        )
        assert result["role"] == "assistant"

    def test_strands_to_dynamo_extracts_text_from_content_list(self):
        """Strands content list should be flattened to string for DynamoDB."""
        from services.tutor_session_manager import DynamoDBSessionManager

        result = DynamoDBSessionManager._strands_to_dynamo_message(
            _make_strands_message("user", "hello")
        )
        assert result["role"] == "user"
        assert result["content"] == "hello"
        assert "timestamp" in result
        assert "related_cards" in result

    def test_strands_to_dynamo_handles_multiple_text_blocks(self):
        """Multiple text blocks should be joined."""
        from services.tutor_session_manager import DynamoDBSessionManager

        message = {
            "role": "assistant",
            "content": [{"text": "part1"}, {"text": "part2"}],
        }
        result = DynamoDBSessionManager._strands_to_dynamo_message(message)
        assert result["content"] == "part1\npart2"

    def test_strands_to_dynamo_handles_empty_content_list(self):
        """Empty content list should result in empty string."""
        from services.tutor_session_manager import DynamoDBSessionManager

        message = {"role": "user", "content": []}
        result = DynamoDBSessionManager._strands_to_dynamo_message(message)
        assert result["content"] == ""

    def test_strands_to_dynamo_skips_non_text_content(self):
        """Non-text content blocks (e.g., toolUse) should be skipped."""
        from services.tutor_session_manager import DynamoDBSessionManager

        message = {
            "role": "assistant",
            "content": [
                {"text": "hello"},
                {"toolUse": {"name": "some_tool"}},
                {"text": "world"},
            ],
        }
        result = DynamoDBSessionManager._strands_to_dynamo_message(message)
        assert result["content"] == "hello\nworld"


# ===================================================================
# Initialize tests
# ===================================================================


class TestInitialize:
    """Tests for DynamoDBSessionManager.initialize."""

    def test_initialize_new_session_empty_messages(self):
        """New session with no messages should leave Agent.messages empty."""
        from services.tutor_session_manager import DynamoDBSessionManager

        table = _make_mock_table(item={
            "user_id": "user1",
            "session_id": "sess1",
            "messages": [],
        })
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="test-table",
            session_id="sess1",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )
        agent = _make_mock_agent()
        sm.initialize(agent)

        assert agent.messages == []

    def test_initialize_restores_existing_messages(self):
        """Existing messages should be converted to Strands format and set on Agent."""
        from services.tutor_session_manager import DynamoDBSessionManager

        dynamo_messages = [
            _make_dynamo_message("user", "hello"),
            _make_dynamo_message("assistant", "hi there"),
        ]
        table = _make_mock_table(item={
            "user_id": "user1",
            "session_id": "sess1",
            "messages": dynamo_messages,
        })
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="test-table",
            session_id="sess1",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )
        agent = _make_mock_agent()
        sm.initialize(agent)

        assert len(agent.messages) == 2
        assert agent.messages[0] == {"role": "user", "content": [{"text": "hello"}]}
        assert agent.messages[1] == {"role": "assistant", "content": [{"text": "hi there"}]}

    def test_initialize_no_item_in_dynamodb(self):
        """If session item does not exist in DynamoDB, Agent.messages stays empty."""
        from services.tutor_session_manager import DynamoDBSessionManager

        table = _make_mock_table(item=None)  # No item
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="test-table",
            session_id="nonexistent",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )
        agent = _make_mock_agent()
        sm.initialize(agent)

        assert agent.messages == []

    def test_initialize_uses_constructor_session_id(self):
        """initialize should use constructor's session_id for get_item key."""
        from services.tutor_session_manager import DynamoDBSessionManager

        table = _make_mock_table(item={
            "user_id": "user1",
            "session_id": "sess1",
            "messages": [],
        })
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="test-table",
            session_id="sess1",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )
        agent = _make_mock_agent()
        sm.initialize(agent)

        table.get_item.assert_called_once_with(
            Key={"user_id": "user1", "session_id": "sess1"}
        )

    def test_initialize_with_session_id_override(self):
        """When session_id is passed to initialize, it should override constructor value."""
        from services.tutor_session_manager import DynamoDBSessionManager

        table = _make_mock_table(item={
            "user_id": "user1",
            "session_id": "override_sess",
            "messages": [],
        })
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="test-table",
            session_id="original_sess",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )
        agent = _make_mock_agent()
        sm.initialize(agent, session_id="override_sess")

        table.get_item.assert_called_once_with(
            Key={"user_id": "user1", "session_id": "override_sess"}
        )

    def test_initialize_item_without_messages_key(self):
        """If item exists but has no 'messages' key, Agent.messages stays empty."""
        from services.tutor_session_manager import DynamoDBSessionManager

        table = _make_mock_table(item={
            "user_id": "user1",
            "session_id": "sess1",
        })
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="test-table",
            session_id="sess1",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )
        agent = _make_mock_agent()
        sm.initialize(agent)

        assert agent.messages == []


# ===================================================================
# append_message tests
# ===================================================================


class TestAppendMessage:
    """Tests for DynamoDBSessionManager.append_message."""

    def test_append_message_updates_dynamodb(self):
        """append_message should call update_item to add message to DynamoDB."""
        from services.tutor_session_manager import DynamoDBSessionManager

        table = _make_mock_table()
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="test-table",
            session_id="sess1",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )
        agent = _make_mock_agent()

        strands_message = _make_strands_message("user", "hello")
        sm.append_message(strands_message, agent)

        table.update_item.assert_called_once()
        call_kwargs = table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"user_id": "user1", "session_id": "sess1"}
        assert "SET messages = list_append" in call_kwargs["UpdateExpression"]

    def test_append_message_converts_strands_to_dynamo_format(self):
        """Message should be converted from Strands to DynamoDB format before storage."""
        from services.tutor_session_manager import DynamoDBSessionManager

        table = _make_mock_table()
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="test-table",
            session_id="sess1",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )
        agent = _make_mock_agent()

        strands_message = _make_strands_message("user", "hello")
        sm.append_message(strands_message, agent)

        call_kwargs = table.update_item.call_args[1]
        dynamo_msg = call_kwargs["ExpressionAttributeValues"][":msg"][0]
        assert dynamo_msg["role"] == "user"
        assert dynamo_msg["content"] == "hello"
        assert "timestamp" in dynamo_msg

    def test_append_message_initializes_list_if_not_exists(self):
        """update_item should handle case where messages list doesn't exist yet."""
        from services.tutor_session_manager import DynamoDBSessionManager

        table = _make_mock_table()
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="test-table",
            session_id="sess1",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )
        agent = _make_mock_agent()

        strands_message = _make_strands_message("assistant", "reply")
        sm.append_message(strands_message, agent)

        # Verify update_item was called (list_append handles the append)
        table.update_item.assert_called_once()


# ===================================================================
# sync_agent tests
# ===================================================================


class TestSyncAgent:
    """Tests for DynamoDBSessionManager.sync_agent."""

    def test_sync_agent_writes_all_messages_to_dynamodb(self):
        """sync_agent should write all Agent.messages to DynamoDB."""
        from services.tutor_session_manager import DynamoDBSessionManager

        table = _make_mock_table()
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="test-table",
            session_id="sess1",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )

        agent = _make_mock_agent(messages=[
            _make_strands_message("user", "hello"),
            _make_strands_message("assistant", "hi there"),
        ])

        sm.sync_agent(agent)

        table.update_item.assert_called_once()
        call_kwargs = table.update_item.call_args[1]
        assert call_kwargs["Key"] == {"user_id": "user1", "session_id": "sess1"}
        dynamo_messages = call_kwargs["ExpressionAttributeValues"][":msgs"]
        assert len(dynamo_messages) == 2
        assert dynamo_messages[0]["content"] == "hello"
        assert dynamo_messages[1]["content"] == "hi there"

    def test_sync_agent_with_empty_messages(self):
        """sync_agent with empty Agent.messages should write empty list."""
        from services.tutor_session_manager import DynamoDBSessionManager

        table = _make_mock_table()
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="test-table",
            session_id="sess1",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )
        agent = _make_mock_agent(messages=[])
        sm.sync_agent(agent)

        call_kwargs = table.update_item.call_args[1]
        dynamo_messages = call_kwargs["ExpressionAttributeValues"][":msgs"]
        assert dynamo_messages == []


# ===================================================================
# close tests
# ===================================================================


class TestClose:
    """Tests for DynamoDBSessionManager.close."""

    def test_close_is_noop(self):
        """close() should succeed without raising exceptions (no-op for DynamoDB)."""
        from services.tutor_session_manager import DynamoDBSessionManager

        table = _make_mock_table()
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="test-table",
            session_id="sess1",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )
        # Should not raise
        sm.close()


# ===================================================================
# Context Manager tests
# ===================================================================


class TestContextManager:
    """Tests for DynamoDBSessionManager as context manager."""

    def test_context_manager_enter_returns_self(self):
        """__enter__ should return the session manager instance."""
        from services.tutor_session_manager import DynamoDBSessionManager

        table = _make_mock_table()
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="test-table",
            session_id="sess1",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )
        with sm as ctx:
            assert ctx is sm

    def test_context_manager_calls_close_on_exit(self):
        """__exit__ should call close()."""
        from services.tutor_session_manager import DynamoDBSessionManager

        table = _make_mock_table()
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="test-table",
            session_id="sess1",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )
        with patch.object(sm, "close") as mock_close:
            with sm:
                pass
            mock_close.assert_called_once()


# ===================================================================
# Constructor / DynamoDB connection tests
# ===================================================================


class TestConstructor:
    """Tests for DynamoDBSessionManager constructor."""

    def test_uses_injected_dynamodb_resource(self):
        """When dynamodb_resource is provided, it should be used directly."""
        from services.tutor_session_manager import DynamoDBSessionManager

        table = _make_mock_table()
        dynamodb = _make_mock_dynamodb(table)

        sm = DynamoDBSessionManager(
            table_name="my-table",
            session_id="sess1",
            user_id="user1",
            dynamodb_resource=dynamodb,
        )
        dynamodb.Table.assert_called_once_with("my-table")
        assert sm.table_name == "my-table"
        assert sm.session_id == "sess1"
        assert sm.user_id == "user1"

    @patch("services.tutor_session_manager.boto3")
    def test_creates_dynamodb_resource_with_endpoint_url(self, mock_boto3):
        """When DYNAMODB_ENDPOINT_URL is set, it should be used for DynamoDB resource."""
        from services.tutor_session_manager import DynamoDBSessionManager

        mock_resource = MagicMock()
        mock_boto3.resource.return_value = mock_resource

        with patch.dict("os.environ", {"DYNAMODB_ENDPOINT_URL": "http://localhost:8000"}):
            DynamoDBSessionManager(
                table_name="my-table",
                session_id="sess1",
                user_id="user1",
            )
        mock_boto3.resource.assert_called_once_with(
            "dynamodb", endpoint_url="http://localhost:8000"
        )

    @patch("services.tutor_session_manager.boto3")
    def test_creates_dynamodb_resource_with_aws_endpoint_url(self, mock_boto3):
        """When AWS_ENDPOINT_URL is set, it should be used as fallback."""
        from services.tutor_session_manager import DynamoDBSessionManager

        mock_resource = MagicMock()
        mock_boto3.resource.return_value = mock_resource

        with patch.dict(
            "os.environ",
            {"AWS_ENDPOINT_URL": "http://localhost:4566"},
            clear=False,
        ):
            # Make sure DYNAMODB_ENDPOINT_URL is not set
            env = {"AWS_ENDPOINT_URL": "http://localhost:4566"}
            with patch.dict("os.environ", env, clear=False):
                with patch.dict("os.environ", {"DYNAMODB_ENDPOINT_URL": ""}, clear=False):
                    DynamoDBSessionManager(
                        table_name="my-table",
                        session_id="sess1",
                        user_id="user1",
                    )
            mock_boto3.resource.assert_called_with(
                "dynamodb", endpoint_url="http://localhost:4566"
            )

    @patch("services.tutor_session_manager.boto3")
    def test_creates_dynamodb_resource_default(self, mock_boto3):
        """Without endpoint env vars, it should create default DynamoDB resource."""
        from services.tutor_session_manager import DynamoDBSessionManager

        mock_resource = MagicMock()
        mock_boto3.resource.return_value = mock_resource

        with patch.dict("os.environ", {"DYNAMODB_ENDPOINT_URL": "", "AWS_ENDPOINT_URL": ""}):
            DynamoDBSessionManager(
                table_name="my-table",
                session_id="sess1",
                user_id="user1",
            )
        mock_boto3.resource.assert_called_once_with("dynamodb")


# ===================================================================
# Round-trip conversion test
# ===================================================================


class TestRoundTripConversion:
    """Test message round-trip: Strands -> DynamoDB -> Strands."""

    def test_roundtrip_preserves_content(self):
        """Converting Strands->DynamoDB->Strands should preserve role and text content."""
        from services.tutor_session_manager import DynamoDBSessionManager

        original = _make_strands_message("user", "Hello, world!")

        dynamo_msg = DynamoDBSessionManager._strands_to_dynamo_message(original)
        restored = DynamoDBSessionManager._dynamo_to_strands_message(dynamo_msg)

        assert restored["role"] == original["role"]
        assert restored["content"] == original["content"]

    def test_roundtrip_assistant_message(self):
        """Round-trip for assistant messages."""
        from services.tutor_session_manager import DynamoDBSessionManager

        original = _make_strands_message("assistant", "Here is my answer.")

        dynamo_msg = DynamoDBSessionManager._strands_to_dynamo_message(original)
        restored = DynamoDBSessionManager._dynamo_to_strands_message(dynamo_msg)

        assert restored["role"] == "assistant"
        assert restored["content"] == [{"text": "Here is my answer."}]

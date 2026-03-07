"""Integration tests for TutorService with SessionManager -- TASK-0169.

Verifies API compatibility (TC-006-01 to TC-006-03), multi-turn conversation
with DynamoDB backend, backend switching, and regression of existing behavior.
"""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from models.tutor import (
    SendMessageResponse,
    TutorMessage,
    TutorSessionResponse,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def integration_dynamodb_tables():
    """Create moto DynamoDB tables for integration testing."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

        # Tutor sessions table
        dynamodb.create_table(
            TableName="memoru-tutor-sessions-integration",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "session_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "session_id", "AttributeType": "S"},
                {"AttributeName": "status", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "user_id-status-index",
                    "KeySchema": [
                        {"AttributeName": "user_id", "KeyType": "HASH"},
                        {"AttributeName": "status", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Decks table
        dynamodb.create_table(
            TableName="memoru-decks-integration",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "deck_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "deck_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        # Cards table
        dynamodb.create_table(
            TableName="memoru-cards-integration",
            KeySchema=[
                {"AttributeName": "user_id", "KeyType": "HASH"},
                {"AttributeName": "card_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "card_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )

        yield dynamodb


@pytest.fixture
def mock_ai_service():
    """Mock AI service returning deterministic responses."""
    ai = MagicMock()
    ai.generate_response.return_value = (
        "こんにちは！このデッキについて一緒に学びましょう。",
        [],
    )
    ai.clean_response_text.side_effect = lambda text: text
    return ai


def _seed_deck(
    dynamodb,
    user_id="integration-user",
    deck_id="deck_int_001",
    name="統合テストデッキ",
):
    """Seed a deck with cards for integration tests."""
    decks_table = dynamodb.Table("memoru-decks-integration")
    decks_table.put_item(
        Item={
            "user_id": user_id,
            "deck_id": deck_id,
            "name": name,
            "card_count": 2,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    cards_table = dynamodb.Table("memoru-cards-integration")
    cards_table.put_item(
        Item={
            "user_id": user_id,
            "card_id": "card_int_001",
            "deck_id": deck_id,
            "front": "apple",
            "back": "りんご",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    cards_table.put_item(
        Item={
            "user_id": user_id,
            "card_id": "card_int_002",
            "deck_id": deck_id,
            "front": "dog",
            "back": "犬",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def _create_service_with_mock_sm(dynamodb, ai_service):
    """Create TutorService with a mock SessionManager factory."""
    mock_sm_factory = MagicMock()
    mock_sm_factory.return_value = MagicMock()

    from services.tutor_service import TutorService

    service = TutorService(
        table_name="memoru-tutor-sessions-integration",
        dynamodb_resource=dynamodb,
        ai_service=ai_service,
        session_manager_factory=mock_sm_factory,
    )
    return service, mock_sm_factory


def _create_service_with_dynamodb_sm(dynamodb, ai_service):
    """Create TutorService with DynamoDB SessionManager (real integration).

    The factory creates actual DynamoDBSessionManager instances backed by moto.
    """
    from services.tutor_session_manager import DynamoDBSessionManager

    def dynamodb_sm_factory(session_id: str, user_id: str):
        return DynamoDBSessionManager(
            table_name="memoru-tutor-sessions-integration",
            session_id=session_id,
            user_id=user_id,
            dynamodb_resource=dynamodb,
        )

    from services.tutor_service import TutorService

    service = TutorService(
        table_name="memoru-tutor-sessions-integration",
        dynamodb_resource=dynamodb,
        ai_service=ai_service,
        session_manager_factory=dynamodb_sm_factory,
    )
    return service, dynamodb_sm_factory


# ---------------------------------------------------------------------------
# 1. API Compatibility Tests (TC-006-01, TC-006-02, TC-006-03)
# ---------------------------------------------------------------------------


class TestAPICompatibility:
    """Verify response shapes are unchanged after SessionManager integration."""

    def test_tc_006_01_start_session_response_format(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """TC-006-01: POST /tutor/sessions returns TutorSessionResponse with all required fields."""
        _seed_deck(integration_dynamodb_tables)
        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            service, _ = _create_service_with_mock_sm(
                integration_dynamodb_tables, mock_ai_service
            )

            result = service.start_session(
                user_id="integration-user",
                deck_id="deck_int_001",
                mode="free_talk",
            )

        # Type check
        assert isinstance(result, TutorSessionResponse)

        # Required fields present and correct
        assert result.session_id.startswith("tutor_")
        assert result.deck_id == "deck_int_001"
        assert result.mode == "free_talk"
        assert result.status == "active"
        assert result.message_count == 0
        assert result.created_at is not None
        assert result.updated_at is not None

        # Messages contain AI greeting
        assert isinstance(result.messages, list)
        assert len(result.messages) == 1
        greeting = result.messages[0]
        assert isinstance(greeting, TutorMessage)
        assert greeting.role == "assistant"
        assert isinstance(greeting.content, str)
        assert len(greeting.content) > 0
        assert isinstance(greeting.timestamp, str)
        assert isinstance(greeting.related_cards, list)

    def test_tc_006_02_send_message_response_format(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """TC-006-02: POST /tutor/sessions/{id}/messages returns SendMessageResponse."""
        _seed_deck(integration_dynamodb_tables)
        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            service, _ = _create_service_with_mock_sm(
                integration_dynamodb_tables, mock_ai_service
            )

            session = service.start_session(
                user_id="integration-user",
                deck_id="deck_int_001",
                mode="free_talk",
            )

            mock_ai_service.generate_response.return_value = (
                "appleはりんごという意味です。",
                ["card_int_001"],
            )

            result = service.send_message(
                user_id="integration-user",
                session_id=session.session_id,
                content="appleについて教えて",
            )

        # Type check
        assert isinstance(result, SendMessageResponse)

        # Required fields
        assert result.session_id == session.session_id
        assert result.message_count == 1
        assert isinstance(result.is_limit_reached, bool)
        assert result.is_limit_reached is False

        # Message structure
        msg = result.message
        assert isinstance(msg, TutorMessage)
        assert msg.role == "assistant"
        assert isinstance(msg.content, str)
        assert len(msg.content) > 0
        assert isinstance(msg.related_cards, list)
        assert msg.related_cards == ["card_int_001"]
        assert isinstance(msg.timestamp, str)

    def test_tc_006_03_list_sessions_response_format(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """TC-006-03: GET /tutor/sessions returns list[TutorSessionResponse] with empty messages."""
        _seed_deck(integration_dynamodb_tables)
        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            service, _ = _create_service_with_mock_sm(
                integration_dynamodb_tables, mock_ai_service
            )

            # Create two sessions
            service.start_session(
                user_id="integration-user",
                deck_id="deck_int_001",
                mode="free_talk",
            )
            service.start_session(
                user_id="integration-user",
                deck_id="deck_int_001",
                mode="quiz",
            )

            result = service.list_sessions(user_id="integration-user")

        # Type check
        assert isinstance(result, list)
        assert len(result) >= 1  # At least the active session

        for session_resp in result:
            assert isinstance(session_resp, TutorSessionResponse)
            assert session_resp.session_id.startswith("tutor_")
            assert session_resp.deck_id == "deck_int_001"
            assert session_resp.mode in ("free_talk", "quiz", "weak_point")
            assert session_resp.status in ("active", "ended", "timed_out")
            assert isinstance(session_resp.message_count, int)
            assert session_resp.created_at is not None
            assert session_resp.updated_at is not None
            # List view returns empty messages (API contract)
            assert session_resp.messages == []

    def test_start_session_response_serializable(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """TutorSessionResponse can be serialized to JSON (Pydantic model_dump)."""
        _seed_deck(integration_dynamodb_tables)
        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            service, _ = _create_service_with_mock_sm(
                integration_dynamodb_tables, mock_ai_service
            )

            result = service.start_session(
                user_id="integration-user",
                deck_id="deck_int_001",
                mode="free_talk",
            )

        data = result.model_dump()
        assert "session_id" in data
        assert "messages" in data
        assert "deck_id" in data
        assert "mode" in data
        assert "status" in data
        assert "message_count" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_send_message_response_serializable(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """SendMessageResponse can be serialized to JSON (Pydantic model_dump)."""
        _seed_deck(integration_dynamodb_tables)
        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            service, _ = _create_service_with_mock_sm(
                integration_dynamodb_tables, mock_ai_service
            )

            session = service.start_session(
                user_id="integration-user",
                deck_id="deck_int_001",
                mode="free_talk",
            )
            mock_ai_service.generate_response.return_value = ("回答です。", [])

            result = service.send_message(
                user_id="integration-user",
                session_id=session.session_id,
                content="テスト質問",
            )

        data = result.model_dump()
        assert "message" in data
        assert "session_id" in data
        assert "message_count" in data
        assert "is_limit_reached" in data
        assert data["message"]["role"] == "assistant"


# ---------------------------------------------------------------------------
# 2. Multi-turn Conversation Tests (DynamoDB backend)
# ---------------------------------------------------------------------------


class TestMultiTurnConversation:
    """Verify multi-turn conversation works with DynamoDB SessionManager."""

    def test_three_rounds_then_fourth_message(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """3 round-trips followed by a 4th message; SessionManager is used each time."""
        _seed_deck(integration_dynamodb_tables)
        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            service, sm_factory = _create_service_with_mock_sm(
                integration_dynamodb_tables, mock_ai_service
            )

            session = service.start_session(
                user_id="integration-user",
                deck_id="deck_int_001",
                mode="free_talk",
            )

            # Factory called once for start_session greeting
            assert sm_factory.call_count == 1

            # Send 4 messages
            for i in range(4):
                mock_ai_service.generate_response.return_value = (
                    f"回答{i + 1}です。",
                    [],
                )
                resp = service.send_message(
                    user_id="integration-user",
                    session_id=session.session_id,
                    content=f"質問{i + 1}",
                )

        # Factory should be called 5 times total (1 start + 4 sends)
        assert sm_factory.call_count == 5

        # All calls used same session_id
        for call in sm_factory.call_args_list:
            assert call[1]["session_id"] == session.session_id
            assert call[1]["user_id"] == "integration-user"

        # Last response has correct count
        assert resp.message_count == 4
        assert resp.message.content == "回答4です。"

    def test_multi_turn_with_dynamodb_session_manager(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """DynamoDB SessionManager is correctly created per turn with real instances.

        Since the AI service is mocked, it does not actually call SessionManager
        methods (initialize/append_message). This test verifies that the
        TutorService correctly creates DynamoDBSessionManager instances for each
        turn, the metadata (message_count) is updated, and SessionManager.close()
        succeeds without error.
        """
        _seed_deck(integration_dynamodb_tables)
        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            service, _ = _create_service_with_dynamodb_sm(
                integration_dynamodb_tables, mock_ai_service
            )

            session = service.start_session(
                user_id="integration-user",
                deck_id="deck_int_001",
                mode="free_talk",
            )

            # Send 3 messages
            for i in range(3):
                mock_ai_service.generate_response.return_value = (
                    f"回答{i + 1}です。",
                    [],
                )
                resp = service.send_message(
                    user_id="integration-user",
                    session_id=session.session_id,
                    content=f"質問{i + 1}",
                )

        assert resp.message_count == 3
        assert resp.message.content == "回答3です。"

        # Verify metadata is persisted correctly in DynamoDB
        table = integration_dynamodb_tables.Table(
            "memoru-tutor-sessions-integration"
        )
        item = table.get_item(
            Key={
                "user_id": "integration-user",
                "session_id": session.session_id,
            }
        )["Item"]

        assert int(item["message_count"]) == 3
        assert item["status"] == "active"

    def test_message_count_increments_correctly(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """Message count increments with each send_message call."""
        _seed_deck(integration_dynamodb_tables)
        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            service, _ = _create_service_with_mock_sm(
                integration_dynamodb_tables, mock_ai_service
            )

            session = service.start_session(
                user_id="integration-user",
                deck_id="deck_int_001",
                mode="free_talk",
            )

            mock_ai_service.generate_response.return_value = ("応答", [])

            counts = []
            for i in range(5):
                resp = service.send_message(
                    "integration-user",
                    session.session_id,
                    f"msg{i}",
                )
                counts.append(resp.message_count)

        assert counts == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# 3. Backend Switching Tests
# ---------------------------------------------------------------------------


class TestBackendSwitching:
    """Verify session manager factory selects correct backend."""

    def test_dynamodb_backend_via_env(self, integration_dynamodb_tables):
        """TUTOR_SESSION_BACKEND=dynamodb creates DynamoDBSessionManager."""
        with patch.dict(os.environ, {
            "TUTOR_SESSION_BACKEND": "dynamodb",
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
        }):
            from services.tutor_session_factory import (
                create_tutor_session_manager,
            )
            from services.tutor_session_manager import DynamoDBSessionManager

            sm = create_tutor_session_manager(
                session_id="tutor_test123",
                user_id="user1",
            )

            assert isinstance(sm, DynamoDBSessionManager)
            assert sm.session_id == "tutor_test123"
            assert sm.user_id == "user1"

    def test_agentcore_backend_requires_memory_id(self):
        """TUTOR_SESSION_BACKEND=agentcore without AGENTCORE_MEMORY_ID raises error."""
        with patch.dict(os.environ, {
            "TUTOR_SESSION_BACKEND": "agentcore",
            "AGENTCORE_MEMORY_ID": "",
        }):
            from services.tutor_ai_service import TutorAIServiceError
            from services.tutor_session_factory import (
                create_tutor_session_manager,
            )

            with pytest.raises(TutorAIServiceError, match="AGENTCORE_MEMORY_ID"):
                create_tutor_session_manager(
                    session_id="tutor_test123",
                    user_id="user1",
                )

    def test_unknown_backend_raises_value_error(self):
        """Unknown backend value raises ValueError."""
        with patch.dict(os.environ, {"TUTOR_SESSION_BACKEND": "redis"}):
            from services.tutor_session_factory import (
                create_tutor_session_manager,
            )

            with pytest.raises(ValueError, match="Unknown"):
                create_tutor_session_manager(
                    session_id="tutor_test123",
                    user_id="user1",
                )

    def test_auto_select_dev_uses_dynamodb(self, integration_dynamodb_tables):
        """ENVIRONMENT=dev with no explicit backend auto-selects dynamodb."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "dev",
            "TUTOR_SESSION_BACKEND": "",
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
        }):
            from services.tutor_session_factory import (
                create_tutor_session_manager,
            )
            from services.tutor_session_manager import DynamoDBSessionManager

            sm = create_tutor_session_manager(
                session_id="tutor_dev123",
                user_id="user_dev",
            )

            assert isinstance(sm, DynamoDBSessionManager)

    def test_tutor_service_uses_factory_for_start_session(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """TutorService.start_session calls session_manager_factory."""
        _seed_deck(integration_dynamodb_tables)
        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            service, sm_factory = _create_service_with_mock_sm(
                integration_dynamodb_tables, mock_ai_service
            )

            service.start_session(
                user_id="integration-user",
                deck_id="deck_int_001",
                mode="free_talk",
            )

        sm_factory.assert_called_once()
        call_kwargs = sm_factory.call_args[1]
        assert call_kwargs["user_id"] == "integration-user"
        assert call_kwargs["session_id"].startswith("tutor_")

    def test_tutor_service_uses_factory_for_send_message(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """TutorService.send_message calls session_manager_factory."""
        _seed_deck(integration_dynamodb_tables)
        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            service, sm_factory = _create_service_with_mock_sm(
                integration_dynamodb_tables, mock_ai_service
            )

            session = service.start_session(
                user_id="integration-user",
                deck_id="deck_int_001",
                mode="free_talk",
            )
            sm_factory.reset_mock()
            mock_ai_service.generate_response.return_value = ("応答", [])

            service.send_message(
                "integration-user", session.session_id, "質問"
            )

        sm_factory.assert_called_once_with(
            session_id=session.session_id,
            user_id="integration-user",
        )


# ---------------------------------------------------------------------------
# 4. SessionManager Mockability Tests (NFR-301)
# ---------------------------------------------------------------------------


class TestSessionManagerMockability:
    """Verify SessionManager can be mocked for testing (NFR-301)."""

    def test_mock_session_manager_works_with_tutor_service(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """TutorService works with a fully mocked SessionManager."""
        _seed_deck(integration_dynamodb_tables)
        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            mock_sm = MagicMock()
            mock_sm_factory = MagicMock(return_value=mock_sm)

            from services.tutor_service import TutorService

            service = TutorService(
                table_name="memoru-tutor-sessions-integration",
                dynamodb_resource=integration_dynamodb_tables,
                ai_service=mock_ai_service,
                session_manager_factory=mock_sm_factory,
            )

            session = service.start_session(
                user_id="integration-user",
                deck_id="deck_int_001",
                mode="free_talk",
            )

        # Service works with mocked SM
        assert session.status == "active"
        mock_sm.close.assert_called_once()

    def test_session_manager_factory_injection(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """Custom session_manager_factory can be injected into TutorService."""
        _seed_deck(integration_dynamodb_tables)

        custom_calls = []

        def custom_factory(session_id: str, user_id: str):
            custom_calls.append((session_id, user_id))
            return MagicMock()

        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            from services.tutor_service import TutorService

            service = TutorService(
                table_name="memoru-tutor-sessions-integration",
                dynamodb_resource=integration_dynamodb_tables,
                ai_service=mock_ai_service,
                session_manager_factory=custom_factory,
            )

            service.start_session(
                user_id="integration-user",
                deck_id="deck_int_001",
                mode="free_talk",
            )

        assert len(custom_calls) == 1
        assert custom_calls[0][1] == "integration-user"
        assert custom_calls[0][0].startswith("tutor_")


# ---------------------------------------------------------------------------
# 5. End-to-End Flow Tests
# ---------------------------------------------------------------------------


class TestEndToEndFlow:
    """Verify complete session lifecycle with SessionManager."""

    def test_full_lifecycle_start_send_end(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """Complete lifecycle: start -> send messages -> end session."""
        _seed_deck(integration_dynamodb_tables)
        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            service, _ = _create_service_with_mock_sm(
                integration_dynamodb_tables, mock_ai_service
            )

            # Start
            session = service.start_session(
                user_id="integration-user",
                deck_id="deck_int_001",
                mode="free_talk",
            )
            assert session.status == "active"

            # Send messages
            mock_ai_service.generate_response.return_value = ("回答1", [])
            r1 = service.send_message(
                "integration-user", session.session_id, "質問1"
            )
            assert r1.message_count == 1

            mock_ai_service.generate_response.return_value = ("回答2", [])
            r2 = service.send_message(
                "integration-user", session.session_id, "質問2"
            )
            assert r2.message_count == 2

            # End
            ended = service.end_session(
                "integration-user", session.session_id
            )
            assert ended.status == "ended"
            assert ended.ended_at is not None

            # Cannot send after end
            from services.tutor_service import SessionEndedError

            with pytest.raises(SessionEndedError):
                service.send_message(
                    "integration-user", session.session_id, "これは送れない"
                )

    def test_list_after_multiple_sessions(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """List sessions returns correct data after creating multiple sessions."""
        _seed_deck(integration_dynamodb_tables)
        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            service, _ = _create_service_with_mock_sm(
                integration_dynamodb_tables, mock_ai_service
            )

            # Start session 1 and end it
            s1 = service.start_session(
                "integration-user", "deck_int_001", "free_talk"
            )
            service.end_session("integration-user", s1.session_id)

            # Start session 2 (active)
            s2 = service.start_session(
                "integration-user", "deck_int_001", "quiz"
            )

            all_sessions = service.list_sessions("integration-user")
            active_sessions = service.list_sessions(
                "integration-user", status="active"
            )
            ended_sessions = service.list_sessions(
                "integration-user", status="ended"
            )

        # All sessions should be returned
        assert len(all_sessions) == 2
        # Filter by status
        assert len(active_sessions) == 1
        assert active_sessions[0].session_id == s2.session_id
        assert len(ended_sessions) == 1
        assert ended_sessions[0].session_id == s1.session_id

        # All have empty messages in list view
        for s in all_sessions:
            assert s.messages == []

    def test_get_session_via_session_manager(
        self, integration_dynamodb_tables, mock_ai_service
    ):
        """get_session retrieves messages via SessionManager.read_messages()."""
        _seed_deck(integration_dynamodb_tables)

        call_count = {"n": 0}

        def smart_factory(session_id: str, user_id: str):
            call_count["n"] += 1
            sm = MagicMock()
            if call_count["n"] > 1:
                # For get_session, return DynamoDB-format messages via read_messages
                sm.read_messages.return_value = [
                    {
                        "role": "assistant",
                        "content": "挨拶メッセージ",
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "related_cards": [],
                    },
                    {
                        "role": "user",
                        "content": "質問です",
                        "timestamp": "2026-01-01T00:00:01+00:00",
                        "related_cards": [],
                    },
                    {
                        "role": "assistant",
                        "content": "回答です",
                        "timestamp": "2026-01-01T00:00:02+00:00",
                        "related_cards": ["card_int_001"],
                    },
                ]
            return sm

        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-integration",
            "DECKS_TABLE": "memoru-decks-integration",
            "CARDS_TABLE": "memoru-cards-integration",
        }):
            from services.tutor_service import TutorService

            service = TutorService(
                table_name="memoru-tutor-sessions-integration",
                dynamodb_resource=integration_dynamodb_tables,
                ai_service=mock_ai_service,
                session_manager_factory=smart_factory,
            )

            session = service.start_session(
                "integration-user", "deck_int_001", "free_talk"
            )

            result = service.get_session(
                "integration-user", session.session_id
            )

        assert isinstance(result, TutorSessionResponse)
        assert len(result.messages) == 3
        assert result.messages[0].role == "assistant"
        assert result.messages[0].content == "挨拶メッセージ"
        assert result.messages[0].timestamp == "2026-01-01T00:00:00+00:00"
        assert result.messages[1].role == "user"
        assert result.messages[2].role == "assistant"
        assert result.messages[2].related_cards == ["card_int_001"]

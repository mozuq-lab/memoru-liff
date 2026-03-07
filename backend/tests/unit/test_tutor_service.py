"""Unit tests for TutorService — TDD Red Phase.

Tests start_session, send_message, end_session, timeout check,
message limit, auto-end active session, TTL.
"""

import os
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def dynamodb_tables():
    """Create mock DynamoDB tables for tutor sessions, decks, and cards."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

        # Tutor sessions table
        dynamodb.create_table(
            TableName="memoru-tutor-sessions-test",
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
            TableName="memoru-decks-test",
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
            TableName="memoru-cards-test",
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
    """Mock TutorAIService."""
    ai = MagicMock()
    ai.generate_response.return_value = (
        "こんにちは！このデッキについて一緒に学びましょう。",
        [],
    )
    ai.clean_response_text.side_effect = lambda text: text
    return ai


@pytest.fixture
def mock_session_manager_factory():
    """Mock SessionManager factory that returns a MagicMock SessionManager."""
    factory = MagicMock()
    factory.return_value = MagicMock()
    return factory


@pytest.fixture
def tutor_service(dynamodb_tables, mock_ai_service, mock_session_manager_factory):
    """Create TutorService with mock DynamoDB, AI service, and SessionManager factory."""
    with patch.dict(os.environ, {
        "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-test",
        "DECKS_TABLE": "memoru-decks-test",
        "CARDS_TABLE": "memoru-cards-test",
    }):
        from services.tutor_service import TutorService

        service = TutorService(
            table_name="memoru-tutor-sessions-test",
            dynamodb_resource=dynamodb_tables,
            ai_service=mock_ai_service,
            session_manager_factory=mock_session_manager_factory,
        )
        return service


def _seed_deck(dynamodb_tables, user_id="test-user", deck_id="deck_001", name="テストデッキ"):
    """Seed a deck with cards for testing."""
    decks_table = dynamodb_tables.Table("memoru-decks-test")
    decks_table.put_item(
        Item={
            "user_id": user_id,
            "deck_id": deck_id,
            "name": name,
            "card_count": 2,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )

    cards_table = dynamodb_tables.Table("memoru-cards-test")
    cards_table.put_item(
        Item={
            "user_id": user_id,
            "card_id": "card_001",
            "deck_id": deck_id,
            "front": "apple",
            "back": "りんご",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    cards_table.put_item(
        Item={
            "user_id": user_id,
            "card_id": "card_002",
            "deck_id": deck_id,
            "front": "dog",
            "back": "犬",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )


class TestStartSession:
    """Tests for TutorService.start_session."""

    def test_start_session_creates_active_session(self, tutor_service, dynamodb_tables):
        _seed_deck(dynamodb_tables)

        session = tutor_service.start_session(
            user_id="test-user",
            deck_id="deck_001",
            mode="free_talk",
        )

        assert session.status == "active"
        assert session.mode == "free_talk"
        assert session.deck_id == "deck_001"
        assert session.session_id.startswith("tutor_")
        assert session.message_count == 0
        assert len(session.messages) >= 1  # AI greeting

    def test_start_session_auto_ends_existing_active(self, tutor_service, dynamodb_tables):
        _seed_deck(dynamodb_tables)

        session1 = tutor_service.start_session(
            user_id="test-user", deck_id="deck_001", mode="free_talk"
        )
        session2 = tutor_service.start_session(
            user_id="test-user", deck_id="deck_001", mode="quiz"
        )

        # session1 should be ended
        old_session = tutor_service.get_session("test-user", session1.session_id)
        assert old_session.status == "ended"
        assert session2.status == "active"

    def test_start_session_calls_ai_for_greeting(self, tutor_service, dynamodb_tables, mock_ai_service):
        _seed_deck(dynamodb_tables)

        tutor_service.start_session(
            user_id="test-user", deck_id="deck_001", mode="free_talk"
        )

        mock_ai_service.generate_response.assert_called_once()


class TestSendMessage:
    """Tests for TutorService.send_message."""

    def test_send_message_returns_ai_response(self, tutor_service, dynamodb_tables, mock_ai_service):
        _seed_deck(dynamodb_tables)
        session = tutor_service.start_session(
            user_id="test-user", deck_id="deck_001", mode="free_talk"
        )

        mock_ai_service.generate_response.return_value = (
            "この概念について説明します。",
            ["card_001"],
        )

        response = tutor_service.send_message(
            user_id="test-user",
            session_id=session.session_id,
            content="appleについて教えて",
        )

        assert response.message.role == "assistant"
        assert response.message.content == "この概念について説明します。"
        assert response.message.related_cards == ["card_001"]
        assert response.message_count == 1

    def test_send_message_increments_count(self, tutor_service, dynamodb_tables, mock_ai_service):
        _seed_deck(dynamodb_tables)
        session = tutor_service.start_session(
            user_id="test-user", deck_id="deck_001", mode="free_talk"
        )

        mock_ai_service.generate_response.return_value = ("Response", [])

        r1 = tutor_service.send_message("test-user", session.session_id, "q1")
        assert r1.message_count == 1

        r2 = tutor_service.send_message("test-user", session.session_id, "q2")
        assert r2.message_count == 2

    def test_send_message_limit_reached(self, tutor_service, dynamodb_tables, mock_ai_service):
        _seed_deck(dynamodb_tables)
        session = tutor_service.start_session(
            user_id="test-user", deck_id="deck_001", mode="free_talk"
        )

        mock_ai_service.generate_response.return_value = ("Response", [])

        # Send up to MAX_ROUNDS
        from services.tutor_service import TutorService

        for i in range(TutorService.MAX_ROUNDS):
            resp = tutor_service.send_message("test-user", session.session_id, f"q{i}")

        assert resp.is_limit_reached is True

    def test_send_message_to_ended_session_raises(self, tutor_service, dynamodb_tables):
        _seed_deck(dynamodb_tables)
        session = tutor_service.start_session(
            user_id="test-user", deck_id="deck_001", mode="free_talk"
        )
        tutor_service.end_session("test-user", session.session_id)

        from services.tutor_service import SessionEndedError

        with pytest.raises(SessionEndedError):
            tutor_service.send_message("test-user", session.session_id, "hello")


class TestEndSession:
    """Tests for TutorService.end_session."""

    def test_end_session_marks_as_ended(self, tutor_service, dynamodb_tables):
        _seed_deck(dynamodb_tables)
        session = tutor_service.start_session(
            user_id="test-user", deck_id="deck_001", mode="free_talk"
        )

        result = tutor_service.end_session("test-user", session.session_id)
        assert result.status == "ended"
        assert result.ended_at is not None

    def test_end_session_sets_ttl(self, tutor_service, dynamodb_tables):
        _seed_deck(dynamodb_tables)
        session = tutor_service.start_session(
            user_id="test-user", deck_id="deck_001", mode="free_talk"
        )

        tutor_service.end_session("test-user", session.session_id)

        # Check TTL in DynamoDB
        table = dynamodb_tables.Table("memoru-tutor-sessions-test")
        item = table.get_item(
            Key={"user_id": "test-user", "session_id": session.session_id}
        )["Item"]
        assert "ttl" in item
        # TTL should be ~7 days from now
        ttl_val = int(item["ttl"])
        now = int(datetime.now(timezone.utc).timestamp())
        assert ttl_val > now
        assert ttl_val < now + (8 * 86400)  # Within 8 days


class TestTimeoutCheck:
    """Tests for request-time timeout detection."""

    def test_timeout_marks_session(self, tutor_service, dynamodb_tables):
        _seed_deck(dynamodb_tables)
        session = tutor_service.start_session(
            user_id="test-user", deck_id="deck_001", mode="free_talk"
        )

        # Manually set updated_at to 31 minutes ago
        table = dynamodb_tables.Table("memoru-tutor-sessions-test")
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
        table.update_item(
            Key={"user_id": "test-user", "session_id": session.session_id},
            UpdateExpression="SET updated_at = :t",
            ExpressionAttributeValues={":t": old_time},
        )

        from services.tutor_service import SessionEndedError

        with pytest.raises(SessionEndedError):
            tutor_service.send_message("test-user", session.session_id, "hello")

        # Verify session is now timed_out
        updated = tutor_service.get_session("test-user", session.session_id)
        assert updated.status == "timed_out"


class TestListSessions:
    """Tests for TutorService.list_sessions."""

    def test_list_sessions_returns_user_sessions(self, tutor_service, dynamodb_tables):
        _seed_deck(dynamodb_tables)
        tutor_service.start_session("test-user", "deck_001", "free_talk")

        sessions = tutor_service.list_sessions("test-user")
        assert len(sessions) >= 1

    def test_list_sessions_filters_by_status(self, tutor_service, dynamodb_tables):
        _seed_deck(dynamodb_tables)
        s1 = tutor_service.start_session("test-user", "deck_001", "free_talk")
        tutor_service.end_session("test-user", s1.session_id)
        tutor_service.start_session("test-user", "deck_001", "quiz")

        active = tutor_service.list_sessions("test-user", status="active")
        assert all(s.status == "active" for s in active)

        ended = tutor_service.list_sessions("test-user", status="ended")
        assert all(s.status == "ended" for s in ended)

    def test_list_sessions_empty_for_other_user(self, tutor_service, dynamodb_tables):
        _seed_deck(dynamodb_tables)
        tutor_service.start_session("test-user", "deck_001", "free_talk")

        sessions = tutor_service.list_sessions("other-user")
        assert len(sessions) == 0


class TestStartSessionWithSessionManager:
    """Tests for TutorService.start_session with SessionManager integration (TASK-0166)."""

    def test_session_manager_factory_called_with_session_id_and_user_id(
        self, dynamodb_tables, mock_ai_service
    ):
        """SessionManager factory is called with generated session_id and user_id."""
        _seed_deck(dynamodb_tables)
        mock_sm_factory = MagicMock()
        mock_sm = MagicMock()
        mock_sm_factory.return_value = mock_sm

        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-test",
            "DECKS_TABLE": "memoru-decks-test",
            "CARDS_TABLE": "memoru-cards-test",
        }):
            from services.tutor_service import TutorService

            service = TutorService(
                table_name="memoru-tutor-sessions-test",
                dynamodb_resource=dynamodb_tables,
                ai_service=mock_ai_service,
                session_manager_factory=mock_sm_factory,
            )

            session = service.start_session(
                user_id="test-user", deck_id="deck_001", mode="free_talk"
            )

        mock_sm_factory.assert_called_once()
        call_kwargs = mock_sm_factory.call_args
        assert call_kwargs[1]["user_id"] == "test-user"
        assert call_kwargs[1]["session_id"].startswith("tutor_")
        assert call_kwargs[1]["session_id"] == session.session_id

    def test_generate_response_receives_session_manager(
        self, dynamodb_tables, mock_ai_service
    ):
        """AI service generate_response is called with session_manager kwarg."""
        _seed_deck(dynamodb_tables)
        mock_sm_factory = MagicMock()
        mock_sm = MagicMock()
        mock_sm_factory.return_value = mock_sm

        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-test",
            "DECKS_TABLE": "memoru-decks-test",
            "CARDS_TABLE": "memoru-cards-test",
        }):
            from services.tutor_service import TutorService

            service = TutorService(
                table_name="memoru-tutor-sessions-test",
                dynamodb_resource=dynamodb_tables,
                ai_service=mock_ai_service,
                session_manager_factory=mock_sm_factory,
            )

            service.start_session(
                user_id="test-user", deck_id="deck_001", mode="free_talk"
            )

        call_kwargs = mock_ai_service.generate_response.call_args
        assert call_kwargs[1]["session_manager"] is mock_sm

    def test_generate_response_receives_string_message(
        self, dynamodb_tables, mock_ai_service
    ):
        """AI service generate_response receives a string message (not list) when session_manager is used."""
        _seed_deck(dynamodb_tables)
        mock_sm_factory = MagicMock()
        mock_sm_factory.return_value = MagicMock()

        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-test",
            "DECKS_TABLE": "memoru-decks-test",
            "CARDS_TABLE": "memoru-cards-test",
        }):
            from services.tutor_service import TutorService

            service = TutorService(
                table_name="memoru-tutor-sessions-test",
                dynamodb_resource=dynamodb_tables,
                ai_service=mock_ai_service,
                session_manager_factory=mock_sm_factory,
            )

            service.start_session(
                user_id="test-user", deck_id="deck_001", mode="free_talk"
            )

        call_kwargs = mock_ai_service.generate_response.call_args
        assert isinstance(call_kwargs[1]["messages"], str)

    def test_metadata_saved_without_messages_field(
        self, dynamodb_tables, mock_ai_service
    ):
        """DynamoDB metadata does not contain messages (SessionManager manages them)."""
        _seed_deck(dynamodb_tables)
        mock_sm_factory = MagicMock()
        mock_sm_factory.return_value = MagicMock()

        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-test",
            "DECKS_TABLE": "memoru-decks-test",
            "CARDS_TABLE": "memoru-cards-test",
        }):
            from services.tutor_service import TutorService

            service = TutorService(
                table_name="memoru-tutor-sessions-test",
                dynamodb_resource=dynamodb_tables,
                ai_service=mock_ai_service,
                session_manager_factory=mock_sm_factory,
            )

            session = service.start_session(
                user_id="test-user", deck_id="deck_001", mode="free_talk"
            )

        # Check DynamoDB item directly
        table = dynamodb_tables.Table("memoru-tutor-sessions-test")
        item = table.get_item(
            Key={"user_id": "test-user", "session_id": session.session_id}
        )["Item"]

        assert item["status"] == "active"
        assert item["mode"] == "free_talk"
        assert item["deck_id"] == "deck_001"
        assert item["message_count"] == 0
        assert "system_prompt" in item
        assert "messages" not in item  # SessionManager manages messages

    def test_validation_failure_preserves_existing_sessions(
        self, dynamodb_tables, mock_ai_service
    ):
        """DeckNotFoundError does not end existing active sessions (regression test)."""
        _seed_deck(dynamodb_tables)
        mock_sm_factory = MagicMock()
        mock_sm_factory.return_value = MagicMock()

        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-test",
            "DECKS_TABLE": "memoru-decks-test",
            "CARDS_TABLE": "memoru-cards-test",
        }):
            from services.tutor_service import TutorService, DeckNotFoundError

            service = TutorService(
                table_name="memoru-tutor-sessions-test",
                dynamodb_resource=dynamodb_tables,
                ai_service=mock_ai_service,
                session_manager_factory=mock_sm_factory,
            )

            # Create an active session
            existing = service.start_session(
                user_id="test-user", deck_id="deck_001", mode="free_talk"
            )

            # Attempt to start a session with a non-existent deck
            with pytest.raises(DeckNotFoundError):
                service.start_session(
                    user_id="test-user", deck_id="deck_nonexistent", mode="free_talk"
                )

            # Existing session should still be active
            check = service.get_session("test-user", existing.session_id)
            assert check.status == "active"

    def test_api_response_format_unchanged(
        self, dynamodb_tables, mock_ai_service
    ):
        """API response contains session_id, messages (with greeting), and expected fields."""
        _seed_deck(dynamodb_tables)
        mock_sm_factory = MagicMock()
        mock_sm_factory.return_value = MagicMock()

        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-test",
            "DECKS_TABLE": "memoru-decks-test",
            "CARDS_TABLE": "memoru-cards-test",
        }):
            from services.tutor_service import TutorService

            service = TutorService(
                table_name="memoru-tutor-sessions-test",
                dynamodb_resource=dynamodb_tables,
                ai_service=mock_ai_service,
                session_manager_factory=mock_sm_factory,
            )

            session = service.start_session(
                user_id="test-user", deck_id="deck_001", mode="free_talk"
            )

        assert session.session_id.startswith("tutor_")
        assert session.status == "active"
        assert session.deck_id == "deck_001"
        assert session.mode == "free_talk"
        assert session.message_count == 0
        assert len(session.messages) == 1
        assert session.messages[0].role == "assistant"
        assert session.messages[0].content == "こんにちは！このデッキについて一緒に学びましょう。"
        assert session.created_at is not None
        assert session.updated_at is not None

    def test_session_manager_close_called(
        self, dynamodb_tables, mock_ai_service
    ):
        """SessionManager.close() is called after greeting generation."""
        _seed_deck(dynamodb_tables)
        mock_sm_factory = MagicMock()
        mock_sm = MagicMock()
        mock_sm_factory.return_value = mock_sm

        with patch.dict(os.environ, {
            "TUTOR_SESSIONS_TABLE": "memoru-tutor-sessions-test",
            "DECKS_TABLE": "memoru-decks-test",
            "CARDS_TABLE": "memoru-cards-test",
        }):
            from services.tutor_service import TutorService

            service = TutorService(
                table_name="memoru-tutor-sessions-test",
                dynamodb_resource=dynamodb_tables,
                ai_service=mock_ai_service,
                session_manager_factory=mock_sm_factory,
            )

            service.start_session(
                user_id="test-user", deck_id="deck_001", mode="free_talk"
            )

        mock_sm.close.assert_called_once()


class TestGetSession:
    """Tests for TutorService.get_session."""

    def test_get_session_returns_full_data(self, tutor_service, dynamodb_tables):
        _seed_deck(dynamodb_tables)
        session = tutor_service.start_session("test-user", "deck_001", "free_talk")

        result = tutor_service.get_session("test-user", session.session_id)
        assert result.session_id == session.session_id
        assert result.deck_id == "deck_001"
        # Messages are now managed by SessionManager, not stored in DynamoDB metadata.
        # get_session reads from DynamoDB so messages will be empty until TASK-0168.
        assert isinstance(result.messages, list)

    def test_get_nonexistent_session_raises(self, tutor_service):
        from services.tutor_service import SessionNotFoundError

        with pytest.raises(SessionNotFoundError):
            tutor_service.get_session("test-user", "tutor_nonexistent")

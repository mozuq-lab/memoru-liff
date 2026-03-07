"""Unit tests for tutor handler — TDD Red Phase.

Tests all tutor endpoints, error responses including 409 for ended sessions, auth.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from models.tutor import TutorMessage, TutorSessionResponse, SendMessageResponse


def _make_session(**kwargs):
    """Create a TutorSessionResponse with defaults."""
    defaults = {
        "session_id": "tutor_test-session-id",
        "deck_id": "deck_001",
        "mode": "free_talk",
        "status": "active",
        "messages": [
            TutorMessage(
                role="assistant",
                content="こんにちは！",
                related_cards=[],
                timestamp="2026-03-07T10:00:00Z",
            )
        ],
        "message_count": 0,
        "created_at": "2026-03-07T10:00:00Z",
        "updated_at": "2026-03-07T10:00:00Z",
        "ended_at": None,
    }
    defaults.update(kwargs)
    return TutorSessionResponse(**defaults)


def _make_send_response(**kwargs):
    """Create a SendMessageResponse with defaults."""
    defaults = {
        "message": TutorMessage(
            role="assistant",
            content="AI の応答です。",
            related_cards=[],
            timestamp="2026-03-07T10:00:25Z",
        ),
        "session_id": "tutor_test-session-id",
        "message_count": 1,
        "is_limit_reached": False,
    }
    defaults.update(kwargs)
    return SendMessageResponse(**defaults)


class TestCreateSession:
    """POST /tutor/sessions endpoint tests."""

    def test_create_session_success(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions",
            body={"deck_id": "deck_001", "mode": "free_talk"},
        )

        mock_session = _make_session()

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc:
            mock_svc.start_session.return_value = mock_session
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 201
        body = json.loads(response["body"])
        assert body["session_id"] == "tutor_test-session-id"
        assert body["status"] == "active"

    def test_create_session_invalid_mode(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions",
            body={"deck_id": "deck_001", "mode": "invalid_mode"},
        )

        from api.handler import handler

        response = handler(event, lambda_context)
        assert response["statusCode"] == 422

    def test_create_session_missing_deck_id(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions",
            body={"mode": "free_talk"},
        )

        from api.handler import handler

        response = handler(event, lambda_context)
        assert response["statusCode"] == 422


class TestSendMessage:
    """POST /tutor/sessions/{sessionId}/messages endpoint tests."""

    def test_send_message_success(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions/tutor_test-id/messages",
            body={"content": "appleについて教えて"},
            path_parameters={"sessionId": "tutor_test-id"},
        )

        mock_response = _make_send_response()

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc:
            mock_svc.send_message.return_value = mock_response
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["message"]["role"] == "assistant"
        assert body["message_count"] == 1

    def test_send_message_409_ended_session(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions/tutor_test-id/messages",
            body={"content": "hello"},
            path_parameters={"sessionId": "tutor_test-id"},
        )

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc:
            from services.tutor_service import SessionEndedError

            mock_svc.send_message.side_effect = SessionEndedError("Session ended")
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 409

    def test_send_message_empty_content(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions/tutor_test-id/messages",
            body={"content": ""},
            path_parameters={"sessionId": "tutor_test-id"},
        )

        from api.handler import handler

        response = handler(event, lambda_context)
        assert response["statusCode"] == 422


class TestEndSession:
    """DELETE /tutor/sessions/{sessionId} endpoint tests."""

    def test_end_session_success(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="DELETE",
            path="/tutor/sessions/tutor_test-id",
            path_parameters={"sessionId": "tutor_test-id"},
        )

        mock_session = _make_session(status="ended", ended_at="2026-03-07T10:30:00Z")

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc:
            mock_svc.end_session.return_value = mock_session
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "ended"

    def test_end_session_404_not_found(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="DELETE",
            path="/tutor/sessions/tutor_nonexistent",
            path_parameters={"sessionId": "tutor_nonexistent"},
        )

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc:
            from services.tutor_service import SessionNotFoundError

            mock_svc.end_session.side_effect = SessionNotFoundError("Not found")
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 404


class TestListSessions:
    """GET /tutor/sessions endpoint tests."""

    def test_list_sessions_success(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="GET",
            path="/tutor/sessions",
        )

        sessions = [_make_session(), _make_session(session_id="tutor_other-id")]

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc:
            mock_svc.list_sessions.return_value = sessions
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert len(body["sessions"]) == 2


class TestGetSession:
    """GET /tutor/sessions/{sessionId} endpoint tests."""

    def test_get_session_success(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="GET",
            path="/tutor/sessions/tutor_test-id",
            path_parameters={"sessionId": "tutor_test-id"},
        )

        mock_session = _make_session()

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc:
            mock_svc.get_session.return_value = mock_session
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["session_id"] == "tutor_test-session-id"

    def test_get_session_404(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="GET",
            path="/tutor/sessions/tutor_nonexistent",
            path_parameters={"sessionId": "tutor_nonexistent"},
        )

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc:
            from services.tutor_service import SessionNotFoundError

            mock_svc.get_session.side_effect = SessionNotFoundError("Not found")
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 404

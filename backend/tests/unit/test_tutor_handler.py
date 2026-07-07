"""Unit tests for tutor handler (ai-async-jobs 版).

create_session / send_message は同期検証（validate_start_session /
validate_send_message）+ ジョブ submit（202）に変換された。
失敗系は validate_* の例外で旧同期実装と同一のステータス・文言を検証する
（フロントは 422 + 文言で UI を出し分けるため文言互換が必須）。

AI 実行（start_session / send_message 本体）の検証は
tests/unit/test_ai_job_executors.py（TestExecuteTutor）へ、
TutorAIServiceError 等のワーカー時分類は tests/unit/test_ai_job_errors.py へ移設。
end_session / list_sessions / get_session は同期 API のまま変更なし。
"""

import json
from unittest.mock import patch


from models.tutor import TutorMessage, TutorSessionResponse

SUBMIT_START_RESULT = {
    "job_id": "aijob_t",
    "job_type": "tutor_start",
    "status": "queued",
}
SUBMIT_MESSAGE_RESULT = {
    "job_id": "aijob_t",
    "job_type": "tutor_message",
    "status": "queued",
}


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


class TestCreateSession:
    """POST /tutor/sessions endpoint tests (submit + 202)."""

    def test_create_session_success_returns_202(self, api_gateway_event, lambda_context):
        """事前検証を通過するとジョブが submit され 202 + job 情報が返る。"""
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions",
            body={"deck_id": "deck_001", "mode": "free_talk"},
        )

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc, patch(
            "api.handlers.tutor_handler.submit_ai_job"
        ) as mock_submit:
            mock_submit.return_value = dict(SUBMIT_START_RESULT)
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body == {
            "job_id": "aijob_t",
            "job_type": "tutor_start",
            "status": "queued",
        }
        mock_svc.validate_start_session.assert_called_once_with(
            user_id="test-user-id", deck_id="deck_001", mode="free_talk"
        )
        mock_submit.assert_called_once_with(
            user_id="test-user-id",
            job_type="tutor_start",
            payload={"deck_id": "deck_001", "mode": "free_talk"},
        )

    def test_create_session_invalid_mode(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions",
            body={"deck_id": "deck_001", "mode": "invalid_mode"},
        )

        with patch("api.handlers.tutor_handler.submit_ai_job") as mock_submit:
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        mock_submit.assert_not_called()

    def test_create_session_missing_deck_id(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions",
            body={"mode": "free_talk"},
        )

        with patch("api.handlers.tutor_handler.submit_ai_job") as mock_submit:
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        mock_submit.assert_not_called()

    def test_create_session_404_deck_not_found(self, api_gateway_event, lambda_context):
        """validate_start_session の DeckNotFoundError → 404 + 既存文言。"""
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions",
            body={"deck_id": "deck_missing", "mode": "free_talk"},
        )

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc, patch(
            "api.handlers.tutor_handler.submit_ai_job"
        ) as mock_submit:
            from services.tutor_service import DeckNotFoundError

            mock_svc.validate_start_session.side_effect = DeckNotFoundError(
                "Deck not found: deck_missing"
            )
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert body["error"] == "Deck not found: deck_missing"
        mock_submit.assert_not_called()

    def test_create_session_422_empty_deck(self, api_gateway_event, lambda_context):
        """validate_start_session の EmptyDeckError → 422 + 既存文言
        （フロントはこの文言で UI を出し分ける）。"""
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions",
            body={"deck_id": "deck_001", "mode": "free_talk"},
        )
        message = (
            "このデッキにはカードがありません。カードを追加してからセッションを開始してください。"
        )

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc, patch(
            "api.handlers.tutor_handler.submit_ai_job"
        ) as mock_submit:
            from services.tutor_service import EmptyDeckError

            mock_svc.validate_start_session.side_effect = EmptyDeckError(message)
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 422
        body = json.loads(response["body"])
        assert body["error"] == message
        mock_submit.assert_not_called()

    def test_create_session_422_insufficient_review_data(
        self, api_gateway_event, lambda_context
    ):
        """validate_start_session の InsufficientReviewDataError → 422 + 既存文言。"""
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions",
            body={"deck_id": "deck_001", "mode": "weak_point"},
        )
        message = "レビュー履歴が不足しています。Free Talk モードをお試しください。"

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc, patch(
            "api.handlers.tutor_handler.submit_ai_job"
        ) as mock_submit:
            from services.tutor_service import InsufficientReviewDataError

            mock_svc.validate_start_session.side_effect = InsufficientReviewDataError(
                message
            )
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 422
        body = json.loads(response["body"])
        assert body["error"] == message
        mock_submit.assert_not_called()

    def test_create_session_500_on_tutor_service_error(
        self, api_gateway_event, lambda_context
    ):
        """validate_start_session の TutorServiceError → 500 + 既存文言。"""
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions",
            body={"deck_id": "deck_001", "mode": "free_talk"},
        )

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc, patch(
            "api.handlers.tutor_handler.submit_ai_job"
        ) as mock_submit:
            from services.tutor_service import TutorServiceError

            mock_svc.validate_start_session.side_effect = TutorServiceError("boom")
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "チューターセッションの開始に失敗しました。"
        mock_submit.assert_not_called()


class TestSendMessage:
    """POST /tutor/sessions/{sessionId}/messages endpoint tests (submit + 202)."""

    def test_send_message_success_returns_202(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions/tutor_test-id/messages",
            body={"content": "appleについて教えて"},
            path_parameters={"sessionId": "tutor_test-id"},
        )

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc, patch(
            "api.handlers.tutor_handler.submit_ai_job"
        ) as mock_submit:
            mock_submit.return_value = dict(SUBMIT_MESSAGE_RESULT)
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body == {
            "job_id": "aijob_t",
            "job_type": "tutor_message",
            "status": "queued",
        }
        mock_svc.validate_send_message.assert_called_once_with(
            user_id="test-user-id", session_id="tutor_test-id"
        )
        mock_submit.assert_called_once_with(
            user_id="test-user-id",
            job_type="tutor_message",
            payload={"session_id": "tutor_test-id", "content": "appleについて教えて"},
        )

    def test_send_message_404_session_not_found(self, api_gateway_event, lambda_context):
        """validate_send_message の SessionNotFoundError → 404 + 既存文言。"""
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions/tutor_test-id/messages",
            body={"content": "hello"},
            path_parameters={"sessionId": "tutor_test-id"},
        )

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc, patch(
            "api.handlers.tutor_handler.submit_ai_job"
        ) as mock_submit:
            from services.tutor_service import SessionNotFoundError

            mock_svc.validate_send_message.side_effect = SessionNotFoundError(
                "Not found"
            )
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert body["error"] == "Session not found: tutor_test-id"
        mock_submit.assert_not_called()

    def test_send_message_429_message_limit(self, api_gateway_event, lambda_context):
        """validate_send_message の MessageLimitError → 429 + 既存文言（409 に変更しない）。"""
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions/tutor_test-id/messages",
            body={"content": "hello"},
            path_parameters={"sessionId": "tutor_test-id"},
        )

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc, patch(
            "api.handlers.tutor_handler.submit_ai_job"
        ) as mock_submit:
            from services.tutor_service import MessageLimitError

            mock_svc.validate_send_message.side_effect = MessageLimitError("limit")
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 429
        body = json.loads(response["body"])
        assert body["error"] == "Session has reached message limit: tutor_test-id"
        mock_submit.assert_not_called()

    def test_send_message_409_ended_session(self, api_gateway_event, lambda_context):
        """validate_send_message の SessionEndedError → 409 + 既存文言。"""
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions/tutor_test-id/messages",
            body={"content": "hello"},
            path_parameters={"sessionId": "tutor_test-id"},
        )

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc, patch(
            "api.handlers.tutor_handler.submit_ai_job"
        ) as mock_submit:
            from services.tutor_service import SessionEndedError

            mock_svc.validate_send_message.side_effect = SessionEndedError(
                "Session ended"
            )
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 409
        body = json.loads(response["body"])
        assert body["error"] == "Session is ended or timed out: tutor_test-id"
        mock_submit.assert_not_called()

    def test_send_message_empty_content(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions/tutor_test-id/messages",
            body={"content": ""},
            path_parameters={"sessionId": "tutor_test-id"},
        )

        with patch("api.handlers.tutor_handler.submit_ai_job") as mock_submit:
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        mock_submit.assert_not_called()

    def test_send_message_500_on_tutor_service_error(
        self, api_gateway_event, lambda_context
    ):
        """validate_send_message の TutorServiceError → 500 + 既存文言。"""
        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions/tutor_test-id/messages",
            body={"content": "hello"},
            path_parameters={"sessionId": "tutor_test-id"},
        )

        with patch("api.handlers.tutor_handler.tutor_service") as mock_svc, patch(
            "api.handlers.tutor_handler.submit_ai_job"
        ) as mock_submit:
            from services.tutor_service import TutorServiceError

            mock_svc.validate_send_message.side_effect = TutorServiceError("boom")
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "メッセージの送信に失敗しました。"
        mock_submit.assert_not_called()


class TestEndSession:
    """DELETE /tutor/sessions/{sessionId} endpoint tests（同期のまま変更なし）."""

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
    """GET /tutor/sessions endpoint tests（同期のまま変更なし）."""

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
    """GET /tutor/sessions/{sessionId} endpoint tests（同期のまま変更なし）."""

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

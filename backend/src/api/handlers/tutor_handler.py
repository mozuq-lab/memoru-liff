"""Tutor API route handlers."""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from pydantic import ValidationError

from api.shared import get_user_id_from_context, make_validation_error_response
from models.tutor import (
    SendMessageRequest,
    SessionListResponse,
    StartSessionRequest,
)
from services.tutor_service import (
    ConcurrentSendError,
    DeckNotFoundError,
    EmptyDeckError,
    InsufficientReviewDataError,
    MessageLimitError,
    SessionEndedError,
    SessionNotFoundError,
    TutorService,
    TutorServiceError,
)
from services.tutor_ai_service import TutorAITimeoutError, TutorAIServiceError

logger = Logger()
tracer = Tracer()
router = Router()

tutor_service = TutorService()

# list_sessions の status クエリパラメータ許可リスト (models/tutor.py の Literal と一致)
VALID_SESSION_STATUSES = frozenset({"active", "ended", "timed_out"})


@router.post("/tutor/sessions")
@tracer.capture_method
def create_session():
    """Start a new tutor session."""
    user_id = get_user_id_from_context(router)

    try:
        body = router.current_event.json_body
        if not isinstance(body, dict):
            return Response(
                status_code=400,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps({"error": "Request body must be a JSON object"}),
            )
        request = StartSessionRequest(**body)
    except ValidationError as e:
        logger.warning("Validation error", extra={"error": str(e)})
        return make_validation_error_response(e)
    except json.JSONDecodeError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid JSON body"}),
        )

    try:
        session = tutor_service.start_session(
            user_id=user_id,
            deck_id=request.deck_id,
            mode=request.mode,
        )
        return Response(
            status_code=201,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps(session.model_dump(mode="json")),
        )
    except DeckNotFoundError as e:
        return Response(
            status_code=404,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": str(e)}),
        )
    except InsufficientReviewDataError as e:
        return Response(
            status_code=422,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": str(e)}),
        )
    except EmptyDeckError as e:
        return Response(
            status_code=422,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": str(e)}),
        )
    except TutorAITimeoutError:
        logger.warning("AI greeting timed out during session creation")
        return Response(
            status_code=504,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "AI応答がタイムアウトしました。もう一度お試しください。"}),
        )
    except TutorAIServiceError as e:
        # USE_STRANDS=false 等で BedrockTutorAIService が SessionManager を拒否する等、
        # AI サービスの構成不備/利用不可。原因不明の 500 ではなく 503 で明示する (N-1)。
        logger.error(
            "Tutor AI service unavailable during session creation "
            "(check USE_STRANDS / model configuration)",
            extra={"error": str(e)},
        )
        return Response(
            status_code=503,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps(
                {"error": "チューター機能が現在利用できません。", "code": "tutor_unavailable"}
            ),
        )
    except TutorServiceError as e:
        logger.error("Failed to start tutor session", extra={"error": str(e)})
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "チューターセッションの開始に失敗しました。"}),
        )


@router.post("/tutor/sessions/<session_id>/messages")
@tracer.capture_method
def send_message(session_id: str):
    """Send message to tutor and get response."""
    user_id = get_user_id_from_context(router)

    try:
        body = router.current_event.json_body
        if not isinstance(body, dict):
            return Response(
                status_code=400,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps({"error": "Request body must be a JSON object"}),
            )
        request = SendMessageRequest(**body)
    except ValidationError as e:
        logger.warning("Validation error", extra={"error": str(e)})
        return make_validation_error_response(e)
    except json.JSONDecodeError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid JSON body"}),
        )

    try:
        result = tutor_service.send_message(
            user_id=user_id,
            session_id=session_id,
            content=request.content,
        )
        return result.model_dump(mode="json")
    except SessionNotFoundError:
        return Response(
            status_code=404,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": f"Session not found: {session_id}"}),
        )
    except MessageLimitError:
        return Response(
            status_code=429,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": f"Session has reached message limit: {session_id}"}),
        )
    except ConcurrentSendError:
        return Response(
            status_code=409,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps(
                {"error": "別のメッセージを処理中です。少し待ってからお試しください。"}
            ),
        )
    except SessionEndedError:
        return Response(
            status_code=409,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": f"Session is ended or timed out: {session_id}"}),
        )
    except TutorAITimeoutError:
        logger.warning("AI response timed out", extra={"session_id": session_id})
        return Response(
            status_code=504,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "AI応答がタイムアウトしました。もう一度お試しください。"}),
        )
    except TutorAIServiceError as e:
        # AI サービスの構成不備/利用不可 (例: USE_STRANDS=false)。503 で明示する (N-1)。
        logger.error(
            "Tutor AI service unavailable while sending message "
            "(check USE_STRANDS / model configuration)",
            extra={"error": str(e), "session_id": session_id},
        )
        return Response(
            status_code=503,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps(
                {"error": "チューター機能が現在利用できません。", "code": "tutor_unavailable"}
            ),
        )
    except TutorServiceError as e:
        logger.error("Failed to send message", extra={"error": str(e), "session_id": session_id})
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "メッセージの送信に失敗しました。"}),
        )


@router.delete("/tutor/sessions/<session_id>")
@tracer.capture_method
def end_session(session_id: str):
    """End a tutor session."""
    user_id = get_user_id_from_context(router)

    try:
        session = tutor_service.end_session(
            user_id=user_id,
            session_id=session_id,
        )
        return session.model_dump(mode="json")
    except SessionNotFoundError:
        return Response(
            status_code=404,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": f"Session not found: {session_id}"}),
        )
    except SessionEndedError:
        return Response(
            status_code=409,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": f"Session is already ended: {session_id}"}),
        )


@router.get("/tutor/sessions")
@tracer.capture_method
def list_sessions():
    """List tutor sessions for current user."""
    user_id = get_user_id_from_context(router)

    params = router.current_event.query_string_parameters or {}
    status = params.get("status")
    deck_id = params.get("deck_id")

    # L-2/L-4: status は許可リストで検証し、不正値は 400 を返す
    # (未検証だと存在しない status で原因不明の空リストが返るため)。
    if status is not None and status not in VALID_SESSION_STATUSES:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps(
                {"error": "Invalid status. Use 'active', 'ended', or 'timed_out'."}
            ),
        )

    sessions = tutor_service.list_sessions(
        user_id=user_id,
        status=status,
        deck_id=deck_id,
    )
    return SessionListResponse(
        sessions=[s.model_dump(mode="json") for s in sessions],
        total=len(sessions),
    ).model_dump(mode="json")


@router.get("/tutor/sessions/<session_id>")
@tracer.capture_method
def get_session(session_id: str):
    """Get full session details."""
    user_id = get_user_id_from_context(router)

    try:
        session = tutor_service.get_session(
            user_id=user_id,
            session_id=session_id,
        )
        return session.model_dump(mode="json")
    except SessionNotFoundError:
        return Response(
            status_code=404,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": f"Session not found: {session_id}"}),
        )

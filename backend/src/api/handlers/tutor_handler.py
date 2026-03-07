"""Tutor API route handlers."""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from pydantic import ValidationError

from api.shared import get_user_id_from_context
from models.tutor import (
    SendMessageRequest,
    SessionListResponse,
    StartSessionRequest,
)
from services.tutor_service import (
    SessionEndedError,
    SessionNotFoundError,
    TutorService,
    TutorServiceError,
)

logger = Logger()
tracer = Tracer()
router = Router()

tutor_service = TutorService()


@router.post("/tutor/sessions")
@tracer.capture_method
def create_session():
    """Start a new tutor session."""
    user_id = get_user_id_from_context(router)

    try:
        body = router.current_event.json_body
        request = StartSessionRequest(**body)
    except ValidationError as e:
        return Response(
            status_code=422,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Validation error", "details": e.errors()}),
        )
    except json.JSONDecodeError:
        return Response(
            status_code=422,
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
    except TutorServiceError as e:
        logger.error("Failed to start tutor session", extra={"error": str(e)})
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": str(e)}),
        )


@router.post("/tutor/sessions/<session_id>/messages")
@tracer.capture_method
def send_message(session_id: str):
    """Send message to tutor and get response."""
    user_id = get_user_id_from_context(router)

    try:
        body = router.current_event.json_body
        request = SendMessageRequest(**body)
    except ValidationError as e:
        return Response(
            status_code=422,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Validation error", "details": e.errors()}),
        )
    except json.JSONDecodeError:
        return Response(
            status_code=422,
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
    except SessionEndedError:
        return Response(
            status_code=409,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": f"Session is ended or timed out: {session_id}"}),
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

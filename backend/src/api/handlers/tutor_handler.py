"""Tutor API route handlers."""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router

from api.shared import (
    check_ai_rate_limit,
    get_user_id_from_context,
    make_job_accepted_response,
    parse_json_body,
)
from models.tutor import (
    SendMessageRequest,
    SessionListResponse,
    StartSessionRequest,
)
from services.ai_job_service import submit_ai_job
from services.tutor_service import (
    DeckNotFoundError,
    EmptyDeckError,
    InsufficientReviewDataError,
    MessageLimitError,
    SessionEndedError,
    SessionNotFoundError,
    TutorService,
    TutorServiceError,
)

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

    rate_limited = check_ai_rate_limit(user_id)
    if rate_limited:
        return rate_limited

    parsed = parse_json_body(router, StartSessionRequest)
    if isinstance(parsed, Response):
        return parsed
    request = parsed

    # ai-async-jobs: 事前検証（fail-fast）のみ同期で行い、AI 実行はワーカーに委ねる。
    # ステータス・文言は変換前の同期実装と完全一致させる（フロントは 422 + 文言で
    # UI を出し分ける。設計レビュー C-3）。
    try:
        tutor_service.validate_start_session(
            user_id=user_id,
            deck_id=request.deck_id,
            mode=request.mode,
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
    except TutorServiceError as e:
        logger.error("Failed to validate tutor session start", extra={"error": str(e)})
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "チューターセッションの開始に失敗しました。"}),
        )

    try:
        job = submit_ai_job(
            user_id=user_id,
            job_type="tutor_start",
            payload={
                "deck_id": request.deck_id,
                "mode": request.mode,
            },
        )
    except Exception as e:
        # submit（DynamoDB/SQS）の一時障害を Lambda 未処理例外として漏らさない
        # （実装レビュー #1）。
        logger.error("Failed to submit tutor_start job", extra={"error": str(e)})
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "チューターセッションの開始に失敗しました。"}),
        )
    return make_job_accepted_response(job)


@router.post("/tutor/sessions/<session_id>/messages")
@tracer.capture_method
def send_message(session_id: str):
    """Send message to tutor and get response."""
    user_id = get_user_id_from_context(router)

    rate_limited = check_ai_rate_limit(user_id)
    if rate_limited:
        return rate_limited

    parsed = parse_json_body(router, SendMessageRequest)
    if isinstance(parsed, Response):
        return parsed
    request = parsed

    # ai-async-jobs: 事前検証（fail-fast）のみ同期で行い、AI 実行はワーカーに委ねる。
    # in-flight ロック取得と最終的な状態遷移の権威はワーカー内の send_message が持つ
    # （二重 submit はワーカーで ConcurrentSendError → failed(409) になる）。
    try:
        tutor_service.validate_send_message(user_id=user_id, session_id=session_id)
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
    except SessionEndedError:
        return Response(
            status_code=409,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": f"Session is ended or timed out: {session_id}"}),
        )
    except TutorServiceError as e:
        logger.error("Failed to validate message send", extra={"error": str(e), "session_id": session_id})
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "メッセージの送信に失敗しました。"}),
        )

    try:
        job = submit_ai_job(
            user_id=user_id,
            job_type="tutor_message",
            payload={
                "session_id": session_id,
                "content": request.content,
            },
        )
    except Exception as e:
        logger.error(
            "Failed to submit tutor_message job",
            extra={"error": str(e), "session_id": session_id},
        )
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "メッセージの送信に失敗しました。"}),
        )
    return make_job_accepted_response(job)


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

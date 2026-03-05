"""Main API handler for Memoru LIFF application.

Routes API Gateway events to domain-specific handlers via Lambda Powertools Router.
Standalone Lambda handlers (grade_ai, advice) remain in this file.
"""

import dataclasses
import json
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

from api.shared import get_user_id_from_context, get_user_id_from_event, map_ai_error_to_http
from api.handlers.user_handler import router as user_router
from api.handlers.cards_handler import router as cards_router
from api.handlers.decks_handler import router as decks_router
from api.handlers.review_handler import router as review_router
from api.handlers.ai_handler import router as ai_router
from api.handlers.stats_handler import router as stats_router

# Standalone handler dependencies
from models.grading import GradeAnswerRequest, GradeAnswerResponse
from models.advice import LearningAdviceResponse
from pydantic import ValidationError
from services.card_service import CardService, CardNotFoundError
from services.review_service import ReviewService
from services.ai_service import create_ai_service, AIServiceError

logger = Logger()
tracer = Tracer()
app = APIGatewayHttpResolver()

# Register domain routers
app.include_router(user_router)
app.include_router(cards_router)
app.include_router(decks_router)
app.include_router(review_router)
app.include_router(ai_router)
app.include_router(stats_router)

# Services for standalone Lambda handlers
card_service = CardService()
review_service = ReviewService()


# Keep backward compatibility alias
_map_ai_error_to_http = map_ai_error_to_http


def _make_lambda_response(status_code: int, body: dict) -> dict:
    """Create a Lambda proxy integration response dict."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


# =============================================================================
# Standalone Lambda Handlers
# =============================================================================


def grade_ai_handler(event: dict, context: Any) -> dict:
    """POST /reviews/{cardId}/grade-ai の Lambda ハンドラー。

    独立 Lambda 関数として API Gateway HTTP API v2 イベントを直接受け取る。
    """
    try:
        user_id = get_user_id_from_event(event)
        if not user_id:
            return _make_lambda_response(401, {"error": "Unauthorized"})

        path_params = event.get("pathParameters") or {}
        card_id = path_params.get("cardId")
        if not card_id:
            return _make_lambda_response(400, {"error": "card_id is required"})

        logger.info(
            "Grade AI request",
            extra={"card_id": card_id, "user_id": user_id, "user_answer_length": len(event.get("body") or "")},
        )

        body_str = event.get("body") or ""
        try:
            body_dict = json.loads(body_str)
            request = GradeAnswerRequest(**body_dict)
        except json.JSONDecodeError:
            return _make_lambda_response(400, {"error": "Invalid request body"})
        except ValidationError as e:
            try:
                details = json.loads(e.json())
            except Exception:
                details = []
            return _make_lambda_response(400, {"error": "Invalid request body", "details": details})

        language = (event.get("queryStringParameters") or {}).get("language", "ja")

        try:
            card = card_service.get_card(user_id, card_id)
        except CardNotFoundError:
            return _make_lambda_response(404, {"error": "Not Found"})

        try:
            ai_service = create_ai_service()
            result = ai_service.grade_answer(
                card_front=card.front,
                card_back=card.back,
                user_answer=request.user_answer,
                language=language,
            )
        except AIServiceError as e:
            logger.warning(
                "AI service error grading card",
                extra={"card_id": card_id, "user_id": user_id, "error_type": type(e).__name__, "error": str(e)},
            )
            ai_response = _map_ai_error_to_http(e)
            return {
                "statusCode": ai_response.status_code,
                "headers": {"Content-Type": "application/json"},
                "body": ai_response.body,
            }

        logger.info(
            "Grade AI succeeded",
            extra={"card_id": card_id, "grade": result.grade, "model": result.model_used},
        )
        response = GradeAnswerResponse(
            grade=result.grade,
            reasoning=result.reasoning,
            card_front=card.front,
            card_back=card.back,
            grading_info={
                "model_used": result.model_used,
                "processing_time_ms": result.processing_time_ms,
            },
        )
        return _make_lambda_response(200, response.model_dump(mode="json"))

    except Exception as e:
        logger.error("Unexpected error in grade_ai_handler", extra={"error": str(e)})
        return _make_lambda_response(500, {"error": "Internal Server Error"})


def advice_handler(event: dict, context: Any) -> dict:
    """GET /advice の Lambda ハンドラー。

    独立 Lambda 関数として API Gateway HTTP API v2 イベントを直接受け取る。
    """
    try:
        user_id = get_user_id_from_event(event)
        if not user_id:
            return _make_lambda_response(401, {"error": "Unauthorized"})

        logger.info("Advice request", extra={"user_id": user_id})

        language = (event.get("queryStringParameters") or {}).get("language", "ja")

        review_summary = review_service.get_review_summary(user_id)
        review_summary_dict = dataclasses.asdict(review_summary)

        try:
            ai_service = create_ai_service()
            result = ai_service.get_learning_advice(
                review_summary=review_summary_dict,
                language=language,
            )
        except AIServiceError as e:
            logger.warning(
                "AI service error getting advice",
                extra={"user_id": user_id, "error_type": type(e).__name__, "error": str(e)},
            )
            ai_response = _map_ai_error_to_http(e)
            return {
                "statusCode": ai_response.status_code,
                "headers": {"Content-Type": "application/json"},
                "body": ai_response.body,
            }

        logger.info(
            "Advice succeeded",
            extra={"user_id": user_id, "model": result.model_used, "time_ms": result.processing_time_ms},
        )
        response = LearningAdviceResponse(
            advice_text=result.advice_text,
            weak_areas=result.weak_areas,
            recommendations=result.recommendations,
            study_stats={
                "total_reviews": review_summary.total_reviews,
                "average_grade": review_summary.average_grade,
                "total_cards": review_summary.total_cards,
                "cards_due_today": review_summary.cards_due_today,
                "streak_days": review_summary.streak_days,
            },
            advice_info={
                "model_used": result.model_used,
                "processing_time_ms": result.processing_time_ms,
            },
        )
        return _make_lambda_response(200, response.model_dump(mode="json"))

    except Exception as e:
        logger.error("Unexpected error in advice_handler", extra={"error": str(e)})
        return _make_lambda_response(500, {"error": "Internal Server Error"})


def url_generate_handler(event: dict, context: Any) -> dict:
    """POST /cards/generate-from-url の Lambda ハンドラー。

    専用 Lambda 関数（120s タイムアウト、512MB メモリ）として実行される。
    """
    return handler(event, context)


# =============================================================================
# Lambda Handler
# =============================================================================


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler for API Gateway events."""
    stage = event.get("requestContext", {}).get("stage", "$default")
    raw_path = event.get("rawPath", "/")
    if stage != "$default" and not raw_path.startswith(f"/{stage}"):
        event["rawPath"] = f"/{stage}{raw_path}"
    return app.resolve(event, context)

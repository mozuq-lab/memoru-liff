"""Stats API route handlers."""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router

from api.shared import get_user_id_from_context
from services.stats_service import StatsService
from services.user_service import UserService

logger = Logger()
tracer = Tracer()
router = Router()

stats_service = StatsService()
user_service = UserService()


def _get_user_timezone(user_id: str) -> str:
    """ユーザー設定からタイムゾーンを取得する（streak・「今日」判定用）。

    review_handler と同じパターン。設定が無い場合はアプリ既定の Asia/Tokyo。
    """
    user = user_service.get_or_create_user(user_id)
    return user.settings.get("timezone", "Asia/Tokyo")


@router.get("/stats")
@tracer.capture_method
def get_stats():
    """Get learning statistics summary."""
    user_id = get_user_id_from_context(router)
    logger.info("Getting stats", extra={"user_id": user_id})

    try:
        user_timezone = _get_user_timezone(user_id)
        response = stats_service.get_stats(user_id, user_timezone=user_timezone)
        return response.model_dump(mode="json")
    except Exception as e:
        logger.error("Error getting stats", extra={"error": str(e)})
        raise


@router.get("/stats/weak-cards")
@tracer.capture_method
def get_weak_cards():
    """Get weak cards list."""
    user_id = get_user_id_from_context(router)
    logger.info("Getting weak cards", extra={"user_id": user_id})

    params = router.current_event.query_string_parameters or {}
    try:
        limit = max(1, min(int(params.get("limit", 10)), 50))
    except (ValueError, TypeError):
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "limit must be a positive integer"}),
        )

    try:
        response = stats_service.get_weak_cards(user_id, limit=limit)
        return response.model_dump(mode="json")
    except Exception as e:
        logger.error("Error getting weak cards", extra={"error": str(e)})
        raise


@router.get("/stats/forecast")
@tracer.capture_method
def get_forecast():
    """Get review forecast."""
    user_id = get_user_id_from_context(router)
    logger.info("Getting forecast", extra={"user_id": user_id})

    params = router.current_event.query_string_parameters or {}
    try:
        days = max(1, min(int(params.get("days", 7)), 30))
    except (ValueError, TypeError):
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "days must be a positive integer"}),
        )

    try:
        user_timezone = _get_user_timezone(user_id)
        response = stats_service.get_forecast(
            user_id, days=days, user_timezone=user_timezone
        )
        return response.model_dump(mode="json")
    except Exception as e:
        logger.error("Error getting forecast", extra={"error": str(e)})
        raise

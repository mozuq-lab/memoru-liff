"""Review API route handlers."""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from pydantic import ValidationError

from api.shared import get_user_id_from_context, make_validation_error_response
from models.review import ReviewRequest
from services.card_service import CardNotFoundError
from services.review_service import (
    ReviewService,
    InvalidGradeError,
    NoReviewHistoryError,
)
from services.user_service import UserService

logger = Logger()
tracer = Tracer()
router = Router()

review_service = ReviewService()
user_service = UserService()


@router.get("/cards/due")
@tracer.capture_method
def get_due_cards():
    """Get cards due for review."""
    user_id = get_user_id_from_context(router)
    logger.info("Getting due cards", extra={"user_id": user_id})

    params = router.current_event.query_string_parameters or {}
    try:
        limit = min(int(params.get("limit", 20)), 100)
    except (ValueError, TypeError):
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "limit must be a positive integer"}),
        )
    include_future = params.get("include_future", "false").lower() == "true"
    deck_id = params.get("deck_id")

    try:
        response = review_service.get_due_cards(
            user_id=user_id,
            limit=limit,
            include_future=include_future,
            deck_id=deck_id,
        )
        return response.model_dump(mode="json")
    except Exception as e:
        logger.error("Error getting due cards", extra={"error": str(e)})
        raise


@router.post("/reviews/<card_id>")
@tracer.capture_method
def submit_review(card_id: str):
    """Submit a review for a card."""
    user_id = get_user_id_from_context(router)
    logger.info("Submitting review", extra={"card_id": card_id, "user_id": user_id})

    try:
        body = router.current_event.json_body
        request = ReviewRequest(**body)
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
        # Get user settings for day boundary normalization
        user = user_service.get_or_create_user(user_id)
        user_timezone = user.settings.get("timezone", "Asia/Tokyo")
        day_start_hour = user.settings.get("day_start_hour", 4)

        response = review_service.submit_review(
            user_id=user_id,
            card_id=card_id,
            grade=request.grade,
            user_timezone=user_timezone,
            day_start_hour=day_start_hour,
        )
        return response.model_dump(mode="json")
    except CardNotFoundError:
        raise NotFoundError(f"Card not found: {card_id}")
    except InvalidGradeError as e:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": str(e)}),
        )
    except Exception as e:
        logger.error("Error submitting review", extra={"card_id": card_id, "error": str(e)})
        raise


@router.post("/reviews/<card_id>/undo")
@tracer.capture_method
def undo_review(card_id: str):
    """Undo the latest review for a card."""
    user_id = get_user_id_from_context(router)
    logger.info("Undoing review", extra={"card_id": card_id, "user_id": user_id})

    try:
        response = review_service.undo_review(
            user_id=user_id,
            card_id=card_id,
        )
        return response.model_dump(mode="json")
    except CardNotFoundError:
        raise NotFoundError(f"Card not found: {card_id}")
    except NoReviewHistoryError as e:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": str(e)}),
        )
    except Exception as e:
        logger.error("Error undoing review", extra={"card_id": card_id, "error": str(e)})
        raise

"""Review API route handlers."""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from pydantic import ValidationError

from api.shared import get_user_id_from_context
from models.review import ReviewRequest
from services.card_service import CardNotFoundError
from services.review_service import (
    ReviewService,
    InvalidGradeError,
    NoReviewHistoryError,
)

logger = Logger()
tracer = Tracer()
router = Router()

review_service = ReviewService()


@router.get("/cards/due")
@tracer.capture_method
def get_due_cards():
    """Get cards due for review."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Getting due cards for user_id: {user_id}")

    params = router.current_event.query_string_parameters or {}
    limit = min(int(params.get("limit", 20)), 100)
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
        logger.error(f"Error getting due cards: {e}")
        raise


@router.post("/reviews/<card_id>")
@tracer.capture_method
def submit_review(card_id: str):
    """Submit a review for a card."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Submitting review for card {card_id} by user_id: {user_id}")

    try:
        body = router.current_event.json_body
        request = ReviewRequest(**body)
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid request", "details": e.errors()}),
        )
    except json.JSONDecodeError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid JSON body"}),
        )

    try:
        response = review_service.submit_review(
            user_id=user_id,
            card_id=card_id,
            grade=request.grade,
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
        logger.error(f"Error submitting review: {e}")
        raise


@router.post("/reviews/<card_id>/undo")
@tracer.capture_method
def undo_review(card_id: str):
    """Undo the latest review for a card."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Undoing review for card {card_id} by user_id: {user_id}")

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
        logger.error(f"Error undoing review: {e}")
        raise

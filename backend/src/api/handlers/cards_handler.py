"""Card API route handlers."""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from pydantic import ValidationError

from api.shared import get_user_id_from_context
from models.card import CreateCardRequest, UpdateCardRequest, CardListResponse
from services.user_service import UserService
from services.card_service import (
    CardService,
    CardNotFoundError,
    CardLimitExceededError,
)

logger = Logger()
tracer = Tracer()
router = Router()

user_service = UserService()
card_service = CardService()


@router.get("/cards")
@tracer.capture_method
def list_cards():
    """List cards for the current user."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Listing cards for user_id: {user_id}")

    params = router.current_event.query_string_parameters or {}
    limit = min(int(params.get("limit", 50)), 100)
    cursor = params.get("cursor")
    deck_id = params.get("deck_id")

    try:
        cards, next_cursor = card_service.list_cards(
            user_id=user_id,
            limit=limit,
            cursor=cursor,
            deck_id=deck_id,
        )
        return CardListResponse(
            cards=[card.to_response() for card in cards],
            total=len(cards),
            next_cursor=next_cursor,
        ).model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error listing cards: {e}")
        raise


@router.post("/cards")
@tracer.capture_method
def create_card():
    """Create a new card."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Creating card for user_id: {user_id}")

    try:
        body = router.current_event.json_body
        request = CreateCardRequest(**body)
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
        user_service.get_or_create_user(user_id)

        card = card_service.create_card(
            user_id=user_id,
            front=request.front,
            back=request.back,
            deck_id=request.deck_id,
            tags=request.tags,
        )
        return Response(
            status_code=201,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps(card.to_response().model_dump(mode="json")),
        )
    except CardLimitExceededError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Card limit exceeded. Maximum 2000 cards per user."}),
        )
    except Exception as e:
        logger.error(f"Error creating card: {e}")
        raise


@router.get("/cards/<card_id>")
@tracer.capture_method
def get_card(card_id: str):
    """Get a specific card."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Getting card {card_id} for user_id: {user_id}")

    try:
        card = card_service.get_card(user_id, card_id)
        return card.to_response().model_dump(mode="json")
    except CardNotFoundError:
        raise NotFoundError(f"Card not found: {card_id}")
    except Exception as e:
        logger.error(f"Error getting card: {e}")
        raise


@router.put("/cards/<card_id>")
@tracer.capture_method
def update_card(card_id: str):
    """Update a card."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Updating card {card_id} for user_id: {user_id}")

    try:
        body = router.current_event.json_body
        request = UpdateCardRequest(**body)
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
        # Determine deck_id: distinguish JSON null from missing key
        update_kwargs = {
            "user_id": user_id,
            "card_id": card_id,
            "front": request.front,
            "back": request.back,
            "tags": request.tags,
            "interval": request.interval,
        }
        if "deck_id" in body:
            # Key present in JSON → pass value (None for null, string for value)
            update_kwargs["deck_id"] = body["deck_id"]

        card = card_service.update_card(**update_kwargs)
        return card.to_response().model_dump(mode="json")
    except CardNotFoundError:
        raise NotFoundError(f"Card not found: {card_id}")
    except Exception as e:
        logger.error(f"Error updating card: {e}")
        raise


@router.delete("/cards/<card_id>")
@tracer.capture_method
def delete_card(card_id: str):
    """Delete a card."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Deleting card {card_id} for user_id: {user_id}")

    try:
        card_service.delete_card(user_id, card_id)
        return Response(
            status_code=204,
            content_type=content_types.APPLICATION_JSON,
            body="",
        )
    except CardNotFoundError:
        raise NotFoundError(f"Card not found: {card_id}")
    except Exception as e:
        logger.error(f"Error deleting card: {e}")
        raise

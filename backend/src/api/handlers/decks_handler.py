"""Deck API route handlers."""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from pydantic import ValidationError

from api.shared import get_user_id_from_context
from models.deck import CreateDeckRequest, UpdateDeckRequest, DeckListResponse
from services.deck_service import (
    DeckService,
    DeckNotFoundError,
    DeckLimitExceededError,
)

logger = Logger()
tracer = Tracer()
router = Router()

deck_service = DeckService()


@router.post("/decks")
@tracer.capture_method
def create_deck():
    """Create a new deck."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Creating deck for user_id: {user_id}")

    try:
        body = router.current_event.json_body
        request = CreateDeckRequest(**body)
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid request", "details": str(e)}),
        )
    except json.JSONDecodeError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid JSON body"}),
        )

    try:
        deck = deck_service.create_deck(
            user_id=user_id,
            name=request.name,
            description=request.description,
            color=request.color,
        )
        return Response(
            status_code=201,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps(deck.to_response().model_dump(mode="json")),
        )
    except DeckLimitExceededError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Deck limit exceeded. Maximum 50 decks per user."}),
        )
    except Exception as e:
        logger.error(f"Error creating deck: {e}")
        raise


@router.get("/decks")
@tracer.capture_method
def list_decks():
    """List all decks for the current user."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Listing decks for user_id: {user_id}")

    try:
        decks = deck_service.list_decks(user_id)

        deck_ids = [d.deck_id for d in decks]
        card_counts = deck_service.get_deck_card_counts(user_id, deck_ids)
        due_counts = deck_service.get_deck_due_counts(user_id, deck_ids)

        return DeckListResponse(
            decks=[
                d.to_response(
                    card_count=card_counts.get(d.deck_id, 0),
                    due_count=due_counts.get(d.deck_id, 0),
                )
                for d in decks
            ],
            total=len(decks),
        ).model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error listing decks: {e}")
        raise


@router.put("/decks/<deck_id>")
@tracer.capture_method
def update_deck(deck_id: str):
    """Update a deck."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Updating deck {deck_id} for user_id: {user_id}")

    try:
        body = router.current_event.json_body
        request = UpdateDeckRequest(**body)
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid request", "details": str(e)}),
        )
    except json.JSONDecodeError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid JSON body"}),
        )

    try:
        deck = deck_service.update_deck(
            user_id=user_id,
            deck_id=deck_id,
            name=request.name,
            description=request.description,
            color=request.color,
        )
        card_counts = deck_service.get_deck_card_counts(user_id, [deck_id])
        due_counts = deck_service.get_deck_due_counts(user_id, [deck_id])

        return deck.to_response(
            card_count=card_counts.get(deck_id, 0),
            due_count=due_counts.get(deck_id, 0),
        ).model_dump(mode="json")
    except DeckNotFoundError:
        raise NotFoundError(f"Deck not found: {deck_id}")
    except Exception as e:
        logger.error(f"Error updating deck: {e}")
        raise


@router.delete("/decks/<deck_id>")
@tracer.capture_method
def delete_deck(deck_id: str):
    """Delete a deck."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Deleting deck {deck_id} for user_id: {user_id}")

    try:
        deck_service.delete_deck(user_id, deck_id)
        return Response(
            status_code=204,
            content_type=content_types.APPLICATION_JSON,
            body="",
        )
    except DeckNotFoundError:
        raise NotFoundError(f"Deck not found: {deck_id}")
    except Exception as e:
        logger.error(f"Error deleting deck: {e}")
        raise

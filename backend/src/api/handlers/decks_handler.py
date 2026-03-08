"""Deck API route handlers."""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from pydantic import ValidationError

from api.shared import get_user_id_from_context, make_validation_error_response
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
    logger.info("Creating deck", extra={"user_id": user_id})

    try:
        body = router.current_event.json_body
        request = CreateDeckRequest(**body)
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
            status_code=409,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Deck limit exceeded. Maximum 50 decks per user."}),
        )
    except Exception as e:
        logger.error("Error creating deck", extra={"error": str(e)})
        raise


@router.get("/decks")
@tracer.capture_method
def list_decks():
    """List all decks for the current user."""
    user_id = get_user_id_from_context(router)
    logger.info("Listing decks", extra={"user_id": user_id})

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
        logger.error("Error listing decks", extra={"error": str(e)})
        raise


@router.put("/decks/<deck_id>")
@tracer.capture_method
def update_deck(deck_id: str):
    """Update a deck."""
    user_id = get_user_id_from_context(router)
    logger.info("Updating deck", extra={"deck_id": deck_id, "user_id": user_id})

    try:
        # 【バリデーション + Sentinel 判別】: Pydantic でフォーマット検証し、
        # model_fields_set で送信されたフィールドを判別する。
        # raw body の key 存在チェックで null/未送信を判別する（Pydantic は
        # null と未送信を区別できないため）。
        body = router.current_event.json_body
        # 【Pydantic バリデーション】: color フォーマット等の検証を実行。
        # model_fields_set でどのフィールドが明示的に送信されたかを取得できるが、
        # null/未送信の判別には raw body の key 存在チェックが必要。
        validated = UpdateDeckRequest.model_validate(body)
        _ = validated.model_fields_set  # 送信されたフィールドセットを取得可能
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
        # 【Sentinel パターン適用】: JSON body の key 存在チェックで null/未送信を判別する
        # key が存在する場合は body の値（None または文字列）をそのまま渡す
        # key が存在しない場合は _UNSET（省略）を渡す → deck_service 側で「変更なし」と判定
        # 🔵 信頼性レベル: 青信号 - Red フェーズ Green 実装方針より
        update_kwargs = {}
        if "name" in body:
            update_kwargs["name"] = body["name"]
        if "description" in body:
            # 【null 通過】: description=None は REMOVE 操作として deck_service に渡す
            update_kwargs["description"] = body["description"]
        if "color" in body:
            # 【null 通過】: color=None は REMOVE 操作として deck_service に渡す
            update_kwargs["color"] = body["color"]

        deck = deck_service.update_deck(
            user_id=user_id,
            deck_id=deck_id,
            **update_kwargs,
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
        logger.error("Error updating deck", extra={"deck_id": deck_id, "error": str(e)})
        raise


@router.delete("/decks/<deck_id>")
@tracer.capture_method
def delete_deck(deck_id: str):
    """Delete a deck."""
    user_id = get_user_id_from_context(router)
    logger.info("Deleting deck", extra={"deck_id": deck_id, "user_id": user_id})

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
        logger.error("Error deleting deck", extra={"deck_id": deck_id, "error": str(e)})
        raise

"""Main API handler for Memoru LIFF application."""

import json
import os
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, Response, content_types
from aws_lambda_powertools.event_handler.exceptions import NotFoundError, BadRequestError, UnauthorizedError
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import ValidationError

from ..models.user import LinkLineRequest, LinkLineResponse, UserSettingsRequest, UserSettingsResponse
from ..models.card import CreateCardRequest, UpdateCardRequest, CardListResponse
from ..services.user_service import (
    UserService,
    UserNotFoundError,
    UserAlreadyLinkedError,
    LineUserIdAlreadyUsedError,
    LineNotLinkedError,
)
from ..services.card_service import (
    CardService,
    CardNotFoundError,
    CardLimitExceededError,
)
from ..services.review_service import (
    ReviewService,
    InvalidGradeError,
)
from ..models.review import ReviewRequest
from ..models.generate import (
    GenerateCardsRequest,
    GenerateCardsResponse,
    GeneratedCardResponse,
    GenerationInfoResponse,
)
from ..services.bedrock import (
    BedrockService,
    BedrockTimeoutError,
    BedrockRateLimitError,
    BedrockInternalError,
    BedrockParseError,
)

logger = Logger()
tracer = Tracer()
app = APIGatewayHttpResolver()

# Initialize services
user_service = UserService()
card_service = CardService()
review_service = ReviewService()
bedrock_service = BedrockService()


def get_user_id_from_context() -> str:
    """Extract user_id from JWT claims in request context.

    Returns:
        User ID from JWT claims.

    Raises:
        UnauthorizedError: If user_id cannot be extracted.
    """
    try:
        # For HTTP API with JWT Authorizer
        claims = app.current_event.request_context.authorizer
        if claims and "jwt" in claims:
            return claims["jwt"]["claims"]["sub"]
        # For REST API with Cognito Authorizer
        if claims and "claims" in claims:
            return claims["claims"]["sub"]
        # Direct claims access
        if claims and "sub" in claims:
            return claims["sub"]
        raise UnauthorizedError("Unable to extract user ID from token")
    except (KeyError, TypeError, AttributeError) as e:
        logger.error(f"Failed to extract user_id: {e}")
        raise UnauthorizedError("Unable to extract user ID from token")


# =============================================================================
# User Endpoints
# =============================================================================


@app.get("/users/me")
@tracer.capture_method
def get_current_user():
    """Get current user information."""
    user_id = get_user_id_from_context()
    logger.info(f"Getting user info for user_id: {user_id}")

    try:
        user = user_service.get_or_create_user(user_id)
        return user.to_response().model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise


@app.post("/users/link-line")
@tracer.capture_method
def link_line_account():
    """Link LINE account to current user."""
    user_id = get_user_id_from_context()
    logger.info(f"Linking LINE account for user_id: {user_id}")

    try:
        body = app.current_event.json_body
        request = LinkLineRequest(**body)
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
        # Ensure user exists
        user_service.get_or_create_user(user_id)
        # Link LINE account
        user_service.link_line(user_id, request.line_user_id)
        return LinkLineResponse(success=True, message="LINE account linked successfully").model_dump()
    except UserAlreadyLinkedError:
        return Response(
            status_code=409,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "User is already linked to a LINE account"}),
        )
    except LineUserIdAlreadyUsedError:
        return Response(
            status_code=409,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "This LINE account is already linked to another user"}),
        )
    except Exception as e:
        logger.error(f"Error linking LINE account: {e}")
        raise


@app.put("/users/me/settings")
@tracer.capture_method
def update_user_settings():
    """Update current user settings."""
    user_id = get_user_id_from_context()
    logger.info(f"Updating settings for user_id: {user_id}")

    try:
        body = app.current_event.json_body
        request = UserSettingsRequest(**body)
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
        # Ensure user exists
        user_service.get_or_create_user(user_id)
        # Update settings
        user = user_service.update_settings(
            user_id,
            notification_time=request.notification_time,
            timezone=request.timezone,
        )
        return UserSettingsResponse(
            success=True,
            settings={
                "notification_time": user.settings.get("notification_time"),
                "timezone": user.settings.get("timezone"),
            },
        ).model_dump()
    except UserNotFoundError:
        raise NotFoundError("User not found")
    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        raise


@app.post("/users/me/unlink-line")
@tracer.capture_method
def unlink_line():
    """Unlink LINE account from current user."""
    user_id = get_user_id_from_context()
    logger.info(f"Unlinking LINE account for user_id: {user_id}")

    try:
        result = user_service.unlink_line(user_id)
        return {"success": True, "data": result}
    except LineNotLinkedError as e:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "LINE account not linked"}),
        )
    except Exception as e:
        logger.error(f"Error unlinking LINE account: {e}")
        raise


# =============================================================================
# AI Card Generation Endpoints
# =============================================================================


@app.post("/cards/generate")
@tracer.capture_method
def generate_cards():
    """Generate flashcards from input text using AI."""
    user_id = get_user_id_from_context()
    logger.info(f"Generating cards for user_id: {user_id}")

    try:
        body = app.current_event.json_body
        request = GenerateCardsRequest(**body)
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
        result = bedrock_service.generate_cards(
            input_text=request.input_text,
            card_count=request.card_count,
            difficulty=request.difficulty,
            language=request.language,
        )

        response = GenerateCardsResponse(
            generated_cards=[
                GeneratedCardResponse(
                    front=card.front,
                    back=card.back,
                    suggested_tags=card.suggested_tags,
                )
                for card in result.cards
            ],
            generation_info=GenerationInfoResponse(
                input_length=result.input_length,
                model_used=result.model_used,
                processing_time_ms=result.processing_time_ms,
            ),
        )
        return response.model_dump(mode="json")

    except BedrockTimeoutError:
        return Response(
            status_code=504,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "AI generation timed out"}),
        )
    except BedrockRateLimitError:
        return Response(
            status_code=429,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Too many requests, please retry later"}),
        )
    except BedrockInternalError:
        return Response(
            status_code=502,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "AI service temporarily unavailable"}),
        )
    except BedrockParseError:
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Failed to parse AI response"}),
        )
    except Exception as e:
        logger.error(f"Error generating cards: {e}")
        raise


# =============================================================================
# Card Endpoints
# =============================================================================


@app.get("/cards")
@tracer.capture_method
def list_cards():
    """List cards for the current user."""
    user_id = get_user_id_from_context()
    logger.info(f"Listing cards for user_id: {user_id}")

    # Get query parameters
    params = app.current_event.query_string_parameters or {}
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


@app.post("/cards")
@tracer.capture_method
def create_card():
    """Create a new card."""
    user_id = get_user_id_from_context()
    logger.info(f"Creating card for user_id: {user_id}")

    try:
        body = app.current_event.json_body
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
        # 【ユーザー存在保証】: カード作成前にユーザーレコードの存在を保証する (EARS-015)
        # 新規ユーザーはcard_count属性を持たないが、Fix 1 (if_not_exists) で安全に処理される
        # 既存ユーザーの場合はそのまま返される (冪等性保証)
        # 🔵 信頼性レベル: 青信号 - CR-02で handler.py L361 のユーザー存在保証不足が特定されている
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


@app.get("/cards/<card_id>")
@tracer.capture_method
def get_card(card_id: str):
    """Get a specific card."""
    user_id = get_user_id_from_context()
    logger.info(f"Getting card {card_id} for user_id: {user_id}")

    try:
        card = card_service.get_card(user_id, card_id)
        return card.to_response().model_dump(mode="json")
    except CardNotFoundError:
        raise NotFoundError(f"Card not found: {card_id}")
    except Exception as e:
        logger.error(f"Error getting card: {e}")
        raise


@app.put("/cards/<card_id>")
@tracer.capture_method
def update_card(card_id: str):
    """Update a card."""
    user_id = get_user_id_from_context()
    logger.info(f"Updating card {card_id} for user_id: {user_id}")

    try:
        body = app.current_event.json_body
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
        card = card_service.update_card(
            user_id=user_id,
            card_id=card_id,
            front=request.front,
            back=request.back,
            deck_id=request.deck_id,
            tags=request.tags,
        )
        return card.to_response().model_dump(mode="json")
    except CardNotFoundError:
        raise NotFoundError(f"Card not found: {card_id}")
    except Exception as e:
        logger.error(f"Error updating card: {e}")
        raise


@app.delete("/cards/<card_id>")
@tracer.capture_method
def delete_card(card_id: str):
    """Delete a card."""
    user_id = get_user_id_from_context()
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


# =============================================================================
# Review Endpoints
# =============================================================================


@app.get("/cards/due")
@tracer.capture_method
def get_due_cards():
    """Get cards due for review."""
    user_id = get_user_id_from_context()
    logger.info(f"Getting due cards for user_id: {user_id}")

    # Get query parameters
    params = app.current_event.query_string_parameters or {}
    limit = min(int(params.get("limit", 20)), 100)
    include_future = params.get("include_future", "false").lower() == "true"

    try:
        response = review_service.get_due_cards(
            user_id=user_id,
            limit=limit,
            include_future=include_future,
        )
        return response.model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error getting due cards: {e}")
        raise


@app.post("/reviews/<card_id>")
@tracer.capture_method
def submit_review(card_id: str):
    """Submit a review for a card."""
    user_id = get_user_id_from_context()
    logger.info(f"Submitting review for card {card_id} by user_id: {user_id}")

    try:
        body = app.current_event.json_body
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


# =============================================================================
# Lambda Handler
# =============================================================================


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler for API Gateway events."""
    return app.resolve(event, context)

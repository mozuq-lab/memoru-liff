"""AI card generation API route handler."""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from pydantic import ValidationError

from api.shared import get_user_id_from_context, map_ai_error_to_http
from models.generate import (
    GenerateCardsRequest,
    GenerateCardsResponse,
    GeneratedCardResponse,
    GenerationInfoResponse,
    RefineCardRequest,
    RefineCardResponse,
)
from services.ai_service import (
    create_ai_service,
    AIServiceError,
)

logger = Logger()
tracer = Tracer()
router = Router()


@router.post("/cards/generate")
@tracer.capture_method
def generate_cards():
    """Generate flashcards from input text using AI."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Generating cards for user_id: {user_id}")

    try:
        body = router.current_event.json_body
        if not isinstance(body, dict):
            return Response(
                status_code=400,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps({"error": "Request body must be a JSON object"}),
            )
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
        ai_service = create_ai_service()
        result = ai_service.generate_cards(
            input_text=request.input_text,
            card_count=request.card_count,
            difficulty=request.difficulty,
            language=request.language,
        )
        logger.info(
            f"Card generation succeeded: model={result.model_used}, "
            f"cards={len(result.cards)}, time_ms={result.processing_time_ms}"
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

    except AIServiceError as e:
        logger.warning(f"AI service error for user_id {user_id}: {type(e).__name__}: {e}")
        return map_ai_error_to_http(e)
    except Exception as e:
        logger.error(f"Error generating cards: {e}")
        raise


@router.post("/cards/refine")
@tracer.capture_method
def refine_card():
    """Refine/improve user-input flashcard using AI."""
    user_id = get_user_id_from_context(router)
    logger.info(f"Refining card for user_id: {user_id}")

    try:
        body = router.current_event.json_body
        if not isinstance(body, dict):
            return Response(
                status_code=400,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps({"error": "Request body must be a JSON object"}),
            )
        request = RefineCardRequest(**body)
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        details = json.loads(e.json())
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid request", "details": details}),
        )
    except json.JSONDecodeError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid JSON body"}),
        )

    try:
        ai_service = create_ai_service()
        result = ai_service.refine_card(
            front=request.front,
            back=request.back,
            language=request.language,
        )
        logger.info(
            f"Card refinement succeeded for user_id: {user_id}, "
            f"model={result.model_used}, time_ms={result.processing_time_ms}"
        )

        response = RefineCardResponse(
            refined_front=result.refined_front,
            refined_back=result.refined_back,
            model_used=result.model_used,
            processing_time_ms=result.processing_time_ms,
        )
        return response.model_dump(mode="json")

    except AIServiceError as e:
        logger.warning(f"AI service error for user_id {user_id}: {type(e).__name__}: {e}")
        return map_ai_error_to_http(e)
    except Exception as e:
        logger.error(f"Error refining card: {e}")
        raise

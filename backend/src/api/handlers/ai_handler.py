"""AI card generation API route handler."""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from pydantic import ValidationError

from api.shared import get_user_id_from_context, map_ai_error_to_http, make_validation_error_response
from services.card_service import CardService
from models.generate import (
    GenerateCardsRequest,
    GenerateCardsResponse,
    GeneratedCardResponse,
    GenerationInfoResponse,
    RefineCardRequest,
    RefineCardResponse,
)
from models.url_generate import (
    GenerateFromUrlRequest,
    GenerateFromUrlResponse,
    PageInfoResponse,
    UrlGenerationInfoResponse,
)
from services.ai_service import (
    create_ai_service,
    AIServiceError,
)
from services.browser_service import BrowserService
from services.content_chunker import chunk_content
from services.url_content_service import ContentFetchError, UrlContentService

logger = Logger()
tracer = Tracer()
router = Router()


@router.post("/cards/generate")
@tracer.capture_method
def generate_cards():
    """Generate flashcards from input text using AI."""
    user_id = get_user_id_from_context(router)
    logger.info("Generating cards", extra={"user_id": user_id})

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
        logger.warning("Validation error", extra={"error": str(e)})
        return make_validation_error_response(e)
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
            "Card generation succeeded",
            extra={"model": result.model_used, "cards": len(result.cards), "time_ms": result.processing_time_ms},
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
        logger.warning("AI service error", extra={"user_id": user_id, "error_type": type(e).__name__, "error": str(e)})
        return map_ai_error_to_http(e)
    except Exception as e:
        logger.error("Error generating cards", extra={"error": str(e)})
        raise


@router.post("/cards/generate-from-url")
@tracer.capture_method
def generate_from_url():
    """Generate flashcards from a URL using AI."""
    user_id = get_user_id_from_context(router)
    logger.info("Generating cards from URL", extra={"user_id": user_id})

    try:
        body = router.current_event.json_body
        if not isinstance(body, dict):
            return Response(
                status_code=400,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps({"error": "Request body must be a JSON object"}),
            )
        request = GenerateFromUrlRequest(**body)
    except ValidationError as e:
        logger.warning("Validation error", extra={"error": str(e)})
        return make_validation_error_response(e)
    except json.JSONDecodeError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid JSON body"}),
        )

    # Duplicate URL detection warning
    duplicate_warning = None
    try:
        card_service = CardService()
        existing_cards, _ = card_service.list_cards(user_id)
        for card in existing_cards:
            refs = getattr(card, "references", None) or []
            for ref in refs:
                ref_val = ref.get("value", "") if isinstance(ref, dict) else getattr(ref, "value", "")
                if ref_val == request.url:
                    duplicate_warning = "この URL からは既にカードが生成されています。"
                    break
            if duplicate_warning:
                break
    except Exception:
        pass  # Non-critical: don't block generation on duplicate check failure

    # Fetch page content
    try:
        content_service = UrlContentService(browser_service=BrowserService())
        page = content_service.fetch_content(
            request.url,
            profile_id=getattr(request, "profile_id", None),
        )
    except ContentFetchError as e:
        logger.warning("Content fetch error", extra={"user_id": user_id, "error": str(e)})
        error_msg = str(e)
        if "timeout" in error_msg.lower():
            status_code = 408
        elif "private" in error_msg.lower() or "blocked" in error_msg.lower():
            status_code = 403
        elif "supported" in error_msg.lower() or "meaningful" in error_msg.lower():
            status_code = 422
        else:
            status_code = 502
        return Response(
            status_code=status_code,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": error_msg}),
        )

    # Chunk content
    chunks = chunk_content(page.text_content, page_title=page.title)
    chunk_texts = [c.text for c in chunks]

    if not chunk_texts:
        return Response(
            status_code=422,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Could not extract meaningful text content from the page"}),
        )

    # Generate cards
    try:
        ai_service = create_ai_service()
        result = ai_service.generate_cards_from_chunks(
            chunks=chunk_texts,
            card_type=request.card_type,
            target_count=request.target_count,
            difficulty=request.difficulty,
            language=request.language,
            page_title=page.title,
        )
        if not result.cards:
            return Response(
                status_code=422,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps({"error": "Failed to generate cards from the page content"}),
            )

        logger.info(
            "URL card generation succeeded",
            extra={
                "model": result.model_used,
                "cards": len(result.cards),
                "chunks": len(chunk_texts),
                "time_ms": result.processing_time_ms,
            },
        )

        response = GenerateFromUrlResponse(
            generated_cards=[
                GeneratedCardResponse(
                    front=card.front,
                    back=card.back,
                    suggested_tags=card.suggested_tags,
                )
                for card in result.cards
            ],
            generation_info=UrlGenerationInfoResponse(
                model_used=result.model_used,
                processing_time_ms=result.processing_time_ms,
                fetch_method=page.fetch_method,
                chunk_count=len(chunk_texts),
                content_length=len(page.text_content),
            ),
            page_info=PageInfoResponse(
                url=page.url,
                title=page.title,
                fetched_at=page.fetched_at,
            ),
            warning=duplicate_warning,
        )
        return response.model_dump(mode="json", exclude_none=True)

    except AIServiceError as e:
        logger.warning("AI service error", extra={"user_id": user_id, "error_type": type(e).__name__, "error": str(e)})
        return map_ai_error_to_http(e)
    except Exception as e:
        logger.error("Error generating cards from URL", extra={"error": str(e)})
        raise


@router.post("/cards/refine")
@tracer.capture_method
def refine_card():
    """Refine/improve user-input flashcard using AI."""
    user_id = get_user_id_from_context(router)
    logger.info("Refining card", extra={"user_id": user_id})

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
        logger.warning("Validation error", extra={"error": str(e)})
        return make_validation_error_response(e)
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
            "Card refinement succeeded",
            extra={"user_id": user_id, "model": result.model_used, "time_ms": result.processing_time_ms},
        )

        response = RefineCardResponse(
            refined_front=result.refined_front,
            refined_back=result.refined_back,
            model_used=result.model_used,
            processing_time_ms=result.processing_time_ms,
        )
        return response.model_dump(mode="json")

    except AIServiceError as e:
        logger.warning("AI service error", extra={"user_id": user_id, "error_type": type(e).__name__, "error": str(e)})
        return map_ai_error_to_http(e)
    except Exception as e:
        logger.error("Error refining card", extra={"error": str(e)})
        raise

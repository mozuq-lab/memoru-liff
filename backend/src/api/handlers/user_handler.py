"""User API route handlers."""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router
from aws_lambda_powertools.event_handler.exceptions import NotFoundError
from pydantic import ValidationError

from api.shared import get_user_id_from_context, make_validation_error_response
from models.user import LinkLineResponse, UserSettingsRequest
from services.user_service import (
    UserService,
    UserNotFoundError,
    UserAlreadyLinkedError,
    LineUserIdAlreadyUsedError,
    LineNotLinkedError,
)
from services.line_service import LineService

logger = Logger()
tracer = Tracer()
router = Router()

user_service = UserService()
line_service = LineService()


@router.get("/users/me")
@tracer.capture_method
def get_current_user():
    """Get current user information."""
    user_id = get_user_id_from_context(router)
    logger.info("Getting user info", extra={"user_id": user_id})

    try:
        user = user_service.get_or_create_user(user_id)
        return user.to_response().model_dump(mode="json")
    except Exception as e:
        logger.error("Error getting user", extra={"error": str(e)})
        raise


@router.post("/users/link-line")
@tracer.capture_method
def link_line_account():
    """Link LINE account to current user."""
    user_id = get_user_id_from_context(router)
    logger.info("Linking LINE account", extra={"user_id": user_id})

    try:
        body = router.current_event.json_body
    except json.JSONDecodeError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid JSON body"}),
        )

    id_token = body.get("id_token") if body else None
    if not id_token:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "id_token is required"}),
        )

    try:
        user_service.get_or_create_user(user_id)
        line_user_id = line_service.verify_id_token(id_token)
        user_service.link_line(user_id, line_user_id)
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
        logger.error("Error linking LINE account", extra={"error": str(e)})
        raise


@router.put("/users/me/settings")
@tracer.capture_method
def update_user_settings():
    """Update current user settings."""
    user_id = get_user_id_from_context(router)
    logger.info("Updating settings", extra={"user_id": user_id})

    try:
        body = router.current_event.json_body
        request = UserSettingsRequest(**body)
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
        user_service.get_or_create_user(user_id)
        user = user_service.update_settings(
            user_id,
            notification_time=request.notification_time,
            timezone=request.timezone,
            day_start_hour=request.day_start_hour,
        )
        return {"success": True, "data": user.to_response().model_dump(mode="json")}
    except UserNotFoundError:
        raise NotFoundError("User not found")
    except Exception as e:
        logger.error("Error updating settings", extra={"error": str(e)})
        raise


@router.post("/users/me/unlink-line")
@tracer.capture_method
def unlink_line():
    """Unlink LINE account from current user."""
    user_id = get_user_id_from_context(router)
    logger.info("Unlinking LINE account", extra={"user_id": user_id})

    try:
        user = user_service.unlink_line(user_id)
        return {"success": True, "data": user.to_response().model_dump(mode="json")}
    except LineNotLinkedError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "LINE account not linked"}),
        )
    except Exception as e:
        logger.error("Error unlinking LINE account", extra={"error": str(e)})
        raise

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
from ..services.user_service import (
    UserService,
    UserNotFoundError,
    UserAlreadyLinkedError,
    LineUserIdAlreadyUsedError,
)

logger = Logger()
tracer = Tracer()
app = APIGatewayHttpResolver()

# Initialize services
user_service = UserService()


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


# =============================================================================
# Lambda Handler
# =============================================================================


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler for API Gateway events."""
    return app.resolve(event, context)

"""Shared utilities for API handlers."""

import base64
import json
import os

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

from pydantic import ValidationError

from services.ai_service import (
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIProviderError,
    AIParseError,
)

logger = Logger()


def _jwt_dev_fallback_decode(auth_header: str | None) -> str | None:
    """Decode user_id from JWT Authorization header (dev + SAM local only).

    Fallback is only activated when ENVIRONMENT=dev AND AWS_SAM_LOCAL=true.
    Logs a warning when activated to ensure visibility.

    Args:
        auth_header: Authorization header value (e.g. "Bearer <token>").

    Returns:
        User ID (sub claim) if successfully decoded, None otherwise.
    """
    environment = os.environ.get("ENVIRONMENT", "")
    aws_sam_local = os.environ.get("AWS_SAM_LOCAL", "")

    if environment != "dev" or aws_sam_local != "true":
        return None

    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    try:
        token = auth_header.split(" ", 1)[1]
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        user_id = decoded.get("sub")
        if user_id:
            logger.warning(
                "JWT dev fallback activated",
                extra={"user_id": user_id, "environment": environment},
            )
        return user_id
    except Exception as e:
        logger.error("Failed to decode JWT from Authorization header", extra={"error": str(e)})
        return None


def get_user_id_from_context(resolver) -> str:
    """Extract user_id from JWT claims in request context.

    Args:
        resolver: APIGatewayHttpResolver or Router instance.

    Returns:
        User ID from JWT claims.

    Raises:
        UnauthorizedError: If user_id cannot be extracted.
    """
    try:
        claims = resolver.current_event.request_context.authorizer
        if claims and "jwt" in claims:
            return claims["jwt"]["claims"]["sub"]
        if claims and "claims" in claims:
            return claims["claims"]["sub"]
        if claims and "sub" in claims:
            return claims["sub"]
    except (KeyError, TypeError, AttributeError) as e:
        logger.warning("Failed to extract user_id from authorizer context", extra={"error": str(e)})

    # Dev fallback: ENVIRONMENT=dev AND AWS_SAM_LOCAL=true required
    auth_header = resolver.current_event.get_header_value("Authorization")
    user_id = _jwt_dev_fallback_decode(auth_header)
    if user_id:
        return user_id

    raise UnauthorizedError("Unable to extract user ID from token")


def get_user_id_from_event(event: dict) -> str | None:
    """Extract user_id from API Gateway HTTP API v2 Lambda event JWT claims.

    Used by standalone Lambda handlers that receive raw API Gateway events
    (not routed through APIGatewayHttpResolver).

    Args:
        event: Raw API Gateway HTTP API v2 Lambda event dict.

    Returns:
        User ID from JWT claims, or None if extraction fails.
    """
    try:
        claims = event.get("requestContext", {}).get("authorizer", {})
        if claims and "jwt" in claims:
            return claims["jwt"]["claims"]["sub"]
        if claims and "claims" in claims:
            return claims["claims"]["sub"]
        if claims and "sub" in claims:
            return claims["sub"]
    except (KeyError, TypeError, AttributeError):
        pass

    # Dev fallback: ENVIRONMENT=dev AND AWS_SAM_LOCAL=true required
    auth_header = (event.get("headers") or {}).get("authorization", "")
    return _jwt_dev_fallback_decode(auth_header)


def make_validation_error_response(e: ValidationError) -> Response:
    """Create a standardized 400 response for Pydantic ValidationError.

    Uses json.loads(e.json()) instead of e.errors() to ensure all values
    are JSON-serializable (e.errors() can contain raw ValueError objects
    in the 'ctx' field which are not JSON-serializable).

    Args:
        e: Pydantic ValidationError instance.

    Returns:
        Response with status 400, error message, and validation details.
    """
    details = json.loads(e.json())
    return Response(
        status_code=400,
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps({"error": "Invalid request", "details": details}),
    )


def map_ai_error_to_http(error: AIServiceError) -> Response:
    """Map AI service exceptions to HTTP responses."""
    if isinstance(error, AITimeoutError):
        return Response(
            status_code=504,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "AI service timeout"}),
        )
    if isinstance(error, AIRateLimitError):
        return Response(
            status_code=429,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "AI service rate limit exceeded"}),
        )
    if isinstance(error, AIProviderError):
        return Response(
            status_code=503,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "AI service unavailable"}),
        )
    if isinstance(error, AIParseError):
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "AI service response parse error"}),
        )
    return Response(
        status_code=500,
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps({"error": "AI service error"}),
    )

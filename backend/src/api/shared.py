"""Shared utilities for API handlers."""

import base64
import json
import os

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

from services.ai_service import (
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIProviderError,
    AIParseError,
)

logger = Logger()


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
        logger.warning(f"Failed to extract user_id from authorizer context: {e}")

    if os.environ.get("ENVIRONMENT") == "dev":
        try:
            auth_header = resolver.current_event.get_header_value("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]
                payload = token.split(".")[1]
                payload += "=" * (4 - len(payload) % 4)
                decoded = json.loads(base64.urlsafe_b64decode(payload))
                return decoded["sub"]
        except Exception as e:
            logger.error(f"Failed to decode JWT from Authorization header: {e}")

    raise UnauthorizedError("Unable to extract user ID from token")


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

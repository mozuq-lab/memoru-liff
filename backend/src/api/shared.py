"""Shared utilities for API handlers."""

import base64
import json
import os
from typing import TypeVar

from aws_lambda_powertools import Logger
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

from pydantic import BaseModel, ValidationError

from services.ai_service import (
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIProviderError,
    AIParseError,
)

logger = Logger()

_RequestModel = TypeVar("_RequestModel", bound=BaseModel)


def parse_json_body(
    resolver, model_class: type[_RequestModel]
) -> _RequestModel | Response:
    """リクエスト JSON ボディを ``model_class`` にパース・検証する。

    全 POST/PUT ハンドラーで重複していた「json_body 取得 → dict 検証 →
    Pydantic 変換 → ValidationError / JSONDecodeError ハンドリング」を一元化する。
    ルーター経由ハンドラーの入力検証を統一し、400 応答仕様を 1 箇所に集約する。

    Args:
        resolver: ``current_event.json_body`` を持つ APIGatewayHttpResolver
            または Router インスタンス。
        model_class: ボディを検証する Pydantic モデルクラス。

    Returns:
        検証済みモデルインスタンス。失敗時は 400 ``Response``
        (非 dict ボディ / バリデーションエラー / 不正 JSON)。呼び出し側は
        ``isinstance(result, Response)`` で早期 return して分岐する。
    """
    try:
        body = resolver.current_event.json_body
        if not isinstance(body, dict):
            return Response(
                status_code=400,
                content_type=content_types.APPLICATION_JSON,
                body=json.dumps({"error": "Request body must be a JSON object"}),
            )
        return model_class(**body)
    except ValidationError as e:
        logger.warning("Validation error", extra={"error": str(e)})
        return make_validation_error_response(e)
    except json.JSONDecodeError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid JSON body"}),
        )


def _is_jwt_dev_fallback_enabled() -> bool:
    """署名検証なし dev JWT フォールバックを有効化してよいか判定する.

    本番混入リスクを下げるため、以下を AND で要求する:

    - ``ENVIRONMENT=dev``
    - ``AWS_SAM_LOCAL=true`` (SAM CLI が自動設定)
    - ``ENABLE_JWT_DEV_FALLBACK`` が明示的に ``"false"`` で**無効化されていない**こと

    ``ENABLE_JWT_DEV_FALLBACK`` は専用キルスイッチ。本番 Lambda には
    ``ENABLE_JWT_DEV_FALLBACK=false`` を設定しておくことで、設定ファイルの誤流用などで
    ``ENVIRONMENT=dev`` / ``AWS_SAM_LOCAL=true`` が紛れ込んでも署名なし JWT を確実に拒否できる。
    既存のローカル開発フロー（dev + SAM local）の挙動は変えないため、デフォルト（未設定）は有効のまま。
    """
    if os.environ.get("ENVIRONMENT", "") != "dev":
        return False
    if os.environ.get("AWS_SAM_LOCAL", "") != "true":
        return False
    # 専用キルスイッチ: 明示的に "false" の場合のみ無効化（未設定はローカル開発のため有効）。
    if os.environ.get("ENABLE_JWT_DEV_FALLBACK", "").lower() == "false":
        return False
    return True


def _jwt_dev_fallback_decode(auth_header: str | None) -> str | None:
    """Decode user_id from JWT Authorization header (dev + SAM local only).

    署名検証を行わない開発専用フォールバック。``_is_jwt_dev_fallback_enabled()``
    が True を返す場合のみ有効化され、有効化されるたびに WARNING ログを出力する
    (監視アラートに接続して本番混入を検知できるようにする想定)。

    Args:
        auth_header: Authorization header value (e.g. "Bearer <token>").

    Returns:
        User ID (sub claim) if successfully decoded, None otherwise.
    """
    if not _is_jwt_dev_fallback_enabled():
        return None

    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    try:
        token = auth_header.split(" ", 1)[1]
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        user_id = decoded.get("sub")
    except Exception as e:
        # 例外メッセージ (str(e)) にはデコード途中のトークン断片が混入し得るため、
        # トークン本体は出さず例外クラス名のみを記録する。
        logger.error(
            "Failed to decode JWT from Authorization header (dev fallback)",
            extra={"error": type(e).__name__},
        )
        return None

    if user_id:
        logger.warning(
            "JWT dev fallback activated (UNVERIFIED signature) — must never run in production",
            extra={"user_id": user_id, "environment": os.environ.get("ENVIRONMENT", "")},
        )
    return user_id


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

    # Dev fallback: ENVIRONMENT=dev AND AWS_SAM_LOCAL=true AND ENABLE_JWT_DEV_FALLBACK=true required
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

    # Dev fallback: ENVIRONMENT=dev AND AWS_SAM_LOCAL=true AND ENABLE_JWT_DEV_FALLBACK=true required
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

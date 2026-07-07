"""Main API handler for Memoru LIFF application.

Routes API Gateway events to domain-specific handlers via Lambda Powertools Router.
Standalone Lambda handlers (grade_ai, advice) remain in this file
(ai-async-jobs: いずれも同期検証 + ジョブ submit のみを行い 202 を返す).
"""

import json
from typing import Any

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools.logging import correlation_paths
from aws_lambda_powertools.utilities.typing import LambdaContext

from api.shared import (
    check_ai_rate_limit_event,
    get_user_id_from_event,
    make_job_accepted_event_response,
    map_ai_error_to_http,
)
from api.handlers.user_handler import router as user_router
from api.handlers.cards_handler import router as cards_router
from api.handlers.decks_handler import router as decks_router
from api.handlers.review_handler import router as review_router
from api.handlers.ai_handler import router as ai_router
from api.handlers.ai_jobs_handler import router as ai_jobs_router
from api.handlers.stats_handler import router as stats_router
from api.handlers.browser_profile_handler import router as browser_profile_router
from api.handlers.tutor_handler import router as tutor_router

# Standalone handler dependencies
from models.grading import GradeAnswerRequest
from pydantic import ValidationError
from services.ai_job_service import submit_ai_job
from services.card_service import CardService, CardNotFoundError

logger = Logger()
tracer = Tracer()
app = APIGatewayHttpResolver()

# 許可する language の許可リスト（ルーター経由の Pydantic Literal["ja", "en"] と対称にする）。
# スタンドアロンハンドラーはクエリパラメーターを Pydantic 検証しないため、ここで明示的に検証する。
ALLOWED_LANGUAGES = frozenset({"ja", "en"})

# Register domain routers
app.include_router(user_router)
app.include_router(cards_router)
app.include_router(decks_router)
app.include_router(review_router)
app.include_router(ai_router)
app.include_router(ai_jobs_router)
app.include_router(stats_router)
app.include_router(browser_profile_router)
app.include_router(tutor_router)

# Services for standalone Lambda handlers
card_service = CardService()


# Keep backward compatibility alias
_map_ai_error_to_http = map_ai_error_to_http


def _make_lambda_response(status_code: int, body: dict) -> dict:
    """Create a Lambda proxy integration response dict."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


# =============================================================================
# Standalone Lambda Handlers
# =============================================================================


def grade_ai_handler(event: dict, context: Any) -> dict:
    """POST /reviews/{cardId}/grade-ai の Lambda ハンドラー（ai-async-jobs: submit のみ）。

    独立 Lambda 関数として API Gateway HTTP API v2 イベントを直接受け取る。
    同期検証（認証・レート制限・バリデーション・カード所有権）後にジョブを登録し
    202 を返す。AI 採点はワーカーが実行する。
    """
    try:
        user_id = get_user_id_from_event(event)
        if not user_id:
            return _make_lambda_response(401, {"error": "Unauthorized"})

        rate_limited = check_ai_rate_limit_event(user_id)
        if rate_limited:
            return rate_limited

        path_params = event.get("pathParameters") or {}
        card_id = path_params.get("cardId")
        if not card_id:
            return _make_lambda_response(400, {"error": "card_id is required"})

        body_str = event.get("body") or ""
        try:
            body_dict = json.loads(body_str)
            request = GradeAnswerRequest(**body_dict)
        except json.JSONDecodeError:
            return _make_lambda_response(400, {"error": "Invalid request body"})
        except ValidationError as e:
            return _make_lambda_response(400, {"error": "Invalid request", "details": json.loads(e.json())})

        logger.info(
            "Grade AI job submit",
            extra={"card_id": card_id, "user_id": user_id, "user_answer_length": len(request.user_answer)},
        )

        language = (event.get("queryStringParameters") or {}).get("language", "ja")
        if language not in ALLOWED_LANGUAGES:
            return _make_lambda_response(400, {"error": "Unsupported language. Use 'ja' or 'en'."})

        # fail-fast: カード存在＋所有権を submit 時に検証（ワーカー側でも再検証される）
        try:
            card_service.get_card(user_id, card_id)
        except CardNotFoundError:
            return _make_lambda_response(404, {"error": "Not Found"})

        job = submit_ai_job(
            user_id=user_id,
            job_type="grade_ai",
            payload={
                "card_id": card_id,
                "user_answer": request.user_answer,
                "language": language,
            },
        )
        return make_job_accepted_event_response(job)

    except Exception as e:
        logger.error("Unexpected error in grade_ai_handler", extra={"error": str(e)})
        return _make_lambda_response(500, {"error": "Internal Server Error"})


def advice_handler(event: dict, context: Any) -> dict:
    """POST /advice の Lambda ハンドラー（ai-async-jobs: submit のみ）。

    独立 Lambda 関数として API Gateway HTTP API v2 イベントを直接受け取る。
    レビューサマリー集計と AI 呼び出しはワーカーが実行する
    （GET → POST 変更。ジョブ作成は非冪等のため。フロント未使用につき互換対応不要）。
    """
    try:
        user_id = get_user_id_from_event(event)
        if not user_id:
            return _make_lambda_response(401, {"error": "Unauthorized"})

        rate_limited = check_ai_rate_limit_event(user_id)
        if rate_limited:
            return rate_limited

        logger.info("Advice job submit", extra={"user_id": user_id})

        language = (event.get("queryStringParameters") or {}).get("language", "ja")
        if language not in ALLOWED_LANGUAGES:
            return _make_lambda_response(400, {"error": "Unsupported language. Use 'ja' or 'en'."})

        job = submit_ai_job(
            user_id=user_id,
            job_type="advice",
            payload={"language": language},
        )
        return make_job_accepted_event_response(job)

    except Exception as e:
        logger.error("Unexpected error in advice_handler", extra={"error": str(e)})
        return _make_lambda_response(500, {"error": "Internal Server Error"})


def url_generate_handler(event: dict, context: Any) -> dict:
    """POST /cards/generate-from-url の Lambda ハンドラー。

    専用 Lambda 関数（120s タイムアウト、512MB メモリ）として実行される。
    """
    return handler(event, context)


# =============================================================================
# Lambda Handler
# =============================================================================


@logger.inject_lambda_context(correlation_id_path=correlation_paths.API_GATEWAY_HTTP)
@tracer.capture_lambda_handler
def handler(event: dict, context: LambdaContext) -> dict:
    """Lambda handler for API Gateway events."""
    # Stage path prefix補完:
    # API Gateway HTTP API v2 ではステージ名が "$default" 以外の場合（例: "prod", "dev"）、
    # rawPath にステージプレフィックスが含まれないことがある。
    # Lambda Powertools の APIGatewayHttpResolver はルートマッチング時に rawPath を使用するが、
    # ステージプレフィックスの自動補完は行わないため、手動で付与する必要がある。
    # 例: stage="prod", rawPath="/cards" → "/prod/cards" に補完してルーティングを正しく動作させる。
    stage = event.get("requestContext", {}).get("stage", "$default")
    raw_path = event.get("rawPath", "/")
    if stage != "$default" and not raw_path.startswith(f"/{stage}"):
        event["rawPath"] = f"/{stage}{raw_path}"
    return app.resolve(event, context)

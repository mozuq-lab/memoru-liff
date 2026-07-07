"""AI card generation API route handler (ai-async-jobs: submit のみ担当).

各エンドポイントは同期検証（認証・レート制限・バリデーション）後にジョブを登録し、
202 Accepted + job_id を即返す。AI 実行はワーカー（jobs/ai_job_worker_handler）が
行い、フロントは GET /ai-jobs/{job_id} をポーリングして結果を取得する。
コンテンツ取得エラー等の分類は services/ai_job_errors.classify_ai_job_error に移設した。
"""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router

from api.shared import (
    check_ai_rate_limit,
    get_user_id_from_context,
    make_job_accepted_response,
    parse_json_body,
)
from models.generate import GenerateCardsRequest, RefineCardRequest
from models.url_generate import GenerateFromUrlRequest
from services.ai_job_service import submit_ai_job
from utils.url_validator import UrlValidationError, validate_url

logger = Logger()
tracer = Tracer()
router = Router()


@router.post("/cards/generate")
@tracer.capture_method
def generate_cards():
    """Generate flashcards from input text using AI (async job submit)."""
    user_id = get_user_id_from_context(router)
    logger.info("Submitting generate job", extra={"user_id": user_id})

    rate_limited = check_ai_rate_limit(user_id)
    if rate_limited:
        return rate_limited

    parsed = parse_json_body(router, GenerateCardsRequest)
    if isinstance(parsed, Response):
        return parsed
    request = parsed

    job = submit_ai_job(
        user_id=user_id,
        job_type="generate",
        payload={
            "input_text": request.input_text,
            "card_count": request.card_count,
            "difficulty": request.difficulty,
            "language": request.language,
        },
    )
    return make_job_accepted_response(job)


@router.post("/cards/generate-from-url")
@tracer.capture_method
def generate_from_url():
    """Generate flashcards from a URL using AI (async job submit)."""
    user_id = get_user_id_from_context(router)
    logger.info("Submitting generate-from-url job", extra={"user_id": user_id})

    rate_limited = check_ai_rate_limit(user_id)
    if rate_limited:
        return rate_limited

    parsed = parse_json_body(router, GenerateFromUrlRequest)
    if isinstance(parsed, Response):
        return parsed
    request = parsed

    # Authenticated-page support (profile_id) is disabled until the
    # AgentCore Browser integration is rewritten. Reject early with 501
    # rather than letting it fall through and 500 inside BrowserService.
    profile_id = getattr(request, "profile_id", None)
    if profile_id:
        logger.info(
            "profile_id request rejected: browser integration disabled",
            extra={"user_id": user_id, "profile_id": profile_id},
        )
        return Response(
            status_code=501,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps(
                {
                    "error": (
                        "認証付きページからのカード生成は現在対応していません。"
                    ),
                    "code": "browser_unavailable",
                }
            ),
        )

    # SSRF バリデーションは submit 時に fail-fast する（ワーカーの fetch 内でも
    # 再検証されるが、無効 URL のジョブ化を避けて即 400 を返す）。
    try:
        normalized_url = validate_url(request.url)
    except UrlValidationError as e:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": f"無効なURLです: {e}"}, ensure_ascii=False),
        )

    job = submit_ai_job(
        user_id=user_id,
        job_type="generate_from_url",
        payload={
            "url": normalized_url,
            "card_type": request.card_type,
            "target_count": request.target_count,
            "difficulty": request.difficulty,
            "language": request.language,
        },
    )
    return make_job_accepted_response(job)


@router.post("/cards/refine")
@tracer.capture_method
def refine_card():
    """Refine/improve user-input flashcard using AI (async job submit)."""
    user_id = get_user_id_from_context(router)
    logger.info("Submitting refine job", extra={"user_id": user_id})

    rate_limited = check_ai_rate_limit(user_id)
    if rate_limited:
        return rate_limited

    parsed = parse_json_body(router, RefineCardRequest)
    if isinstance(parsed, Response):
        return parsed
    request = parsed

    job = submit_ai_job(
        user_id=user_id,
        job_type="refine",
        payload={
            "front": request.front,
            "back": request.back,
            "language": request.language,
        },
    )
    return make_job_accepted_response(job)

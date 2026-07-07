"""AI job polling API route handler (ai-async-jobs)."""

import json

from aws_lambda_powertools import Logger, Tracer
from aws_lambda_powertools.event_handler import Response, content_types
from aws_lambda_powertools.event_handler.api_gateway import Router

from api.shared import get_user_id_from_context
from services.ai_job_store import AiJobStore

logger = Logger()
tracer = Tracer()
router = Router()

ai_job_store = AiJobStore()

# ポーリングレスポンスに含める属性。payload（リクエスト原文）や schema_version は
# クライアントに不要なため返さない。
_PUBLIC_FIELDS = (
    "job_id",
    "job_type",
    "status",
    "result",
    "error",
    "created_at",
    "updated_at",
)


def _not_found_response() -> Response:
    """存在しない / 他ユーザーのジョブは同一の 404 を返す（IDOR 対策: 列挙防止）。"""
    return Response(
        status_code=404,
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps({"error": "Job not found"}),
    )


@router.get("/ai-jobs/<job_id>")
@tracer.capture_method
def get_ai_job(job_id: str):
    """ジョブの状態・結果を返す（ポーリング用）。"""
    user_id = get_user_id_from_context(router)

    try:
        job = ai_job_store.get_job(job_id)
    except Exception as e:
        # ポーリングは高頻度なため、DynamoDB の一時障害を Lambda 未処理例外として
        # 漏らさず統一形式の 500 で返す（フロントは次のポーリングで再試行する）。
        logger.error("Failed to get AI job", extra={"job_id": job_id, "error": str(e)})
        return Response(
            status_code=500,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Internal Server Error"}),
        )

    if job is None or job.get("user_id") != user_id:
        return _not_found_response()

    body = {k: job[k] for k in _PUBLIC_FIELDS if k in job}
    return body

"""AI 非同期ジョブの executor 群 (ai-async-jobs)。

job_type ごとに payload を受け取り、既存サービス層を呼び出して
「現行同期レスポンスと同一スキーマ」の result dict を返す。

- ここでは HTTP 変換を行わない。例外はそのまま送出し、呼び出し側
  （ワーカー / inline 実行）が classify_ai_job_error で failed ジョブに変換する。
- SQS ワーカーと submit の inline モードの両方から呼ばれる（単一実装）。
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Dict, Literal, cast

from aws_lambda_powertools import Logger

from models.advice import LearningAdviceResponse
from models.generate import (
    GenerateCardsResponse,
    GeneratedCardResponse,
    GenerationInfoResponse,
    RefineCardResponse,
)
from models.grading import GradeAnswerResponse
from models.url_generate import (
    GenerateFromUrlResponse,
    PageInfoResponse,
    UrlGenerationInfoResponse,
)
from services.ai_job_errors import NoCardsGeneratedError
from services.ai_service import create_ai_service
from services.browser_service import BrowserService
from services.card_service import CardService
from services.review_service import ReviewService
from services.tutor_service import TutorService
from services.url_content_service import UrlContentService
from services.url_generation_service import fetch_and_generate_cards
from services.user_service import UserService

logger = Logger()

# TutorService は AI サービスファクトリ等の初期化を伴うため遅延生成でキャッシュする
# （tutor_handler のモジュールレベル生成と同等。テストでは本モジュールの
# _tutor_service を差し替える）。
_tutor_service: TutorService | None = None


def _get_tutor_service() -> TutorService:
    global _tutor_service
    if _tutor_service is None:
        _tutor_service = TutorService()
    return _tutor_service


def execute_generate(user_id: str, payload: dict) -> dict:
    """POST /cards/generate 相当（GenerateCardsResponse）。"""
    ai_service = create_ai_service()
    result = ai_service.generate_cards(
        input_text=payload["input_text"],
        card_count=payload["card_count"],
        difficulty=payload["difficulty"],
        language=payload["language"],
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


def execute_generate_from_url(user_id: str, payload: dict) -> dict:
    """POST /cards/generate-from-url 相当（GenerateFromUrlResponse）。

    重複 URL 警告もここで算出する（現行 sync ハンドラーから移設。
    警告算出の失敗は生成をブロックしない）。
    """
    url = payload["url"]

    duplicate_warning = None
    try:
        matched_cards = CardService().find_cards_by_reference_url(user_id, url)
        if matched_cards:
            duplicate_warning = "この URL からは既にカードが生成されています。"
    except Exception:
        pass  # Non-critical: don't block generation on duplicate check failure

    page, chunk_texts, result = fetch_and_generate_cards(
        url,
        card_type=payload["card_type"],
        target_count=payload["target_count"],
        difficulty=payload["difficulty"],
        language=payload["language"],
        content_service=UrlContentService(browser_service=BrowserService()),
        profile_id=None,
    )

    if not result.cards:
        raise NoCardsGeneratedError("Failed to generate cards from the page content")

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
            # PageContent.fetch_method は str 型だが実値は "http" | "browser" のみ
            # (url_content_service)。モデル側の Literal に合わせて cast する。
            fetch_method=cast(Literal["http", "browser"], page.fetch_method),
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


def execute_refine(user_id: str, payload: dict) -> dict:
    """POST /cards/refine 相当（RefineCardResponse）。"""
    ai_service = create_ai_service()
    result = ai_service.refine_card(
        front=payload["front"],
        back=payload["back"],
        language=payload["language"],
    )
    response = RefineCardResponse(
        refined_front=result.refined_front,
        refined_back=result.refined_back,
        model_used=result.model_used,
        processing_time_ms=result.processing_time_ms,
    )
    return response.model_dump(mode="json")


def execute_grade_ai(user_id: str, payload: dict) -> dict:
    """POST /reviews/{cardId}/grade-ai 相当（GradeAnswerResponse）。

    カードが submit 後に削除された場合は CardNotFoundError → failed(404)。
    """
    card = CardService().get_card(user_id, payload["card_id"])
    ai_service = create_ai_service()
    result = ai_service.grade_answer(
        card_front=card.front,
        card_back=card.back,
        user_answer=payload["user_answer"],
        language=payload["language"],
    )
    response = GradeAnswerResponse(
        grade=result.grade,
        reasoning=result.reasoning,
        card_front=card.front,
        card_back=card.back,
        grading_info={
            "model_used": result.model_used,
            "processing_time_ms": result.processing_time_ms,
        },
    )
    return response.model_dump(mode="json")


def execute_advice(user_id: str, payload: dict) -> dict:
    """GET(→POST) /advice 相当（LearningAdviceResponse）。"""
    user = UserService().get_or_create_user(user_id)
    user_timezone = user.settings.get("timezone", "Asia/Tokyo")

    review_summary = ReviewService().get_review_summary(
        user_id, user_timezone=user_timezone
    )
    review_summary_dict = dataclasses.asdict(review_summary)

    ai_service = create_ai_service()
    result = ai_service.get_learning_advice(
        review_summary=review_summary_dict,
        language=payload["language"],
    )
    response = LearningAdviceResponse(
        advice_text=result.advice_text,
        weak_areas=result.weak_areas,
        recommendations=result.recommendations,
        study_stats={
            "total_reviews": review_summary.total_reviews,
            "average_grade": review_summary.average_grade,
            "total_cards": review_summary.total_cards,
            "cards_due_today": review_summary.cards_due_today,
            "streak_days": review_summary.streak_days,
        },
        advice_info={
            "model_used": result.model_used,
            "processing_time_ms": result.processing_time_ms,
        },
    )
    return response.model_dump(mode="json")


def execute_tutor_start(user_id: str, payload: dict) -> dict:
    """POST /tutor/sessions 相当（TutorSessionResponse）。"""
    session = _get_tutor_service().start_session(
        user_id=user_id,
        deck_id=payload["deck_id"],
        mode=payload["mode"],
    )
    return session.model_dump(mode="json")


def execute_tutor_message(user_id: str, payload: dict) -> dict:
    """POST /tutor/sessions/{id}/messages 相当（SendMessageResponse）。

    in-flight ロック・終了済みセッションへの書き込み防止（レビュー #9 対応）は
    send_message 内でそのまま有効。
    """
    result = _get_tutor_service().send_message(
        user_id=user_id,
        session_id=payload["session_id"],
        content=payload["content"],
    )
    return result.model_dump(mode="json")


# job_type → executor のディスパッチテーブル
EXECUTORS: Dict[str, Callable[[str, dict], dict]] = {
    "generate": execute_generate,
    "generate_from_url": execute_generate_from_url,
    "refine": execute_refine,
    "grade_ai": execute_grade_ai,
    "advice": execute_advice,
    "tutor_start": execute_tutor_start,
    "tutor_message": execute_tutor_message,
}

# heavy キュー（AiJobHeavyQueue）で処理する job_type。それ以外は interactive。
HEAVY_JOB_TYPES = frozenset({"generate_from_url"})


def execute_job(job: dict) -> dict:
    """ジョブレコードに対応する executor を実行して result を返す。

    Raises:
        KeyError 等はそのまま送出（呼び出し側で classify → internal）。
    """
    executor = EXECUTORS[job["job_type"]]
    return executor(job["user_id"], job["payload"])


def is_supported_schema(job: dict) -> bool:
    """ジョブの schema_version が現行実装で処理可能かを返す。"""
    from services.ai_job_store import SCHEMA_VERSION

    return int(job.get("schema_version", 0)) == SCHEMA_VERSION

"""AI 非同期ジョブのエラー分類 (ai-async-jobs)。

ワーカー実行時に発生した例外を、failed ジョブの ``error`` フィールド
``{status, code, message}`` に一元的に変換する。

status / message は現行の同期ハンドラー（ai_handler / tutor_handler /
api.shared.map_ai_error_to_http）の分類・文言と完全一致させること。
フロントは `ApiError.status` の分岐と、tutor 系では 422 + メッセージ文言で
UI を出し分けるため、ここの文言変更は UI 回帰になる（設計レビュー C-3/H-2）。
"""

from __future__ import annotations

from dataclasses import dataclass

from services.ai_service import (
    AIParseError,
    AIProviderError,
    AIRateLimitError,
    AIServiceError,
    AITimeoutError,
)
from services.card_service import CardNotFoundError
from services.tutor_ai_service import TutorAIServiceError, TutorAITimeoutError
from services.tutor_errors import (
    ConcurrentSendError,
    DeckNotFoundError,
    EmptyDeckError,
    InsufficientReviewDataError,
    MessageLimitError,
    SessionEndedError,
    SessionNotFoundError,
)
from services.url_content_service import ContentFetchError
from services.url_generation_service import EmptyContentError


class NoCardsGeneratedError(Exception):
    """URL からカードを 1 枚も生成できなかった（現行 ai_handler の 422 と同じ扱い）。"""


@dataclass(frozen=True)
class JobError:
    """failed ジョブに記録するエラー情報。"""

    status: int
    code: str
    message: str

    def to_dict(self) -> dict:
        return {"status": self.status, "code": self.code, "message": self.message}


def classify_ai_job_error(exc: Exception) -> JobError:
    """例外を JobError に分類する。

    分類の順序は「具象 → 抽象」。ここに無い例外は internal(500) に落ちる。
    """
    # --- コンテンツ取得系（現行 ai_handler.generate_from_url の分岐を移設） ---
    if isinstance(exc, ContentFetchError):
        error_msg = str(exc)
        lowered = error_msg.lower()
        if "timeout" in lowered:
            return JobError(408, "content_fetch_timeout", error_msg)
        if "private" in lowered or "blocked" in lowered:
            return JobError(403, "content_forbidden", error_msg)
        if "supported" in lowered or "meaningful" in lowered:
            return JobError(422, "content_unsupported", error_msg)
        return JobError(502, "content_fetch_error", error_msg)
    if isinstance(exc, EmptyContentError):
        return JobError(
            422,
            "content_unsupported",
            "Could not extract meaningful text content from the page",
        )
    if isinstance(exc, NoCardsGeneratedError):
        return JobError(
            422, "content_unsupported", "Failed to generate cards from the page content"
        )

    # --- Tutor 系（現行 tutor_handler の分岐と同一の status / 文言） ---
    if isinstance(exc, SessionNotFoundError):
        return JobError(404, "not_found", str(exc))
    if isinstance(exc, DeckNotFoundError):
        return JobError(404, "not_found", str(exc))
    if isinstance(exc, MessageLimitError):
        # 現行 429 を維持（409 に変更しない。設計レビュー H-4）
        return JobError(429, "message_limit", str(exc))
    if isinstance(exc, ConcurrentSendError):
        return JobError(
            409, "conflict", "別のメッセージを処理中です。少し待ってからお試しください。"
        )
    if isinstance(exc, SessionEndedError):
        return JobError(409, "conflict", str(exc))
    if isinstance(exc, (EmptyDeckError, InsufficientReviewDataError)):
        # 現行 422 + 例外メッセージそのまま（フロントは 422 + 文言で UI を出し分ける）
        return JobError(422, "validation_error", str(exc))
    if isinstance(exc, TutorAITimeoutError):
        return JobError(504, "ai_timeout", "AI応答がタイムアウトしました。もう一度お試しください。")
    if isinstance(exc, TutorAIServiceError):
        return JobError(503, "ai_unavailable", "チューター機能が現在利用できません。")

    # --- カード系 ---
    if isinstance(exc, CardNotFoundError):
        return JobError(404, "not_found", "Not Found")

    # --- AI サービス系（現行 map_ai_error_to_http と同一の status / 文言） ---
    if isinstance(exc, AITimeoutError):
        return JobError(504, "ai_timeout", "AI service timeout")
    if isinstance(exc, AIRateLimitError):
        return JobError(429, "ai_rate_limit", "AI service rate limit exceeded")
    if isinstance(exc, AIProviderError):
        return JobError(503, "ai_unavailable", "AI service unavailable")
    if isinstance(exc, AIParseError):
        return JobError(500, "ai_error", "AI service response parse error")
    if isinstance(exc, AIServiceError):
        return JobError(500, "ai_error", "AI service error")

    # --- 想定外 ---
    return JobError(500, "internal", "Internal Server Error")

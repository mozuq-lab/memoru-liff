"""Unit tests for services/ai_job_errors.py (ai-async-jobs).

status / message は現行同期ハンドラーの分類・文言と完全一致していること
（フロントは status + 文言で UI を出し分ける。設計レビュー C-2/C-3/H-2）。
"""

import pytest

from services.ai_job_errors import NoCardsGeneratedError, classify_ai_job_error
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


@pytest.mark.parametrize(
    ("exc", "expected_status", "expected_code"),
    [
        # AI サービス系（map_ai_error_to_http と同一分類）
        (AITimeoutError("t"), 504, "ai_timeout"),
        (AIRateLimitError("r"), 429, "ai_rate_limit"),
        (AIProviderError("p"), 503, "ai_unavailable"),
        (AIParseError("x"), 500, "ai_error"),
        (AIServiceError("generic"), 500, "ai_error"),
        # コンテンツ取得系（ai_handler の分岐と同一。文字列判定）
        (ContentFetchError("Request timeout while fetching"), 408, "content_fetch_timeout"),
        (ContentFetchError("URL points to a private address"), 403, "content_forbidden"),
        (ContentFetchError("Access blocked by the site"), 403, "content_forbidden"),
        (ContentFetchError("Content type not supported"), 422, "content_unsupported"),
        (ContentFetchError("No meaningful text found"), 422, "content_unsupported"),
        (ContentFetchError("Connection reset"), 502, "content_fetch_error"),
        (EmptyContentError("no text"), 422, "content_unsupported"),
        (NoCardsGeneratedError("none"), 422, "content_unsupported"),
        # Tutor 系（tutor_handler と同一分類）
        (SessionNotFoundError("Session x not found"), 404, "not_found"),
        (DeckNotFoundError("Deck y not found"), 404, "not_found"),
        (MessageLimitError("limit"), 429, "message_limit"),  # 現行 429 維持
        (ConcurrentSendError("busy"), 409, "conflict"),
        (SessionEndedError("Session x is ended"), 409, "conflict"),
        (EmptyDeckError("このデッキにはカードがありません。"), 422, "validation_error"),
        (
            InsufficientReviewDataError("レビュー履歴が不足しています。"),
            422,
            "validation_error",
        ),
        (TutorAITimeoutError("t"), 504, "ai_timeout"),
        (TutorAIServiceError("cfg"), 503, "ai_unavailable"),
        # カード系
        (CardNotFoundError("card"), 404, "not_found"),
        # 想定外
        (RuntimeError("boom"), 500, "internal"),
        (KeyError("job_type"), 500, "internal"),
    ],
)
def test_classification(exc, expected_status, expected_code):
    job_error = classify_ai_job_error(exc)
    assert job_error.status == expected_status
    assert job_error.code == expected_code
    assert job_error.message  # 必ず非空メッセージを持つ


class TestMessagesMatchSyncHandlers:
    """フロントが依存する文言の完全一致（抜粋）。"""

    def test_ai_timeout_message(self):
        assert classify_ai_job_error(AITimeoutError("x")).message == "AI service timeout"

    def test_rate_limit_message(self):
        assert (
            classify_ai_job_error(AIRateLimitError("x")).message
            == "AI service rate limit exceeded"
        )

    def test_empty_deck_keeps_exception_message(self):
        """TutorContext は 422 + 「カードがありません」の文言で UI を出し分ける。"""
        msg = "このデッキにはカードがありません。カードを追加してからセッションを開始してください。"
        assert classify_ai_job_error(EmptyDeckError(msg)).message == msg

    def test_insufficient_review_keeps_exception_message(self):
        msg = "レビュー履歴が不足しています。Free Talk モードをお試しください。"
        assert classify_ai_job_error(InsufficientReviewDataError(msg)).message == msg

    def test_concurrent_send_message(self):
        assert (
            classify_ai_job_error(ConcurrentSendError("x")).message
            == "別のメッセージを処理中です。少し待ってからお試しください。"
        )

    def test_to_dict_shape(self):
        d = classify_ai_job_error(AITimeoutError("x")).to_dict()
        assert set(d.keys()) == {"status", "code", "message"}

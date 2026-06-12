"""Unit tests for url_generation_service core/分類ロジック (R-2).

検証:
  - コア関数の例外分類（ContentFetchError→transient、空テキスト→permanent、
    カード 0 件→permanent、AIParseError→transient、DynamoDB ClientError→transient）。
  - 成功時のみ push まで到達。
  - インラインラッパー generate_and_push_url_cards は例外を握りつぶし通知して
    正常 return（現行挙動を維持）。
"""

from dataclasses import dataclass
from typing import List
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

import services.url_generation_service as svc
from services.url_content_service import ContentFetchError
from services.ai_service import AIParseError, GeneratedCard, GenerationResult


@dataclass
class _FakePage:
    url: str = "https://example.com/a"
    title: str = "Title"
    text_content: str = "本文 " * 200


def _result_with_cards(n: int) -> GenerationResult:
    cards: List[GeneratedCard] = [
        GeneratedCard(front=f"q{i}", back=f"a{i}", suggested_tags=[]) for i in range(n)
    ]
    return GenerationResult(
        cards=cards, input_length=100, model_used="m", processing_time_ms=1
    )


@pytest.fixture
def patched(monkeypatch):
    """fetch/chunk/ai/store/line を差し替えるための共通パッチ群を返す。"""
    fetch = MagicMock(return_value=_FakePage())
    ai = MagicMock()
    ai.generate_cards_from_chunks.return_value = _result_with_cards(3)
    store = MagicMock()
    store.store_pending_cards.return_value = "REF123"
    line = MagicMock()

    monkeypatch.setattr(svc, "url_cards_store", store)
    monkeypatch.setattr(svc, "line_service", line)

    content_service = MagicMock()
    content_service.fetch_content = fetch
    monkeypatch.setattr(svc, "UrlContentService", lambda: content_service)
    monkeypatch.setattr(svc, "create_ai_service", lambda: ai)

    return {"fetch": fetch, "ai": ai, "store": store, "line": line}


class TestCoreClassification:
    def test_success_pushes_carousel(self, patched):
        svc.generate_url_cards_core("u", "line-1", "https://example.com/a")
        # 成功時に push されている。
        patched["line"].push_message.assert_called_once()
        patched["store"].store_pending_cards.assert_called_once()

    def test_content_fetch_error_is_transient(self, patched):
        patched["fetch"].side_effect = ContentFetchError("network down")
        with pytest.raises(svc.UrlGenerationTransientError) as ei:
            svc.generate_url_cards_core("u", "line-1", "https://example.com/a")
        assert ei.value.user_message  # ユーザー向けメッセージを持つ
        patched["line"].push_message.assert_not_called()

    def test_empty_text_is_permanent(self, patched):
        patched["fetch"].return_value = _FakePage(text_content="   ")
        with pytest.raises(svc.UrlGenerationPermanentError) as ei:
            svc.generate_url_cards_core("u", "line-1", "https://example.com/a")
        assert "抽出" in ei.value.user_message

    def test_no_cards_is_permanent(self, patched):
        patched["ai"].generate_cards_from_chunks.return_value = _result_with_cards(0)
        with pytest.raises(svc.UrlGenerationPermanentError):
            svc.generate_url_cards_core("u", "line-1", "https://example.com/a")

    def test_ai_parse_error_is_transient(self, patched):
        # LLM 出力は非決定的なため AIParseError は transient 扱い。
        patched["ai"].generate_cards_from_chunks.side_effect = AIParseError("bad json")
        with pytest.raises(svc.UrlGenerationTransientError):
            svc.generate_url_cards_core("u", "line-1", "https://example.com/a")

    def test_dynamodb_client_error_is_transient(self, patched):
        patched["store"].store_pending_cards.side_effect = ClientError(
            {"Error": {"Code": "ProvisionedThroughputExceededException"}}, "PutItem"
        )
        with pytest.raises(svc.UrlGenerationTransientError):
            svc.generate_url_cards_core("u", "line-1", "https://example.com/a")
        # push（プレビュー）には到達しない。
        patched["line"].push_message.assert_not_called()


class TestInlineWrapper:
    def test_wrapper_swallows_transient_and_notifies(self, patched):
        patched["fetch"].side_effect = ContentFetchError("network down")
        # 例外を投げず正常 return（現行挙動）。
        svc.generate_and_push_url_cards("u", "line-1", "https://example.com/a")
        # エラー通知の push が行われる。
        assert patched["line"].push_message.called

    def test_wrapper_swallows_permanent_and_notifies(self, patched):
        patched["fetch"].return_value = _FakePage(text_content="   ")
        svc.generate_and_push_url_cards("u", "line-1", "https://example.com/a")
        assert patched["line"].push_message.called

    def test_wrapper_swallows_unexpected_and_notifies(self, patched):
        patched["ai"].generate_cards_from_chunks.side_effect = RuntimeError("boom")
        svc.generate_and_push_url_cards("u", "line-1", "https://example.com/a")
        assert patched["line"].push_message.called

    def test_wrapper_success_pushes_carousel(self, patched):
        svc.generate_and_push_url_cards("u", "line-1", "https://example.com/a")
        patched["line"].push_message.assert_called_once()


class TestNotifyHelper:
    def test_notify_failure_swallows_push_error(self, monkeypatch):
        line = MagicMock()
        line.push_message.side_effect = RuntimeError("push down")
        monkeypatch.setattr(svc, "line_service", line)
        # 例外を伝播しない。
        svc.notify_generation_failure("line-1", "msg")

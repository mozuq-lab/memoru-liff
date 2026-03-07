"""Unit tests for TutorAIService — TDD Red Phase.

Tests Bedrock API call, multi-turn conversation, and related card extraction.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


class TestTutorAIServiceInit:
    """Tests for TutorAIService initialization."""

    def test_default_model_from_env(self):
        with patch.dict("os.environ", {"TUTOR_MODEL_ID": "test-model-id"}):
            from services.tutor_ai_service import TutorAIService

            service = TutorAIService()
            assert service.model_id == "test-model-id"

    def test_fallback_to_bedrock_model_id(self):
        with patch.dict(
            "os.environ",
            {"TUTOR_MODEL_ID": "", "BEDROCK_MODEL_ID": "fallback-model"},
            clear=False,
        ):
            from services.tutor_ai_service import TutorAIService

            service = TutorAIService()
            assert service.model_id == "fallback-model"

    def test_explicit_model_id_overrides_env(self):
        from services.tutor_ai_service import TutorAIService

        service = TutorAIService(model_id="explicit-model", bedrock_client=MagicMock())
        assert service.model_id == "explicit-model"


class TestGenerateResponse:
    """Tests for generate_response method."""

    def test_generate_response_returns_content_and_related_cards(self):
        from services.tutor_ai_service import TutorAIService

        mock_client = MagicMock()
        mock_response_body = json.dumps(
            {
                "content": [
                    {
                        "text": "この概念について説明します。\n\n[RELATED_CARDS: card_abc123, card_def456]"
                    }
                ],
            }
        )
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=MagicMock(return_value=mock_response_body.encode()))
        }

        service = TutorAIService(model_id="test-model", bedrock_client=mock_client)

        content, related_cards = service.generate_response(
            system_prompt="You are a tutor.",
            messages=[
                {"role": "user", "content": "このカードの意味を教えてください"},
            ],
        )

        assert isinstance(content, str)
        assert len(content) > 0
        assert isinstance(related_cards, list)

    def test_generate_response_sends_system_prompt(self):
        from services.tutor_ai_service import TutorAIService

        mock_client = MagicMock()
        mock_response_body = json.dumps(
            {"content": [{"text": "OK"}]}
        )
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=MagicMock(return_value=mock_response_body.encode()))
        }

        service = TutorAIService(model_id="test-model", bedrock_client=mock_client)
        service.generate_response(
            system_prompt="Custom system prompt",
            messages=[{"role": "user", "content": "hello"}],
        )

        call_args = mock_client.invoke_model.call_args
        request_body = json.loads(call_args[1]["body"])
        assert request_body["system"] == "Custom system prompt"

    def test_generate_response_sends_messages(self):
        from services.tutor_ai_service import TutorAIService

        mock_client = MagicMock()
        mock_response_body = json.dumps({"content": [{"text": "OK"}]})
        mock_client.invoke_model.return_value = {
            "body": MagicMock(read=MagicMock(return_value=mock_response_body.encode()))
        }

        service = TutorAIService(model_id="test-model", bedrock_client=mock_client)
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "question?"},
        ]
        service.generate_response(system_prompt="sys", messages=messages)

        call_args = mock_client.invoke_model.call_args
        request_body = json.loads(call_args[1]["body"])
        assert request_body["messages"] == messages


class TestExtractRelatedCards:
    """Tests for related card extraction from AI response."""

    def test_extract_cards_from_tagged_response(self):
        from services.tutor_ai_service import TutorAIService

        service = TutorAIService(model_id="test", bedrock_client=MagicMock())
        text = "説明文です。\n\n[RELATED_CARDS: card_abc123, card_def456]"
        cards = service.extract_related_cards(text)
        assert "card_abc123" in cards
        assert "card_def456" in cards

    def test_extract_no_cards_when_no_tag(self):
        from services.tutor_ai_service import TutorAIService

        service = TutorAIService(model_id="test", bedrock_client=MagicMock())
        text = "これは普通の返答です。"
        cards = service.extract_related_cards(text)
        assert cards == []

    def test_extract_single_card(self):
        from services.tutor_ai_service import TutorAIService

        service = TutorAIService(model_id="test", bedrock_client=MagicMock())
        text = "解説。[RELATED_CARDS: card_xyz789]"
        cards = service.extract_related_cards(text)
        assert cards == ["card_xyz789"]

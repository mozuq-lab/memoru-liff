"""Unit tests for TutorAIService — Bedrock and Strands implementations.

Tests Bedrock API call, Strands Agent multi-turn conversation,
related card extraction, and factory function.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


# ===================================================================
# BedrockTutorAIService (TutorAIService alias) tests
# ===================================================================


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
        from services.tutor_ai_service import extract_related_cards

        text = "説明文です。\n\n[RELATED_CARDS: card_abc123, card_def456]"
        cards = extract_related_cards(text)
        assert "card_abc123" in cards
        assert "card_def456" in cards

    def test_extract_no_cards_when_no_tag(self):
        from services.tutor_ai_service import extract_related_cards

        text = "これは普通の返答です。"
        cards = extract_related_cards(text)
        assert cards == []

    def test_extract_single_card(self):
        from services.tutor_ai_service import extract_related_cards

        text = "解説。[RELATED_CARDS: card_xyz789]"
        cards = extract_related_cards(text)
        assert cards == ["card_xyz789"]


class TestCleanResponseText:
    """Tests for clean_response_text function."""

    def test_removes_related_cards_tag(self):
        from services.tutor_ai_service import clean_response_text

        text = "解説文です。\n\n[RELATED_CARDS: card_abc, card_def]"
        cleaned = clean_response_text(text)
        assert "[RELATED_CARDS" not in cleaned
        assert "解説文です。" in cleaned

    def test_no_tag_returns_unchanged(self):
        from services.tutor_ai_service import clean_response_text

        text = "普通のテキスト"
        assert clean_response_text(text) == "普通のテキスト"


# ===================================================================
# StrandsTutorAIService tests
# ===================================================================


class TestStrandsTutorAIServiceInit:
    """Tests for StrandsTutorAIService initialization."""

    @patch("services.tutor_ai_service.os.environ.get")
    def test_dev_environment_creates_ollama_model(self, mock_env_get):
        """Dev environment should use OllamaModel."""
        mock_env_get.side_effect = lambda key, default="": {
            "ENVIRONMENT": "dev",
            "OLLAMA_HOST": "http://localhost:11434",
            "OLLAMA_MODEL": "llama3.2",
        }.get(key, default)

        mock_ollama_model = MagicMock()
        with patch.dict("sys.modules", {"strands.models.ollama": MagicMock()}):
            with patch(
                "services.tutor_ai_service.StrandsTutorAIService._create_model",
                return_value=(mock_ollama_model, "strands_ollama"),
            ):
                from services.tutor_ai_service import StrandsTutorAIService

                service = StrandsTutorAIService(environment="dev")
                assert service.model_used == "strands_ollama"

    def test_prod_environment_creates_bedrock_model(self):
        """Prod environment should use BedrockModel."""
        mock_bedrock_model = MagicMock()
        with patch(
            "services.tutor_ai_service.StrandsTutorAIService._create_model",
            return_value=(mock_bedrock_model, "strands_bedrock"),
        ):
            from services.tutor_ai_service import StrandsTutorAIService

            service = StrandsTutorAIService(environment="prod")
            assert service.model_used == "strands_bedrock"


class TestStrandsTutorAIServiceGenerateResponse:
    """Tests for StrandsTutorAIService.generate_response."""

    def test_generate_response_with_strands_agent(self):
        """Strands Agent should be called with system_prompt and conversation history."""
        from services.tutor_ai_service import StrandsTutorAIService

        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "応答です。[RELATED_CARDS: card_1]"

        with patch(
            "services.tutor_ai_service.StrandsTutorAIService._create_model",
            return_value=(MagicMock(), "strands_ollama"),
        ):
            service = StrandsTutorAIService(environment="dev")
            service._create_agent = MagicMock(return_value=mock_agent_instance)

            content, related_cards = service.generate_response(
                system_prompt="You are a tutor.",
                messages=[
                    {"role": "user", "content": "hello"},
                    {"role": "assistant", "content": "hi"},
                    {"role": "user", "content": "質問です"},
                ],
            )

            # _create_agent was called with system_prompt and history (without last message)
            create_kwargs = service._create_agent.call_args[1]
            assert create_kwargs["system_prompt"] == "You are a tutor."
            assert len(create_kwargs["messages"]) == 2  # history without last user msg
            assert create_kwargs["messages"][0]["role"] == "user"
            assert create_kwargs["messages"][0]["content"] == [{"text": "hello"}]
            assert create_kwargs["messages"][1]["role"] == "assistant"
            assert create_kwargs["messages"][1]["content"] == [{"text": "hi"}]

            # Agent was called with the last user message
            mock_agent_instance.assert_called_once_with("質問です")

            assert "応答です。" in content
            assert "card_1" in related_cards

    def test_generate_response_single_message(self):
        """With a single user message, history should be empty."""
        from services.tutor_ai_service import StrandsTutorAIService

        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = "はい、説明します。"

        with patch(
            "services.tutor_ai_service.StrandsTutorAIService._create_model",
            return_value=(MagicMock(), "strands_ollama"),
        ):
            service = StrandsTutorAIService(environment="dev")
            service._create_agent = MagicMock(return_value=mock_agent_instance)

            content, related_cards = service.generate_response(
                system_prompt="sys",
                messages=[{"role": "user", "content": "最初の質問"}],
            )

            create_kwargs = service._create_agent.call_args[1]
            assert create_kwargs["messages"] == []  # no history
            mock_agent_instance.assert_called_once_with("最初の質問")
            assert content == "はい、説明します。"
            assert related_cards == []

    def test_generate_response_timeout_error(self):
        """TimeoutError should be wrapped in TutorAITimeoutError."""
        from services.tutor_ai_service import StrandsTutorAIService, TutorAITimeoutError

        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = TimeoutError("timed out")

        with patch(
            "services.tutor_ai_service.StrandsTutorAIService._create_model",
            return_value=(MagicMock(), "strands_ollama"),
        ):
            service = StrandsTutorAIService(environment="dev")
            service._create_agent = MagicMock(return_value=mock_agent_instance)

            with pytest.raises(TutorAITimeoutError):
                service.generate_response(
                    system_prompt="sys",
                    messages=[{"role": "user", "content": "hello"}],
                )

    def test_generate_response_connection_error(self):
        """ConnectionError should be wrapped in TutorAIServiceError."""
        from services.tutor_ai_service import StrandsTutorAIService, TutorAIServiceError

        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = ConnectionError("connection refused")

        with patch(
            "services.tutor_ai_service.StrandsTutorAIService._create_model",
            return_value=(MagicMock(), "strands_ollama"),
        ):
            service = StrandsTutorAIService(environment="dev")
            service._create_agent = MagicMock(return_value=mock_agent_instance)

            with pytest.raises(TutorAIServiceError, match="connection"):
                service.generate_response(
                    system_prompt="sys",
                    messages=[{"role": "user", "content": "hello"}],
                )


# ===================================================================
# Factory function tests
# ===================================================================


class TestCreateTutorAIService:
    """Tests for create_tutor_ai_service factory."""

    def test_returns_bedrock_when_use_strands_false(self):
        from services.tutor_ai_service import BedrockTutorAIService, create_tutor_ai_service

        service = create_tutor_ai_service(use_strands=False)
        assert isinstance(service, BedrockTutorAIService)

    def test_returns_strands_when_use_strands_true(self):
        from services.tutor_ai_service import StrandsTutorAIService, create_tutor_ai_service

        with patch(
            "services.tutor_ai_service.StrandsTutorAIService._create_model",
            return_value=(MagicMock(), "strands_bedrock"),
        ):
            service = create_tutor_ai_service(use_strands=True)
            assert isinstance(service, StrandsTutorAIService)

    def test_reads_use_strands_env_var(self):
        from services.tutor_ai_service import BedrockTutorAIService, create_tutor_ai_service

        with patch.dict("os.environ", {"USE_STRANDS": "false"}):
            service = create_tutor_ai_service()
            assert isinstance(service, BedrockTutorAIService)

    def test_reads_use_strands_env_var_true(self):
        from services.tutor_ai_service import StrandsTutorAIService, create_tutor_ai_service

        with patch(
            "services.tutor_ai_service.StrandsTutorAIService._create_model",
            return_value=(MagicMock(), "strands_ollama"),
        ):
            with patch.dict("os.environ", {"USE_STRANDS": "true"}):
                service = create_tutor_ai_service()
                assert isinstance(service, StrandsTutorAIService)

    def test_factory_wraps_initialization_error(self):
        """Initialization failures should be wrapped in TutorAIServiceError."""
        from services.tutor_ai_service import TutorAIServiceError, create_tutor_ai_service

        with patch(
            "services.tutor_ai_service.StrandsTutorAIService._create_model",
            side_effect=RuntimeError("Ollama not running"),
        ):
            with pytest.raises(TutorAIServiceError, match="Failed to initialize"):
                create_tutor_ai_service(use_strands=True)

    def test_tutor_ai_service_is_alias_for_bedrock(self):
        from services.tutor_ai_service import BedrockTutorAIService, TutorAIService

        assert TutorAIService is BedrockTutorAIService


class TestStrandsEmptyMessages:
    """Edge case: empty messages list."""

    def test_generate_response_empty_messages_raises(self):
        from services.tutor_ai_service import StrandsTutorAIService, TutorAIServiceError

        with patch(
            "services.tutor_ai_service.StrandsTutorAIService._create_model",
            return_value=(MagicMock(), "strands_ollama"),
        ):
            service = StrandsTutorAIService(environment="dev")

            with pytest.raises(TutorAIServiceError, match="must not be empty"):
                service.generate_response(
                    system_prompt="sys",
                    messages=[],
                )

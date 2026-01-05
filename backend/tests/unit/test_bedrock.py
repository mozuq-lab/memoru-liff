"""Unit tests for Bedrock service and AI card generation."""

import json
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from src.services.bedrock import (
    BedrockService,
    BedrockTimeoutError,
    BedrockRateLimitError,
    BedrockInternalError,
    BedrockParseError,
    GeneratedCard,
)
from src.services.prompts import get_card_generation_prompt


class TestPrompts:
    """Tests for prompt generation."""

    def test_japanese_prompt_generation(self):
        """Test Japanese prompt generation."""
        prompt = get_card_generation_prompt(
            input_text="テスト入力テキスト",
            card_count=5,
            difficulty="medium",
            language="ja",
        )

        assert "フラッシュカード作成の専門家" in prompt
        assert "5枚作成" in prompt
        assert "テスト入力テキスト" in prompt
        assert "medium" in prompt

    def test_english_prompt_generation(self):
        """Test English prompt generation."""
        prompt = get_card_generation_prompt(
            input_text="Test input text",
            card_count=3,
            difficulty="hard",
            language="en",
        )

        assert "expert at creating flashcards" in prompt
        assert "3 effective flashcards" in prompt
        assert "Test input text" in prompt
        assert "hard" in prompt

    def test_difficulty_levels(self):
        """Test different difficulty levels are included."""
        for difficulty in ["easy", "medium", "hard"]:
            prompt = get_card_generation_prompt(
                input_text="Test",
                card_count=1,
                difficulty=difficulty,
                language="ja",
            )
            assert difficulty in prompt


class TestBedrockServiceParsing:
    """Tests for BedrockService response parsing."""

    @pytest.fixture
    def bedrock_service(self):
        """Create BedrockService with mock client."""
        mock_client = MagicMock()
        return BedrockService(bedrock_client=mock_client)

    def test_parse_valid_json_response(self, bedrock_service):
        """Test parsing valid JSON response."""
        response = '''```json
{
  "cards": [
    {"front": "Question 1", "back": "Answer 1", "tags": ["tag1"]},
    {"front": "Question 2", "back": "Answer 2", "tags": ["tag2"]}
  ]
}
```'''

        cards = bedrock_service._parse_response(response)

        assert len(cards) == 2
        assert cards[0].front == "Question 1"
        assert cards[0].back == "Answer 1"
        assert "AI生成" in cards[0].suggested_tags

    def test_parse_json_without_code_block(self, bedrock_service):
        """Test parsing JSON without markdown code block."""
        response = '''{"cards": [{"front": "Q", "back": "A", "tags": []}]}'''

        cards = bedrock_service._parse_response(response)

        assert len(cards) == 1
        assert cards[0].front == "Q"

    def test_parse_skips_invalid_cards(self, bedrock_service):
        """Test that invalid cards are skipped."""
        response = '''```json
{
  "cards": [
    {"front": "Valid", "back": "Valid"},
    {"front": "", "back": "Empty front"},
    {"front": "Empty back", "back": ""},
    {"front": "Only front"},
    {"back": "Only back"}
  ]
}
```'''

        cards = bedrock_service._parse_response(response)

        # Only the first card is valid
        assert len(cards) == 1
        assert cards[0].front == "Valid"

    def test_parse_invalid_json(self, bedrock_service):
        """Test parsing invalid JSON raises error."""
        response = "This is not valid JSON"

        with pytest.raises(BedrockParseError):
            bedrock_service._parse_response(response)

    def test_parse_missing_cards_field(self, bedrock_service):
        """Test parsing response without cards field."""
        response = '''{"items": []}'''

        with pytest.raises(BedrockParseError):
            bedrock_service._parse_response(response)

    def test_parse_empty_cards(self, bedrock_service):
        """Test parsing response with no valid cards."""
        response = '''{"cards": []}'''

        with pytest.raises(BedrockParseError):
            bedrock_service._parse_response(response)


class TestBedrockServiceInvoke:
    """Tests for BedrockService API invocation."""

    @pytest.fixture
    def mock_bedrock_client(self):
        """Create mock Bedrock client."""
        return MagicMock()

    @pytest.fixture
    def bedrock_service(self, mock_bedrock_client):
        """Create BedrockService with mock client."""
        return BedrockService(bedrock_client=mock_bedrock_client)

    def test_invoke_success(self, bedrock_service, mock_bedrock_client):
        """Test successful API invocation."""
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": '```json\n{"cards": [{"front": "Q", "back": "A", "tags": []}]}\n```'}]
        }).encode()

        mock_bedrock_client.invoke_model.return_value = {"body": mock_response_body}

        result = bedrock_service.generate_cards(
            input_text="Test input text for card generation",
            card_count=1,
        )

        assert len(result.cards) == 1
        assert result.cards[0].front == "Q"
        assert result.processing_time_ms >= 0
        mock_bedrock_client.invoke_model.assert_called_once()

    def test_invoke_timeout_error(self, bedrock_service, mock_bedrock_client):
        """Test timeout error handling."""
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ReadTimeoutError", "Message": "Timeout"}},
            "InvokeModel",
        )

        with pytest.raises(BedrockTimeoutError):
            bedrock_service.generate_cards(
                input_text="Test input text",
                card_count=1,
            )

    def test_invoke_rate_limit_error(self, bedrock_service, mock_bedrock_client):
        """Test rate limit error with retry."""
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
            "InvokeModel",
        )

        with pytest.raises(BedrockRateLimitError):
            bedrock_service.generate_cards(
                input_text="Test input text",
                card_count=1,
            )

        # Should have retried
        assert mock_bedrock_client.invoke_model.call_count == 3  # Initial + 2 retries

    def test_invoke_internal_error(self, bedrock_service, mock_bedrock_client):
        """Test internal error with retry."""
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "InternalServerException", "Message": "Internal"}},
            "InvokeModel",
        )

        with pytest.raises(BedrockInternalError):
            bedrock_service.generate_cards(
                input_text="Test input text",
                card_count=1,
            )

        # Should have retried
        assert mock_bedrock_client.invoke_model.call_count == 3


class TestBedrockServiceRetry:
    """Tests for retry logic."""

    def test_retry_success_after_rate_limit(self):
        """Test successful retry after rate limit."""
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        # First call fails with rate limit, second succeeds
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": '{"cards": [{"front": "Q", "back": "A", "tags": []}]}'}]
        }).encode()

        mock_client.invoke_model.side_effect = [
            ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
                "InvokeModel",
            ),
            {"body": mock_response_body},
        ]

        result = service.generate_cards(
            input_text="Test input text",
            card_count=1,
        )

        assert len(result.cards) == 1
        assert mock_client.invoke_model.call_count == 2


class TestGenerateCardsValidation:
    """Tests for generate cards input validation."""

    def test_model_used_in_result(self):
        """Test that model ID is included in result."""
        mock_client = MagicMock()
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": '{"cards": [{"front": "Q", "back": "A", "tags": []}]}'}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        service = BedrockService(
            model_id="test-model-id",
            bedrock_client=mock_client,
        )

        result = service.generate_cards(
            input_text="Test input text",
            card_count=1,
        )

        assert result.model_used == "test-model-id"

    def test_input_length_in_result(self):
        """Test that input length is included in result."""
        mock_client = MagicMock()
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": '{"cards": [{"front": "Q", "back": "A", "tags": []}]}'}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        service = BedrockService(bedrock_client=mock_client)
        input_text = "This is a test input text"

        result = service.generate_cards(
            input_text=input_text,
            card_count=1,
        )

        assert result.input_length == len(input_text)

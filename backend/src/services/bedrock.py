"""Amazon Bedrock service for AI card generation."""

import json
import os
import re
import time
from dataclasses import dataclass
from typing import List, Literal, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from .prompts import DifficultyLevel, Language, get_card_generation_prompt


class BedrockServiceError(Exception):
    """Base exception for Bedrock service errors."""

    pass


class BedrockTimeoutError(BedrockServiceError):
    """Raised when Bedrock API times out."""

    pass


class BedrockRateLimitError(BedrockServiceError):
    """Raised when Bedrock API rate limit is exceeded."""

    pass


class BedrockInternalError(BedrockServiceError):
    """Raised when Bedrock API returns internal error."""

    pass


class BedrockParseError(BedrockServiceError):
    """Raised when Bedrock response cannot be parsed."""

    pass


@dataclass
class GeneratedCard:
    """A generated flashcard."""

    front: str
    back: str
    suggested_tags: List[str]


@dataclass
class GenerationResult:
    """Result of card generation."""

    cards: List[GeneratedCard]
    input_length: int
    model_used: str
    processing_time_ms: int


class BedrockService:
    """Service for interacting with Amazon Bedrock."""

    DEFAULT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
    MAX_TOKENS = 4096
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_TIMEOUT = 30
    MAX_RETRIES = 2

    def __init__(
        self,
        model_id: Optional[str] = None,
        bedrock_client=None,
    ):
        """Initialize BedrockService.

        Args:
            model_id: Bedrock model ID. Defaults to Claude 3 Haiku.
            bedrock_client: Optional boto3 Bedrock client for testing.
        """
        self.model_id = model_id or os.environ.get(
            "BEDROCK_MODEL_ID", self.DEFAULT_MODEL_ID
        )

        if bedrock_client:
            self.client = bedrock_client
        else:
            config = Config(
                read_timeout=self.DEFAULT_TIMEOUT,
                connect_timeout=5,
                retries={"max_attempts": 0},  # We handle retries ourselves
            )
            endpoint_url = os.environ.get("BEDROCK_ENDPOINT_URL")
            if endpoint_url:
                self.client = boto3.client(
                    "bedrock-runtime",
                    config=config,
                    endpoint_url=endpoint_url,
                )
            else:
                self.client = boto3.client("bedrock-runtime", config=config)

    def generate_cards(
        self,
        input_text: str,
        card_count: int = 5,
        difficulty: DifficultyLevel = "medium",
        language: Language = "ja",
    ) -> GenerationResult:
        """Generate flashcards from input text using AI.

        Args:
            input_text: Source text to generate cards from.
            card_count: Number of cards to generate (1-10).
            difficulty: Difficulty level (easy/medium/hard).
            language: Output language (ja/en).

        Returns:
            GenerationResult with generated cards and metadata.

        Raises:
            BedrockTimeoutError: If API times out.
            BedrockRateLimitError: If rate limit exceeded.
            BedrockInternalError: If API returns internal error.
            BedrockParseError: If response cannot be parsed.
        """
        start_time = time.time()

        # Generate prompt
        prompt = get_card_generation_prompt(
            input_text=input_text,
            card_count=card_count,
            difficulty=difficulty,
            language=language,
        )

        # Call Bedrock API with retry logic
        response_text = self._invoke_with_retry(prompt)

        # Parse response
        cards = self._parse_response(response_text)

        processing_time_ms = int((time.time() - start_time) * 1000)

        return GenerationResult(
            cards=cards,
            input_length=len(input_text),
            model_used=self.model_id,
            processing_time_ms=processing_time_ms,
        )

    def _invoke_with_retry(self, prompt: str) -> str:
        """Invoke Bedrock API with retry logic.

        Args:
            prompt: The prompt to send.

        Returns:
            Response text from the model.

        Raises:
            BedrockTimeoutError: If API times out after retries.
            BedrockRateLimitError: If rate limit exceeded after retries.
            BedrockInternalError: If internal error after retries.
        """
        last_error = None

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return self._invoke_claude(prompt)
            except BedrockTimeoutError:
                # Don't retry timeouts
                raise
            except BedrockRateLimitError as e:
                last_error = e
                if attempt < self.MAX_RETRIES:
                    # Exponential backoff
                    time.sleep(2 ** attempt)
                    continue
                raise
            except BedrockInternalError as e:
                last_error = e
                if attempt < self.MAX_RETRIES:
                    time.sleep(1)
                    continue
                raise

        raise last_error or BedrockServiceError("Unknown error during retry")

    def _invoke_claude(self, prompt: str) -> str:
        """Invoke Claude model via Bedrock.

        Args:
            prompt: The prompt to send.

        Returns:
            Response text from the model.

        Raises:
            BedrockTimeoutError: If API times out.
            BedrockRateLimitError: If rate limit exceeded.
            BedrockInternalError: If internal error.
        """
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.MAX_TOKENS,
            "temperature": self.DEFAULT_TEMPERATURE,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        }

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")

            if error_code in ("ReadTimeoutError", "ConnectTimeoutError"):
                raise BedrockTimeoutError("Bedrock API timed out") from e
            elif error_code in ("ThrottlingException", "TooManyRequestsException"):
                raise BedrockRateLimitError("Bedrock rate limit exceeded") from e
            elif error_code in ("InternalServerException", "ServiceException"):
                raise BedrockInternalError("Bedrock internal error") from e
            else:
                raise BedrockServiceError(f"Bedrock API error: {error_code}") from e
        except Exception as e:
            if "timeout" in str(e).lower():
                raise BedrockTimeoutError("Bedrock API timed out") from e
            raise BedrockServiceError(f"Bedrock API error: {e}") from e

    def _parse_response(self, response_text: str) -> List[GeneratedCard]:
        """Parse Bedrock response into card objects.

        Args:
            response_text: Raw text response from the model.

        Returns:
            List of GeneratedCard objects.

        Raises:
            BedrockParseError: If response cannot be parsed.
        """
        try:
            # Try to extract JSON from markdown code block
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response_text)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to parse the whole response as JSON
                json_str = response_text.strip()

            data = json.loads(json_str)

            if "cards" not in data:
                raise BedrockParseError("Response missing 'cards' field")

            cards = []
            for card_data in data["cards"]:
                # Validate required fields
                if "front" not in card_data or "back" not in card_data:
                    continue  # Skip invalid cards

                front = str(card_data["front"]).strip()
                back = str(card_data["back"]).strip()

                if not front or not back:
                    continue  # Skip empty cards

                tags = card_data.get("tags", [])
                if not isinstance(tags, list):
                    tags = []
                tags = [str(t).strip() for t in tags if t]

                # Add AI generation tag
                if "AI生成" not in tags and "AI Generated" not in tags:
                    tags.insert(0, "AI生成")

                cards.append(
                    GeneratedCard(
                        front=front,
                        back=back,
                        suggested_tags=tags,
                    )
                )

            if not cards:
                raise BedrockParseError("No valid cards in response")

            return cards

        except json.JSONDecodeError as e:
            raise BedrockParseError(f"Failed to parse JSON: {e}") from e
        except BedrockParseError:
            raise
        except Exception as e:
            raise BedrockParseError(f"Failed to parse response: {e}") from e

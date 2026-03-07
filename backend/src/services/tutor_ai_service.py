"""TutorAIService — Bedrock Messages API multi-turn conversation.

Handles AI dialogue for tutor sessions with system prompt injection
and related card extraction from AI responses.
"""

import json
import os
import re

import boto3
from aws_lambda_powertools import Logger
from botocore.config import Config
from botocore.exceptions import ClientError

logger = Logger()


class TutorAIServiceError(Exception):
    """Base exception for TutorAIService errors."""


class TutorAITimeoutError(TutorAIServiceError):
    """Raised when Bedrock API times out."""


class TutorAIService:
    """Service for multi-turn AI tutor conversations via Bedrock Messages API."""

    DEFAULT_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    MAX_TOKENS = 1024
    TEMPERATURE = 0.7
    TIMEOUT = 60
    # Approximate character limit for system prompt to stay within model input limits.
    # Claude allows ~200k tokens; using conservative char limit for safety.
    MAX_SYSTEM_PROMPT_CHARS = 150_000

    def __init__(
        self,
        model_id: str | None = None,
        bedrock_client=None,
    ):
        tutor_model = os.environ.get("TUTOR_MODEL_ID", "")
        fallback_model = os.environ.get("BEDROCK_MODEL_ID", self.DEFAULT_MODEL_ID)
        self.model_id = model_id or tutor_model or fallback_model

        if bedrock_client:
            self.client = bedrock_client
        else:
            config = Config(
                read_timeout=self.TIMEOUT,
                connect_timeout=5,
                retries={"max_attempts": 2},
            )
            endpoint_url = os.environ.get("BEDROCK_ENDPOINT_URL")
            if endpoint_url:
                self.client = boto3.client(
                    "bedrock-runtime", config=config, endpoint_url=endpoint_url
                )
            else:
                self.client = boto3.client("bedrock-runtime", config=config)

    def generate_response(
        self,
        system_prompt: str,
        messages: list[dict],
    ) -> tuple[str, list[str]]:
        """Generate an AI response for a multi-turn conversation.

        Args:
            system_prompt: Mode-specific system prompt with card context.
            messages: Conversation history as list of {"role": ..., "content": ...}.

        Returns:
            Tuple of (response_content, related_card_ids).

        Raises:
            TutorAIServiceError: If the Bedrock API call fails.
            TutorAITimeoutError: If the call times out.
        """
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.MAX_TOKENS,
            "temperature": self.TEMPERATURE,
            "system": system_prompt[:self.MAX_SYSTEM_PROMPT_CHARS],
            "messages": messages,
        }

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json",
            )

            response_body = json.loads(response["body"].read())
            content = response_body["content"][0]["text"]

            related_cards = self.extract_related_cards(content)

            return content, related_cards

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code in ("ReadTimeoutError", "ConnectTimeoutError"):
                raise TutorAITimeoutError("Bedrock API timed out") from e
            raise TutorAIServiceError(f"Bedrock API error: {error_code}") from e
        except TutorAIServiceError:
            raise
        except Exception as e:
            if "timeout" in str(e).lower():
                raise TutorAITimeoutError("Bedrock API timed out") from e
            raise TutorAIServiceError(f"Bedrock API error: {e}") from e

    def extract_related_cards(self, text: str) -> list[str]:
        """Extract related card IDs from AI response text.

        Looks for the pattern: [RELATED_CARDS: card_id1, card_id2]

        Args:
            text: AI response text.

        Returns:
            List of card ID strings.
        """
        match = re.search(r"\[RELATED_CARDS:\s*([^\]]+)\]", text)
        if not match:
            return []
        raw = match.group(1)
        return [card_id.strip() for card_id in raw.split(",") if card_id.strip()]

    def clean_response_text(self, text: str) -> str:
        """Remove the RELATED_CARDS tag from AI response text for display.

        Args:
            text: AI response text potentially containing the tag.

        Returns:
            Cleaned text without the tag.
        """
        return re.sub(r"\s*\[RELATED_CARDS:[^\]]*\]", "", text).strip()

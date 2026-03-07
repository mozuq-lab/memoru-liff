"""TutorAIService — AI service for tutor multi-turn conversations.

Supports two backends:
- BedrockTutorAIService: Bedrock Messages API direct invocation
- StrandsTutorAIService: Strands Agents SDK (Ollama for dev, Bedrock for prod)

Use create_tutor_ai_service() factory to select based on USE_STRANDS env var.
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
    """Raised when AI API times out."""


# ---------------------------------------------------------------------------
# Shared constants & helpers
# ---------------------------------------------------------------------------

_DEFAULT_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
_MAX_TOKENS = 1024
_TEMPERATURE = 0.7
_TIMEOUT = 60
_MAX_SYSTEM_PROMPT_CHARS = 150_000


def _resolve_tutor_model_id(model_id: str | None = None) -> str:
    """Resolve the model ID from explicit arg or env vars."""
    tutor_model = os.environ.get("TUTOR_MODEL_ID", "")
    fallback_model = os.environ.get("BEDROCK_MODEL_ID", _DEFAULT_MODEL_ID)
    return model_id or tutor_model or fallback_model


def extract_related_cards(text: str) -> list[str]:
    """Extract related card IDs from AI response text.

    Looks for the pattern: [RELATED_CARDS: card_id1, card_id2]
    """
    match = re.search(r"\[RELATED_CARDS:\s*([^\]]+)\]", text)
    if not match:
        return []
    raw = match.group(1)
    return [card_id.strip() for card_id in raw.split(",") if card_id.strip()]


def clean_response_text(text: str) -> str:
    """Remove the RELATED_CARDS tag from AI response text for display."""
    return re.sub(r"\s*\[RELATED_CARDS:[^\]]*\]", "", text).strip()


# ---------------------------------------------------------------------------
# BedrockTutorAIService — Bedrock Messages API direct invocation
# ---------------------------------------------------------------------------


class BedrockTutorAIService:
    """Service for multi-turn AI tutor conversations via Bedrock Messages API."""

    def __init__(
        self,
        model_id: str | None = None,
        bedrock_client=None,
    ):
        self.model_id = _resolve_tutor_model_id(model_id)

        if bedrock_client:
            self.client = bedrock_client
        else:
            config = Config(
                read_timeout=_TIMEOUT,
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
        """
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": _MAX_TOKENS,
            "temperature": _TEMPERATURE,
            "system": system_prompt[:_MAX_SYSTEM_PROMPT_CHARS],
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

            related_cards = extract_related_cards(content)

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

    # Keep instance methods for backward compatibility
    extract_related_cards = staticmethod(extract_related_cards)
    clean_response_text = staticmethod(clean_response_text)


# ---------------------------------------------------------------------------
# StrandsTutorAIService — Strands Agents SDK (Ollama for dev, Bedrock for prod)
# ---------------------------------------------------------------------------


class StrandsTutorAIService:
    """Strands SDK-based AI tutor service.

    ENVIRONMENT=dev uses OllamaModel (local LLM),
    otherwise uses BedrockModel (AWS Bedrock).
    """

    def __init__(self, environment: str | None = None):
        if environment is None:
            environment = os.environ.get("ENVIRONMENT", "prod")
        self.environment = environment
        self.model, self.model_used = self._create_model()

    def _create_model(self) -> tuple[object, str]:
        """Select model provider based on environment."""
        if self.environment == "dev":
            try:
                from strands.models.ollama import OllamaModel
            except ImportError:
                raise TutorAIServiceError(
                    "ollama package is required for dev environment. "
                    "Install with: pip install strands-agents[ollama]"
                )

            ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
            ollama_model = os.environ.get("OLLAMA_MODEL", "llama3.2")
            model = OllamaModel(host=ollama_host, model_id=ollama_model)
            return model, "strands_ollama"
        else:
            from strands.models import BedrockModel

            model_id = _resolve_tutor_model_id()
            model = BedrockModel(model_id=model_id)
            return model, "strands_bedrock"

    def _create_agent(self, system_prompt: str, messages: list[dict]):
        """Create a Strands Agent instance. Separated for testability."""
        from strands import Agent

        return Agent(
            model=self.model,
            system_prompt=system_prompt,
            messages=messages,
        )

    def generate_response(
        self,
        system_prompt: str,
        messages: list[dict],
    ) -> tuple[str, list[str]]:
        """Generate an AI response using Strands Agent.

        Args:
            system_prompt: Mode-specific system prompt with card context.
            messages: Conversation history as list of {"role": ..., "content": ...}.
                The last message must be a user message.

        Returns:
            Tuple of (response_content, related_card_ids).
        """
        try:
            # Split into history + latest user message
            if not messages:
                raise TutorAIServiceError("messages must not be empty")
            history = messages[:-1]
            last_user_content = messages[-1]["content"]

            # Convert history to Strands message format: content is list of {"text": ...}
            strands_messages = []
            for msg in history:
                strands_messages.append({
                    "role": msg["role"],
                    "content": [{"text": msg["content"]}],
                })
            agent = self._create_agent(
                system_prompt=system_prompt[:_MAX_SYSTEM_PROMPT_CHARS],
                messages=strands_messages,
            )
            response = agent(last_user_content)
            content = str(response)

            related_cards = extract_related_cards(content)
            return content, related_cards

        except TutorAIServiceError:
            raise
        except TimeoutError as e:
            raise TutorAITimeoutError(f"Agent timed out: {e}") from e
        except ConnectionError as e:
            raise TutorAIServiceError(f"Provider connection error: {e}") from e
        except Exception as e:
            error_str = str(e).lower()
            if "timeout" in error_str or "timed out" in error_str:
                raise TutorAITimeoutError(f"Agent timed out: {e}") from e
            raise TutorAIServiceError(f"AI service error: {e}") from e

    # Instance methods for compatibility
    extract_related_cards = staticmethod(extract_related_cards)
    clean_response_text = staticmethod(clean_response_text)


# ---------------------------------------------------------------------------
# Backward-compatible alias & factory
# ---------------------------------------------------------------------------

# Keep TutorAIService as alias for BedrockTutorAIService (backward compatibility)
TutorAIService = BedrockTutorAIService


def create_tutor_ai_service(
    use_strands: bool | None = None,
) -> BedrockTutorAIService | StrandsTutorAIService:
    """Create a tutor AI service based on USE_STRANDS env var.

    Args:
        use_strands: Explicitly select implementation. None reads USE_STRANDS env var.

    Returns:
        BedrockTutorAIService (direct Bedrock) or StrandsTutorAIService (Strands SDK).

    Raises:
        TutorAIServiceError: If service initialization fails.
    """
    if use_strands is None:
        use_strands = os.getenv("USE_STRANDS", "false").lower() == "true"

    try:
        if use_strands:
            return StrandsTutorAIService()
        else:
            return BedrockTutorAIService()
    except TutorAIServiceError:
        raise
    except Exception as e:
        raise TutorAIServiceError(f"Failed to initialize tutor AI service: {e}") from e

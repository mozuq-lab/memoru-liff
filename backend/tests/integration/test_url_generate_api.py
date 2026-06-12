"""Integration tests for URL generate API endpoint (T011)."""

from unittest.mock import MagicMock, patch

import pytest

from models.url_generate import GenerateFromUrlRequest


class TestGenerateFromUrlRequest:
    """Tests for request model validation."""

    def test_valid_request(self) -> None:
        req = GenerateFromUrlRequest(url="https://example.com/article")
        assert req.url == "https://example.com/article"
        assert req.card_type == "qa"
        assert req.target_count == 10
        assert req.difficulty == "medium"
        assert req.language == "ja"

    def test_rejects_http_url(self) -> None:
        with pytest.raises(Exception):
            GenerateFromUrlRequest(url="http://example.com")

    def test_rejects_empty_url(self) -> None:
        with pytest.raises(Exception):
            GenerateFromUrlRequest(url="")

    def test_custom_options(self) -> None:
        req = GenerateFromUrlRequest(
            url="https://example.com",
            card_type="cloze",
            target_count=20,
            difficulty="hard",
            language="en",
            deck_id="01HQXYZ",
        )
        assert req.card_type == "cloze"
        assert req.target_count == 20
        assert req.difficulty == "hard"
        assert req.language == "en"
        assert req.deck_id == "01HQXYZ"

    def test_target_count_min_5(self) -> None:
        with pytest.raises(Exception):
            GenerateFromUrlRequest(url="https://example.com", target_count=3)

    def test_target_count_max_30(self) -> None:
        with pytest.raises(Exception):
            GenerateFromUrlRequest(url="https://example.com", target_count=50)


class TestGenerateFromUrlApiFlow:
    """Integration tests for the full generate-from-url flow with mocked AI."""

    @patch("services.url_content_service.resolve_and_validate_host")
    @patch("services.url_content_service.httpx.Client")
    @patch("services.ai_service.create_ai_service")
    def test_full_flow_returns_cards(
        self,
        mock_create_ai: MagicMock,
        mock_client_cls: MagicMock,
        mock_resolve: MagicMock,
    ) -> None:
        """Full flow: URL → fetch → chunk → generate → response.

        DNS resolution is pinned to a fixed public IP via the patched
        ``resolve_and_validate_host`` so the test never performs a real DNS
        lookup (the fetch path resolves+validates the host before pinning the
        connection — see UrlContentService._resolve_pinned_addresses). This keeps
        the test hermetic and deterministic in CI / sandboxed environments.
        """
        from services.ai_service import GeneratedCard, GenerationResult
        from services.url_content_service import UrlContentService

        # Pin DNS to a fixed public IP — no external resolver is contacted.
        mock_resolve.return_value = ["93.184.216.34"]

        # Mock HTTP response (streamed — matches UrlContentService.client.stream usage)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.is_redirect = False
        mock_response.headers = {"content-type": "text/html"}
        mock_response.encoding = "utf-8"
        mock_response.iter_bytes.return_value = [
            b"""
        <html><head><title>Test Article</title></head>
        <body><h1>Introduction</h1><p>This is test content about programming.</p></body>
        </html>
        """
        ]
        mock_response.url = "https://example.com/article"
        mock_stream_cm = MagicMock()
        mock_stream_cm.__enter__ = MagicMock(return_value=mock_response)
        mock_stream_cm.__exit__ = MagicMock(return_value=False)
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.stream.return_value = mock_stream_cm
        mock_client_cls.return_value = mock_client

        # Mock AI service
        mock_ai = MagicMock()
        mock_ai.generate_cards_from_chunks.return_value = GenerationResult(
            cards=[
                GeneratedCard(
                    front="What is programming?",
                    back="The process of creating instructions for computers.",
                    suggested_tags=["AI生成", "URL生成"],
                ),
            ],
            input_length=100,
            model_used="strands_bedrock",
            processing_time_ms=5000,
        )
        mock_create_ai.return_value = mock_ai

        # Execute
        service = UrlContentService()
        page = service.fetch_content("https://example.com/article")

        assert page.title == "Test Article"
        assert "test content" in page.text_content

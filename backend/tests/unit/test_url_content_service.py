"""Unit tests for URL content service (T010)."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from services.url_content_service import UrlContentService, PageContent, ContentFetchError


class TestUrlContentService:
    """Tests for UrlContentService."""

    def setup_method(self) -> None:
        self.service = UrlContentService()

    def test_page_content_dataclass(self) -> None:
        """PageContent has expected fields."""
        pc = PageContent(
            url="https://example.com",
            title="Example",
            text_content="Hello world",
            content_type="text/html",
            fetch_method="http",
            fetched_at="2026-03-05T10:00:00Z",
        )
        assert pc.url == "https://example.com"
        assert pc.title == "Example"
        assert pc.fetch_method == "http"

    @patch("services.url_content_service.httpx.Client")
    def test_fetch_http_success(self, mock_client_cls: MagicMock) -> None:
        """Successful HTTP fetch returns PageContent with text extracted."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html; charset=utf-8"}
        mock_response.text = """
        <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Main Title</h1>
            <p>This is meaningful content about testing.</p>
        </body>
        </html>
        """
        mock_response.url = "https://example.com/article"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        result = self.service.fetch_content("https://example.com/article")

        assert isinstance(result, PageContent)
        assert result.fetch_method == "http"
        assert "Test Page" in result.title
        assert "meaningful content" in result.text_content

    @patch("services.url_content_service.httpx.Client")
    def test_fetch_http_non_html_raises(self, mock_client_cls: MagicMock) -> None:
        """Non-HTML content type raises ContentFetchError."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/pdf"}
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        with pytest.raises(ContentFetchError, match="[Ss]upported|HTML"):
            self.service.fetch_content("https://example.com/doc.pdf")

    @patch("services.url_content_service.httpx.Client")
    def test_fetch_http_404_raises(self, mock_client_cls: MagicMock) -> None:
        """HTTP 404 raises ContentFetchError."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "404", request=MagicMock(), response=mock_response
        )
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        with pytest.raises(ContentFetchError):
            self.service.fetch_content("https://example.com/not-found")

    @patch("services.url_content_service.httpx.Client")
    def test_fetch_http_timeout_raises(self, mock_client_cls: MagicMock) -> None:
        """HTTP timeout raises ContentFetchError."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.TimeoutException("timeout")
        mock_client_cls.return_value = mock_client

        with pytest.raises(ContentFetchError, match="[Tt]imeout"):
            self.service.fetch_content("https://slow-site.example.com")

    def test_extract_text_strips_scripts_and_styles(self) -> None:
        """HTML text extraction removes script and style tags."""
        html = """
        <html>
        <head><title>Page</title><style>body{color:red}</style></head>
        <body>
            <script>alert('xss')</script>
            <p>Visible content here</p>
            <style>.hidden{display:none}</style>
        </body>
        </html>
        """
        title, text = self.service._extract_text_from_html(html)
        assert "alert" not in text
        assert "color:red" not in text
        assert "Visible content" in text

    def test_extract_text_gets_title(self) -> None:
        """Title is extracted from <title> tag."""
        html = "<html><head><title>My Page Title</title></head><body><p>Content</p></body></html>"
        title, text = self.service._extract_text_from_html(html)
        assert title == "My Page Title"

    def test_extract_text_empty_title_fallback(self) -> None:
        """Missing title falls back to empty string."""
        html = "<html><head></head><body><p>Content</p></body></html>"
        title, text = self.service._extract_text_from_html(html)
        assert title == ""

    def test_validates_url_before_fetch(self) -> None:
        """Invalid URL is rejected before making any HTTP request."""
        with pytest.raises(ContentFetchError):
            self.service.fetch_content("http://example.com")

    def test_validates_ssrf_before_fetch(self) -> None:
        """Private IP URLs are rejected."""
        with pytest.raises(ContentFetchError):
            self.service.fetch_content("https://192.168.1.1/admin")

"""Unit tests for AgentCore Browser service (T022)."""

from unittest.mock import MagicMock, patch

import pytest

from services.browser_service import BrowserService, BrowserFetchError
from services.url_content_service import PageContent


class TestBrowserService:
    """Tests for BrowserService."""

    def test_browser_service_init(self) -> None:
        """BrowserService initializes with default region."""
        with patch("services.browser_service.boto3") as mock_boto3:
            service = BrowserService()
            assert service.region is not None

    @patch("services.browser_service.boto3")
    def test_fetch_content_success(self, mock_boto3: MagicMock) -> None:
        """Successful browser fetch returns PageContent with browser method."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        # Mock create session
        mock_client.create_browser_session.return_value = {
            "sessionId": "test-session-123",
        }

        # Mock navigate - returns rendered HTML
        rendered_html = """
        <html>
        <head><title>Rendered SPA Page</title></head>
        <body>
            <div id="root">
                <h1>Dynamic Content</h1>
                <p>This content was rendered by JavaScript and contains important study material.</p>
            </div>
        </body>
        </html>
        """
        mock_client.get_browser_content.return_value = {
            "content": rendered_html,
        }

        service = BrowserService()
        result = service.fetch_content("https://spa-example.com")

        assert isinstance(result, PageContent)
        assert result.fetch_method == "browser"
        assert result.title == "Rendered SPA Page"
        assert "Dynamic Content" in result.text_content

    @patch("services.browser_service.boto3")
    def test_fetch_content_session_error(self, mock_boto3: MagicMock) -> None:
        """Browser session creation failure raises BrowserFetchError."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.create_browser_session.side_effect = Exception("Session failed")

        service = BrowserService()

        with pytest.raises(BrowserFetchError, match="Browser session"):
            service.fetch_content("https://example.com")

    @patch("services.browser_service.boto3")
    def test_fetch_content_empty_result(self, mock_boto3: MagicMock) -> None:
        """Empty browser render result raises BrowserFetchError."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.create_browser_session.return_value = {
            "sessionId": "test-session-123",
        }
        mock_client.get_browser_content.return_value = {
            "content": "<html><body></body></html>",
        }

        service = BrowserService()

        with pytest.raises(BrowserFetchError, match="meaningful"):
            service.fetch_content("https://empty-spa.example.com")

    @patch("services.browser_service.boto3")
    def test_fetch_content_closes_session(self, mock_boto3: MagicMock) -> None:
        """Browser session is closed after fetch, even on error."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.create_browser_session.return_value = {
            "sessionId": "test-session-123",
        }
        mock_client.get_browser_content.side_effect = Exception("Render failed")

        service = BrowserService()

        with pytest.raises(BrowserFetchError):
            service.fetch_content("https://error.example.com")

        # Session should be closed
        mock_client.close_browser_session.assert_called_once_with(
            sessionId="test-session-123"
        )

    @patch("services.browser_service.boto3")
    def test_fetch_content_timeout(self, mock_boto3: MagicMock) -> None:
        """Browser timeout raises BrowserFetchError."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        mock_client.create_browser_session.return_value = {
            "sessionId": "test-session-123",
        }
        mock_client.get_browser_content.side_effect = TimeoutError("Render timeout")

        service = BrowserService()

        with pytest.raises(BrowserFetchError, match="[Tt]imeout"):
            service.fetch_content("https://slow.example.com")

"""Integration tests for authenticated page access via browser profiles (T040)."""

from unittest.mock import MagicMock, patch

import pytest

from services.browser_service import BrowserService, BrowserFetchError
from services.url_content_service import UrlContentService, PageContent, ContentFetchError


class TestAuthenticatedUrlGenerate:
    """Tests for URL generation with browser profile authentication."""

    @patch("services.browser_service.boto3")
    def test_browser_service_with_profile_id(self, mock_boto3: MagicMock) -> None:
        """BrowserService passes profile_id to session creation."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_client.create_browser_session.return_value = {
            "sessionId": "test-session",
        }
        mock_client.get_browser_content.return_value = {
            "content": """
            <html><head><title>Auth Page</title></head>
            <body><p>This is authenticated content that requires login to view and has enough text.</p></body>
            </html>
            """,
        }

        service = BrowserService()
        result = service.fetch_content(
            "https://private.example.com/dashboard",
            profile_id="profile-123",
        )

        assert result.fetch_method == "browser"
        mock_client.create_browser_session.assert_called_once_with(
            profileId="profile-123",
        )

    @patch("services.browser_service.boto3")
    def test_browser_service_without_profile_id(self, mock_boto3: MagicMock) -> None:
        """BrowserService creates session without profile when not specified."""
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        mock_client.create_browser_session.return_value = {
            "sessionId": "test-session",
        }
        mock_client.get_browser_content.return_value = {
            "content": """
            <html><head><title>Public Page</title></head>
            <body><p>This is public content that does not require login to view and has enough text.</p></body>
            </html>
            """,
        }

        service = BrowserService()
        result = service.fetch_content("https://public.example.com")

        mock_client.create_browser_session.assert_called_once_with()

    @patch("services.url_content_service.httpx.Client")
    def test_url_content_service_passes_profile_to_browser(self, mock_client_cls: MagicMock) -> None:
        """UrlContentService passes profile_id to browser service on SPA fallback."""
        # Setup HTTP response as SPA
        spa_html = """
        <html><head><title>SPA</title></head>
        <body>
            <noscript>You need to enable JavaScript to run this app.</noscript>
            <div id="root"></div>
        </body>
        </html>
        """
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "text/html"}
        mock_response.text = spa_html
        mock_response.url = "https://spa.example.com"
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_cls.return_value = mock_client

        # Mock browser service
        mock_browser = MagicMock()
        mock_browser.fetch_content.return_value = PageContent(
            url="https://spa.example.com",
            title="Rendered",
            text_content="Authenticated rendered content with enough text for processing.",
            content_type="text/html",
            fetch_method="browser",
            fetched_at="2026-03-06T10:00:00Z",
        )

        service = UrlContentService(browser_service=mock_browser)
        result = service.fetch_content(
            "https://spa.example.com",
            profile_id="profile-456",
        )

        mock_browser.fetch_content.assert_called_once_with(
            "https://spa.example.com",
            profile_id="profile-456",
        )

    @patch("services.url_content_service.httpx.Client")
    def test_profile_id_always_uses_browser(self, mock_client_cls: MagicMock) -> None:
        """When profile_id is specified, browser is always used (user wants authenticated access)."""
        mock_browser = MagicMock()
        mock_browser.fetch_content.return_value = PageContent(
            url="https://example.com",
            title="Authenticated Page",
            text_content="Content fetched via browser with authentication profile.",
            content_type="text/html",
            fetch_method="browser",
            fetched_at="2026-03-06T10:00:00Z",
        )

        service = UrlContentService(browser_service=mock_browser)
        result = service.fetch_content(
            "https://example.com",
            profile_id="profile-789",
        )

        # Browser should be called directly when profile_id is provided
        assert result.fetch_method == "browser"
        mock_browser.fetch_content.assert_called_once_with(
            "https://example.com",
            profile_id="profile-789",
        )
        # HTTP client should NOT be used
        mock_client_cls.assert_not_called()

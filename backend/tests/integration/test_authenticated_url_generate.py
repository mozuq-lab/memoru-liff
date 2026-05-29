"""Integration tests for the (currently disabled) authenticated-page fetch path.

profile_id-based authenticated URL fetching depends on the AgentCore Browser
integration which is intentionally disabled. The HTTP path of UrlContentService
must continue to work, and any browser-bound request should surface as a
ContentFetchError so callers can convert it to a graceful HTTP response.
"""

from unittest.mock import MagicMock, patch

import pytest

from services.browser_service import BrowserService, BrowserFetchError
from services.url_content_service import (
    ContentFetchError,
    PageContent,
    UrlContentService,
)


class TestBrowserDisabled:
    """The placeholder BrowserService refuses every fetch."""

    def test_browser_service_with_profile_id_raises(self) -> None:
        with pytest.raises(BrowserFetchError, match="not implemented"):
            BrowserService().fetch_content(
                "https://private.example.com/dashboard",
                profile_id="profile-123",
            )

    def test_browser_service_without_profile_id_raises(self) -> None:
        with pytest.raises(BrowserFetchError, match="not implemented"):
            BrowserService().fetch_content("https://public.example.com")


class TestUrlContentServiceWithRealBrowser:
    """When a real (disabled) BrowserService is wired in, browser-bound paths
    surface as ContentFetchError for the handler to translate."""

    def test_profile_id_with_real_browser_surfaces_content_fetch_error(self) -> None:
        # Real BrowserService (always raises) wired into UrlContentService.
        service = UrlContentService(browser_service=BrowserService())

        with pytest.raises(ContentFetchError):
            service.fetch_content(
                "https://example.com",
                profile_id="profile-789",
            )


class TestUrlContentServiceWithMockedBrowser:
    """The plumbing between UrlContentService and a (hypothetical, mocked)
    BrowserService remains correct, so re-enabling the feature later is a
    drop-in replacement."""

    def test_profile_id_routes_directly_to_browser(self) -> None:
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

        assert result.fetch_method == "browser"
        mock_browser.fetch_content.assert_called_once_with(
            "https://example.com",
            profile_id="profile-789",
        )

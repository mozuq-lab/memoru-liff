"""Unit tests for the (currently disabled) AgentCore Browser service.

The previous implementation referenced non-existent boto3 service/method names
and could never have run in production. The current placeholder always raises
BrowserFetchError. These tests pin that contract so future re-enablement is
done deliberately.
"""

import pytest

from services.browser_service import BrowserService, BrowserFetchError


class TestBrowserServiceDisabled:
    """The placeholder BrowserService must always refuse to fetch."""

    def test_fetch_content_always_raises(self) -> None:
        service = BrowserService()
        with pytest.raises(BrowserFetchError, match="not implemented"):
            service.fetch_content("https://example.com")

    def test_fetch_content_with_profile_id_also_raises(self) -> None:
        service = BrowserService()
        with pytest.raises(BrowserFetchError, match="not implemented"):
            service.fetch_content("https://example.com", profile_id="bp-x")

    def test_init_accepts_region_for_compat(self) -> None:
        # region kwarg is kept only for backward compatibility with callers.
        service = BrowserService(region="ap-northeast-1")
        assert isinstance(service, BrowserService)

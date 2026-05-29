"""AgentCore Browser service — currently disabled.

Browser-based content extraction (SPA fallback / authenticated pages) is
intentionally **not implemented**. The previous implementation referenced a
non-existent boto3 service name (`bedrock-agentcore-browser`) and non-existent
methods (`create_browser_session` / `get_browser_content` /
`close_browser_session`); none of it would ever have run in production.

This module keeps the class and exception types so that callers
(`UrlContentService`, `ai_handler`) compile, but every fetch attempt now
raises `BrowserFetchError("not implemented")` immediately. The handler turns
profile_id requests into 501 Not Implemented; the SPA fallback degrades to a
422 with a clear message.

When the feature is re-introduced, replace the body of `fetch_content` with a
real `bedrock-agentcore` client (`start_browser_session` / `invoke_browser`
via the live-view stream / CDP) and restore the IAM policy for it in
`backend/template.yaml`.
"""

from __future__ import annotations


class BrowserFetchError(Exception):
    """Raised when browser-based content fetch fails (or, currently, is unavailable)."""

    pass


class BrowserService:
    """Disabled placeholder for the AgentCore Browser-based content fetcher."""

    # Kept for caller compatibility; intentionally accepts no args of its own.
    def __init__(self, region: str | None = None) -> None:  # noqa: ARG002 — region kept for ABI compat
        pass

    def fetch_content(self, url: str, profile_id: str | None = None):  # noqa: ARG002
        """Always raises — this fetch path is not implemented yet."""
        raise BrowserFetchError(
            "Browser-based content extraction is not implemented yet. "
            "SPA / authenticated-page support is disabled."
        )

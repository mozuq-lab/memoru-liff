"""AgentCore Browser service for SPA content extraction."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Tuple

import boto3
from bs4 import BeautifulSoup

from services.url_content_service import PageContent

# Minimum text length to consider page has meaningful content
_MIN_TEXT_LENGTH = 50


class BrowserFetchError(Exception):
    """Raised when browser-based content fetch fails."""

    pass


class BrowserService:
    """Service for fetching SPA content via AgentCore Browser."""

    def __init__(self, region: str | None = None) -> None:
        self.region = region or os.getenv(
            "AGENTCORE_BROWSER_REGION", "ap-northeast-1"
        )
        self.client = boto3.client(
            "bedrock-agentcore-browser",
            region_name=self.region,
        )

    def fetch_content(self, url: str) -> PageContent:
        """Fetch content from URL using AgentCore Browser.

        Creates a browser session, navigates to the URL, waits for
        JavaScript to render, then extracts the DOM content.

        Args:
            url: The URL to fetch.

        Returns:
            PageContent with extracted text and metadata.

        Raises:
            BrowserFetchError: If content cannot be fetched.
        """
        session_id = None
        try:
            # Create browser session
            session_response = self.client.create_browser_session()
            session_id = session_response["sessionId"]

            # Navigate and get rendered content
            content_response = self.client.get_browser_content(
                sessionId=session_id,
                url=url,
            )

            html = content_response.get("content", "")
            title, text_content = self._extract_text_from_html(html)

            if len(text_content.strip()) < _MIN_TEXT_LENGTH:
                raise BrowserFetchError(
                    "Could not extract meaningful text content from the rendered page."
                )

            return PageContent(
                url=url,
                title=title,
                text_content=text_content,
                content_type="text/html",
                fetch_method="browser",
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )

        except BrowserFetchError:
            raise
        except TimeoutError as e:
            raise BrowserFetchError(f"Browser render timeout: {e}") from e
        except Exception as e:
            raise BrowserFetchError(
                f"Browser session failed: {e}"
            ) from e
        finally:
            if session_id:
                try:
                    self.client.close_browser_session(sessionId=session_id)
                except Exception:
                    pass

    def _extract_text_from_html(self, html: str) -> Tuple[str, str]:
        """Extract title and text content from rendered HTML."""
        soup = BeautifulSoup(html, "html.parser")

        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        body = soup.find("body")
        target = body if body else soup

        text = target.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text_content = "\n\n".join(lines)

        return title, text_content

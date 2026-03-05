"""URL content fetching service for card generation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Tuple

import httpx
from bs4 import BeautifulSoup

from utils.url_validator import UrlValidationError, validate_url

# Timeout for HTTP requests (seconds)
_HTTP_TIMEOUT = 30

# Minimum text length to consider page has meaningful content
_MIN_TEXT_LENGTH = 50

# User-Agent for HTTP requests
_USER_AGENT = "MemoruLIFF/1.0 (Card Generator)"


class ContentFetchError(Exception):
    """Raised when content cannot be fetched or extracted from a URL."""

    pass


@dataclass
class PageContent:
    """Extracted content from a web page."""

    url: str
    title: str
    text_content: str
    content_type: str
    fetch_method: str  # "http" or "browser"
    fetched_at: str  # ISO 8601


class UrlContentService:
    """Service for fetching and extracting text content from URLs."""

    def fetch_content(self, url: str) -> PageContent:
        """Fetch and extract text content from a URL.

        Args:
            url: The URL to fetch content from. Must be https.

        Returns:
            PageContent with extracted text and metadata.

        Raises:
            ContentFetchError: If content cannot be fetched or extracted.
        """
        # Validate URL (SSRF prevention)
        try:
            url = validate_url(url)
        except UrlValidationError as e:
            raise ContentFetchError(str(e)) from e

        return self._fetch_via_http(url)

    def _fetch_via_http(self, url: str) -> PageContent:
        """Fetch content using HTTP GET."""
        try:
            with httpx.Client(
                timeout=_HTTP_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                response = client.get(url)

                if response.status_code >= 400:
                    response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type.lower():
                    raise ContentFetchError(
                        f"Only HTML pages are supported. Got content-type: {content_type}"
                    )

                html = response.text
                final_url = str(response.url)

        except httpx.TimeoutException as e:
            raise ContentFetchError(f"Request timeout: {e}") from e
        except ContentFetchError:
            raise
        except Exception as e:
            raise ContentFetchError(f"Failed to fetch URL: {e}") from e

        title, text_content = self._extract_text_from_html(html)

        if len(text_content.strip()) < _MIN_TEXT_LENGTH:
            raise ContentFetchError(
                "Could not extract meaningful text content from the page. "
                "The page may be image-heavy or require JavaScript rendering."
            )

        return PageContent(
            url=final_url,
            title=title,
            text_content=text_content,
            content_type="text/html",
            fetch_method="http",
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def _extract_text_from_html(self, html: str) -> Tuple[str, str]:
        """Extract title and text content from HTML.

        Args:
            html: Raw HTML string.

        Returns:
            Tuple of (title, text_content).
        """
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Remove unwanted elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
            tag.decompose()

        # Extract text from body, or the whole document if no body
        body = soup.find("body")
        target = body if body else soup

        # Get text with newlines between block elements
        text = target.get_text(separator="\n", strip=True)

        # Clean up excessive newlines
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text_content = "\n\n".join(lines)

        return title, text_content

"""URL content fetching service for card generation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Tuple

import httpx
from bs4 import BeautifulSoup

from utils.url_validator import UrlValidationError, validate_url

if TYPE_CHECKING:
    from services.browser_service import BrowserService

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
    """Service for fetching and extracting text content from URLs.

    Supports 2-stage fetching: HTTP first, then AgentCore Browser fallback
    when SPA content is detected.
    """

    def __init__(self, browser_service: Optional["BrowserService"] = None) -> None:
        self._browser_service = browser_service

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

        # Stage 1: HTTP fetch
        page = self._fetch_via_http(url, allow_spa_fallback=True)
        return page

    def _fetch_via_http(self, url: str, allow_spa_fallback: bool = False) -> PageContent:
        """Fetch content using HTTP GET with optional SPA fallback."""
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

        # Stage 2: SPA detection → browser fallback
        if allow_spa_fallback and self._detect_spa(html):
            if self._browser_service:
                from services.browser_service import BrowserFetchError

                try:
                    return self._browser_service.fetch_content(url)
                except BrowserFetchError as e:
                    raise ContentFetchError(
                        f"Browser rendering failed: {e}"
                    ) from e
            else:
                raise ContentFetchError(
                    "This page requires JavaScript rendering but browser "
                    "service is not available. The page may be a Single Page "
                    "Application (SPA)."
                )

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

    def _detect_spa(self, html: str) -> bool:
        """Detect if page is a Single Page Application requiring JS rendering.

        Checks for common SPA indicators:
        1. <noscript> tag with "enable JavaScript" message
        2. Empty #root, #app, or #__next container
        3. bundle.js or chunk.js script patterns
        4. Very little text content relative to script tags

        Args:
            html: Raw HTML string.

        Returns:
            True if page appears to be an SPA.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Check 1: noscript tag with JS enable message
        noscript_tags = soup.find_all("noscript")
        for tag in noscript_tags:
            text = tag.get_text(strip=True).lower()
            if "javascript" in text and ("enable" in text or "run" in text or "require" in text):
                return True

        # Check 2: Empty SPA root containers
        for container_id in ("root", "app", "__next"):
            container = soup.find(id=container_id)
            if container:
                # Get direct text content (not from nested scripts)
                inner_text = container.get_text(strip=True)
                if len(inner_text) < 20:
                    return True

        # Check 3: bundle.js / chunk.js patterns
        script_tags = soup.find_all("script", src=True)
        spa_patterns = re.compile(
            r"(bundle|chunk|main\.[a-f0-9]+)\.(js|mjs)", re.IGNORECASE
        )
        spa_script_count = sum(
            1 for tag in script_tags
            if spa_patterns.search(tag.get("src", ""))
        )
        if spa_script_count >= 2:
            return True

        # Check 4: Very little body text + scripts present
        body = soup.find("body")
        if body:
            # Remove scripts before measuring text
            body_copy = BeautifulSoup(str(body), "html.parser")
            for tag in body_copy(["script", "style", "noscript"]):
                tag.decompose()
            body_text = body_copy.get_text(strip=True)

            if len(body_text) < 50 and len(script_tags) >= 1:
                return True

        return False

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

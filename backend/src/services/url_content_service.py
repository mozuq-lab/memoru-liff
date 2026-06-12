"""URL content fetching service for card generation."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import httpx
from aws_lambda_powertools import Logger
from bs4 import BeautifulSoup

from utils.url_validator import (
    UrlValidationError,
    resolve_and_validate_host,
    validate_url,
)

logger = Logger(child=True)

if TYPE_CHECKING:
    from services.browser_service import BrowserService

# Timeout for HTTP requests (seconds)
_HTTP_TIMEOUT = 30

# Maximum number of redirects to follow manually
_MAX_REDIRECTS = 10

# Maximum response body size to download in bytes — prevents memory exhaustion (N-7)
_MAX_CONTENT_BYTES = 10 * 1024 * 1024  # 10 MB

# Minimum text length to consider page has meaningful content
_MIN_TEXT_LENGTH = 50

# User-Agent for HTTP requests
_USER_AGENT = "MemoruLIFF/1.0 (Card Generator)"


class ContentFetchError(Exception):
    """Raised when content cannot be fetched or extracted from a URL."""

    pass


@dataclass
class _HopResult:
    """Outcome of fetching a single redirect hop.

    Exactly one of ``redirect_url`` / ``html`` is set: ``redirect_url`` when the
    hop returned a (validated) redirect, ``html`` when it returned the final
    page body.
    """

    redirect_url: str | None = None
    html: str | None = None


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

    def fetch_content(
        self,
        url: str,
        profile_id: str | None = None,
    ) -> PageContent:
        """Fetch and extract text content from a URL.

        Args:
            url: The URL to fetch content from. Must be https.
            profile_id: Optional browser profile ID for authenticated access.

        Returns:
            PageContent with extracted text and metadata.

        Raises:
            ContentFetchError: If content cannot be fetched or extracted.
        """
        # Validate URL (SSRF prevention)
        try:
            url = validate_url(url)
        except UrlValidationError as e:
            logger.warning("URL validation failed", extra={"url": url, "error": str(e)})
            raise ContentFetchError(str(e)) from e

        logger.info("Fetching URL content", extra={"url": url, "has_profile": bool(profile_id)})

        # If profile_id specified, go directly to browser fetch
        if profile_id and self._browser_service:
            from services.browser_service import BrowserFetchError

            try:
                return self._browser_service.fetch_content(url, profile_id=profile_id)
            except BrowserFetchError as e:
                raise ContentFetchError(
                    f"Browser rendering with profile failed: {e}"
                ) from e

        # Stage 1: HTTP fetch
        page = self._fetch_via_http(url, allow_spa_fallback=True, profile_id=profile_id)
        return page

    def _resolve_pinned_addresses(self, url: str) -> tuple[str, list[str]]:
        """Resolve+validate a URL's host, returning (original_host, addresses).

        SSRF / DNS-rebinding defence (joint-review #9): instead of letting httpx
        resolve the hostname independently at connect time (which would create a
        TOCTOU window after ``validate_url``), we resolve the host *once* here
        and verify *every* resolved address is public. The caller then pins the
        connection to one of these already-validated IPs, eliminating the second,
        unchecked resolution.

        Returns the (non-empty) list of validated public IPs so the caller can
        try them in order and fall back on connection-level failures.

        Raises:
            UrlValidationError: If the host resolves to a private/internal IP.
            ContentFetchError: If the host is missing or cannot be resolved.
        """
        parsed = urlparse(url)
        original_host = parsed.hostname
        if not original_host:
            raise ContentFetchError("URL must have a valid hostname")

        # Resolve once and verify *all* addresses are public (rebinding-safe).
        addresses = resolve_and_validate_host(original_host)
        if not addresses:
            # NXDOMAIN / no records — surface as a connection error, matching
            # the previous behaviour where httpx would fail to resolve.
            raise ContentFetchError(f"Failed to resolve host: {original_host}")

        return original_host, addresses

    def _build_pinned_request(
        self,
        client: httpx.Client,
        url: str,
        pinned_ip: str | None = None,
    ) -> httpx.Request:
        """Build a GET request pinned to a freshly-validated resolved IP.

        SSRF / DNS-rebinding defence (joint-review #9): the request is dialled
        directly at an already-validated public IP so httpx never performs a
        second, unchecked DNS resolution.

        To keep TLS and virtual-host routing correct while connecting to a raw
        IP:
          * The request URL's host is replaced with the validated IP (port
            preserved). httpx therefore opens the TCP connection to that exact
            IP — no re-resolution happens.
          * The ``Host`` header is set to the original hostname so origin
            virtual-host / CDN routing is unchanged (Host + SNI together make
            the request indistinguishable from a normal one).
          * ``extensions={"sni_hostname": original_host}`` makes httpcore pass
            the original hostname as ``server_hostname`` to
            ``ssl_context.wrap_socket``. That drives both the TLS SNI extension
            and certificate hostname verification, so the cert is still validated
            against the real hostname (not the IP).

        Args:
            client: The httpx client used to build the request.
            url: The original (hostname-based) URL.
            pinned_ip: A specific already-validated IP to pin to. When ``None``
                the host is resolved+validated here and the first address used
                (kept for backwards compatibility with existing callers/tests).

        Raises:
            UrlValidationError: If the host resolves to a private/internal IP.
            ContentFetchError: If the host cannot be resolved (no records).
        """
        parsed = urlparse(url)

        original_host: str
        if pinned_ip is None:
            original_host, addresses = self._resolve_pinned_addresses(url)
            pinned_ip = addresses[0]
        else:
            host = parsed.hostname
            if not host:
                raise ContentFetchError("URL must have a valid hostname")
            original_host = host

        # Embed IPv6 literals in bracket form; leave IPv4 / hostnames bare.
        try:
            host_part = (
                f"[{pinned_ip}]"
                if isinstance(ipaddress.ip_address(pinned_ip), ipaddress.IPv6Address)
                else pinned_ip
            )
        except ValueError:  # pragma: no cover - resolve_host returns IP literals
            host_part = pinned_ip

        # Preserve the original port (urlparse normalises it to None when absent).
        netloc = f"{host_part}:{parsed.port}" if parsed.port is not None else host_part
        pinned_url = urlunparse(parsed._replace(netloc=netloc))

        # Host header carries the original hostname (incl. explicit port if any)
        # so virtual-host routing is unaffected by the IP pinning.
        host_header = original_host
        if parsed.port is not None:
            host_header = f"{original_host}:{parsed.port}"

        return client.build_request(
            "GET",
            pinned_url,
            headers={"Host": host_header},
            extensions={"sni_hostname": original_host},
        )

    def _fetch_hop(self, current_url: str, addresses: list[str]) -> _HopResult:
        """Fetch a single redirect hop, trying each validated IP in order.

        Uses a **fresh** ``httpx.Client`` so this hop never reuses a pooled TLS
        connection established for a previous (different-hostname) hop — that
        would skip ``sni_hostname`` certificate verification on shared-CDN IPs.

        Connection-level failures (ConnectError / ConnectTimeout) fall back to
        the next IP; the last such error is re-raised if every IP fails. Failures
        after a successful connection are not retried.
        """
        last_connect_error: Exception | None = None

        for pinned_ip in addresses:
            with httpx.Client(
                timeout=_HTTP_TIMEOUT,
                follow_redirects=False,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                request = self._build_pinned_request(
                    client, current_url, pinned_ip=pinned_ip
                )
                stream_cm = client.stream(
                    "GET",
                    request.url,
                    headers=request.headers,
                    extensions=request.extensions,
                )
                try:
                    response = stream_cm.__enter__()
                except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                    # Connection-level failure for this IP — try the next one.
                    last_connect_error = e
                    continue
                # Connected successfully: process the response within the stream
                # context so the body is always closed. Failures from here on are
                # NOT retried against other IPs.
                try:
                    return self._process_hop_response(current_url, response)
                finally:
                    stream_cm.__exit__(None, None, None)

        # Every validated IP failed at the connection level.
        if last_connect_error is not None:
            raise ContentFetchError(
                f"Failed to connect to {urlparse(current_url).hostname}: {last_connect_error}"
            ) from last_connect_error
        # addresses is guaranteed non-empty by _resolve_pinned_addresses, so this
        # branch is unreachable; kept defensively.
        raise ContentFetchError(  # pragma: no cover
            f"Failed to connect to {urlparse(current_url).hostname}"
        )

    def _process_hop_response(
        self, current_url: str, response: httpx.Response
    ) -> _HopResult:
        """Process a connected hop's streamed response into a _HopResult."""
        if response.is_redirect:
            location = response.headers.get("location")
            if not location:
                raise ContentFetchError("Redirect without Location header")
            # Resolve the Location against the *original* hostname URL
            # (current_url), NOT the IP-pinned request URL, so relative redirects
            # keep the real host rather than the raw pinned IP.
            redirect_url = str(httpx.URL(current_url).join(location))
            # Validate redirect target against SSRF. The next loop iteration
            # re-resolves + re-pins this hop, so each hop gets the same
            # resolve → validate → pin treatment.
            try:
                redirect_url = validate_url(redirect_url)
            except UrlValidationError as e:
                raise ContentFetchError(
                    f"Redirect target blocked by SSRF protection: {e}"
                ) from e
            return _HopResult(redirect_url=redirect_url)

        # Non-redirect response
        if response.status_code >= 400:
            response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        ct_lower = content_type.lower()

        # Reject PDF files
        if "application/pdf" in ct_lower:
            raise ContentFetchError(
                "PDF files are not supported. Please paste the text content directly."
            )

        # Reject image responses
        if ct_lower.startswith("image/"):
            raise ContentFetchError(
                "Image URLs are not supported. Please provide a web page URL."
            )

        if "text/html" not in ct_lower:
            raise ContentFetchError(
                f"Only HTML pages are supported. Got content-type: {content_type}"
            )

        # Reject oversized responses early via declared Content-Length (N-7)
        declared = response.headers.get("content-length")
        if declared is not None:
            try:
                if int(declared) > _MAX_CONTENT_BYTES:
                    raise ContentFetchError(
                        "Content too large. The page exceeds the maximum "
                        f"supported size ({_MAX_CONTENT_BYTES // (1024 * 1024)} MB)."
                    )
            except ValueError:
                pass  # Malformed header — rely on the streaming cap below

        # Stream the body with a hard cap to bound memory usage (N-7).
        # Covers chunked / spoofed Content-Length where the header lies.
        buf = bytearray()
        for chunk in response.iter_bytes():
            buf.extend(chunk)
            if len(buf) > _MAX_CONTENT_BYTES:
                raise ContentFetchError(
                    "Content too large. The page exceeds the maximum "
                    f"supported size ({_MAX_CONTENT_BYTES // (1024 * 1024)} MB)."
                )

        html = buf.decode(response.encoding or "utf-8", errors="replace")
        return _HopResult(html=html)

    def _fetch_via_http(
        self,
        url: str,
        allow_spa_fallback: bool = False,
        profile_id: str | None = None,
    ) -> PageContent:
        """Fetch content using HTTP GET with optional SPA fallback.

        Manually follows redirects, and for each hop independently re-resolves,
        re-validates and re-pins the connection to a verified IP (SSRF /
        DNS-rebinding defence).

        Each hop uses a **fresh** ``httpx.Client`` (connection-pool isolation):
        sharing one client across hops lets httpcore reuse a TLS connection keyed
        on the (IP, port) origin, which would bypass per-hop ``sni_hostname``
        certificate verification when two different hostnames resolve to the same
        CDN IP. A new client per hop forces a new TLS handshake — and hence a
        fresh cert check against the new hostname — for every redirect target.
        The ``_MAX_REDIRECTS`` (10) cap bounds the client-creation cost.

        Within a hop, the validated public IPs are tried in order: on a
        *connection-level* failure (ConnectError / ConnectTimeout) the next IP is
        attempted. Failures after a successful connection (HTTP errors, size
        caps) are not retried.
        """
        html: str | None = None
        final_url = url
        try:
            current_url = url
            for _ in range(_MAX_REDIRECTS):
                # Resolve + validate this hop's host once; try each verified IP
                # in order, falling back only on connection-level failures.
                try:
                    _host, addresses = self._resolve_pinned_addresses(current_url)
                except UrlValidationError as e:
                    raise ContentFetchError(
                        f"Blocked by SSRF protection: {e}"
                    ) from e

                result = self._fetch_hop(current_url, addresses)

                if result.redirect_url is not None:
                    current_url = result.redirect_url
                    continue

                html = result.html
                # Report the original-host URL, not the IP-pinned one that was
                # actually dialled, so downstream consumers see the real address.
                final_url = current_url
                break
            else:
                raise ContentFetchError(
                    "Too many redirects. The URL may be invalid or require authentication."
                )

        except httpx.TimeoutException as e:
            raise ContentFetchError(f"Request timeout: {e}") from e
        except ContentFetchError:
            raise
        except Exception as e:
            raise ContentFetchError(f"Failed to fetch URL: {e}") from e

        if html is None:  # pragma: no cover - loop always sets html or raises
            raise ContentFetchError("Failed to fetch URL: no content")

        # Stage 2: SPA detection → browser fallback
        if allow_spa_fallback and self._detect_spa(html):
            logger.info("SPA detected, falling back to browser", extra={"url": url})
            if self._browser_service:
                from services.browser_service import BrowserFetchError

                try:
                    return self._browser_service.fetch_content(url, profile_id=profile_id)
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

        logger.info(
            "Content extracted via HTTP",
            extra={
                "url": final_url,
                "title": title,
                "content_length": len(text_content),
            },
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
        # BeautifulSoup attribute values may be lists (AttributeValueList);
        # only count plain string src attributes.
        script_srcs = (tag.get("src") for tag in script_tags)
        spa_script_count = sum(
            1 for src in script_srcs
            if isinstance(src, str) and spa_patterns.search(src)
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

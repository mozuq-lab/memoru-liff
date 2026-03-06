"""URL validation and SSRF prevention for URL card generation."""

import ipaddress
import os
import re
from urllib.parse import urlparse


class UrlValidationError(Exception):
    """Raised when URL validation fails."""

    pass


# Hostnames that should be blocked
_BLOCKED_HOSTNAMES = frozenset({
    "localhost",
    "localhost.localdomain",
    "0.0.0.0",
})

# Domain allow/block lists from environment variables
# Format: comma-separated domains, e.g. "example.com,docs.example.com"
_ALLOWED_DOMAINS: frozenset[str] | None = None
_BLOCKED_DOMAINS: frozenset[str] = frozenset()


def _load_domain_lists() -> None:
    """Load domain allow/block lists from environment variables."""
    global _ALLOWED_DOMAINS, _BLOCKED_DOMAINS

    allow_env = os.getenv("URL_ALLOWED_DOMAINS", "").strip()
    if allow_env:
        _ALLOWED_DOMAINS = frozenset(
            d.strip().lower() for d in allow_env.split(",") if d.strip()
        )
    else:
        _ALLOWED_DOMAINS = None

    block_env = os.getenv("URL_BLOCKED_DOMAINS", "").strip()
    if block_env:
        _BLOCKED_DOMAINS = frozenset(
            d.strip().lower() for d in block_env.split(",") if d.strip()
        )
    else:
        _BLOCKED_DOMAINS = frozenset()


_load_domain_lists()

# Regex for IPv6 in brackets
_IPV6_BRACKET_RE = re.compile(r"^\[(.+)\]$")


def _is_private_ip(hostname: str) -> bool:
    """Check if a hostname resolves to a private/loopback IP address."""
    # Strip brackets from IPv6
    match = _IPV6_BRACKET_RE.match(hostname)
    if match:
        hostname = match.group(1)

    try:
        addr = ipaddress.ip_address(hostname)
        return addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local
    except ValueError:
        # Not a raw IP address (it's a hostname) — allow it
        return False


def validate_url(url: str) -> str:
    """Validate and sanitize a URL for content fetching.

    Args:
        url: The URL to validate.

    Returns:
        The validated, stripped URL.

    Raises:
        UrlValidationError: If the URL is invalid or points to a blocked resource.
    """
    url = url.strip()

    if not url:
        raise UrlValidationError("URL cannot be empty")

    if len(url) > 2048:
        raise UrlValidationError("URL must not exceed 2048 characters")

    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise UrlValidationError("URL must use https scheme")

    hostname = parsed.hostname
    if not hostname:
        raise UrlValidationError("URL must have a valid hostname")

    # Check blocked hostnames
    if hostname.lower() in _BLOCKED_HOSTNAMES:
        raise UrlValidationError(f"Access to private/internal hosts is blocked: {hostname}")

    # Check for private/loopback IPs
    if _is_private_ip(hostname):
        raise UrlValidationError(f"Access to private/internal IP addresses is blocked: {hostname}")

    # Check domain allow list (if configured, only these domains are allowed)
    hostname_lower = hostname.lower()
    if _ALLOWED_DOMAINS is not None:
        if not any(
            hostname_lower == d or hostname_lower.endswith(f".{d}")
            for d in _ALLOWED_DOMAINS
        ):
            raise UrlValidationError(f"Domain not in allow list: {hostname}")

    # Check domain block list
    if any(
        hostname_lower == d or hostname_lower.endswith(f".{d}")
        for d in _BLOCKED_DOMAINS
    ):
        raise UrlValidationError(f"Domain is blocked: {hostname}")

    return url

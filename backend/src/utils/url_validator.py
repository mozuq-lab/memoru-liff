"""URL validation and SSRF prevention for URL card generation."""

import ipaddress
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

    return url

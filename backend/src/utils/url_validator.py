"""URL validation and SSRF prevention for URL card generation."""

import ipaddress
import os
import re
import socket
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


def is_private_ip_address(addr_str: str) -> bool:
    """Check if an IP address string is private/loopback/reserved/link-local.

    Public helper so that the content-fetch layer can re-use the exact same
    blocklist logic when pinning a connection to an already-resolved IP
    (SSRF / DNS-rebinding defence). Returns False for strings that are not
    valid IP literals.
    """
    try:
        addr = ipaddress.ip_address(addr_str)
        return addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local
    except ValueError:
        return False


# Backwards-compatible private alias (kept for any internal references).
_is_private_ip_address = is_private_ip_address


def resolve_host(hostname: str) -> list[str]:
    """Resolve a hostname to all of its IP addresses.

    If ``hostname`` is already an IP literal (optionally bracketed IPv6) it is
    returned as a single-element list without a DNS lookup.

    Returns an empty list if DNS resolution fails (NXDOMAIN / no records); the
    caller treats this as a connection error, matching the prior behaviour.
    """
    # Strip brackets from IPv6 literals
    match = _IPV6_BRACKET_RE.match(hostname)
    if match:
        hostname = match.group(1)

    # Raw IP literal — no DNS lookup needed.
    try:
        ipaddress.ip_address(hostname)
        return [hostname]
    except ValueError:
        pass

    try:
        addrinfos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return []

    seen: list[str] = []
    for _family, _type, _proto, _canon, sockaddr in addrinfos:
        ip_str = str(sockaddr[0])  # IPv6 sockaddr tuples may type as str | int
        if ip_str not in seen:
            seen.append(ip_str)
    return seen


def resolve_and_validate_host(hostname: str) -> list[str]:
    """Resolve ``hostname`` once and verify *every* resolved IP is public.

    This performs a single DNS lookup and checks all returned addresses against
    the private/loopback/reserved blocklist. Checking *all* results (rather than
    just the first) is what gives DNS-rebinding resistance: a malicious resolver
    cannot hide a private IP behind a public one.

    Args:
        hostname: The host part of the URL (IP literal or DNS name).

    Returns:
        The list of resolved IP address strings (non-empty) when all are public.
        Returns an empty list when DNS resolution yields no records, so the
        caller can surface a connection error.

    Raises:
        UrlValidationError: If any resolved address is private/internal.
    """
    addresses = resolve_host(hostname)
    for ip_str in addresses:
        if is_private_ip_address(ip_str):
            raise UrlValidationError(
                f"Access to private/internal IP addresses is blocked: {hostname}"
            )
    return addresses


def _is_private_ip(hostname: str) -> bool:
    """Check if a hostname resolves to a private/loopback IP address.

    Checks both raw IP literals and DNS-resolved addresses. DNS failure is
    treated as "not private" here; the HTTP client raises a connection error
    if the host truly doesn't exist.
    """
    for ip_str in resolve_host(hostname):
        if is_private_ip_address(ip_str):
            return True
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

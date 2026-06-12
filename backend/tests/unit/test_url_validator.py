"""Unit tests for URL validator (T004)."""

from unittest.mock import patch

import pytest

from utils.url_validator import (
    UrlValidationError,
    is_private_ip_address,
    resolve_and_validate_host,
    resolve_host,
    validate_url,
)


class TestValidateUrl:
    """Tests for validate_url function."""

    def test_valid_https_url(self) -> None:
        """Valid https URL passes validation."""
        result = validate_url("https://example.com/article")
        assert result == "https://example.com/article"

    def test_valid_https_url_with_path_and_query(self) -> None:
        """URL with path, query params, and fragment passes."""
        url = "https://docs.example.com/en/guide?page=1#section"
        assert validate_url(url) == url

    def test_rejects_http_url(self) -> None:
        """HTTP (non-secure) URLs are rejected."""
        with pytest.raises(UrlValidationError, match="https"):
            validate_url("http://example.com")

    def test_rejects_ftp_url(self) -> None:
        """FTP scheme is rejected."""
        with pytest.raises(UrlValidationError, match="https"):
            validate_url("ftp://files.example.com/doc.pdf")

    def test_rejects_javascript_url(self) -> None:
        """javascript: scheme is rejected."""
        with pytest.raises(UrlValidationError, match="https"):
            validate_url("javascript:alert(1)")

    def test_rejects_empty_url(self) -> None:
        """Empty string is rejected."""
        with pytest.raises(UrlValidationError):
            validate_url("")

    def test_rejects_whitespace_url(self) -> None:
        """Whitespace-only string is rejected."""
        with pytest.raises(UrlValidationError):
            validate_url("   ")

    def test_rejects_url_exceeding_max_length(self) -> None:
        """URL exceeding 2048 characters is rejected."""
        long_url = "https://example.com/" + "a" * 2048
        with pytest.raises(UrlValidationError, match="2048"):
            validate_url(long_url)

    def test_rejects_localhost(self) -> None:
        """localhost URLs are rejected (SSRF prevention)."""
        with pytest.raises(UrlValidationError, match="[Pp]rivate|internal|blocked"):
            validate_url("https://localhost/admin")

    def test_rejects_127_0_0_1(self) -> None:
        """Loopback IP is rejected."""
        with pytest.raises(UrlValidationError, match="[Pp]rivate|internal|blocked"):
            validate_url("https://127.0.0.1/admin")

    def test_rejects_private_ip_10(self) -> None:
        """10.x.x.x private IP range is rejected."""
        with pytest.raises(UrlValidationError, match="[Pp]rivate|internal|blocked"):
            validate_url("https://10.0.0.1/internal")

    def test_rejects_private_ip_172_16(self) -> None:
        """172.16.x.x private IP range is rejected."""
        with pytest.raises(UrlValidationError, match="[Pp]rivate|internal|blocked"):
            validate_url("https://172.16.0.1/internal")

    def test_rejects_private_ip_192_168(self) -> None:
        """192.168.x.x private IP range is rejected."""
        with pytest.raises(UrlValidationError, match="[Pp]rivate|internal|blocked"):
            validate_url("https://192.168.1.1/internal")

    def test_rejects_ipv6_loopback(self) -> None:
        """IPv6 loopback [::1] is rejected."""
        with pytest.raises(UrlValidationError, match="[Pp]rivate|internal|blocked"):
            validate_url("https://[::1]/admin")

    def test_strips_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped."""
        result = validate_url("  https://example.com  ")
        assert result == "https://example.com"

    def test_rejects_no_hostname(self) -> None:
        """URL without hostname is rejected."""
        with pytest.raises(UrlValidationError):
            validate_url("https:///path")

    def test_url_at_max_length_passes(self) -> None:
        """URL at exactly 2048 characters passes."""
        base = "https://example.com/"
        padding = "a" * (2048 - len(base))
        url = base + padding
        assert len(url) == 2048
        assert validate_url(url) == url


class TestIsPrivateIpAddress:
    """Tests for the public is_private_ip_address helper."""

    @pytest.mark.parametrize(
        "addr",
        ["127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1", "::1", "169.254.0.1"],
    )
    def test_private_addresses(self, addr: str) -> None:
        assert is_private_ip_address(addr) is True

    @pytest.mark.parametrize("addr", ["93.184.216.34", "8.8.8.8", "2606:2800:220:1:248:1893:25c8:1946"])
    def test_public_addresses(self, addr: str) -> None:
        assert is_private_ip_address(addr) is False

    def test_non_ip_string_is_false(self) -> None:
        assert is_private_ip_address("not-an-ip") is False


class TestResolveHost:
    """Tests for resolve_host (single-resolution helper)."""

    def test_ip_literal_returned_without_dns(self) -> None:
        with patch("utils.url_validator.socket.getaddrinfo") as mock_getaddr:
            assert resolve_host("93.184.216.34") == ["93.184.216.34"]
            mock_getaddr.assert_not_called()

    def test_bracketed_ipv6_literal_unwrapped(self) -> None:
        assert resolve_host("[2606:2800:220:1:248:1893:25c8:1946]") == [
            "2606:2800:220:1:248:1893:25c8:1946"
        ]

    def test_dns_resolution_dedupes(self) -> None:
        fake = [
            (2, 1, 6, "", ("93.184.216.34", 0)),
            (2, 1, 6, "", ("93.184.216.34", 0)),
            (2, 1, 6, "", ("93.184.216.35", 0)),
        ]
        with patch("utils.url_validator.socket.getaddrinfo", return_value=fake):
            assert resolve_host("example.com") == ["93.184.216.34", "93.184.216.35"]

    def test_nxdomain_returns_empty(self) -> None:
        import socket as _socket

        with patch(
            "utils.url_validator.socket.getaddrinfo",
            side_effect=_socket.gaierror("nxdomain"),
        ):
            assert resolve_host("missing.example.com") == []


class TestResolveAndValidateHost:
    """Tests for resolve_and_validate_host (rebinding-resistant validation)."""

    def test_all_public_returns_addresses(self) -> None:
        fake = [(2, 1, 6, "", ("93.184.216.34", 0))]
        with patch("utils.url_validator.socket.getaddrinfo", return_value=fake):
            assert resolve_and_validate_host("example.com") == ["93.184.216.34"]

    def test_any_private_address_rejected(self) -> None:
        # A public + a private address in the same result must be rejected.
        fake = [
            (2, 1, 6, "", ("93.184.216.34", 0)),
            (2, 1, 6, "", ("127.0.0.1", 0)),
        ]
        with patch("utils.url_validator.socket.getaddrinfo", return_value=fake):
            with pytest.raises(UrlValidationError, match="private|internal"):
                resolve_and_validate_host("rebind.example.com")

    def test_nxdomain_returns_empty_list(self) -> None:
        import socket as _socket

        with patch(
            "utils.url_validator.socket.getaddrinfo",
            side_effect=_socket.gaierror("nxdomain"),
        ):
            assert resolve_and_validate_host("missing.example.com") == []

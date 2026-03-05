"""Unit tests for URL validator (T004)."""

import pytest

from utils.url_validator import validate_url, UrlValidationError


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

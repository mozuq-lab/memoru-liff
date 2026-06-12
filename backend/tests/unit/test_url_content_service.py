"""Unit tests for URL content service (T010)."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from services.url_content_service import UrlContentService, PageContent, ContentFetchError


@pytest.fixture(autouse=True)
def _stub_dns_resolution():
    """Pin DNS resolution to a fixed public IP for all content-service tests.

    The fetch path resolves+validates the host once and pins the connection to
    a verified IP (SSRF / DNS-rebinding defence). Tests use non-resolvable
    example hostnames, so without this stub every fetch would fail at
    resolution. Returning a single public IP keeps the existing behavioural
    assertions intact while exercising the pinning code path.
    """
    with patch(
        "services.url_content_service.resolve_and_validate_host",
        return_value=["93.184.216.34"],
    ) as mock_resolve:
        yield mock_resolve


def _setup_stream_client(
    mock_client_cls,
    *,
    text=None,
    status_code=200,
    is_redirect=False,
    headers=None,
    url="https://example.com",
    next_url=None,
    raise_for_status=None,
    iter_bytes_side_effect=None,
):
    """Configure a mocked httpx.Client whose .stream() yields a streamed response.

    Mirrors the production usage `with client.stream("GET", ...) as response:`.
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_redirect = is_redirect
    resp.headers = headers if headers is not None else {"content-type": "text/html; charset=utf-8"}
    resp.encoding = "utf-8"
    resp.url = url
    if iter_bytes_side_effect is not None:
        resp.iter_bytes.side_effect = iter_bytes_side_effect
    else:
        resp.iter_bytes.return_value = [text.encode("utf-8")] if text is not None else []
    if next_url is not None:
        resp.next_request = MagicMock()
        resp.next_request.url = next_url
    else:
        resp.next_request = None
    if raise_for_status is not None:
        resp.raise_for_status.side_effect = raise_for_status

    stream_cm = MagicMock()
    stream_cm.__enter__ = MagicMock(return_value=resp)
    stream_cm.__exit__ = MagicMock(return_value=False)

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.stream.return_value = stream_cm
    mock_client_cls.return_value = mock_client
    return mock_client, resp


class TestUrlContentService:
    """Tests for UrlContentService."""

    def setup_method(self) -> None:
        self.service = UrlContentService()

    def test_page_content_dataclass(self) -> None:
        """PageContent has expected fields."""
        pc = PageContent(
            url="https://example.com",
            title="Example",
            text_content="Hello world",
            content_type="text/html",
            fetch_method="http",
            fetched_at="2026-03-05T10:00:00Z",
        )
        assert pc.url == "https://example.com"
        assert pc.title == "Example"
        assert pc.fetch_method == "http"

    @patch("services.url_content_service.httpx.Client")
    def test_fetch_http_success(self, mock_client_cls: MagicMock) -> None:
        """Successful HTTP fetch returns PageContent with text extracted."""
        html = """
        <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Main Title</h1>
            <p>This is meaningful content about testing.</p>
        </body>
        </html>
        """
        _setup_stream_client(
            mock_client_cls,
            text=html,
            url="https://example.com/article",
        )

        result = self.service.fetch_content("https://example.com/article")

        assert isinstance(result, PageContent)
        assert result.fetch_method == "http"
        assert "Test Page" in result.title
        assert "meaningful content" in result.text_content

    @patch("services.url_content_service.httpx.Client")
    def test_fetch_http_non_html_raises(self, mock_client_cls: MagicMock) -> None:
        """Non-HTML content type raises ContentFetchError."""
        _setup_stream_client(
            mock_client_cls,
            headers={"content-type": "application/pdf"},
        )

        with pytest.raises(ContentFetchError, match="[Ss]upported|HTML"):
            self.service.fetch_content("https://example.com/doc.pdf")

    @patch("services.url_content_service.httpx.Client")
    def test_fetch_http_404_raises(self, mock_client_cls: MagicMock) -> None:
        """HTTP 404 raises ContentFetchError."""
        _setup_stream_client(
            mock_client_cls,
            status_code=404,
            raise_for_status=httpx.HTTPStatusError(
                "404", request=MagicMock(), response=MagicMock()
            ),
        )

        with pytest.raises(ContentFetchError):
            self.service.fetch_content("https://example.com/not-found")

    @patch("services.url_content_service.httpx.Client")
    def test_fetch_http_timeout_raises(self, mock_client_cls: MagicMock) -> None:
        """HTTP timeout raises ContentFetchError."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.stream.side_effect = httpx.TimeoutException("timeout")
        mock_client_cls.return_value = mock_client

        with pytest.raises(ContentFetchError, match="[Tt]imeout"):
            self.service.fetch_content("https://slow-site.example.com")

    @patch("services.url_content_service.httpx.Client")
    def test_fetch_rejects_large_declared_content_length(self, mock_client_cls: MagicMock) -> None:
        """Declared Content-Length over the cap is rejected before reading body (N-7)."""
        _setup_stream_client(
            mock_client_cls,
            text="<html><body>small</body></html>",
            headers={
                "content-type": "text/html; charset=utf-8",
                "content-length": str(20 * 1024 * 1024),  # 20 MB > 10 MB cap
            },
            url="https://huge.example.com",
        )

        with pytest.raises(ContentFetchError, match="too large|exceeds"):
            self.service.fetch_content("https://huge.example.com")

    @patch("services.url_content_service.httpx.Client")
    def test_fetch_rejects_body_exceeding_cap_when_streaming(self, mock_client_cls: MagicMock) -> None:
        """Body exceeding the cap during streaming is rejected even w/o Content-Length (N-7)."""
        chunk = b"x" * (6 * 1024 * 1024)  # two 6 MB chunks exceed the 10 MB cap
        _setup_stream_client(
            mock_client_cls,
            headers={"content-type": "text/html; charset=utf-8"},
            url="https://chunked.example.com",
            iter_bytes_side_effect=lambda: iter([chunk, chunk]),
        )

        with pytest.raises(ContentFetchError, match="too large|exceeds"):
            self.service.fetch_content("https://chunked.example.com")

    def test_extract_text_strips_scripts_and_styles(self) -> None:
        """HTML text extraction removes script and style tags."""
        html = """
        <html>
        <head><title>Page</title><style>body{color:red}</style></head>
        <body>
            <script>alert('xss')</script>
            <p>Visible content here</p>
            <style>.hidden{display:none}</style>
        </body>
        </html>
        """
        title, text = self.service._extract_text_from_html(html)
        assert "alert" not in text
        assert "color:red" not in text
        assert "Visible content" in text

    def test_extract_text_gets_title(self) -> None:
        """Title is extracted from <title> tag."""
        html = "<html><head><title>My Page Title</title></head><body><p>Content</p></body></html>"
        title, text = self.service._extract_text_from_html(html)
        assert title == "My Page Title"

    def test_extract_text_empty_title_fallback(self) -> None:
        """Missing title falls back to empty string."""
        html = "<html><head></head><body><p>Content</p></body></html>"
        title, text = self.service._extract_text_from_html(html)
        assert title == ""

    def test_validates_url_before_fetch(self) -> None:
        """Invalid URL is rejected before making any HTTP request."""
        with pytest.raises(ContentFetchError):
            self.service.fetch_content("http://example.com")

    def test_validates_ssrf_before_fetch(self) -> None:
        """Private IP URLs are rejected."""
        with pytest.raises(ContentFetchError):
            self.service.fetch_content("https://192.168.1.1/admin")


class TestIpPinning:
    """Tests for IP-pinning SSRF / DNS-rebinding defence (joint-review #9)."""

    def setup_method(self) -> None:
        self.service = UrlContentService()

    def test_build_pinned_request_pins_ipv4_and_sets_host_and_sni(self) -> None:
        """Request URL is the resolved IP; Host + sni_hostname keep the real host."""
        with patch(
            "services.url_content_service.resolve_and_validate_host",
            return_value=["93.184.216.34"],
        ):
            with httpx.Client() as client:
                req = self.service._build_pinned_request(
                    client, "https://example.com/article?q=1"
                )

        assert req.url.host == "93.184.216.34"
        assert req.url.path == "/article"
        assert req.url.query == b"q=1"
        # Host header carries the ORIGINAL hostname for vhost/CDN routing.
        assert req.headers["host"] == "example.com"
        # SNI / cert verification done against the original hostname.
        assert req.extensions["sni_hostname"] == "example.com"

    def test_build_pinned_request_resolves_host_only_once(self) -> None:
        """The host is resolved exactly once (no TOCTOU second resolution)."""
        with patch(
            "services.url_content_service.resolve_and_validate_host",
            return_value=["93.184.216.34"],
        ) as mock_resolve:
            with httpx.Client() as client:
                self.service._build_pinned_request(client, "https://example.com/x")

        mock_resolve.assert_called_once_with("example.com")

    def test_build_pinned_request_preserves_port(self) -> None:
        """A non-default port is preserved in both the pinned URL and Host header."""
        with patch(
            "services.url_content_service.resolve_and_validate_host",
            return_value=["93.184.216.34"],
        ):
            with httpx.Client() as client:
                req = self.service._build_pinned_request(
                    client, "https://example.com:8443/path"
                )

        assert req.url.host == "93.184.216.34"
        assert req.url.port == 8443
        assert req.headers["host"] == "example.com:8443"

    def test_build_pinned_request_ipv6_literal_bracketed(self) -> None:
        """IPv6 resolved address is bracketed in the URL host part."""
        with patch(
            "services.url_content_service.resolve_and_validate_host",
            return_value=["2606:2800:220:1:248:1893:25c8:1946"],
        ):
            with httpx.Client() as client:
                req = self.service._build_pinned_request(
                    client, "https://example.com/path"
                )

        assert req.url.host == "2606:2800:220:1:248:1893:25c8:1946"
        assert req.extensions["sni_hostname"] == "example.com"
        assert req.headers["host"] == "example.com"

    def test_build_pinned_request_rejects_private_resolution(self) -> None:
        """If resolution validation rejects (private IP mixed in), it propagates."""
        from utils.url_validator import UrlValidationError

        with patch(
            "services.url_content_service.resolve_and_validate_host",
            side_effect=UrlValidationError("private"),
        ):
            with httpx.Client() as client:
                with pytest.raises(UrlValidationError):
                    self.service._build_pinned_request(client, "https://evil.example.com/")

    def test_build_pinned_request_nxdomain_raises_fetch_error(self) -> None:
        """Empty resolution (NXDOMAIN) surfaces as a ContentFetchError."""
        with patch(
            "services.url_content_service.resolve_and_validate_host",
            return_value=[],
        ):
            with httpx.Client() as client:
                with pytest.raises(ContentFetchError, match="resolve"):
                    self.service._build_pinned_request(client, "https://missing.example.com/")

    def test_fetch_blocks_when_any_resolved_ip_is_private(self) -> None:
        """A host whose resolution includes a private IP is rejected (rebinding)."""
        from utils.url_validator import UrlValidationError

        # resolve_and_validate_host raises when ANY address is private.
        with patch(
            "services.url_content_service.resolve_and_validate_host",
            side_effect=UrlValidationError(
                "Access to private/internal IP addresses is blocked: rebind.example.com"
            ),
        ):
            with pytest.raises(ContentFetchError, match="SSRF"):
                self.service.fetch_content("https://rebind.example.com/page")

    @patch("services.url_content_service.httpx.Client")
    def test_fetch_passes_pinned_request_to_stream(self, mock_client_cls: MagicMock) -> None:
        """The streamed request uses the pinned IP URL, Host header and sni_hostname."""
        html = (
            "<html><head><title>T</title></head><body>"
            "<p>Plenty of meaningful content for the extractor to accept here.</p>"
            "</body></html>"
        )
        mock_client, resp = _setup_stream_client(
            mock_client_cls, text=html, url="https://example.com/article"
        )
        # Provide a real-ish build_request that records the pinned values.
        real_req = httpx.Request(
            "GET",
            "https://93.184.216.34/article",
            headers={"Host": "example.com"},
            extensions={"sni_hostname": "example.com"},
        )
        mock_client.build_request.return_value = real_req

        with patch(
            "services.url_content_service.resolve_and_validate_host",
            return_value=["93.184.216.34"],
        ):
            self.service.fetch_content("https://example.com/article")

        # stream() called with the pinned IP URL, Host header, sni extension.
        args, kwargs = mock_client.stream.call_args
        assert str(args[1]).startswith("https://93.184.216.34/")
        assert kwargs["headers"]["Host"] == "example.com"
        assert kwargs["extensions"]["sni_hostname"] == "example.com"

    @patch("services.url_content_service.httpx.Client")
    def test_redirect_hop_repins_each_hop(self, mock_client_cls: MagicMock) -> None:
        """Each redirect hop independently resolves + validates + pins."""
        # First response: redirect to a different host; second: real HTML.
        redirect_resp = MagicMock()
        redirect_resp.is_redirect = True
        redirect_resp.status_code = 302
        redirect_resp.headers = {"location": "https://final.example.com/dest"}

        ok_resp = MagicMock()
        ok_resp.is_redirect = False
        ok_resp.status_code = 200
        ok_resp.headers = {"content-type": "text/html; charset=utf-8"}
        ok_resp.encoding = "utf-8"
        ok_resp.url = "https://final.example.com/dest"
        ok_resp.iter_bytes.return_value = [
            b"<html><head><title>F</title></head><body>"
            b"<p>Plenty of meaningful destination content present here now.</p>"
            b"</body></html>"
        ]

        def make_cm(resp):
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=resp)
            cm.__exit__ = MagicMock(return_value=False)
            return cm

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.stream.side_effect = [make_cm(redirect_resp), make_cm(ok_resp)]
        mock_client.build_request.side_effect = lambda *a, **k: httpx.Request(
            "GET", "https://1.2.3.4/x", headers={"Host": "h"}, extensions={}
        )
        mock_client_cls.return_value = mock_client

        with patch(
            "services.url_content_service.resolve_and_validate_host",
            return_value=["93.184.216.34"],
        ) as mock_resolve:
            result = self.service.fetch_content("https://start.example.com/a")

        # Resolved twice: once for the start host, once for the redirect host.
        hosts = [c.args[0] for c in mock_resolve.call_args_list]
        assert hosts == ["start.example.com", "final.example.com"]
        assert result.url == "https://final.example.com/dest"


class TestSpaDetection:
    """Tests for SPA detection logic (T021)."""

    def setup_method(self) -> None:
        self.service = UrlContentService()

    def test_static_page_not_detected_as_spa(self) -> None:
        """Normal static HTML page is not detected as SPA."""
        html = """
        <html>
        <head><title>Static Page</title></head>
        <body>
            <h1>Hello World</h1>
            <p>This is a static page with plenty of content for reading.</p>
            <p>Another paragraph with more meaningful text content here.</p>
        </body>
        </html>
        """
        assert self.service._detect_spa(html) is False

    def test_noscript_with_enable_js_detected(self) -> None:
        """Page with noscript tag telling user to enable JS is detected as SPA."""
        html = """
        <html>
        <head><title>SPA App</title></head>
        <body>
            <noscript>You need to enable JavaScript to run this app.</noscript>
            <div id="root"></div>
        </body>
        </html>
        """
        assert self.service._detect_spa(html) is True

    def test_empty_root_container_detected(self) -> None:
        """Page with empty #root or #app container is detected as SPA."""
        html = """
        <html>
        <head><title>React App</title></head>
        <body>
            <div id="root"></div>
            <script src="/static/js/bundle.js"></script>
        </body>
        </html>
        """
        assert self.service._detect_spa(html) is True

    def test_empty_app_container_detected(self) -> None:
        """Page with empty #app container is detected as SPA."""
        html = """
        <html>
        <head><title>Vue App</title></head>
        <body>
            <div id="app"></div>
            <script src="/js/app.js"></script>
        </body>
        </html>
        """
        assert self.service._detect_spa(html) is True

    def test_bundle_js_pattern_detected(self) -> None:
        """Page with bundle.js or chunk.js script tags is detected as SPA."""
        html = """
        <html>
        <head><title>App</title></head>
        <body>
            <div id="root"></div>
            <script src="/static/js/main.chunk.js"></script>
            <script src="/static/js/bundle.js"></script>
        </body>
        </html>
        """
        assert self.service._detect_spa(html) is True

    def test_low_text_with_scripts_detected(self) -> None:
        """Page with very little text but many scripts is detected as SPA."""
        html = """
        <html>
        <head><title>App</title></head>
        <body>
            <div id="__next"></div>
            <script src="/_next/static/chunks/main.js"></script>
            <script src="/_next/static/chunks/pages/_app.js"></script>
        </body>
        </html>
        """
        assert self.service._detect_spa(html) is True

    def test_populated_root_not_detected(self) -> None:
        """Page with populated #root container is not detected as SPA."""
        html = """
        <html>
        <head><title>SSR App</title></head>
        <body>
            <div id="root">
                <h1>Server-rendered content</h1>
                <p>This page has been server-side rendered with actual content visible.</p>
                <p>Multiple paragraphs with meaningful text for the user to read and study.</p>
            </div>
        </body>
        </html>
        """
        assert self.service._detect_spa(html) is False

    @patch("services.url_content_service.httpx.Client")
    def test_fetch_content_retries_with_browser_on_spa(self, mock_client_cls: MagicMock) -> None:
        """When SPA is detected, fetch_content falls back to browser fetch."""
        spa_html = """
        <html>
        <head><title>SPA</title></head>
        <body>
            <noscript>You need to enable JavaScript to run this app.</noscript>
            <div id="root"></div>
            <script src="/static/js/bundle.js"></script>
        </body>
        </html>
        """
        _setup_stream_client(
            mock_client_cls,
            text=spa_html,
            url="https://spa-example.com",
        )

        service = UrlContentService()
        # Without browser service, SPA detection should raise ContentFetchError
        with pytest.raises(ContentFetchError, match="JavaScript"):
            service.fetch_content("https://spa-example.com")

    @patch("services.url_content_service.httpx.Client")
    def test_fetch_with_browser_fallback_success(self, mock_client_cls: MagicMock) -> None:
        """When SPA detected and browser service available, falls back to browser."""
        spa_html = """
        <html>
        <head><title>SPA</title></head>
        <body>
            <noscript>You need to enable JavaScript to run this app.</noscript>
            <div id="root"></div>
        </body>
        </html>
        """
        _setup_stream_client(
            mock_client_cls,
            text=spa_html,
            url="https://spa-example.com",
        )

        # Create mock browser service
        mock_browser = MagicMock()
        mock_browser.fetch_content.return_value = PageContent(
            url="https://spa-example.com",
            title="SPA Rendered",
            text_content="This is the rendered SPA content with plenty of text to process.",
            content_type="text/html",
            fetch_method="browser",
            fetched_at="2026-03-06T10:00:00Z",
        )

        service = UrlContentService(browser_service=mock_browser)
        result = service.fetch_content("https://spa-example.com")

        assert result.fetch_method == "browser"
        assert "rendered SPA content" in result.text_content
        mock_browser.fetch_content.assert_called_once_with("https://spa-example.com", profile_id=None)

"""Unit tests for URL detection in LINE webhook handler (T033)."""

import json
from unittest.mock import MagicMock, patch, ANY

import pytest

from webhook.line_handler import (
    detect_url_in_message,
    handle_message,
)
from services.line_service import LineEvent


class TestUrlDetection:
    """Tests for URL detection in LINE messages."""

    def test_detect_https_url(self) -> None:
        """Detects https URL in message text."""
        url = detect_url_in_message("Check this https://example.com/article")
        assert url == "https://example.com/article"

    def test_detect_http_url_normalizes_to_https(self) -> None:
        """Detects http URL and normalizes to https."""
        url = detect_url_in_message("See http://example.com/page")
        assert url == "https://example.com/page"

    def test_detect_url_with_path_and_query(self) -> None:
        """Detects URL with path and query parameters."""
        url = detect_url_in_message("https://example.com/path?q=test&page=1")
        assert url == "https://example.com/path?q=test&page=1"

    def test_detect_url_with_fragment(self) -> None:
        """Detects URL with fragment."""
        url = detect_url_in_message("https://example.com/docs#section-1")
        assert url == "https://example.com/docs#section-1"

    def test_no_url_returns_none(self) -> None:
        """Returns None when no URL in message."""
        url = detect_url_in_message("Just a normal message without links")
        assert url is None

    def test_empty_message_returns_none(self) -> None:
        """Returns None for empty message."""
        url = detect_url_in_message("")
        assert url is None

    def test_first_url_is_returned(self) -> None:
        """Returns first URL when multiple URLs present."""
        url = detect_url_in_message(
            "https://first.com and https://second.com"
        )
        assert url == "https://first.com"

    def test_url_only_message(self) -> None:
        """Detects URL when message is just a URL."""
        url = detect_url_in_message("https://example.com")
        assert url == "https://example.com"

    def test_ignores_non_url_text_with_dots(self) -> None:
        """Does not false-positive on text with dots."""
        url = detect_url_in_message("The version is 3.14.159")
        assert url is None


class TestHandleMessage:
    """Tests for message event handling with URL detection."""

    @patch("webhook.line_handler.line_service")
    def test_url_message_triggers_card_generation(self, mock_line_service: MagicMock) -> None:
        """URL message triggers card generation flow."""
        mock_line_service.get_user_id_from_line.return_value = "user-123"

        event = LineEvent(
            event_type="message",
            source_user_id="line-user-1",
            reply_token="reply-token-1",
            postback_data=None,
            timestamp=1234567890,
        )
        # Simulate message text in the event
        event.message_text = "https://example.com/article"  # type: ignore[attr-defined]

        with patch("webhook.line_handler.handle_url_card_generation") as mock_url_gen:
            handle_message(event)
            mock_url_gen.assert_called_once()

    @patch("webhook.line_handler.line_service")
    def test_non_url_message_ignored(self, mock_line_service: MagicMock) -> None:
        """Non-URL messages are not processed for card generation."""
        event = LineEvent(
            event_type="message",
            source_user_id="line-user-1",
            reply_token="reply-token-1",
            postback_data=None,
            timestamp=1234567890,
        )
        event.message_text = "Hello, how are you?"  # type: ignore[attr-defined]

        with patch("webhook.line_handler.handle_url_card_generation") as mock_url_gen:
            handle_message(event)
            mock_url_gen.assert_not_called()

    @patch("webhook.line_handler.line_service")
    def test_unlinked_user_gets_link_message(self, mock_line_service: MagicMock) -> None:
        """Unlinked user sending URL gets account link prompt."""
        mock_line_service.get_user_id_from_line.return_value = None

        event = LineEvent(
            event_type="message",
            source_user_id="line-user-1",
            reply_token="reply-token-1",
            postback_data=None,
            timestamp=1234567890,
        )
        event.message_text = "https://example.com/article"  # type: ignore[attr-defined]

        handle_message(event)
        mock_line_service.reply_message.assert_called_once()

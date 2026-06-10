"""Unit tests for URL detection in LINE webhook handler (T033)."""

from unittest.mock import MagicMock, patch


from webhook.line_handler import (
    detect_url_in_message,
    handle_message,
    handle_postback,
    handle_save_url_cards,
)
from services.line_service import LineEvent


class TestUrlDetection:
    """Tests for URL detection in LINE messages."""

    def test_detect_https_url(self) -> None:
        """Detects https URL in message text."""
        url = detect_url_in_message("Check this https://example.com/article")
        assert url == "https://example.com/article"

    def test_detect_http_url_returns_as_is(self) -> None:
        """Detects http URL and returns it without normalization (validation delegated to validate_url)."""
        url = detect_url_in_message("See http://example.com/page")
        assert url == "http://example.com/page"

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


class TestHandleSaveUrlCards:
    """C-3: ref-key based save flow (no re-generation)."""

    @patch("webhook.line_handler.card_service")
    @patch("webhook.line_handler.url_cards_store")
    @patch("webhook.line_handler.line_service")
    def test_save_from_store_no_regeneration(
        self, mock_line_service, mock_store, mock_card_service
    ):
        """Cards are loaded from the store and saved as-is (no AI/fetch)."""
        mock_store.get_pending_cards.return_value = {
            "cards": [
                {"front": "Q1", "back": "A1", "suggested_tags": ["t"]},
                {"front": "Q2", "back": "A2", "suggested_tags": []},
            ],
            "page_url": "https://example.com/page",
            "page_title": "Title",
            "saved": False,
        }
        mock_store.mark_saved.return_value = True

        with patch("webhook.line_handler.create_ai_service") as mock_ai, patch(
            "webhook.line_handler.UrlContentService"
        ) as mock_url:
            handle_save_url_cards(
                user_id="user-1",
                line_user_id="line-1",
                ref_key="URLCARDS#abc",
                reply_token="rt",
            )
            # No re-generation, no re-fetch.
            mock_ai.assert_not_called()
            mock_url.assert_not_called()

        assert mock_card_service.create_card.call_count == 2
        mock_line_service.reply_message.assert_called_once()
        reply = mock_line_service.reply_message.call_args.args[1]
        assert "2枚" in reply[0]["text"]

    @patch("webhook.line_handler.card_service")
    @patch("webhook.line_handler.url_cards_store")
    @patch("webhook.line_handler.line_service")
    def test_expired_or_missing_record_replies_expired(
        self, mock_line_service, mock_store, mock_card_service
    ):
        """Missing/expired ref returns the 'expired' reply and saves nothing."""
        mock_store.get_pending_cards.return_value = None

        handle_save_url_cards(
            user_id="user-1",
            line_user_id="line-1",
            ref_key="URLCARDS#gone",
            reply_token="rt",
        )

        mock_card_service.create_card.assert_not_called()
        reply = mock_line_service.reply_message.call_args.args[1]
        assert "有効期限" in reply[0]["text"]

    @patch("webhook.line_handler.card_service")
    @patch("webhook.line_handler.url_cards_store")
    @patch("webhook.line_handler.line_service")
    def test_double_tap_does_not_resave(
        self, mock_line_service, mock_store, mock_card_service
    ):
        """A second tap (mark_saved False) skips saving."""
        mock_store.get_pending_cards.return_value = {
            "cards": [{"front": "Q1", "back": "A1", "suggested_tags": []}],
            "page_url": "https://example.com",
            "page_title": "t",
            "saved": True,
        }
        mock_store.mark_saved.return_value = False

        handle_save_url_cards(
            user_id="user-1",
            line_user_id="line-1",
            ref_key="URLCARDS#abc",
            reply_token="rt",
        )

        mock_card_service.create_card.assert_not_called()
        reply = mock_line_service.reply_message.call_args.args[1]
        assert "既に保存" in reply[0]["text"]


class TestSaveUrlCardsPostbackRouting:
    """Routing of save_url_cards postbacks: ref= (new) vs url= (legacy)."""

    @patch("webhook.line_handler.line_service")
    def test_ref_postback_uses_new_handler(self, mock_line_service):
        mock_line_service.get_user_id_from_line.return_value = "user-1"
        event = LineEvent(
            event_type="postback",
            source_user_id="line-1",
            reply_token="rt",
            postback_data="action=save_url_cards&ref=URLCARDS#abc&count=2",
            timestamp=1,
        )
        with patch(
            "webhook.line_handler.handle_save_url_cards"
        ) as mock_new, patch(
            "webhook.line_handler.handle_save_url_cards_legacy"
        ) as mock_legacy:
            handle_postback(event)
            mock_new.assert_called_once()
            assert mock_new.call_args.args[2] == "URLCARDS#abc"
            mock_legacy.assert_not_called()

    @patch("webhook.line_handler.line_service")
    def test_legacy_url_postback_falls_back(self, mock_line_service):
        mock_line_service.get_user_id_from_line.return_value = "user-1"
        event = LineEvent(
            event_type="postback",
            source_user_id="line-1",
            reply_token="rt",
            postback_data="action=save_url_cards&url=https%3A%2F%2Fexample.com&count=5",
            timestamp=1,
        )
        with patch(
            "webhook.line_handler.handle_save_url_cards"
        ) as mock_new, patch(
            "webhook.line_handler.handle_save_url_cards_legacy"
        ) as mock_legacy:
            handle_postback(event)
            mock_legacy.assert_called_once()
            assert mock_legacy.call_args.args[2] == "https://example.com"
            mock_new.assert_not_called()

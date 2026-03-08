"""Unit tests for webhook/line_handler.py.

Note: URL detection and handle_message tests are in test_webhook_url_handler.py.
This file covers handler() signature verification and handle_postback() routing.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.line_service import LineEvent, SignatureVerificationError


class TestHandlerSignatureVerification:
    """Tests for the Lambda handler's signature verification logic."""

    @patch("webhook.line_handler.line_service")
    def test_handler_returns_200_on_valid_signature(self, mock_line_service):
        """Valid signature and empty events returns 200."""
        from webhook.line_handler import handler

        mock_line_service.verify_request.return_value = True
        mock_line_service.parse_events.return_value = []

        event = {
            "body": json.dumps({"events": []}),
            "headers": {"x-line-signature": "valid-sig"},
        }
        response = handler(event, MagicMock())

        assert response["statusCode"] == 200
        mock_line_service.verify_request.assert_called_once()

    @patch("webhook.line_handler.line_service")
    def test_handler_returns_400_on_missing_signature(self, mock_line_service):
        """Missing signature header returns 400."""
        from webhook.line_handler import handler

        event = {
            "body": "{}",
            "headers": {},
        }
        response = handler(event, MagicMock())

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "signature" in body["error"].lower()

    @patch("webhook.line_handler.line_service")
    def test_handler_returns_400_on_invalid_signature(self, mock_line_service):
        """Invalid signature returns 400."""
        from webhook.line_handler import handler

        mock_line_service.verify_request.return_value = False

        event = {
            "body": "{}",
            "headers": {"x-line-signature": "invalid-sig"},
        }
        response = handler(event, MagicMock())

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "signature" in body["error"].lower()

    @patch("webhook.line_handler.line_service")
    def test_handler_returns_500_on_signature_verification_error(self, mock_line_service):
        """SignatureVerificationError returns 500."""
        from webhook.line_handler import handler

        mock_line_service.verify_request.side_effect = SignatureVerificationError("config error")

        event = {
            "body": "{}",
            "headers": {"x-line-signature": "some-sig"},
        }
        response = handler(event, MagicMock())

        assert response["statusCode"] == 500

    @patch("webhook.line_handler.line_service")
    def test_handler_decodes_base64_body(self, mock_line_service):
        """Base64-encoded body is decoded before verification."""
        import base64

        from webhook.line_handler import handler

        mock_line_service.verify_request.return_value = True
        mock_line_service.parse_events.return_value = []

        original_body = '{"events": []}'
        encoded_body = base64.b64encode(original_body.encode()).decode()

        event = {
            "body": encoded_body,
            "isBase64Encoded": True,
            "headers": {"x-line-signature": "valid-sig"},
        }
        response = handler(event, MagicMock())

        assert response["statusCode"] == 200
        mock_line_service.verify_request.assert_called_once_with(original_body, "valid-sig")


class TestHandlerEventRouting:
    """Tests for event type routing in handler."""

    @patch("webhook.line_handler.line_service")
    @patch("webhook.line_handler.handle_postback")
    def test_handler_routes_postback_events(self, mock_handle_postback, mock_line_service):
        """Postback events are routed to handle_postback."""
        from webhook.line_handler import handler

        mock_line_service.verify_request.return_value = True
        postback_event = LineEvent(
            event_type="postback",
            source_user_id="line-user-1",
            reply_token="reply-token",
            postback_data="action=start",
            timestamp=1234567890,
        )
        mock_line_service.parse_events.return_value = [postback_event]

        event = {
            "body": "{}",
            "headers": {"x-line-signature": "valid-sig"},
        }
        handler(event, MagicMock())

        mock_handle_postback.assert_called_once_with(postback_event)

    @patch("webhook.line_handler.line_service")
    @patch("webhook.line_handler.handle_message")
    def test_handler_routes_message_events(self, mock_handle_message, mock_line_service):
        """Message events are routed to handle_message."""
        from webhook.line_handler import handler

        mock_line_service.verify_request.return_value = True
        message_event = LineEvent(
            event_type="message",
            source_user_id="line-user-1",
            reply_token="reply-token",
            postback_data=None,
            timestamp=1234567890,
            message_text="hello",
        )
        mock_line_service.parse_events.return_value = [message_event]

        event = {
            "body": "{}",
            "headers": {"x-line-signature": "valid-sig"},
        }
        handler(event, MagicMock())

        mock_handle_message.assert_called_once_with(message_event)

    @patch("webhook.line_handler.line_service")
    def test_handler_ignores_unknown_event_types(self, mock_line_service):
        """Unknown event types are silently ignored."""
        from webhook.line_handler import handler

        mock_line_service.verify_request.return_value = True
        unknown_event = LineEvent(
            event_type="follow",
            source_user_id="line-user-1",
            reply_token="reply-token",
            postback_data=None,
            timestamp=1234567890,
        )
        mock_line_service.parse_events.return_value = [unknown_event]

        event = {
            "body": "{}",
            "headers": {"x-line-signature": "valid-sig"},
        }
        response = handler(event, MagicMock())

        assert response["statusCode"] == 200


class TestHandlePostback:
    """Tests for postback event handling and action routing."""

    @patch("webhook.line_handler.line_service")
    @patch("webhook.line_handler.handle_start_action")
    def test_postback_start_action(self, mock_start, mock_line_service):
        """Postback with action=start routes to handle_start_action."""
        from webhook.line_handler import handle_postback

        mock_line_service.get_user_id_from_line.return_value = "user-123"

        event = LineEvent(
            event_type="postback",
            source_user_id="line-user-1",
            reply_token="reply-token",
            postback_data="action=start",
            timestamp=1234567890,
        )
        handle_postback(event)

        mock_start.assert_called_once_with("user-123", "line-user-1", "reply-token")

    @patch("webhook.line_handler.line_service")
    @patch("webhook.line_handler.handle_reveal_action")
    def test_postback_reveal_action(self, mock_reveal, mock_line_service):
        """Postback with action=reveal routes to handle_reveal_action."""
        from webhook.line_handler import handle_postback

        mock_line_service.get_user_id_from_line.return_value = "user-123"

        event = LineEvent(
            event_type="postback",
            source_user_id="line-user-1",
            reply_token="reply-token",
            postback_data="action=reveal&card_id=card-abc",
            timestamp=1234567890,
        )
        handle_postback(event)

        mock_reveal.assert_called_once_with("user-123", "card-abc", "reply-token")

    @patch("webhook.line_handler.line_service")
    @patch("webhook.line_handler.handle_grade_action")
    def test_postback_grade_action(self, mock_grade, mock_line_service):
        """Postback with action=grade routes to handle_grade_action."""
        from webhook.line_handler import handle_postback

        mock_line_service.get_user_id_from_line.return_value = "user-123"

        event = LineEvent(
            event_type="postback",
            source_user_id="line-user-1",
            reply_token="reply-token",
            postback_data="action=grade&card_id=card-abc&grade=4",
            timestamp=1234567890,
        )
        handle_postback(event)

        mock_grade.assert_called_once_with("user-123", "card-abc", 4, "reply-token")

    @patch("webhook.line_handler.line_service")
    def test_postback_unlinked_user_gets_link_message(self, mock_line_service):
        """Unlinked user gets account link prompt on postback."""
        from webhook.line_handler import handle_postback

        mock_line_service.get_user_id_from_line.return_value = None

        event = LineEvent(
            event_type="postback",
            source_user_id="line-user-1",
            reply_token="reply-token",
            postback_data="action=start",
            timestamp=1234567890,
        )
        handle_postback(event)

        mock_line_service.reply_message.assert_called_once()

    @patch("webhook.line_handler.line_service")
    def test_postback_missing_data_returns_early(self, mock_line_service):
        """Missing postback_data returns early without error."""
        from webhook.line_handler import handle_postback

        event = LineEvent(
            event_type="postback",
            source_user_id="line-user-1",
            reply_token="reply-token",
            postback_data=None,
            timestamp=1234567890,
        )
        handle_postback(event)

        mock_line_service.get_user_id_from_line.assert_not_called()

    @patch("webhook.line_handler.line_service")
    def test_postback_unknown_action(self, mock_line_service):
        """Unknown postback action sends fallback message."""
        from webhook.line_handler import handle_postback

        mock_line_service.get_user_id_from_line.return_value = "user-123"

        event = LineEvent(
            event_type="postback",
            source_user_id="line-user-1",
            reply_token="reply-token",
            postback_data="action=unknown_action",
            timestamp=1234567890,
        )
        handle_postback(event)

        mock_line_service.reply_message.assert_called_once()

    @patch("webhook.line_handler.line_service")
    def test_postback_grade_invalid_value_sends_error(self, mock_line_service):
        """Invalid grade value (>5) sends error message."""
        from webhook.line_handler import handle_postback

        mock_line_service.get_user_id_from_line.return_value = "user-123"

        event = LineEvent(
            event_type="postback",
            source_user_id="line-user-1",
            reply_token="reply-token",
            postback_data="action=grade&card_id=card-abc&grade=7",
            timestamp=1234567890,
        )
        handle_postback(event)

        mock_line_service.reply_message.assert_called_once()

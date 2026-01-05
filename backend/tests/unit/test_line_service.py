"""Unit tests for LINE service."""

import base64
import hashlib
import hmac
import json
import pytest
from unittest.mock import MagicMock, patch

from src.services.line_service import (
    LineService,
    LineEvent,
    verify_signature,
    SignatureVerificationError,
    LineApiError,
)
from src.services.flex_messages import (
    create_question_message,
    create_answer_message,
    create_no_cards_message,
    create_completion_message,
    create_link_required_message,
)


class TestSignatureVerification:
    """Tests for LINE signature verification."""

    def test_verify_signature_success(self):
        """Test successful signature verification."""
        body = '{"events": []}'
        channel_secret = "test-secret"

        # Calculate expected signature
        hash_value = hmac.new(
            channel_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(hash_value).decode("utf-8")

        assert verify_signature(body, signature, channel_secret) is True

    def test_verify_signature_invalid(self):
        """Test failed signature verification with wrong signature."""
        body = '{"events": []}'
        channel_secret = "test-secret"
        wrong_signature = "wrong-signature"

        assert verify_signature(body, wrong_signature, channel_secret) is False

    def test_verify_signature_empty(self):
        """Test failed signature verification with empty signature."""
        body = '{"events": []}'
        channel_secret = "test-secret"

        assert verify_signature(body, "", channel_secret) is False

    def test_verify_signature_none(self):
        """Test failed signature verification with None signature."""
        body = '{"events": []}'
        channel_secret = "test-secret"

        assert verify_signature(body, None, channel_secret) is False


class TestLineServiceParsing:
    """Tests for LINE event parsing."""

    @pytest.fixture
    def line_service(self):
        """Create LineService with mock credentials."""
        return LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )

    def test_parse_postback_event(self, line_service):
        """Test parsing postback event."""
        body = json.dumps({
            "events": [
                {
                    "type": "postback",
                    "timestamp": 1704067200000,
                    "source": {
                        "type": "user",
                        "userId": "U1234567890",
                    },
                    "replyToken": "reply-token-123",
                    "postback": {
                        "data": "action=start",
                    },
                }
            ]
        })

        events = line_service.parse_events(body)

        assert len(events) == 1
        assert events[0].event_type == "postback"
        assert events[0].source_user_id == "U1234567890"
        assert events[0].reply_token == "reply-token-123"
        assert events[0].postback_data == "action=start"

    def test_parse_multiple_events(self, line_service):
        """Test parsing multiple events."""
        body = json.dumps({
            "events": [
                {
                    "type": "postback",
                    "source": {"userId": "U1"},
                    "replyToken": "token1",
                    "postback": {"data": "action=start"},
                    "timestamp": 0,
                },
                {
                    "type": "message",
                    "source": {"userId": "U2"},
                    "replyToken": "token2",
                    "timestamp": 0,
                },
            ]
        })

        events = line_service.parse_events(body)

        assert len(events) == 2
        assert events[0].event_type == "postback"
        assert events[1].event_type == "message"

    def test_parse_invalid_json(self, line_service):
        """Test parsing invalid JSON returns empty list."""
        events = line_service.parse_events("invalid json")
        assert events == []

    def test_parse_empty_events(self, line_service):
        """Test parsing body with no events."""
        body = json.dumps({"events": []})
        events = line_service.parse_events(body)
        assert events == []


class TestLineServiceVerify:
    """Tests for LineService.verify_request."""

    def test_verify_request_success(self):
        """Test successful request verification."""
        service = LineService(
            channel_access_token="token",
            channel_secret="secret",
        )
        body = '{"events": []}'

        hash_value = hmac.new(
            "secret".encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(hash_value).decode("utf-8")

        assert service.verify_request(body, signature) is True

    def test_verify_request_no_secret(self):
        """Test verification fails without channel secret."""
        service = LineService(
            channel_access_token="token",
            channel_secret=None,
        )

        with pytest.raises(SignatureVerificationError):
            service.verify_request('{"events": []}', "signature")


class TestLineServiceApi:
    """Tests for LINE API calls."""

    @pytest.fixture
    def line_service(self):
        """Create LineService with mock credentials."""
        return LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )

    @patch("src.services.line_service.requests.post")
    def test_reply_message_success(self, mock_post, line_service):
        """Test successful reply message."""
        mock_post.return_value.raise_for_status = MagicMock()

        result = line_service.reply_message(
            "reply-token",
            [{"type": "text", "text": "Hello"}],
        )

        assert result is True
        mock_post.assert_called_once()

    @patch("src.services.line_service.requests.post")
    def test_push_message_success(self, mock_post, line_service):
        """Test successful push message."""
        mock_post.return_value.raise_for_status = MagicMock()

        result = line_service.push_message(
            "U1234567890",
            [{"type": "text", "text": "Hello"}],
        )

        assert result is True
        mock_post.assert_called_once()

    def test_reply_message_no_token(self):
        """Test reply fails without access token."""
        service = LineService(
            channel_access_token=None,
            channel_secret="secret",
        )

        with pytest.raises(LineApiError):
            service.reply_message("token", [{"type": "text", "text": "test"}])


class TestFlexMessages:
    """Tests for Flex Message generation."""

    def test_create_question_message(self):
        """Test question message generation."""
        message = create_question_message("card-123", "What is Python?")

        assert message["type"] == "flex"
        assert message["altText"] == "復習カード"
        assert "What is Python?" in json.dumps(message)
        assert "card-123" in json.dumps(message)

    def test_create_answer_message(self):
        """Test answer message generation."""
        message = create_answer_message(
            "card-123",
            "What is Python?",
            "A programming language",
        )

        assert message["type"] == "flex"
        assert "What is Python?" in json.dumps(message)
        assert "A programming language" in json.dumps(message)
        # Check grade buttons exist
        content = json.dumps(message)
        assert "grade=0" in content
        assert "grade=5" in content

    def test_create_no_cards_message(self):
        """Test no cards message generation."""
        message = create_no_cards_message()

        assert message["type"] == "text"
        assert "復習するカード" in message["text"]

    def test_create_completion_message(self):
        """Test completion message generation."""
        message = create_completion_message(5)

        assert message["type"] == "flex"
        assert "5枚" in json.dumps(message, ensure_ascii=False)

    def test_create_link_required_message(self):
        """Test link required message generation."""
        message = create_link_required_message("https://liff.line.me/xxx")

        assert message["type"] == "flex"
        assert "https://liff.line.me/xxx" in json.dumps(message)

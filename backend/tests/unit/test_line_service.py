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

    # TASK-0028: Timing attack prevention tests

    def test_verify_signature_with_none_signature_timing_safe(self):
        """Test that None signature still performs timing-safe comparison.

        This test verifies that hmac.compare_digest is called even for None signatures,
        preventing timing attacks by ensuring constant-time comparison.

        Requirements:
            - REQ-TASK-0028-001: hmac.compare_digest must be called for None signature
            - REQ-TASK-0028-101: None is normalized to empty string
            - NFR-TASK-0028-101: Constant processing time (timing-safe)
            - EDGE-TASK-0028-001: None signature returns False with timing-safe comparison

        Test Steps:
            1. Prepare request body as JSON string
            2. Call verify_signature with signature=None
            3. Verify function returns False
            4. Ensure hmac.compare_digest was called (timing-safe)
        """
        # Arrange
        body = '{"events": []}'
        channel_secret = "test-secret"

        # Act & Assert
        # Use patch to verify hmac.compare_digest is called
        with patch("hmac.compare_digest") as mock_compare:
            mock_compare.return_value = False
            result = verify_signature(body, None, channel_secret)

            # Should return False (verification failed)
            assert result is False

            # Critical: hmac.compare_digest must be called for timing-safe comparison
            # If early return happens, this assertion will fail
            mock_compare.assert_called_once()
            # Verify it was called with expected signature (empty string after normalization)
            args = mock_compare.call_args[0]
            assert args[1] == "" or args[1] is None  # signature arg should be empty or None

    def test_verify_signature_with_empty_signature_timing_safe(self):
        """Test that empty signature still performs timing-safe comparison.

        This test ensures that empty string signature ("") does not trigger
        an early return, but goes through hmac.compare_digest for timing safety.

        Requirements:
            - REQ-TASK-0028-002: hmac.compare_digest must be called for empty signature
            - REQ-TASK-0028-102: Empty string is used as-is (no normalization)
            - NFR-TASK-0028-101: Constant processing time (timing-safe)
            - EDGE-TASK-0028-002: Empty signature returns False with timing-safe comparison

        Test Steps:
            1. Prepare request body as JSON string
            2. Call verify_signature with signature=""
            3. Verify function returns False
            4. Ensure hmac.compare_digest was called (timing-safe)
        """
        # Arrange
        body = '{"events": []}'
        channel_secret = "test-secret"

        # Act & Assert
        # Use patch to verify hmac.compare_digest is called
        with patch("hmac.compare_digest") as mock_compare:
            mock_compare.return_value = False
            result = verify_signature(body, "", channel_secret)

            # Should return False (verification failed)
            assert result is False

            # Critical: hmac.compare_digest must be called for timing-safe comparison
            # If early return happens (if not signature: return False), this will fail
            mock_compare.assert_called_once()
            # Verify it was called with empty string signature
            args = mock_compare.call_args[0]
            assert args[1] == ""  # signature arg should be empty string

    def test_verify_signature_success_with_valid_signature(self):
        """Test successful signature verification with valid signature.

        This test ensures that valid signatures (calculated correctly using
        HMAC-SHA256) are still verified successfully after the timing-safe fix.

        Requirements:
            - REQ-TASK-0028-003: Valid signature returns True
            - NFR-TASK-0028-201: Existing valid signature verification flow must succeed

        Test Steps:
            1. Prepare request body as JSON string
            2. Calculate valid signature using HMAC-SHA256 + Base64
            3. Call verify_signature with valid signature
            4. Verify function returns True (verification success)
        """
        # Arrange
        body = '{"events": []}'
        channel_secret = "test-secret"

        # Calculate expected signature (same as LINE server does)
        hash_value = hmac.new(
            channel_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(hash_value).decode("utf-8")

        # Act
        result = verify_signature(body, signature, channel_secret)

        # Assert
        assert result is True

    def test_verify_signature_fails_with_invalid_signature(self):
        """Test failed signature verification with invalid signature.

        This test ensures that invalid signatures (incorrect HMAC values)
        are correctly rejected by the timing-safe verification.

        Requirements:
            - REQ-TASK-0028-004: Invalid signature returns False
            - NFR-TASK-0028-202: Existing invalid signature rejection flow must succeed

        Test Steps:
            1. Prepare request body as JSON string
            2. Provide wrong signature string
            3. Call verify_signature with wrong signature
            4. Verify function returns False (verification failed)
        """
        # Arrange
        body = '{"events": []}'
        channel_secret = "test-secret"
        wrong_signature = "wrong-signature-value"

        # Act
        result = verify_signature(body, wrong_signature, channel_secret)

        # Assert
        assert result is False

    def test_verify_signature_fails_with_modified_body(self):
        """Test signature verification fails when body is modified.

        This test ensures that body tampering is detected by signature verification,
        even with the timing-safe implementation.

        Requirements:
            - REQ-TASK-0028-103: Modified body fails signature verification

        Test Steps:
            1. Prepare original request body
            2. Calculate valid signature for original body
            3. Modify the request body (simulate tampering)
            4. Call verify_signature with modified body + original signature
            5. Verify function returns False (tampering detected)
        """
        # Arrange
        original_body = '{"events": []}'
        channel_secret = "test-secret"
        modified_body = '{"events": [{"type": "message"}]}'

        # Calculate signature for original body
        hash_value = hmac.new(
            channel_secret.encode("utf-8"),
            original_body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(hash_value).decode("utf-8")

        # Act: Verify signature with modified body
        result = verify_signature(modified_body, signature, channel_secret)

        # Assert
        # Signature was calculated for original_body, but verifying modified_body
        # This should fail (tampering detected)
        assert result is False


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

    @patch("src.services.line_service.httpx.post")
    def test_reply_message_success(self, mock_post, line_service):
        """Test successful reply message."""
        mock_post.return_value.raise_for_status = MagicMock()

        result = line_service.reply_message(
            "reply-token",
            [{"type": "text", "text": "Hello"}],
        )

        assert result is True
        mock_post.assert_called_once()

    @patch("src.services.line_service.httpx.post")
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

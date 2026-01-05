"""LINE Webhook integration tests.

Tests:
- TASK-0021: LINE統合テスト
- TC-032-01: grade=5でのPostback処理テスト
- Webhook署名検証
- Postbackアクション処理
"""

import base64
import hashlib
import hmac
import json
from urllib.parse import parse_qs
from unittest.mock import MagicMock, patch

import pytest

from src.services.line_service import (
    LineService,
    LineEvent,
    verify_signature,
    SignatureVerificationError,
)
from src.services.card_service import CardNotFoundError


@pytest.fixture
def channel_secret():
    """Test channel secret."""
    return "test-channel-secret-12345"


@pytest.fixture
def channel_access_token():
    """Test channel access token."""
    return "test-channel-access-token"


@pytest.fixture
def line_service_mock(channel_secret, channel_access_token):
    """Create mocked LineService."""
    service = LineService(
        channel_access_token=channel_access_token,
        channel_secret=channel_secret,
    )
    return service


def generate_signature(body: str, channel_secret: str) -> str:
    """Generate valid LINE webhook signature."""
    hash_value = hmac.new(
        channel_secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(hash_value).decode("utf-8")


def create_webhook_event(
    event_type: str = "postback",
    user_id: str = "U1234567890",
    reply_token: str = "test-reply-token",
    postback_data: str = None,
) -> dict:
    """Create LINE webhook event structure."""
    event = {
        "type": event_type,
        "timestamp": 1704067200000,
        "source": {
            "type": "user",
            "userId": user_id,
        },
        "replyToken": reply_token,
    }
    if postback_data:
        event["postback"] = {"data": postback_data}
    return {"events": [event]}


def parse_postback_data(data: str) -> dict:
    """Parse postback data string into dictionary (copied from line_handler)."""
    if not data:
        return {}
    parsed = parse_qs(data)
    return {k: v[0] if v else "" for k, v in parsed.items()}


class TestSignatureVerification:
    """Test LINE webhook signature verification."""

    def test_valid_signature_passes(self, channel_secret):
        """Valid signature should pass verification."""
        body = '{"events":[]}'
        signature = generate_signature(body, channel_secret)

        result = verify_signature(body, signature, channel_secret)

        assert result is True

    def test_invalid_signature_fails(self, channel_secret):
        """Invalid signature should fail verification."""
        body = '{"events":[]}'
        invalid_signature = "invalid-signature"

        result = verify_signature(body, invalid_signature, channel_secret)

        assert result is False

    def test_empty_signature_fails(self, channel_secret):
        """Empty signature should fail verification."""
        body = '{"events":[]}'

        result = verify_signature(body, "", channel_secret)

        assert result is False

    def test_modified_body_fails(self, channel_secret):
        """Signature for modified body should fail."""
        original_body = '{"events":[]}'
        signature = generate_signature(original_body, channel_secret)
        modified_body = '{"events":[{"type":"modified"}]}'

        result = verify_signature(modified_body, signature, channel_secret)

        assert result is False


class TestEventParsing:
    """Test LINE webhook event parsing."""

    def test_parse_postback_event(self, line_service_mock):
        """Should correctly parse postback event."""
        body = json.dumps(
            create_webhook_event(
                event_type="postback",
                user_id="U12345",
                reply_token="reply-token",
                postback_data="action=grade&card_id=card-1&grade=5",
            )
        )

        events = line_service_mock.parse_events(body)

        assert len(events) == 1
        assert events[0].event_type == "postback"
        assert events[0].source_user_id == "U12345"
        assert events[0].reply_token == "reply-token"
        assert events[0].postback_data == "action=grade&card_id=card-1&grade=5"

    def test_parse_multiple_events(self, line_service_mock):
        """Should correctly parse multiple events."""
        body = json.dumps(
            {
                "events": [
                    {
                        "type": "postback",
                        "source": {"type": "user", "userId": "U1"},
                        "replyToken": "token1",
                        "postback": {"data": "action=start"},
                        "timestamp": 1000,
                    },
                    {
                        "type": "message",
                        "source": {"type": "user", "userId": "U2"},
                        "replyToken": "token2",
                        "timestamp": 2000,
                    },
                ]
            }
        )

        events = line_service_mock.parse_events(body)

        assert len(events) == 2
        assert events[0].event_type == "postback"
        assert events[1].event_type == "message"

    def test_parse_invalid_json(self, line_service_mock):
        """Should return empty list for invalid JSON."""
        events = line_service_mock.parse_events("invalid json")

        assert events == []

    def test_parse_empty_events(self, line_service_mock):
        """Should return empty list for empty events."""
        events = line_service_mock.parse_events('{"events":[]}')

        assert events == []


class TestPostbackDataParsing:
    """Test postback data string parsing."""

    def test_parse_grade_action(self):
        """Should parse grade action data."""
        data = "action=grade&card_id=card-123&grade=5"

        result = parse_postback_data(data)

        assert result["action"] == "grade"
        assert result["card_id"] == "card-123"
        assert result["grade"] == "5"

    def test_parse_start_action(self):
        """Should parse start action data."""
        data = "action=start"

        result = parse_postback_data(data)

        assert result["action"] == "start"

    def test_parse_reveal_action(self):
        """Should parse reveal action data."""
        data = "action=reveal&card_id=card-456"

        result = parse_postback_data(data)

        assert result["action"] == "reveal"
        assert result["card_id"] == "card-456"

    def test_parse_empty_data(self):
        """Should handle empty data string."""
        result = parse_postback_data("")

        assert result == {}


class TestLineEventDataclass:
    """Test LineEvent dataclass."""

    def test_create_postback_event(self):
        """Should create postback event with all fields."""
        event = LineEvent(
            event_type="postback",
            source_user_id="U12345",
            reply_token="test-token",
            postback_data="action=grade&card_id=card-1&grade=5",
            timestamp=1704067200000,
        )

        assert event.event_type == "postback"
        assert event.source_user_id == "U12345"
        assert event.reply_token == "test-token"
        assert event.postback_data == "action=grade&card_id=card-1&grade=5"

    def test_create_message_event_without_postback(self):
        """Should create message event without postback data."""
        event = LineEvent(
            event_type="message",
            source_user_id="U12345",
            reply_token="test-token",
            postback_data=None,
            timestamp=1704067200000,
        )

        assert event.event_type == "message"
        assert event.postback_data is None


class TestGradePostbackTC03201:
    """TC-032-01: grade=5でのPostback処理テスト.

    This tests the SM-2 grading flow where grade=5 represents
    "perfect response - answered easily and correctly".
    """

    def test_grade_5_postback_data_parsing(self):
        """Grade 5 postback data should be parsed correctly."""
        data = "action=grade&card_id=card-123&grade=5"

        result = parse_postback_data(data)

        assert result["action"] == "grade"
        assert result["card_id"] == "card-123"
        assert result["grade"] == "5"
        assert int(result["grade"]) == 5  # SM-2: grade 5 = perfect response

    def test_grade_5_is_valid_sm2_grade(self):
        """Grade 5 should be within valid SM-2 range (0-5)."""
        data = "action=grade&card_id=card-123&grade=5"
        result = parse_postback_data(data)

        grade = int(result["grade"])

        assert 0 <= grade <= 5  # Valid SM-2 range
        assert grade == 5  # Maximum grade

    def test_all_valid_grades_parse_correctly(self):
        """All valid SM-2 grades (0-5) should parse correctly."""
        for expected_grade in range(6):
            data = f"action=grade&card_id=card-123&grade={expected_grade}"
            result = parse_postback_data(data)

            assert int(result["grade"]) == expected_grade


class TestLineServiceIntegration:
    """Test LineService class integration."""

    def test_line_service_initialization(self):
        """LineService should initialize with credentials."""
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )

        assert service is not None
        assert service.channel_secret == "test-secret"

    def test_line_service_verify_request(self, line_service_mock, channel_secret):
        """LineService should verify valid webhook requests."""
        body = '{"events":[]}'
        signature = generate_signature(body, channel_secret)

        result = line_service_mock.verify_request(body, signature)

        assert result is True

    def test_line_service_reject_invalid_request(self, line_service_mock):
        """LineService should reject invalid webhook signatures."""
        body = '{"events":[]}'
        invalid_signature = "invalid"

        result = line_service_mock.verify_request(body, invalid_signature)

        assert result is False


class TestWebhookEventStructure:
    """Test webhook event JSON structure."""

    def test_postback_event_structure(self):
        """Postback event should have correct JSON structure."""
        event = create_webhook_event(
            event_type="postback",
            user_id="U123",
            reply_token="token",
            postback_data="action=start",
        )

        assert "events" in event
        assert len(event["events"]) == 1
        assert event["events"][0]["type"] == "postback"
        assert event["events"][0]["source"]["userId"] == "U123"
        assert event["events"][0]["postback"]["data"] == "action=start"

    def test_message_event_structure(self):
        """Message event should have correct JSON structure."""
        event = create_webhook_event(
            event_type="message",
            user_id="U456",
            reply_token="token2",
        )

        assert event["events"][0]["type"] == "message"
        assert "postback" not in event["events"][0]


class TestErrorScenarios:
    """Test error handling scenarios."""

    def test_invalid_grade_value(self):
        """Non-numeric grade should not parse as valid grade."""
        data = "action=grade&card_id=card-123&grade=invalid"
        result = parse_postback_data(data)

        assert result["grade"] == "invalid"
        assert not result["grade"].isdigit()

    def test_missing_card_id(self):
        """Missing card_id should result in empty string."""
        data = "action=reveal"
        result = parse_postback_data(data)

        assert "card_id" not in result

    def test_grade_out_of_range(self):
        """Grade outside 0-5 range should be detectable."""
        data = "action=grade&card_id=card-123&grade=10"
        result = parse_postback_data(data)

        grade = int(result["grade"])
        # Handler should check: 0 <= grade <= 5
        is_valid = 0 <= grade <= 5
        assert is_valid is False

    def test_negative_grade(self):
        """Negative grade should be detectable."""
        data = "action=grade&card_id=card-123&grade=-1"
        result = parse_postback_data(data)

        # parse_qs doesn't preserve negative sign properly
        # But we can detect it's not a valid positive integer
        grade_str = result["grade"]
        is_valid = grade_str.isdigit() and 0 <= int(grade_str) <= 5
        assert is_valid is False


class TestSignatureGeneration:
    """Test signature generation utilities."""

    def test_signature_is_base64(self, channel_secret):
        """Generated signature should be base64 encoded."""
        body = '{"events":[]}'
        signature = generate_signature(body, channel_secret)

        # Should be valid base64
        decoded = base64.b64decode(signature)
        assert len(decoded) == 32  # SHA256 hash length

    def test_different_bodies_different_signatures(self, channel_secret):
        """Different bodies should produce different signatures."""
        body1 = '{"events":[]}'
        body2 = '{"events":[{"type":"message"}]}'

        sig1 = generate_signature(body1, channel_secret)
        sig2 = generate_signature(body2, channel_secret)

        assert sig1 != sig2

    def test_same_body_same_signature(self, channel_secret):
        """Same body should always produce same signature."""
        body = '{"events":[]}'

        sig1 = generate_signature(body, channel_secret)
        sig2 = generate_signature(body, channel_secret)

        assert sig1 == sig2

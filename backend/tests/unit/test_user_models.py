"""Unit tests for user models."""

import pytest
from pydantic import ValidationError

from src.models.user import LinkLineRequest, UserSettingsRequest, User


class TestLinkLineRequest:
    """Tests for LinkLineRequest model (TASK-0044: id_token based)."""

    def test_valid_id_token(self):
        """Test valid LIFF ID token."""
        request = LinkLineRequest(id_token="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test")
        assert request.id_token == "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test"

    def test_empty_id_token_raises_validation_error(self):
        """Test that empty id_token raises ValidationError."""
        with pytest.raises(ValidationError):
            LinkLineRequest(id_token="")

    def test_missing_id_token_raises_validation_error(self):
        """Test that missing id_token raises ValidationError."""
        with pytest.raises(ValidationError):
            LinkLineRequest()

    def test_id_token_any_non_empty_string(self):
        """Test that any non-empty string is accepted as id_token."""
        request = LinkLineRequest(id_token="any-non-empty-string")
        assert request.id_token == "any-non-empty-string"


class TestUserSettingsRequest:
    """Tests for UserSettingsRequest model."""

    def test_valid_notification_time(self):
        """Test valid notification time format."""
        request = UserSettingsRequest(notification_time="09:00")
        assert request.notification_time == "09:00"

    def test_valid_notification_time_midnight(self):
        """Test midnight notification time."""
        request = UserSettingsRequest(notification_time="00:00")
        assert request.notification_time == "00:00"

    def test_valid_notification_time_end_of_day(self):
        """Test end of day notification time."""
        request = UserSettingsRequest(notification_time="23:59")
        assert request.notification_time == "23:59"

    def test_invalid_notification_time_25_hour(self):
        """Test invalid notification time with 25 hour."""
        with pytest.raises(ValidationError) as exc_info:
            UserSettingsRequest(notification_time="25:00")
        assert "Invalid notification time format" in str(exc_info.value)

    def test_invalid_notification_time_60_minute(self):
        """Test invalid notification time with 60 minute."""
        with pytest.raises(ValidationError) as exc_info:
            UserSettingsRequest(notification_time="12:60")
        assert "Invalid notification time format" in str(exc_info.value)

    def test_invalid_notification_time_format(self):
        """Test invalid notification time format."""
        with pytest.raises(ValidationError) as exc_info:
            UserSettingsRequest(notification_time="9:00")
        assert "Invalid notification time format" in str(exc_info.value)

    def test_valid_timezone(self):
        """Test valid timezone."""
        request = UserSettingsRequest(timezone="Asia/Tokyo")
        assert request.timezone == "Asia/Tokyo"

    def test_valid_timezone_utc(self):
        """Test UTC timezone."""
        request = UserSettingsRequest(timezone="UTC")
        assert request.timezone == "UTC"

    def test_none_values_allowed(self):
        """Test that None values are allowed."""
        request = UserSettingsRequest()
        assert request.notification_time is None
        assert request.timezone is None


class TestUser:
    """Tests for User model."""

    def test_to_response(self):
        """Test conversion to response model."""
        from datetime import datetime

        user = User(
            user_id="test-user-id",
            line_user_id="U1234567890abcdef1234567890abcdef",
            display_name="Test User",
            settings={"notification_time": "10:00", "timezone": "Asia/Tokyo"},
            created_at=datetime(2024, 1, 1, 0, 0, 0),
        )
        response = user.to_response()
        assert response.user_id == "test-user-id"
        assert response.display_name == "Test User"
        assert response.line_linked is True
        assert response.notification_time == "10:00"
        assert response.timezone == "Asia/Tokyo"

    def test_to_response_no_line_linked(self):
        """Test conversion when LINE is not linked."""
        from datetime import datetime

        user = User(
            user_id="test-user-id",
            created_at=datetime(2024, 1, 1, 0, 0, 0),
        )
        response = user.to_response()
        assert response.line_linked is False

    def test_to_dynamodb_item(self):
        """Test conversion to DynamoDB item."""
        from datetime import datetime

        user = User(
            user_id="test-user-id",
            line_user_id="U1234567890abcdef1234567890abcdef",
            display_name="Test User",
            settings={"notification_time": "10:00", "timezone": "Asia/Tokyo"},
            created_at=datetime(2024, 1, 1, 0, 0, 0),
        )
        item = user.to_dynamodb_item()
        assert item["user_id"] == "test-user-id"
        assert item["line_user_id"] == "U1234567890abcdef1234567890abcdef"
        assert item["display_name"] == "Test User"
        assert item["settings"]["notification_time"] == "10:00"

    def test_from_dynamodb_item(self):
        """Test creation from DynamoDB item."""
        item = {
            "user_id": "test-user-id",
            "line_user_id": "U1234567890abcdef1234567890abcdef",
            "display_name": "Test User",
            "settings": {"notification_time": "10:00", "timezone": "Asia/Tokyo"},
            "created_at": "2024-01-01T00:00:00",
        }
        user = User.from_dynamodb_item(item)
        assert user.user_id == "test-user-id"
        assert user.line_user_id == "U1234567890abcdef1234567890abcdef"
        assert user.display_name == "Test User"
        assert user.settings["notification_time"] == "10:00"

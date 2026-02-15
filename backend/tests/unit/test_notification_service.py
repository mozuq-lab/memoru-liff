"""Unit tests for notification service and due push handler."""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.models.user import User
from src.services.notification_service import NotificationService, NotificationResult
from src.services.line_service import LineApiError
from src.services.flex_messages import create_reminder_message


class TestCreateReminderMessage:
    """Tests for reminder message generation."""

    def test_create_reminder_message(self):
        """Test reminder message generation with due count."""
        message = create_reminder_message(5)

        assert message["type"] == "flex"
        assert message["altText"] == "復習リマインド"
        # Check content includes due count
        content = json.dumps(message, ensure_ascii=False)
        assert "5枚のカードが復習を待っています" in content
        assert "action=start" in content

    def test_create_reminder_message_single_card(self):
        """Test reminder message with single card."""
        message = create_reminder_message(1)

        content = json.dumps(message, ensure_ascii=False)
        assert "1枚のカードが復習を待っています" in content


class TestNotificationService:
    """Tests for NotificationService."""

    @pytest.fixture
    def mock_services(self):
        """Create mock services."""
        user_service = MagicMock()
        card_service = MagicMock()
        line_service = MagicMock()
        return user_service, card_service, line_service

    @pytest.fixture
    def notification_service(self, mock_services):
        """Create NotificationService with mocks."""
        user_service, card_service, line_service = mock_services
        return NotificationService(
            user_service=user_service,
            card_service=card_service,
            line_service=line_service,
        )

    def _create_user(
        self,
        user_id: str,
        line_user_id: str = "U1234567890abcdef1234567890abcdef",
        last_notified_date: str = None,
    ) -> User:
        """Helper to create a User object."""
        return User(
            user_id=user_id,
            line_user_id=line_user_id,
            last_notified_date=last_notified_date,
            created_at=datetime.now(timezone.utc),
        )

    def test_process_notifications_success(self, notification_service, mock_services):
        """Test successful notification processing."""
        user_service, card_service, line_service = mock_services

        # Setup mocks
        user = self._create_user("user-1")
        user_service.get_linked_users.return_value = [user]
        card_service.get_due_card_count.return_value = 5
        line_service.push_message.return_value = True

        # Process
        current_time = datetime(2024, 1, 5, 9, 0, 0, tzinfo=timezone.utc)
        result = notification_service.process_notifications(current_time)

        # Verify
        assert result.processed == 1
        assert result.sent == 1
        assert result.skipped == 0
        assert len(result.errors) == 0

        # Verify push was called
        line_service.push_message.assert_called_once()
        user_service.update_last_notified_date.assert_called_once_with(
            "user-1", "2024-01-05"
        )

    def test_process_notifications_already_notified_today(
        self, notification_service, mock_services
    ):
        """Test skipping user who was already notified today."""
        user_service, card_service, line_service = mock_services

        # User already notified today
        user = self._create_user("user-1", last_notified_date="2024-01-05")
        user_service.get_linked_users.return_value = [user]

        # Process
        current_time = datetime(2024, 1, 5, 9, 0, 0, tzinfo=timezone.utc)
        result = notification_service.process_notifications(current_time)

        # Verify
        assert result.processed == 1
        assert result.sent == 0
        assert result.skipped == 1
        line_service.push_message.assert_not_called()

    def test_process_notifications_no_due_cards(
        self, notification_service, mock_services
    ):
        """Test skipping user with no due cards."""
        user_service, card_service, line_service = mock_services

        user = self._create_user("user-1")
        user_service.get_linked_users.return_value = [user]
        card_service.get_due_card_count.return_value = 0

        # Process
        current_time = datetime(2024, 1, 5, 9, 0, 0, tzinfo=timezone.utc)
        result = notification_service.process_notifications(current_time)

        # Verify
        assert result.processed == 1
        assert result.sent == 0
        assert result.skipped == 1
        line_service.push_message.assert_not_called()

    def test_process_notifications_multiple_users(
        self, notification_service, mock_services
    ):
        """Test processing multiple users."""
        user_service, card_service, line_service = mock_services

        users = [
            self._create_user("user-1"),
            self._create_user("user-2"),
            self._create_user("user-3"),
        ]
        user_service.get_linked_users.return_value = users
        card_service.get_due_card_count.return_value = 3
        line_service.push_message.return_value = True

        # Process
        current_time = datetime(2024, 1, 5, 9, 0, 0, tzinfo=timezone.utc)
        result = notification_service.process_notifications(current_time)

        # Verify
        assert result.processed == 3
        assert result.sent == 3
        assert result.skipped == 0
        assert line_service.push_message.call_count == 3

    def test_process_notifications_line_api_error(
        self, notification_service, mock_services
    ):
        """Test handling LINE API error (e.g., user blocked)."""
        user_service, card_service, line_service = mock_services

        user = self._create_user("user-1")
        user_service.get_linked_users.return_value = [user]
        card_service.get_due_card_count.return_value = 5
        line_service.push_message.side_effect = LineApiError("User blocked the bot")

        # Process
        current_time = datetime(2024, 1, 5, 9, 0, 0, tzinfo=timezone.utc)
        result = notification_service.process_notifications(current_time)

        # Verify - error is logged but processing continues
        assert result.processed == 1
        assert result.sent == 0
        assert result.skipped == 0
        assert len(result.errors) == 1
        assert result.errors[0]["error_type"] == "line_api_error"

    def test_process_notifications_partial_failure(
        self, notification_service, mock_services
    ):
        """Test partial failure - some users blocked."""
        user_service, card_service, line_service = mock_services

        users = [
            self._create_user("user-1", "U0000000000000000000000000000001"),
            self._create_user("user-2", "U0000000000000000000000000000002"),  # blocked
            self._create_user("user-3", "U0000000000000000000000000000003"),
        ]
        user_service.get_linked_users.return_value = users
        card_service.get_due_card_count.return_value = 3

        # Second user is blocked
        def push_side_effect(line_user_id, messages):
            if line_user_id == "U0000000000000000000000000000002":
                raise LineApiError("User blocked")
            return True

        line_service.push_message.side_effect = push_side_effect

        # Process
        current_time = datetime(2024, 1, 5, 9, 0, 0, tzinfo=timezone.utc)
        result = notification_service.process_notifications(current_time)

        # Verify
        assert result.processed == 3
        assert result.sent == 2  # 2 successful
        assert result.skipped == 0
        assert len(result.errors) == 1  # 1 error

    def test_process_notifications_get_users_error(
        self, notification_service, mock_services
    ):
        """Test handling error when getting users."""
        user_service, card_service, line_service = mock_services

        user_service.get_linked_users.side_effect = Exception("DynamoDB error")

        # Process
        current_time = datetime(2024, 1, 5, 9, 0, 0, tzinfo=timezone.utc)
        result = notification_service.process_notifications(current_time)

        # Verify
        assert result.processed == 0
        assert result.sent == 0
        assert len(result.errors) == 1
        assert result.errors[0]["type"] == "get_users_failed"


class TestDuePushHandler:
    """Tests for the due push Lambda handler."""

    def test_handler_success(self):
        """Test handler returns success response."""
        # Mock the notification_service before importing handler
        with patch("src.services.notification_service.NotificationService") as MockService:
            mock_service = MagicMock()
            mock_result = NotificationResult(
                processed=10,
                sent=8,
                skipped=2,
                errors=[],
            )
            mock_service.process_notifications.return_value = mock_result
            MockService.return_value = mock_service

            # Import and reload module to pick up the mock
            import importlib
            import src.jobs.due_push_handler as handler_module
            importlib.reload(handler_module)

            # Call handler
            event = {}
            context = MagicMock()
            response = handler_module.handler(event, context)

            # Verify
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["processed_users"] == 10
            assert body["sent_notifications"] == 8
            assert body["skipped_users"] == 2
            assert body["error_count"] == 0

    def test_handler_with_errors(self):
        """Test handler includes error count in response."""
        # Mock the notification_service before importing handler
        with patch("src.services.notification_service.NotificationService") as MockService:
            mock_service = MagicMock()
            mock_result = NotificationResult(
                processed=10,
                sent=7,
                skipped=1,
                errors=[
                    {"user_id": "user-1", "error": "blocked"},
                    {"user_id": "user-2", "error": "blocked"},
                ],
            )
            mock_service.process_notifications.return_value = mock_result
            MockService.return_value = mock_service

            # Import and reload module
            import importlib
            import src.jobs.due_push_handler as handler_module
            importlib.reload(handler_module)

            # Call handler
            event = {}
            context = MagicMock()
            response = handler_module.handler(event, context)

            # Verify
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["error_count"] == 2

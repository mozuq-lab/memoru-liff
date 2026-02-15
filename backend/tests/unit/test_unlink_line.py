"""Unit tests for LINE account unlink functionality."""

import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from moto import mock_aws
import boto3
from botocore.exceptions import ClientError

from src.services.user_service import (
    UserService,
    UserNotFoundError,
    UserServiceError,
    LineNotLinkedError,
)


@pytest.fixture
def dynamodb_table():
    """Create a mock DynamoDB table."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        table = dynamodb.create_table(
            TableName="memoru-users-test",
            KeySchema=[{"AttributeName": "user_id", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "line_user_id", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "line_user_id-index",
                    "KeySchema": [{"AttributeName": "line_user_id", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        yield dynamodb


@pytest.fixture
def user_service(dynamodb_table):
    """Create UserService with mock DynamoDB."""
    return UserService(table_name="memoru-users-test", dynamodb_resource=dynamodb_table)


class TestUserServiceUnlinkLine:
    """Tests for UserService.unlink_line method."""

    def test_unlink_line_success(self, user_service, dynamodb_table):
        """Test unlinking LINE account successfully."""
        # Setup: create a user with LINE linked
        table = dynamodb_table.Table("memoru-users-test")
        line_user_id = "U1234567890abcdef1234567890abcdef"
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "line_user_id": line_user_id,
                "display_name": "Test User",
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                "created_at": "2024-01-01T00:00:00+00:00",
            }
        )

        # Execute
        result = user_service.unlink_line("test-user-id")

        # Assert
        assert result["user_id"] == "test-user-id"
        assert "unlinked_at" in result

        # Verify line_user_id was removed from DynamoDB
        response = table.get_item(Key={"user_id": "test-user-id"})
        item = response["Item"]
        assert "line_user_id" not in item
        assert "updated_at" in item

    def test_unlink_line_not_linked(self, user_service, dynamodb_table):
        """Test unlinking when user has no LINE account linked."""
        # Setup: create a user without LINE linked
        table = dynamodb_table.Table("memoru-users-test")
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "display_name": "Test User",
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                "created_at": "2024-01-01T00:00:00+00:00",
            }
        )

        # Execute & Assert: should raise LineNotLinkedError
        with pytest.raises(LineNotLinkedError) as exc_info:
            user_service.unlink_line("test-user-id")

        # Verify the error message
        assert "not linked" in str(exc_info.value).lower()

    def test_unlink_line_user_not_found(self, user_service):
        """Test unlinking LINE for non-existent user."""
        # Execute & Assert: DynamoDB will not raise error for non-existent user
        # if there's no ConditionExpression checking user existence,
        # but ConditionExpression on line_user_id will fail for non-existent users too
        with pytest.raises(LineNotLinkedError):
            user_service.unlink_line("non-existent-user")

    def test_unlink_line_datetime_timezone_aware(self, user_service, dynamodb_table):
        """Test that unlink_line uses timezone-aware datetime (UTC)."""
        # Setup: create a user with LINE linked
        table = dynamodb_table.Table("memoru-users-test")
        line_user_id = "U1234567890abcdef1234567890abcdef"
        table.put_item(
            Item={
                "user_id": "test-user-id",
                "line_user_id": line_user_id,
                "settings": {"notification_time": "09:00", "timezone": "Asia/Tokyo"},
                "created_at": "2024-01-01T00:00:00+00:00",
            }
        )

        # Execute
        result = user_service.unlink_line("test-user-id")

        # Assert: check that unlinked_at is timezone-aware (has +00:00 or Z suffix)
        unlinked_at = result["unlinked_at"]
        assert "+00:00" in unlinked_at or unlinked_at.endswith("Z")


class TestUnlinkLineAPIHandler:
    """Tests for POST /users/me/unlink-line endpoint."""

    def test_unlink_line_function_exists(self):
        """Test that unlink_line function is defined in handler module."""
        from src.api import handler

        # Verify the function exists
        assert hasattr(handler, "unlink_line")
        assert callable(handler.unlink_line)

    def test_unlink_line_function_calls_service(self):
        """Test that unlink_line function calls user_service.unlink_line with correct user_id."""
        from unittest.mock import patch, MagicMock
        from src.api.handler import unlink_line, app, get_user_id_from_context

        # Setup: mock dependencies
        with patch("src.api.handler.user_service") as mock_user_service, \
             patch("src.api.handler.get_user_id_from_context") as mock_get_user_id:

            mock_get_user_id.return_value = "test-user-id"
            mock_user_service.unlink_line.return_value = {
                "user_id": "test-user-id",
                "unlinked_at": "2024-01-15T10:00:00+00:00",
            }

            # Execute
            result = unlink_line()

            # Assert
            mock_get_user_id.assert_called_once()
            mock_user_service.unlink_line.assert_called_once_with("test-user-id")
            assert result["success"] is True
            assert result["data"]["user_id"] == "test-user-id"

    def test_unlink_line_function_handles_not_linked_error(self):
        """Test that unlink_line function handles LineNotLinkedError with 400 response."""
        from unittest.mock import patch
        from src.api.handler import unlink_line
        from src.services.user_service import LineNotLinkedError
        import json

        # Setup: mock dependencies
        with patch("src.api.handler.user_service") as mock_user_service, \
             patch("src.api.handler.get_user_id_from_context") as mock_get_user_id:

            mock_get_user_id.return_value = "test-user-id"
            mock_user_service.unlink_line.side_effect = LineNotLinkedError("LINE account not linked")

            # Execute
            response = unlink_line()

            # Assert
            assert response.status_code == 400
            body = json.loads(response.body)
            assert "error" in body
            assert "not linked" in body["error"].lower()

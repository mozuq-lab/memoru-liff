"""Pytest configuration and fixtures."""

import os
import sys

import pytest

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Set environment variables for testing
os.environ["ENVIRONMENT"] = "test"
os.environ["AWS_DEFAULT_REGION"] = "ap-northeast-1"
os.environ["USERS_TABLE"] = "memoru-users-test"
os.environ["CARDS_TABLE"] = "memoru-cards-test"
os.environ["REVIEWS_TABLE"] = "memoru-reviews-test"
# ai-async-jobs: AiJobStore の既定テーブル名 (memoru-ai-jobs-dev) への
# 実アクセスを防ぐため、テストでは必ずテスト用テーブル名を指す。
os.environ["AI_JOBS_TABLE"] = "memoru-ai-jobs-test"
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["POWERTOOLS_SERVICE_NAME"] = "memoru-test"
os.environ["POWERTOOLS_TRACE_DISABLED"] = "true"


@pytest.fixture
def api_gateway_event():
    """Create a base API Gateway HTTP API event."""

    def _create_event(
        method: str = "GET",
        path: str = "/",
        body: dict = None,
        headers: dict = None,
        path_parameters: dict = None,
        query_string_parameters: dict = None,
        user_id: str = "test-user-id",
    ):
        event = {
            "version": "2.0",
            "routeKey": f"{method} {path}",
            "rawPath": path,
            "rawQueryString": "",
            "headers": headers or {"content-type": "application/json"},
            "requestContext": {
                "accountId": "123456789012",
                "apiId": "api-id",
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "sub": user_id,
                            "iss": "https://keycloak.example.com/realms/memoru",
                        },
                        "scopes": ["openid", "profile"],
                    }
                },
                "domainName": "api.example.com",
                "domainPrefix": "api",
                "http": {
                    "method": method,
                    "path": path,
                    "protocol": "HTTP/1.1",
                    "sourceIp": "127.0.0.1",
                    "userAgent": "pytest",
                },
                "requestId": "request-id",
                "routeKey": f"{method} {path}",
                "stage": "$default",
                "time": "01/Jan/2024:00:00:00 +0000",
                "timeEpoch": 1704067200000,
            },
            "pathParameters": path_parameters or {},
            "stageVariables": None,
            "isBase64Encoded": False,
        }
        if body:
            import json

            event["body"] = json.dumps(body)
        if query_string_parameters:
            event["queryStringParameters"] = query_string_parameters
            event["rawQueryString"] = "&".join(
                f"{k}={v}" for k, v in query_string_parameters.items()
            )
        return event

    return _create_event


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""

    class MockContext:
        function_name = "memoru-api-test"
        memory_limit_in_mb = 256
        invoked_function_arn = (
            "arn:aws:lambda:ap-northeast-1:123456789012:function:memoru-api-test"
        )
        aws_request_id = "test-request-id"

    return MockContext()


@pytest.fixture
def user_response_factory():
    """Create UserResponse models for handler tests."""
    from models.user import UserResponse

    def _create(**overrides):
        values = {
            "user_id": "test-user-id",
            "display_name": None,
            "picture_url": None,
            "line_linked": False,
            "notification_time": "09:00",
            "timezone": "Asia/Tokyo",
            "day_start_hour": 4,
            "created_at": "2024-01-01T00:00:00+00:00",
            "updated_at": "2024-01-02T00:00:00+00:00",
        }
        values.update(overrides)
        return UserResponse(**values)

    return _create

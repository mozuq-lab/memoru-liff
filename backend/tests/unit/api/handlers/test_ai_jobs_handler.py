"""Unit tests for GET /ai-jobs/{jobId} (ai-async-jobs)."""

import json
from unittest.mock import patch

import pytest  # noqa: F401


def _make_job(user_id="test-user-id", status="completed", **overrides):
    job = {
        "job_id": "aijob_123",
        "user_id": user_id,
        "job_type": "generate",
        "status": status,
        "schema_version": 1,
        "payload": {"input_text": "secret input"},
        "created_at": "2026-07-07T00:00:00+00:00",
        "updated_at": "2026-07-07T00:00:05+00:00",
    }
    if status == "completed":
        job["result"] = {"generated_cards": []}
    if status == "failed":
        job["error"] = {"status": 504, "code": "ai_timeout", "message": "AI service timeout"}
    job.update(overrides)
    return job


class TestGetAiJob:
    def test_returns_completed_job_with_result(self, api_gateway_event, lambda_context):
        event = api_gateway_event(method="GET", path="/ai-jobs/aijob_123")

        with patch("api.handlers.ai_jobs_handler.ai_job_store") as mock_store:
            mock_store.get_job.return_value = _make_job()
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["job_id"] == "aijob_123"
        assert body["status"] == "completed"
        assert body["result"] == {"generated_cards": []}
        mock_store.get_job.assert_called_once_with("aijob_123")

    def test_hides_payload_and_schema_version(self, api_gateway_event, lambda_context):
        """payload（リクエスト原文）は返さない。"""
        event = api_gateway_event(method="GET", path="/ai-jobs/aijob_123")

        with patch("api.handlers.ai_jobs_handler.ai_job_store") as mock_store:
            mock_store.get_job.return_value = _make_job()
            from api.handler import handler

            response = handler(event, lambda_context)

        body = json.loads(response["body"])
        assert "payload" not in body
        assert "schema_version" not in body
        assert "user_id" not in body

    def test_failed_job_includes_error(self, api_gateway_event, lambda_context):
        event = api_gateway_event(method="GET", path="/ai-jobs/aijob_123")

        with patch("api.handlers.ai_jobs_handler.ai_job_store") as mock_store:
            mock_store.get_job.return_value = _make_job(status="failed")
            from api.handler import handler

            response = handler(event, lambda_context)

        body = json.loads(response["body"])
        assert body["status"] == "failed"
        assert body["error"]["status"] == 504
        assert body["error"]["code"] == "ai_timeout"

    def test_missing_job_returns_404(self, api_gateway_event, lambda_context):
        event = api_gateway_event(method="GET", path="/ai-jobs/aijob_missing")

        with patch("api.handlers.ai_jobs_handler.ai_job_store") as mock_store:
            mock_store.get_job.return_value = None
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 404
        assert json.loads(response["body"]) == {"error": "Job not found"}

    def test_other_users_job_returns_same_404(self, api_gateway_event, lambda_context):
        """他ユーザーのジョブも存在しない場合と同一の 404（IDOR: 列挙防止）。"""
        event = api_gateway_event(method="GET", path="/ai-jobs/aijob_123")

        with patch("api.handlers.ai_jobs_handler.ai_job_store") as mock_store:
            mock_store.get_job.return_value = _make_job(user_id="other-user")
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 404
        assert json.loads(response["body"]) == {"error": "Job not found"}

    def test_unauthorized_returns_401(self, api_gateway_event, lambda_context):
        event = api_gateway_event(method="GET", path="/ai-jobs/aijob_123")
        event["requestContext"]["authorizer"] = {}

        with patch("api.handlers.ai_jobs_handler.ai_job_store"):
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 401

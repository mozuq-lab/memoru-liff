"""Unit tests for the shared SQS client factory (utils/sqs_client)."""

from unittest.mock import MagicMock, patch

from utils import sqs_client


class TestGetSqsEndpointUrl:
    def test_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("SQS_ENDPOINT_URL", raising=False)
        assert sqs_client.get_sqs_endpoint_url() is None

    def test_returns_none_when_empty_string(self, monkeypatch):
        monkeypatch.setenv("SQS_ENDPOINT_URL", "")
        assert sqs_client.get_sqs_endpoint_url() is None

    def test_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("SQS_ENDPOINT_URL", "http://elasticmq:9324")
        assert sqs_client.get_sqs_endpoint_url() == "http://elasticmq:9324"


class TestGetSqsClient:
    def test_passes_endpoint_url_when_set(self, monkeypatch):
        monkeypatch.setenv("SQS_ENDPOINT_URL", "http://elasticmq:9324")
        with patch.object(sqs_client, "boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            sqs_client.get_sqs_client()
            mock_boto3.client.assert_called_once_with(
                "sqs", endpoint_url="http://elasticmq:9324"
            )

    def test_omits_endpoint_url_when_unset(self, monkeypatch):
        monkeypatch.delenv("SQS_ENDPOINT_URL", raising=False)
        with patch.object(sqs_client, "boto3") as mock_boto3:
            mock_boto3.client.return_value = MagicMock()
            sqs_client.get_sqs_client()
            mock_boto3.client.assert_called_once_with("sqs")

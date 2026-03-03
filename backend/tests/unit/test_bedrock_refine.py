"""BedrockService.refine_card() テスト.

TASK-0145: 正常系・パース系・エラー系テスト
"""

import json

import pytest
from botocore.exceptions import ClientError
from unittest.mock import MagicMock

from services.bedrock import (
    BedrockService,
    BedrockParseError,
    BedrockTimeoutError,
)
from services.ai_service import RefineResult


class TestBedrockRefineCardSuccess:
    """正常系テスト."""

    @pytest.fixture
    def mock_bedrock_client(self):
        return MagicMock()

    @pytest.fixture
    def bedrock_service(self, mock_bedrock_client):
        return BedrockService(bedrock_client=mock_bedrock_client)

    def _mock_invoke_response(self, mock_client, response_text):
        """Bedrock invoke_model のモックレスポンスを設定するヘルパー."""
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps({
            "content": [{"text": response_text}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_body}

    def test_refine_both(self, bedrock_service, mock_bedrock_client):
        """表面・裏面両方の refine が成功すること."""
        self._mock_invoke_response(
            mock_bedrock_client,
            '{"refined_front": "改善された質問", "refined_back": "改善された回答"}',
        )

        result = bedrock_service.refine_card(front="元の質問", back="元の回答")

        assert isinstance(result, RefineResult)
        assert result.refined_front == "改善された質問"
        assert result.refined_back == "改善された回答"
        assert result.model_used == bedrock_service.model_id
        assert isinstance(result.processing_time_ms, int)
        assert result.processing_time_ms >= 0

    def test_refine_front_only(self, bedrock_service, mock_bedrock_client):
        """表面のみ入力での refine が成功すること."""
        self._mock_invoke_response(
            mock_bedrock_client,
            '{"refined_front": "改善された質問", "refined_back": "生成された回答"}',
        )

        result = bedrock_service.refine_card(front="元の質問", back="")

        assert isinstance(result, RefineResult)
        assert result.refined_front == "改善された質問"
        assert result.refined_back == "生成された回答"


class TestBedrockRefineCardParsing:
    """パース系テスト."""

    @pytest.fixture
    def mock_bedrock_client(self):
        return MagicMock()

    @pytest.fixture
    def bedrock_service(self, mock_bedrock_client):
        return BedrockService(bedrock_client=mock_bedrock_client)

    def _mock_invoke_response(self, mock_client, response_text):
        """Bedrock invoke_model のモックレスポンスを設定するヘルパー."""
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps({
            "content": [{"text": response_text}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_body}

    def test_markdown_json_response(self, bedrock_service, mock_bedrock_client):
        """Markdown コードブロック内 JSON がパースされること."""
        self._mock_invoke_response(
            mock_bedrock_client,
            '```json\n{"refined_front": "改善された質問", "refined_back": "改善された回答"}\n```',
        )

        result = bedrock_service.refine_card(front="元の質問", back="元の回答")

        assert result.refined_front == "改善された質問"
        assert result.refined_back == "改善された回答"

    def test_missing_field_raises_error(self, bedrock_service, mock_bedrock_client):
        """必須フィールド欠落で BedrockParseError が発生すること."""
        self._mock_invoke_response(
            mock_bedrock_client,
            '{"refined_front": "改善された質問"}',
        )

        with pytest.raises(BedrockParseError, match="refined_back"):
            bedrock_service.refine_card(front="元の質問", back="元の回答")


class TestBedrockRefineCardErrors:
    """エラー系テスト."""

    @pytest.fixture
    def mock_bedrock_client(self):
        return MagicMock()

    @pytest.fixture
    def bedrock_service(self, mock_bedrock_client):
        return BedrockService(bedrock_client=mock_bedrock_client)

    def test_timeout_raises_error(self, bedrock_service, mock_bedrock_client):
        """タイムアウト時に BedrockTimeoutError が発生すること."""
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ReadTimeoutError", "Message": "Read timed out"}},
            "InvokeModel",
        )

        with pytest.raises(BedrockTimeoutError):
            bedrock_service.refine_card(front="元の質問", back="元の回答")

        # タイムアウトはリトライしない
        assert mock_bedrock_client.invoke_model.call_count == 1

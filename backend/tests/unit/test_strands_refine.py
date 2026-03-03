"""StrandsAIService.refine_card() テストスイート.

カテゴリ:
- TestRefineCardSuccess: refine_card 正常系テスト
- TestRefineCardParsing: _parse_refine_result テスト
- TestRefineCardErrors: エラーハンドリングテスト
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.ai_service import (
    AIParseError,
    AIServiceError,
    AITimeoutError,
    RefineResult,
)
from services.strands_service import StrandsAIService


def _make_mock_agent_instance(response_text: str) -> MagicMock:
    """Agent インスタンスのモックを作成するヘルパー."""
    mock_response = MagicMock()
    mock_response.__str__ = MagicMock(return_value=response_text)
    mock_agent = MagicMock()
    mock_agent.return_value = mock_response
    return mock_agent


class TestRefineCardSuccess:
    """refine_card() 正常系テスト."""

    def test_refine_both_front_and_back(self):
        """表面・裏面の両方を送信した場合、両方の改善結果が返ること."""
        response_json = json.dumps({
            "refined_front": "クロージャとは何か？",
            "refined_back": "外部スコープの変数を参照し続ける関数のこと。",
        })
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.refine_card(
                front="クロージャとは？",
                back="変数を覚えてる関数",
            )

        assert isinstance(result, RefineResult)
        assert result.refined_front == "クロージャとは何か？"
        assert result.refined_back == "外部スコープの変数を参照し続ける関数のこと。"

    def test_refine_front_only(self):
        """表面のみ送信した場合、refined_front のみ有効で refined_back が空文字."""
        response_json = json.dumps({
            "refined_front": "クロージャとは何か？",
            "refined_back": "",
        })
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.refine_card(front="クロージャ", back="")

        assert result.refined_front == "クロージャとは何か？"
        assert result.refined_back == ""

    def test_refine_back_only(self):
        """裏面のみ送信した場合、refined_back のみ有効で refined_front が空文字."""
        response_json = json.dumps({
            "refined_front": "",
            "refined_back": "外部スコープの変数を参照し続ける関数のこと。",
        })
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.refine_card(front="", back="変数を覚えてる関数")

        assert result.refined_front == ""
        assert result.refined_back == "外部スコープの変数を参照し続ける関数のこと。"

    def test_refine_markdown_wrapped_response(self):
        """Markdown コードブロック内 JSON が正しくパースされる."""
        response_text = '```json\n{"refined_front": "Q", "refined_back": "A"}\n```'
        mock_agent_instance = _make_mock_agent_instance(response_text)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.refine_card(front="q", back="a")

        assert result.refined_front == "Q"
        assert result.refined_back == "A"


class TestRefineCardParsing:
    """_parse_refine_result() テスト."""

    def _create_service(self):
        """テスト用サービスインスタンスを作成."""
        with patch("services.strands_service.BedrockModel"):
            return StrandsAIService()

    def test_parse_valid_json(self):
        """正しい JSON レスポンスのパースが成功すること."""
        service = self._create_service()
        response = json.dumps({"refined_front": "改善表面", "refined_back": "改善裏面"})
        refined_front, refined_back = service._parse_refine_result(response)

        assert refined_front == "改善表面"
        assert refined_back == "改善裏面"

    def test_parse_invalid_json(self):
        """不正な JSON の場合に AIParseError が発生すること."""
        service = self._create_service()
        with pytest.raises(AIParseError, match="Failed to parse JSON"):
            service._parse_refine_result("not valid json")

    def test_parse_missing_refined_front(self):
        """refined_front キーが欠落している場合のエラーハンドリング."""
        service = self._create_service()
        response = json.dumps({"refined_back": "裏面"})
        with pytest.raises(AIParseError, match="refined_front"):
            service._parse_refine_result(response)

    def test_parse_missing_refined_back(self):
        """refined_back キーが欠落している場合のエラーハンドリング."""
        service = self._create_service()
        response = json.dumps({"refined_front": "表面"})
        with pytest.raises(AIParseError, match="refined_back"):
            service._parse_refine_result(response)

    def test_parse_markdown_code_block(self):
        """Markdown コードブロック内の JSON が正しくパースされること."""
        service = self._create_service()
        response = '```json\n{"refined_front": "F", "refined_back": "B"}\n```'
        refined_front, refined_back = service._parse_refine_result(response)

        assert refined_front == "F"
        assert refined_back == "B"


class TestRefineCardErrors:
    """refine_card エラーハンドリングテスト."""

    def test_timeout_error(self):
        """タイムアウト時に AITimeoutError が発生すること."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = TimeoutError("Agent timed out")

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            with pytest.raises(AITimeoutError):
                service.refine_card(front="テスト", back="")

    def test_connection_error(self):
        """接続エラー時に AIServiceError 系が発生すること."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = ConnectionError("Connection refused")

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            with pytest.raises(AIServiceError):
                service.refine_card(front="テスト", back="")

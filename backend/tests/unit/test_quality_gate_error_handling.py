"""TASK-0065: 品質ゲート - エラーハンドリング一貫性.

カテゴリ 5: StrandsAIService エラーハンドリング一貫性 (TC-QG-011)
カテゴリ 6: BedrockService エラーハンドリング (TC-QG-012)

🔵 信頼性: 既存 test_quality_gate.py から分割。ロジック変更なし。
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.ai_service import (
    AIParseError,
    AIProviderError,
    AIRateLimitError,
    AIServiceError,
    AITimeoutError,
)
from services.bedrock import (
    BedrockInternalError,
    BedrockRateLimitError,
    BedrockService,
    BedrockTimeoutError,
)
from services.strands_service import StrandsAIService
from tests.unit.conftest import make_client_error, make_mock_agent


# =============================================================================
# カテゴリ 5: StrandsAIService エラーハンドリング一貫性 (TestStrandsErrorHandlingFinal)
# =============================================================================


class TestStrandsErrorHandlingFinal:
    """StrandsAIService の 3 メソッド全てが同一のエラーハンドリングパターンを持つことを最終確認.

    TC-QG-011-001 ~ TC-QG-011-012

    【テスト方針】: 各メソッド (generate_cards, grade_answer, get_learning_advice) が
    同一の例外マッピングロジックを持つことを parametrize で横断検証する。
    """

    # 【共通 kwargs】: 3 メソッドを parametrize で呼び出す際の引数セット
    _all_methods = [
        ("generate_cards", {"input_text": "test"}),
        ("grade_answer", {"card_front": "Q", "card_back": "A", "user_answer": "A"}),
        ("get_learning_advice", {"review_summary": {}}),
    ]

    @pytest.fixture
    def strands_service(self):
        """BedrockModel をモックした StrandsAIService のインスタンスを提供する."""
        with patch("services.strands_service.BedrockModel"), patch.dict("os.environ", {"ENVIRONMENT": "prod"}):
            service = StrandsAIService()
        return service

    def test_timeout_error_generate_cards(self, strands_service):
        """TC-QG-011-001: TimeoutError -> AITimeoutError (generate_cards)."""
        mock_agent = make_mock_agent("")
        mock_agent.side_effect = TimeoutError("Agent timed out")

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AITimeoutError):
                strands_service.generate_cards(input_text="test")

    def test_timeout_error_grade_answer(self, strands_service):
        """TC-QG-011-002: TimeoutError -> AITimeoutError (grade_answer)."""
        mock_agent = MagicMock()
        mock_agent.side_effect = TimeoutError("Agent timed out")

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AITimeoutError):
                strands_service.grade_answer(card_front="Q", card_back="A", user_answer="A")

    def test_timeout_error_get_learning_advice(self, strands_service):
        """TC-QG-011-003: TimeoutError -> AITimeoutError (get_learning_advice)."""
        mock_agent = MagicMock()
        mock_agent.side_effect = TimeoutError("Agent timed out")

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AITimeoutError):
                strands_service.get_learning_advice(review_summary={})

    @pytest.mark.parametrize("method_name,kwargs", _all_methods)
    def test_connection_error_raises_provider_error(self, strands_service, method_name, kwargs):
        """TC-QG-011-004: ConnectionError -> AIProviderError (全 3 メソッド)."""
        mock_agent = MagicMock()
        mock_agent.side_effect = ConnectionError("Connection refused")

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AIProviderError):
                getattr(strands_service, method_name)(**kwargs)

    @pytest.mark.parametrize("method_name,kwargs", _all_methods)
    def test_throttling_exception_raises_rate_limit_error(self, strands_service, method_name, kwargs):
        """TC-QG-011-005: botocore ThrottlingException -> AIRateLimitError (全 3 メソッド)."""
        mock_agent = MagicMock()
        mock_agent.side_effect = make_client_error("ThrottlingException")

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AIRateLimitError):
                getattr(strands_service, method_name)(**kwargs)

    @pytest.mark.parametrize("method_name,kwargs", _all_methods)
    def test_error_message_timeout_raises_ai_timeout(self, strands_service, method_name, kwargs):
        """TC-QG-011-006: エラーメッセージに "timeout" を含む例外 -> AITimeoutError (全 3 メソッド)."""
        mock_agent = MagicMock()
        mock_agent.side_effect = RuntimeError("request timeout exceeded")

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AITimeoutError):
                getattr(strands_service, method_name)(**kwargs)

    @pytest.mark.parametrize("method_name,kwargs", _all_methods)
    def test_error_message_connection_raises_provider_error(self, strands_service, method_name, kwargs):
        """TC-QG-011-007: エラーメッセージに "connection" を含む例外 -> AIProviderError (全 3 メソッド)."""
        mock_agent = MagicMock()
        mock_agent.side_effect = RuntimeError("connection reset by peer")

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AIProviderError):
                getattr(strands_service, method_name)(**kwargs)

    def test_ai_service_error_subclass_is_reraised_generate_cards(self, strands_service):
        """TC-QG-011-008: 既に AIServiceError サブクラスの例外はそのまま re-raise (generate_cards: AIParseError)."""
        invalid_response = json.dumps({"data": []})  # cards フィールド欠落
        mock_agent = make_mock_agent(invalid_response)

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AIParseError):
                strands_service.generate_cards(input_text="test")

    @pytest.mark.parametrize("method_name,kwargs", _all_methods)
    def test_unexpected_error_raises_ai_service_error(self, strands_service, method_name, kwargs):
        """TC-QG-011-009: その他の例外 -> AIServiceError("Unexpected error: ...") (全 3 メソッド)."""
        mock_agent = MagicMock()
        mock_agent.side_effect = RuntimeError("Something unexpected")

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AIServiceError) as exc_info:
                getattr(strands_service, method_name)(**kwargs)
        assert "Unexpected error" in str(exc_info.value)

    @pytest.mark.parametrize("method_name,kwargs", _all_methods)
    def test_exception_chain_preserved(self, strands_service, method_name, kwargs):
        """TC-QG-011-010: 例外チェーン (__cause__) が全 3 メソッドで保持される."""
        mock_agent = MagicMock()
        mock_agent.side_effect = ConnectionError("Connection refused")

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AIProviderError) as exc_info:
                getattr(strands_service, method_name)(**kwargs)
        assert exc_info.value.__cause__ is not None

    @pytest.mark.parametrize("method_name,kwargs", _all_methods)
    def test_timed_out_message_raises_ai_timeout_error(self, strands_service, method_name, kwargs):
        """TC-QG-011-011: エラーメッセージに "timed out" を含む例外 -> AITimeoutError (全 3 メソッド)."""
        mock_agent = MagicMock()
        mock_agent.side_effect = RuntimeError("operation timed out waiting for response")

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AITimeoutError):
                getattr(strands_service, method_name)(**kwargs)

    @pytest.mark.parametrize("method_name,kwargs", _all_methods)
    def test_connect_class_name_raises_provider_error(self, strands_service, method_name, kwargs):
        """TC-QG-011-012: 例外クラス名に "connect" を含む例外 -> AIProviderError (全 3 メソッド)."""
        mock_agent = MagicMock()
        ConnectError = type("ConnectError", (Exception,), {})
        mock_agent.side_effect = ConnectError("failed")

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AIProviderError):
                getattr(strands_service, method_name)(**kwargs)


# =============================================================================
# カテゴリ 6: BedrockService エラーハンドリング (TestBedrockErrorHandlingFinal)
# =============================================================================


class TestBedrockErrorHandlingFinal:
    """BedrockService のエラーマッピングとリトライロジック最終確認 (TC-QG-012-001 ~ TC-QG-012-006)."""

    def test_read_timeout_error_raises_bedrock_timeout(self):
        """TC-QG-012-001: ClientError "ReadTimeoutError" -> BedrockTimeoutError."""
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = make_client_error("ReadTimeoutError")
        service = BedrockService(bedrock_client=mock_client)

        with pytest.raises(BedrockTimeoutError):
            service.generate_cards(input_text="test input text")

    def test_throttling_exception_raises_bedrock_rate_limit(self):
        """TC-QG-012-002: ClientError "ThrottlingException" -> BedrockRateLimitError."""
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = make_client_error("ThrottlingException")
        service = BedrockService(bedrock_client=mock_client)

        with patch("time.sleep"):
            with pytest.raises(BedrockRateLimitError):
                service.generate_cards(input_text="test input text")

    def test_internal_server_exception_raises_bedrock_internal(self):
        """TC-QG-012-003: ClientError "InternalServerException" -> BedrockInternalError."""
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = make_client_error("InternalServerException")
        service = BedrockService(bedrock_client=mock_client)

        with patch("time.sleep"):
            with pytest.raises(BedrockInternalError):
                service.generate_cards(input_text="test input text")

    def test_rate_limit_retry_count(self):
        """TC-QG-012-004: BedrockRateLimitError に対してリトライが最大 MAX_RETRIES (2) 回実行される."""
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = make_client_error("ThrottlingException")
        service = BedrockService(bedrock_client=mock_client)

        with patch("time.sleep"):
            with pytest.raises(BedrockRateLimitError):
                service.generate_cards(input_text="test input text")

        # 【検証】: 初回 + リトライ 2 回 = 合計 3 回呼ばれることを確認
        assert mock_client.invoke_model.call_count == 3

    def test_timeout_no_retry(self):
        """TC-QG-012-005: BedrockTimeoutError に対してリトライなし (即座に raise)."""
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = make_client_error("ReadTimeoutError")
        service = BedrockService(bedrock_client=mock_client)

        with pytest.raises(BedrockTimeoutError):
            service.generate_cards(input_text="test input text")

        # 【検証】: タイムアウトはリトライしないので 1 回のみ呼ばれることを確認
        assert mock_client.invoke_model.call_count == 1

    def test_retry_jitter_within_range(self):
        """TC-QG-012-006: リトライ間隔が Full Jitter Exponential Backoff パターンに従う."""
        service = BedrockService(bedrock_client=MagicMock())

        # 【検証】: 各 attempt で複数回呼び出し、全て [0, 2^attempt] 範囲内であることを確認
        for attempt in range(3):
            for _ in range(10):
                delay = service._retry_with_jitter(attempt)
                max_delay = min(2 ** attempt, 30)
                assert 0 <= delay <= max_delay, (
                    f"attempt={attempt}: delay={delay} is not in [0, {max_delay}]"
                )

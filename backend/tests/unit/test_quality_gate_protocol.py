"""TASK-0065: 品質ゲート - Protocol準拠性 / ファクトリ / モデル選択 / 例外階層.

カテゴリ 1: Protocol 準拠性 (TC-QG-004)
カテゴリ 2: ファクトリルーティング (TC-QG-005)
カテゴリ 3: モデルプロバイダー選択 (TC-QG-006)
カテゴリ 4: 例外階層の正確性 (TC-QG-009)

🔵 信頼性: 既存 test_quality_gate.py から分割。ロジック変更なし。
"""

import asyncio
import inspect
import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from services.ai_service import (
    AIInternalError,
    AIParseError,
    AIProviderError,
    AIRateLimitError,
    AIService,
    AIServiceError,
    AITimeoutError,
    create_ai_service,
)
from services.bedrock import (
    BedrockInternalError,
    BedrockParseError,
    BedrockRateLimitError,
    BedrockService,
    BedrockServiceError,
    BedrockTimeoutError,
)
from services.strands_service import StrandsAIService


# =============================================================================
# カテゴリ 1: Protocol 準拠性 (TestProtocolComplianceFinal)
# =============================================================================


class TestProtocolComplianceFinal:
    """Protocol 準拠性の最終確認 (TC-QG-004-001 ~ TC-QG-004-012).

    StrandsAIService と BedrockService が AIService Protocol を
    正しく満たしていることを包括的に検証する。
    """

    @patch("services.strands_service.BedrockModel")
    def test_strands_isinstance_protocol(self, mock_bedrock_model):
        """TC-QG-004-001: StrandsAIService が AIService Protocol を満たす (isinstance)."""
        with patch.dict("os.environ", {"ENVIRONMENT": "prod"}):
            service = StrandsAIService()
        assert isinstance(service, AIService)

    @patch("services.bedrock.boto3")
    def test_bedrock_isinstance_protocol(self, mock_boto3):
        """TC-QG-004-002: BedrockService が AIService Protocol を満たす (isinstance)."""
        service = BedrockService(bedrock_client=MagicMock())
        assert isinstance(service, AIService)

    @patch("services.strands_service.BedrockModel")
    def test_strands_generate_cards_signature(self, mock_bedrock_model):
        """TC-QG-004-003: StrandsAIService.generate_cards() のシグネチャが Protocol と一致."""
        with patch.dict("os.environ", {"ENVIRONMENT": "prod"}):
            service = StrandsAIService()

        sig = inspect.signature(service.generate_cards)
        params = sig.parameters

        assert "input_text" in params
        assert "card_count" in params
        assert params["card_count"].default == 5
        assert "difficulty" in params
        assert params["difficulty"].default == "medium"
        assert "language" in params
        assert params["language"].default == "ja"

    @patch("services.strands_service.BedrockModel")
    def test_strands_grade_answer_signature(self, mock_bedrock_model):
        """TC-QG-004-004: StrandsAIService.grade_answer() のシグネチャが Protocol と一致."""
        with patch.dict("os.environ", {"ENVIRONMENT": "prod"}):
            service = StrandsAIService()

        sig = inspect.signature(service.grade_answer)
        params = sig.parameters

        assert "card_front" in params
        assert "card_back" in params
        assert "user_answer" in params
        assert "language" in params
        assert params["language"].default == "ja"

    @patch("services.strands_service.BedrockModel")
    def test_strands_get_learning_advice_signature(self, mock_bedrock_model):
        """TC-QG-004-005: StrandsAIService.get_learning_advice() のシグネチャが Protocol と一致."""
        with patch.dict("os.environ", {"ENVIRONMENT": "prod"}):
            service = StrandsAIService()

        sig = inspect.signature(service.get_learning_advice)
        params = sig.parameters

        assert "review_summary" in params
        assert "language" in params
        assert params["language"].default == "ja"

    def test_bedrock_generate_cards_signature(self):
        """TC-QG-004-006: BedrockService.generate_cards() のシグネチャが Protocol と一致."""
        service = BedrockService(bedrock_client=MagicMock())
        sig = inspect.signature(service.generate_cards)
        params = sig.parameters

        assert "input_text" in params
        assert "card_count" in params
        assert params["card_count"].default == 5
        assert "difficulty" in params
        assert params["difficulty"].default == "medium"
        assert "language" in params
        assert params["language"].default == "ja"

    def test_bedrock_grade_answer_signature(self):
        """TC-QG-004-007: BedrockService.grade_answer() のシグネチャが Protocol と一致."""
        service = BedrockService(bedrock_client=MagicMock())
        sig = inspect.signature(service.grade_answer)
        params = sig.parameters

        assert "card_front" in params
        assert "card_back" in params
        assert "user_answer" in params
        assert "language" in params
        assert params["language"].default == "ja"

    def test_bedrock_get_learning_advice_signature(self):
        """TC-QG-004-008: BedrockService.get_learning_advice() のシグネチャが Protocol と一致."""
        service = BedrockService(bedrock_client=MagicMock())
        sig = inspect.signature(service.get_learning_advice)
        params = sig.parameters

        assert "review_summary" in params
        assert "language" in params
        assert params["language"].default == "ja"

    @patch("services.strands_service.BedrockModel")
    def test_strands_all_methods_are_sync(self, mock_bedrock_model):
        """TC-QG-004-009: StrandsAIService の全 Protocol メソッドが同期 (非 async)."""
        with patch.dict("os.environ", {"ENVIRONMENT": "prod"}):
            service = StrandsAIService()

        assert not asyncio.iscoroutinefunction(service.generate_cards)
        assert not asyncio.iscoroutinefunction(service.grade_answer)
        assert not asyncio.iscoroutinefunction(service.get_learning_advice)

    def test_bedrock_all_methods_are_sync(self):
        """TC-QG-004-010: BedrockService の全 Protocol メソッドが同期 (非 async)."""
        service = BedrockService(bedrock_client=MagicMock())

        assert not asyncio.iscoroutinefunction(service.generate_cards)
        assert not asyncio.iscoroutinefunction(service.grade_answer)
        assert not asyncio.iscoroutinefunction(service.get_learning_advice)

    @patch("services.strands_service.BedrockModel")
    def test_strands_has_all_protocol_methods(self, mock_bedrock_model):
        """TC-QG-004-011: StrandsAIService が全 3 Protocol メソッドを持つ."""
        with patch.dict("os.environ", {"ENVIRONMENT": "prod"}):
            service = StrandsAIService()

        assert hasattr(service, "generate_cards") and callable(service.generate_cards)
        assert hasattr(service, "grade_answer") and callable(service.grade_answer)
        assert hasattr(service, "get_learning_advice") and callable(service.get_learning_advice)

    def test_bedrock_has_all_protocol_methods(self):
        """TC-QG-004-012: BedrockService が全 3 Protocol メソッドを持つ."""
        service = BedrockService(bedrock_client=MagicMock())

        assert hasattr(service, "generate_cards") and callable(service.generate_cards)
        assert hasattr(service, "grade_answer") and callable(service.grade_answer)
        assert hasattr(service, "get_learning_advice") and callable(service.get_learning_advice)


# =============================================================================
# カテゴリ 2: ファクトリルーティング (TestFactoryRoutingFinal)
# =============================================================================


class TestFactoryRoutingFinal:
    """ファクトリ関数 create_ai_service() の最終検証 (TC-QG-005-001 ~ TC-QG-005-008).

    USE_STRANDS 環境変数と明示的パラメータによるルーティングを包括的に検証する。
    """

    def test_use_strands_true_returns_strands_service(self):
        """TC-QG-005-001: USE_STRANDS=true で StrandsAIService インスタンスを返す."""
        mock_strands_module = MagicMock()
        mock_strands_cls = MagicMock()
        mock_strands_module.StrandsAIService = mock_strands_cls

        with patch.dict("os.environ", {"USE_STRANDS": "true"}):
            with patch.dict("sys.modules", {"services.strands_service": mock_strands_module}):
                create_ai_service()
                mock_strands_cls.assert_called_once()

    @patch("services.bedrock.BedrockService")
    def test_use_strands_false_returns_bedrock_service(self, mock_bedrock_cls):
        """TC-QG-005-002: USE_STRANDS=false で BedrockService インスタンスを返す."""
        mock_bedrock_cls.return_value = MagicMock()
        with patch.dict("os.environ", {"USE_STRANDS": "false"}):
            create_ai_service()
        mock_bedrock_cls.assert_called_once()

    @patch("services.bedrock.BedrockService")
    def test_use_strands_unset_returns_bedrock_service(self, mock_bedrock_cls):
        """TC-QG-005-003: USE_STRANDS 未設定でデフォルト BedrockService を返す."""
        mock_bedrock_cls.return_value = MagicMock()
        env = {k: v for k, v in os.environ.items() if k != "USE_STRANDS"}
        with patch.dict("os.environ", env, clear=True):
            create_ai_service()
        mock_bedrock_cls.assert_called_once()

    @patch("services.bedrock.BedrockService")
    def test_explicit_false_overrides_env_true(self, mock_bedrock_cls):
        """TC-QG-005-005: use_strands=False パラメータが環境変数 USE_STRANDS=true をオーバーライド."""
        mock_bedrock_cls.return_value = MagicMock()
        with patch.dict("os.environ", {"USE_STRANDS": "true"}):
            create_ai_service(use_strands=False)
        mock_bedrock_cls.assert_called_once()

    def test_explicit_true_overrides_env_false(self):
        """TC-QG-005-004: use_strands=True パラメータが環境変数 USE_STRANDS=false をオーバーライド."""
        mock_strands_module = MagicMock()
        mock_strands_cls = MagicMock()
        mock_strands_module.StrandsAIService = mock_strands_cls

        with patch.dict("os.environ", {"USE_STRANDS": "false"}):
            with patch.dict("sys.modules", {"services.strands_service": mock_strands_module}):
                create_ai_service(use_strands=True)
                mock_strands_cls.assert_called_once()

    @pytest.mark.parametrize("env_value", ["True", "TRUE", "true"])
    def test_use_strands_case_insensitive(self, env_value):
        """TC-QG-005-006: USE_STRANDS の大文字小文字不問 ("True", "TRUE", "true" 全て StrandsAIService)."""
        mock_strands_module = MagicMock()
        mock_strands_cls = MagicMock()
        mock_strands_module.StrandsAIService = mock_strands_cls

        with patch.dict("os.environ", {"USE_STRANDS": env_value}):
            with patch.dict("sys.modules", {"services.strands_service": mock_strands_module}):
                create_ai_service()
                mock_strands_cls.assert_called_once()

    @patch("services.bedrock.BedrockService", side_effect=RuntimeError("init failed"))
    def test_init_failure_raises_provider_error(self, mock_bedrock_cls):
        """TC-QG-005-007: 初期化失敗時に AIProviderError を raise."""
        with pytest.raises(AIProviderError) as exc_info:
            create_ai_service(use_strands=False)
        assert "Failed to initialize AI service" in str(exc_info.value)

    @patch("services.bedrock.BedrockService", side_effect=RuntimeError("init failed"))
    def test_init_failure_chains_original_exception(self, mock_bedrock_cls):
        """TC-QG-005-008: 初期化失敗時に元の例外がチェーンされる (__cause__)."""
        with pytest.raises(AIProviderError) as exc_info:
            create_ai_service(use_strands=False)
        assert isinstance(exc_info.value.__cause__, RuntimeError)


# =============================================================================
# カテゴリ 3: モデルプロバイダー選択 (TestModelProviderSelectionFinal)
# =============================================================================


class TestModelProviderSelectionFinal:
    """StrandsAIService._create_model() のモデルプロバイダー選択最終確認 (TC-QG-006-001 ~ TC-QG-006-008)."""

    @patch("services.strands_service.BedrockModel")
    @patch("services.strands_service.OllamaModel")
    def test_env_dev_selects_ollama(self, mock_ollama_cls, mock_bedrock_cls):
        """TC-QG-006-001: ENVIRONMENT=dev で OllamaModel が選択される."""
        with patch.dict("os.environ", {"ENVIRONMENT": "dev"}):
            StrandsAIService()
        mock_ollama_cls.assert_called_once()
        mock_bedrock_cls.assert_not_called()

    @patch("services.strands_service.BedrockModel")
    def test_env_prod_selects_bedrock(self, mock_bedrock_cls):
        """TC-QG-006-002: ENVIRONMENT=prod で BedrockModel が選択される."""
        with patch.dict("os.environ", {"ENVIRONMENT": "prod"}):
            StrandsAIService()
        mock_bedrock_cls.assert_called_once()

    @patch("services.strands_service.BedrockModel")
    def test_env_staging_selects_bedrock(self, mock_bedrock_cls):
        """TC-QG-006-003: ENVIRONMENT=staging で BedrockModel が選択される."""
        with patch.dict("os.environ", {"ENVIRONMENT": "staging"}):
            StrandsAIService()
        mock_bedrock_cls.assert_called_once()

    @patch("services.strands_service.BedrockModel")
    def test_env_unset_defaults_to_bedrock(self, mock_bedrock_cls):
        """TC-QG-006-004: ENVIRONMENT 未設定でデフォルト "prod" として BedrockModel."""
        env = {k: v for k, v in os.environ.items() if k != "ENVIRONMENT"}
        with patch.dict("os.environ", env, clear=True):
            StrandsAIService()
        mock_bedrock_cls.assert_called_once()

    @patch("services.strands_service.OllamaModel")
    def test_env_dev_ollama_host_and_model_reflected(self, mock_ollama_cls):
        """TC-QG-006-005: ENVIRONMENT=dev 時 OLLAMA_HOST / OLLAMA_MODEL 環境変数が反映される."""
        env = {"ENVIRONMENT": "dev", "OLLAMA_HOST": "http://custom:11434", "OLLAMA_MODEL": "gemma2"}
        with patch.dict("os.environ", env):
            StrandsAIService()
        mock_ollama_cls.assert_called_once_with(host="http://custom:11434", model_id="gemma2")

    @patch("services.strands_service.OllamaModel")
    def test_env_dev_ollama_host_default(self, mock_ollama_cls):
        """TC-QG-006-006: ENVIRONMENT=dev 時 OLLAMA_HOST 未設定はデフォルト http://localhost:11434."""
        env = {k: v for k, v in os.environ.items() if k not in ("OLLAMA_HOST", "OLLAMA_MODEL")}
        env["ENVIRONMENT"] = "dev"
        with patch.dict("os.environ", env, clear=True):
            StrandsAIService()
        mock_ollama_cls.assert_called_once_with(host="http://localhost:11434", model_id="llama3.2")

    @patch("services.strands_service.BedrockModel")
    def test_bedrock_model_id_env_var_reflected(self, mock_bedrock_cls):
        """TC-QG-006-007: BEDROCK_MODEL_ID 環境変数がカスタムモデル ID に反映される."""
        custom_model_id = "anthropic.claude-3-sonnet-20240229-v1:0"
        with patch.dict("os.environ", {"ENVIRONMENT": "prod", "BEDROCK_MODEL_ID": custom_model_id}):
            StrandsAIService()
        mock_bedrock_cls.assert_called_once_with(model_id=custom_model_id)

    @patch("services.strands_service.BedrockModel")
    @patch("services.strands_service.OllamaModel")
    def test_model_used_field_reflects_environment(self, mock_ollama_cls, mock_bedrock_cls):
        """TC-QG-006-008: model_used フィールドが ENVIRONMENT=dev で "strands_ollama"、それ以外で "strands_bedrock"."""
        with patch.dict("os.environ", {"ENVIRONMENT": "dev"}):
            service_dev = StrandsAIService()
        assert service_dev.model_used == "strands_ollama"

        mock_bedrock_cls.reset_mock()
        with patch.dict("os.environ", {"ENVIRONMENT": "prod"}):
            service_prod = StrandsAIService()
        assert service_prod.model_used == "strands_bedrock"


# =============================================================================
# カテゴリ 4: 例外階層の正確性 (TestExceptionHierarchyFinal)
# =============================================================================


class TestExceptionHierarchyFinal:
    """例外クラスの継承関係最終確認 (TC-QG-009-001 ~ TC-QG-009-008)."""

    @pytest.mark.parametrize(
        "exc_class",
        [AITimeoutError, AIRateLimitError, AIInternalError, AIParseError, AIProviderError],
    )
    def test_all_ai_exceptions_are_subclasses_of_ai_service_error(self, exc_class):
        """TC-QG-009-001: 全 5 共通例外が AIServiceError のサブクラス."""
        assert issubclass(exc_class, AIServiceError)

    def test_bedrock_timeout_error_multiple_inheritance(self):
        """TC-QG-009-002: BedrockTimeoutError が BedrockServiceError と AITimeoutError の両方のサブクラス."""
        assert issubclass(BedrockTimeoutError, BedrockServiceError)
        assert issubclass(BedrockTimeoutError, AITimeoutError)

    def test_bedrock_rate_limit_error_multiple_inheritance(self):
        """TC-QG-009-003: BedrockRateLimitError が BedrockServiceError と AIRateLimitError の両方のサブクラス."""
        assert issubclass(BedrockRateLimitError, BedrockServiceError)
        assert issubclass(BedrockRateLimitError, AIRateLimitError)

    def test_bedrock_internal_error_multiple_inheritance(self):
        """TC-QG-009-004: BedrockInternalError が BedrockServiceError と AIInternalError の両方のサブクラス."""
        assert issubclass(BedrockInternalError, BedrockServiceError)
        assert issubclass(BedrockInternalError, AIInternalError)

    def test_bedrock_parse_error_multiple_inheritance(self):
        """TC-QG-009-005: BedrockParseError が BedrockServiceError と AIParseError の両方のサブクラス."""
        assert issubclass(BedrockParseError, BedrockServiceError)
        assert issubclass(BedrockParseError, AIParseError)

    @pytest.mark.parametrize(
        "exc_class",
        [BedrockTimeoutError, BedrockRateLimitError, BedrockInternalError, BedrockParseError],
    )
    def test_bedrock_exceptions_caught_by_ai_service_error(self, exc_class):
        """TC-QG-009-006: 各 Bedrock 例外が AIServiceError で catch 可能."""
        with pytest.raises(AIServiceError):
            raise exc_class("test error")

    def test_bedrock_service_error_is_subclass_of_ai_service_error(self):
        """TC-QG-009-007: BedrockServiceError 自体が AIServiceError のサブクラス."""
        assert issubclass(BedrockServiceError, AIServiceError)

    def test_ai_service_error_is_subclass_of_exception(self):
        """TC-QG-009-008: AIServiceError が Exception のサブクラス."""
        assert issubclass(AIServiceError, Exception)

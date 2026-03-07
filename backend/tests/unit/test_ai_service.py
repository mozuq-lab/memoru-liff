"""AIService Protocol、共通型定義、例外階層のテスト.

TASK-0053: AIService Protocol + 共通型定義 + 例外階層
"""
import asyncio
import inspect
import os
import sys
from dataclasses import fields
from typing import get_args, get_type_hints
from unittest.mock import MagicMock, patch

import pytest

# Import will fail until implementation exists
from services.ai_service import (
    AIService,
    GeneratedCard,
    GenerationResult,
    GradingResult,
    LearningAdvice,
    ReviewSummary,
    DifficultyLevel,
    Language,
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIInternalError,
    AIParseError,
    AIProviderError,
    create_ai_service,
)


class TestAIServiceProtocol:
    """AIService Protocol テスト."""

    def test_protocol_has_required_methods(self):
        """TC-PROTO-001: Protocol は 4 つの必須メソッドを持つ."""
        assert hasattr(AIService, "generate_cards")
        assert hasattr(AIService, "grade_answer")
        assert hasattr(AIService, "get_learning_advice")
        assert hasattr(AIService, "refine_card")

    def test_protocol_is_runtime_checkable(self):
        """TC-PROTO-002: Protocol は runtime_checkable である."""

        class _ConformingService:
            def generate_cards(self, input_text, card_count=5, difficulty="medium", language="ja"):
                pass

            def grade_answer(self, card_front, card_back, user_answer, language="ja"):
                pass

            def get_learning_advice(self, review_summary, language="ja"):
                pass

            def refine_card(self, front, back, language="ja"):
                pass

            def generate_cards_from_chunks(self, chunks, card_type="qa", target_count=10, difficulty="medium", language="ja", page_title=""):
                pass

        assert isinstance(_ConformingService(), AIService)

    def test_non_conforming_class_fails_isinstance(self):
        """TC-PROTO-003: Protocol を満たさないクラスは isinstance チェックに失敗する."""

        class _NonConformingService:
            def generate_cards(self, input_text):
                pass
            # grade_answer, get_learning_advice が欠けている

        assert not isinstance(_NonConformingService(), AIService)

    def test_protocol_methods_are_sync(self):
        """TC-PROTO-004: Protocol メソッドは同期（非 async）である."""
        assert not asyncio.iscoroutinefunction(AIService.generate_cards)
        assert not asyncio.iscoroutinefunction(AIService.grade_answer)
        assert not asyncio.iscoroutinefunction(AIService.get_learning_advice)

    def test_generate_cards_signature(self):
        """TC-PROTO-005: generate_cards メソッドシグネチャが期待通りである."""
        sig = inspect.signature(AIService.generate_cards)
        params = sig.parameters

        assert "self" in params
        assert "input_text" in params
        assert "card_count" in params
        assert params["card_count"].default == 5
        assert "difficulty" in params
        assert params["difficulty"].default == "medium"
        assert "language" in params
        assert params["language"].default == "ja"

    def test_grade_answer_signature(self):
        """TC-PROTO-006: grade_answer メソッドシグネチャが期待通りである."""
        sig = inspect.signature(AIService.grade_answer)
        params = sig.parameters

        assert "self" in params
        assert "card_front" in params
        assert "card_back" in params
        assert "user_answer" in params
        assert "language" in params
        assert params["language"].default == "ja"

    def test_get_learning_advice_signature(self):
        """TC-PROTO-007: get_learning_advice メソッドシグネチャが期待通りである."""
        sig = inspect.signature(AIService.get_learning_advice)
        params = sig.parameters

        assert "self" in params
        assert "review_summary" in params
        assert "language" in params
        assert params["language"].default == "ja"


class TestDataClasses:
    """データクラステスト."""

    def test_generated_card_required_fields_only(self):
        """TC-DATA-001: GeneratedCard - 必須フィールドのみで作成."""
        card = GeneratedCard(front="Q", back="A")
        assert card.front == "Q"
        assert card.back == "A"
        assert card.suggested_tags == []

    def test_generated_card_with_all_fields(self):
        """TC-DATA-002: GeneratedCard - 全フィールド指定で作成."""
        card = GeneratedCard(front="Q", back="A", suggested_tags=["tag1", "tag2"])
        assert card.suggested_tags == ["tag1", "tag2"]

    def test_generation_result_creation(self):
        """TC-DATA-003: GenerationResult - 全フィールド指定で作成."""
        card = GeneratedCard(front="Q", back="A")
        result = GenerationResult(
            cards=[card],
            input_length=100,
            model_used="bedrock",
            processing_time_ms=1500,
        )
        assert len(result.cards) == 1
        assert isinstance(result.cards[0], GeneratedCard)
        assert result.input_length == 100
        assert result.model_used == "bedrock"
        assert result.processing_time_ms == 1500

    def test_grading_result_creation(self):
        """TC-DATA-004: GradingResult - 全フィールド指定で作成."""
        result = GradingResult(
            grade=4,
            reasoning="Correct",
            model_used="bedrock",
            processing_time_ms=500,
        )
        assert result.grade == 4
        assert result.reasoning == "Correct"
        assert result.model_used == "bedrock"
        assert result.processing_time_ms == 500

    def test_grading_result_grade_is_int(self):
        """TC-DATA-005: GradingResult - grade は int 型である."""
        result = GradingResult(
            grade=3,
            reasoning="OK",
            model_used="bedrock",
            processing_time_ms=100,
        )
        assert isinstance(result.grade, int)

    def test_learning_advice_creation(self):
        """TC-DATA-006: LearningAdvice - 全フィールド指定で作成."""
        advice = LearningAdvice(
            advice_text="Focus on verbs",
            weak_areas=["verb_conjugation"],
            recommendations=["Practice daily"],
            model_used="bedrock",
            processing_time_ms=1000,
        )
        assert advice.advice_text == "Focus on verbs"
        assert advice.weak_areas == ["verb_conjugation"]
        assert advice.recommendations == ["Practice daily"]
        assert advice.model_used == "bedrock"
        assert advice.processing_time_ms == 1000

    def test_learning_advice_lists(self):
        """TC-DATA-007: LearningAdvice - weak_areas と recommendations はリスト型."""
        advice = LearningAdvice(
            advice_text="Study more",
            weak_areas=["math"],
            recommendations=["Review notes"],
            model_used="bedrock",
            processing_time_ms=200,
        )
        assert isinstance(advice.weak_areas, list)
        assert isinstance(advice.recommendations, list)

    def test_review_summary_required_fields_only(self):
        """TC-DATA-008: ReviewSummary - 必須フィールドのみで作成."""
        summary = ReviewSummary(
            total_reviews=100,
            average_grade=3.5,
            total_cards=50,
            cards_due_today=10,
            streak_days=7,
        )
        assert summary.tag_performance == {}
        assert summary.recent_review_dates == []

    def test_review_summary_with_all_fields(self):
        """TC-DATA-009: ReviewSummary - 全フィールド指定で作成."""
        summary = ReviewSummary(
            total_reviews=100,
            average_grade=3.5,
            total_cards=50,
            cards_due_today=10,
            streak_days=7,
            tag_performance={"math": 0.8, "science": 0.6},
            recent_review_dates=["2026-02-23", "2026-02-22"],
        )
        assert summary.tag_performance == {"math": 0.8, "science": 0.6}
        assert isinstance(summary.tag_performance, dict)
        assert summary.recent_review_dates == ["2026-02-23", "2026-02-22"]

    def test_generated_card_mutable_default_independence(self):
        """TC-DATA-010: GeneratedCard - ミュータブルデフォルトの独立性."""
        card1 = GeneratedCard(front="Q1", back="A1")
        card2 = GeneratedCard(front="Q2", back="A2")
        card1.suggested_tags.append("tag1")
        assert card2.suggested_tags == []
        assert card1.suggested_tags == ["tag1"]

    def test_review_summary_mutable_default_independence(self):
        """TC-DATA-011: ReviewSummary - tag_performance ミュータブルデフォルトの独立性."""
        summary1 = ReviewSummary(
            total_reviews=10, average_grade=3.0, total_cards=5, cards_due_today=2, streak_days=1
        )
        summary2 = ReviewSummary(
            total_reviews=20, average_grade=4.0, total_cards=10, cards_due_today=3, streak_days=2
        )
        summary1.tag_performance["math"] = 0.9
        assert summary2.tag_performance == {}

    def test_review_summary_recent_dates_mutable_default_independence(self):
        """TC-DATA-012: ReviewSummary - recent_review_dates ミュータブルデフォルトの独立性."""
        summary1 = ReviewSummary(
            total_reviews=10, average_grade=3.0, total_cards=5, cards_due_today=2, streak_days=1
        )
        summary2 = ReviewSummary(
            total_reviews=20, average_grade=4.0, total_cards=10, cards_due_today=3, streak_days=2
        )
        summary1.recent_review_dates.append("2026-02-23")
        assert summary2.recent_review_dates == []


class TestExceptionHierarchy:
    """例外階層テスト."""

    def test_ai_service_error_is_exception_subclass(self):
        """TC-EXC-001: AIServiceError は Exception のサブクラス."""
        assert issubclass(AIServiceError, Exception)

    @pytest.mark.parametrize(
        "exc_class",
        [
            AITimeoutError,
            AIRateLimitError,
            AIInternalError,
            AIParseError,
            AIProviderError,
        ],
    )
    def test_all_child_exceptions_are_subclasses(self, exc_class):
        """TC-EXC-002: 全 5 子例外は AIServiceError のサブクラス."""
        assert issubclass(exc_class, AIServiceError)

    @pytest.mark.parametrize(
        "exc_class",
        [
            AITimeoutError,
            AIRateLimitError,
            AIInternalError,
            AIParseError,
            AIProviderError,
        ],
    )
    def test_child_exceptions_caught_by_base(self, exc_class):
        """TC-EXC-003: 各子例外は AIServiceError で catch できる."""
        with pytest.raises(AIServiceError):
            raise exc_class("test error")

    @pytest.mark.parametrize(
        "exc_class",
        [
            AITimeoutError,
            AIRateLimitError,
            AIInternalError,
            AIParseError,
            AIProviderError,
        ],
    )
    def test_child_exceptions_caught_by_own_type(self, exc_class):
        """TC-EXC-004: 各子例外は自身の型で catch できる."""
        with pytest.raises(exc_class):
            raise exc_class("test error")

    @pytest.mark.parametrize(
        "exc_class,message",
        [
            (AITimeoutError, "Request timed out after 30s"),
            (AIRateLimitError, "Too many requests"),
            (AIInternalError, "Internal server error"),
            (AIParseError, "Failed to parse response"),
            (AIProviderError, "Provider initialization failed"),
        ],
    )
    def test_exception_message_preserved(self, exc_class, message):
        """TC-EXC-005: 例外メッセージが保持される."""
        with pytest.raises(AIServiceError) as exc_info:
            raise exc_class(message)
        assert str(exc_info.value) == message

    def test_base_exception_can_be_raised(self):
        """TC-EXC-006: AIServiceError 自体もインスタンス化・送出できる."""
        with pytest.raises(Exception):
            raise AIServiceError("base error")


class TestCreateAIService:
    """ファクトリ関数テスト."""

    @patch.dict("os.environ", {"USE_STRANDS": "false"})
    @patch("services.bedrock.BedrockService")
    def test_create_with_use_strands_false_env(self, mock_bedrock_cls):
        """TC-FACT-001: USE_STRANDS=false で BedrockAIService を返却."""
        mock_bedrock_cls.return_value = MagicMock()
        result = create_ai_service()
        mock_bedrock_cls.assert_called_once()
        assert result == mock_bedrock_cls.return_value

    def test_create_with_use_strands_true_env(self):
        """TC-FACT-002: USE_STRANDS=true で StrandsAIService を返却."""
        mock_strands_module = MagicMock()
        mock_strands_cls = MagicMock()
        mock_strands_module.StrandsAIService = mock_strands_cls

        with patch.dict("os.environ", {"USE_STRANDS": "true"}):
            with patch.dict("sys.modules", {"services.strands_service": mock_strands_module}):
                result = create_ai_service()
                mock_strands_cls.assert_called_once()
                assert result == mock_strands_cls.return_value

    @patch.dict("os.environ", {}, clear=True)
    @patch("services.bedrock.BedrockService")
    def test_create_default_without_env_var(self, mock_bedrock_cls):
        """TC-FACT-003: USE_STRANDS 未設定時はデフォルトで BedrockAIService."""
        os.environ.pop("USE_STRANDS", None)
        mock_bedrock_cls.return_value = MagicMock()
        result = create_ai_service()
        mock_bedrock_cls.assert_called_once()

    @patch.dict("os.environ", {"USE_STRANDS": "true"})
    @patch("services.bedrock.BedrockService")
    def test_create_explicit_false_overrides_env(self, mock_bedrock_cls):
        """TC-FACT-004: use_strands=False 明示パラメータが環境変数をオーバーライド."""
        mock_bedrock_cls.return_value = MagicMock()
        result = create_ai_service(use_strands=False)
        mock_bedrock_cls.assert_called_once()

    def test_create_explicit_true_overrides_env(self):
        """TC-FACT-005: use_strands=True 明示パラメータが環境変数をオーバーライド."""
        mock_strands_module = MagicMock()
        mock_strands_cls = MagicMock()
        mock_strands_module.StrandsAIService = mock_strands_cls

        with patch.dict("os.environ", {"USE_STRANDS": "false"}):
            with patch.dict("sys.modules", {"services.strands_service": mock_strands_module}):
                result = create_ai_service(use_strands=True)
                mock_strands_cls.assert_called_once()

    @patch("services.bedrock.BedrockService", side_effect=RuntimeError("init failed"))
    def test_create_raises_provider_error_on_init_failure(self, mock_bedrock_cls):
        """TC-FACT-006: 初期化失敗時に AIProviderError を送出."""
        with pytest.raises(AIProviderError) as exc_info:
            create_ai_service(use_strands=False)
        assert "Failed to initialize AI service" in str(exc_info.value)

    @patch("services.bedrock.BedrockService", side_effect=RuntimeError("init failed"))
    def test_create_chains_original_exception(self, mock_bedrock_cls):
        """TC-FACT-007: 初期化失敗時に元の例外がチェーンされる."""
        with pytest.raises(AIProviderError) as exc_info:
            create_ai_service(use_strands=False)
        assert isinstance(exc_info.value.__cause__, RuntimeError)

    @pytest.mark.parametrize("env_value", ["True", "TRUE", "true"])
    def test_create_env_case_insensitive_true(self, env_value):
        """TC-FACT-008: USE_STRANDS の大文字小文字不問（"True", "TRUE"）."""
        mock_strands_module = MagicMock()
        mock_strands_cls = MagicMock()
        mock_strands_module.StrandsAIService = mock_strands_cls

        with patch.dict("os.environ", {"USE_STRANDS": env_value}):
            with patch.dict("sys.modules", {"services.strands_service": mock_strands_module}):
                result = create_ai_service()
                mock_strands_cls.assert_called_once()


class TestTypeAliases:
    """型定義テスト."""

    def test_difficulty_level_values(self):
        """TC-TYPE-001: DifficultyLevel は "easy", "medium", "hard" の 3 値."""
        assert set(get_args(DifficultyLevel)) == {"easy", "medium", "hard"}

    def test_language_values(self):
        """TC-TYPE-002: Language は "ja", "en" の 2 値."""
        assert set(get_args(Language)) == {"ja", "en"}

    def test_difficulty_level_does_not_include_intermediate(self):
        """TC-TYPE-003: DifficultyLevel は "intermediate" を含まない."""
        assert "intermediate" not in get_args(DifficultyLevel)

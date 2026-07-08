"""Unit tests for services/ai_job_executors.py (ai-async-jobs).

AI 系エンドポイントが「202 + job_id を返す submit」に変換されたため、
旧同期ハンドラーテストが検証していた以下の観点を executor レベルに移設した:

- レスポンス形状（result dict が現行同期レスポンスと同一スキーマであること）
- AI サービスファクトリ（create_ai_service）の使用と引数伝播
- AI 例外がそのまま伝播すること（HTTP ステータスへの分類は
  tests/unit/test_ai_job_errors.py の classify_ai_job_error テストが担保する）

移設元:
- tests/unit/test_handler_grade_ai.py（カテゴリ E/F/G: AI 呼び出し・レスポンス・AI エラー）
- tests/unit/test_handler_advice.py（カテゴリ B/C/D: データフロー・レスポンス・AI エラー）
- tests/unit/test_handler_refine.py（正常系レスポンス・AI エラー）
- tests/unit/api/handlers/test_ai_handler.py（generate-from-url の重複警告）
- tests/unit/test_handler_ai_service_factory.py（カテゴリ A/C: ファクトリ統合・互換性）
- tests/unit/test_tutor_handler.py（tutor_start / tutor_message 正常系）
"""

import dataclasses
from unittest.mock import MagicMock, patch

import pytest

from models.tutor import SendMessageResponse, TutorMessage, TutorSessionResponse
from services.ai_job_errors import NoCardsGeneratedError, classify_ai_job_error
from services.ai_job_executors import (
    EXECUTORS,
    HEAVY_JOB_TYPES,
    execute_advice,
    execute_generate,
    execute_generate_from_url,
    execute_grade_ai,
    execute_refine,
    execute_tutor_message,
    execute_tutor_start,
)
from services.ai_service import (
    AIInternalError,
    AIParseError,
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
    GeneratedCard,
    GenerationResult,
    GradingResult,
    LearningAdvice,
    RefineResult,
    ReviewSummary,
)
from services.card_service import CardNotFoundError

# 旧同期ハンドラーの AI 例外 → HTTP ステータス対応（map_ai_error_to_http と同一）。
# executor では例外がそのまま伝播し、classify_ai_job_error が同じステータスに
# 分類することで、旧テストのエラーマッピング検証を引き継ぐ。
AI_ERROR_STATUS_CASES = [
    (AITimeoutError("timeout"), 504),
    (AIRateLimitError("rate limit"), 429),
    (AIProviderError("provider down"), 503),
    (AIParseError("invalid json"), 500),
    (AIInternalError("internal failure"), 500),
]


def _make_generation_result() -> GenerationResult:
    return GenerationResult(
        cards=[
            GeneratedCard(front="Q1", back="A1", suggested_tags=["tag1"]),
            GeneratedCard(front="Q2", back="A2", suggested_tags=["tag1", "tag2"]),
        ],
        input_length=64,
        model_used="test-model",
        processing_time_ms=1200,
    )


# =============================================================================
# execute_generate（旧 POST /cards/generate 同期実装相当）
# =============================================================================


class TestExecuteGenerate:
    """create_ai_service ファクトリ経由の生成と GenerateCardsResponse 形状を検証。"""

    PAYLOAD = {
        "input_text": "量子力学の基礎について学びましょう。原子の構造と電子の振る舞い。",
        "card_count": 5,
        "difficulty": "hard",
        "language": "en",
    }

    def test_calls_create_ai_service_factory_once(self):
        """旧 TC-056-001: create_ai_service() ファクトリが 1 回呼ばれる。"""
        with patch("services.ai_job_executors.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.generate_cards.return_value = _make_generation_result()
            mock_factory.return_value = mock_service

            execute_generate("user-1", dict(self.PAYLOAD))

        mock_factory.assert_called_once()

    def test_passes_correct_args_to_generate_cards(self):
        """旧 TC-056-002: payload の各パラメータが generate_cards に伝播する。"""
        with patch("services.ai_job_executors.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.generate_cards.return_value = _make_generation_result()
            mock_factory.return_value = mock_service

            execute_generate("user-1", dict(self.PAYLOAD))

        mock_service.generate_cards.assert_called_once_with(
            input_text=self.PAYLOAD["input_text"],
            card_count=5,
            difficulty="hard",
            language="en",
        )

    def test_result_shape_matches_generate_cards_response(self):
        """旧 TC-056-010: result が GenerateCardsResponse と同一形状であること。"""
        with patch("services.ai_job_executors.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.generate_cards.return_value = _make_generation_result()
            mock_factory.return_value = mock_service

            result = execute_generate("user-1", dict(self.PAYLOAD))

        assert result == {
            "generated_cards": [
                {"front": "Q1", "back": "A1", "suggested_tags": ["tag1"]},
                {"front": "Q2", "back": "A2", "suggested_tags": ["tag1", "tag2"]},
            ],
            "generation_info": {
                "input_length": 64,
                "model_used": "test-model",
                "processing_time_ms": 1200,
            },
        }

    @pytest.mark.parametrize("error,expected_status", AI_ERROR_STATUS_CASES)
    def test_ai_errors_propagate_and_classify_to_old_status(self, error, expected_status):
        """旧 TC-056-011〜013: AI 例外はそのまま伝播し、classify で旧ステータスになる。"""
        with patch("services.ai_job_executors.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.generate_cards.side_effect = error
            mock_factory.return_value = mock_service

            with pytest.raises(type(error)) as exc_info:
                execute_generate("user-1", dict(self.PAYLOAD))

        assert classify_ai_job_error(exc_info.value).status == expected_status

    def test_factory_init_failure_propagates_as_provider_error(self):
        """旧 TC-056-013: create_ai_service() 自体の初期化失敗（503 相当）も伝播する。"""
        with patch("services.ai_job_executors.create_ai_service") as mock_factory:
            mock_factory.side_effect = AIProviderError("Failed to initialize AI service")

            with pytest.raises(AIProviderError) as exc_info:
                execute_generate("user-1", dict(self.PAYLOAD))

        assert classify_ai_job_error(exc_info.value).status == 503


# =============================================================================
# execute_refine（旧 POST /cards/refine 同期実装相当）
# =============================================================================


class TestExecuteRefine:
    """RefineCardResponse 形状と AI 例外伝播を検証（旧 test_handler_refine.py）。"""

    PAYLOAD = {"front": "クロージャとは？", "back": "変数を覚えてる関数", "language": "ja"}

    def test_result_shape_matches_refine_card_response(self):
        with patch("services.ai_job_executors.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.refine_card.return_value = RefineResult(
                refined_front="クロージャとは何か？",
                refined_back="外部スコープの変数を参照し続ける関数。",
                model_used="strands_bedrock",
                processing_time_ms=1200,
            )
            mock_factory.return_value = mock_service

            result = execute_refine("user-1", dict(self.PAYLOAD))

        assert result == {
            "refined_front": "クロージャとは何か？",
            "refined_back": "外部スコープの変数を参照し続ける関数。",
            "model_used": "strands_bedrock",
            "processing_time_ms": 1200,
        }

    def test_front_only_refine_returns_empty_back(self):
        """表面のみの改善でも空 back を保ったまま成功する（旧 front_only テスト）。"""
        with patch("services.ai_job_executors.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.refine_card.return_value = RefineResult(
                refined_front="クロージャとは何か？",
                refined_back="",
                model_used="strands_bedrock",
                processing_time_ms=800,
            )
            mock_factory.return_value = mock_service

            result = execute_refine(
                "user-1", {"front": "クロージャ", "back": "", "language": "ja"}
            )

        assert result["refined_front"] == "クロージャとは何か？"
        assert result["refined_back"] == ""

    def test_passes_args_to_refine_card(self):
        with patch("services.ai_job_executors.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.refine_card.return_value = RefineResult(
                refined_front="f", refined_back="b", model_used="m", processing_time_ms=1
            )
            mock_factory.return_value = mock_service

            execute_refine("user-1", dict(self.PAYLOAD))

        mock_service.refine_card.assert_called_once_with(
            front="クロージャとは？", back="変数を覚えてる関数", language="ja"
        )

    @pytest.mark.parametrize("error,expected_status", AI_ERROR_STATUS_CASES)
    def test_ai_errors_propagate_and_classify_to_old_status(self, error, expected_status):
        """旧 TestRefineCardAIErrors: 504/429/503/500 の分類を classify で引き継ぐ。"""
        with patch("services.ai_job_executors.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.refine_card.side_effect = error
            mock_factory.return_value = mock_service

            with pytest.raises(type(error)) as exc_info:
                execute_refine("user-1", dict(self.PAYLOAD))

        assert classify_ai_job_error(exc_info.value).status == expected_status


# =============================================================================
# execute_grade_ai（旧 POST /reviews/{cardId}/grade-ai 同期実装相当）
# =============================================================================


class TestExecuteGradeAi:
    """GradeAnswerResponse 形状・カード取得・AI 例外伝播を検証。

    移設元: test_handler_grade_ai.py カテゴリ D/E/F/G。
    """

    PAYLOAD = {"card_id": "card-123", "user_answer": "東京", "language": "ja"}

    def _mock_services(self, card_front="日本の首都は？", card_back="東京"):
        mock_card = MagicMock()
        mock_card.front = card_front
        mock_card.back = card_back
        card_service_cls = patch("services.ai_job_executors.CardService")
        factory = patch("services.ai_job_executors.create_ai_service")
        return card_service_cls, factory, mock_card

    def test_result_shape_matches_grade_answer_response(self):
        """旧 TC-060-RES-002〜005: grade / reasoning / card_front / card_back / grading_info。"""
        card_cls, factory, mock_card = self._mock_services(
            card_front="フランスの首都は？", card_back="パリ"
        )
        with card_cls as mock_card_cls, factory as mock_factory:
            mock_card_cls.return_value.get_card.return_value = mock_card
            mock_service = MagicMock()
            mock_service.grade_answer.return_value = GradingResult(
                grade=5,
                reasoning="Perfect match",
                model_used="claude-3-haiku",
                processing_time_ms=350,
            )
            mock_factory.return_value = mock_service

            result = execute_grade_ai(
                "e2e-user", {"card_id": "e2e-card", "user_answer": "パリ", "language": "ja"}
            )

        assert result == {
            "grade": 5,
            "reasoning": "Perfect match",
            "card_front": "フランスの首都は？",
            "card_back": "パリ",
            "grading_info": {
                "model_used": "claude-3-haiku",
                "processing_time_ms": 350,
            },
        }

    def test_fetches_card_with_user_and_card_id(self):
        """旧 TC-060-AUTH-003/PATH-001: user_id / card_id が get_card に渡る。"""
        card_cls, factory, mock_card = self._mock_services()
        with card_cls as mock_card_cls, factory as mock_factory:
            mock_card_cls.return_value.get_card.return_value = mock_card
            mock_service = MagicMock()
            mock_service.grade_answer.return_value = GradingResult(
                grade=4, reasoning="ok", model_used="m", processing_time_ms=1
            )
            mock_factory.return_value = mock_service

            execute_grade_ai(
                "user-abc-123",
                {"card_id": "card-xyz-789", "user_answer": "東京", "language": "ja"},
            )

        mock_card_cls.return_value.get_card.assert_called_once_with(
            "user-abc-123", "card-xyz-789"
        )

    def test_passes_card_front_back_and_language_to_grade_answer(self):
        """旧 TC-060-CARD-002/AI-002/AI-003: カード内容と language の伝播。"""
        card_cls, factory, mock_card = self._mock_services()
        with card_cls as mock_card_cls, factory as mock_factory:
            mock_card_cls.return_value.get_card.return_value = mock_card
            mock_service = MagicMock()
            mock_service.grade_answer.return_value = GradingResult(
                grade=4, reasoning="ok", model_used="m", processing_time_ms=1
            )
            mock_factory.return_value = mock_service

            execute_grade_ai(
                "user-1", {"card_id": "card-123", "user_answer": "Tokyo", "language": "en"}
            )

        mock_service.grade_answer.assert_called_once_with(
            card_front="日本の首都は？",
            card_back="東京",
            user_answer="Tokyo",
            language="en",
        )

    def test_card_not_found_propagates_and_classifies_to_404(self):
        """旧 TC-060-CARD-001/003: submit 後にカードが消えた場合は failed(404) になる。"""
        card_cls, factory, _ = self._mock_services()
        with card_cls as mock_card_cls, factory:
            mock_card_cls.return_value.get_card.side_effect = CardNotFoundError(
                "Card not found"
            )

            with pytest.raises(CardNotFoundError) as exc_info:
                execute_grade_ai("user-1", dict(self.PAYLOAD))

        job_error = classify_ai_job_error(exc_info.value)
        assert job_error.status == 404
        assert job_error.message == "Not Found"

    @pytest.mark.parametrize("error,expected_status", AI_ERROR_STATUS_CASES)
    def test_ai_errors_propagate_and_classify_to_old_status(self, error, expected_status):
        """旧 TC-060-ERR-001〜005: AI 例外の旧ステータス分類を classify で引き継ぐ。"""
        card_cls, factory, mock_card = self._mock_services()
        with card_cls as mock_card_cls, factory as mock_factory:
            mock_card_cls.return_value.get_card.return_value = mock_card
            mock_service = MagicMock()
            mock_service.grade_answer.side_effect = error
            mock_factory.return_value = mock_service

            with pytest.raises(type(error)) as exc_info:
                execute_grade_ai("user-1", dict(self.PAYLOAD))

        assert classify_ai_job_error(exc_info.value).status == expected_status

    def test_factory_init_failure_propagates_as_provider_error(self):
        """旧 TC-060-ERR-006: ファクトリ初期化失敗（503 相当）も伝播する。"""
        card_cls, factory, mock_card = self._mock_services()
        with card_cls as mock_card_cls, factory as mock_factory:
            mock_card_cls.return_value.get_card.return_value = mock_card
            mock_factory.side_effect = AIProviderError("Failed to initialize AI service")

            with pytest.raises(AIProviderError) as exc_info:
                execute_grade_ai("user-1", dict(self.PAYLOAD))

        assert classify_ai_job_error(exc_info.value).status == 503


# =============================================================================
# execute_advice（旧 GET /advice 同期実装相当）
# =============================================================================


class TestExecuteAdvice:
    """LearningAdviceResponse 形状・データフロー・AI 例外伝播を検証。

    移設元: test_handler_advice.py カテゴリ B/C/D。
    """

    PAYLOAD = {"language": "ja"}

    def _make_summary(self, **overrides) -> ReviewSummary:
        values = dict(
            total_reviews=100,
            average_grade=3.5,
            total_cards=50,
            cards_due_today=10,
            streak_days=5,
            tag_performance={"math": 0.8, "science": 0.6},
            recent_review_dates=["2026-02-24", "2026-02-23"],
        )
        values.update(overrides)
        return ReviewSummary(**values)

    def _patches(self):
        return (
            patch("services.ai_job_executors.UserService"),
            patch("services.ai_job_executors.ReviewService"),
            patch("services.ai_job_executors.create_ai_service"),
        )

    def _make_advice(self) -> LearningAdvice:
        return LearningAdvice(
            advice_text="数学の復習頻度を上げましょう。",
            weak_areas=["数学", "物理"],
            recommendations=["毎日10枚のカードを復習する", "弱点タグを重点的に復習"],
            model_used="test-model",
            processing_time_ms=800,
        )

    def test_result_shape_matches_learning_advice_response(self):
        """旧 TC-062-RES-002〜006: advice_text / weak_areas / recommendations /
        study_stats / advice_info の全フィールド。"""
        user_cls, review_cls, factory = self._patches()
        with user_cls as mock_user_cls, review_cls as mock_review_cls, factory as mock_factory:
            mock_user_cls.return_value.get_or_create_user.return_value.settings = {
                "timezone": "Asia/Tokyo"
            }
            mock_review_cls.return_value.get_review_summary.return_value = (
                self._make_summary()
            )
            mock_service = MagicMock()
            mock_service.get_learning_advice.return_value = self._make_advice()
            mock_factory.return_value = mock_service

            result = execute_advice("user-1", dict(self.PAYLOAD))

        assert result == {
            "advice_text": "数学の復習頻度を上げましょう。",
            "weak_areas": ["数学", "物理"],
            "recommendations": ["毎日10枚のカードを復習する", "弱点タグを重点的に復習"],
            "study_stats": {
                "total_reviews": 100,
                "average_grade": 3.5,
                "total_cards": 50,
                "cards_due_today": 10,
                "streak_days": 5,
            },
            "advice_info": {
                "model_used": "test-model",
                "processing_time_ms": 800,
            },
        }

    def test_uses_user_timezone_for_review_summary(self):
        """旧 TC-062-AUTH-003/FLOW-001: ユーザー設定の timezone で集計する。"""
        user_cls, review_cls, factory = self._patches()
        with user_cls as mock_user_cls, review_cls as mock_review_cls, factory as mock_factory:
            mock_user_cls.return_value.get_or_create_user.return_value.settings = {
                "timezone": "America/New_York"
            }
            mock_review_cls.return_value.get_review_summary.return_value = (
                self._make_summary()
            )
            mock_service = MagicMock()
            mock_service.get_learning_advice.return_value = self._make_advice()
            mock_factory.return_value = mock_service

            execute_advice("user-abc-123", dict(self.PAYLOAD))

        mock_user_cls.return_value.get_or_create_user.assert_called_once_with(
            "user-abc-123"
        )
        mock_review_cls.return_value.get_review_summary.assert_called_once_with(
            "user-abc-123", user_timezone="America/New_York"
        )

    def test_passes_review_summary_dict_and_language_to_ai_service(self):
        """旧 TC-062-FLOW-002〜004: ReviewSummary が dict 化され language と共に渡る。"""
        user_cls, review_cls, factory = self._patches()
        with user_cls as mock_user_cls, review_cls as mock_review_cls, factory as mock_factory:
            mock_user_cls.return_value.get_or_create_user.return_value.settings = {}
            summary = self._make_summary()
            mock_review_cls.return_value.get_review_summary.return_value = summary
            mock_service = MagicMock()
            mock_service.get_learning_advice.return_value = self._make_advice()
            mock_factory.return_value = mock_service

            execute_advice("user-1", {"language": "en"})

        mock_factory.assert_called_once()
        call_kwargs = mock_service.get_learning_advice.call_args.kwargs
        assert call_kwargs["review_summary"] == dataclasses.asdict(summary)
        assert call_kwargs["review_summary"]["total_reviews"] == 100
        assert call_kwargs["review_summary"]["average_grade"] == 3.5
        assert call_kwargs["language"] == "en"

    def test_works_with_empty_review_summary(self):
        """旧 TC-062-DB-002: 全ゼロの ReviewSummary でも成功する。"""
        user_cls, review_cls, factory = self._patches()
        with user_cls as mock_user_cls, review_cls as mock_review_cls, factory as mock_factory:
            mock_user_cls.return_value.get_or_create_user.return_value.settings = {}
            mock_review_cls.return_value.get_review_summary.return_value = ReviewSummary(
                total_reviews=0,
                average_grade=0.0,
                total_cards=0,
                cards_due_today=0,
                streak_days=0,
            )
            mock_service = MagicMock()
            mock_service.get_learning_advice.return_value = self._make_advice()
            mock_factory.return_value = mock_service

            result = execute_advice("user-1", dict(self.PAYLOAD))

        assert result["study_stats"]["total_reviews"] == 0

    def test_review_service_exception_propagates(self):
        """旧 TC-062-DB-001: 集計失敗は internal(500) として failed になる。"""
        user_cls, review_cls, factory = self._patches()
        with user_cls as mock_user_cls, review_cls as mock_review_cls, factory:
            mock_user_cls.return_value.get_or_create_user.return_value.settings = {}
            mock_review_cls.return_value.get_review_summary.side_effect = Exception(
                "DB connection error"
            )

            with pytest.raises(Exception) as exc_info:
                execute_advice("user-1", dict(self.PAYLOAD))

        assert classify_ai_job_error(exc_info.value).status == 500

    @pytest.mark.parametrize("error,expected_status", AI_ERROR_STATUS_CASES)
    def test_ai_errors_propagate_and_classify_to_old_status(self, error, expected_status):
        """旧 TC-062-ERR-001〜005: AI 例外の旧ステータス分類を classify で引き継ぐ。"""
        user_cls, review_cls, factory = self._patches()
        with user_cls as mock_user_cls, review_cls as mock_review_cls, factory as mock_factory:
            mock_user_cls.return_value.get_or_create_user.return_value.settings = {}
            mock_review_cls.return_value.get_review_summary.return_value = (
                self._make_summary()
            )
            mock_service = MagicMock()
            mock_service.get_learning_advice.side_effect = error
            mock_factory.return_value = mock_service

            with pytest.raises(type(error)) as exc_info:
                execute_advice("user-1", dict(self.PAYLOAD))

        assert classify_ai_job_error(exc_info.value).status == expected_status


# =============================================================================
# execute_generate_from_url（旧 POST /cards/generate-from-url 同期実装相当）
# =============================================================================


class TestExecuteGenerateFromUrl:
    """GenerateFromUrlResponse 形状・重複警告・生成 0 件を検証。

    移設元: tests/unit/api/handlers/test_ai_handler.py（重複警告）と
    旧 ai_handler.generate_from_url の同期実装テスト。
    """

    PAYLOAD = {
        "url": "https://example.com/page",
        "card_type": "qa",
        "target_count": 10,
        "difficulty": "medium",
        "language": "ja",
    }

    def _make_page(self, url="https://example.com/page"):
        page = MagicMock()
        page.url = url
        page.title = "t"
        page.text_content = "x" * 200
        page.fetch_method = "http"
        page.fetched_at = "2026-05-09T00:00:00+00:00"
        return page

    def _make_result(self, cards=None):
        return GenerationResult(
            cards=(
                cards
                if cards is not None
                else [GeneratedCard(front="f", back="b", suggested_tags=[])]
            ),
            input_length=200,
            model_used="claude",
            processing_time_ms=10,
        )

    def _patches(self):
        return (
            patch("services.ai_job_executors.CardService"),
            patch("services.ai_job_executors.fetch_and_generate_cards"),
            patch("services.ai_job_executors.UrlContentService"),
            patch("services.ai_job_executors.BrowserService"),
        )

    def test_result_shape_matches_generate_from_url_response(self):
        card_cls, fetch, url_svc, browser = self._patches()
        with card_cls as mock_card_cls, fetch as mock_fetch, url_svc, browser:
            mock_card_cls.return_value.find_cards_by_reference_url.return_value = []
            mock_fetch.return_value = (
                self._make_page(),
                ["x" * 200],
                self._make_result(),
            )

            result = execute_generate_from_url("user-1", dict(self.PAYLOAD))

        assert result == {
            "generated_cards": [{"front": "f", "back": "b", "suggested_tags": []}],
            "generation_info": {
                "model_used": "claude",
                "processing_time_ms": 10,
                "fetch_method": "http",
                "chunk_count": 1,
                "content_length": 200,
            },
            "page_info": {
                "url": "https://example.com/page",
                "title": "t",
                "fetched_at": "2026-05-09T00:00:00+00:00",
            },
        }
        # 重複なしの場合 warning は含まれない（exclude_none）
        assert "warning" not in result

    def test_passes_generation_params_and_no_profile_id(self):
        """profile_id は無効化中のため常に None で fetch する。"""
        card_cls, fetch, url_svc, browser = self._patches()
        with card_cls as mock_card_cls, fetch as mock_fetch, url_svc, browser:
            mock_card_cls.return_value.find_cards_by_reference_url.return_value = []
            mock_fetch.return_value = (
                self._make_page(),
                ["x" * 200],
                self._make_result(),
            )

            execute_generate_from_url(
                "user-1",
                {
                    "url": "https://example.com/page",
                    "card_type": "definition",
                    "target_count": 5,
                    "difficulty": "hard",
                    "language": "en",
                },
            )

        call_kwargs = mock_fetch.call_args.kwargs
        assert mock_fetch.call_args.args == ("https://example.com/page",)
        assert call_kwargs["card_type"] == "definition"
        assert call_kwargs["target_count"] == 5
        assert call_kwargs["difficulty"] == "hard"
        assert call_kwargs["language"] == "en"
        assert call_kwargs["profile_id"] is None

    def test_duplicate_url_sets_warning(self):
        """旧 C-5 テスト: 既存カードに同一 URL があれば warning フィールドを付与。"""
        card_cls, fetch, url_svc, browser = self._patches()
        with card_cls as mock_card_cls, fetch as mock_fetch, url_svc, browser:
            mock_card_cls.return_value.find_cards_by_reference_url.return_value = [
                MagicMock()
            ]
            mock_fetch.return_value = (
                self._make_page(url="https://example.com/dup"),
                ["x" * 200],
                self._make_result(),
            )

            result = execute_generate_from_url(
                "user-1", {**self.PAYLOAD, "url": "https://example.com/dup"}
            )

        assert result.get("warning")
        mock_card_cls.return_value.find_cards_by_reference_url.assert_called_once_with(
            "user-1", "https://example.com/dup"
        )
        # list_cards はもう重複チェックに使わない
        mock_card_cls.return_value.list_cards.assert_not_called()

    def test_duplicate_check_failure_does_not_block_generation(self):
        """重複チェックの失敗は生成をブロックしない（non-critical）。"""
        card_cls, fetch, url_svc, browser = self._patches()
        with card_cls as mock_card_cls, fetch as mock_fetch, url_svc, browser:
            mock_card_cls.return_value.find_cards_by_reference_url.side_effect = (
                Exception("DynamoDB unavailable")
            )
            mock_fetch.return_value = (
                self._make_page(),
                ["x" * 200],
                self._make_result(),
            )

            result = execute_generate_from_url("user-1", dict(self.PAYLOAD))

        assert result["generated_cards"]
        assert "warning" not in result

    def test_no_cards_raises_no_cards_generated_error(self):
        """生成 0 件は NoCardsGeneratedError（旧同期実装の 422 相当）。"""
        card_cls, fetch, url_svc, browser = self._patches()
        with card_cls as mock_card_cls, fetch as mock_fetch, url_svc, browser:
            mock_card_cls.return_value.find_cards_by_reference_url.return_value = []
            mock_fetch.return_value = (
                self._make_page(),
                ["x" * 200],
                self._make_result(cards=[]),
            )

            with pytest.raises(NoCardsGeneratedError) as exc_info:
                execute_generate_from_url("user-1", dict(self.PAYLOAD))

        job_error = classify_ai_job_error(exc_info.value)
        assert job_error.status == 422
        assert job_error.code == "content_unsupported"


# =============================================================================
# execute_tutor_start / execute_tutor_message
# =============================================================================


def _make_session(**kwargs) -> TutorSessionResponse:
    defaults = {
        "session_id": "tutor_test-session-id",
        "deck_id": "deck_001",
        "mode": "free_talk",
        "status": "active",
        "messages": [
            TutorMessage(
                role="assistant",
                content="こんにちは！",
                related_cards=[],
                timestamp="2026-03-07T10:00:00Z",
            )
        ],
        "message_count": 0,
        "created_at": "2026-03-07T10:00:00Z",
        "updated_at": "2026-03-07T10:00:00Z",
        "ended_at": None,
    }
    defaults.update(kwargs)
    return TutorSessionResponse(**defaults)


class TestExecuteTutor:
    """tutor_start / tutor_message の executor を検証。

    移設元: test_tutor_handler.py の create_session / send_message 成功系。
    AI 実行は _tutor_service（モジュールキャッシュ）差し替えで代替する。
    """

    def test_tutor_start_result_shape_matches_session_response(self, monkeypatch):
        mock_service = MagicMock()
        mock_service.start_session.return_value = _make_session()
        monkeypatch.setattr(
            "services.ai_job_executors._tutor_service", mock_service
        )

        result = execute_tutor_start(
            "user-1", {"deck_id": "deck_001", "mode": "free_talk"}
        )

        assert result["session_id"] == "tutor_test-session-id"
        assert result["status"] == "active"
        assert result["deck_id"] == "deck_001"
        assert result["messages"][0]["role"] == "assistant"
        assert result == _make_session().model_dump(mode="json")

    def test_tutor_start_passes_args(self, monkeypatch):
        mock_service = MagicMock()
        mock_service.start_session.return_value = _make_session()
        monkeypatch.setattr(
            "services.ai_job_executors._tutor_service", mock_service
        )

        execute_tutor_start("user-9", {"deck_id": "deck_002", "mode": "quiz"})

        mock_service.start_session.assert_called_once_with(
            user_id="user-9", deck_id="deck_002", mode="quiz"
        )

    def test_tutor_message_result_shape_matches_send_message_response(
        self, monkeypatch
    ):
        response = SendMessageResponse(
            message=TutorMessage(
                role="assistant",
                content="AI の応答です。",
                related_cards=[],
                timestamp="2026-03-07T10:00:25Z",
            ),
            session_id="tutor_test-session-id",
            message_count=1,
            is_limit_reached=False,
        )
        mock_service = MagicMock()
        mock_service.send_message.return_value = response
        monkeypatch.setattr(
            "services.ai_job_executors._tutor_service", mock_service
        )

        result = execute_tutor_message(
            "user-1",
            {"session_id": "tutor_test-session-id", "content": "appleについて教えて"},
        )

        assert result["message"]["role"] == "assistant"
        assert result["message_count"] == 1
        assert result["is_limit_reached"] is False
        assert result == response.model_dump(mode="json")

    def test_tutor_message_passes_args(self, monkeypatch):
        mock_service = MagicMock()
        mock_service.send_message.return_value = SendMessageResponse(
            message=TutorMessage(
                role="assistant",
                content="ok",
                related_cards=[],
                timestamp="2026-03-07T10:00:25Z",
            ),
            session_id="tutor_x",
            message_count=2,
            is_limit_reached=False,
        )
        monkeypatch.setattr(
            "services.ai_job_executors._tutor_service", mock_service
        )

        execute_tutor_message(
            "user-9", {"session_id": "tutor_x", "content": "hello"}
        )

        mock_service.send_message.assert_called_once_with(
            user_id="user-9", session_id="tutor_x", content="hello"
        )


# =============================================================================
# ディスパッチテーブル
# =============================================================================


class TestExecutorRegistry:
    """EXECUTORS / HEAVY_JOB_TYPES が全 7 job_type をカバーすることを検証。"""

    def test_executors_cover_all_seven_job_types(self):
        assert set(EXECUTORS.keys()) == {
            "generate",
            "generate_from_url",
            "refine",
            "grade_ai",
            "advice",
            "tutor_start",
            "tutor_message",
        }

    def test_generate_from_url_is_heavy(self):
        assert HEAVY_JOB_TYPES == frozenset({"generate_from_url"})

    def test_all_executors_are_callable(self):
        for executor in EXECUTORS.values():
            assert callable(executor)

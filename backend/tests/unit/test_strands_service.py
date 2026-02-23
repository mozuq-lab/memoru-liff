"""StrandsAIService のテストスイート.

TASK-0057: StrandsAIService 基本実装（カード生成）- TDD Red フェーズ

カテゴリ:
- TestStrandsServiceProtocol: Protocol 準拠テスト (TC-PROTO-001 ~ TC-PROTO-003)
- TestStrandsServiceGenerateCards: カード生成 正常系テスト (TC-GEN-001 ~ TC-GEN-005)
- TestStrandsServiceEnvironment: 環境別モデルプロバイダー選択テスト (TC-ENV-001 ~ TC-ENV-005)
- TestStrandsServiceStubs: Phase 3 スタブメソッドテスト (TC-STUB-001 ~ TC-STUB-003)
- TestStrandsServiceErrors: エラーハンドリングテスト (TC-ERR-001 ~ TC-ERR-008)
- TestStrandsServiceParsing: レスポンス解析テスト (TC-PARSE-001 ~ TC-PARSE-009)
- TestStrandsServiceFactory: ファクトリ統合テスト (TC-COMPAT-001 ~ TC-COMPAT-002)
"""

import inspect
import json
import os
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from services.ai_service import (
    AIService,
    GeneratedCard,
    GenerationResult,
    GradingResult,
    LearningAdvice,
    DifficultyLevel,
    Language,
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIParseError,
    AIProviderError,
    create_ai_service,
)
from services.strands_service import StrandsAIService


# ---------------------------------------------------------------------------
# テストデータフィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture
def valid_agent_response():
    """Agent が返す正常なレスポンステキスト."""
    return json.dumps({
        "cards": [
            {"front": "光合成とは何か？", "back": "植物が太陽光を使って...", "tags": ["生物学"]},
            {"front": "葉緑体の役割は？", "back": "光合成の場...", "tags": ["生物学", "細胞"]},
            {"front": "光合成の化学式は？", "back": "6CO2 + 6H2O → C6H12O6 + 6O2", "tags": ["化学"]},
        ]
    })


@pytest.fixture
def markdown_wrapped_response():
    """Markdown コードブロックで囲まれた JSON レスポンス."""
    return '```json\n{"cards": [{"front": "Q1", "back": "A1", "tags": ["tag1"]}]}\n```'


@pytest.fixture
def invalid_json_response():
    """JSON として解析できないレスポンス."""
    return "This is not valid JSON at all"


@pytest.fixture
def missing_cards_response():
    """cards フィールドが欠落したレスポンス."""
    return json.dumps({"data": "no cards here"})


@pytest.fixture
def all_invalid_cards_response():
    """全カードが無効なレスポンス."""
    return json.dumps({"cards": [{"front": ""}, {"back": "A2"}]})


def _make_mock_agent_instance(response_text: str) -> MagicMock:
    """Agent インスタンスのモックを作成するヘルパー.

    Agent の __call__ メソッドが MagicMock を返し、
    str() を呼ぶと response_text が返るようにする。
    """
    mock_response = MagicMock()
    mock_response.__str__ = MagicMock(return_value=response_text)
    mock_agent = MagicMock()
    mock_agent.return_value = mock_response
    return mock_agent


# ---------------------------------------------------------------------------
# Category 1: Protocol 準拠テスト (TC-PROTO)
# ---------------------------------------------------------------------------


class TestStrandsServiceProtocol:
    """Protocol 準拠テスト (TC-PROTO-001 ~ TC-PROTO-003)."""

    def test_strands_service_implements_ai_service_protocol(self):
        """TC-PROTO-001: StrandsAIService は AIService Protocol を満たす."""
        # Given
        with patch("services.strands_service.Agent"), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

        # Then
        assert isinstance(service, AIService)

    def test_strands_service_has_all_protocol_methods(self):
        """TC-PROTO-002: Protocol 定義の 3 メソッドが全て存在し callable である."""
        with patch("services.strands_service.Agent"), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

        assert hasattr(service, "generate_cards") and callable(service.generate_cards)
        assert hasattr(service, "grade_answer") and callable(service.grade_answer)
        assert hasattr(service, "get_learning_advice") and callable(service.get_learning_advice)

    def test_generate_cards_signature_matches_protocol(self):
        """TC-PROTO-003: generate_cards() のシグネチャが Protocol と一致する."""
        with patch("services.strands_service.Agent"), \
             patch("services.strands_service.BedrockModel"):
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


# ---------------------------------------------------------------------------
# Category 2: カード生成 正常系テスト (TC-GEN)
# ---------------------------------------------------------------------------


class TestStrandsServiceGenerateCards:
    """カード生成 正常系テスト (TC-GEN-001 ~ TC-GEN-005)."""

    def test_generate_cards_happy_path(self):
        """TC-GEN-001: 有効な入力で GenerationResult が返される."""
        # Given
        response_json = json.dumps({
            "cards": [
                {"front": "Q1", "back": "A1", "tags": ["tag1"]},
                {"front": "Q2", "back": "A2", "tags": ["tag2"]},
                {"front": "Q3", "back": "A3", "tags": ["tag3"]},
            ]
        })
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.generate_cards(
                input_text="光合成は植物が太陽光を使って二酸化炭素と水から有機物を合成する反応です。",
                card_count=3,
                difficulty="medium",
                language="ja",
            )

        # Then
        assert isinstance(result, GenerationResult)
        assert len(result.cards) == 3
        for card in result.cards:
            assert isinstance(card, GeneratedCard)
            assert len(card.front) > 0
            assert len(card.back) > 0
            assert isinstance(card.suggested_tags, list)

    def test_generate_cards_input_length(self):
        """TC-GEN-002: input_length が入力テキストの文字数と一致する."""
        input_text = "あ" * 150  # 150文字

        response_json = json.dumps({
            "cards": [{"front": "Q", "back": "A", "tags": []}]
        })
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.generate_cards(input_text=input_text)

        assert result.input_length == 150

    def test_generate_cards_model_used_is_nonempty_string(self):
        """TC-GEN-003: model_used が空でない文字列を含む."""
        response_json = json.dumps({
            "cards": [{"front": "Q", "back": "A", "tags": []}]
        })
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.generate_cards(input_text="テスト入力テキスト")

        assert isinstance(result.model_used, str)
        assert len(result.model_used) > 0

    def test_generate_cards_processing_time_ms(self):
        """TC-GEN-004: processing_time_ms が 0 以上の整数である."""
        response_json = json.dumps({
            "cards": [{"front": "Q", "back": "A", "tags": []}]
        })
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.generate_cards(input_text="テスト入力テキスト")

        assert isinstance(result.processing_time_ms, int)
        assert result.processing_time_ms >= 0

    @patch("services.strands_service.get_card_generation_prompt", return_value="mocked prompt")
    def test_generate_cards_passes_correct_args_to_prompt(self, mock_prompt):
        """TC-GEN-005: get_card_generation_prompt() に正しい引数が渡される."""
        input_text = "Test input"
        response_json = json.dumps({
            "cards": [{"front": "Q", "back": "A", "tags": []}]
        })
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            service.generate_cards(
                input_text=input_text,
                card_count=7,
                difficulty="hard",
                language="en",
            )

        mock_prompt.assert_called_once_with(
            input_text=input_text,
            card_count=7,
            difficulty="hard",
            language="en",
        )


# ---------------------------------------------------------------------------
# Category 3: 環境別モデルプロバイダー選択テスト (TC-ENV)
# ---------------------------------------------------------------------------


class TestStrandsServiceEnvironment:
    """環境別モデルプロバイダー選択テスト (TC-ENV-001 ~ TC-ENV-005)."""

    @patch.dict(os.environ, {"ENVIRONMENT": "dev"})
    @patch("services.strands_service.Agent")
    @patch("services.strands_service.OllamaModel")
    @patch("services.strands_service.BedrockModel")
    def test_dev_environment_selects_ollama(self, mock_bedrock, mock_ollama, mock_agent):
        """TC-ENV-001: ENVIRONMENT=dev で OllamaModel が選択される."""
        service = StrandsAIService()

        mock_ollama.assert_called_once()
        mock_bedrock.assert_not_called()

    @patch.dict(os.environ, {"ENVIRONMENT": "prod"})
    @patch("services.strands_service.Agent")
    @patch("services.strands_service.BedrockModel")
    @patch("services.strands_service.OllamaModel")
    def test_prod_environment_selects_bedrock(self, mock_ollama, mock_bedrock, mock_agent):
        """TC-ENV-002: ENVIRONMENT=prod で BedrockModel が選択される."""
        service = StrandsAIService()

        mock_bedrock.assert_called_once()
        mock_ollama.assert_not_called()

    @patch.dict(os.environ, {"ENVIRONMENT": "staging"})
    @patch("services.strands_service.Agent")
    @patch("services.strands_service.BedrockModel")
    def test_staging_environment_selects_bedrock(self, mock_bedrock, mock_agent):
        """TC-ENV-003: ENVIRONMENT=staging で BedrockModel が選択される."""
        service = StrandsAIService()

        mock_bedrock.assert_called_once()

    @patch("services.strands_service.Agent")
    @patch("services.strands_service.BedrockModel")
    def test_no_environment_defaults_to_bedrock(self, mock_bedrock, mock_agent):
        """TC-ENV-004: ENVIRONMENT 未設定でも BedrockModel がデフォルト選択される."""
        # conftest.py で ENVIRONMENT=test が設定されているため、明示的に削除する
        os.environ.pop("ENVIRONMENT", None)
        try:
            service = StrandsAIService()
            mock_bedrock.assert_called_once()
        finally:
            # テスト後に conftest.py の値を復元する
            os.environ["ENVIRONMENT"] = "test"

    @patch.dict(os.environ, {"ENVIRONMENT": "prod"})
    @patch("services.strands_service.Agent")
    @patch("services.strands_service.OllamaModel")
    @patch("services.strands_service.BedrockModel")
    def test_constructor_environment_overrides_env_var(self, mock_bedrock, mock_ollama, mock_agent):
        """TC-ENV-005: コンストラクタ引数で環境変数をオーバーライドできる."""
        service = StrandsAIService(environment="dev")

        mock_ollama.assert_called_once()
        mock_bedrock.assert_not_called()


# ---------------------------------------------------------------------------
# Category 4: Phase 3 スタブメソッドテスト (TC-STUB)
# ---------------------------------------------------------------------------


class TestStrandsServiceStubs:
    """Phase 3 スタブメソッドテスト (TC-STUB-001 ~ TC-STUB-003)."""

    def test_grade_answer_raises_not_implemented(self):
        """TC-STUB-001: grade_answer() は NotImplementedError を raise する."""
        with patch("services.strands_service.Agent"), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

        with pytest.raises(NotImplementedError):
            service.grade_answer(
                card_front="日本の首都は？",
                card_back="東京",
                user_answer="東京",
            )

    def test_get_learning_advice_raises_not_implemented(self):
        """TC-STUB-002: get_learning_advice() は NotImplementedError を raise する."""
        with patch("services.strands_service.Agent"), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

        with pytest.raises(NotImplementedError):
            service.get_learning_advice(
                review_summary={"total_reviews": 10},
            )

    def test_not_implemented_error_message_contains_phase3(self):
        """TC-STUB-003: NotImplementedError のメッセージに 'Phase 3' を含む."""
        with patch("services.strands_service.Agent"), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

        with pytest.raises(NotImplementedError, match="Phase 3"):
            service.grade_answer(card_front="Q", card_back="A", user_answer="A")

        with pytest.raises(NotImplementedError, match="Phase 3"):
            service.get_learning_advice(review_summary={})


# ---------------------------------------------------------------------------
# Category 5: エラーハンドリングテスト (TC-ERR)
# ---------------------------------------------------------------------------


class TestStrandsServiceErrors:
    """エラーハンドリングテスト (TC-ERR-001 ~ TC-ERR-008)."""

    def test_agent_timeout_raises_ai_timeout_error(self):
        """TC-ERR-001: Agent タイムアウト時に AITimeoutError が raise される. (🟡 SDK 依存)"""
        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = TimeoutError("Agent timed out")

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AITimeoutError):
                service.generate_cards(input_text="テスト")

    def test_provider_connection_error_raises_ai_provider_error(self):
        """TC-ERR-002: プロバイダー接続エラー時に AIProviderError が raise される. (🟡 SDK 依存)"""
        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = ConnectionError("Connection refused")

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIProviderError):
                service.generate_cards(input_text="テスト")

    def test_invalid_json_response_raises_ai_parse_error(self):
        """TC-ERR-003: 不正な JSON レスポンス時に AIParseError が raise される."""
        mock_agent_instance = MagicMock()
        # Agent が JSON でない文字列を返す
        mock_agent_instance.return_value = MagicMock(
            __str__=MagicMock(return_value="This is not JSON")
        )

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIParseError):
                service.generate_cards(input_text="テスト")

    def test_missing_cards_field_raises_ai_parse_error(self):
        """TC-ERR-004: 'cards' フィールドが欠落した場合 AIParseError が raise される."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = MagicMock(
            __str__=MagicMock(return_value=json.dumps({"data": []}))
        )

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIParseError):
                service.generate_cards(input_text="テスト")

    def test_exception_chain_preserved_with_from_e(self):
        """TC-ERR-005: 例外チェーンが __cause__ で保持される."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.return_value = MagicMock(
            __str__=MagicMock(return_value="not valid json {{{")
        )

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIParseError) as exc_info:
                service.generate_cards(input_text="テスト")

            assert exc_info.value.__cause__ is not None

    @pytest.mark.parametrize("exception_class", [
        AITimeoutError,
        AIRateLimitError,
        AIParseError,
        AIProviderError,
        AIServiceError,
    ])
    def test_all_exceptions_are_ai_service_error_subclasses(self, exception_class):
        """TC-ERR-006: StrandsAIService が使用する例外は全て AIServiceError のサブクラス."""
        assert issubclass(exception_class, AIServiceError)
        err = exception_class("test")
        assert isinstance(err, AIServiceError)

    def test_unknown_exception_wrapped_in_ai_service_error(self):
        """TC-ERR-007: 予期しない例外は AIServiceError にラップされる."""
        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = RuntimeError("Something unexpected")

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIServiceError):
                service.generate_cards(input_text="テスト")

    def test_rate_limit_raises_ai_rate_limit_error(self):
        """TC-ERR-008: レート制限エラー時に AIRateLimitError が raise される. (🟡 SDK 依存)"""
        # 🟡 Strands SDK のレート制限例外クラスに応じて side_effect を調整
        from botocore.exceptions import ClientError
        mock_agent_instance = MagicMock()
        # ClientError の ThrottlingException 等をシミュレート
        mock_agent_instance.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
            "InvokeModel",
        )

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIRateLimitError):
                service.generate_cards(input_text="テスト")


# ---------------------------------------------------------------------------
# Category 6: レスポンス解析テスト (TC-PARSE)
# ---------------------------------------------------------------------------


class TestStrandsServiceParsing:
    """レスポンス解析テスト (TC-PARSE-001 ~ TC-PARSE-009)."""

    def test_parse_valid_json_creates_generated_cards(self):
        """TC-PARSE-001: 正常な JSON からカードが生成される."""
        response = json.dumps({
            "cards": [{"front": "Q1", "back": "A1", "tags": ["tag1"]}]
        })
        mock_agent_instance = _make_mock_agent_instance(response)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.generate_cards(input_text="テスト")

        assert len(result.cards) == 1
        assert result.cards[0].front == "Q1"
        assert result.cards[0].back == "A1"
        assert "AI生成" in result.cards[0].suggested_tags
        assert "tag1" in result.cards[0].suggested_tags

    def test_parse_markdown_wrapped_json(self):
        """TC-PARSE-002: Markdown コードブロック内の JSON が正しく解析される."""
        response = '```json\n{"cards": [{"front": "Q1", "back": "A1", "tags": []}]}\n```'
        mock_agent_instance = _make_mock_agent_instance(response)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.generate_cards(input_text="テスト")

        assert len(result.cards) == 1
        assert result.cards[0].front == "Q1"

    def test_parse_skips_cards_missing_front_or_back(self):
        """TC-PARSE-003: front/back 欠落カードはスキップされる."""
        response = json.dumps({
            "cards": [
                {"front": "Q1"},           # back 欠落
                {"back": "A2"},            # front 欠落
                {"front": "Q3", "back": "A3"},  # 有効
            ]
        })
        mock_agent_instance = _make_mock_agent_instance(response)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.generate_cards(input_text="テスト")

        assert len(result.cards) == 1
        assert result.cards[0].front == "Q3"

    def test_parse_all_invalid_cards_raises_ai_parse_error(self):
        """TC-PARSE-004: 全カードが無効な場合 AIParseError が raise される."""
        response = json.dumps({
            "cards": [
                {"front": "", "back": "A1"},   # front 空
                {"front": "Q2", "back": ""},   # back 空
                {"front": "Q3"},               # back 欠落
            ]
        })
        mock_agent_instance = _make_mock_agent_instance(response)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIParseError):
                service.generate_cards(input_text="テスト")

    def test_parse_missing_tags_defaults_to_ai_generated_only(self):
        """TC-PARSE-005: tags がない場合、suggested_tags は ['AI生成'] となる."""
        response = json.dumps({"cards": [{"front": "Q", "back": "A"}]})
        mock_agent_instance = _make_mock_agent_instance(response)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.generate_cards(input_text="テスト")

        assert result.cards[0].suggested_tags == ["AI生成"]

    def test_parse_missing_cards_key_raises_ai_parse_error(self):
        """TC-PARSE-006: 'cards' キーがない JSON で AIParseError."""
        response = json.dumps({"data": [], "items": []})
        mock_agent_instance = _make_mock_agent_instance(response)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIParseError):
                service.generate_cards(input_text="テスト")

    def test_parse_no_duplicate_ai_generated_tag(self):
        """TC-PARSE-007: 'AI生成' タグが既存の場合は重複追加しない."""
        response = json.dumps({
            "cards": [{"front": "Q", "back": "A", "tags": ["AI生成", "physics"]}]
        })
        mock_agent_instance = _make_mock_agent_instance(response)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.generate_cards(input_text="テスト")

        assert result.cards[0].suggested_tags == ["AI生成", "physics"]
        assert result.cards[0].suggested_tags.count("AI生成") == 1

    def test_parse_non_list_tags_falls_back_to_empty(self):
        """TC-PARSE-008: tags がリストでない場合は空リストにフォールバック."""
        response = json.dumps({
            "cards": [{"front": "Q", "back": "A", "tags": "string-tag"}]
        })
        mock_agent_instance = _make_mock_agent_instance(response)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.generate_cards(input_text="テスト")

        assert result.cards[0].suggested_tags == ["AI生成"]

    def test_parse_empty_cards_array_raises_ai_parse_error(self):
        """TC-PARSE-009: 空の cards 配列で AIParseError."""
        response = json.dumps({"cards": []})
        mock_agent_instance = _make_mock_agent_instance(response)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIParseError):
                service.generate_cards(input_text="テスト")


# ---------------------------------------------------------------------------
# Category 7: ファクトリ統合テスト (TC-COMPAT)
# ---------------------------------------------------------------------------


class TestStrandsServiceFactory:
    """ファクトリ統合テスト (TC-COMPAT-001 ~ TC-COMPAT-002)."""

    def test_factory_returns_strands_service_when_use_strands_true(self):
        """TC-COMPAT-001: create_ai_service(use_strands=True) が StrandsAIService を返す."""
        with patch("services.strands_service.Agent"), \
             patch("services.strands_service.BedrockModel"):
            service = create_ai_service(use_strands=True)

        assert isinstance(service, StrandsAIService)

    def test_generation_result_has_all_required_fields(self):
        """TC-COMPAT-002: GenerationResult が API 仕様に準拠した全フィールドを持つ."""
        response_json = json.dumps({
            "cards": [{"front": "Q", "back": "A", "tags": []}]
        })
        mock_agent_instance = _make_mock_agent_instance(response_json)

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            result = service.generate_cards(input_text="テスト入力テキスト")

        assert hasattr(result, "cards")
        assert hasattr(result, "input_length")
        assert hasattr(result, "model_used")
        assert hasattr(result, "processing_time_ms")

        assert isinstance(result.cards, list)
        assert isinstance(result.input_length, int)
        assert isinstance(result.model_used, str)
        assert isinstance(result.processing_time_ms, int)

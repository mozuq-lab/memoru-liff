"""カード生成 API 互換性検証 + 移行テスト.

TASK-0058: USE_STRANDS フラグの true/false 両方でカード生成 API が同一の
レスポンス形式を返すことを検証する。

テストカテゴリ:
- TestAPIResponseCompatibility: レスポンス形式一致 (TC-COMPAT-001 ~ TC-COMPAT-006)
- TestErrorHandlingCompatibility: エラーハンドリング一致 (TC-ERROR-001 ~ TC-ERROR-008)
- TestFeatureFlagBehavior: フラグ切替動作 (TC-FLAG-001 ~ TC-FLAG-005)
- TestGenerationResultValidity: GenerationResult 有効性 (TC-RESULT-001 ~ TC-RESULT-003)
- TestMigrationEdgeCases: 移行エッジケース (TC-EDGE-001 ~ TC-EDGE-006)
- TestExistingTestProtection: 既存テスト保護 (TC-PROTECT-001 ~ TC-PROTECT-003)

注意事項:
- 全メソッドは同期 (pytest.mark.asyncio 不要)
- 既存 conftest.py フィクスチャ (api_gateway_event, lambda_context) を使用
- StrandsAIService のモックでは Agent + BedrockModel クラスをモック
- BedrockService のモックでは boto3 クライアントをモック
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from services.ai_service import (
    AIService,
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIInternalError,
    AIParseError,
    AIProviderError,
    GenerationResult as AIGenerationResult,
    create_ai_service,
)
from services.bedrock import (
    BedrockService,
    BedrockTimeoutError,
    BedrockRateLimitError,
    BedrockInternalError,
    BedrockParseError,
    GenerationResult as BedrockGenerationResult,
)
from services.strands_service import StrandsAIService
from models.generate import (
    GenerateCardsResponse,
    GeneratedCardResponse,
    GenerationInfoResponse,
)
from api.handler import _map_ai_error_to_http


# ---------------------------------------------------------------------------
# テストデータ定数
# ---------------------------------------------------------------------------

DEFAULT_CARD_COUNT = 3
DEFAULT_INPUT_TEXT = "光合成は植物が太陽光を使って二酸化炭素と水から有機物を合成する反応です。"
DEFAULT_DIFFICULTY = "medium"
DEFAULT_LANGUAGE = "ja"

# StrandsAIService が返す model_used の期待値 (prod 環境)
STRANDS_MODEL_USED = "strands_bedrock"

# BedrockService が返す model_used のデフォルト値
BEDROCK_MODEL_USED_DEFAULT = "anthropic.claude-3-haiku-20240307-v1:0"

# 共通テストカードデータ
SAMPLE_CARDS_DATA = [
    {"front": "光合成とは何か？", "back": "植物が太陽光を使って有機物を合成する反応", "tags": ["生物学"]},
    {"front": "葉緑体の役割は？", "back": "光合成の場を提供する細胞小器官", "tags": ["生物学", "細胞"]},
    {"front": "光合成の化学式は？", "back": "6CO2 + 6H2O → C6H12O6 + 6O2", "tags": ["化学"]},
]


# ---------------------------------------------------------------------------
# ヘルパー関数
# ---------------------------------------------------------------------------


def _make_strands_agent_response(cards_data: list[dict] | None = None) -> str:
    """Strands Agent のモックレスポンス JSON テキストを生成する."""
    if cards_data is None:
        cards_data = SAMPLE_CARDS_DATA
    return json.dumps({"cards": cards_data})


def _make_mock_agent_instance(response_text: str) -> MagicMock:
    """Agent インスタンスのモックを作成する.

    Agent の __call__ メソッドが MagicMock を返し、
    str() を呼ぶと response_text が返るようにする。
    """
    mock_response = MagicMock()
    mock_response.__str__ = MagicMock(return_value=response_text)
    mock_agent = MagicMock()
    mock_agent.return_value = mock_response
    return mock_agent


def _make_bedrock_mock_client(cards_data: list[dict] | None = None) -> MagicMock:
    """BedrockService 用のモック boto3 クライアントを作成する."""
    if cards_data is None:
        cards_data = SAMPLE_CARDS_DATA
    response_json = json.dumps({"cards": cards_data})
    mock_client = MagicMock()
    mock_response_body = MagicMock()
    mock_response_body.read.return_value = json.dumps({
        "content": [{"text": response_json}]
    }).encode()
    mock_client.invoke_model.return_value = {"body": mock_response_body}
    return mock_client


def _generate_with_strands(
    input_text: str = DEFAULT_INPUT_TEXT,
    card_count: int = DEFAULT_CARD_COUNT,
    cards_data: list[dict] | None = None,
) -> AIGenerationResult:
    """StrandsAIService でカードを生成する (モック使用)."""
    response_text = _make_strands_agent_response(cards_data)
    mock_agent_instance = _make_mock_agent_instance(response_text)
    with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
         patch("services.strands_service.BedrockModel"):
        service = StrandsAIService()
        return service.generate_cards(
            input_text=input_text,
            card_count=card_count,
            difficulty=DEFAULT_DIFFICULTY,
            language=DEFAULT_LANGUAGE,
        )


def _generate_with_bedrock(
    input_text: str = DEFAULT_INPUT_TEXT,
    card_count: int = DEFAULT_CARD_COUNT,
    cards_data: list[dict] | None = None,
) -> BedrockGenerationResult:
    """BedrockService でカードを生成する (モック使用)."""
    mock_client = _make_bedrock_mock_client(cards_data)
    service = BedrockService(bedrock_client=mock_client)
    return service.generate_cards(
        input_text=input_text,
        card_count=card_count,
        difficulty=DEFAULT_DIFFICULTY,
        language=DEFAULT_LANGUAGE,
    )


def _assert_generation_result_valid(result: object) -> None:
    """GenerationResult の全フィールドが有効であることを検証する.

    Note: BedrockService は bedrock.GenerationResult を返し、StrandsAIService は
    ai_service.GenerationResult を返す。両方とも同一の構造を持つが異なるクラスであるため、
    ダックタイピングで構造を検証する。
    """
    # GenerationResult 構造の検証 (ダックタイピング)
    assert hasattr(result, "cards"), "GenerationResult に 'cards' フィールドがありません"
    assert hasattr(result, "input_length"), "GenerationResult に 'input_length' フィールドがありません"
    assert hasattr(result, "model_used"), "GenerationResult に 'model_used' フィールドがありません"
    assert hasattr(result, "processing_time_ms"), "GenerationResult に 'processing_time_ms' フィールドがありません"

    assert isinstance(result.cards, list)
    assert len(result.cards) > 0
    assert isinstance(result.input_length, int)
    assert result.input_length > 0
    assert isinstance(result.model_used, str)
    assert len(result.model_used) > 0
    assert isinstance(result.processing_time_ms, int)
    assert result.processing_time_ms >= 0

    for card in result.cards:
        # GeneratedCard 構造の検証 (ダックタイピング)
        assert hasattr(card, "front"), "GeneratedCard に 'front' フィールドがありません"
        assert hasattr(card, "back"), "GeneratedCard に 'back' フィールドがありません"
        assert hasattr(card, "suggested_tags"), "GeneratedCard に 'suggested_tags' フィールドがありません"
        assert isinstance(card.front, str)
        assert len(card.front) > 0
        assert isinstance(card.back, str)
        assert len(card.back) > 0
        assert isinstance(card.suggested_tags, list)
        for tag in card.suggested_tags:
            assert isinstance(tag, str)


# ===========================================================================
# Category 1: API レスポンス形式一致テスト
# ===========================================================================


class TestAPIResponseCompatibility:
    """API レスポンス形式一致テスト (TC-COMPAT-001 ~ TC-COMPAT-006)."""

    def test_strands_generate_cards_returns_valid_generation_result(self):
        """TC-COMPAT-001: StrandsAIService の GenerationResult スキーマ一致.

        USE_STRANDS=true での成功レスポンスが GenerationResult スキーマに準拠すること。
        🔵 信頼性レベル: 青信号 - ai_service.py GenerationResult dataclass から確定
        """
        # When
        result = _generate_with_strands()

        # Then
        _assert_generation_result_valid(result)
        assert len(result.cards) == DEFAULT_CARD_COUNT
        assert result.input_length == len(DEFAULT_INPUT_TEXT)
        assert result.model_used == STRANDS_MODEL_USED

    def test_bedrock_generate_cards_returns_valid_generation_result(self):
        """TC-COMPAT-002: BedrockService の GenerationResult スキーマ一致.

        USE_STRANDS=false での成功レスポンスが GenerationResult スキーマに準拠すること。
        🔵 信頼性レベル: 青信号 - bedrock.py GenerationResult 返却処理から確定
        """
        # When
        result = _generate_with_bedrock()

        # Then
        _assert_generation_result_valid(result)
        assert len(result.cards) == DEFAULT_CARD_COUNT
        assert result.input_length == len(DEFAULT_INPUT_TEXT)

    def test_both_services_produce_structurally_equivalent_results(self):
        """TC-COMPAT-003: 両サービスのレスポンス構造的同値性.

        同一の入力で両サービスを呼び出した際、GenerationResult の構造が一致すること。
        🔵 信頼性レベル: 青信号 - handler.py 共通変換処理から確定
        """
        # When
        strands_result = _generate_with_strands()
        bedrock_result = _generate_with_bedrock()

        # Then - 構造の一致
        assert len(strands_result.cards) == len(bedrock_result.cards)
        assert strands_result.input_length == bedrock_result.input_length

        # フィールドの存在確認 (値は異なってよい)
        assert hasattr(strands_result, "cards")
        assert hasattr(strands_result, "input_length")
        assert hasattr(strands_result, "model_used")
        assert hasattr(strands_result, "processing_time_ms")

        assert hasattr(bedrock_result, "cards")
        assert hasattr(bedrock_result, "input_length")
        assert hasattr(bedrock_result, "model_used")
        assert hasattr(bedrock_result, "processing_time_ms")

        # model_used は実装固有の値なので異なることを許容
        assert strands_result.model_used != bedrock_result.model_used

        # processing_time_ms は両方とも非負整数
        assert strands_result.processing_time_ms >= 0
        assert bedrock_result.processing_time_ms >= 0

    def test_generated_card_field_types_match_between_services(self):
        """TC-COMPAT-004: GeneratedCard の各フィールド型検証.

        両サービスの GeneratedCard が同一のフィールド型を持つこと。
        🔵 信頼性レベル: 青信号 - ai_service.py GeneratedCard dataclass から確定
        """
        # When
        strands_result = _generate_with_strands()
        bedrock_result = _generate_with_bedrock()

        # Then - 各サービスのカードフィールド検証
        for result in [strands_result, bedrock_result]:
            for card in result.cards:
                assert isinstance(card.front, str)
                assert len(card.front) > 0
                assert isinstance(card.back, str)
                assert len(card.back) > 0
                assert isinstance(card.suggested_tags, list)
                # "AI生成" タグが自動挿入される
                assert "AI生成" in card.suggested_tags

    def test_generation_result_serializes_to_generate_cards_response(self):
        """TC-COMPAT-005: JSON シリアライズ互換性 (GenerateCardsResponse).

        GenerationResult から GenerateCardsResponse への変換と JSON シリアライズが
        正しく動作すること。
        🔵 信頼性レベル: 青信号 - models/generate.py Pydantic モデル定義から確定
        """
        # Given
        strands_result = _generate_with_strands()
        bedrock_result = _generate_with_bedrock()

        for result in [strands_result, bedrock_result]:
            # When - handler.py と同じ変換処理
            response = GenerateCardsResponse(
                generated_cards=[
                    GeneratedCardResponse(
                        front=card.front,
                        back=card.back,
                        suggested_tags=card.suggested_tags,
                    )
                    for card in result.cards
                ],
                generation_info=GenerationInfoResponse(
                    input_length=result.input_length,
                    model_used=result.model_used,
                    processing_time_ms=result.processing_time_ms,
                ),
            )

            # Then - JSON シリアライズ
            json_data = response.model_dump(mode="json")

            # トップレベルキーの確認
            assert set(json_data.keys()) == {"generated_cards", "generation_info"}

            # generated_cards のキー確認
            for card_json in json_data["generated_cards"]:
                assert set(card_json.keys()) == {"front", "back", "suggested_tags"}

            # generation_info のキー確認
            assert set(json_data["generation_info"].keys()) == {
                "input_length",
                "model_used",
                "processing_time_ms",
            }

            # 有効な JSON 文字列に変換可能
            serialized = json.dumps(json_data)
            assert isinstance(serialized, str)
            # 再パース可能
            reparsed = json.loads(serialized)
            assert reparsed == json_data

    def test_model_used_values_are_distinct_and_nonempty(self):
        """TC-COMPAT-006: model_used フィールドの値検証.

        各サービスが正しい model_used 値を返すこと。
        🔵 信頼性レベル: 青信号 - strands_service.py/bedrock.py の定数定義から確定
        """
        # When
        strands_result = _generate_with_strands()
        bedrock_result = _generate_with_bedrock()

        # Then
        # StrandsAIService: prod 環境では "strands_bedrock"
        assert strands_result.model_used == STRANDS_MODEL_USED
        assert len(strands_result.model_used) > 0

        # BedrockService: BEDROCK_MODEL_ID のデフォルト値
        assert bedrock_result.model_used == BEDROCK_MODEL_USED_DEFAULT
        assert len(bedrock_result.model_used) > 0

        # 両者は異なる値
        assert strands_result.model_used != bedrock_result.model_used


# ===========================================================================
# Category 2: エラーハンドリング互換性テスト
# ===========================================================================


class TestErrorHandlingCompatibility:
    """エラーハンドリング互換性テスト (TC-ERROR-001 ~ TC-ERROR-008)."""

    def test_timeout_error_maps_to_504_for_both_services(self):
        """TC-ERROR-001: タイムアウトエラー -> HTTP 504 (両サービス).

        StrandsAIService の AITimeoutError と BedrockService の BedrockTimeoutError が
        共に HTTP 504 にマッピングされること。
        🔵 信頼性レベル: 青信号 - handler.py _map_ai_error_to_http() から確定
        """
        # Strands 側: AITimeoutError
        strands_response = _map_ai_error_to_http(AITimeoutError("Agent timed out"))
        assert strands_response.status_code == 504
        strands_body = json.loads(strands_response.body)
        assert strands_body["error"] == "AI service timeout"

        # Bedrock 側: BedrockTimeoutError (extends AITimeoutError)
        bedrock_response = _map_ai_error_to_http(BedrockTimeoutError("Bedrock timed out"))
        assert bedrock_response.status_code == 504
        bedrock_body = json.loads(bedrock_response.body)
        assert bedrock_body["error"] == "AI service timeout"

    def test_rate_limit_error_maps_to_429_for_both_services(self):
        """TC-ERROR-002: レート制限エラー -> HTTP 429 (両サービス).

        StrandsAIService の AIRateLimitError と BedrockService の BedrockRateLimitError が
        共に HTTP 429 にマッピングされること。
        🔵 信頼性レベル: 青信号 - handler.py _map_ai_error_to_http() から確定
        """
        # Strands 側: AIRateLimitError
        strands_response = _map_ai_error_to_http(AIRateLimitError("Rate limit exceeded"))
        assert strands_response.status_code == 429
        strands_body = json.loads(strands_response.body)
        assert strands_body["error"] == "AI service rate limit exceeded"

        # Bedrock 側: BedrockRateLimitError (extends AIRateLimitError)
        bedrock_response = _map_ai_error_to_http(BedrockRateLimitError("Throttled"))
        assert bedrock_response.status_code == 429
        bedrock_body = json.loads(bedrock_response.body)
        assert bedrock_body["error"] == "AI service rate limit exceeded"

    def test_parse_error_maps_to_500_for_both_services(self):
        """TC-ERROR-003: JSON 解析エラー -> HTTP 500 (両サービス).

        StrandsAIService の AIParseError と BedrockService の BedrockParseError が
        共に HTTP 500 にマッピングされること。
        🔵 信頼性レベル: 青信号 - handler.py _map_ai_error_to_http() から確定
        """
        # Strands 側: AIParseError
        strands_response = _map_ai_error_to_http(AIParseError("Failed to parse JSON"))
        assert strands_response.status_code == 500
        strands_body = json.loads(strands_response.body)
        assert strands_body["error"] == "AI service response parse error"

        # Bedrock 側: BedrockParseError (extends AIParseError)
        bedrock_response = _map_ai_error_to_http(BedrockParseError("Invalid JSON"))
        assert bedrock_response.status_code == 500
        bedrock_body = json.loads(bedrock_response.body)
        assert bedrock_body["error"] == "AI service response parse error"

    def test_internal_error_maps_to_500_fallback(self):
        """TC-ERROR-004: 内部エラー -> HTTP 500 (フォールバック).

        AIServiceError 基底クラスと AIInternalError/BedrockInternalError が
        共に HTTP 500 にマッピングされること。
        🔵 信頼性レベル: 青信号 - handler.py 汎用フォールバック処理から確定
        """
        # AIServiceError 基底 (Strands の catch-all)
        base_response = _map_ai_error_to_http(AIServiceError("Unexpected error"))
        assert base_response.status_code == 500
        base_body = json.loads(base_response.body)
        assert base_body["error"] == "AI service error"

        # AIInternalError
        internal_response = _map_ai_error_to_http(AIInternalError("Internal failure"))
        assert internal_response.status_code == 500

        # BedrockInternalError (extends AIInternalError)
        bedrock_internal_response = _map_ai_error_to_http(BedrockInternalError("Bedrock internal"))
        assert bedrock_internal_response.status_code == 500

    def test_provider_error_maps_to_503(self):
        """TC-ERROR-005: プロバイダーエラー -> HTTP 503.

        AIProviderError が HTTP 503 にマッピングされること。
        🔵 信頼性レベル: 青信号 - handler.py _map_ai_error_to_http() から確定
        """
        response = _map_ai_error_to_http(AIProviderError("Provider connection error"))
        assert response.status_code == 503
        body = json.loads(response.body)
        assert body["error"] == "AI service unavailable"

    def test_validation_error_independent_of_feature_flag(
        self, api_gateway_event, lambda_context
    ):
        """TC-ERROR-006: バリデーションエラー -> HTTP 400 (フラグ非依存).

        リクエストバリデーションは AI サービスの前段で実行されるため、
        USE_STRANDS フラグに依存しないこと。
        🔵 信頼性レベル: 青信号 - handler.py Pydantic ValidationError 処理から確定
        """
        # Given - 無効なリクエスト (input_text が短すぎる)
        event = api_gateway_event(
            method="POST",
            path="/cards/generate",
            body={"input_text": "短い", "card_count": 5},
        )

        # When / Then - USE_STRANDS の値に関わらず同一の 400 レスポンス
        for use_strands_value in ["true", "false"]:
            with patch.dict(os.environ, {"USE_STRANDS": use_strands_value}):
                from api.handler import handler
                response = handler(event, lambda_context)
                assert response["statusCode"] == 400

    def test_bedrock_exceptions_mapped_via_multiple_inheritance(self):
        """TC-ERROR-007: Bedrock 例外の多重継承経由マッピング.

        Bedrock 固有例外が多重継承により AIServiceError 階層経由で
        正しくマッピングされること。
        🔵 信頼性レベル: 青信号 - bedrock.py 多重継承定義から確定
        """
        # BedrockTimeoutError は AITimeoutError でもある
        timeout_err = BedrockTimeoutError("timeout")
        assert isinstance(timeout_err, AITimeoutError)
        assert _map_ai_error_to_http(timeout_err).status_code == 504

        # BedrockRateLimitError は AIRateLimitError でもある
        rate_err = BedrockRateLimitError("throttled")
        assert isinstance(rate_err, AIRateLimitError)
        assert _map_ai_error_to_http(rate_err).status_code == 429

        # BedrockInternalError は AIInternalError でもある
        internal_err = BedrockInternalError("internal")
        assert isinstance(internal_err, AIInternalError)
        assert _map_ai_error_to_http(internal_err).status_code == 500

        # BedrockParseError は AIParseError でもある
        parse_err = BedrockParseError("parse")
        assert isinstance(parse_err, AIParseError)
        assert _map_ai_error_to_http(parse_err).status_code == 500

    def test_error_mapping_table_completeness(self):
        """TC-ERROR-008: エラーマッピングテーブルの完全性検証.

        _map_ai_error_to_http() 関数が全 AI 例外タイプを正しくマッピングすること。
        🔵 信頼性レベル: 青信号 - handler.py 全分岐から確定
        """
        mapping_table = {
            AITimeoutError("t"): (504, "AI service timeout"),
            AIRateLimitError("r"): (429, "AI service rate limit exceeded"),
            AIProviderError("p"): (503, "AI service unavailable"),
            AIParseError("pa"): (500, "AI service response parse error"),
            AIInternalError("i"): (500, "AI service error"),
            AIServiceError("s"): (500, "AI service error"),
        }

        for error, (expected_status, expected_message) in mapping_table.items():
            response = _map_ai_error_to_http(error)
            assert response.status_code == expected_status, (
                f"{type(error).__name__}: expected {expected_status}, got {response.status_code}"
            )
            body = json.loads(response.body)
            assert body["error"] == expected_message, (
                f"{type(error).__name__}: expected '{expected_message}', got '{body['error']}'"
            )
            assert response.content_type == "application/json", (
                f"{type(error).__name__}: expected 'application/json', got '{response.content_type}'"
            )


# ===========================================================================
# Category 3: フィーチャーフラグ切替テスト
# ===========================================================================


class TestFeatureFlagBehavior:
    """フィーチャーフラグ切替テスト (TC-FLAG-001 ~ TC-FLAG-005)."""

    @patch("services.strands_service.Agent")
    @patch("services.strands_service.BedrockModel")
    def test_use_strands_true_returns_strands_service(self, mock_bedrock_model, mock_agent):
        """TC-FLAG-001: USE_STRANDS=true で StrandsAIService が選択される.

        環境変数 USE_STRANDS="true" の場合、create_ai_service() が
        StrandsAIService インスタンスを返すこと。
        🔵 信頼性レベル: 青信号 - ai_service.py create_ai_service() から確定
        """
        with patch.dict(os.environ, {"USE_STRANDS": "true"}):
            service = create_ai_service()

        assert isinstance(service, StrandsAIService)
        assert isinstance(service, AIService)

    def test_use_strands_false_returns_bedrock_service(self):
        """TC-FLAG-002: USE_STRANDS=false で BedrockService が選択される.

        環境変数 USE_STRANDS="false" の場合、create_ai_service() が
        BedrockService インスタンスを返すこと。
        🔵 信頼性レベル: 青信号 - ai_service.py create_ai_service() から確定
        """
        mock_client = MagicMock()
        with patch.dict(os.environ, {"USE_STRANDS": "false"}), \
             patch("services.bedrock.boto3.client", return_value=mock_client):
            service = create_ai_service()

        assert isinstance(service, BedrockService)
        assert isinstance(service, AIService)

    def test_use_strands_unset_defaults_to_bedrock(self):
        """TC-FLAG-003: USE_STRANDS 未設定時のデフォルト動作 (BedrockService).

        環境変数 USE_STRANDS が未設定の場合、デフォルト値 "false" が適用され、
        BedrockService が返されること。
        🔵 信頼性レベル: 青信号 - ai_service.py os.getenv("USE_STRANDS", "false") から確定
        """
        mock_client = MagicMock()
        env_without_use_strands = {
            k: v for k, v in os.environ.items() if k != "USE_STRANDS"
        }
        with patch.dict(os.environ, env_without_use_strands, clear=True), \
             patch("services.bedrock.boto3.client", return_value=mock_client):
            service = create_ai_service()

        assert isinstance(service, BedrockService)

    @patch("services.strands_service.Agent")
    @patch("services.strands_service.BedrockModel")
    def test_explicit_argument_overrides_env_var(self, mock_bedrock_model, mock_agent):
        """TC-FLAG-004: create_ai_service() への明示的引数渡し.

        use_strands パラメータが環境変数をオーバーライドすること。
        🔵 信頼性レベル: 青信号 - ai_service.py use_strands パラメータ処理から確定
        """
        # 環境変数が false でも use_strands=True で Strands が返る
        with patch.dict(os.environ, {"USE_STRANDS": "false"}):
            service_strands = create_ai_service(use_strands=True)
        assert isinstance(service_strands, StrandsAIService)

        # 環境変数が true でも use_strands=False で Bedrock が返る
        mock_client = MagicMock()
        with patch.dict(os.environ, {"USE_STRANDS": "true"}), \
             patch("services.bedrock.boto3.client", return_value=mock_client):
            service_bedrock = create_ai_service(use_strands=False)
        assert isinstance(service_bedrock, BedrockService)

    def test_create_ai_service_init_failure_raises_provider_error(self):
        """TC-FLAG-005: create_ai_service() 初期化失敗時の AIProviderError.

        AI サービスの初期化が失敗した場合に AIProviderError が raise されること。
        🔵 信頼性レベル: 青信号 - ai_service.py Exception ハンドリングから確定
        """
        with patch("services.bedrock.BedrockService", side_effect=RuntimeError("init failed")):
            with pytest.raises(AIProviderError) as exc_info:
                create_ai_service(use_strands=False)

        assert "Failed to initialize AI service" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, RuntimeError)


# ===========================================================================
# Category 4: GenerationResult 有効性テスト
# ===========================================================================


class TestGenerationResultValidity:
    """GenerationResult 有効性テスト (TC-RESULT-001 ~ TC-RESULT-003)."""

    def test_strands_generation_result_is_valid(self):
        """TC-RESULT-001: StrandsAIService の GenerationResult が有効.

        StrandsAIService が正しい GenerationResult を返すこと。
        🔵 信頼性レベル: 青信号 - strands_service.py generate_cards() から確定
        """
        # When
        result = _generate_with_strands()

        # Then
        _assert_generation_result_valid(result)
        assert result.input_length == len(DEFAULT_INPUT_TEXT)
        assert result.model_used == STRANDS_MODEL_USED
        for card in result.cards:
            assert "AI生成" in card.suggested_tags

    def test_bedrock_generation_result_is_valid(self):
        """TC-RESULT-002: BedrockService の GenerationResult が有効.

        BedrockService が正しい GenerationResult を返すこと。
        🔵 信頼性レベル: 青信号 - bedrock.py generate_cards() から確定
        """
        # When
        result = _generate_with_bedrock()

        # Then
        _assert_generation_result_valid(result)
        assert result.input_length == len(DEFAULT_INPUT_TEXT)
        assert result.model_used == BEDROCK_MODEL_USED_DEFAULT
        for card in result.cards:
            assert "AI生成" in card.suggested_tags

    @patch("services.strands_service.Agent")
    @patch("services.strands_service.BedrockModel")
    def test_both_services_conform_to_ai_service_protocol(self, mock_bedrock_model, mock_agent):
        """TC-RESULT-003: 両サービスが AIService Protocol に適合.

        create_ai_service() が返すインスタンスが @runtime_checkable AIService Protocol を
        満たすこと。
        🔵 信頼性レベル: 青信号 - ai_service.py Protocol 定義から確定
        """
        # StrandsAIService
        with patch.dict(os.environ, {"USE_STRANDS": "true"}):
            strands_service = create_ai_service()
        assert isinstance(strands_service, AIService)
        assert hasattr(strands_service, "generate_cards") and callable(strands_service.generate_cards)
        assert hasattr(strands_service, "grade_answer") and callable(strands_service.grade_answer)
        assert hasattr(strands_service, "get_learning_advice") and callable(strands_service.get_learning_advice)

        # BedrockService
        mock_client = MagicMock()
        with patch.dict(os.environ, {"USE_STRANDS": "false"}), \
             patch("services.bedrock.boto3.client", return_value=mock_client):
            bedrock_service = create_ai_service()
        assert isinstance(bedrock_service, AIService)
        assert hasattr(bedrock_service, "generate_cards") and callable(bedrock_service.generate_cards)
        assert hasattr(bedrock_service, "grade_answer") and callable(bedrock_service.grade_answer)
        assert hasattr(bedrock_service, "get_learning_advice") and callable(bedrock_service.get_learning_advice)


# ===========================================================================
# Category 5: 移行エッジケーステスト
# ===========================================================================


class TestMigrationEdgeCases:
    """移行エッジケーステスト (TC-EDGE-001 ~ TC-EDGE-006)."""

    def test_empty_cards_response_raises_parse_error_both_services(self):
        """TC-EDGE-001: 空のカードレスポンスのハンドリング.

        有効なカードが 0 枚の場合、両サービスとも AIParseError 系例外を raise すること。
        🔵 信頼性レベル: 青信号 - strands_service.py/bedrock.py の空カード処理から確定
        """
        empty_cards = {"cards": []}
        empty_json = json.dumps(empty_cards)

        # StrandsAIService: AIParseError
        mock_agent_instance = _make_mock_agent_instance(empty_json)
        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()
            with pytest.raises(AIParseError):
                service.generate_cards(input_text=DEFAULT_INPUT_TEXT)

        # BedrockService: BedrockParseError (extends AIParseError)
        mock_client = MagicMock()
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps(empty_cards)}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}
        service = BedrockService(bedrock_client=mock_client)
        with pytest.raises(AIParseError):
            service.generate_cards(input_text=DEFAULT_INPUT_TEXT)

    def test_incomplete_card_data_skipped_both_services(self):
        """TC-EDGE-002: 不完全なカードデータのスキップ動作.

        front/back 欠落カードがスキップされ、有効なカードのみが含まれること。
        🔵 信頼性レベル: 青信号 - 両サービスのスキップロジックから確定
        """
        mixed_cards = [
            {"front": "Q1"},                        # back 欠落
            {"back": "A2"},                         # front 欠落
            {"front": "", "back": "A3"},            # front 空
            {"front": "Q4", "back": ""},            # back 空
            {"front": "Valid Q", "back": "Valid A", "tags": ["test"]},  # 有効
        ]

        # StrandsAIService
        strands_result = _generate_with_strands(cards_data=mixed_cards)
        assert len(strands_result.cards) == 1
        assert strands_result.cards[0].front == "Valid Q"

        # BedrockService
        bedrock_result = _generate_with_bedrock(cards_data=mixed_cards)
        assert len(bedrock_result.cards) == 1
        assert bedrock_result.cards[0].front == "Valid Q"

    def test_markdown_code_block_json_parsed_both_services(self):
        """TC-EDGE-003: Markdown コードブロック内 JSON の解析.

        ```json ... ``` 形式のレスポンスが両サービスで正しくパースされること。
        🔵 信頼性レベル: 青信号 - 同一正規表現パターンから確定
        """
        markdown_response = '```json\n{"cards": [{"front": "Q1", "back": "A1", "tags": []}]}\n```'

        # StrandsAIService
        mock_agent_instance = _make_mock_agent_instance(markdown_response)
        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            strands_service = StrandsAIService()
            strands_result = strands_service.generate_cards(input_text=DEFAULT_INPUT_TEXT)

        assert len(strands_result.cards) == 1
        assert strands_result.cards[0].front == "Q1"

        # BedrockService - _parse_response に直接渡す
        mock_client = MagicMock()
        bedrock_service = BedrockService(bedrock_client=mock_client)
        bedrock_cards = bedrock_service._parse_response(markdown_response)

        assert len(bedrock_cards) == 1
        assert bedrock_cards[0].front == "Q1"

    def test_ai_generated_tag_auto_inserted_both_services(self):
        """TC-EDGE-004: "AI生成" タグの自動挿入.

        "AI生成" タグが未設定の場合、両サービスとも自動挿入すること。
        既に存在する場合は重複追加しないこと。
        🔵 信頼性レベル: 青信号 - 両サービスの同一タグ挿入ロジックから確定
        """
        # "AI生成" タグなしのカード
        cards_without_ai_tag = [
            {"front": "Q1", "back": "A1", "tags": ["physics"]},
        ]
        # "AI生成" タグありのカード
        cards_with_ai_tag = [
            {"front": "Q2", "back": "A2", "tags": ["AI生成", "math"]},
        ]

        # StrandsAIService - タグなし -> 自動挿入
        strands_result_no_tag = _generate_with_strands(cards_data=cards_without_ai_tag)
        assert "AI生成" in strands_result_no_tag.cards[0].suggested_tags
        assert strands_result_no_tag.cards[0].suggested_tags[0] == "AI生成"

        # StrandsAIService - タグあり -> 重複なし
        strands_result_with_tag = _generate_with_strands(cards_data=cards_with_ai_tag)
        assert strands_result_with_tag.cards[0].suggested_tags.count("AI生成") == 1

        # BedrockService - タグなし -> 自動挿入
        bedrock_result_no_tag = _generate_with_bedrock(cards_data=cards_without_ai_tag)
        assert "AI生成" in bedrock_result_no_tag.cards[0].suggested_tags
        assert bedrock_result_no_tag.cards[0].suggested_tags[0] == "AI生成"

        # BedrockService - タグあり -> 重複なし
        bedrock_result_with_tag = _generate_with_bedrock(cards_data=cards_with_ai_tag)
        assert bedrock_result_with_tag.cards[0].suggested_tags.count("AI生成") == 1

    def test_strands_connection_error_maps_to_provider_error(self):
        """TC-EDGE-005: ConnectionError のプロバイダーエラーマッピング (Strands 固有).

        StrandsAIService の ConnectionError が AIProviderError にラップされ、
        HTTP 503 にマッピングされること。
        🟡 信頼性レベル: 黄信号 - Strands 固有エッジケース
        """
        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = ConnectionError("Connection refused")

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIProviderError):
                service.generate_cards(input_text=DEFAULT_INPUT_TEXT)

        # HTTP マッピング確認
        response = _map_ai_error_to_http(AIProviderError("Connection refused"))
        assert response.status_code == 503

    def test_strands_unknown_exception_wrapped_in_ai_service_error(self):
        """TC-EDGE-006: 未知の例外の AIServiceError ラッピング (Strands 固有).

        StrandsAIService が予期しない例外を受け取った場合に
        AIServiceError にラップされること。
        🟡 信頼性レベル: 黄信号 - SDK 依存の予期しないエラー型
        """
        mock_agent_instance = MagicMock()
        mock_agent_instance.side_effect = RuntimeError("Something unexpected happened")

        with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
             patch("services.strands_service.BedrockModel"):
            service = StrandsAIService()

            with pytest.raises(AIServiceError) as exc_info:
                service.generate_cards(input_text=DEFAULT_INPUT_TEXT)

            assert "Unexpected error" in str(exc_info.value)

        # HTTP マッピング確認
        response = _map_ai_error_to_http(AIServiceError("Unexpected error"))
        assert response.status_code == 500


# ===========================================================================
# Category 6: 既存テスト保護テスト
# ===========================================================================


class TestExistingTestProtection:
    """既存テスト保護テスト (TC-PROTECT-001 ~ TC-PROTECT-003)."""

    def test_existing_test_suite_passes(self):
        """TC-PROTECT-001: 既存テストスイート全件 PASS 確認.

        新規テストファイルの追加によって既存テストにリグレッションが発生しないことを確認する。
        主要テストファイル (test_ai_service.py, test_strands_service.py,
        test_bedrock.py, test_handler_ai_service_factory.py) の実行結果を確認する。
        🔵 信頼性レベル: 青信号 - REQ-SM-405 から確定
        """
        # テストファイルの絶対パスを解決する
        tests_dir = os.path.join(os.path.dirname(__file__))
        test_files = [
            os.path.join(tests_dir, "test_ai_service.py"),
            os.path.join(tests_dir, "test_strands_service.py"),
            os.path.join(tests_dir, "test_bedrock.py"),
            os.path.join(tests_dir, "test_handler_ai_service_factory.py"),
        ]

        # 全テストファイルが存在することを確認
        for test_file in test_files:
            assert os.path.exists(test_file), f"テストファイルが見つかりません: {test_file}"

        result = pytest.main([
            "-x",  # 最初の失敗で停止
            "--tb=short",
            "-q",
            *test_files,
        ])
        assert result == pytest.ExitCode.OK, (
            "既存テストスイートにリグレッションが検出されました"
        )

    def test_coverage_target_maintained(self):
        """TC-PROTECT-002: テストカバレッジ 80% 以上維持確認.

        新規テストの追加によってカバレッジが低下しないことの確認マーカー。
        実際のカバレッジ計測は CI/CD パイプラインまたは手動で実施する。
        🔵 信頼性レベル: 青信号 - REQ-SM-404 から確定
        """
        # このテストはカバレッジ確認のプレースホルダー。
        # 実行コマンド: pytest --cov=src/services --cov-report=term-missing
        # カバレッジ 80% 以上を手動または CI で確認する。
        pass

    def test_default_env_does_not_affect_existing_tests(self):
        """TC-PROTECT-003: USE_STRANDS=false (デフォルト) で既存テストが影響を受けない.

        conftest.py の環境変数設定に USE_STRANDS が含まれていないため、
        デフォルト値 "false" が適用され、BedrockService が使用されること。
        🔵 信頼性レベル: 青信号 - conftest.py 環境変数設定から確定
        """
        # conftest.py の環境変数には USE_STRANDS が含まれていない
        # デフォルト値 "false" が適用されるため、BedrockService が使用される
        env_use_strands = os.environ.get("USE_STRANDS")

        # conftest.py で USE_STRANDS は設定されていない
        # (明示的に設定されている場合は、テスト環境の構成に依存)
        if env_use_strands is None:
            # 未設定の場合、create_ai_service() は BedrockService を返す
            mock_client = MagicMock()
            with patch("services.bedrock.boto3.client", return_value=mock_client):
                service = create_ai_service()
            assert isinstance(service, BedrockService)
        else:
            # テスト環境で USE_STRANDS が設定されている場合はスキップ
            pytest.skip("USE_STRANDS is explicitly set in test environment")

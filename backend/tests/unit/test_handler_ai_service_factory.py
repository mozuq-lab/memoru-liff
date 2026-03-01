"""Unit tests for handler.py AIServiceFactory integration and template.yaml/env.json updates.

TASK-0056: handler.py AIServiceFactory 統合 + template.yaml 更新
対象テストケース: TC-056-001 〜 TC-056-027 (カテゴリ A〜G 全27ケース)

テストカテゴリ:
  A: AIServiceFactory 統合テスト (TC-056-001〜002)
  B: エラーマッピングテスト (TC-056-003〜009)
  C: generate_cards エンドポイント互換性テスト (TC-056-010〜013)
  D: スタブハンドラーテスト (TC-056-014〜015)
  E: template.yaml 設定検証テスト (TC-056-016〜023)
  F: env.json 設定検証テスト (TC-056-024〜025)
  G: Bedrock 例外階層経由マッピングテスト (TC-056-026〜027)

注意事項:
  - 全メソッドは同期 (pytest.mark.asyncio 不要)
  - 既存 conftest.py フィクスチャ (api_gateway_event, lambda_context) を使用
  - テストファイルは新規作成 (既存テストは変更しない)
  - template.yaml/env.json テスト (カテゴリ E/F) はファイルを直接読み込む
"""

import json
import os

import pytest
import yaml
from unittest.mock import patch, MagicMock


# CloudFormation 固有タグ (!Ref, !Sub, !If, !Equals, !GetAtt 等) を
# yaml.safe_load では処理できないため、カスタムローダーを定義する
class _CFnLoader(yaml.SafeLoader):
    """CloudFormation テンプレートを読み込むための YAML ローダー.

    !Ref, !Sub, !If, !Equals 等の CloudFormation 固有タグをそのまま文字列や
    リスト・辞書として読み込む。
    """
    pass


def _cfn_tag_constructor(loader, tag_suffix, node):
    """CloudFormation タグを汎用的に処理するコンストラクタ."""
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node)


_CFnLoader.add_multi_constructor("!", _cfn_tag_constructor)


# ==============================================================================
# カテゴリ A: AIServiceFactory 統合テスト
# ==============================================================================


class TestFactoryIntegration:
    """カテゴリ A: generate_cards エンドポイントが create_ai_service() ファクトリを使用することを確認."""

    def test_generate_cards_uses_create_ai_service_factory(self, api_gateway_event, lambda_context):
        """TC-056-001: generate_cards エンドポイントのファクトリ呼び出し確認.

        【テスト目的】: generate_cards が create_ai_service() ファクトリを使用することを確認
        【テスト内容】: POST /cards/generate リクエストを送信し、ファクトリが呼ばれることを検証
        【期待される動作】: create_ai_service() が 1 回呼ばれ、200 レスポンスが返る
        🔵 信頼性レベル: 青信号 - 要件定義書 2.1 節「グローバル変数変更」「generate_cards エンドポイント改修」から確定
        """
        # Given
        # 【テストデータ準備】: 有効なカード生成リクエストを作成
        event = api_gateway_event(
            method="POST",
            path="/cards/generate",
            body={
                "input_text": "テスト用の学習テキストです。十分な長さが必要です。",
                "card_count": 3,
                "difficulty": "medium",
                "language": "ja",
            },
            user_id="test-user-123",
        )

        # When
        # 【実際の処理実行】: handler を通じて generate_cards エンドポイントを呼び出す
        with patch("api.handlers.ai_handler.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.generate_cards.return_value = MagicMock(
                cards=[MagicMock(front="Q1", back="A1", suggested_tags=["tag1"])],
                input_length=30,
                model_used="test-model",
                processing_time_ms=500,
            )
            mock_factory.return_value = mock_service

            from api.handler import handler
            response = handler(event, lambda_context)

        # Then
        # 【結果検証】: ファクトリが呼ばれ、正常レスポンスが返ること
        mock_factory.assert_called_once()  # 【検証項目】: create_ai_service() が 1 回呼ばれる 🔵
        assert response["statusCode"] == 200  # 【検証項目】: 200 OK が返る 🔵
        body = json.loads(response["body"])
        assert "generated_cards" in body  # 【検証項目】: レスポンスに generated_cards が含まれる 🔵

    def test_generate_cards_passes_correct_args_to_ai_service(self, api_gateway_event, lambda_context):
        """TC-056-002: ファクトリ生成サービスへの引数伝播確認.

        【テスト目的】: ファクトリから返されたサービスに正しい引数が渡されることを確認
        【テスト内容】: リクエストパラメータがサービスの generate_cards() に正しく伝播されることを検証
        【期待される動作】: input_text, card_count, difficulty, language が正しく伝播する
        🔵 信頼性レベル: 青信号 - 要件定義書 2.1 節「generate_cards エンドポイント改修」から確定
        """
        # Given
        # 【テストデータ準備】: 特定のパラメータ値でリクエストを作成（伝播を確認できる特定値）
        event = api_gateway_event(
            method="POST",
            path="/cards/generate",
            body={
                "input_text": "量子力学の基礎について学びましょう。原子の構造と電子の振る舞い。",
                "card_count": 5,
                "difficulty": "hard",
                "language": "en",
            },
            user_id="test-user-456",
        )

        # When
        # 【実際の処理実行】: create_ai_service をモックして引数伝播を検証
        with patch("api.handlers.ai_handler.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.generate_cards.return_value = MagicMock(
                cards=[MagicMock(front="Q", back="A", suggested_tags=[])],
                input_length=38,
                model_used="test-model",
                processing_time_ms=100,
            )
            mock_factory.return_value = mock_service

            from api.handler import handler
            handler(event, lambda_context)

        # Then
        # 【結果検証】: サービスの generate_cards() が正しい引数で呼ばれたこと
        mock_service.generate_cards.assert_called_once_with(
            input_text="量子力学の基礎について学びましょう。原子の構造と電子の振る舞い。",
            card_count=5,
            difficulty="hard",
            language="en",
        )  # 【検証項目】: 各パラメータがリクエストボディの値と一致する 🔵


# ==============================================================================
# カテゴリ B: エラーマッピングテスト
# ==============================================================================


class TestErrorMapping:
    """カテゴリ B: _map_ai_error_to_http() エラーマッピングテスト."""

    def test_map_ai_error_timeout_returns_504(self):
        """TC-056-003: AITimeoutError → HTTP 504 マッピング.

        【テスト目的】: AITimeoutError が HTTP 504 にマッピングされることを確認
        【テスト内容】: _map_ai_error_to_http() に AITimeoutError を渡して結果を検証
        【期待される動作】: 504 ステータスと "AI service timeout" メッセージ
        🔵 信頼性レベル: 青信号 - 要件定義書 2.1 節「_map_ai_error_to_http() ヘルパー関数」仕様表から確定
        """
        # Given
        # 【テストデータ準備】: AITimeoutError インスタンスを作成
        from api.handler import _map_ai_error_to_http
        from services.ai_service import AITimeoutError

        error = AITimeoutError("test timeout")

        # When
        # 【実際の処理実行】: エラーマッピング関数を呼び出す
        response = _map_ai_error_to_http(error)

        # Then
        # 【結果検証】: ステータスコードとエラーメッセージ
        assert response.status_code == 504  # 【検証項目】: HTTP 504 Gateway Timeout 🔵
        body = json.loads(response.body)
        assert body["error"] == "AI service timeout"  # 【検証項目】: エラーメッセージの完全一致 🔵

    def test_map_ai_error_rate_limit_returns_429(self):
        """TC-056-004: AIRateLimitError → HTTP 429 マッピング.

        【テスト目的】: AIRateLimitError が HTTP 429 にマッピングされることを確認
        【期待される動作】: 429 ステータスと "AI service rate limit exceeded" メッセージ
        🔵 信頼性レベル: 青信号 - 要件定義書 2.1 節「_map_ai_error_to_http() ヘルパー関数」から確定
        """
        # Given
        from api.handler import _map_ai_error_to_http
        from services.ai_service import AIRateLimitError

        error = AIRateLimitError("rate limit hit")

        # When
        response = _map_ai_error_to_http(error)

        # Then
        assert response.status_code == 429  # 【検証項目】: HTTP 429 Too Many Requests 🔵
        body = json.loads(response.body)
        assert body["error"] == "AI service rate limit exceeded"  # 🔵

    def test_map_ai_error_provider_returns_503(self):
        """TC-056-005: AIProviderError → HTTP 503 マッピング.

        【テスト目的】: AIProviderError が HTTP 503 にマッピングされることを確認
        【期待される動作】: 503 ステータスと "AI service unavailable" メッセージ
        🔵 信頼性レベル: 青信号 - 要件定義書 2.1 節「_map_ai_error_to_http() ヘルパー関数」から確定
        """
        # Given
        from api.handler import _map_ai_error_to_http
        from services.ai_service import AIProviderError

        error = AIProviderError("provider down")

        # When
        response = _map_ai_error_to_http(error)

        # Then
        assert response.status_code == 503  # 【検証項目】: HTTP 503 Service Unavailable 🔵
        body = json.loads(response.body)
        assert body["error"] == "AI service unavailable"  # 🔵

    def test_map_ai_error_parse_returns_500(self):
        """TC-056-006: AIParseError → HTTP 500 マッピング.

        【テスト目的】: AIParseError が HTTP 500 にマッピングされることを確認
        【期待される動作】: 500 ステータスと "AI service response parse error" メッセージ
        🔵 信頼性レベル: 青信号 - 要件定義書 2.1 節「_map_ai_error_to_http() ヘルパー関数」から確定
        """
        # Given
        from api.handler import _map_ai_error_to_http
        from services.ai_service import AIParseError

        error = AIParseError("invalid json")

        # When
        response = _map_ai_error_to_http(error)

        # Then
        assert response.status_code == 500  # 【検証項目】: HTTP 500 Internal Server Error 🔵
        body = json.loads(response.body)
        assert body["error"] == "AI service response parse error"  # 🔵

    def test_map_ai_error_internal_returns_500(self):
        """TC-056-007: AIInternalError → HTTP 500 マッピング.

        【テスト目的】: AIInternalError が HTTP 500 にマッピングされることを確認
        【期待される動作】: 500 ステータスと "AI service error" メッセージ
        🔵 信頼性レベル: 青信号 - 要件定義書 2.1 節「_map_ai_error_to_http() ヘルパー関数」から確定
        """
        # Given
        from api.handler import _map_ai_error_to_http
        from services.ai_service import AIInternalError

        error = AIInternalError("internal failure")

        # When
        response = _map_ai_error_to_http(error)

        # Then
        assert response.status_code == 500  # 【検証項目】: HTTP 500 🔵
        body = json.loads(response.body)
        assert body["error"] == "AI service error"  # 🔵

    def test_map_ai_error_generic_fallback_returns_500(self):
        """TC-056-008: AIServiceError 汎用 → HTTP 500 フォールバック.

        【テスト目的】: AIServiceError（基底クラス）が汎用フォールバックとして HTTP 500 を返すことを確認
        【テスト内容】: 基底クラスを直接渡した場合に 500 の汎用エラーが返ること
        【期待される動作】: 500 ステータスと "AI service error" メッセージ
        🔵 信頼性レベル: 青信号 - 要件定義書 2.1 節「_map_ai_error_to_http() ヘルパー関数」の汎用フォールバック行から確定
        """
        # Given
        from api.handler import _map_ai_error_to_http
        from services.ai_service import AIServiceError

        error = AIServiceError("unknown ai error")

        # When
        response = _map_ai_error_to_http(error)

        # Then
        assert response.status_code == 500  # 【検証項目】: HTTP 500 フォールバック 🔵
        body = json.loads(response.body)
        assert body["error"] == "AI service error"  # 🔵

    def test_map_ai_error_all_responses_are_json(self):
        """TC-056-009: エラーレスポンスの Content-Type 確認.

        【テスト目的】: 全例外タイプで Content-Type が application/json であることを確認
        【テスト内容】: 全 6 種類の例外クラスに対してレスポンスの Content-Type を検証
        【期待される動作】: 全例外タイプで Content-Type が application/json
        🔵 信頼性レベル: 青信号 - 要件定義書 2.1 節「レスポンスフォーマット」から確定
        """
        # Given
        from api.handler import _map_ai_error_to_http
        from services.ai_service import (
            AIServiceError, AITimeoutError, AIRateLimitError,
            AIProviderError, AIParseError, AIInternalError,
        )

        errors = [
            AITimeoutError("t"),
            AIRateLimitError("r"),
            AIProviderError("p"),
            AIParseError("pa"),
            AIInternalError("i"),
            AIServiceError("s"),
        ]

        # When / Then
        # 【結果検証】: 各例外タイプのレスポンス Content-Type が application/json
        for error in errors:
            response = _map_ai_error_to_http(error)
            # 【検証項目】: Content-Type が application/json
            assert response.content_type == "application/json", (
                f"{type(error).__name__} response has wrong content_type: {response.content_type}"
            )  # 🔵
            # 【検証項目】: body が有効な JSON としてパース可能で "error" キーを含む
            body = json.loads(response.body)
            assert "error" in body  # 🔵


# ==============================================================================
# カテゴリ C: generate_cards エンドポイント互換性テスト
# ==============================================================================


class TestGenerateCardsCompatibility:
    """カテゴリ C: ファクトリパターン移行後の generate_cards エンドポイント互換性テスト."""

    def test_generate_cards_response_format_backward_compatible(self, api_gateway_event, lambda_context):
        """TC-056-010: generate_cards レスポンス後方互換性.

        【テスト目的】: ファクトリ移行後も generate_cards のレスポンス形式が変わらないことを確認
        【テスト内容】: 成功時のレスポンスが generated_cards + generation_info の構造であることを検証
        【期待される動作】: generated_cards 配列と generation_info オブジェクトを含む 200 レスポンス
        🔵 信頼性レベル: 青信号 - 要件定義書 2.1 節「generate_cards エンドポイント改修」出力仕様、REQ-SM-402 から確定
        """
        # Given
        # 【テストデータ準備】: 2 枚のカードを返すモックサービスを用意
        event = api_gateway_event(
            method="POST",
            path="/cards/generate",
            body={
                "input_text": "The mitochondria is the powerhouse of the cell. ATP synthesis.",
                "card_count": 2,
                "difficulty": "easy",
                "language": "en",
            },
            user_id="test-user-789",
        )

        with patch("api.handlers.ai_handler.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.generate_cards.return_value = MagicMock(
                cards=[
                    MagicMock(front="What is mitochondria?", back="Powerhouse of the cell", suggested_tags=["biology"]),
                    MagicMock(front="What is ATP?", back="Adenosine triphosphate", suggested_tags=["biology", "chemistry"]),
                ],
                input_length=64,
                model_used="anthropic.claude-3-haiku-20240307-v1:0",
                processing_time_ms=1200,
            )
            mock_factory.return_value = mock_service

            # When
            # 【実際の処理実行】: generate_cards エンドポイントを呼び出す
            from api.handler import handler
            response = handler(event, lambda_context)

        # Then
        # 【結果検証】: レスポンス構造の後方互換性
        assert response["statusCode"] == 200  # 🔵
        body = json.loads(response["body"])

        # 【検証項目】: generated_cards 配列の構造
        assert "generated_cards" in body  # 🔵
        assert len(body["generated_cards"]) == 2  # 🔵
        card = body["generated_cards"][0]
        assert "front" in card  # 🔵
        assert "back" in card  # 🔵
        assert "suggested_tags" in card  # 🔵

        # 【検証項目】: generation_info オブジェクトの構造
        assert "generation_info" in body  # 🔵
        info = body["generation_info"]
        assert info["input_length"] == 64  # 🔵
        assert info["model_used"] == "anthropic.claude-3-haiku-20240307-v1:0"  # 🔵
        assert info["processing_time_ms"] == 1200  # 🔵

    def test_generate_cards_handles_ai_timeout_error(self, api_gateway_event, lambda_context):
        """TC-056-011: generate_cards での AITimeoutError ハンドリング.

        【テスト目的】: generate_cards が AITimeoutError を HTTP 504 に変換することを確認
        【テスト内容】: モックサービスが AITimeoutError を送出した場合の動作を検証
        【期待される動作】: _map_ai_error_to_http() を通じて 504 レスポンスが返る
        🔵 信頼性レベル: 青信号 - 要件定義書 4.2 節 EC-01 から確定
        """
        # Given
        event = api_gateway_event(
            method="POST",
            path="/cards/generate",
            body={
                "input_text": "テスト用テキストです。十分な長さを確保しています。",
                "card_count": 3,
                "difficulty": "medium",
                "language": "ja",
            },
        )

        with patch("api.handlers.ai_handler.create_ai_service") as mock_factory:
            from services.ai_service import AITimeoutError
            mock_service = MagicMock()
            mock_service.generate_cards.side_effect = AITimeoutError("timeout")
            mock_factory.return_value = mock_service

            # When
            # 【実際の処理実行】: AITimeoutError が発生するシナリオでハンドラを呼び出す
            from api.handler import handler
            response = handler(event, lambda_context)

        # Then
        assert response["statusCode"] == 504  # 【検証項目】: タイムアウトで 504 が返る 🔵

    def test_generate_cards_handles_ai_rate_limit_error(self, api_gateway_event, lambda_context):
        """TC-056-012: generate_cards での AIRateLimitError ハンドリング.

        【テスト目的】: generate_cards が AIRateLimitError を HTTP 429 に変換することを確認
        🔵 信頼性レベル: 青信号 - 要件定義書 4.2 節 EC-02 から確定
        """
        # Given
        event = api_gateway_event(
            method="POST",
            path="/cards/generate",
            body={
                "input_text": "テスト用テキストです。十分な長さを確保しています。",
                "card_count": 3,
                "difficulty": "medium",
                "language": "ja",
            },
        )

        with patch("api.handlers.ai_handler.create_ai_service") as mock_factory:
            from services.ai_service import AIRateLimitError
            mock_service = MagicMock()
            mock_service.generate_cards.side_effect = AIRateLimitError("rate limit")
            mock_factory.return_value = mock_service

            # When
            from api.handler import handler
            response = handler(event, lambda_context)

        # Then
        assert response["statusCode"] == 429  # 【検証項目】: レート制限で 429 が返る 🔵

    def test_generate_cards_handles_ai_provider_error(self, api_gateway_event, lambda_context):
        """TC-056-013: generate_cards での AIProviderError ハンドリング.

        【テスト目的】: generate_cards が AIProviderError を HTTP 503 に変換することを確認
        【テスト内容】: create_ai_service() の初期化失敗シナリオを含む
        🔵 信頼性レベル: 青信号 - 要件定義書 4.2 節 EC-03、4.3 節 EDGE-02 から確定
        """
        # Given
        event = api_gateway_event(
            method="POST",
            path="/cards/generate",
            body={
                "input_text": "テスト用テキストです。十分な長さを確保しています。",
                "card_count": 3,
                "difficulty": "medium",
                "language": "ja",
            },
        )

        with patch("api.handlers.ai_handler.create_ai_service") as mock_factory:
            from services.ai_service import AIProviderError
            # 【テストデータ準備】: ファクトリ自体が初期化失敗する AIProviderError を送出
            mock_factory.side_effect = AIProviderError("Failed to initialize AI service")

            # When
            from api.handler import handler
            response = handler(event, lambda_context)

        # Then
        assert response["statusCode"] == 503  # 【検証項目】: プロバイダーエラーで 503 が返る 🔵


# ==============================================================================
# カテゴリ D: スタブハンドラーテスト
# ==============================================================================


class TestStubHandlers:
    """カテゴリ D: grade_ai_handler 実装確認。

    TC-056-015 (advice_handler スタブの 501 テスト) は TASK-0062 で advice_handler が
    本実装されたため削除済み。
    """

    def test_grade_ai_handler_is_implemented(self, lambda_context):
        """TC-056-014: grade_ai_handler が 501 スタブではなく本実装であることを確認.

        【テスト目的】: TASK-0060 実装後、grade_ai_handler がスタブ(501)を返さないことを確認
        【テスト内容】: 認証なしイベントを渡して 401 が返ること（501 ではないこと）を検証
        【期待される動作】: statusCode != 501（認証なしなので 401 Unauthorized が返る）
        🔵 信頼性レベル: 青信号 - TASK-0060 で grade_ai_handler 本実装済み
        """
        # Given
        # 【テストデータ準備】: 認証情報なしの Lambda イベント
        event = {
            "version": "2.0",
            "routeKey": "POST /reviews/{cardId}/grade-ai",
            "rawPath": "/reviews/card-123/grade-ai",
            "pathParameters": {"cardId": "card-123"},
            "requestContext": {
                "http": {"method": "POST"},
                "authorizer": {},
            },
        }

        # When
        # 【実際の処理実行】: grade_ai_handler を直接呼び出す
        from api.handler import grade_ai_handler
        response = grade_ai_handler(event, lambda_context)

        # Then
        # 【結果検証】: スタブ(501)ではなく本実装のレスポンスが返ること
        assert response["statusCode"] != 501  # 【検証項目】: スタブ 501 が返らないこと 🔵
        assert response["headers"]["Content-Type"] == "application/json"  # 🔵
        # 認証情報なしなので 401 Unauthorized が返ることを確認
        assert response["statusCode"] == 401  # 🔵


# ==============================================================================
# カテゴリ E: template.yaml 設定検証テスト
# ==============================================================================


class TestTemplateYamlConfig:
    """カテゴリ E: template.yaml の設定検証テスト (ファイルを直接読み込んでパース)."""

    TEMPLATE_PATH = os.path.join(
        os.path.dirname(__file__), "..", "..", "template.yaml"
    )

    def _load_template(self) -> dict:
        """template.yaml を読み込んで YAML パースした辞書を返す.

        CloudFormation 固有タグ (!Ref, !Sub, !If, !Equals 等) を含むため、
        _CFnLoader を使用してパースする。
        """
        with open(self.TEMPLATE_PATH, "r") as f:
            return yaml.load(f, Loader=_CFnLoader)

    def test_template_yaml_use_strands_parameter(self):
        """TC-056-016: UseStrands パラメータ定義の確認.

        【テスト目的】: UseStrands パラメータが正しく定義されていることを確認
        【テスト内容】: template.yaml の Parameters セクションに UseStrands が含まれること
        【期待される動作】: Type=String, Default="false", AllowedValues=["true", "false"]
        🔵 信頼性レベル: 青信号 - 要件定義書 2.2 節「UseStrands パラメータ追加」、REQ-SM-103 から確定
        """
        # Given
        # 【テストデータ準備】: template.yaml を読み込む
        template = self._load_template()

        # Then
        # 【結果検証】: UseStrands パラメータの定義を確認
        assert "UseStrands" in template["Parameters"]  # 【検証項目】: パラメータが存在する 🔵
        param = template["Parameters"]["UseStrands"]
        assert param["Type"] == "String"  # 【検証項目】: Type が String 🔵
        assert param["Default"] == "false"  # 【検証項目】: デフォルト値が "false" 🔵
        assert "true" in param["AllowedValues"]  # 【検証項目】: "true" が許可値に含まれる 🔵
        assert "false" in param["AllowedValues"]  # 【検証項目】: "false" が許可値に含まれる 🔵

    def test_template_yaml_should_use_strands_condition(self):
        """TC-056-017: ShouldUseStrands コンディション定義の確認.

        【テスト目的】: ShouldUseStrands コンディションが定義されていることを確認
        【テスト内容】: Conditions セクションに ShouldUseStrands が存在すること
        🔵 信頼性レベル: 青信号 - 要件定義書 2.2 節「ShouldUseStrands コンディション追加」から確定
        """
        # Given
        template = self._load_template()

        # Then
        assert "Conditions" in template  # 【検証項目】: Conditions セクションが存在する 🔵
        assert "ShouldUseStrands" in template["Conditions"]  # 【検証項目】: コンディションが存在する 🔵

    def test_template_yaml_global_timeout_is_60(self):
        """TC-056-018: Global タイムアウトが 120 秒に設定されていること.

        【テスト目的】: Lambda のグローバルタイムアウトが 120 秒であることを確認
        【テスト内容】: Globals.Function.Timeout が 120 であること
        【期待される動作】: デッキ管理機能追加後のタイムアウト設定
        🔵 信頼性レベル: 青信号 - 現行 template.yaml の実測値から確定
        """
        # Given
        template = self._load_template()

        # Then
        assert template["Globals"]["Function"]["Timeout"] == 120  # 【検証項目】: タイムアウトが 120 秒 🔵

    def test_template_yaml_globals_have_use_strands_env_var(self):
        """TC-056-019: USE_STRANDS 環境変数が Globals に定義されていること.

        【テスト目的】: Globals 環境変数に USE_STRANDS が定義されていることを確認
        【テスト内容】: Globals.Function.Environment.Variables に USE_STRANDS が含まれること
        🔵 信頼性レベル: 青信号 - 要件定義書 2.2 節「Globals 環境変数追加」から確定
        """
        # Given
        template = self._load_template()

        # Then
        # 【結果検証】: Globals 環境変数の確認
        env_vars = template["Globals"]["Function"]["Environment"]["Variables"]
        assert "USE_STRANDS" in env_vars  # 【検証項目】: USE_STRANDS が定義されている 🔵

    def test_template_yaml_new_lambda_functions_defined(self):
        """TC-056-020: 新 Lambda 関数が template.yaml に定義されていること.

        【テスト目的】: ReviewsGradeAiFunction と AdviceFunction が正しく定義されていることを確認
        【テスト内容】: Resources セクションに両関数が存在し、適切なプロパティを持つ
        【期待される動作】: Handler, Timeout=60, MemorySize=512 が設定されている
        🔵 信頼性レベル: 青信号 - 要件定義書 2.2 節「新 API ルート（Lambda 関数）追加」仕様表から確定
        """
        # Given
        template = self._load_template()
        resources = template["Resources"]

        # Then
        # 【検証項目】: ReviewsGradeAiFunction の定義
        assert "ReviewsGradeAiFunction" in resources  # 🔵
        grade_fn = resources["ReviewsGradeAiFunction"]["Properties"]
        assert grade_fn["Handler"] == "api.handler.grade_ai_handler"  # 🔵
        assert grade_fn["Timeout"] == 60  # 🔵
        assert grade_fn["MemorySize"] == 512  # 🔵

        # 【検証項目】: AdviceFunction の定義
        assert "AdviceFunction" in resources  # 🔵
        advice_fn = resources["AdviceFunction"]["Properties"]
        assert advice_fn["Handler"] == "api.handler.advice_handler"  # 🔵
        assert advice_fn["Timeout"] == 60  # 🔵
        assert advice_fn["MemorySize"] == 512  # 🔵

    def test_template_yaml_new_lambda_event_routes(self):
        """TC-056-021: 新 Lambda 関数のイベントルートが正しいこと.

        【テスト目的】: 新 Lambda 関数の API ルートが正しいことを確認
        【テスト内容】: grade-ai と advice の Path, Method, Type を検証
        【期待される動作】: grade-ai は POST /reviews/{cardId}/grade-ai, advice は GET /advice
        🔵 信頼性レベル: 青信号 - 要件定義書 2.2 節「ReviewsGradeAiFunction」「AdviceFunction」仕様表から確定
        """
        # Given
        template = self._load_template()
        resources = template["Resources"]

        # Then
        # 【検証項目】: grade-ai ルート
        grade_events = resources["ReviewsGradeAiFunction"]["Properties"]["Events"]
        grade_event_key = list(grade_events.keys())[0]
        grade_event = grade_events[grade_event_key]
        assert grade_event["Type"] == "HttpApi"  # 🔵
        assert grade_event["Properties"]["Path"] == "/reviews/{cardId}/grade-ai"  # 🔵
        assert grade_event["Properties"]["Method"].upper() == "POST"  # 🔵

        # 【検証項目】: advice ルート
        advice_events = resources["AdviceFunction"]["Properties"]["Events"]
        advice_event_key = list(advice_events.keys())[0]
        advice_event = advice_events[advice_event_key]
        assert advice_event["Type"] == "HttpApi"  # 🔵
        assert advice_event["Properties"]["Path"] == "/advice"  # 🔵
        assert advice_event["Properties"]["Method"].upper() == "GET"  # 🔵

    def test_template_yaml_new_log_groups(self):
        """TC-056-022: 新 Lambda 関数の LogGroup が定義されていること.

        【テスト目的】: 新 Lambda 関数の CloudWatch LogGroup が定義されていることを確認
        【テスト内容】: ReviewsGradeAiFunctionLogGroup と AdviceFunctionLogGroup の存在と型を検証
        🔵 信頼性レベル: 青信号 - 要件定義書 2.2 節「LogGroups」・既存パターン (ApiFunctionLogGroup) から確定
        """
        # Given
        template = self._load_template()
        resources = template["Resources"]

        # Then
        # 【検証項目】: ReviewsGradeAiFunctionLogGroup の定義
        assert "ReviewsGradeAiFunctionLogGroup" in resources  # 🔵
        assert resources["ReviewsGradeAiFunctionLogGroup"]["Type"] == "AWS::Logs::LogGroup"  # 🔵

        # 【検証項目】: AdviceFunctionLogGroup の定義
        assert "AdviceFunctionLogGroup" in resources  # 🔵
        assert resources["AdviceFunctionLogGroup"]["Type"] == "AWS::Logs::LogGroup"  # 🔵

    def test_template_yaml_new_outputs(self):
        """TC-056-023: 新 Lambda 関数の Outputs が定義されていること.

        【テスト目的】: 新 Lambda 関数の CloudFormation Outputs が定義されていることを確認
        【テスト内容】: ReviewsGradeAiFunctionArn と AdviceFunctionArn の存在を検証
        🔵 信頼性レベル: 青信号 - 要件定義書 2.2 節「Outputs」・既存パターン (ApiFunctionArn) から確定
        """
        # Given
        template = self._load_template()

        # Then
        outputs = template["Outputs"]
        assert "ReviewsGradeAiFunctionArn" in outputs  # 🔵
        assert "AdviceFunctionArn" in outputs  # 🔵


# ==============================================================================
# カテゴリ F: env.json 設定検証テスト
# ==============================================================================


class TestEnvJsonConfig:
    """カテゴリ F: env.json の設定検証テスト (ファイルを直接読み込んでパース)."""

    ENV_JSON_PATH = os.path.join(
        os.path.dirname(__file__), "..", "..", "env.json"
    )

    def _load_env_json(self) -> dict:
        """env.json を読み込んで JSON パースした辞書を返す."""
        with open(self.ENV_JSON_PATH, "r") as f:
            return json.load(f)

    def test_env_json_existing_functions_have_new_vars(self):
        """TC-056-024: 既存関数に USE_STRANDS, OLLAMA_HOST, OLLAMA_MODEL が追加されていること.

        【テスト目的】: 既存関数に新環境変数が追加されていることを確認
        【テスト内容】: ApiFunction, LineWebhookFunction, DuePushJobFunction に新変数が存在することを検証
        【期待される動作】: 各関数に USE_STRANDS, OLLAMA_HOST, OLLAMA_MODEL が設定されている
        🔵 信頼性レベル: 青信号 - 現行 env.json の実測値から確定
        """
        # Given
        # 【テストデータ準備】: env.json を読み込む
        env_config = self._load_env_json()

        # Then
        # 【結果検証】: 既存 3 関数に新環境変数が存在すること
        for func_name in ["ApiFunction", "LineWebhookFunction", "DuePushJobFunction"]:
            assert func_name in env_config, f"{func_name} が env.json に存在しない"  # 🔵
            func_vars = env_config[func_name]
            assert "USE_STRANDS" in func_vars, f"{func_name} に USE_STRANDS がない"  # 🔵
            assert "OLLAMA_HOST" in func_vars, f"{func_name} に OLLAMA_HOST がない"  # 🔵
            assert "OLLAMA_MODEL" in func_vars, f"{func_name} に OLLAMA_MODEL がない"  # 🔵

    def test_env_json_new_functions_defined(self):
        """TC-056-025: 新規関数（ReviewsGradeAiFunction, AdviceFunction）が env.json に定義されていること.

        【テスト目的】: 新規関数が env.json に正しく定義されていることを確認
        【テスト内容】: 両関数に必要な全環境変数が設定されていることを検証
        【期待される動作】: ENVIRONMENT, テーブル名, KEYCLOAK_ISSUER 等の全変数が設定されている
        🔵 信頼性レベル: 青信号 - 要件定義書 2.3 節「新規関数の環境変数定義」から確定
        """
        # Given
        env_config = self._load_env_json()

        # Then
        # 【テストデータ準備】: 必須環境変数の一覧
        required_vars = [
            "ENVIRONMENT", "USERS_TABLE", "CARDS_TABLE", "REVIEWS_TABLE",
            "KEYCLOAK_ISSUER", "BEDROCK_MODEL_ID", "LOG_LEVEL",
            "DYNAMODB_ENDPOINT_URL", "AWS_ENDPOINT_URL",
            "USE_STRANDS", "OLLAMA_HOST", "OLLAMA_MODEL",
        ]

        for func_name in ["ReviewsGradeAiFunction", "AdviceFunction"]:
            assert func_name in env_config, f"{func_name} が env.json に存在しない"  # 🔵
            func_vars = env_config[func_name]
            for var_name in required_vars:
                assert var_name in func_vars, (
                    f"{func_name} に {var_name} がない"
                )  # 🔵

            # 【検証項目】: USE_STRANDS の設定値
            assert func_vars["USE_STRANDS"] in ("true", "false")  # 🔵
            # 【検証項目】: OLLAMA_HOST のローカル開発値
            # SAM local は Docker コンテナ内で Lambda を実行するため host.docker.internal を使用
            assert func_vars["OLLAMA_HOST"] == "http://host.docker.internal:11434"  # 🔵
            # 【検証項目】: OLLAMA_MODEL のローカル開発値
            assert func_vars["OLLAMA_MODEL"] != ""  # 🔵


# ==============================================================================
# カテゴリ G: Bedrock 例外の AIServiceError 階層経由キャッチ（エッジケース）
# ==============================================================================


class TestBedrockExceptionMapping:
    """カテゴリ G: Bedrock 例外が AIServiceError 階層経由で正しくマッピングされることを確認."""

    def test_bedrock_timeout_error_mapped_via_ai_hierarchy(self):
        """TC-056-026: BedrockTimeoutError が _map_ai_error_to_http() で HTTP 504 にマッピングされること.

        【テスト目的】: BedrockTimeoutError が AITimeoutError 階層経由で 504 にマッピングされることを確認
        【テスト内容】: TASK-0055 で実施した多重継承により、Bedrock 例外が AI 例外として処理される
        【期待される動作】: isinstance(error, AITimeoutError) が True となり、504 にマッピングされる
        🔵 信頼性レベル: 青信号 - 要件定義書 4.3 節 EDGE-01、TASK-0055 の多重継承設計から確定
        """
        # Given
        # 【テストデータ準備】: BedrockTimeoutError インスタンスを作成（多重継承で AITimeoutError でもある）
        from api.handler import _map_ai_error_to_http
        from services.bedrock import BedrockTimeoutError

        error = BedrockTimeoutError("Bedrock API timed out")

        # When
        # 【実際の処理実行】: エラーマッピング関数を呼び出す
        response = _map_ai_error_to_http(error)

        # Then
        assert response.status_code == 504  # 【検証項目】: Bedrock 例外が AITimeoutError として 504 になる 🔵

    def test_bedrock_rate_limit_error_mapped_via_ai_hierarchy(self):
        """TC-056-027: BedrockRateLimitError が _map_ai_error_to_http() で HTTP 429 にマッピングされること.

        【テスト目的】: BedrockRateLimitError が AIRateLimitError 階層経由で 429 になることを確認
        【テスト内容】: 多重継承により Bedrock 固有例外が AI 統一例外として処理される
        🔵 信頼性レベル: 青信号 - TASK-0055 多重継承、要件定義書 EDGE-01 から確定
        """
        # Given
        from api.handler import _map_ai_error_to_http
        from services.bedrock import BedrockRateLimitError

        error = BedrockRateLimitError("throttled")

        # When
        response = _map_ai_error_to_http(error)

        # Then
        assert response.status_code == 429  # 【検証項目】: Bedrock 例外が AIRateLimitError として 429 になる 🔵

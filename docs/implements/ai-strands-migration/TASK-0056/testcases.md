# TDD テストケース定義: TASK-0056 handler.py AIServiceFactory 統合 + template.yaml 更新

**機能名**: ai-strands-migration
**タスクID**: TASK-0056
**要件名**: handler.py AIServiceFactory 統合 + template.yaml 更新
**出力ファイル名**: `docs/implements/ai-strands-migration/TASK-0056/testcases.md`
**作成日**: 2026-02-23

---

## 開発言語・フレームワーク

- **プログラミング言語**: Python 3.12
  - **言語選択の理由**: プロジェクト全体が Python バックエンドで統一されており、既存テストも Python で記述済み
  - **テストに適した機能**: unittest.mock（patch, MagicMock）、isinstance チェック、json パース
- **テストフレームワーク**: pytest + unittest.mock (MagicMock, patch)
  - **フレームワーク選択の理由**: 既存テスト (`test_handler_link_line.py` 等) が pytest + MagicMock + patch で記述されている
  - **テスト実行環境**: `cd backend && pytest tests/unit/test_handler_ai_service_factory.py -v`
- **重要な注意事項**:
  - 全メソッドは**同期**（`def`、`async def` ではない）-- `pytest.mark.asyncio` は不要
  - handler.py は `APIGatewayHttpResolver` を使用した Lambda Powertools ベースの API ハンドラー
  - generate_cards() は `app.current_event` でリクエストデータを取得する同期関数
  - `_map_ai_error_to_http()` はスタンドアロン関数（クラスメソッドではない）として直接 import・テスト可能
  - テストファイルは **新規ファイル** `backend/tests/unit/test_handler_ai_service_factory.py` に作成（既存テストを変更しない）
  - 既存の conftest.py フィクスチャ (`api_gateway_event`, `lambda_context`) を使用
  - template.yaml / env.json のテストではファイルを直接読み込んでパースする
- 🔵 既存テストパターン `backend/tests/unit/test_handler_link_line.py` と要件定義書 6 節「テスト対象の概要」から確定

---

## 要件定義との対応関係

- **参照した機能概要**: 要件定義書 1 節 - handler.py の BedrockService 直接参照を create_ai_service() ファクトリ経由に変更
- **参照した入力・出力仕様**: 要件定義書 2 節 - handler.py 改修（import 変更、generate_cards 改修、_map_ai_error_to_http）、template.yaml 改修、env.json 改修、スタブハンドラー追加
- **参照した制約条件**: 要件定義書 3 節 - Lambda タイムアウト 60 秒、同期呼び出し、API レスポンス互換性、既存テスト保護
- **参照した使用例**: 要件定義書 4 節 - UC-01〜UC-03 基本パターン、EC-01〜EC-05 エラーケース、EDGE-01〜EDGE-03 エッジケース
- **参照した実装ファイル**:
  - `backend/src/api/handler.py` - 現行 handler（L41-47 import、L57 bedrock_service、L241-316 generate_cards）
  - `backend/src/services/ai_service.py` - AIService Protocol、create_ai_service() ファクトリ、例外階層
  - `backend/src/services/bedrock.py` - BedrockService（多重継承例外、TASK-0055 改修済み）
  - `backend/template.yaml` - 現行 SAM テンプレート（Timeout: 30、UseStrands なし）
  - `backend/env.json` - 現行ローカル環境設定（3 関数、OLLAMA_* なし）
  - `backend/tests/conftest.py` - api_gateway_event, lambda_context フィクスチャ
  - `backend/tests/unit/test_handler_link_line.py` - 既存テストパターン参照

---

## テストケース実装時の日本語コメント指針

各テストケースの実装時には以下の日本語コメントを必ず含める:

```python
# 【テスト目的】: このテストで何を確認するかを日本語で明記
# 【テスト内容】: 具体的にどのような処理をテストするかを説明
# 【期待される動作】: 正常に動作した場合の結果を説明

# Given
# 【テストデータ準備】: なぜこのデータを用意するかの理由
# 【前提条件確認】: テスト実行に必要な前提条件

# When
# 【実際の処理実行】: どの機能/メソッドを呼び出すかを説明

# Then
# 【結果検証】: 何を検証するかを具体的に説明
# 【検証項目】: この検証で確認している具体的な項目
```

---

## カテゴリ A: AIServiceFactory 統合テスト

### TC-056-001: generate_cards エンドポイントが create_ai_service() ファクトリを呼び出すこと

- **テスト名**: generate_cards エンドポイントのファクトリ呼び出し確認
  - **何をテストするか**: handler.py の generate_cards エンドポイントが `create_ai_service()` を呼び出し、その戻り値の `generate_cards()` メソッドを使用していること
  - **期待される動作**: POST /cards/generate リクエスト時に `create_ai_service()` が 1 回呼ばれ、200 レスポンスが返る
- **入力値**: 有効な GenerateCardsRequest ボディ（`input_text`, `card_count`, `difficulty`, `language`）
  - **入力データの意味**: カード生成の標準的なリクエスト
- **期待される結果**: `create_ai_service()` が 1 回呼ばれ、HTTP 200 + `generated_cards` を含むレスポンスが返る
  - **期待結果の理由**: ファクトリパターンにより、エンドポイント呼び出しごとにサービスインスタンスが生成される
- **テストの目的**: handler.py が BedrockService 直接参照ではなくファクトリ経由で AI サービスを取得していることの確認
  - **確認ポイント**: `mock_factory.assert_called_once()` でファクトリが呼ばれたことを検証
- 🔵 要件定義書 2.1 節「グローバル変数変更」「generate_cards エンドポイント改修」から確定

```python
def test_generate_cards_uses_create_ai_service_factory(self, api_gateway_event, lambda_context):
    # 【テスト目的】: generate_cards が create_ai_service() ファクトリを使用することを確認
    # 【テスト内容】: POST /cards/generate リクエストを送信し、ファクトリが呼ばれることを検証
    # 【期待される動作】: create_ai_service() が 1 回呼ばれ、200 レスポンスが返る
    # 🔵

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
    with patch("api.handler.create_ai_service") as mock_factory:
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
```

### TC-056-002: generate_cards がファクトリ生成サービスの generate_cards() を正しい引数で呼び出すこと

- **テスト名**: ファクトリ生成サービスへの引数伝播確認
  - **何をテストするか**: ファクトリから返されたサービスの `generate_cards()` が、リクエストボディのパラメータで正しく呼び出されること
  - **期待される動作**: `input_text`, `card_count`, `difficulty`, `language` が正しく伝播する
- **入力値**: 各パラメータを明示的に指定した GenerateCardsRequest
  - **入力データの意味**: パラメータ伝播のトレーサビリティを確保するための特定値
- **期待される結果**: `mock_service.generate_cards.assert_called_once_with(...)` が正しいパラメータで通過
  - **期待結果の理由**: ファクトリパターン移行後もパラメータの受け渡しが変わらないこと
- **テストの目的**: API リクエスト → サービス呼び出しのパラメータ伝播の正確性
  - **確認ポイント**: 各引数がリクエストボディの値と一致すること
- 🔵 要件定義書 2.1 節「generate_cards エンドポイント改修」・handler.py L265-271 から確定

```python
def test_generate_cards_passes_correct_args_to_ai_service(self, api_gateway_event, lambda_context):
    # 【テスト目的】: ファクトリ生成サービスに正しい引数が渡されることを確認
    # 【テスト内容】: リクエストパラメータがサービスの generate_cards() に正しく伝播されることを検証
    # 🔵

    # Given
    # 【テストデータ準備】: 特定のパラメータ値でリクエストを作成
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
    with patch("api.handler.create_ai_service") as mock_factory:
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
    )  # 🔵
```

---

## カテゴリ B: エラーマッピングテスト

### TC-056-003: _map_ai_error_to_http(AITimeoutError) が HTTP 504 を返すこと

- **テスト名**: AITimeoutError → HTTP 504 マッピング
  - **何をテストするか**: `_map_ai_error_to_http()` に `AITimeoutError` を渡した場合に HTTP 504 レスポンスが返ること
  - **期待される動作**: ステータスコード 504、エラーメッセージ "AI service timeout"
- **入力値**: `AITimeoutError("test timeout")`
  - **入力データの意味**: AI サービスのタイムアウト例外
- **期待される結果**: `status_code=504`, `body={"error": "AI service timeout"}`
  - **期待結果の理由**: 要件定義書 2.1 節の _map_ai_error_to_http() 仕様表に基づく
- **テストの目的**: エラーマッピング関数の AITimeoutError 処理確認
  - **確認ポイント**: ステータスコードとエラーメッセージの完全一致
- 🔵 要件定義書 2.1 節「_map_ai_error_to_http() ヘルパー関数」の仕様表から確定

```python
def test_map_ai_error_timeout_returns_504(self):
    # 【テスト目的】: AITimeoutError が HTTP 504 にマッピングされることを確認
    # 【テスト内容】: _map_ai_error_to_http() に AITimeoutError を渡して結果を検証
    # 【期待される動作】: 504 ステータスと "AI service timeout" メッセージ
    # 🔵

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
```

### TC-056-004: _map_ai_error_to_http(AIRateLimitError) が HTTP 429 を返すこと

- **テスト名**: AIRateLimitError → HTTP 429 マッピング
  - **何をテストするか**: `_map_ai_error_to_http()` に `AIRateLimitError` を渡した場合に HTTP 429 レスポンスが返ること
  - **期待される動作**: ステータスコード 429、エラーメッセージ "AI service rate limit exceeded"
- **入力値**: `AIRateLimitError("rate limit hit")`
  - **入力データの意味**: AI サービスのレート制限例外
- **期待される結果**: `status_code=429`, `body={"error": "AI service rate limit exceeded"}`
  - **期待結果の理由**: 要件定義書 2.1 節の仕様表に基づく
- **テストの目的**: レート制限エラーのマッピング確認
- 🔵 要件定義書 2.1 節「_map_ai_error_to_http() ヘルパー関数」から確定

```python
def test_map_ai_error_rate_limit_returns_429(self):
    # 【テスト目的】: AIRateLimitError が HTTP 429 にマッピングされることを確認
    # 🔵

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
```

### TC-056-005: _map_ai_error_to_http(AIProviderError) が HTTP 503 を返すこと

- **テスト名**: AIProviderError → HTTP 503 マッピング
  - **何をテストするか**: `_map_ai_error_to_http()` に `AIProviderError` を渡した場合に HTTP 503 レスポンスが返ること
  - **期待される動作**: ステータスコード 503、エラーメッセージ "AI service unavailable"
- **入力値**: `AIProviderError("provider down")`
  - **入力データの意味**: AI プロバイダーのエラー例外（初期化失敗等）
- **期待される結果**: `status_code=503`, `body={"error": "AI service unavailable"}`
  - **期待結果の理由**: 要件定義書 2.1 節の仕様表に基づく
- **テストの目的**: プロバイダーエラーのマッピング確認
- 🔵 要件定義書 2.1 節「_map_ai_error_to_http() ヘルパー関数」から確定

```python
def test_map_ai_error_provider_returns_503(self):
    # 【テスト目的】: AIProviderError が HTTP 503 にマッピングされることを確認
    # 🔵

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
```

### TC-056-006: _map_ai_error_to_http(AIParseError) が HTTP 500 を返すこと

- **テスト名**: AIParseError → HTTP 500 マッピング
  - **何をテストするか**: `_map_ai_error_to_http()` に `AIParseError` を渡した場合に HTTP 500 レスポンスが返ること
  - **期待される動作**: ステータスコード 500、エラーメッセージ "AI service response parse error"
- **入力値**: `AIParseError("invalid json")`
  - **入力データの意味**: AI レスポンスの解析失敗例外
- **期待される結果**: `status_code=500`, `body={"error": "AI service response parse error"}`
  - **期待結果の理由**: 要件定義書 2.1 節の仕様表に基づく
- **テストの目的**: パースエラーのマッピング確認
- 🔵 要件定義書 2.1 節「_map_ai_error_to_http() ヘルパー関数」から確定

```python
def test_map_ai_error_parse_returns_500(self):
    # 【テスト目的】: AIParseError が HTTP 500 にマッピングされることを確認
    # 🔵

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
```

### TC-056-007: _map_ai_error_to_http(AIInternalError) が HTTP 500 を返すこと

- **テスト名**: AIInternalError → HTTP 500 マッピング
  - **何をテストするか**: `_map_ai_error_to_http()` に `AIInternalError` を渡した場合に HTTP 500 レスポンスが返ること
  - **期待される動作**: ステータスコード 500、エラーメッセージ "AI service error"
- **入力値**: `AIInternalError("internal failure")`
  - **入力データの意味**: AI サービス内部エラー例外
- **期待される結果**: `status_code=500`, `body={"error": "AI service error"}`
  - **期待結果の理由**: 要件定義書 2.1 節の仕様表（AIInternalError は汎用 "AI service error"）
- **テストの目的**: 内部エラーのマッピング確認
- 🔵 要件定義書 2.1 節「_map_ai_error_to_http() ヘルパー関数」から確定

```python
def test_map_ai_error_internal_returns_500(self):
    # 【テスト目的】: AIInternalError が HTTP 500 にマッピングされることを確認
    # 🔵

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
```

### TC-056-008: _map_ai_error_to_http(AIServiceError) が汎用フォールバックとして HTTP 500 を返すこと

- **テスト名**: AIServiceError 汎用 → HTTP 500 フォールバック
  - **何をテストするか**: 基底クラス `AIServiceError` を直接渡した場合に HTTP 500 の汎用エラーが返ること
  - **期待される動作**: ステータスコード 500、エラーメッセージ "AI service error"
- **入力値**: `AIServiceError("unknown ai error")`
  - **入力データの意味**: 予期しない AI サービスエラー（サブクラス以外の汎用例外）
- **期待される結果**: `status_code=500`, `body={"error": "AI service error"}`
  - **期待結果の理由**: 要件定義書 2.1 節の仕様表で AIServiceError（汎用）は 500 "AI service error"
- **テストの目的**: 汎用フォールバックパスの確認
  - **確認ポイント**: 未知のサブクラスでも安全に 500 が返ること
- 🔵 要件定義書 2.1 節「_map_ai_error_to_http() ヘルパー関数」の汎用フォールバック行から確定

```python
def test_map_ai_error_generic_fallback_returns_500(self):
    # 【テスト目的】: AIServiceError（基底クラス）が汎用フォールバックとして HTTP 500 を返すことを確認
    # 🔵

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
```

### TC-056-009: _map_ai_error_to_http のレスポンスが常に application/json であること

- **テスト名**: エラーレスポンスの Content-Type 確認
  - **何をテストするか**: `_map_ai_error_to_http()` が返す全レスポンスの Content-Type が `application/json` であること
  - **期待される動作**: 全例外タイプで Content-Type が `application/json`
- **入力値**: 全 6 種類の例外クラスインスタンス
  - **入力データの意味**: 全例外パスをカバーする網羅テスト
- **期待される結果**: 全てのレスポンスで `content_type == "application/json"`
  - **期待結果の理由**: 要件定義書 2.1 節「Content-Type: application/json」
- **テストの目的**: レスポンスフォーマットの一貫性確認
- 🔵 要件定義書 2.1 節「レスポンスフォーマット」から確定

```python
def test_map_ai_error_all_responses_are_json(self):
    # 【テスト目的】: 全例外タイプで Content-Type が application/json であることを確認
    # 🔵

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
    for error in errors:
        response = _map_ai_error_to_http(error)
        # 【結果検証】: Content-Type が application/json
        assert response.content_type == "application/json", (
            f"{type(error).__name__} response has wrong content_type: {response.content_type}"
        )  # 🔵
        # 【検証項目】: body が有効な JSON としてパース可能
        body = json.loads(response.body)
        assert "error" in body  # 🔵
```

---

## カテゴリ C: generate_cards エンドポイント互換性テスト

### TC-056-010: generate_cards が成功時に既存レスポンス形式を返すこと

- **テスト名**: generate_cards レスポンス後方互換性
  - **何をテストするか**: ファクトリパターン移行後も `GenerateCardsResponse` 形式のレスポンスが返ること
  - **期待される動作**: `generated_cards` 配列と `generation_info` オブジェクトを含む 200 レスポンス
- **入力値**: 有効な GenerateCardsRequest ボディ、モックサービスが 2 枚のカードを返す
  - **入力データの意味**: 複数カード生成の標準的なシナリオ
- **期待される結果**: HTTP 200、`generated_cards` に 2 要素、`generation_info` に `input_length`, `model_used`, `processing_time_ms`
  - **期待結果の理由**: REQ-SM-402 API レスポンス互換性要件
- **テストの目的**: 後方互換性の確保
  - **確認ポイント**: レスポンス構造が GenerateCardsResponse Pydantic モデルと一致すること
- 🔵 要件定義書 2.1 節「generate_cards エンドポイント改修」の出力仕様、REQ-SM-402 から確定

```python
def test_generate_cards_response_format_backward_compatible(self, api_gateway_event, lambda_context):
    # 【テスト目的】: ファクトリ移行後も generate_cards のレスポンス形式が変わらないことを確認
    # 【テスト内容】: 成功時のレスポンスが generated_cards + generation_info の構造であることを検証
    # 🔵

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

    with patch("api.handler.create_ai_service") as mock_factory:
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
```

### TC-056-011: generate_cards エンドポイントが AIServiceError 例外を適切に処理すること

- **テスト名**: generate_cards での AIServiceError ハンドリング
  - **何をテストするか**: ファクトリ生成サービスが `AITimeoutError` を送出した場合、エンドポイントが 504 を返すこと
  - **期待される動作**: `_map_ai_error_to_http()` を通じて適切な HTTP レスポンスに変換される
- **入力値**: モックサービスが `AITimeoutError` を送出するリクエスト
  - **入力データの意味**: AI サービスのタイムアウトシナリオ
- **期待される結果**: HTTP 504 レスポンス
  - **期待結果の理由**: EDGE-01 BedrockService の例外が AIServiceError 階層で捕捉される
- **テストの目的**: エンドポイントレベルでのエラーハンドリング統合確認
- 🔵 要件定義書 4.2 節 EC-01 から確定

```python
def test_generate_cards_handles_ai_timeout_error(self, api_gateway_event, lambda_context):
    # 【テスト目的】: generate_cards が AITimeoutError を HTTP 504 に変換することを確認
    # 🔵

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

    with patch("api.handler.create_ai_service") as mock_factory:
        from services.ai_service import AITimeoutError
        mock_service = MagicMock()
        mock_service.generate_cards.side_effect = AITimeoutError("timeout")
        mock_factory.return_value = mock_service

        # When
        from api.handler import handler
        response = handler(event, lambda_context)

    # Then
    assert response["statusCode"] == 504  # 【検証項目】: タイムアウトで 504 が返る 🔵
```

### TC-056-012: generate_cards エンドポイントが AIRateLimitError を HTTP 429 に変換すること

- **テスト名**: generate_cards での AIRateLimitError ハンドリング
  - **何をテストするか**: `AIRateLimitError` が HTTP 429 にマッピングされること
- **入力値**: モックサービスが `AIRateLimitError` を送出
- **期待される結果**: HTTP 429
- **テストの目的**: レート制限エラーのエンドポイントレベルハンドリング
- 🔵 要件定義書 4.2 節 EC-02 から確定

```python
def test_generate_cards_handles_ai_rate_limit_error(self, api_gateway_event, lambda_context):
    # 【テスト目的】: generate_cards が AIRateLimitError を HTTP 429 に変換することを確認
    # 🔵

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

    with patch("api.handler.create_ai_service") as mock_factory:
        from services.ai_service import AIRateLimitError
        mock_service = MagicMock()
        mock_service.generate_cards.side_effect = AIRateLimitError("rate limit")
        mock_factory.return_value = mock_service

        from api.handler import handler
        response = handler(event, lambda_context)

    # Then
    assert response["statusCode"] == 429  # 🔵
```

### TC-056-013: generate_cards エンドポイントが AIProviderError を HTTP 503 に変換すること

- **テスト名**: generate_cards での AIProviderError ハンドリング
  - **何をテストするか**: `AIProviderError`（create_ai_service 初期化失敗を含む）が HTTP 503 にマッピングされること
- **入力値**: モックサービスが `AIProviderError` を送出
- **期待される結果**: HTTP 503
- **テストの目的**: プロバイダーエラーのエンドポイントレベルハンドリング（EDGE-02 対応）
- 🔵 要件定義書 4.2 節 EC-03、4.3 節 EDGE-02 から確定

```python
def test_generate_cards_handles_ai_provider_error(self, api_gateway_event, lambda_context):
    # 【テスト目的】: generate_cards が AIProviderError を HTTP 503 に変換することを確認
    # 【テスト内容】: create_ai_service() の初期化失敗シナリオを含む
    # 🔵

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

    with patch("api.handler.create_ai_service") as mock_factory:
        from services.ai_service import AIProviderError
        mock_factory.side_effect = AIProviderError("Failed to initialize AI service")

        from api.handler import handler
        response = handler(event, lambda_context)

    # Then
    assert response["statusCode"] == 503  # 【検証項目】: プロバイダーエラーで 503 が返る 🔵
```

---

## カテゴリ D: スタブハンドラーテスト

### TC-056-014: grade_ai_handler が HTTP 501 を返すこと

- **テスト名**: grade_ai_handler スタブの 501 レスポンス確認
  - **何をテストするか**: `grade_ai_handler(event, context)` が HTTP 501 + `{"error": "Not implemented"}` を返すこと
  - **期待される動作**: スタブハンドラーが SAM デプロイ可能な最低限のレスポンスを返す
- **入力値**: 最小限の Lambda イベント dict とコンテキスト
  - **入力データの意味**: Lambda ランタイムからの直接呼び出しシミュレーション
- **期待される結果**: `{"statusCode": 501, "headers": {"Content-Type": "application/json"}, "body": "{\"error\": \"Not implemented\"}"}`
  - **期待結果の理由**: 要件定義書 2.4 節のスタブハンドラー仕様
- **テストの目的**: SAM ビルド・デプロイ時に handler 参照が解決可能であることの確認
  - **確認ポイント**: statusCode, Content-Type ヘッダー, body の完全一致
- 🔵 要件定義書 2.4 節「handler.py スタブハンドラー追加」から確定

```python
def test_grade_ai_handler_returns_501(self, lambda_context):
    # 【テスト目的】: grade_ai_handler スタブが 501 を返すことを確認
    # 【テスト内容】: Lambda イベントを直接渡してスタブレスポンスを検証
    # 🔵

    # Given
    # 【テストデータ準備】: 最小限の Lambda イベント
    event = {
        "version": "2.0",
        "routeKey": "POST /reviews/{cardId}/grade-ai",
        "rawPath": "/reviews/card-123/grade-ai",
        "requestContext": {
            "http": {"method": "POST"},
        },
    }

    # When
    # 【実際の処理実行】: grade_ai_handler を直接呼び出す
    from api.handler import grade_ai_handler
    response = grade_ai_handler(event, lambda_context)

    # Then
    # 【結果検証】: 501 Not Implemented レスポンス
    assert response["statusCode"] == 501  # 🔵
    assert response["headers"]["Content-Type"] == "application/json"  # 🔵
    body = json.loads(response["body"])
    assert body["error"] == "Not implemented"  # 🔵
```

### TC-056-015: advice_handler が HTTP 501 を返すこと

- **テスト名**: advice_handler スタブの 501 レスポンス確認
  - **何をテストするか**: `advice_handler(event, context)` が HTTP 501 + `{"error": "Not implemented"}` を返すこと
  - **期待される動作**: スタブハンドラーが SAM デプロイ可能な最低限のレスポンスを返す
- **入力値**: 最小限の Lambda イベント dict とコンテキスト
- **期待される結果**: `{"statusCode": 501, ...}`
  - **期待結果の理由**: 要件定義書 2.4 節のスタブハンドラー仕様
- **テストの目的**: SAM ビルド・デプロイ時に handler 参照が解決可能であることの確認
- 🔵 要件定義書 2.4 節「handler.py スタブハンドラー追加」から確定

```python
def test_advice_handler_returns_501(self, lambda_context):
    # 【テスト目的】: advice_handler スタブが 501 を返すことを確認
    # 🔵

    # Given
    event = {
        "version": "2.0",
        "routeKey": "GET /advice",
        "rawPath": "/advice",
        "requestContext": {
            "http": {"method": "GET"},
        },
    }

    # When
    from api.handler import advice_handler
    response = advice_handler(event, lambda_context)

    # Then
    assert response["statusCode"] == 501  # 🔵
    assert response["headers"]["Content-Type"] == "application/json"  # 🔵
    body = json.loads(response["body"])
    assert body["error"] == "Not implemented"  # 🔵
```

---

## カテゴリ E: template.yaml 設定検証テスト

### TC-056-016: UseStrands パラメータが template.yaml に存在すること

- **テスト名**: UseStrands パラメータ定義の確認
  - **何をテストするか**: template.yaml の Parameters セクションに `UseStrands` パラメータが正しく定義されていること
  - **期待される動作**: Type=String, Default="false", AllowedValues=["true", "false"]
- **入力値**: template.yaml ファイルの YAML パース結果
  - **入力データの意味**: CloudFormation テンプレートのパラメータ定義
- **期待される結果**: パラメータが存在し、デフォルト値が "false"、許可値に "true" と "false" が含まれる
  - **期待結果の理由**: 要件定義書 2.2 節「UseStrands パラメータ追加」、REQ-SM-103 デフォルト "false"
- **テストの目的**: フィーチャーフラグパラメータの正確な定義確認
- 🔵 要件定義書 2.2 節「UseStrands パラメータ追加」から確定

```python
def test_template_yaml_use_strands_parameter(self):
    # 【テスト目的】: UseStrands パラメータが正しく定義されていることを確認
    # 🔵

    # Given
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

    # Then
    assert "UseStrands" in template["Parameters"]  # 🔵
    param = template["Parameters"]["UseStrands"]
    assert param["Type"] == "String"  # 🔵
    assert param["Default"] == "false"  # 【検証項目】: デフォルト値が "false" 🔵
    assert "true" in param["AllowedValues"]  # 🔵
    assert "false" in param["AllowedValues"]  # 🔵
```

### TC-056-017: ShouldUseStrands コンディションが定義されていること

- **テスト名**: ShouldUseStrands コンディション定義の確認
  - **何をテストするか**: Conditions セクションに `ShouldUseStrands` が定義されていること
- **入力値**: template.yaml の YAML パース結果
- **期待される結果**: `ShouldUseStrands` が Conditions に存在
  - **期待結果の理由**: 要件定義書 2.2 節「ShouldUseStrands コンディション追加」
- **テストの目的**: 条件付きリソース設定の基盤確認
- 🔵 要件定義書 2.2 節から確定

```python
def test_template_yaml_should_use_strands_condition(self):
    # 【テスト目的】: ShouldUseStrands コンディションが定義されていることを確認
    # 🔵

    # Given
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

    # Then
    assert "Conditions" in template  # 🔵
    assert "ShouldUseStrands" in template["Conditions"]  # 🔵
```

### TC-056-018: Global タイムアウトが 60 秒に設定されていること

- **テスト名**: Lambda Global タイムアウト 60 秒確認
  - **何をテストするか**: `Globals.Function.Timeout` が 60 に設定されていること
  - **期待される動作**: 全 Lambda 関数のデフォルトタイムアウトが 60 秒
- **入力値**: template.yaml の YAML パース結果
- **期待される結果**: `template["Globals"]["Function"]["Timeout"] == 60`
  - **期待結果の理由**: 要件定義書 2.2 節「Global タイムアウト更新」、REQ-SM-401
- **テストの目的**: Strands SDK 処理時間対応のタイムアウト設定確認
- 🔵 要件定義書 2.2 節「Global タイムアウト更新」、REQ-SM-401 から確定

```python
def test_template_yaml_global_timeout_is_60(self):
    # 【テスト目的】: Lambda のグローバルタイムアウトが 60 秒であることを確認
    # 🔵

    # Given
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

    # Then
    assert template["Globals"]["Function"]["Timeout"] == 60  # 🔵
```

### TC-056-019: USE_STRANDS 環境変数が Globals に定義されていること

- **テスト名**: Globals 環境変数 USE_STRANDS の定義確認
  - **何をテストするか**: `Globals.Function.Environment.Variables` に `USE_STRANDS` が含まれること
- **入力値**: template.yaml の YAML パース結果
- **期待される結果**: USE_STRANDS が環境変数に存在
  - **期待結果の理由**: 要件定義書 2.2 節「Globals 環境変数追加」
- **テストの目的**: フィーチャーフラグ環境変数の定義確認
- 🔵 要件定義書 2.2 節「Globals 環境変数追加」から確定

```python
def test_template_yaml_globals_have_use_strands_env_var(self):
    # 【テスト目的】: Globals 環境変数に USE_STRANDS が定義されていることを確認
    # 🔵

    # Given
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

    # Then
    env_vars = template["Globals"]["Function"]["Environment"]["Variables"]
    assert "USE_STRANDS" in env_vars  # 🔵
```

### TC-056-020: 新 Lambda 関数が template.yaml に定義されていること

- **テスト名**: ReviewsGradeAiFunction と AdviceFunction の定義確認
  - **何をテストするか**: Resources セクションに `ReviewsGradeAiFunction` と `AdviceFunction` が定義されていること
  - **期待される動作**: 各関数に Handler、Timeout、MemorySize、Events が設定されている
- **入力値**: template.yaml の YAML パース結果
- **期待される結果**: 両関数が存在し、適切なプロパティを持つ
  - **期待結果の理由**: 要件定義書 2.2 節「新 API ルート（Lambda 関数）追加」
- **テストの目的**: 新 API ルートのインフラ定義確認
  - **確認ポイント**: Handler パス、タイムアウト、メモリサイズ、イベントパスとメソッド
- 🔵 要件定義書 2.2 節「ReviewsGradeAiFunction」「AdviceFunction」の仕様表から確定

```python
def test_template_yaml_new_lambda_functions_defined(self):
    # 【テスト目的】: 新 Lambda 関数が template.yaml に正しく定義されていることを確認
    # 🔵

    # Given
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

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
```

### TC-056-021: 新 Lambda 関数のイベントルートが正しいこと

- **テスト名**: 新 Lambda 関数の API ルート定義確認
  - **何をテストするか**: ReviewsGradeAiFunction のパスが `/reviews/{cardId}/grade-ai` (POST)、AdviceFunction のパスが `/advice` (GET) であること
- **入力値**: template.yaml の YAML パース結果
- **期待される結果**: 各関数の Events 内にイベント定義があり、パスとメソッドが正しい
  - **期待結果の理由**: 要件定義書 2.2 節の仕様表
- **テストの目的**: API ルーティングの正確性確認
- 🔵 要件定義書 2.2 節「ReviewsGradeAiFunction」「AdviceFunction」から確定

```python
def test_template_yaml_new_lambda_event_routes(self):
    # 【テスト目的】: 新 Lambda 関数の API ルートが正しいことを確認
    # 🔵

    # Given
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

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
```

### TC-056-022: 新 Lambda 関数の LogGroup が定義されていること

- **テスト名**: 新 Lambda 関数の CloudWatch LogGroup 定義確認
  - **何をテストするか**: `ReviewsGradeAiFunctionLogGroup` と `AdviceFunctionLogGroup` が Resources に存在すること
- **入力値**: template.yaml の YAML パース結果
- **期待される結果**: 両 LogGroup リソースが存在し、`AWS::Logs::LogGroup` タイプであること
  - **期待結果の理由**: 要件定義書 2.2 節「LogGroups」、既存パターン（ApiFunctionLogGroup）に準拠
- **テストの目的**: ログ管理インフラの完全性確認
- 🔵 要件定義書 2.2 節「LogGroups」・既存パターンから確定

```python
def test_template_yaml_new_log_groups(self):
    # 【テスト目的】: 新 Lambda 関数の LogGroup が定義されていることを確認
    # 🔵

    # Given
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

    resources = template["Resources"]

    # Then
    assert "ReviewsGradeAiFunctionLogGroup" in resources  # 🔵
    assert resources["ReviewsGradeAiFunctionLogGroup"]["Type"] == "AWS::Logs::LogGroup"  # 🔵

    assert "AdviceFunctionLogGroup" in resources  # 🔵
    assert resources["AdviceFunctionLogGroup"]["Type"] == "AWS::Logs::LogGroup"  # 🔵
```

### TC-056-023: 新 Lambda 関数の Outputs が定義されていること

- **テスト名**: 新 Lambda 関数の CloudFormation Outputs 定義確認
  - **何をテストするか**: `ReviewsGradeAiFunctionArn` と `AdviceFunctionArn` が Outputs に存在すること
- **入力値**: template.yaml の YAML パース結果
- **期待される結果**: 両 Output が存在
  - **期待結果の理由**: 要件定義書 2.2 節「Outputs」・既存パターン（ApiFunctionArn）に準拠
- **テストの目的**: スタック間参照の基盤確認
- 🔵 要件定義書 2.2 節「Outputs」から確定

```python
def test_template_yaml_new_outputs(self):
    # 【テスト目的】: 新 Lambda 関数の Outputs が定義されていることを確認
    # 🔵

    # Given
    import yaml
    with open("backend/template.yaml", "r") as f:
        template = yaml.safe_load(f)

    outputs = template["Outputs"]

    # Then
    assert "ReviewsGradeAiFunctionArn" in outputs  # 🔵
    assert "AdviceFunctionArn" in outputs  # 🔵
```

---

## カテゴリ F: env.json 設定検証テスト

### TC-056-024: 既存関数に USE_STRANDS, OLLAMA_HOST, OLLAMA_MODEL が追加されていること

- **テスト名**: 既存関数の新環境変数確認
  - **何をテストするか**: ApiFunction, LineWebhookFunction, DuePushJobFunction に `USE_STRANDS`, `OLLAMA_HOST`, `OLLAMA_MODEL` が追加されていること
  - **期待される動作**: 各関数のローカル開発用環境変数に新変数が含まれる
- **入力値**: env.json の JSON パース結果
  - **入力データの意味**: SAM ローカル実行時の環境変数設定
- **期待される結果**: 3 関数全てに 3 つの新変数が存在
  - **期待結果の理由**: 要件定義書 2.3 節「既存関数への環境変数追加」
- **テストの目的**: ローカル開発環境の設定完全性確認
  - **確認ポイント**: 変数名の存在と値の正確性
- 🔵 要件定義書 2.3 節「既存関数への環境変数追加」から確定

```python
def test_env_json_existing_functions_have_new_vars(self):
    # 【テスト目的】: 既存関数に新環境変数が追加されていることを確認
    # 🔵

    # Given
    import json as json_mod
    with open("backend/env.json", "r") as f:
        env_config = json_mod.load(f)

    # Then
    for func_name in ["ApiFunction", "LineWebhookFunction", "DuePushJobFunction"]:
        assert func_name in env_config, f"{func_name} が env.json に存在しない"  # 🔵
        func_vars = env_config[func_name]
        assert "USE_STRANDS" in func_vars, f"{func_name} に USE_STRANDS がない"  # 🔵
        assert func_vars["USE_STRANDS"] == "false"  # 【検証項目】: デフォルト値 "false" 🔵
        assert "OLLAMA_HOST" in func_vars, f"{func_name} に OLLAMA_HOST がない"  # 🔵
        assert "OLLAMA_MODEL" in func_vars, f"{func_name} に OLLAMA_MODEL がない"  # 🔵
```

### TC-056-025: 新規関数（ReviewsGradeAiFunction, AdviceFunction）が env.json に定義されていること

- **テスト名**: 新規関数の env.json エントリ確認
  - **何をテストするか**: `ReviewsGradeAiFunction` と `AdviceFunction` が env.json に定義され、必要な全環境変数を持つこと
  - **期待される動作**: 両関数に ENVIRONMENT, テーブル名, KEYCLOAK_ISSUER, BEDROCK_MODEL_ID, USE_STRANDS, OLLAMA_HOST, OLLAMA_MODEL 等が設定されている
- **入力値**: env.json の JSON パース結果
- **期待される結果**: 両関数のエントリが存在し、全必要変数が設定されている
  - **期待結果の理由**: 要件定義書 2.3 節「新規関数の環境変数定義」
- **テストの目的**: 新規関数のローカル開発環境の設定完全性確認
- 🔵 要件定義書 2.3 節「新規関数の環境変数定義」から確定

```python
def test_env_json_new_functions_defined(self):
    # 【テスト目的】: 新規関数が env.json に正しく定義されていることを確認
    # 🔵

    # Given
    import json as json_mod
    with open("backend/env.json", "r") as f:
        env_config = json_mod.load(f)

    # Then
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

        # 【検証項目】: USE_STRANDS のデフォルト値
        assert func_vars["USE_STRANDS"] == "false"  # 🔵
        # 【検証項目】: OLLAMA_HOST のローカル開発値
        assert func_vars["OLLAMA_HOST"] == "http://localhost:11434"  # 🔵
        # 【検証項目】: OLLAMA_MODEL のローカル開発値
        assert func_vars["OLLAMA_MODEL"] == "neural-chat"  # 🔵
```

---

## カテゴリ G: Bedrock 例外の AIServiceError 階層経由キャッチ（エッジケース）

### TC-056-026: BedrockTimeoutError が _map_ai_error_to_http() で HTTP 504 にマッピングされること

- **テスト名**: Bedrock 例外の AIServiceError 階層経由マッピング確認
  - **何をテストするか**: `BedrockTimeoutError`（`AITimeoutError` のサブクラス）を `_map_ai_error_to_http()` に渡した場合に HTTP 504 が返ること
  - **期待される動作**: 多重継承により `isinstance(error, AITimeoutError)` が True となり、504 にマッピングされる
- **入力値**: `BedrockTimeoutError("Bedrock timeout")`
  - **入力データの意味**: TASK-0055 で多重継承に改修済みの Bedrock 例外インスタンス
- **期待される結果**: `status_code=504`
  - **期待結果の理由**: 要件定義書 4.3 節 EDGE-01 - BedrockService の例外が AIServiceError 階層で捕捉される
- **テストの目的**: 多重継承例外の統一エラーハンドリング確認
  - **確認ポイント**: Bedrock 固有例外が AI 統一例外として処理される
- 🔵 要件定義書 4.3 節 EDGE-01、TASK-0055 の多重継承設計から確定

```python
def test_bedrock_timeout_error_mapped_via_ai_hierarchy(self):
    # 【テスト目的】: BedrockTimeoutError が AITimeoutError 階層経由で 504 にマッピングされることを確認
    # 【テスト内容】: TASK-0055 で実施した多重継承により、Bedrock 例外が AI 例外として処理される
    # 🔵

    # Given
    from api.handler import _map_ai_error_to_http
    from services.bedrock import BedrockTimeoutError

    error = BedrockTimeoutError("Bedrock API timed out")

    # When
    response = _map_ai_error_to_http(error)

    # Then
    assert response.status_code == 504  # 【検証項目】: Bedrock 例外が AITimeoutError として 504 になる 🔵
```

### TC-056-027: BedrockRateLimitError が _map_ai_error_to_http() で HTTP 429 にマッピングされること

- **テスト名**: BedrockRateLimitError → HTTP 429 マッピング（多重継承経由）
  - **何をテストするか**: `BedrockRateLimitError` が `AIRateLimitError` として処理され 429 が返ること
- **入力値**: `BedrockRateLimitError("throttled")`
- **期待される結果**: `status_code=429`
- **テストの目的**: レート制限の多重継承例外マッピング確認
- 🔵 TASK-0055 多重継承、要件定義書 EDGE-01 から確定

```python
def test_bedrock_rate_limit_error_mapped_via_ai_hierarchy(self):
    # 【テスト目的】: BedrockRateLimitError が AIRateLimitError 階層経由で 429 になることを確認
    # 🔵

    # Given
    from api.handler import _map_ai_error_to_http
    from services.bedrock import BedrockRateLimitError

    error = BedrockRateLimitError("throttled")

    # When
    response = _map_ai_error_to_http(error)

    # Then
    assert response.status_code == 429  # 🔵
```

---

## テストケースサマリー

| ID | カテゴリ | テスト名 | 信頼性 |
|----|---------|---------|--------|
| TC-056-001 | A: Factory 統合 | generate_cards のファクトリ呼び出し確認 | 🔵 |
| TC-056-002 | A: Factory 統合 | ファクトリ生成サービスへの引数伝播確認 | 🔵 |
| TC-056-003 | B: エラーマッピング | AITimeoutError → 504 | 🔵 |
| TC-056-004 | B: エラーマッピング | AIRateLimitError → 429 | 🔵 |
| TC-056-005 | B: エラーマッピング | AIProviderError → 503 | 🔵 |
| TC-056-006 | B: エラーマッピング | AIParseError → 500 | 🔵 |
| TC-056-007 | B: エラーマッピング | AIInternalError → 500 | 🔵 |
| TC-056-008 | B: エラーマッピング | AIServiceError → 500 (汎用) | 🔵 |
| TC-056-009 | B: エラーマッピング | 全レスポンス application/json 確認 | 🔵 |
| TC-056-010 | C: 互換性 | generate_cards レスポンス後方互換性 | 🔵 |
| TC-056-011 | C: 互換性 | generate_cards AITimeoutError → 504 | 🔵 |
| TC-056-012 | C: 互換性 | generate_cards AIRateLimitError → 429 | 🔵 |
| TC-056-013 | C: 互換性 | generate_cards AIProviderError → 503 | 🔵 |
| TC-056-014 | D: スタブ | grade_ai_handler → 501 | 🔵 |
| TC-056-015 | D: スタブ | advice_handler → 501 | 🔵 |
| TC-056-016 | E: template.yaml | UseStrands パラメータ定義 | 🔵 |
| TC-056-017 | E: template.yaml | ShouldUseStrands コンディション | 🔵 |
| TC-056-018 | E: template.yaml | Global タイムアウト 60 秒 | 🔵 |
| TC-056-019 | E: template.yaml | USE_STRANDS 環境変数定義 | 🔵 |
| TC-056-020 | E: template.yaml | 新 Lambda 関数定義 | 🔵 |
| TC-056-021 | E: template.yaml | 新 Lambda イベントルート | 🔵 |
| TC-056-022 | E: template.yaml | 新 LogGroup 定義 | 🔵 |
| TC-056-023 | E: template.yaml | 新 Outputs 定義 | 🔵 |
| TC-056-024 | F: env.json | 既存関数の新環境変数 | 🔵 |
| TC-056-025 | F: env.json | 新規関数の環境変数 | 🔵 |
| TC-056-026 | G: エッジケース | BedrockTimeoutError → 504（多重継承） | 🔵 |
| TC-056-027 | G: エッジケース | BedrockRateLimitError → 429（多重継承） | 🔵 |

---

## 信頼性レベルサマリー

### 統計

- 🔵 **青信号**: 27 件 (100%)
- 🟡 **黄信号**: 0 件 (0%)
- 🔴 **赤信号**: 0 件 (0%)

### 根拠

全テストケースが以下のいずれかから確定:
- 要件定義書 2.1 節の `_map_ai_error_to_http()` 仕様表（エラーマッピングテスト）
- 要件定義書 2.2 節の template.yaml 仕様（インフラテスト）
- 要件定義書 2.3 節の env.json 仕様（環境変数テスト）
- 要件定義書 2.4 節のスタブハンドラー仕様（スタブテスト）
- 要件定義書 4 節の使用例・エラーケース・エッジケース（統合テスト）
- 既存実装コード（handler.py, ai_service.py, bedrock.py）の直接確認

---

## テスト実装時の import 一覧

```python
import json
import os

import pytest
from unittest.mock import patch, MagicMock

# テスト対象
from api.handler import (
    handler,
    _map_ai_error_to_http,
    grade_ai_handler,
    advice_handler,
)

# AI サービス例外階層
from services.ai_service import (
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIInternalError,
    AIParseError,
    AIProviderError,
    create_ai_service,
)

# Bedrock 例外（エッジケーステスト用）
from services.bedrock import (
    BedrockTimeoutError,
    BedrockRateLimitError,
)
```

---

## テストクラス構成案

```python
class TestFactoryIntegration:
    """カテゴリ A: AIServiceFactory 統合テスト"""
    # TC-056-001, TC-056-002

class TestErrorMapping:
    """カテゴリ B: _map_ai_error_to_http() エラーマッピングテスト"""
    # TC-056-003, TC-056-004, TC-056-005, TC-056-006, TC-056-007, TC-056-008, TC-056-009

class TestGenerateCardsCompatibility:
    """カテゴリ C: generate_cards エンドポイント互換性テスト"""
    # TC-056-010, TC-056-011, TC-056-012, TC-056-013

class TestStubHandlers:
    """カテゴリ D: スタブハンドラーテスト"""
    # TC-056-014, TC-056-015

class TestTemplateYamlConfig:
    """カテゴリ E: template.yaml 設定検証テスト"""
    # TC-056-016, TC-056-017, TC-056-018, TC-056-019, TC-056-020, TC-056-021, TC-056-022, TC-056-023

class TestEnvJsonConfig:
    """カテゴリ F: env.json 設定検証テスト"""
    # TC-056-024, TC-056-025

class TestBedrockExceptionMapping:
    """カテゴリ G: Bedrock 例外の AIServiceError 階層経由キャッチ"""
    # TC-056-026, TC-056-027
```

---

## テストファイル

- **新規作成**: `backend/tests/unit/test_handler_ai_service_factory.py`
- **既存テスト**: 変更なし（既存の 260+ テストを保護）
- **フィクスチャ**: 既存 `conftest.py` の `api_gateway_event`, `lambda_context` を使用

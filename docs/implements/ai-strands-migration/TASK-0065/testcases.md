# TASK-0065: 全体統合テスト + 品質確認 - テストケース一覧

**タスクID**: TASK-0065
**作成日**: 2026-02-24
**テストファイル**: `backend/tests/unit/test_quality_gate.py`
**テストフレームワーク**: pytest 8.3.5 + pytest-cov

---

## テストケース概要

| カテゴリ | テストクラス | テストケース数 |
|---------|-------------|---------------|
| 1. Protocol 準拠性 | TestProtocolComplianceFinal | 12 |
| 2. ファクトリルーティング | TestFactoryRoutingFinal | 8 |
| 3. モデルプロバイダー選択 | TestModelProviderSelectionFinal | 8 |
| 4. 例外階層の正確性 | TestExceptionHierarchyFinal | 8 |
| 5. エラーハンドリング一貫性 (Strands) | TestStrandsErrorHandlingFinal | 12 |
| 6. エラーハンドリング一貫性 (Bedrock) | TestBedrockErrorHandlingFinal | 6 |
| 7. 全エンドポイント動作検証 | TestEndpointFunctionalFinal | 7 |
| 8. レスポンスフォーマット検証 | TestResponseFormatFinal | 7 |
| 9. クロスエンドポイントエラーマッピング | TestCrossEndpointErrorMappingFinal | 7 |
| 10. レスポンス解析 (Strands) | TestStrandsResponseParsingFinal | 10 |
| 11. レスポンス解析 (Bedrock) | TestBedrockResponseParsingFinal | 5 |
| 12. プロンプトセキュリティ | TestPromptSecurityFinal | 5 |
| **合計** | | **95** |

---

## カテゴリ 1: Protocol 準拠性 (TestProtocolComplianceFinal)

Protocol 定義 (`backend/src/services/ai_service.py` の `AIService`) に対する
両実装クラスの構造的準拠を最終検証する。

### TC-QG-004-001: StrandsAIService が AIService Protocol を満たす (isinstance)

- **Given**: `StrandsAIService` のインスタンスを作成する (BedrockModel をモック)
- **When**: `isinstance(service, AIService)` を評価する
- **Then**: `True` が返される

### TC-QG-004-002: BedrockService が AIService Protocol を満たす (isinstance)

- **Given**: `BedrockService` のインスタンスを作成する (bedrock_client をモック)
- **When**: `isinstance(service, AIService)` を評価する
- **Then**: `True` が返される

### TC-QG-004-003: StrandsAIService.generate_cards() のシグネチャが Protocol と一致

- **Given**: `StrandsAIService` のインスタンスと `AIService.generate_cards` の `inspect.signature()`
- **When**: パラメータ名 (`input_text`, `card_count`, `difficulty`, `language`) とデフォルト値 (`5`, `"medium"`, `"ja"`) を比較する
- **Then**: 全パラメータ名が一致し、デフォルト値が同一である

### TC-QG-004-004: StrandsAIService.grade_answer() のシグネチャが Protocol と一致

- **Given**: `StrandsAIService` のインスタンスと `AIService.grade_answer` の `inspect.signature()`
- **When**: パラメータ名 (`card_front`, `card_back`, `user_answer`, `language`) とデフォルト値 (`"ja"`) を比較する
- **Then**: 全パラメータ名が一致し、デフォルト値が同一である

### TC-QG-004-005: StrandsAIService.get_learning_advice() のシグネチャが Protocol と一致

- **Given**: `StrandsAIService` のインスタンスと `AIService.get_learning_advice` の `inspect.signature()`
- **When**: パラメータ名 (`review_summary`, `language`) とデフォルト値 (`"ja"`) を比較する
- **Then**: 全パラメータ名が一致し、デフォルト値が同一である

### TC-QG-004-006: BedrockService.generate_cards() のシグネチャが Protocol と一致

- **Given**: `BedrockService` のインスタンスと `AIService.generate_cards` の `inspect.signature()`
- **When**: パラメータ名 (`input_text`, `card_count`, `difficulty`, `language`) とデフォルト値 (`5`, `"medium"`, `"ja"`) を比較する
- **Then**: 全パラメータ名が一致し、デフォルト値が同一である

### TC-QG-004-007: BedrockService.grade_answer() のシグネチャが Protocol と一致

- **Given**: `BedrockService` のインスタンスと `AIService.grade_answer` の `inspect.signature()`
- **When**: パラメータ名 (`card_front`, `card_back`, `user_answer`, `language`) とデフォルト値 (`"ja"`) を比較する
- **Then**: 全パラメータ名が一致し、デフォルト値が同一である

### TC-QG-004-008: BedrockService.get_learning_advice() のシグネチャが Protocol と一致

- **Given**: `BedrockService` のインスタンスと `AIService.get_learning_advice` の `inspect.signature()`
- **When**: パラメータ名 (`review_summary`, `language`) とデフォルト値 (`"ja"`) を比較する
- **Then**: 全パラメータ名が一致し、デフォルト値が同一である

### TC-QG-004-009: StrandsAIService の全 Protocol メソッドが同期 (非 async)

- **Given**: `StrandsAIService` のインスタンス
- **When**: `asyncio.iscoroutinefunction()` で `generate_cards`, `grade_answer`, `get_learning_advice` をチェック
- **Then**: 全てが `False` を返す (同期メソッドである)

### TC-QG-004-010: BedrockService の全 Protocol メソッドが同期 (非 async)

- **Given**: `BedrockService` のインスタンス
- **When**: `asyncio.iscoroutinefunction()` で `generate_cards`, `grade_answer`, `get_learning_advice` をチェック
- **Then**: 全てが `False` を返す (同期メソッドである)

### TC-QG-004-011: StrandsAIService が generate_cards/grade_answer/get_learning_advice の全 3 メソッドを持つ

- **Given**: `StrandsAIService` のインスタンス
- **When**: `hasattr()` と `callable()` で 3 メソッドの存在をチェック
- **Then**: 3 メソッドが全て存在し callable である

### TC-QG-004-012: BedrockService が generate_cards/grade_answer/get_learning_advice の全 3 メソッドを持つ

- **Given**: `BedrockService` のインスタンス
- **When**: `hasattr()` と `callable()` で 3 メソッドの存在をチェック
- **Then**: 3 メソッドが全て存在し callable である

---

## カテゴリ 2: ファクトリルーティング (TestFactoryRoutingFinal)

`create_ai_service()` ファクトリ関数の `USE_STRANDS` 環境変数に基づくルーティングを最終検証する。
対象: `backend/src/services/ai_service.py` の `create_ai_service()`

### TC-QG-005-001: USE_STRANDS=true で StrandsAIService インスタンスを返す

- **Given**: 環境変数 `USE_STRANDS=true` を設定し、`StrandsAIService` の依存をモック
- **When**: `create_ai_service()` を引数なしで呼び出す
- **Then**: 返されたインスタンスが `StrandsAIService` である

### TC-QG-005-002: USE_STRANDS=false で BedrockService インスタンスを返す

- **Given**: 環境変数 `USE_STRANDS=false` を設定し、`BedrockService` をモック
- **When**: `create_ai_service()` を引数なしで呼び出す
- **Then**: `BedrockService()` が呼ばれ、そのインスタンスが返される

### TC-QG-005-003: USE_STRANDS 未設定でデフォルト BedrockService を返す

- **Given**: 環境変数 `USE_STRANDS` を未設定にし、`BedrockService` をモック
- **When**: `create_ai_service()` を引数なしで呼び出す
- **Then**: `BedrockService()` が呼ばれる (デフォルト値 `"false"` が適用される)

### TC-QG-005-004: use_strands=True パラメータが環境変数をオーバーライド

- **Given**: 環境変数 `USE_STRANDS=false` を設定し、`StrandsAIService` の依存をモック
- **When**: `create_ai_service(use_strands=True)` を呼び出す
- **Then**: `StrandsAIService` インスタンスが返される (環境変数 `false` を無視)

### TC-QG-005-005: use_strands=False パラメータが環境変数をオーバーライド

- **Given**: 環境変数 `USE_STRANDS=true` を設定し、`BedrockService` をモック
- **When**: `create_ai_service(use_strands=False)` を呼び出す
- **Then**: `BedrockService()` が呼ばれる (環境変数 `true` を無視)

### TC-QG-005-006: USE_STRANDS の大文字小文字不問 ("True", "TRUE", "true" 全て StrandsAIService)

- **Given**: 環境変数 `USE_STRANDS` に `"True"`, `"TRUE"`, `"true"` をそれぞれ設定
- **When**: 各設定値で `create_ai_service()` を呼び出す (parametrize)
- **Then**: 全てのケースで `StrandsAIService` が返される

### TC-QG-005-007: 初期化失敗時に AIProviderError を raise

- **Given**: `BedrockService` コンストラクタが `RuntimeError` を raise するようモック
- **When**: `create_ai_service(use_strands=False)` を呼び出す
- **Then**: `AIProviderError` が raise され、メッセージに "Failed to initialize AI service" が含まれる

### TC-QG-005-008: 初期化失敗時に元の例外がチェーンされる (__cause__)

- **Given**: `BedrockService` コンストラクタが `RuntimeError("init failed")` を raise するようモック
- **When**: `create_ai_service(use_strands=False)` を呼び出す
- **Then**: `AIProviderError.__cause__` が `RuntimeError` インスタンスである

---

## カテゴリ 3: モデルプロバイダー選択 (TestModelProviderSelectionFinal)

`StrandsAIService._create_model()` の `ENVIRONMENT` 環境変数に基づくモデルプロバイダー選択を最終検証する。
対象: `backend/src/services/strands_service.py`

### TC-QG-006-001: ENVIRONMENT=dev で OllamaModel が選択される

- **Given**: 環境変数 `ENVIRONMENT=dev` を設定し、`OllamaModel` と `BedrockModel` をモック
- **When**: `StrandsAIService()` を作成する
- **Then**: `OllamaModel()` が呼ばれ、`BedrockModel()` は呼ばれない

### TC-QG-006-002: ENVIRONMENT=prod で BedrockModel が選択される

- **Given**: 環境変数 `ENVIRONMENT=prod` を設定し、`BedrockModel` をモック
- **When**: `StrandsAIService()` を作成する
- **Then**: `BedrockModel()` が呼ばれる

### TC-QG-006-003: ENVIRONMENT=staging で BedrockModel が選択される

- **Given**: 環境変数 `ENVIRONMENT=staging` を設定し、`BedrockModel` をモック
- **When**: `StrandsAIService()` を作成する
- **Then**: `BedrockModel()` が呼ばれる

### TC-QG-006-004: ENVIRONMENT 未設定でデフォルト "prod" として BedrockModel

- **Given**: 環境変数 `ENVIRONMENT` を未設定にし、`BedrockModel` をモック
- **When**: `StrandsAIService()` を作成する
- **Then**: `BedrockModel()` が呼ばれる (デフォルト "prod" が適用される)

### TC-QG-006-005: ENVIRONMENT=dev 時 OLLAMA_HOST / OLLAMA_MODEL 環境変数が反映される

- **Given**: `ENVIRONMENT=dev`, `OLLAMA_HOST=http://custom:11434`, `OLLAMA_MODEL=gemma2` を設定し、`OllamaModel` をモック
- **When**: `StrandsAIService()` を作成する
- **Then**: `OllamaModel(host="http://custom:11434", model_id="gemma2")` で呼ばれる

### TC-QG-006-006: ENVIRONMENT=dev 時 OLLAMA_HOST 未設定はデフォルト http://localhost:11434

- **Given**: `ENVIRONMENT=dev` を設定し、`OLLAMA_HOST` を未設定に。`OllamaModel` をモック
- **When**: `StrandsAIService()` を作成する
- **Then**: `OllamaModel(host="http://localhost:11434", model_id="llama3.2")` で呼ばれる

### TC-QG-006-007: BEDROCK_MODEL_ID 環境変数がカスタムモデル ID に反映される

- **Given**: `ENVIRONMENT=prod`, `BEDROCK_MODEL_ID=anthropic.claude-3-sonnet-20240229-v1:0` を設定
- **When**: `StrandsAIService()` を作成する
- **Then**: `BedrockModel(model_id="anthropic.claude-3-sonnet-20240229-v1:0")` で呼ばれる

### TC-QG-006-008: model_used フィールドが ENVIRONMENT=dev で "strands_ollama"、それ以外で "strands_bedrock"

- **Given**: `ENVIRONMENT=dev` と `ENVIRONMENT=prod` の 2 ケースで `StrandsAIService` を作成
- **When**: `service.model_used` を確認する
- **Then**: `ENVIRONMENT=dev` -> `"strands_ollama"`, `ENVIRONMENT=prod` -> `"strands_bedrock"`

---

## カテゴリ 4: 例外階層の正確性 (TestExceptionHierarchyFinal)

例外クラスの継承関係を最終検証する。
対象: `backend/src/services/ai_service.py` (共通例外), `backend/src/services/bedrock.py` (Bedrock 固有例外)

### TC-QG-009-001: 全 5 共通例外が AIServiceError のサブクラス

- **Given**: `AITimeoutError`, `AIRateLimitError`, `AIInternalError`, `AIParseError`, `AIProviderError`
- **When**: 各クラスに対して `issubclass(cls, AIServiceError)` を評価する (parametrize)
- **Then**: 全て `True` を返す

### TC-QG-009-002: BedrockTimeoutError が BedrockServiceError と AITimeoutError の両方のサブクラス (多重継承)

- **Given**: `BedrockTimeoutError` クラス
- **When**: `issubclass(BedrockTimeoutError, BedrockServiceError)` と `issubclass(BedrockTimeoutError, AITimeoutError)` を評価
- **Then**: 両方 `True` を返す

### TC-QG-009-003: BedrockRateLimitError が BedrockServiceError と AIRateLimitError の両方のサブクラス

- **Given**: `BedrockRateLimitError` クラス
- **When**: `issubclass(BedrockRateLimitError, BedrockServiceError)` と `issubclass(BedrockRateLimitError, AIRateLimitError)` を評価
- **Then**: 両方 `True` を返す

### TC-QG-009-004: BedrockInternalError が BedrockServiceError と AIInternalError の両方のサブクラス

- **Given**: `BedrockInternalError` クラス
- **When**: `issubclass(BedrockInternalError, BedrockServiceError)` と `issubclass(BedrockInternalError, AIInternalError)` を評価
- **Then**: 両方 `True` を返す

### TC-QG-009-005: BedrockParseError が BedrockServiceError と AIParseError の両方のサブクラス

- **Given**: `BedrockParseError` クラス
- **When**: `issubclass(BedrockParseError, BedrockServiceError)` と `issubclass(BedrockParseError, AIParseError)` を評価
- **Then**: 両方 `True` を返す

### TC-QG-009-006: 各 Bedrock 例外が AIServiceError で catch 可能

- **Given**: `BedrockTimeoutError`, `BedrockRateLimitError`, `BedrockInternalError`, `BedrockParseError` のインスタンス
- **When**: `pytest.raises(AIServiceError)` ブロック内で各例外を raise する (parametrize)
- **Then**: 全てが `AIServiceError` として catch される

### TC-QG-009-007: BedrockServiceError 自体が AIServiceError のサブクラス

- **Given**: `BedrockServiceError` クラス
- **When**: `issubclass(BedrockServiceError, AIServiceError)` を評価
- **Then**: `True` を返す

### TC-QG-009-008: AIServiceError が Exception のサブクラス

- **Given**: `AIServiceError` クラス
- **When**: `issubclass(AIServiceError, Exception)` を評価
- **Then**: `True` を返す

---

## カテゴリ 5: StrandsAIService エラーハンドリング一貫性 (TestStrandsErrorHandlingFinal)

`StrandsAIService` の 3 メソッド全てが同一のエラーハンドリングパターンを実装していることを最終検証する。
対象: `backend/src/services/strands_service.py` の `generate_cards()`, `grade_answer()`, `get_learning_advice()`

### TC-QG-011-001: TimeoutError -> AITimeoutError (generate_cards)

- **Given**: `Agent.__call__` が `TimeoutError("Agent timed out")` を raise するようモック
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `AITimeoutError` が raise される

### TC-QG-011-002: TimeoutError -> AITimeoutError (grade_answer)

- **Given**: `Agent.__call__` が `TimeoutError("Agent timed out")` を raise するようモック
- **When**: `service.grade_answer(card_front="Q", card_back="A", user_answer="A")` を呼び出す
- **Then**: `AITimeoutError` が raise される

### TC-QG-011-003: TimeoutError -> AITimeoutError (get_learning_advice)

- **Given**: `Agent.__call__` が `TimeoutError("Agent timed out")` を raise するようモック
- **When**: `service.get_learning_advice(review_summary={})` を呼び出す
- **Then**: `AITimeoutError` が raise される

### TC-QG-011-004: ConnectionError -> AIProviderError (全 3 メソッド parametrize)

- **Given**: `Agent.__call__` が `ConnectionError("Connection refused")` を raise するようモック
- **When**: `generate_cards`, `grade_answer`, `get_learning_advice` の各メソッドを呼び出す (parametrize)
- **Then**: 全てで `AIProviderError` が raise される

### TC-QG-011-005: botocore ThrottlingException -> AIRateLimitError (全 3 メソッド parametrize)

- **Given**: `Agent.__call__` が `ClientError({"Error": {"Code": "ThrottlingException", ...}}, ...)` を raise するようモック
- **When**: `generate_cards`, `grade_answer`, `get_learning_advice` の各メソッドを呼び出す (parametrize)
- **Then**: 全てで `AIRateLimitError` が raise される

### TC-QG-011-006: エラーメッセージに "timeout" を含む例外 -> AITimeoutError (全 3 メソッド parametrize)

- **Given**: `Agent.__call__` が `RuntimeError("request timeout exceeded")` を raise するようモック
- **When**: `generate_cards`, `grade_answer`, `get_learning_advice` の各メソッドを呼び出す (parametrize)
- **Then**: 全てで `AITimeoutError` が raise される

### TC-QG-011-007: エラーメッセージに "connection" を含む例外 -> AIProviderError (全 3 メソッド parametrize)

- **Given**: `Agent.__call__` が `RuntimeError("connection reset by peer")` を raise するようモック
- **When**: `generate_cards`, `grade_answer`, `get_learning_advice` の各メソッドを呼び出す (parametrize)
- **Then**: 全てで `AIProviderError` が raise される

### TC-QG-011-008: 既に AIServiceError サブクラスの例外はそのまま re-raise (全 3 メソッド)

- **Given**: `Agent.__call__` が正常応答を返すが、パース結果で `AIParseError` が raise されるレスポンスをモック
- **When**: `generate_cards` (cards フィールド欠落), `grade_answer` (grade 欠落), `get_learning_advice` (advice_text 欠落) を呼び出す
- **Then**: 全てで `AIParseError` がそのまま raise される (AIServiceError にラップされない)

### TC-QG-011-009: その他の例外 -> AIServiceError("Unexpected error: ...") (全 3 メソッド parametrize)

- **Given**: `Agent.__call__` が `RuntimeError("Something unexpected")` を raise するようモック
- **When**: `generate_cards`, `grade_answer`, `get_learning_advice` の各メソッドを呼び出す (parametrize)
- **Then**: 全てで `AIServiceError` が raise され、メッセージに "Unexpected error" が含まれる

### TC-QG-011-010: 例外チェーン (__cause__) が全 3 メソッドで保持される

- **Given**: `Agent.__call__` が `ConnectionError("Connection refused")` を raise するようモック
- **When**: `generate_cards`, `grade_answer`, `get_learning_advice` の各メソッドで例外を catch
- **Then**: 全てで `exc.__cause__` が `None` ではない (元の例外が保持されている)

### TC-QG-011-011: エラーメッセージに "timed out" を含む例外 -> AITimeoutError (全 3 メソッド)

- **Given**: `Agent.__call__` が `RuntimeError("operation timed out waiting for response")` を raise するようモック
- **When**: `generate_cards`, `grade_answer`, `get_learning_advice` を呼び出す (parametrize)
- **Then**: 全てで `AITimeoutError` が raise される ("timed out" キーワードも検出される)

### TC-QG-011-012: 例外クラス名に "connect" を含む例外 -> AIProviderError (全 3 メソッド)

- **Given**: `Agent.__call__` が `type("ConnectError", (Exception,), {})("failed")` を raise するようモック
- **When**: `generate_cards`, `grade_answer`, `get_learning_advice` を呼び出す (parametrize)
- **Then**: 全てで `AIProviderError` が raise される (クラス名に "connect" を含むため)

---

## カテゴリ 6: BedrockService エラーハンドリング (TestBedrockErrorHandlingFinal)

`BedrockService` のエラーマッピングとリトライロジックを最終検証する。
対象: `backend/src/services/bedrock.py` の `_invoke_claude()`, `_invoke_with_retry()`

### TC-QG-012-001: ClientError "ReadTimeoutError" -> BedrockTimeoutError

- **Given**: `bedrock_client.invoke_model` が `ClientError({"Error": {"Code": "ReadTimeoutError"}}, ...)` を raise するようモック
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `BedrockTimeoutError` が raise される

### TC-QG-012-002: ClientError "ThrottlingException" -> BedrockRateLimitError

- **Given**: `bedrock_client.invoke_model` が `ClientError({"Error": {"Code": "ThrottlingException"}}, ...)` を raise するようモック
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `BedrockRateLimitError` が raise される

### TC-QG-012-003: ClientError "InternalServerException" -> BedrockInternalError

- **Given**: `bedrock_client.invoke_model` が `ClientError({"Error": {"Code": "InternalServerException"}}, ...)` を raise するようモック
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `BedrockInternalError` が raise される

### TC-QG-012-004: BedrockRateLimitError に対してリトライが最大 MAX_RETRIES (2) 回実行される

- **Given**: `bedrock_client.invoke_model` が常に `ClientError ThrottlingException` を raise するようモック。`time.sleep` をモック
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `invoke_model` が合計 3 回 (初回 + リトライ 2 回) 呼ばれた後、`BedrockRateLimitError` が raise される

### TC-QG-012-005: BedrockTimeoutError に対してリトライなし (即座に raise)

- **Given**: `bedrock_client.invoke_model` が `ClientError ReadTimeoutError` を raise するようモック
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `invoke_model` が 1 回だけ呼ばれ、`BedrockTimeoutError` が即座に raise される

### TC-QG-012-006: リトライ間隔が Full Jitter Exponential Backoff パターンに従う

- **Given**: `BedrockService` の `_retry_with_jitter(attempt)` メソッド
- **When**: `attempt=0`, `attempt=1`, `attempt=2` でそれぞれ呼び出す (複数回)
- **Then**: 全ての戻り値が `0 <= delay <= min(2^attempt, 30)` の範囲内である

---

## カテゴリ 7: 全エンドポイント動作検証 (TestEndpointFunctionalFinal)

USE_STRANDS 環境変数の各状態で全 3 AI エンドポイントが HTTP 200 を返すことを最終検証する。
対象: `backend/src/api/handler.py` の `handler()`, `grade_ai_handler()`, `advice_handler()`

### TC-QG-007-001: USE_STRANDS=true で POST /cards/generate が HTTP 200 を返す

- **Given**: `USE_STRANDS=true` 環境変数、`create_ai_service()` がモックサービスを返すよう設定
- **When**: `handler(generate_event, lambda_context)` を呼び出す
- **Then**: `response["statusCode"] == 200`

### TC-QG-007-002: USE_STRANDS=true で POST /reviews/{cardId}/grade-ai が HTTP 200 を返す

- **Given**: `USE_STRANDS=true` 環境変数、`create_ai_service()` と `card_service.get_card()` をモック
- **When**: `grade_ai_handler(grade_event, lambda_context)` を呼び出す
- **Then**: `response["statusCode"] == 200`

### TC-QG-007-003: USE_STRANDS=true で GET /advice が HTTP 200 を返す

- **Given**: `USE_STRANDS=true` 環境変数、`create_ai_service()` と `review_service.get_review_summary()` をモック
- **When**: `advice_handler(advice_event, lambda_context)` を呼び出す
- **Then**: `response["statusCode"] == 200`

### TC-QG-007-004: USE_STRANDS=false で POST /cards/generate が HTTP 200 を返す

- **Given**: `USE_STRANDS=false` 環境変数、同上のモック設定
- **When**: `handler(generate_event, lambda_context)` を呼び出す
- **Then**: `response["statusCode"] == 200`

### TC-QG-007-005: USE_STRANDS=false で POST /reviews/{cardId}/grade-ai が HTTP 200 を返す

- **Given**: `USE_STRANDS=false` 環境変数、同上のモック設定
- **When**: `grade_ai_handler(grade_event, lambda_context)` を呼び出す
- **Then**: `response["statusCode"] == 200`

### TC-QG-007-006: USE_STRANDS=false で GET /advice が HTTP 200 を返す

- **Given**: `USE_STRANDS=false` 環境変数、同上のモック設定
- **When**: `advice_handler(advice_event, lambda_context)` を呼び出す
- **Then**: `response["statusCode"] == 200`

### TC-QG-007-007: USE_STRANDS 未設定で全 3 エンドポイントがデフォルト動作 (HTTP 200)

- **Given**: `USE_STRANDS` 環境変数を除去し、同上のモック設定
- **When**: `handler`, `grade_ai_handler`, `advice_handler` を順に呼び出す
- **Then**: 全てが `statusCode == 200` を返す

---

## カテゴリ 8: レスポンスフォーマット検証 (TestResponseFormatFinal)

各エンドポイントのレスポンス構造が API 仕様に準拠していることを最終検証する。

### TC-QG-008-001: POST /cards/generate レスポンスに generated_cards 配列 + generation_info が含まれる

- **Given**: `create_ai_service()` がモックカード生成結果を返すよう設定
- **When**: `handler(generate_event, lambda_context)` を呼び出してレスポンス body を JSON パース
- **Then**: `body` に `"generated_cards"` (配列) と `"generation_info"` (オブジェクト) が含まれる

### TC-QG-008-002: POST /cards/generate の generated_cards[].front, back, suggested_tags が存在

- **Given**: TC-QG-008-001 と同一の設定
- **When**: レスポンスの `generated_cards[0]` を検査する
- **Then**: `"front"`, `"back"`, `"suggested_tags"` フィールドが存在する

### TC-QG-008-003: POST /cards/generate の generation_info に input_length, model_used, processing_time_ms が存在

- **Given**: TC-QG-008-001 と同一の設定
- **When**: レスポンスの `generation_info` を検査する
- **Then**: `"input_length"`, `"model_used"`, `"processing_time_ms"` フィールドが存在する

### TC-QG-008-004: POST /reviews/{cardId}/grade-ai レスポンスに grade, reasoning, card_front, card_back, grading_info が含まれる

- **Given**: `create_ai_service()` がモック採点結果 (`GradingResult`) を返すよう設定
- **When**: `grade_ai_handler(grade_event, lambda_context)` を呼び出してレスポンス body を JSON パース
- **Then**: `body` に `"grade"`, `"reasoning"`, `"card_front"`, `"card_back"`, `"grading_info"` が含まれる

### TC-QG-008-005: POST /reviews/{cardId}/grade-ai の grade が int 型で 0-5 範囲

- **Given**: `GradingResult(grade=4, ...)` をモック
- **When**: レスポンスの `body["grade"]` を検査
- **Then**: `isinstance(body["grade"], int)` かつ `0 <= body["grade"] <= 5`

### TC-QG-008-006: GET /advice レスポンスに advice_text, weak_areas, recommendations, study_stats, advice_info が含まれる

- **Given**: `create_ai_service()` がモックアドバイス結果 (`LearningAdvice`) を返すよう設定
- **When**: `advice_handler(advice_event, lambda_context)` を呼び出してレスポンス body を JSON パース
- **Then**: `body` に `"advice_text"`, `"weak_areas"`, `"recommendations"`, `"study_stats"`, `"advice_info"` が含まれる

### TC-QG-008-007: GET /advice の advice_info に model_used, processing_time_ms が存在

- **Given**: TC-QG-008-006 と同一の設定
- **When**: レスポンスの `advice_info` を検査する
- **Then**: `"model_used"`, `"processing_time_ms"` フィールドが存在する

---

## カテゴリ 9: クロスエンドポイントエラーマッピング (TestCrossEndpointErrorMappingFinal)

AI サービスの各例外タイプが全 3 エンドポイントで同一の HTTP ステータスコードにマッピングされることを最終検証する。
対象: `backend/src/api/handler.py` の `_map_ai_error_to_http()`

### TC-QG-010-001: AITimeoutError -> 全 3 エンドポイントで HTTP 504

- **Given**: AI サービスの全メソッドが `AITimeoutError("timeout")` を raise するようモック
- **When**: `handler`, `grade_ai_handler`, `advice_handler` を順に呼び出す
- **Then**: 3 件全て `statusCode == 504` かつ `body.error == "AI service timeout"`

### TC-QG-010-002: AIRateLimitError -> 全 3 エンドポイントで HTTP 429

- **Given**: AI サービスの全メソッドが `AIRateLimitError("rate limit")` を raise するようモック
- **When**: `handler`, `grade_ai_handler`, `advice_handler` を順に呼び出す
- **Then**: 3 件全て `statusCode == 429` かつ `body.error == "AI service rate limit exceeded"`

### TC-QG-010-003: AIProviderError -> 全 3 エンドポイントで HTTP 503

- **Given**: AI サービスの全メソッドが `AIProviderError("provider down")` を raise するようモック
- **When**: `handler`, `grade_ai_handler`, `advice_handler` を順に呼び出す
- **Then**: 3 件全て `statusCode == 503` かつ `body.error == "AI service unavailable"`

### TC-QG-010-004: AIParseError -> 全 3 エンドポイントで HTTP 500

- **Given**: AI サービスの全メソッドが `AIParseError("invalid json")` を raise するようモック
- **When**: `handler`, `grade_ai_handler`, `advice_handler` を順に呼び出す
- **Then**: 3 件全て `statusCode == 500` かつ `body.error == "AI service response parse error"`

### TC-QG-010-005: AIInternalError -> 全 3 エンドポイントで HTTP 500

- **Given**: AI サービスの全メソッドが `AIInternalError("internal failure")` を raise するようモック
- **When**: `handler`, `grade_ai_handler`, `advice_handler` を順に呼び出す
- **Then**: 3 件全て `statusCode == 500` かつ `body.error == "AI service error"`

### TC-QG-010-006: AIServiceError (基底) -> 全 3 エンドポイントで HTTP 500

- **Given**: AI サービスの全メソッドが `AIServiceError("generic error")` を raise するようモック
- **When**: `handler`, `grade_ai_handler`, `advice_handler` を順に呼び出す
- **Then**: 3 件全て `statusCode == 500` かつ `body.error == "AI service error"`

### TC-QG-010-007: create_ai_service() 初期化失敗 -> 全 3 エンドポイントで HTTP 503

- **Given**: `create_ai_service()` 自体が `AIProviderError("Failed to initialize")` を raise するようモック
- **When**: `handler`, `grade_ai_handler`, `advice_handler` を順に呼び出す
- **Then**: 3 件全て `statusCode == 503` かつ `body.error == "AI service unavailable"`

---

## カテゴリ 10: StrandsAIService レスポンス解析 (TestStrandsResponseParsingFinal)

`StrandsAIService` の 3 つのパーサー (`_parse_generation_result`, `_parse_grading_result`, `_parse_advice_result`) の動作を最終検証する。
対象: `backend/src/services/strands_service.py`

### TC-QG-013-001: プレーン JSON レスポンスが正しく解析される (generate_cards)

- **Given**: Agent レスポンスが `{"cards": [{"front": "Q", "back": "A", "tags": ["tag"]}]}` の JSON 文字列
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `result.cards` に 1 枚のカードが含まれ、`front=="Q"`, `back=="A"` である

### TC-QG-013-002: Markdown ```json ... ``` コードブロックが正しく解析される (generate_cards)

- **Given**: Agent レスポンスが `` ```json\n{"cards": [{"front": "Q", "back": "A", "tags": []}]}\n``` ``
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `result.cards` に 1 枚のカードが含まれる

### TC-QG-013-003: "cards" フィールド欠落時に AIParseError が raise される

- **Given**: Agent レスポンスが `{"data": []}` (cards なし)
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `AIParseError` が raise される

### TC-QG-013-004: 不正 JSON 文字列に対して AIParseError が raise される

- **Given**: Agent レスポンスが `"This is not valid JSON at all"`
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `AIParseError` が raise される

### TC-QG-013-005: front/back 欠落のカードがスキップされる (空でないカードのみ返却)

- **Given**: Agent レスポンスに front 欠落、back 欠落、有効の 3 カードが含まれる
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: 有効な 1 枚のカードのみが返される

### TC-QG-013-006: 有効カード 0 枚時に AIParseError が raise される

- **Given**: Agent レスポンスの全カードが `front==""` または `back` 欠落
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `AIParseError` が raise される

### TC-QG-013-007: "AI生成" タグが未設定のカードに自動挿入される

- **Given**: Agent レスポンスが `{"cards": [{"front": "Q", "back": "A"}]}` (tags なし)
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `result.cards[0].suggested_tags` に `"AI生成"` が含まれる

### TC-QG-013-008: grade_answer パース: "grade" / "reasoning" 欠落時に AIParseError

- **Given**: Agent レスポンスが `{"reasoning": "..."}` (grade 欠落) または `{"grade": 5}` (reasoning 欠落)
- **When**: `service.grade_answer(card_front="Q", card_back="A", user_answer="A")` を呼び出す
- **Then**: `AIParseError` が raise される

### TC-QG-013-009: grade_answer パース: grade が整数に変換できない場合に AIParseError

- **Given**: Agent レスポンスが `{"grade": "five", "reasoning": "..."}`
- **When**: `service.grade_answer(card_front="Q", card_back="A", user_answer="A")` を呼び出す
- **Then**: `AIParseError` が raise される

### TC-QG-013-010: get_learning_advice パース: "advice_text" / "weak_areas" / "recommendations" 欠落時に AIParseError

- **Given**: Agent レスポンスに `"advice_text"`, `"weak_areas"`, `"recommendations"` のいずれかが欠落 (parametrize)
- **When**: `service.get_learning_advice(review_summary={})` を呼び出す
- **Then**: `AIParseError` が raise される

---

## カテゴリ 11: BedrockService レスポンス解析 (TestBedrockResponseParsingFinal)

`BedrockService` のパーサー (`_parse_response`, `_parse_json_response`) の動作を最終検証する。
対象: `backend/src/services/bedrock.py`

### TC-QG-014-001: プレーン JSON レスポンスが正しく解析される (generate_cards)

- **Given**: Bedrock API が `{"cards": [{"front": "Q", "back": "A", "tags": ["tag"]}]}` を返すようモック
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `result.cards` に 1 枚のカードが含まれる

### TC-QG-014-002: Markdown ```json ... ``` コードブロックが正しく解析される

- **Given**: Bedrock API が `` ```json\n{"cards": [{"front": "Q", "back": "A", "tags": []}]}\n``` `` を返すようモック
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `result.cards` に 1 枚のカードが含まれる

### TC-QG-014-003: "cards" フィールド欠落時に BedrockParseError が raise される

- **Given**: Bedrock API が `{"data": []}` (cards なし) を返すようモック
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `BedrockParseError` が raise される

### TC-QG-014-004: 必須フィールド欠落時に BedrockParseError (grade, advice)

- **Given**: Bedrock API が grade_answer で `{"reasoning": "..."}` (grade 欠落), get_learning_advice で `{"advice_text": "...", "weak_areas": []}` (recommendations 欠落) を返すようモック
- **When**: `service.grade_answer(...)`, `service.get_learning_advice(...)` を呼び出す
- **Then**: `BedrockParseError` が raise される

### TC-QG-014-005: 不正 JSON 文字列に対して BedrockParseError が raise される

- **Given**: Bedrock API が `"Not valid JSON"` を返すようモック
- **When**: `service.generate_cards(input_text="test")` を呼び出す
- **Then**: `BedrockParseError` が raise される

---

## カテゴリ 12: プロンプトセキュリティ (TestPromptSecurityFinal)

プロンプトテンプレートとシステムプロンプトの構造的分離を最終検証する。
対象: `backend/src/services/prompts/generate.py`, `grading.py`, `advice.py`

### TC-QG-015-001: get_card_generation_prompt() が入力テキストをテンプレートに埋め込んで返す

- **Given**: `input_text="テストテキスト"`, `card_count=3`, `difficulty="medium"`, `language="ja"`
- **When**: `get_card_generation_prompt(input_text, card_count, difficulty, language)` を呼び出す
- **Then**: 返り値に `"テストテキスト"` が含まれ、`"3"` (カード枚数) が含まれる

### TC-QG-015-002: get_grading_prompt() が card_front, card_back, user_answer を埋め込んで返す

- **Given**: `card_front="日本の首都は？"`, `card_back="東京"`, `user_answer="東京"`
- **When**: `get_grading_prompt(card_front, card_back, user_answer)` を呼び出す
- **Then**: 返り値に `"日本の首都は？"`, `"東京"` が含まれる

### TC-QG-015-003: get_advice_prompt() が review_summary データを埋め込んで返す

- **Given**: `review_summary={"total_reviews": 100, "average_grade": 3.5, "total_cards": 50, "cards_due_today": 10, "streak_days": 7}`
- **When**: `get_advice_prompt(review_summary, language="ja")` を呼び出す
- **Then**: 返り値に `"100"`, `"3.5"`, `"50"` が含まれる

### TC-QG-015-004: GRADING_SYSTEM_PROMPT 定数がユーザー入力変数を含まない

- **Given**: `GRADING_SYSTEM_PROMPT` 定数文字列
- **When**: 文字列内に Python のフォーマット変数 (`{card_front}`, `{user_answer}` 等) が含まれないかチェック
- **Then**: `{card_front}`, `{card_back}`, `{user_answer}`, `{input_text}` のいずれも含まれない

### TC-QG-015-005: ADVICE_SYSTEM_PROMPT 定数がユーザー入力変数を含まない

- **Given**: `ADVICE_SYSTEM_PROMPT` 定数文字列
- **When**: 文字列内に Python のフォーマット変数 (`{review_summary}`, `{total_reviews}` 等) が含まれないかチェック
- **Then**: `{review_summary}`, `{total_reviews}`, `{average_grade}`, `{input_text}` のいずれも含まれない

---

## 手動確認項目 (テストコードに含めない)

以下はテストコード内で実装せず、`pytest` コマンドの実行結果で手動確認する項目。

### HC-QG-001: 全テスト通過確認

```bash
cd backend && make test
```

- [ ] pytest 実行結果が exit code 0 (全テスト PASS)
- [ ] テスト総数が 651 件以上 (新規追加分含む)
- [ ] FAILED 数が 0 件
- [ ] ERROR 数が 0 件

### HC-QG-002: 既存テスト保護 (非回帰)

- [ ] 既存 AI 関連テスト (test_ai_service.py, test_strands_service.py, test_bedrock.py 等) が全て PASS
- [ ] 既存非 AI テスト (test_card_service.py, test_srs.py 等) が全て PASS

### HC-QG-003: テストカバレッジ 80% 以上

```bash
cd backend && pytest --cov=src --cov-report=term-missing --cov-fail-under=80
```

- [ ] 全体カバレッジが 80% 以上
- [ ] `src/services/ai_service.py` のカバレッジが 85% 以上
- [ ] `src/services/strands_service.py` のカバレッジが 85% 以上
- [ ] `src/services/bedrock.py` のカバレッジが 80% 以上

### HC-QG-004: ドキュメント更新

- [ ] CLAUDE.md に ai-strands-migration セクションが追加されている
- [ ] overview.md の TASK-0065 状態が `[x]` に更新されている

---

## テスト実装方針

### ファイル構成

```
backend/tests/unit/test_quality_gate.py
```

### クラス構成

```python
class TestProtocolComplianceFinal:       # カテゴリ 1 (12 テスト)
class TestFactoryRoutingFinal:           # カテゴリ 2 (8 テスト)
class TestModelProviderSelectionFinal:   # カテゴリ 3 (8 テスト)
class TestExceptionHierarchyFinal:       # カテゴリ 4 (8 テスト)
class TestStrandsErrorHandlingFinal:     # カテゴリ 5 (12 テスト)
class TestBedrockErrorHandlingFinal:     # カテゴリ 6 (6 テスト)
class TestEndpointFunctionalFinal:       # カテゴリ 7 (7 テスト)
class TestResponseFormatFinal:           # カテゴリ 8 (7 テスト)
class TestCrossEndpointErrorMappingFinal: # カテゴリ 9 (7 テスト)
class TestStrandsResponseParsingFinal:   # カテゴリ 10 (10 テスト)
class TestBedrockResponseParsingFinal:   # カテゴリ 11 (5 テスト)
class TestPromptSecurityFinal:           # カテゴリ 12 (5 テスト)
```

### 既存テストとの関係

- 既存テストファイルは **一切変更しない**
- `test_quality_gate.py` は既存テストを補完する最終品質ゲート
- 既存テスト (test_ai_service.py, test_strands_service.py, test_bedrock.py 等) と部分的に重複するが、独立した横断的・包括的な品質検証を目的とする

### モック戦略

- **StrandsAIService**: `Agent` と `BedrockModel` / `OllamaModel` をモック
- **BedrockService**: `bedrock_client` (boto3) をモック
- **ハンドラー**: `create_ai_service()`, `card_service`, `review_service` をモック
- **全テストはモックベース** (実際の AI サービスは呼び出さない)

### テスト命名規則

既存テストに合わせ、テストメソッド名は `test_` プレフィックス + 英語の説明。
docstring には TC-QG-XXX-YYY 形式のテスト ID を含める。

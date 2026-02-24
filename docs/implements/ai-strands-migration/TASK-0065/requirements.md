# TASK-0065: 全体統合テスト + 品質確認 - テスト要件定義

**タスクID**: TASK-0065
**タスクタイプ**: TDD
**作成日**: 2026-02-24
**対象**: AI Strands Migration 最終品質ゲート

## 概要

AI Strands Migration (TASK-0052 ~ TASK-0064) の全実装に対する最終品質確認。
全テスト実行、テストカバレッジ確認、既存テスト保護、Protocol 準拠性、ファクトリパターン、
エラーハンドリング一貫性、フィーチャーフラグ動作の網羅的検証を実施する。

### 実装の実態

以下が実際のコードベースにおける正確な情報である（タスクファイル TASK-0065.md の記述と異なる部分あり）。

- **AIService Protocol** (`backend/src/services/ai_service.py`): `generate_cards()`, `grade_answer()`, `get_learning_advice()` の 3 メソッド（全て同期）
- **2 つの実装クラス**: `StrandsAIService` (`strands_service.py`), `BedrockService` (`bedrock.py`)
- **3 つの AI エンドポイント**: `POST /cards/generate`, `POST /reviews/{cardId}/grade-ai`, `GET /advice`
- **ファクトリ関数**: `create_ai_service(use_strands=None)` - `USE_STRANDS` 環境変数を参照
- **StrandsAIService のモデル選択**: `ENVIRONMENT=dev` -> OllamaModel, それ以外 -> BedrockModel
- **テストフレームワーク**: pytest 8.3.5 + pytest-cov
- **現在のテスト数**: ~651 テスト（全 PASS が前提）
- **カバレッジ目標**: 80% 以上
- **mypy --strict は未設定**（このプロジェクトでは使用していない）
- **InputValidationError, sanitize() は未実装**（コードベースに存在しない）

---

## テスト要件（EARS 記法）

### 信頼性レベル凡例

- **BLUE**: ソースコード・既存テスト・設計文書から確実に特定された要件
- **YELLOW**: 技術仕様から妥当な推測による要件
- **RED**: 文書にない推測による要件

---

### カテゴリ 1: 全テスト実行 + 既存テスト保護

#### REQ-QG-001: 全テスト通過確認

**EARS**: システムがテストスイートを実行した場合、全 651+ テストが PASS しなければならない。

**信頼性**: BLUE (REQ-SM-404/405 より。現在のテストスイート数は pytest --collect-only で確認可能)

**テスト方法**:
```bash
cd backend && make test
```

**検証項目**:
- [ ] TC-QG-001-001: `pytest` 実行結果が exit code 0 (全テスト PASS)
- [ ] TC-QG-001-002: テスト総数が 651 件以上（新規追加分含む）
- [ ] TC-QG-001-003: FAILED 数が 0 件
- [ ] TC-QG-001-004: ERROR 数が 0 件

#### REQ-QG-002: 既存テスト保護（非回帰）

**EARS**: AI Strands Migration のテスト追加後、既存テストスイートに回帰が発生してはならない。

**信頼性**: BLUE (REQ-SM-405 より。既存テストは全て保護される)

**検証項目**:
- [ ] TC-QG-002-001: 既存 AI 関連テストファイル（test_ai_service.py, test_strands_service.py, test_bedrock.py, test_bedrock_protocol.py, test_handler_ai_service_factory.py, test_migration_compat.py, test_handler_grade_ai.py, test_handler_advice.py）が全て PASS
- [ ] TC-QG-002-002: 既存非 AI テストファイル（test_card_service.py, test_srs.py, test_user_service.py 等）が全て PASS
- [ ] TC-QG-002-003: 統合テスト (test_integration.py) が全て PASS

---

### カテゴリ 2: テストカバレッジ

#### REQ-QG-003: 全体テストカバレッジ 80% 以上

**EARS**: システムのテストカバレッジが 80% 以上でなければならない。

**信頼性**: BLUE (REQ-SM-404 より。CLAUDE.md にも「テストカバレッジ 80% 以上を目標」と明記)

**テスト方法**:
```bash
cd backend && pytest --cov=src --cov-report=term-missing --cov-fail-under=80
```

**検証項目**:
- [ ] TC-QG-003-001: 全体カバレッジが 80% 以上
- [ ] TC-QG-003-002: `src/services/ai_service.py` のカバレッジが 85% 以上
- [ ] TC-QG-003-003: `src/services/strands_service.py` のカバレッジが 85% 以上
- [ ] TC-QG-003-004: `src/services/bedrock.py` のカバレッジが 80% 以上
- [ ] TC-QG-003-005: `src/services/prompts/` のカバレッジが 75% 以上

---

### カテゴリ 3: Protocol 準拠性

#### REQ-QG-004: 両実装クラスが AIService Protocol を満たす

**EARS**: `StrandsAIService` および `BedrockService` が `AIService` Protocol の全メソッド（`generate_cards()`, `grade_answer()`, `get_learning_advice()`）を実装していなければならない。

**信頼性**: BLUE (AIService Protocol は `@runtime_checkable` で定義済み。既存テストで部分的に検証済みだが、最終ゲートとして包括的に再確認)

**テストケース**:

| ID | テスト内容 | 信頼性 |
|----|-----------|--------|
| TC-QG-004-001 | `isinstance(StrandsAIService(...), AIService)` が True | BLUE |
| TC-QG-004-002 | `isinstance(BedrockService(...), AIService)` が True | BLUE |
| TC-QG-004-003 | `StrandsAIService.generate_cards()` のシグネチャが Protocol と一致 | BLUE |
| TC-QG-004-004 | `StrandsAIService.grade_answer()` のシグネチャが Protocol と一致 | BLUE |
| TC-QG-004-005 | `StrandsAIService.get_learning_advice()` のシグネチャが Protocol と一致 | BLUE |
| TC-QG-004-006 | `BedrockService.generate_cards()` のシグネチャが Protocol と一致 | BLUE |
| TC-QG-004-007 | `BedrockService.grade_answer()` のシグネチャが Protocol と一致 | BLUE |
| TC-QG-004-008 | `BedrockService.get_learning_advice()` のシグネチャが Protocol と一致 | BLUE |
| TC-QG-004-009 | 両実装の全 Protocol メソッドが同期（非 async）である | BLUE |

**実装方針**: `inspect.signature()` で各メソッドのパラメータ名・デフォルト値・戻り値型を Protocol 定義と比較する。`asyncio.iscoroutinefunction()` で同期性を確認する。

---

### カテゴリ 4: ファクトリパターン + フィーチャーフラグ

#### REQ-QG-005: create_ai_service() ファクトリの正しいルーティング

**EARS**: `create_ai_service()` が `USE_STRANDS` 環境変数に応じて正しい実装クラスを返さなければならない。

**信頼性**: BLUE (ファクトリ関数は `ai_service.py` に実装済み。既存テストで部分検証済みだが最終ゲートとして包括確認)

**テストケース**:

| ID | テスト内容 | 信頼性 |
|----|-----------|--------|
| TC-QG-005-001 | `USE_STRANDS=true` -> `StrandsAIService` インスタンスを返す | BLUE |
| TC-QG-005-002 | `USE_STRANDS=false` -> `BedrockService` インスタンスを返す | BLUE |
| TC-QG-005-003 | `USE_STRANDS` 未設定 -> デフォルトで `BedrockService` を返す | BLUE |
| TC-QG-005-004 | `use_strands=True` 明示パラメータが環境変数をオーバーライド | BLUE |
| TC-QG-005-005 | `use_strands=False` 明示パラメータが環境変数をオーバーライド | BLUE |
| TC-QG-005-006 | 大文字小文字不問（"True", "TRUE", "true" -> 全て StrandsAIService） | BLUE |
| TC-QG-005-007 | 初期化失敗時に `AIProviderError` を raise し、元の例外がチェーンされる | BLUE |

#### REQ-QG-006: StrandsAIService のモデルプロバイダー選択

**EARS**: `ENVIRONMENT` 環境変数の値に応じて `StrandsAIService` が正しいモデルプロバイダーを選択しなければならない。

**信頼性**: BLUE (strands_service.py の `_create_model()` メソッドで `ENVIRONMENT` 値による分岐が実装済み)

**テストケース**:

| ID | テスト内容 | 信頼性 |
|----|-----------|--------|
| TC-QG-006-001 | `ENVIRONMENT=dev` -> OllamaModel が選択される | BLUE |
| TC-QG-006-002 | `ENVIRONMENT=prod` -> BedrockModel が選択される | BLUE |
| TC-QG-006-003 | `ENVIRONMENT=staging` -> BedrockModel が選択される | BLUE |
| TC-QG-006-004 | `ENVIRONMENT` 未設定 -> デフォルト "prod" として BedrockModel | BLUE |
| TC-QG-006-005 | `ENVIRONMENT=dev` 時、`OLLAMA_HOST` / `OLLAMA_MODEL` 環境変数が反映される | BLUE |
| TC-QG-006-006 | `ENVIRONMENT=dev` 時、`OLLAMA_HOST` 未設定はデフォルト `http://localhost:11434` | BLUE |
| TC-QG-006-007 | `BEDROCK_MODEL_ID` 環境変数がカスタムモデル ID の指定に反映される | BLUE |
| TC-QG-006-008 | `model_used` フィールドが `ENVIRONMENT=dev` で "strands_ollama"、それ以外で "strands_bedrock" | BLUE |

---

### カテゴリ 5: 全 3 エンドポイント動作検証

#### REQ-QG-007: 全エンドポイントが USE_STRANDS=true/false で動作する

**EARS**: `USE_STRANDS=true` および `USE_STRANDS=false` の両環境変数設定下で、全 3 AI エンドポイント（`POST /cards/generate`, `POST /reviews/{cardId}/grade-ai`, `GET /advice`）が HTTP 200 を返さなければならない。

**信頼性**: BLUE (既存の test_integration.py の TestFeatureFlagConsistency で部分的に検証済み。最終ゲートとして再確認)

**テストケース**:

| ID | テスト内容 | 信頼性 |
|----|-----------|--------|
| TC-QG-007-001 | `USE_STRANDS=true` で POST /cards/generate が HTTP 200 を返す | BLUE |
| TC-QG-007-002 | `USE_STRANDS=true` で POST /reviews/{cardId}/grade-ai が HTTP 200 を返す | BLUE |
| TC-QG-007-003 | `USE_STRANDS=true` で GET /advice が HTTP 200 を返す | BLUE |
| TC-QG-007-004 | `USE_STRANDS=false` で POST /cards/generate が HTTP 200 を返す | BLUE |
| TC-QG-007-005 | `USE_STRANDS=false` で POST /reviews/{cardId}/grade-ai が HTTP 200 を返す | BLUE |
| TC-QG-007-006 | `USE_STRANDS=false` で GET /advice が HTTP 200 を返す | BLUE |
| TC-QG-007-007 | `USE_STRANDS` 未設定で全 3 エンドポイントがデフォルト動作（HTTP 200） | BLUE |

#### REQ-QG-008: 各エンドポイントのレスポンスフォーマット検証

**EARS**: 各エンドポイントが正しいレスポンスフォーマットを返さなければならない。

**信頼性**: BLUE (handler 実装と test_integration.py の TestEndpointE2EFlow で検証済み構造を最終確認)

**テストケース**:

| ID | テスト内容 | 信頼性 |
|----|-----------|--------|
| TC-QG-008-001 | POST /cards/generate: レスポンスに `generated_cards` 配列 + `generation_info` オブジェクトが含まれる | BLUE |
| TC-QG-008-002 | POST /cards/generate: `generated_cards[].front`, `back`, `suggested_tags` フィールドが存在 | BLUE |
| TC-QG-008-003 | POST /cards/generate: `generation_info.input_length`, `model_used`, `processing_time_ms` フィールドが存在 | BLUE |
| TC-QG-008-004 | POST /reviews/{cardId}/grade-ai: レスポンスに `grade`, `reasoning`, `card_front`, `card_back`, `grading_info` が含まれる | BLUE |
| TC-QG-008-005 | POST /reviews/{cardId}/grade-ai: `grade` が int 型で 0-5 範囲 | BLUE |
| TC-QG-008-006 | GET /advice: レスポンスに `advice_text`, `weak_areas`, `recommendations`, `study_stats`, `advice_info` が含まれる | BLUE |
| TC-QG-008-007 | GET /advice: `advice_info.model_used`, `processing_time_ms` フィールドが存在 | BLUE |

---

### カテゴリ 6: エラーハンドリング一貫性

#### REQ-QG-009: 例外階層の正確性

**EARS**: AI サービスの例外階層が設計通りに構成されていなければならない。

**信頼性**: BLUE (ai_service.py の例外定義と bedrock.py の Bedrock 固有例外が実装済み)

**テストケース**:

| ID | テスト内容 | 信頼性 |
|----|-----------|--------|
| TC-QG-009-001 | `AITimeoutError`, `AIRateLimitError`, `AIInternalError`, `AIParseError`, `AIProviderError` が全て `AIServiceError` のサブクラス | BLUE |
| TC-QG-009-002 | `BedrockTimeoutError` が `BedrockServiceError` と `AITimeoutError` の両方のサブクラス（多重継承） | BLUE |
| TC-QG-009-003 | `BedrockRateLimitError` が `BedrockServiceError` と `AIRateLimitError` の両方のサブクラス | BLUE |
| TC-QG-009-004 | `BedrockInternalError` が `BedrockServiceError` と `AIInternalError` の両方のサブクラス | BLUE |
| TC-QG-009-005 | `BedrockParseError` が `BedrockServiceError` と `AIParseError` の両方のサブクラス | BLUE |
| TC-QG-009-006 | 各 Bedrock 例外が `AIServiceError` で catch 可能 | BLUE |

#### REQ-QG-010: 全エンドポイント横断エラーマッピング一貫性

**EARS**: AI サービスの各例外タイプが、全 3 エンドポイントで同一の HTTP ステータスコードにマッピングされなければならない。

**信頼性**: BLUE (_map_ai_error_to_http() 関数と既存 test_integration.py TestCrossEndpointErrorConsistency で検証済み)

**テストケース**:

| ID | テスト内容 | 期待 HTTP | 信頼性 |
|----|-----------|-----------|--------|
| TC-QG-010-001 | `AITimeoutError` -> 全 3 エンドポイントで HTTP 504 | 504 | BLUE |
| TC-QG-010-002 | `AIRateLimitError` -> 全 3 エンドポイントで HTTP 429 | 429 | BLUE |
| TC-QG-010-003 | `AIProviderError` -> 全 3 エンドポイントで HTTP 503 | 503 | BLUE |
| TC-QG-010-004 | `AIParseError` -> 全 3 エンドポイントで HTTP 500 | 500 | BLUE |
| TC-QG-010-005 | `AIInternalError` -> 全 3 エンドポイントで HTTP 500 | 500 | BLUE |
| TC-QG-010-006 | `AIServiceError`（基底）-> 全 3 エンドポイントで HTTP 500 | 500 | BLUE |
| TC-QG-010-007 | `create_ai_service()` 初期化失敗 -> 全 3 エンドポイントで HTTP 503 | 503 | BLUE |

#### REQ-QG-011: StrandsAIService のエラーハンドリング統一パターン

**EARS**: `StrandsAIService` の 3 メソッド（`generate_cards`, `grade_answer`, `get_learning_advice`）が、全て同一のエラーハンドリングパターンを実装していなければならない。

**信頼性**: BLUE (strands_service.py の各メソッドに同一の try/except パターンが実装済み)

**テストケース**:

| ID | テスト内容 | 信頼性 |
|----|-----------|--------|
| TC-QG-011-001 | `TimeoutError` -> `AITimeoutError` に変換（全 3 メソッド） | BLUE |
| TC-QG-011-002 | `ConnectionError` -> `AIProviderError` に変換（全 3 メソッド） | BLUE |
| TC-QG-011-003 | botocore ThrottlingException -> `AIRateLimitError` に変換（全 3 メソッド） | BLUE |
| TC-QG-011-004 | エラーメッセージに "timeout" を含む -> `AITimeoutError` に変換（全 3 メソッド） | BLUE |
| TC-QG-011-005 | エラーメッセージに "connection" を含む -> `AIProviderError` に変換（全 3 メソッド） | BLUE |
| TC-QG-011-006 | 既に `AIServiceError` サブクラスの例外はそのまま re-raise（全 3 メソッド） | BLUE |
| TC-QG-011-007 | その他の例外 -> `AIServiceError("Unexpected error: ...")` に変換（全 3 メソッド） | BLUE |

#### REQ-QG-012: BedrockService のエラーハンドリングパターン

**EARS**: `BedrockService` が Bedrock API エラーを Bedrock 固有例外に正しくマッピングし、リトライ可能なエラーにはリトライロジックを適用しなければならない。

**信頼性**: BLUE (bedrock.py の _invoke_claude() と _invoke_with_retry() に実装済み)

**テストケース**:

| ID | テスト内容 | 信頼性 |
|----|-----------|--------|
| TC-QG-012-001 | ClientError "ReadTimeoutError" -> `BedrockTimeoutError` | BLUE |
| TC-QG-012-002 | ClientError "ThrottlingException" -> `BedrockRateLimitError` | BLUE |
| TC-QG-012-003 | ClientError "InternalServerException" -> `BedrockInternalError` | BLUE |
| TC-QG-012-004 | `BedrockRateLimitError` に対してリトライが最大 `MAX_RETRIES` (2) 回実行される | BLUE |
| TC-QG-012-005 | `BedrockTimeoutError` に対してリトライなし（即座に raise） | BLUE |
| TC-QG-012-006 | リトライ間隔が Full Jitter Exponential Backoff パターンに従う | BLUE |

---

### カテゴリ 7: レスポンス解析

#### REQ-QG-013: StrandsAIService のレスポンス解析の堅牢性

**EARS**: `StrandsAIService` のレスポンスパーサーが、プレーン JSON と Markdown コードブロック JSON の両方を正しく解析しなければならない。

**信頼性**: BLUE (strands_service.py の _parse_generation_result(), _parse_grading_result(), _parse_advice_result() に実装済み)

**テストケース**:

| ID | テスト内容 | 信頼性 |
|----|-----------|--------|
| TC-QG-013-001 | プレーン JSON レスポンスが正しく解析される（generate_cards） | BLUE |
| TC-QG-013-002 | Markdown ```json ... ``` コードブロックが正しく解析される（generate_cards） | BLUE |
| TC-QG-013-003 | `"cards"` フィールド欠落時に `AIParseError` が raise される | BLUE |
| TC-QG-013-004 | 不正 JSON 文字列に対して `AIParseError` が raise される | BLUE |
| TC-QG-013-005 | front/back 欠落のカードがスキップされる（空でないカードのみ返却） | BLUE |
| TC-QG-013-006 | 有効カード 0 枚時に `AIParseError` が raise される | BLUE |
| TC-QG-013-007 | "AI生成" タグが未設定のカードに自動挿入される | BLUE |
| TC-QG-013-008 | grade_answer: `"grade"` / `"reasoning"` フィールド欠落時に `AIParseError` | BLUE |
| TC-QG-013-009 | grade_answer: grade が整数に変換できない場合に `AIParseError` | BLUE |
| TC-QG-013-010 | get_learning_advice: `"advice_text"` / `"weak_areas"` / `"recommendations"` 欠落時に `AIParseError` | BLUE |

#### REQ-QG-014: BedrockService のレスポンス解析の堅牢性

**EARS**: `BedrockService` のレスポンスパーサーが、プレーン JSON と Markdown コードブロック JSON の両方を正しく解析しなければならない。

**信頼性**: BLUE (bedrock.py の _parse_response() と _parse_json_response() に実装済み)

**テストケース**:

| ID | テスト内容 | 信頼性 |
|----|-----------|--------|
| TC-QG-014-001 | プレーン JSON レスポンスが正しく解析される（generate_cards） | BLUE |
| TC-QG-014-002 | Markdown ```json ... ``` コードブロックが正しく解析される | BLUE |
| TC-QG-014-003 | `"cards"` フィールド欠落時に `BedrockParseError` が raise される | BLUE |
| TC-QG-014-004 | 必須フィールド欠落時に `BedrockParseError` が raise される（grade, advice） | BLUE |
| TC-QG-014-005 | 不正 JSON 文字列に対して `BedrockParseError` が raise される | BLUE |

---

### カテゴリ 8: セキュリティ（プロンプト分離）

#### REQ-QG-015: プロンプトテンプレートの安全な構造

**EARS**: システムプロンプトとユーザー入力が分離されて構成されていなければならない。

**信頼性**: YELLOW (NFR-SM-102 から妥当な推測。実際のコードベースには sanitize() や InputValidationError は存在しないが、プロンプトテンプレートの分離構造は確認可能)

**注意**: タスクファイルの記述とは異なり、`InputValidationError` や `sanitize()` 関数はこのコードベースに存在しない。テストはプロンプトテンプレートの構造的分離に焦点を当てる。

**テストケース**:

| ID | テスト内容 | 信頼性 |
|----|-----------|--------|
| TC-QG-015-001 | `get_card_generation_prompt()` が入力テキストをテンプレートに埋め込んで返す | BLUE |
| TC-QG-015-002 | `get_grading_prompt()` が card_front, card_back, user_answer をテンプレートに埋め込んで返す | BLUE |
| TC-QG-015-003 | `get_advice_prompt()` が review_summary をテンプレートに埋め込んで返す | BLUE |
| TC-QG-015-004 | `GRADING_SYSTEM_PROMPT` 定数がユーザー入力変数を含まない（テンプレート変数なし） | BLUE |
| TC-QG-015-005 | `ADVICE_SYSTEM_PROMPT` 定数がユーザー入力変数を含まない | BLUE |
| TC-QG-015-006 | 各プロンプト関数が入力の長さ制限を超えないことの確認（boundary） | YELLOW |

---

### カテゴリ 9: ドキュメント更新

#### REQ-QG-016: CLAUDE.md の進捗セクション更新

**EARS**: タスク完了時に `CLAUDE.md` の ai-strands-migration セクションが更新されていなければならない。

**信頼性**: BLUE (タスクファイルの完了条件に明記)

**検証項目**:
- [ ] TC-QG-016-001: CLAUDE.md に `ai-strands-migration` セクションが追加されている
- [ ] TC-QG-016-002: Phase 1 ~ Phase 4 が全て `[x]` (完了) でマークされている

#### REQ-QG-017: overview.md のタスク一覧更新

**EARS**: タスク完了時に `docs/tasks/ai-strands-migration/overview.md` のタスク状態が更新されていなければならない。

**信頼性**: BLUE (タスクファイルの完了条件に明記)

**検証項目**:
- [ ] TC-QG-017-001: TASK-0065 の状態が `[x]` に更新されている
- [ ] TC-QG-017-002: Phase 4 が完了（`[x]`）でマークされている

---

## テスト実装方針

### 新規テストファイル

最終品質ゲート用の新規テストファイルを作成する:

```
backend/tests/unit/test_quality_gate.py
```

このファイルには以下のテストクラスを含める:

1. **TestProtocolComplianceFinal**: カテゴリ 3 (REQ-QG-004) - 両実装の Protocol 準拠性最終確認
2. **TestFactoryRoutingFinal**: カテゴリ 4 (REQ-QG-005) - ファクトリパターン最終確認
3. **TestModelProviderSelectionFinal**: カテゴリ 4 (REQ-QG-006) - モデルプロバイダー選択最終確認
4. **TestErrorHandlingConsistencyFinal**: カテゴリ 6 (REQ-QG-009, REQ-QG-011) - エラーハンドリング最終確認
5. **TestResponseParsingFinal**: カテゴリ 7 (REQ-QG-013, REQ-QG-014) - レスポンス解析最終確認
6. **TestPromptSecurityFinal**: カテゴリ 8 (REQ-QG-015) - プロンプト安全性最終確認

### 既存テストとの関係

既存テストファイルは一切変更しない。`test_quality_gate.py` は既存テストを補完し、最終品質ゲートとして横断的・包括的な検証を追加する。既存テスト（test_ai_service.py, test_strands_service.py, test_bedrock.py, test_bedrock_protocol.py, test_integration.py 等）と重複する検証もあるが、品質ゲートとしての独立した確認を目的とする。

### カバレッジ・全テスト実行は手動確認

カテゴリ 1 (REQ-QG-001/002) とカテゴリ 2 (REQ-QG-003) は pytest コマンドの実行結果による手動確認とする。テストコード内のプレースホルダーテスト（test_integration.py の TC-INT-PROTECT-003 等）は既に存在するためそれを活用する。

---

## テスト実装順序

1. **Red フェーズ**: `test_quality_gate.py` に全テストケースを記述（全て FAIL）
2. **Green フェーズ**: 既存実装で全テスト PASS を確認。不足する実装があれば追加
3. **Refactor フェーズ**: テストの整理、カバレッジ不足モジュールの補強

---

## 信頼性レベルサマリー

| カテゴリ | 信頼性 | テストケース数 |
|---------|--------|---------------|
| カテゴリ 1: 全テスト実行 + 既存テスト保護 | BLUE | 7 |
| カテゴリ 2: テストカバレッジ | BLUE | 5 |
| カテゴリ 3: Protocol 準拠性 | BLUE | 9 |
| カテゴリ 4: ファクトリ + フィーチャーフラグ | BLUE | 15 |
| カテゴリ 5: エンドポイント動作検証 | BLUE | 14 |
| カテゴリ 6: エラーハンドリング一貫性 | BLUE | 27 |
| カテゴリ 7: レスポンス解析 | BLUE | 15 |
| カテゴリ 8: セキュリティ（プロンプト分離） | BLUE/YELLOW | 6 |
| カテゴリ 9: ドキュメント更新 | BLUE | 4 |

**合計テストケース数**: 102

| レベル | 件数 | 割合 |
|--------|------|------|
| BLUE | 101 | 99% |
| YELLOW | 1 | 1% |
| RED | 0 | 0% |

**品質評価**: 高品質（BLUE 99%、RED なし）

---

## 参照ファイル

### 実装ソース
- `backend/src/services/ai_service.py` - AIService Protocol + ファクトリ + 例外階層
- `backend/src/services/strands_service.py` - StrandsAIService 実装
- `backend/src/services/bedrock.py` - BedrockService 実装
- `backend/src/services/prompts/generate.py` - カード生成プロンプト
- `backend/src/services/prompts/grading.py` - 採点プロンプト
- `backend/src/services/prompts/advice.py` - アドバイスプロンプト
- `backend/src/api/handler.py` - Lambda ハンドラー（全エンドポイント）

### 既存テスト
- `backend/tests/unit/test_ai_service.py` - Protocol + ファクトリテスト
- `backend/tests/unit/test_strands_service.py` - StrandsAIService テスト
- `backend/tests/unit/test_bedrock.py` - BedrockService テスト
- `backend/tests/unit/test_bedrock_protocol.py` - Bedrock Protocol 準拠テスト
- `backend/tests/unit/test_handler_ai_service_factory.py` - ハンドラー統合テスト
- `backend/tests/unit/test_migration_compat.py` - マイグレーション互換性テスト
- `backend/tests/unit/test_handler_grade_ai.py` - grade-ai ハンドラーテスト
- `backend/tests/unit/test_handler_advice.py` - advice ハンドラーテスト
- `backend/tests/integration/test_integration.py` - 統合テスト

### 設計文書
- `docs/spec/ai-strands-migration/requirements.md` - 要件定義書
- `docs/design/ai-strands-migration/architecture.md` - アーキテクチャ設計
- `docs/tasks/ai-strands-migration/TASK-0065.md` - タスクファイル

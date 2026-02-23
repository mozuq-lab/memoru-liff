# TASK-0058: カード生成 API 互換性検証 + 移行テスト - TDD 要件定義書

**作成日**: 2026-02-23
**タスクタイプ**: TDD (Test-Driven Development)
**フェーズ**: Phase 2 - Strands カード生成移行
**推定工数**: 8時間

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 既存実装コード・設計文書・タスクファイルから確実に特定された要件
- 🟡 **黄信号**: 既存実装・設計文書から妥当な推測による要件
- 🔴 **赤信号**: 設計文書にない推測による要件

---

## 1. 目的と概要

TASK-0058 は **USE_STRANDS フィーチャーフラグの true/false 両方でカード生成 API (POST /cards/generate) が同一のレスポンス形式を返すことを TDD で検証する**タスクである。

### 検証の 4 本柱

1. **API レスポンス形式の完全一致**: GenerateCardsResponse が両サービスで同一構造
2. **エラーハンドリングの統一**: 同一エラーシナリオで同一 HTTP ステータスコードを返す
3. **フィーチャーフラグの動的切替**: USE_STRANDS 環境変数に応じた正しいサービス選択
4. **既存テスト保護**: 444 件の既存テストが引き続き全て PASS する

### 成果物

| ファイル | 種別 | 内容 |
|---------|------|------|
| `backend/tests/unit/test_migration_compat.py` | 新規 | 互換性検証の単体テスト |
| `backend/tests/integration/test_migration_integration.py` | 新規 | エンドツーエンド統合テスト |

### 前提タスク

- **TASK-0053**: AIService Protocol + 共通型定義 (`ai_service.py`)
- **TASK-0055**: BedrockAIService Protocol 準拠改修 (`bedrock.py`)
- **TASK-0056**: handler.py AIServiceFactory 統合 (`handler.py`, `template.yaml`)
- **TASK-0057**: StrandsAIService 基本実装 (`strands_service.py`)

### 関連要件 ID

- REQ-SM-002: カード生成機能の Strands Agents 移行
- REQ-SM-402: API レスポンス形式互換性
- REQ-SM-404: テストカバレッジ 80% 以上維持
- REQ-SM-405: 既存テスト保護

---

## 2. API レスポンス形式互換性要件

### REQ-058-001: GenerateCardsResponse スキーマ一致 (USE_STRANDS=true) 🔵

**信頼性**: 🔵 *api-endpoints.md の POST /cards/generate レスポンス仕様、models/generate.py の Pydantic モデル定義から確定*

**Given**: USE_STRANDS=true 環境変数が設定されている
**When**: POST /cards/generate に有効なリクエストを送信する
**Then**:
- HTTP ステータスコード 200 が返される
- レスポンスボディが GenerateCardsResponse スキーマに準拠する:
  - `generated_cards`: GeneratedCardResponse のリスト
    - 各要素に `front` (string), `back` (string), `suggested_tags` (List[str]) を含む
  - `generation_info`: GenerationInfoResponse オブジェクト
    - `input_length` (int), `model_used` (string), `processing_time_ms` (int) を含む
- `generated_cards` の要素数がリクエストの `card_count` と一致する

**検証ソース**: `backend/src/models/generate.py` (L8-L64), `backend/src/api/handler.py` (L290-L344)

**モック対象**: `services.strands_service.Agent` - Strands Agent をモックし、有効な JSON カードレスポンスを返す

---

### REQ-058-002: GenerateCardsResponse スキーマ一致 (USE_STRANDS=false) 🔵

**信頼性**: 🔵 *api-endpoints.md の POST /cards/generate レスポンス仕様、既存 test_bedrock.py テストパターンから確定*

**Given**: USE_STRANDS=false 環境変数が設定されている
**When**: POST /cards/generate に有効なリクエストを送信する
**Then**:
- HTTP ステータスコード 200 が返される
- レスポンスボディが REQ-058-001 と **同一の** GenerateCardsResponse スキーマに準拠する
- フィールド構造が REQ-058-001 と完全に一致する

**検証ソース**: `backend/src/services/bedrock.py` (L118-L165), `backend/src/api/handler.py` (L329-L344)

**モック対象**: `services.bedrock.boto3.client` - Bedrock API クライアントをモックし、有効な JSON レスポンスを返す

---

### REQ-058-003: GenerationResult 内部型の互換性 🔵

**信頼性**: 🔵 *ai_service.py の GenerationResult dataclass 定義、bedrock.py と strands_service.py の両方が同一型を返すことから確定*

**Given**: 両サービス (StrandsAIService, BedrockService) に同一の入力を与える
**When**: `generate_cards()` メソッドを呼び出す
**Then**:
- 両方が `GenerationResult` dataclass のインスタンスを返す
- `GenerationResult` の必須フィールドが全て存在する:
  - `cards`: `List[GeneratedCard]` - 各要素に `front`, `back`, `suggested_tags`
  - `input_length`: `int` - 入力テキストの長さ
  - `model_used`: `str` - 使用モデル名 (値は異なってよい)
  - `processing_time_ms`: `int` - 正の整数

**注意**: `model_used` の値は以下のように異なる:
- BedrockService: `"anthropic.claude-3-haiku-20240307-v1:0"` (BEDROCK_MODEL_ID 環境変数)
- StrandsAIService: `"strands_bedrock"` または `"strands_ollama"` (_MODEL_USED_BEDROCK/OLLAMA 定数)

**検証ソース**: `backend/src/services/ai_service.py` (L28-L34), `backend/src/services/strands_service.py` (L142-L147), `backend/src/services/bedrock.py` (L160-L165)

---

### REQ-058-004: GeneratedCard の各フィールド型検証 🔵

**信頼性**: 🔵 *ai_service.py L19-L24 の GeneratedCard dataclass 定義から確定*

**Given**: 両サービスでカード生成が成功する
**When**: 生成結果の各カードを検査する
**Then**:
- `front`: 空でない文字列
- `back`: 空でない文字列
- `suggested_tags`: 文字列のリスト (空リストも許容)
- `"AI生成"` タグが tags リストに含まれる (両サービスとも自動挿入)

**検証ソース**: `backend/src/services/strands_service.py` (L230-L233), `backend/src/services/bedrock.py` (L468-L470)

---

### REQ-058-005: レスポンスの JSON シリアライズ互換性 🔵

**信頼性**: 🔵 *handler.py L329-L344 の GenerateCardsResponse 変換処理、models/generate.py の Pydantic model_dump() から確定*

**Given**: handler.py が GenerationResult を GenerateCardsResponse に変換する
**When**: `response.model_dump(mode="json")` でシリアライズする
**Then**:
- 結果が有効な JSON 文字列に変換可能
- トップレベルキー: `"generated_cards"`, `"generation_info"` のみ
- `generated_cards[*]` のキー: `"front"`, `"back"`, `"suggested_tags"` のみ
- `generation_info` のキー: `"input_length"`, `"model_used"`, `"processing_time_ms"` のみ
- 余分なキーが含まれない

**検証ソース**: `backend/src/models/generate.py` (L44-L64)

---

### REQ-058-006: model_used フィールドの値検証 🔵

**信頼性**: 🔵 *strands_service.py L46-L47 の定数定義、bedrock.py L79 のモデル ID から確定*

**Given**: 各サービスでカード生成が成功する
**When**: `generation_info.model_used` を検査する
**Then**:
- USE_STRANDS=false: BEDROCK_MODEL_ID 環境変数の値 (デフォルト: `"anthropic.claude-3-haiku-20240307-v1:0"`)
- USE_STRANDS=true (ENVIRONMENT=prod): `"strands_bedrock"`
- USE_STRANDS=true (ENVIRONMENT=dev): `"strands_ollama"`
- model_used が空文字列ではない

**検証ソース**: `backend/src/services/strands_service.py` (L46-L47), `backend/src/services/bedrock.py` (L96-L98)

---

## 3. エラーハンドリング互換性要件

### REQ-058-010: タイムアウトエラーの HTTP ステータス一致 (504) 🔵

**信頼性**: 🔵 *handler.py L74-L80 の _map_ai_error_to_http() 実装、strands_service.py L152-L153 と bedrock.py L413 の例外マッピングから確定*

**Given**: AI サービスがタイムアウト例外を raise する
**When**: handler.py がエラーを処理する
**Then**:
- USE_STRANDS=true: StrandsAIService の `TimeoutError` → `AITimeoutError` → HTTP 504
- USE_STRANDS=false: BedrockService の `ClientError(ReadTimeoutError)` → `BedrockTimeoutError` (extends AITimeoutError) → HTTP 504
- 両方で HTTP ステータスコード 504 が返される
- レスポンスボディに `{"error": "AI service timeout"}` が含まれる

**検証ソース**: `backend/src/api/handler.py` (L74-L80), `backend/src/services/strands_service.py` (L152-L153), `backend/src/services/bedrock.py` (L412-L413)

---

### REQ-058-011: レート制限エラーの HTTP ステータス一致 (429) 🔵

**信頼性**: 🔵 *handler.py L81-L87 の _map_ai_error_to_http() 実装、strands_service.py L161-L162 と bedrock.py L414-L415 の例外マッピングから確定*

**Given**: AI サービスがレート制限例外を raise する
**When**: handler.py がエラーを処理する
**Then**:
- USE_STRANDS=true: StrandsAIService の `_is_rate_limit_error()` → `AIRateLimitError` → HTTP 429
- USE_STRANDS=false: BedrockService の `ClientError(ThrottlingException)` → `BedrockRateLimitError` (extends AIRateLimitError) → HTTP 429
- 両方で HTTP ステータスコード 429 が返される
- レスポンスボディに `{"error": "AI service rate limit exceeded"}` が含まれる

**検証ソース**: `backend/src/api/handler.py` (L81-L87), `backend/src/services/strands_service.py` (L161-L162), `backend/src/services/bedrock.py` (L414-L415)

---

### REQ-058-012: JSON 解析エラーの HTTP ステータス一致 (500) 🔵

**信頼性**: 🔵 *handler.py L95-L101 の _map_ai_error_to_http() 実装、strands_service.py L203 と bedrock.py L485-L486 の AIParseError から確定*

**Given**: AI サービスがレスポンス解析に失敗する
**When**: handler.py がエラーを処理する
**Then**:
- USE_STRANDS=true: StrandsAIService の `_parse_generation_result()` → `AIParseError` → HTTP 500
- USE_STRANDS=false: BedrockService の `_parse_response()` → `BedrockParseError` (extends AIParseError) → HTTP 500
- 両方で HTTP ステータスコード 500 が返される
- レスポンスボディに `{"error": "AI service response parse error"}` が含まれる

**検証ソース**: `backend/src/api/handler.py` (L95-L101), `backend/src/services/strands_service.py` (L192-L209), `backend/src/services/bedrock.py` (L425-L490)

---

### REQ-058-013: 内部エラーの HTTP ステータス一致 (500) 🔵

**信頼性**: 🔵 *handler.py L102-L107 の _map_ai_error_to_http() 実装から確定*

**Given**: AI サービスが内部エラーを raise する
**When**: handler.py がエラーを処理する
**Then**:
- USE_STRANDS=true: StrandsAIService の予期しないエラー → `AIServiceError` → HTTP 500
- USE_STRANDS=false: BedrockService の `ClientError(InternalServerException)` → `BedrockInternalError` (extends AIInternalError) → HTTP 500
- 両方で HTTP ステータスコード 500 が返される
- レスポンスボディに `{"error": "AI service error"}` が含まれる

**検証ソース**: `backend/src/api/handler.py` (L102-L107)

---

### REQ-058-014: プロバイダーエラーの HTTP ステータス一致 (503) 🔵

**信頼性**: 🔵 *handler.py L88-L94 の _map_ai_error_to_http() 実装、ai_service.py L197-L198 の create_ai_service() 例外処理から確定*

**Given**: AI サービスの初期化が失敗する
**When**: `create_ai_service()` が `AIProviderError` を raise する
**Then**:
- HTTP ステータスコード 503 が返される
- レスポンスボディに `{"error": "AI service unavailable"}` が含まれる

**検証ソース**: `backend/src/api/handler.py` (L88-L94), `backend/src/services/ai_service.py` (L196-L198)

---

### REQ-058-015: バリデーションエラーの HTTP ステータス一致 (400) 🔵

**信頼性**: 🔵 *handler.py L300-L312 の Pydantic ValidationError 処理から確定*

**Given**: リクエストボディが GenerateCardsRequest のバリデーションに失敗する
**When**: POST /cards/generate を呼び出す
**Then**:
- USE_STRANDS の値に関わらず HTTP ステータスコード 400 が返される
- レスポンスボディに `{"error": "Invalid request", "details": [...]}` が含まれる
- バリデーションは AI サービスの前段で実行されるため、フラグに依存しない

**検証ソース**: `backend/src/api/handler.py` (L300-L312), `backend/src/models/generate.py` (L8-L41)

---

### REQ-058-016: Bedrock 例外の多重継承による AIServiceError 階層経由マッピング 🔵

**信頼性**: 🔵 *bedrock.py L27-L54 の多重継承定義、test_handler_ai_service_factory.py TC-056-026/027 で検証済みのパターンから確定*

**Given**: BedrockService が Bedrock 固有の例外を raise する
**When**: handler.py の `except AIServiceError` ブロックが例外を捕捉する
**Then**:
- `BedrockTimeoutError` (extends `BedrockServiceError`, `AITimeoutError`) → HTTP 504
- `BedrockRateLimitError` (extends `BedrockServiceError`, `AIRateLimitError`) → HTTP 429
- `BedrockInternalError` (extends `BedrockServiceError`, `AIInternalError`) → HTTP 500
- `BedrockParseError` (extends `BedrockServiceError`, `AIParseError`) → HTTP 500
- 多重継承により `isinstance(error, AITimeoutError)` 等の判定が正しく動作する

**検証ソース**: `backend/src/services/bedrock.py` (L27-L54), `backend/tests/unit/test_handler_ai_service_factory.py` (TC-056-026, TC-056-027)

---

### REQ-058-017: エラーマッピングテーブルの完全性検証 🔵

**信頼性**: 🔵 *handler.py L62-L107 の _map_ai_error_to_http() 関数の全分岐から確定*

**Given**: `_map_ai_error_to_http()` 関数が存在する
**When**: 全 AI 例外タイプを入力として渡す
**Then**: 以下のマッピングが正しいことを確認する:

| 例外タイプ | HTTP ステータス | エラーメッセージ |
|-----------|---------------|----------------|
| AITimeoutError | 504 | "AI service timeout" |
| AIRateLimitError | 429 | "AI service rate limit exceeded" |
| AIProviderError | 503 | "AI service unavailable" |
| AIParseError | 500 | "AI service response parse error" |
| AIInternalError | 500 | "AI service error" |
| AIServiceError (基底) | 500 | "AI service error" |

- 全レスポンスの Content-Type が `"application/json"` である

**検証ソース**: `backend/src/api/handler.py` (L62-L107)

---

## 4. フィーチャーフラグ切替要件

### REQ-058-020: USE_STRANDS=true で StrandsAIService が選択される 🔵

**信頼性**: 🔵 *ai_service.py L185-L192 の create_ai_service() 実装から確定*

**Given**: 環境変数 `USE_STRANDS` が `"true"` に設定されている
**When**: `create_ai_service()` を呼び出す
**Then**:
- 返されるインスタンスが `StrandsAIService` 型である
- `isinstance(service, StrandsAIService)` が True
- サービスの `model_used` 属性が `"strands_bedrock"` (ENVIRONMENT != "dev" の場合)

**検証ソース**: `backend/src/services/ai_service.py` (L185-L192)

---

### REQ-058-021: USE_STRANDS=false で BedrockService が選択される 🔵

**信頼性**: 🔵 *ai_service.py L185-L195 の create_ai_service() 実装から確定*

**Given**: 環境変数 `USE_STRANDS` が `"false"` に設定されている
**When**: `create_ai_service()` を呼び出す
**Then**:
- 返されるインスタンスが `BedrockService` 型である
- `isinstance(service, BedrockService)` が True

**検証ソース**: `backend/src/services/ai_service.py` (L193-L195)

---

### REQ-058-022: USE_STRANDS 未設定時のデフォルト動作 🔵

**信頼性**: 🔵 *ai_service.py L186 の `os.getenv("USE_STRANDS", "false")` から確定。デフォルト値 "false" が明確にコード実装されている*

**Given**: 環境変数 `USE_STRANDS` が未設定 (存在しない)
**When**: `create_ai_service()` を呼び出す
**Then**:
- デフォルト値 `"false"` が適用される
- 返されるインスタンスが `BedrockService` 型である
- 安全なフォールバックとして既存実装が使用される

**検証ソース**: `backend/src/services/ai_service.py` (L186)

---

### REQ-058-023: create_ai_service() への明示的引数渡し 🔵

**信頼性**: 🔵 *ai_service.py L171-L192 の use_strands パラメータ処理から確定*

**Given**: `create_ai_service(use_strands=True)` を明示的に呼び出す
**When**: 環境変数に依存せず引数で制御する
**Then**:
- `use_strands=True` → StrandsAIService が返される
- `use_strands=False` → BedrockService が返される
- `use_strands=None` → 環境変数 USE_STRANDS を参照する

**検証ソース**: `backend/src/services/ai_service.py` (L171-L192)

---

### REQ-058-024: create_ai_service() 初期化失敗時の AIProviderError 🔵

**信頼性**: 🔵 *ai_service.py L196-L198 の Exception ハンドリングから確定*

**Given**: AI サービスの初期化時に例外が発生する
**When**: `create_ai_service()` を呼び出す
**Then**:
- 任意の初期化エラーが `AIProviderError` にラップされる
- エラーメッセージに元の例外情報が含まれる (`f"Failed to initialize AI service: {e}"`)
- 元の例外が `__cause__` チェーンに保持される

**検証ソース**: `backend/src/services/ai_service.py` (L196-L198)

---

## 5. Factory 関数動作検証要件

### REQ-058-030: handler.py が create_ai_service() ファクトリを使用する 🔵

**信頼性**: 🔵 *handler.py L317 の `ai_service = create_ai_service()` 呼び出しから確定*

**Given**: POST /cards/generate リクエストが到着する
**When**: handler.py の `generate_cards()` 関数が実行される
**Then**:
- `create_ai_service()` が 1 回呼ばれる
- ファクトリから返されたサービスの `generate_cards()` メソッドが呼ばれる
- リクエストの `input_text`, `card_count`, `difficulty`, `language` が正しく伝播する

**検証ソース**: `backend/src/api/handler.py` (L317-L323)

---

### REQ-058-031: ファクトリが AIService Protocol 準拠インスタンスを返す 🔵

**信頼性**: 🔵 *ai_service.py L109-L131 の @runtime_checkable Protocol 定義から確定*

**Given**: `create_ai_service()` が任意のフラグ値で呼ばれる
**When**: 返されたインスタンスの Protocol 適合性を検査する
**Then**:
- `isinstance(service, AIService)` が True (@runtime_checkable)
- `generate_cards()` メソッドが存在する
- `grade_answer()` メソッドが存在する
- `get_learning_advice()` メソッドが存在する

**検証ソース**: `backend/src/services/ai_service.py` (L108-L131)

---

## 6. 両実装の GenerationResult 生成要件

### REQ-058-040: StrandsAIService の GenerationResult が有効 🔵

**信頼性**: 🔵 *strands_service.py L96-L147 の generate_cards() 実装から確定*

**Given**: StrandsAIService が有効なモックレスポンスを受け取る
**When**: `generate_cards()` を呼び出す
**Then**:
- `GenerationResult` の `cards` フィールドに `GeneratedCard` のリストが含まれる
- `input_length` が入力テキストの `len()` と一致する
- `model_used` が `"strands_bedrock"` または `"strands_ollama"` のいずれか
- `processing_time_ms` が正の整数 (0 より大きい)
- 各 `GeneratedCard` の `front` と `back` が空でない文字列

**モック対象**: `strands.Agent` - Agent のコンストラクタと `__call__` をモック

**検証ソース**: `backend/src/services/strands_service.py` (L96-L147)

---

### REQ-058-041: BedrockService の GenerationResult が有効 🔵

**信頼性**: 🔵 *bedrock.py L118-L165 の generate_cards() 実装から確定*

**Given**: BedrockService が有効なモックレスポンスを受け取る
**When**: `generate_cards()` を呼び出す
**Then**:
- `GenerationResult` の `cards` フィールドに `GeneratedCard` のリストが含まれる
- `input_length` が入力テキストの `len()` と一致する
- `model_used` が BEDROCK_MODEL_ID の値 (デフォルト: `"anthropic.claude-3-haiku-20240307-v1:0"`)
- `processing_time_ms` が正の整数 (0 より大きい)
- 各 `GeneratedCard` の `front` と `back` が空でない文字列

**モック対象**: `boto3.client('bedrock-runtime')` の `invoke_model` メソッド

**検証ソース**: `backend/src/services/bedrock.py` (L118-L165)

---

### REQ-058-042: 両サービスのレスポンス構造的同値性 🔵

**信頼性**: 🔵 *handler.py L329-L344 で GenerationResult → GenerateCardsResponse への共通変換処理から確定。両サービスが同一の GenerationResult を返すため、変換結果も同一構造になる*

**Given**: 同一の入力パラメータで両サービスを呼び出す
**When**: 生成された GenerationResult を比較する
**Then**:
- `len(strands_result.cards)` == `len(bedrock_result.cards)` (リクエストの card_count と一致)
- 両結果の `input_length` が一致する (同一入力テキスト)
- 各カードのフィールド名 (`front`, `back`, `suggested_tags`) が一致する
- `processing_time_ms` は両方とも正の整数 (値は異なってよい)
- `model_used` は異なる値を持つ (BedrockService: モデル ID, StrandsAIService: プロバイダー識別子)

**検証ソース**: `backend/src/services/ai_service.py` (L28-L34)

---

## 7. 既存テスト保護要件

### REQ-058-050: 既存テストスイート全件 PASS (444 テスト) 🔵

**信頼性**: 🔵 *pytest tests/ で 444 tests collected を確認済み。CLAUDE.md の「テストカバレッジ 80% 以上を目標」REQ-SM-405 から確定*

**Given**: 全テストスイートを実行する
**When**: `pytest backend/tests/ -v` を実行する
**Then**:
- 444 件の既存テストが全て PASS する
- テストの追加・変更によってリグレッションが発生しない
- 新規テストファイルは既存テストに影響しない

**テストファイル内訳** (主要):
- `test_bedrock.py`: 20 テスト (BedrockService)
- `test_strands_service.py`: 39 テスト (StrandsAIService)
- `test_ai_service.py`: 54 テスト (Protocol + Factory)
- `test_handler_ai_service_factory.py`: 27 テスト (ハンドラー統合)
- その他 (カード、レビュー、ユーザー、通知等): 304 テスト

---

### REQ-058-051: テストカバレッジ 80% 以上維持 🔵

**信頼性**: 🔵 *CLAUDE.md の「テストカバレッジ 80% 以上を目標とする」注意事項、REQ-SM-404 から確定*

**Given**: 全テスト (既存 + 新規) を実行する
**When**: `pytest --cov=src/services --cov-report=term-missing` を実行する
**Then**:
- サービス層のカバレッジが 80% 以上を維持する
- 新規テストが ai_service.py, strands_service.py, bedrock.py のカバレッジを向上させる

---

### REQ-058-052: USE_STRANDS=false (デフォルト) で既存テストが影響を受けない 🔵

**信頼性**: 🔵 *conftest.py の環境変数設定には USE_STRANDS が含まれていないため、デフォルト値 "false" が適用される。既存テストは BedrockService ベースの動作を検証しているため、影響なし*

**Given**: テスト環境で USE_STRANDS が未設定 (conftest.py のデフォルト)
**When**: 既存テストスイートを実行する
**Then**:
- デフォルト値 "false" により BedrockService が使用される
- 既存の BedrockService テストが全て PASS する
- 既存の handler テストが全て PASS する

**検証ソース**: `backend/tests/conftest.py` (L12-L19)

---

## 8. 移行エッジケース要件

### REQ-058-060: 空のカードレスポンスのハンドリング 🔵

**信頼性**: 🔵 *strands_service.py L242-L248 と bedrock.py L480-L481 の両方で空カードの AIParseError を確認済み*

**Given**: AI モデルが有効なカードを 0 枚含むレスポンスを返す
**When**: 両サービスでレスポンスをパースする
**Then**:
- StrandsAIService: `AIParseError("No valid cards found in response...")` を raise
- BedrockService: `BedrockParseError("No valid cards in response")` を raise
- 両方とも handler.py で HTTP 500 にマッピングされる

**検証ソース**: `backend/src/services/strands_service.py` (L242-L248), `backend/src/services/bedrock.py` (L480-L481)

---

### REQ-058-061: 不完全なカードデータのスキップ動作 🔵

**信頼性**: 🔵 *strands_service.py L213-L221 と bedrock.py L453-L461 の両方で同一のスキップロジックを確認済み*

**Given**: AI モデルが front/back の欠落したカードを含むレスポンスを返す
**When**: 両サービスでレスポンスをパースする
**Then**:
- `front` または `back` が欠落しているカードはスキップされる
- `front` または `back` が空文字列のカードはスキップされる
- 有効なカードのみが `GenerationResult.cards` に含まれる
- 有効なカードが 1 枚以上あれば成功レスポンスが返される

**検証ソース**: `backend/src/services/strands_service.py` (L213-L221), `backend/src/services/bedrock.py` (L453-L461)

---

### REQ-058-062: Markdown コードブロック内 JSON の解析 🔵

**信頼性**: 🔵 *strands_service.py L194 と bedrock.py L439 の両方で同一の正規表現パターン `r"```json\s*([\s\S]*?)\s*```"` を使用していることから確定*

**Given**: AI モデルが ` ```json ... ``` ` 形式でレスポンスを返す
**When**: 両サービスでレスポンスをパースする
**Then**:
- Markdown コードブロック内の JSON が正しく抽出される
- プレーン JSON レスポンスも正しくパースされる
- 両方のサービスで同一のパース結果が得られる

**検証ソース**: `backend/src/services/strands_service.py` (L194), `backend/src/services/bedrock.py` (L439)

---

### REQ-058-063: "AI生成" タグの自動挿入 🔵

**信頼性**: 🔵 *strands_service.py L231-L232 と bedrock.py L469-L470 で同一のロジックを確認済み*

**Given**: AI モデルが "AI生成" タグを含まないカードを返す
**When**: 両サービスでレスポンスをパースする
**Then**:
- 両サービスとも `"AI生成"` タグを tags リストの先頭に挿入する
- `"AI生成"` または `"AI Generated"` が既に存在する場合は挿入しない
- tags が list でない場合は空リストに変換する

**検証ソース**: `backend/src/services/strands_service.py` (L231-L232), `backend/src/services/bedrock.py` (L469-L470)

---

### REQ-058-064: ConnectionError のプロバイダーエラーマッピング (Strands 固有) 🟡

**信頼性**: 🟡 *strands_service.py L155 の ConnectionError 処理から確認。BedrockService には同等の直接的な ConnectionError 処理がないため、Strands 固有のエッジケースとして推測*

**Given**: StrandsAIService がプロバイダーへの接続に失敗する
**When**: `ConnectionError` が raise される
**Then**:
- `AIProviderError` にラップされる
- handler.py で HTTP 503 にマッピングされる

**検証ソース**: `backend/src/services/strands_service.py` (L155)

---

### REQ-058-065: 未知の例外の AIServiceError ラッピング (Strands 固有) 🟡

**信頼性**: 🟡 *strands_service.py L173 の catch-all Exception 処理から確認。SDK 依存の予期しないエラー型に対する安全策として推測*

**Given**: StrandsAIService が未知の例外を受け取る
**When**: Strands SDK が予期しないエラーを raise する
**Then**:
- `AIServiceError("Unexpected error: ...")` にラップされる
- handler.py で HTTP 500 にマッピングされる

**検証ソース**: `backend/src/services/strands_service.py` (L173)

---

## 9. 統合テスト要件

### REQ-058-070: E2E 互換性テスト (USE_STRANDS=true) 🔵

**信頼性**: 🔵 *handler.py の lambda_handler → app.resolve → generate_cards → create_ai_service → StrandsAIService の完全パスから確定*

**Given**: USE_STRANDS=true, Strands Agent がモック済み
**When**: API Gateway イベントをシミュレートして handler.py の `handler()` を呼び出す
**Then**:
- HTTP ステータスコード 200 が返される
- レスポンスボディが GenerateCardsResponse スキーマに準拠する
- `generation_info.model_used` が Strands プロバイダー識別子を含む
- `generated_cards` の要素数がリクエストの `card_count` と一致する

**テスト手法**: `api_gateway_event` フィクスチャ + `create_ai_service` のモック

---

### REQ-058-071: E2E 互換性テスト (USE_STRANDS=false) 🔵

**信頼性**: 🔵 *handler.py の lambda_handler → app.resolve → generate_cards → create_ai_service → BedrockService の完全パスから確定*

**Given**: USE_STRANDS=false, Bedrock がモック済み
**When**: API Gateway イベントをシミュレートして handler.py の `handler()` を呼び出す
**Then**:
- HTTP ステータスコード 200 が返される
- レスポンスボディが GenerateCardsResponse スキーマに準拠する
- レスポンス構造が REQ-058-070 と完全に一致する (model_used の値は異なる)

---

### REQ-058-072: E2E エラーレスポンス互換性テスト 🔵

**信頼性**: 🔵 *handler.py L346-L349 の `except AIServiceError` ブロックで両サービスのエラーが統一的に処理されることから確定*

**Given**: 両フラグ値で AI サービスがエラーを raise する
**When**: API Gateway イベントをシミュレートする
**Then**:
- 同一のエラータイプに対して同一の HTTP ステータスコードが返される
- エラーレスポンスの JSON 構造が両フラグ値で一致する (`{"error": "..."}`)
- バリデーションエラー (400) は USE_STRANDS フラグに依存しない

---

## 10. テストファイル設計

### 単体テスト: `backend/tests/unit/test_migration_compat.py`

| テストクラス | テストケース数 | 対象要件 |
|------------|-------------|---------|
| TestAPIResponseCompatibility | 6 | REQ-058-001 ~ REQ-058-006 |
| TestErrorHandlingCompatibility | 8 | REQ-058-010 ~ REQ-058-017 |
| TestFeatureFlagBehavior | 5 | REQ-058-020 ~ REQ-058-024 |
| TestGenerationResultValidity | 3 | REQ-058-040 ~ REQ-058-042 |
| TestMigrationEdgeCases | 6 | REQ-058-060 ~ REQ-058-065 |
| TestExistingTestProtection | 3 | REQ-058-050 ~ REQ-058-052 |
| **合計** | **31** | |

### 統合テスト: `backend/tests/integration/test_migration_integration.py`

| テストクラス | テストケース数 | 対象要件 |
|------------|-------------|---------|
| TestE2ECompatibility | 3 | REQ-058-070 ~ REQ-058-072 |
| **合計** | **3** | |

### テスト総数: 34 テストケース

---

## 11. モック戦略

### StrandsAIService のモック

```python
# Agent クラスをモックし、__call__ メソッドで JSON レスポンスを返す
@patch("services.strands_service.Agent")
def test_xxx(mock_agent_cls):
    mock_agent = MagicMock()
    mock_agent.return_value = json.dumps({
        "cards": [
            {"front": "Q1", "back": "A1", "tags": ["tag1"]}
        ]
    })
    mock_agent_cls.return_value = mock_agent
```

### BedrockService のモック

```python
# boto3 クライアントの invoke_model をモックし、Claude API レスポンスを返す
mock_client = MagicMock()
mock_client.invoke_model.return_value = {
    "body": io.BytesIO(json.dumps({
        "content": [{"text": json.dumps({"cards": [...]})}]
    }).encode())
}
service = BedrockService(bedrock_client=mock_client)
```

### 環境変数の管理

```python
# patch.dict で環境変数を一時的に設定 (テスト間の汚染防止)
@pytest.fixture
def use_strands_true():
    with patch.dict(os.environ, {"USE_STRANDS": "true"}):
        yield

@pytest.fixture
def use_strands_false():
    with patch.dict(os.environ, {"USE_STRANDS": "false"}):
        yield
```

---

## 12. 信頼性レベルサマリー

| レベル | 件数 | 割合 | 対象要件 |
|--------|------|------|---------|
| 🔵 **青信号** | 32件 | 94% | REQ-058-001 ~ REQ-058-063, REQ-058-070 ~ REQ-058-072 |
| 🟡 **黄信号** | 2件 | 6% | REQ-058-064, REQ-058-065 |
| 🔴 **赤信号** | 0件 | 0% | - |

**品質評価**: 高品質 (青信号 94%、赤信号なし)

### 黄信号の詳細

| 要件 ID | 内容 | 理由 |
|---------|------|------|
| REQ-058-064 | ConnectionError のプロバイダーエラーマッピング | Strands 固有のエッジケース。BedrockService には同等の処理がないため、Strands 側のみの検証 |
| REQ-058-065 | 未知の例外の AIServiceError ラッピング | SDK 依存の予期しないエラー型。具体的なエラー型は Strands SDK のバージョンに依存 |

---

## 13. 参考リソース

### 関連タスク

- [TASK-0053: AIService Protocol + 共通型定義](../../tasks/ai-strands-migration/TASK-0053.md) → `ai_service.py`
- [TASK-0055: BedrockAIService Protocol 準拠改修](../../tasks/ai-strands-migration/TASK-0055.md) → `bedrock.py`
- [TASK-0056: handler.py AIServiceFactory 統合](../../tasks/ai-strands-migration/TASK-0056.md) → `handler.py`
- [TASK-0057: StrandsAIService 基本実装](../../tasks/ai-strands-migration/TASK-0057.md) → `strands_service.py`

### 設計文書

- [requirements.md](../../spec/ai-strands-migration/requirements.md) - REQ-SM-002, REQ-SM-402, REQ-SM-404, REQ-SM-405
- [architecture.md](../../design/ai-strands-migration/architecture.md) - Protocol + Factory パターン
- [api-endpoints.md](../../design/ai-strands-migration/api-endpoints.md) - POST /cards/generate 仕様
- [interfaces.py](../../design/ai-strands-migration/interfaces.py) - GenerationResult 型定義
- [dataflow.md](../../design/ai-strands-migration/dataflow.md) - データフロー図

### 実装ファイル

- `backend/src/services/ai_service.py` - Protocol, Factory, 例外階層
- `backend/src/services/strands_service.py` - StrandsAIService 実装
- `backend/src/services/bedrock.py` - BedrockService 実装
- `backend/src/api/handler.py` - API ハンドラー, _map_ai_error_to_http()
- `backend/src/models/generate.py` - Pydantic リクエスト/レスポンスモデル
- `backend/tests/conftest.py` - テストフィクスチャ

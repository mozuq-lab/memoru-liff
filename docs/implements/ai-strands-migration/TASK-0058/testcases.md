# TASK-0058: カード生成 API 互換性検証 + 移行テスト - テストケース定義書

**作成日**: 2026-02-23
**タスクタイプ**: TDD (Test-Driven Development)
**テストファイル**: `backend/tests/unit/test_migration_compat.py`
**テスト総数**: 31 テストケース

**【信頼性レベル凡例】**:
- 🔵 **青信号**: 既存実装コード・設計文書・タスクファイルから確実に特定された要件
- 🟡 **黄信号**: 既存実装・設計文書から妥当な推測による要件
- 🔴 **赤信号**: 設計文書にない推測による要件

**【重要な実装発見事項】**:
`bedrock.py` は独自の `GenerationResult` / `GeneratedCard` dataclass を定義しており (L57-L73)、
`ai_service.py` の同名クラスとは別のクラスです。両クラスは同一の構造（同一フィールド名・型）を
持ちますが、`isinstance()` チェックでは互換性がありません。テストではダックタイピングによる
構造検証を採用し、フィールドの存在と型をチェックしています。
API レスポンスレベル（GenerateCardsResponse）では handler.py の変換処理で統一されるため、
この差異はエンドユーザーに影響しません。

---

## テストクラス一覧

| # | テストクラス | テスト数 | 対象要件 |
|---|------------|---------|---------|
| 1 | TestAPIResponseCompatibility | 6 | REQ-058-001 ~ REQ-058-006 |
| 2 | TestErrorHandlingCompatibility | 8 | REQ-058-010 ~ REQ-058-017 |
| 3 | TestFeatureFlagBehavior | 5 | REQ-058-020 ~ REQ-058-024 |
| 4 | TestGenerationResultValidity | 3 | REQ-058-040 ~ REQ-058-042 |
| 5 | TestMigrationEdgeCases | 6 | REQ-058-060 ~ REQ-058-065 |
| 6 | TestExistingTestProtection | 3 | REQ-058-050 ~ REQ-058-052 |
| **合計** | | **31** | |

---

## 1. TestAPIResponseCompatibility (TC-COMPAT-001 ~ TC-COMPAT-006)

### TC-COMPAT-001: StrandsAIService の GenerationResult スキーマ一致 🔵

**信頼性**: 🔵 *ai_service.py L28-L34 の GenerationResult dataclass 定義、strands_service.py L142-L147 の返却処理から確定*

**対象要件**: REQ-058-001

```
Given: USE_STRANDS=true, StrandsAIService が有効な JSON カードレスポンスを返すモック
When: generate_cards() を呼び出す
Then:
  - 戻り値が GenerationResult インスタンスである
  - cards フィールドが GeneratedCard のリストである
  - 各カードに front (非空文字列), back (非空文字列), suggested_tags (List[str]) を含む
  - input_length が入力テキストの len() と一致する
  - model_used が空でない文字列である
  - processing_time_ms が 0 以上の整数である
```

**モック対象**: `services.strands_service.Agent`, `services.strands_service.BedrockModel`

---

### TC-COMPAT-002: BedrockService の GenerationResult スキーマ一致 🔵

**信頼性**: 🔵 *bedrock.py L160-L165 の返却処理、既存 test_bedrock.py テストパターンから確定*

**対象要件**: REQ-058-002

```
Given: USE_STRANDS=false, BedrockService が有効な JSON カードレスポンスを返すモック
When: generate_cards() を呼び出す
Then:
  - 戻り値が GenerationResult インスタンスである
  - TC-COMPAT-001 と同一の構造を持つ
  - cards, input_length, model_used, processing_time_ms の全フィールドが存在する
```

**モック対象**: `boto3.client('bedrock-runtime')` の `invoke_model`

---

### TC-COMPAT-003: 両サービスのレスポンス構造的同値性 🔵

**信頼性**: 🔵 *handler.py L329-L344 の GenerationResult -> GenerateCardsResponse 共通変換処理から確定*

**対象要件**: REQ-058-042

```
Given: 同一の入力テキストで両サービスを呼び出す
When: 両方の GenerationResult を比較する
Then:
  - len(strands_result.cards) == len(bedrock_result.cards) (同一の card_count に対応)
  - 両結果の input_length が一致する (同一入力テキスト)
  - 各カードのフィールド名 (front, back, suggested_tags) が一致する
  - processing_time_ms は両方とも正の整数 (値は異なってよい)
  - model_used は異なる値を持つ (許容: 実装固有の識別子)
```

---

### TC-COMPAT-004: GeneratedCard の各フィールド型検証 🔵

**信頼性**: 🔵 *ai_service.py L19-L24 の GeneratedCard dataclass 定義から確定*

**対象要件**: REQ-058-004

```
Given: 両サービスでカード生成が成功する
When: 生成結果の各カードを検査する
Then:
  - front: 空でない文字列 (str, len > 0)
  - back: 空でない文字列 (str, len > 0)
  - suggested_tags: 文字列のリスト (List[str])
  - "AI生成" タグが suggested_tags に含まれる (両サービスとも自動挿入)
```

---

### TC-COMPAT-005: JSON シリアライズ互換性 (GenerateCardsResponse) 🔵

**信頼性**: 🔵 *models/generate.py L44-L64 の Pydantic モデル定義、handler.py L329-L344 の変換処理から確定*

**対象要件**: REQ-058-005

```
Given: handler.py が GenerationResult を GenerateCardsResponse に変換する
When: response.model_dump(mode="json") でシリアライズする
Then:
  - トップレベルキー: "generated_cards", "generation_info" のみ
  - generated_cards[*] のキー: "front", "back", "suggested_tags" のみ
  - generation_info のキー: "input_length", "model_used", "processing_time_ms" のみ
  - 余分なキーが含まれない
  - 有効な JSON 文字列に変換可能
```

---

### TC-COMPAT-006: model_used フィールドの値検証 🔵

**信頼性**: 🔵 *strands_service.py L46-L47 の定数定義、bedrock.py L79 のモデル ID から確定*

**対象要件**: REQ-058-006

```
Given: 各サービスでカード生成が成功する
When: generation_info.model_used を検査する
Then:
  - StrandsAIService (ENVIRONMENT != "dev"): "strands_bedrock"
  - BedrockService: BEDROCK_MODEL_ID の値 (デフォルト: "anthropic.claude-3-haiku-20240307-v1:0")
  - model_used が空文字列ではない
```

---

## 2. TestErrorHandlingCompatibility (TC-ERROR-001 ~ TC-ERROR-008)

### TC-ERROR-001: タイムアウトエラー → HTTP 504 (両サービス) 🔵

**信頼性**: 🔵 *handler.py L74-L80 の _map_ai_error_to_http()、strands_service.py L152-L153 と bedrock.py L412-L413 の例外マッピングから確定*

**対象要件**: REQ-058-010

```
Given: StrandsAIService が AITimeoutError を raise, BedrockService が BedrockTimeoutError を raise
When: handler.py の _map_ai_error_to_http() がエラーを処理する
Then:
  - 両方で HTTP ステータスコード 504 が返される
  - レスポンスボディに {"error": "AI service timeout"} が含まれる
  - BedrockTimeoutError は isinstance(error, AITimeoutError) == True (多重継承)
```

---

### TC-ERROR-002: レート制限エラー → HTTP 429 (両サービス) 🔵

**信頼性**: 🔵 *handler.py L81-L87、strands_service.py L161-L162 と bedrock.py L414-L415 から確定*

**対象要件**: REQ-058-011

```
Given: StrandsAIService が AIRateLimitError を raise, BedrockService が BedrockRateLimitError を raise
When: handler.py の _map_ai_error_to_http() がエラーを処理する
Then:
  - 両方で HTTP ステータスコード 429 が返される
  - レスポンスボディに {"error": "AI service rate limit exceeded"} が含まれる
```

---

### TC-ERROR-003: JSON 解析エラー → HTTP 500 (両サービス) 🔵

**信頼性**: 🔵 *handler.py L95-L101、strands_service.py L203 と bedrock.py L485-L486 から確定*

**対象要件**: REQ-058-012

```
Given: StrandsAIService が AIParseError を raise, BedrockService が BedrockParseError を raise
When: handler.py の _map_ai_error_to_http() がエラーを処理する
Then:
  - 両方で HTTP ステータスコード 500 が返される
  - レスポンスボディに {"error": "AI service response parse error"} が含まれる
```

---

### TC-ERROR-004: 内部エラー → HTTP 500 (フォールバック) 🔵

**信頼性**: 🔵 *handler.py L102-L107 の汎用 AIServiceError フォールバック処理から確定*

**対象要件**: REQ-058-013

```
Given: StrandsAIService が AIServiceError を raise, BedrockService が BedrockInternalError を raise
When: handler.py の _map_ai_error_to_http() がエラーを処理する
Then:
  - 両方で HTTP ステータスコード 500 が返される
  - レスポンスボディに {"error": "AI service error"} が含まれる
```

---

### TC-ERROR-005: プロバイダーエラー → HTTP 503 🔵

**信頼性**: 🔵 *handler.py L88-L94、ai_service.py L196-L198 の create_ai_service() 例外処理から確定*

**対象要件**: REQ-058-014

```
Given: create_ai_service() が AIProviderError を raise する
When: handler.py がエラーを処理する
Then:
  - HTTP ステータスコード 503 が返される
  - レスポンスボディに {"error": "AI service unavailable"} が含まれる
```

---

### TC-ERROR-006: バリデーションエラー → HTTP 400 (フラグ非依存) 🔵

**信頼性**: 🔵 *handler.py L300-L312 の Pydantic ValidationError 処理から確定*

**対象要件**: REQ-058-015

```
Given: リクエストボディが GenerateCardsRequest のバリデーションに失敗する
When: POST /cards/generate を呼び出す (USE_STRANDS の値は問わない)
Then:
  - HTTP ステータスコード 400 が返される
  - バリデーションは AI サービスの前段で実行されるため、フラグに依存しない
```

---

### TC-ERROR-007: Bedrock 例外の多重継承経由マッピング 🔵

**信頼性**: 🔵 *bedrock.py L27-L54 の多重継承定義、test_handler_ai_service_factory.py TC-056-026/027 で検証済みから確定*

**対象要件**: REQ-058-016

```
Given: BedrockService が Bedrock 固有例外を raise する
When: handler.py の except AIServiceError ブロックが例外を捕捉する
Then:
  - BedrockTimeoutError (extends BedrockServiceError, AITimeoutError) → HTTP 504
  - BedrockRateLimitError (extends BedrockServiceError, AIRateLimitError) → HTTP 429
  - BedrockInternalError (extends BedrockServiceError, AIInternalError) → HTTP 500
  - BedrockParseError (extends BedrockServiceError, AIParseError) → HTTP 500
  - isinstance() チェックが正しく動作する
```

---

### TC-ERROR-008: エラーマッピングテーブルの完全性検証 🔵

**信頼性**: 🔵 *handler.py L62-L107 の _map_ai_error_to_http() 関数の全分岐から確定*

**対象要件**: REQ-058-017

```
Given: _map_ai_error_to_http() 関数が存在する
When: 全 AI 例外タイプを入力として渡す
Then:
  - AITimeoutError → 504, "AI service timeout"
  - AIRateLimitError → 429, "AI service rate limit exceeded"
  - AIProviderError → 503, "AI service unavailable"
  - AIParseError → 500, "AI service response parse error"
  - AIInternalError → 500, "AI service error"
  - AIServiceError (基底) → 500, "AI service error"
  - 全レスポンスの Content-Type が "application/json"
```

---

## 3. TestFeatureFlagBehavior (TC-FLAG-001 ~ TC-FLAG-005)

### TC-FLAG-001: USE_STRANDS=true で StrandsAIService が選択される 🔵

**信頼性**: 🔵 *ai_service.py L185-L192 の create_ai_service() 実装から確定*

**対象要件**: REQ-058-020

```
Given: 環境変数 USE_STRANDS="true"
When: create_ai_service() を呼び出す
Then:
  - 返されるインスタンスが StrandsAIService 型である
  - isinstance(service, StrandsAIService) == True
```

---

### TC-FLAG-002: USE_STRANDS=false で BedrockService が選択される 🔵

**信頼性**: 🔵 *ai_service.py L193-L196 の create_ai_service() 実装から確定*

**対象要件**: REQ-058-021

```
Given: 環境変数 USE_STRANDS="false"
When: create_ai_service() を呼び出す
Then:
  - 返されるインスタンスが BedrockService 型である
  - isinstance(service, BedrockService) == True
```

---

### TC-FLAG-003: USE_STRANDS 未設定時のデフォルト動作 (BedrockService) 🔵

**信頼性**: 🔵 *ai_service.py L186 の os.getenv("USE_STRANDS", "false") から確定*

**対象要件**: REQ-058-022

```
Given: 環境変数 USE_STRANDS が未設定
When: create_ai_service() を呼び出す
Then:
  - デフォルト値 "false" が適用される
  - 返されるインスタンスが BedrockService 型である
```

---

### TC-FLAG-004: create_ai_service() への明示的引数渡し 🔵

**信頼性**: 🔵 *ai_service.py L171-L192 の use_strands パラメータ処理から確定*

**対象要件**: REQ-058-023

```
Given: create_ai_service(use_strands=True/False) を明示的に呼び出す
When: 引数で制御する (環境変数に依存しない)
Then:
  - use_strands=True → StrandsAIService が返される
  - use_strands=False → BedrockService が返される
  - 環境変数の値は無視される
```

---

### TC-FLAG-005: create_ai_service() 初期化失敗時の AIProviderError 🔵

**信頼性**: 🔵 *ai_service.py L196-L198 の Exception ハンドリングから確定*

**対象要件**: REQ-058-024

```
Given: AI サービスの初期化時に例外が発生する
When: create_ai_service() を呼び出す
Then:
  - AIProviderError にラップされる
  - エラーメッセージに "Failed to initialize AI service" が含まれる
  - 元の例外が __cause__ チェーンに保持される
```

---

## 4. TestGenerationResultValidity (TC-RESULT-001 ~ TC-RESULT-003)

### TC-RESULT-001: StrandsAIService の GenerationResult が有効 🔵

**信頼性**: 🔵 *strands_service.py L96-L147 の generate_cards() 実装から確定*

**対象要件**: REQ-058-040

```
Given: StrandsAIService が有効なモックレスポンスを受け取る
When: generate_cards() を呼び出す
Then:
  - GenerationResult の cards に GeneratedCard のリストが含まれる
  - input_length が入力テキストの len() と一致する
  - model_used が "strands_bedrock" (ENVIRONMENT != "dev" 時)
  - processing_time_ms が 0 以上の整数
  - 各 GeneratedCard の front と back が空でない文字列
```

---

### TC-RESULT-002: BedrockService の GenerationResult が有効 🔵

**信頼性**: 🔵 *bedrock.py L118-L165 の generate_cards() 実装から確定*

**対象要件**: REQ-058-041

```
Given: BedrockService が有効なモックレスポンスを受け取る
When: generate_cards() を呼び出す
Then:
  - GenerationResult の cards に GeneratedCard のリストが含まれる
  - input_length が入力テキストの len() と一致する
  - model_used が BEDROCK_MODEL_ID の値
  - processing_time_ms が 0 以上の整数
  - 各 GeneratedCard の front と back が空でない文字列
```

---

### TC-RESULT-003: 両サービスが AIService Protocol に適合 🔵

**信頼性**: 🔵 *ai_service.py L109-L131 の @runtime_checkable Protocol 定義から確定*

**対象要件**: REQ-058-031

```
Given: create_ai_service() が任意のフラグ値で呼ばれる
When: 返されたインスタンスの Protocol 適合性を検査する
Then:
  - isinstance(service, AIService) == True (@runtime_checkable)
  - generate_cards() メソッドが存在する
  - grade_answer() メソッドが存在する
  - get_learning_advice() メソッドが存在する
```

---

## 5. TestMigrationEdgeCases (TC-EDGE-001 ~ TC-EDGE-006)

### TC-EDGE-001: 空のカードレスポンスのハンドリング 🔵

**信頼性**: 🔵 *strands_service.py L242-L248 と bedrock.py L480-L481 の AIParseError から確定*

**対象要件**: REQ-058-060

```
Given: AI モデルが有効なカードを 0 枚含むレスポンスを返す
When: 両サービスでレスポンスをパースする
Then:
  - StrandsAIService: AIParseError を raise
  - BedrockService: BedrockParseError (extends AIParseError) を raise
  - 両方とも handler.py で HTTP 500 にマッピングされる
```

---

### TC-EDGE-002: 不完全なカードデータのスキップ動作 🔵

**信頼性**: 🔵 *strands_service.py L213-L221 と bedrock.py L453-L461 のスキップロジックから確定*

**対象要件**: REQ-058-061

```
Given: AI モデルが front/back の欠落したカードを含むレスポンスを返す
When: 両サービスでレスポンスをパースする
Then:
  - front または back が欠落しているカードはスキップされる
  - front または back が空文字列のカードはスキップされる
  - 有効なカードのみが GenerationResult.cards に含まれる
```

---

### TC-EDGE-003: Markdown コードブロック内 JSON の解析 🔵

**信頼性**: 🔵 *strands_service.py L194 と bedrock.py L439 の同一正規表現パターンから確定*

**対象要件**: REQ-058-062

```
Given: AI モデルが ```json ... ``` 形式でレスポンスを返す
When: 両サービスでレスポンスをパースする
Then:
  - Markdown コードブロック内の JSON が正しく抽出される
  - 両方のサービスで同一のパース結果が得られる
```

---

### TC-EDGE-004: "AI生成" タグの自動挿入 🔵

**信頼性**: 🔵 *strands_service.py L231-L232 と bedrock.py L469-L470 の同一ロジックから確定*

**対象要件**: REQ-058-063

```
Given: AI モデルが "AI生成" タグを含まないカードを返す
When: 両サービスでレスポンスをパースする
Then:
  - 両サービスとも "AI生成" タグを suggested_tags リストの先頭に挿入する
  - "AI生成" が既に存在する場合は挿入しない
```

---

### TC-EDGE-005: ConnectionError のプロバイダーエラーマッピング (Strands 固有) 🟡

**信頼性**: 🟡 *strands_service.py L155 の ConnectionError 処理から確認。BedrockService には同等の直接的な ConnectionError 処理がないため、Strands 固有のエッジケースとして推測*

**対象要件**: REQ-058-064

```
Given: StrandsAIService がプロバイダーへの接続に失敗する (ConnectionError)
When: generate_cards() を呼び出す
Then:
  - AIProviderError にラップされる
  - handler.py で HTTP 503 にマッピングされる
```

---

### TC-EDGE-006: 未知の例外の AIServiceError ラッピング (Strands 固有) 🟡

**信頼性**: 🟡 *strands_service.py L173 の catch-all Exception 処理から確認*

**対象要件**: REQ-058-065

```
Given: StrandsAIService が予期しない例外 (RuntimeError 等) を受け取る
When: generate_cards() を呼び出す
Then:
  - AIServiceError("Unexpected error: ...") にラップされる
  - handler.py で HTTP 500 にマッピングされる
```

---

## 6. TestExistingTestProtection (TC-PROTECT-001 ~ TC-PROTECT-003)

### TC-PROTECT-001: 既存テストスイート全件 PASS 確認 🔵

**信頼性**: 🔵 *pytest tests/ で 444 tests collected を確認済み。REQ-SM-405 から確定*

**対象要件**: REQ-058-050

```
Given: 全テストスイートを実行する
When: pytest で主要テストファイルを再実行する
Then:
  - 既存テスト結果が全て PASS する
  - テストの追加によってリグレッションが発生しない
```

**注意**: このテストは pytest.main() を使用して既存テストファイルの実行結果を確認する。

---

### TC-PROTECT-002: テストカバレッジ 80% 以上維持確認 🔵

**信頼性**: 🔵 *CLAUDE.md の「テストカバレッジ 80% 以上を目標」、REQ-SM-404 から確定*

**対象要件**: REQ-058-051

```
Given: 全テスト (既存 + 新規) を実行する
When: カバレッジレポートを確認する
Then:
  - サービス層のカバレッジが 80% 以上を維持する
```

**注意**: 実行時に手動で確認する。テスト自体はマーカーで示す。

---

### TC-PROTECT-003: USE_STRANDS=false (デフォルト) で既存テストが影響を受けない 🔵

**信頼性**: 🔵 *conftest.py の環境変数設定に USE_STRANDS が含まれていないため、デフォルト "false" が適用される。既存テストは BedrockService ベースのため影響なし*

**対象要件**: REQ-058-052

```
Given: conftest.py の環境変数 (USE_STRANDS 未設定)
When: デフォルト動作で既存テストを実行する
Then:
  - デフォルト値 "false" により BedrockService が使用される
  - 既存テストに USE_STRANDS の影響がない
```

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 **青信号** | 29件 | 94% |
| 🟡 **黄信号** | 2件 | 6% |
| 🔴 **赤信号** | 0件 | 0% |

**品質評価**: 高品質 (青信号 94%、赤信号なし)

### 黄信号の詳細

| テストケース | 内容 | 理由 |
|-------------|------|------|
| TC-EDGE-005 | ConnectionError のプロバイダーエラーマッピング | Strands 固有エッジケース。BedrockService に同等処理なし |
| TC-EDGE-006 | 未知の例外の AIServiceError ラッピング | SDK 依存の予期しないエラー型への安全策 |

---

## モック戦略

### StrandsAIService のモック

```python
def _make_mock_agent_instance(response_text: str) -> MagicMock:
    """Agent インスタンスのモックを作成."""
    mock_response = MagicMock()
    mock_response.__str__ = MagicMock(return_value=response_text)
    mock_agent = MagicMock()
    mock_agent.return_value = mock_response
    return mock_agent

# 使用例:
with patch("services.strands_service.Agent", return_value=mock_agent_instance), \
     patch("services.strands_service.BedrockModel"):
    service = StrandsAIService()
    result = service.generate_cards(input_text="...")
```

### BedrockService のモック

```python
mock_client = MagicMock()
mock_response_body = MagicMock()
mock_response_body.read.return_value = json.dumps({
    "content": [{"text": json.dumps({"cards": [...]})}]
}).encode()
mock_client.invoke_model.return_value = {"body": mock_response_body}
service = BedrockService(bedrock_client=mock_client)
```

### 環境変数の管理

```python
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

## 参考リソース

### 実装ファイル
- `backend/src/services/ai_service.py` - Protocol, Factory, 例外階層
- `backend/src/services/strands_service.py` - StrandsAIService 実装
- `backend/src/services/bedrock.py` - BedrockService 実装
- `backend/src/api/handler.py` - API ハンドラー, _map_ai_error_to_http()
- `backend/src/models/generate.py` - Pydantic リクエスト/レスポンスモデル

### 既存テストファイル
- `backend/tests/unit/test_ai_service.py` - Protocol + Factory テスト (54 tests)
- `backend/tests/unit/test_strands_service.py` - StrandsAIService テスト (39 tests)
- `backend/tests/unit/test_bedrock.py` - BedrockService テスト (20 tests)
- `backend/tests/unit/test_handler_ai_service_factory.py` - ハンドラー統合テスト (27 tests)
- `backend/tests/conftest.py` - テストフィクスチャ

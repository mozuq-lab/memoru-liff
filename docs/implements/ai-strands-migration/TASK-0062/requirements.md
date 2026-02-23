# TASK-0062: 学習アドバイス AI 実装 + GET /advice エンドポイント - TDD Requirements

## 概要

本ドキュメントは TASK-0062 の TDD Red フェーズで作成するテストケースの詳細要件を定義する。
対象は以下の 3 つのコンポーネント:

1. **StrandsAIService.get_learning_advice()** - NotImplementedError スタブからの本実装
2. **BedrockService.get_learning_advice()** - 既に実装済み、テスト追加のみ
3. **advice_handler Lambda** - 501 スタブからの本実装

**関連要件**: REQ-SM-004（学習アドバイス/AI 分析）、REQ-SM-403（Pydantic v2）、REQ-SM-404（テストカバレッジ 80%）

---

## 構造的前提

### advice_handler は独立 Lambda ハンドラー

`advice_handler` は `grade_ai_handler` と同一パターンの**独立 Lambda 関数**。template.yaml で `Handler: api.handler.advice_handler` として定義されており、API Gateway HTTP API v2 イベントを直接受け取る。

- `@app.get(...)` デコレータは使用しない
- `app.current_event` は使用できない
- レスポンスは Lambda プロキシ統合形式の dict（`statusCode`, `headers`, `body`）
- `_get_user_id_from_event()` で JWT claims からユーザー ID を取得
- `_make_lambda_response()` でレスポンスを構築

### AI サービスメソッドは同期

全 AI サービスメソッド (`generate_cards`, `grade_answer`, `get_learning_advice`) は同期。`async` は使用しない。

### BedrockService.get_learning_advice() は実装済み

`bedrock.py` L220-267 で完全に実装済み。テスト追加のみが必要。

---

## Part A: StrandsAIService.get_learning_advice() テスト

### A.1 設計要件

- **REQ-STR-ADV-001** 🔵: `get_learning_advice(review_summary, language)` が `LearningAdvice` dataclass を返すこと。
  - *根拠*: AIService Protocol の get_learning_advice シグネチャ（ai_service.py L153-167）
- **REQ-STR-ADV-002** 🔵: `get_advice_prompt(review_summary, language)` にパラメータを渡してプロンプトを生成すること。
  - *根拠*: BedrockService.get_learning_advice() の既存実装パターン（bedrock.py L242-244）
- **REQ-STR-ADV-003** 🔵: `Agent(model=self.model)` で Agent を作成し、プロンプトを渡して呼び出すこと。
  - *根拠*: generate_cards() / grade_answer() の既存 Agent 呼び出しパターン（strands_service.py L134-135, L288-289）
- **REQ-STR-ADV-004** 🔵: JSON レスポンスから `advice_text`, `weak_areas`, `recommendations` を抽出すること。
  - *根拠*: LearningAdvice dataclass のフィールド定義（ai_service.py L61-67）
- **REQ-STR-ADV-005** 🔵: `model_used` は `self.model_used` と一致すること。
  - *根拠*: generate_cards() / grade_answer() のメタデータパターン（strands_service.py L147, L301）
- **REQ-STR-ADV-006** 🔵: `processing_time_ms` が 0 以上の整数であること。
  - *根拠*: generate_cards() / grade_answer() のメタデータパターン
- **REQ-STR-ADV-007** 🔵: Markdown コードブロック (```` ```json ... ``` ````) 内の JSON が正しく解析されること。
  - *根拠*: _parse_grading_result() の既存パターン（strands_service.py L349-353）
- **REQ-STR-ADV-008** 🔵: 不正な JSON レスポンスで `AIParseError` を raise すること。
  - *根拠*: _parse_grading_result() の既存パターン（strands_service.py L357-358）
- **REQ-STR-ADV-009** 🔵: 必須フィールド欠損で `AIParseError` を raise すること。
  - *根拠*: _parse_grading_result() の既存パターン（strands_service.py L361-370）
- **REQ-STR-ADV-010** 🔵: `TimeoutError` で `AITimeoutError` を raise すること。
  - *根拠*: generate_cards() / grade_answer() のエラーハンドリングパターン（strands_service.py L153-154, L307-308）
- **REQ-STR-ADV-011** 🔵: `ConnectionError` で `AIProviderError` を raise すること。
  - *根拠*: generate_cards() / grade_answer() のエラーハンドリングパターン（strands_service.py L155-156, L309-310）
- **REQ-STR-ADV-012** 🟡: `ClientError (ThrottlingException)` で `AIRateLimitError` を raise すること。
  - *根拠*: _is_rate_limit_error() ヘルパーの既存パターン。SDK 固有の例外形式に依存。
- **REQ-STR-ADV-013** 🔵: 未知の例外は `AIServiceError` にラップされること。
  - *根拠*: generate_cards() / grade_answer() の汎用 except パターン（strands_service.py L173-174, L328）
- **REQ-STR-ADV-014** 🔵: 例外チェーン (`__cause__`) が保持されること。
  - *根拠*: 全例外で `from e` を使用する既存パターン

### A.2 テストケース: StrandsAIService.get_learning_advice()

**ファイル**: `backend/tests/unit/test_strands_service.py`
**テストクラス**: `TestStrandsAdvice`

#### 正常系

| TC ID | テスト名 | Given | When | Then | 信頼性 |
|-------|---------|-------|------|------|--------|
| TC-STR-ADV-001 | `test_get_learning_advice_success` | Agent が正常な JSON `{"advice_text": "...", "weak_areas": [...], "recommendations": [...]}` を返す | `get_learning_advice(review_summary={"total_reviews": 50}, language="ja")` を呼び出す | `LearningAdvice` が返り、`advice_text` が空でない文字列、`weak_areas` がリスト、`recommendations` がリスト | 🔵 |
| TC-STR-ADV-002 | `test_get_learning_advice_markdown_wrapped` | Agent が ```` ```json\n{...}\n``` ```` 形式で返す | `get_learning_advice(...)` を呼び出す | Markdown コードブロック内の JSON が正しく解析される | 🔵 |
| TC-STR-ADV-003 | `test_get_learning_advice_model_used` | Agent が正常なレスポンスを返す | `get_learning_advice(...)` を呼び出す | `result.model_used == service.model_used` | 🔵 |
| TC-STR-ADV-004 | `test_get_learning_advice_processing_time_ms` | Agent が正常なレスポンスを返す | `get_learning_advice(...)` を呼び出す | `result.processing_time_ms` が 0 以上の整数 | 🔵 |

#### 引数伝搬

| TC ID | テスト名 | Given | When | Then | 信頼性 |
|-------|---------|-------|------|------|--------|
| TC-STR-ADV-005 | `test_get_learning_advice_passes_args_to_prompt` | `get_advice_prompt` をモックする | `get_learning_advice(review_summary={"total_reviews": 10}, language="ja")` を呼び出す | `get_advice_prompt(review_summary={"total_reviews": 10}, language="ja")` が呼ばれる | 🔵 |
| TC-STR-ADV-006 | `test_get_learning_advice_language_en` | `get_advice_prompt` をモックする | `get_learning_advice(..., language="en")` を呼び出す | `get_advice_prompt(..., language="en")` が呼ばれる | 🔵 |

#### パースエラー

| TC ID | テスト名 | Given | When | Then | 信頼性 |
|-------|---------|-------|------|------|--------|
| TC-STR-ADV-007 | `test_get_learning_advice_parse_error_invalid_json` | Agent が `"This is not valid JSON"` を返す | `get_learning_advice(...)` を呼び出す | `AIParseError` が raise される | 🔵 |
| TC-STR-ADV-008 | `test_get_learning_advice_parse_error_missing_advice_text` | Agent が `{"weak_areas": [], "recommendations": []}` (advice_text 欠損) を返す | `get_learning_advice(...)` を呼び出す | `AIParseError` が raise される | 🔵 |
| TC-STR-ADV-009 | `test_get_learning_advice_parse_error_missing_weak_areas` | Agent が `{"advice_text": "...", "recommendations": []}` (weak_areas 欠損) を返す | `get_learning_advice(...)` を呼び出す | `AIParseError` が raise される | 🔵 |
| TC-STR-ADV-010 | `test_get_learning_advice_parse_error_missing_recommendations` | Agent が `{"advice_text": "...", "weak_areas": []}` (recommendations 欠損) を返す | `get_learning_advice(...)` を呼び出す | `AIParseError` が raise される | 🔵 |

#### エラーハンドリング

| TC ID | テスト名 | Given | When | Then | 信頼性 |
|-------|---------|-------|------|------|--------|
| TC-STR-ADV-011 | `test_get_learning_advice_timeout` | Agent が `TimeoutError` を raise する | `get_learning_advice(...)` を呼び出す | `AITimeoutError` が raise される | 🔵 |
| TC-STR-ADV-012 | `test_get_learning_advice_connection_error` | Agent が `ConnectionError` を raise する | `get_learning_advice(...)` を呼び出す | `AIProviderError` が raise される | 🔵 |
| TC-STR-ADV-013 | `test_get_learning_advice_rate_limit` | Agent が `ClientError (ThrottlingException)` を raise する | `get_learning_advice(...)` を呼び出す | `AIRateLimitError` が raise される | 🟡 |
| TC-STR-ADV-014 | `test_get_learning_advice_unknown_exception` | Agent が `RuntimeError` を raise する | `get_learning_advice(...)` を呼び出す | `AIServiceError` が raise される | 🔵 |
| TC-STR-ADV-015 | `test_get_learning_advice_exception_chain_preserved` | Agent が `ConnectionError` を raise する | `get_learning_advice(...)` を呼び出す | `exc.__cause__` が `None` でない | 🔵 |

---

## Part B: BedrockService.get_learning_advice() テスト

### B.1 設計要件

- **REQ-BDK-ADV-001** 🔵: `get_learning_advice(review_summary, language)` が `LearningAdvice` dataclass を返すこと。
  - *根拠*: bedrock.py L220-267 の実装済みコード
- **REQ-BDK-ADV-002** 🔵: `get_advice_prompt(review_summary, language)` にパラメータを渡してプロンプトを生成すること。
  - *根拠*: bedrock.py L242-244
- **REQ-BDK-ADV-003** 🔵: `_invoke_with_retry()` でリトライ付き Bedrock 呼び出しを行うこと。
  - *根拠*: bedrock.py L247
- **REQ-BDK-ADV-004** 🔵: `_parse_json_response()` で `advice_text`, `weak_areas`, `recommendations` を抽出すること。
  - *根拠*: bedrock.py L249-253
- **REQ-BDK-ADV-005** 🔵: `model_used` が `self.model_id` と一致すること。
  - *根拠*: bedrock.py L265
- **REQ-BDK-ADV-006** 🔵: `processing_time_ms` が 0 以上の整数であること。
  - *根拠*: bedrock.py L263
- **REQ-BDK-ADV-007** 🔵: Markdown コードブロック内の JSON が正しく解析されること。
  - *根拠*: _parse_json_response() の実装（bedrock.py L293-294）
- **REQ-BDK-ADV-008** 🔵: 不正な JSON で `BedrockParseError` を raise すること。
  - *根拠*: _parse_json_response() の実装（bedrock.py L310-311）
- **REQ-BDK-ADV-009** 🔵: 必須フィールド欠損で `BedrockParseError` を raise すること。
  - *根拠*: _parse_json_response() の実装（bedrock.py L301-306）
- **REQ-BDK-ADV-010** 🔵: `ReadTimeoutError` で `BedrockTimeoutError` を raise すること（リトライなし）。
  - *根拠*: _invoke_with_retry() の実装（bedrock.py L351-353）
- **REQ-BDK-ADV-011** 🔵: `ThrottlingException` で `BedrockRateLimitError` を raise すること（リトライあり）。
  - *根拠*: _invoke_with_retry() の実装（bedrock.py L354-361）
- **REQ-BDK-ADV-012** 🔵: `InternalServerException` で `BedrockInternalError` を raise すること（リトライあり）。
  - *根拠*: _invoke_with_retry() の実装（bedrock.py L362-369）

### B.2 テストケース: BedrockService.get_learning_advice()

**ファイル**: `backend/tests/unit/test_bedrock.py`
**テストクラス**: `TestBedrockGetLearningAdvice`

#### 正常系

| TC ID | テスト名 | Given | When | Then | 信頼性 |
|-------|---------|-------|------|------|--------|
| TC-BDK-ADV-001 | `test_get_learning_advice_success` | Bedrock が `{"advice_text": "...", "weak_areas": [...], "recommendations": [...]}` を返す | `get_learning_advice(review_summary={"total_reviews": 50})` を呼び出す | `LearningAdvice` が返り、全フィールドが正しい | 🔵 |
| TC-BDK-ADV-002 | `test_get_learning_advice_with_markdown` | Bedrock が ```` ```json\n{...}\n``` ```` 形式で返す | `get_learning_advice(...)` を呼び出す | Markdown コードブロック内の JSON が正しく解析される | 🔵 |
| TC-BDK-ADV-003 | `test_get_learning_advice_model_used` | `model_id="test-model-id"` で初期化 | `get_learning_advice(...)` を呼び出す | `result.model_used == "test-model-id"` | 🔵 |
| TC-BDK-ADV-004 | `test_get_learning_advice_processing_time_ms` | Bedrock が正常なレスポンスを返す | `get_learning_advice(...)` を呼び出す | `result.processing_time_ms` が 0 以上の整数 | 🔵 |

#### 引数伝搬

| TC ID | テスト名 | Given | When | Then | 信頼性 |
|-------|---------|-------|------|------|--------|
| TC-BDK-ADV-005 | `test_get_learning_advice_calls_get_advice_prompt` | `get_advice_prompt` をモックする | `get_learning_advice(review_summary={"total_reviews": 10}, language="en")` を呼び出す | `get_advice_prompt(review_summary={"total_reviews": 10}, language="en")` が呼ばれる | 🔵 |

#### パースエラー

| TC ID | テスト名 | Given | When | Then | 信頼性 |
|-------|---------|-------|------|------|--------|
| TC-BDK-ADV-006 | `test_get_learning_advice_parse_error` | Bedrock が `"This is not valid JSON"` を返す | `get_learning_advice(...)` を呼び出す | `BedrockParseError` が raise される | 🔵 |
| TC-BDK-ADV-007 | `test_get_learning_advice_missing_advice_text` | Bedrock が `{"weak_areas": [], "recommendations": []}` を返す | `get_learning_advice(...)` を呼び出す | `BedrockParseError` が raise される（missing field） | 🔵 |
| TC-BDK-ADV-008 | `test_get_learning_advice_missing_weak_areas` | Bedrock が `{"advice_text": "...", "recommendations": []}` を返す | `get_learning_advice(...)` を呼び出す | `BedrockParseError` が raise される | 🔵 |
| TC-BDK-ADV-009 | `test_get_learning_advice_missing_recommendations` | Bedrock が `{"advice_text": "...", "weak_areas": []}` を返す | `get_learning_advice(...)` を呼び出す | `BedrockParseError` が raise される | 🔵 |

#### API エラー

| TC ID | テスト名 | Given | When | Then | 信頼性 |
|-------|---------|-------|------|------|--------|
| TC-BDK-ADV-010 | `test_get_learning_advice_timeout` | Bedrock が `ClientError(ReadTimeoutError)` を raise する | `get_learning_advice(...)` を呼び出す | `BedrockTimeoutError` が raise される | 🔵 |
| TC-BDK-ADV-011 | `test_get_learning_advice_rate_limit` | Bedrock が `ClientError(ThrottlingException)` を raise する | `get_learning_advice(...)` を呼び出す | `BedrockRateLimitError` が raise される、invoke_model が 3 回呼ばれる | 🔵 |
| TC-BDK-ADV-012 | `test_get_learning_advice_internal_error` | Bedrock が `ClientError(InternalServerException)` を raise する | `get_learning_advice(...)` を呼び出す | `BedrockInternalError` が raise される、invoke_model が 3 回呼ばれる | 🔵 |

---

## Part C: advice_handler Lambda テスト

### C.1 設計要件

#### 認証

- **REQ-ADV-AUTH-001** 🔵: `_get_user_id_from_event(event)` で `requestContext.authorizer.jwt.claims.sub` から `user_id` を抽出すること。
  - *根拠*: _get_user_id_from_event() 実装（handler.py L152-188）、grade_ai_handler の認証パターン
- **REQ-ADV-AUTH-002** 🔵: 認証情報が取得できない場合は HTTP 401 を返すこと。
  - *根拠*: grade_ai_handler の認証パターン（handler.py L668-669）

#### データフロー

- **REQ-ADV-FLOW-001** 🔵: `review_service.get_review_summary(user_id)` でユーザーの学習データを集計すること。
  - *根拠*: dataflow.md 機能3 学習アドバイスフロー、TASK-0062.md L267
- **REQ-ADV-FLOW-002** 🔵: `ReviewSummary` を `dataclasses.asdict()` で dict に変換し、`ai_service.get_learning_advice(review_summary=dict, language=language)` に渡すこと。
  - *根拠*: AIService Protocol の get_learning_advice シグネチャ（`review_summary: dict`）
- **REQ-ADV-FLOW-003** 🔵: `create_ai_service()` ファクトリーを使用して AI サービスを取得すること。
  - *根拠*: 既存 generate_cards / grade_ai_handler のパターン
- **REQ-ADV-FLOW-004** 🔵: `language` パラメータは `event.queryStringParameters.language` から取得し、デフォルトは `"ja"` とすること。
  - *根拠*: grade_ai_handler の language 取得パターン（handler.py L698）、TASK-0062.md L258-259

#### レスポンス

- **REQ-ADV-RES-001** 🔵: 成功時は HTTP 200 を返すこと。
  - *根拠*: api-endpoints.md「レスポンス（成功 200）」
- **REQ-ADV-RES-002** 🔵: レスポンスに `advice_text`, `weak_areas`, `recommendations` が含まれること。
  - *根拠*: LearningAdviceResponse モデル定義（advice.py L8-22）
- **REQ-ADV-RES-003** 🔵: レスポンスに `study_stats` が含まれ、`total_reviews`, `average_grade`, `total_cards`, `cards_due_today`, `streak_days` を含むこと。
  - *根拠*: LearningAdviceResponse.study_stats フィールド（advice.py L23-26）、TASK-0062.md L276-281
- **REQ-ADV-RES-004** 🔵: レスポンスに `advice_info` が含まれ、`model_used` と `processing_time_ms` を含むこと。
  - *根拠*: LearningAdviceResponse.advice_info フィールド（advice.py L27-29）、TASK-0062.md L288-291
- **REQ-ADV-RES-005** 🔵: Content-Type ヘッダーは `application/json` であること。
  - *根拠*: _make_lambda_response() のレスポンスパターン（handler.py L201-205）

#### エラーハンドリング

- **REQ-ADV-ERR-001** 🔵: `AITimeoutError` → HTTP 504 にマッピングされること。
  - *根拠*: _map_ai_error_to_http() の実装（handler.py L75-80）
- **REQ-ADV-ERR-002** 🔵: `AIRateLimitError` → HTTP 429 にマッピングされること。
  - *根拠*: _map_ai_error_to_http() の実装（handler.py L82-87）
- **REQ-ADV-ERR-003** 🔵: `AIProviderError` → HTTP 503 にマッピングされること。
  - *根拠*: _map_ai_error_to_http() の実装（handler.py L89-94）
- **REQ-ADV-ERR-004** 🔵: `AIParseError` → HTTP 500 にマッピングされること。
  - *根拠*: _map_ai_error_to_http() の実装（handler.py L96-101）
- **REQ-ADV-ERR-005** 🔵: `AIInternalError` / その他 `AIServiceError` → HTTP 500 にマッピングされること。
  - *根拠*: _map_ai_error_to_http() の実装（handler.py L103-107）
- **REQ-ADV-ERR-006** 🔵: `AIProviderError` (ファクトリー初期化失敗) → HTTP 503 にマッピングされること。
  - *根拠*: create_ai_service() の AIProviderError（ai_service.py L198）
- **REQ-ADV-ERR-007** 🔵: 予期しない例外は HTTP 500 にマッピングすること。
  - *根拠*: grade_ai_handler の except Exception パターン（handler.py L741-743）

#### ロギング

- **REQ-ADV-LOG-001** 🔵: リクエスト受信時に `logger.info` で `user_id` と `language` を記録すること。
  - *根拠*: TASK-0062.md ロギング仕様 L340-348
- **REQ-ADV-LOG-002** 🔵: 成功時に `logger.info` で `weak_areas_count`, `recommendations_count`, `model_used` を記録すること。
  - *根拠*: TASK-0062.md ロギング仕様、grade_ai_handler の成功ログパターン（handler.py L725-728）
- **REQ-ADV-LOG-003** 🔵: AI エラー時に `logger.warning` で記録すること。
  - *根拠*: grade_ai_handler の AI エラーログパターン（handler.py L716）

### C.2 テストケース: advice_handler

**ファイル**: `backend/tests/unit/test_handler_advice.py`

#### テストイベント構築ヘルパー

```python
def _make_advice_event(
    user_id: str = "test-user-id",
    query_params: dict | None = None,
    authorizer: dict | None = None,
) -> dict:
    """advice_handler 用の API Gateway HTTP API v2 イベントを構築する。"""
    if authorizer is None:
        authorizer = {
            "jwt": {
                "claims": {"sub": user_id},
                "scopes": ["openid", "profile"],
            }
        }
    event = {
        "version": "2.0",
        "routeKey": "GET /advice",
        "rawPath": "/advice",
        "rawQueryString": "",
        "pathParameters": None,
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api-id",
            "authorizer": authorizer,
            "http": {"method": "GET"},
            "requestId": "test-request-id",
            "routeKey": "GET /advice",
            "stage": "$default",
        },
        "headers": {"content-type": "application/json"},
        "isBase64Encoded": False,
    }
    if query_params:
        event["queryStringParameters"] = query_params
    return event
```

#### モックフィクスチャ

```python
@pytest.fixture
def mock_review_service():
    """ReviewService のモック。ReviewSummary を返す。"""
    with patch("api.handler.review_service") as mock:
        mock.get_review_summary.return_value = ReviewSummary(
            total_reviews=100,
            average_grade=3.5,
            total_cards=50,
            cards_due_today=10,
            streak_days=5,
            tag_performance={"math": 0.8, "science": 0.6},
            recent_review_dates=["2026-02-24", "2026-02-23"],
        )
        yield mock

@pytest.fixture
def mock_ai_service():
    """create_ai_service のモック。LearningAdvice を返す。"""
    with patch("api.handler.create_ai_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.get_learning_advice.return_value = LearningAdvice(
            advice_text="数学の復習頻度を上げましょう。",
            weak_areas=["数学", "物理"],
            recommendations=["毎日10枚のカードを復習する", "弱点タグを重点的に復習"],
            model_used="test-model",
            processing_time_ms=800,
        )
        mock_factory.return_value = mock_service
        yield mock_factory, mock_service
```

---

#### カテゴリ A: 認証テスト

| TC ID | テスト名 | Given | When | Then | 信頼性 |
|-------|---------|-------|------|------|--------|
| TC-062-AUTH-001 | `test_advice_returns_401_when_no_authorizer` | `requestContext.authorizer` が空辞書 `{}` | `advice_handler(event, context)` を呼び出す | HTTP 401, `{"error": "Unauthorized"}` | 🔵 |
| TC-062-AUTH-002 | `test_advice_returns_401_when_no_sub_claim` | `authorizer.jwt.claims` に `sub` がない（`iss` のみ） | `advice_handler(event, context)` を呼び出す | HTTP 401, `{"error": "Unauthorized"}` | 🔵 |
| TC-062-AUTH-003 | `test_advice_extracts_user_id_from_jwt_claims` | `authorizer.jwt.claims.sub = "user-abc-123"` | `advice_handler(event, context)` を呼び出す | `review_service.get_review_summary` が `user_id="user-abc-123"` で呼ばれる | 🔵 |

---

#### カテゴリ B: データフローテスト

| TC ID | テスト名 | Given | When | Then | 信頼性 |
|-------|---------|-------|------|------|--------|
| TC-062-FLOW-001 | `test_advice_calls_get_review_summary` | ReviewService と AI サービスが正常動作するモック | `advice_handler(event, context)` を呼び出す | `review_service.get_review_summary("test-user-id")` が 1 回呼ばれる | 🔵 |
| TC-062-FLOW-002 | `test_advice_calls_create_ai_service_factory` | モック設定済み | `advice_handler(event, context)` を呼び出す | `create_ai_service()` が 1 回呼ばれる | 🔵 |
| TC-062-FLOW-003 | `test_advice_passes_review_summary_dict_to_ai_service` | ReviewService が ReviewSummary(total_reviews=100, ...) を返す | `advice_handler(event, context)` を呼び出す | `ai_service.get_learning_advice(review_summary=<dict containing total_reviews=100>, ...)` が呼ばれる | 🔵 |
| TC-062-FLOW-004 | `test_advice_passes_language_param_to_ai_service` | `queryStringParameters = {"language": "en"}` | `advice_handler(event, context)` を呼び出す | `ai_service.get_learning_advice(..., language="en")` が呼ばれる | 🔵 |
| TC-062-FLOW-005 | `test_advice_uses_default_language_ja` | `queryStringParameters` なし | `advice_handler(event, context)` を呼び出す | `ai_service.get_learning_advice(..., language="ja")` が呼ばれる | 🔵 |

---

#### カテゴリ C: 正常系レスポンステスト

| TC ID | テスト名 | Given | When | Then | 信頼性 |
|-------|---------|-------|------|------|--------|
| TC-062-RES-001 | `test_advice_success_returns_200` | ReviewService と AI サービスが正常動作 | `advice_handler(event, context)` を呼び出す | HTTP 200 | 🔵 |
| TC-062-RES-002 | `test_advice_success_response_contains_advice_text` | AI が `advice_text="数学の復習頻度を上げましょう。"` を返す | `advice_handler(event, context)` を呼び出す | `body["advice_text"] == "数学の復習頻度を上げましょう。"` | 🔵 |
| TC-062-RES-003 | `test_advice_success_response_contains_weak_areas` | AI が `weak_areas=["数学", "物理"]` を返す | `advice_handler(event, context)` を呼び出す | `body["weak_areas"] == ["数学", "物理"]` | 🔵 |
| TC-062-RES-004 | `test_advice_success_response_contains_recommendations` | AI が `recommendations=["毎日10枚...", "弱点タグ..."]` を返す | `advice_handler(event, context)` を呼び出す | `body["recommendations"]` が 2 要素のリスト | 🔵 |
| TC-062-RES-005 | `test_advice_success_response_contains_study_stats` | ReviewService が `total_reviews=100, average_grade=3.5, total_cards=50, cards_due_today=10, streak_days=5` を返す | `advice_handler(event, context)` を呼び出す | `body["study_stats"]` に `total_reviews=100`, `average_grade=3.5`, `total_cards=50`, `cards_due_today=10`, `streak_days=5` が含まれる | 🔵 |
| TC-062-RES-006 | `test_advice_success_response_contains_advice_info` | AI が `model_used="test-model", processing_time_ms=800` を返す | `advice_handler(event, context)` を呼び出す | `body["advice_info"]["model_used"] == "test-model"`, `body["advice_info"]["processing_time_ms"] == 800` | 🔵 |
| TC-062-RES-007 | `test_advice_success_response_is_json` | 正常リクエスト | `advice_handler(event, context)` を呼び出す | Content-Type が `application/json` | 🔵 |
| TC-062-RES-008 | `test_advice_success_full_e2e_flow` | カスタム user_id, ReviewSummary, AI 結果で一連フロー | `advice_handler(event, context)` を呼び出す | 全フィールドが正しく返される、全呼び出し引数が正しい | 🔵 |

---

#### カテゴリ D: AI エラーハンドリングテスト

| TC ID | テスト名 | Given | When | Then | 信頼性 |
|-------|---------|-------|------|------|--------|
| TC-062-ERR-001 | `test_advice_returns_504_on_ai_timeout` | `get_learning_advice` が `AITimeoutError` を raise する | `advice_handler(event, context)` を呼び出す | HTTP 504, `{"error": "AI service timeout"}` | 🔵 |
| TC-062-ERR-002 | `test_advice_returns_429_on_ai_rate_limit` | `get_learning_advice` が `AIRateLimitError` を raise する | `advice_handler(event, context)` を呼び出す | HTTP 429, `{"error": "AI service rate limit exceeded"}` | 🔵 |
| TC-062-ERR-003 | `test_advice_returns_503_on_ai_provider_error` | `get_learning_advice` が `AIProviderError` を raise する | `advice_handler(event, context)` を呼び出す | HTTP 503, `{"error": "AI service unavailable"}` | 🔵 |
| TC-062-ERR-004 | `test_advice_returns_500_on_ai_parse_error` | `get_learning_advice` が `AIParseError` を raise する | `advice_handler(event, context)` を呼び出す | HTTP 500, `{"error": "AI service response parse error"}` | 🔵 |
| TC-062-ERR-005 | `test_advice_returns_500_on_ai_internal_error` | `get_learning_advice` が `AIInternalError` を raise する | `advice_handler(event, context)` を呼び出す | HTTP 500, `{"error": "AI service error"}` | 🔵 |
| TC-062-ERR-006 | `test_advice_returns_503_on_factory_init_failure` | `create_ai_service()` が `AIProviderError` を raise する | `advice_handler(event, context)` を呼び出す | HTTP 503, `{"error": "AI service unavailable"}` | 🔵 |
| TC-062-ERR-007 | `test_advice_returns_500_on_unexpected_exception` | `get_learning_advice` が `RuntimeError` を raise する | `advice_handler(event, context)` を呼び出す | HTTP 500, `{"error": "Internal Server Error"}` | 🔵 |

---

#### カテゴリ E: DB/ReviewService エラーテスト

| TC ID | テスト名 | Given | When | Then | 信頼性 |
|-------|---------|-------|------|------|--------|
| TC-062-DB-001 | `test_advice_handles_review_service_exception` | `review_service.get_review_summary` が `Exception` を raise する | `advice_handler(event, context)` を呼び出す | HTTP 500, `{"error": "Internal Server Error"}` | 🔵 |
| TC-062-DB-002 | `test_advice_works_with_empty_review_summary` | `review_service.get_review_summary` がデフォルト ReviewSummary（全ゼロ）を返す | `advice_handler(event, context)` を呼び出す | HTTP 200 で正常にアドバイスが返る（復習履歴なしでも動作） | 🔵 |

---

#### カテゴリ F: ロギングテスト

| TC ID | テスト名 | Given | When | Then | 信頼性 |
|-------|---------|-------|------|------|--------|
| TC-062-LOG-001 | `test_advice_logs_request_info` | 正常リクエスト | `advice_handler(event, context)` を呼び出す | `logger.info` が `user_id` を含む引数で呼ばれる | 🔵 |
| TC-062-LOG-002 | `test_advice_logs_success_info` | AI アドバイス生成成功 | `advice_handler(event, context)` を呼び出す | `logger.info` が成功に関する情報で呼ばれる | 🔵 |
| TC-062-LOG-003 | `test_advice_logs_ai_error` | `get_learning_advice` が `AITimeoutError` を raise する | `advice_handler(event, context)` を呼び出す | `logger.warning` または `logger.error` が呼ばれる | 🔵 |

---

## テストファイル構成サマリー

### Part A: StrandsAIService テスト追加

| ファイル | テストクラス | TC 数 |
|---------|------------|-------|
| `backend/tests/unit/test_strands_service.py` | `TestStrandsAdvice` | 15 |

### Part B: BedrockService テスト追加

| ファイル | テストクラス | TC 数 |
|---------|------------|-------|
| `backend/tests/unit/test_bedrock.py` | `TestBedrockGetLearningAdvice` | 12 |

### Part C: advice_handler テスト新規作成

| ファイル | テストクラス | TC 数 |
|---------|------------|-------|
| `backend/tests/unit/test_handler_advice.py` | `TestAdviceHandlerAuth` | 3 |
| | `TestAdviceHandlerFlow` | 5 |
| | `TestAdviceHandlerSuccess` | 8 |
| | `TestAdviceHandlerAIErrors` | 7 |
| | `TestAdviceHandlerDBErrors` | 2 |
| | `TestAdviceHandlerLogging` | 3 |

### テスト合計

| カテゴリ | 件数 |
|---------|------|
| StrandsAIService 正常系 | 4 |
| StrandsAIService 引数伝搬 | 2 |
| StrandsAIService パースエラー | 4 |
| StrandsAIService エラーハンドリング | 5 |
| BedrockService 正常系 | 4 |
| BedrockService 引数伝搬 | 1 |
| BedrockService パースエラー | 4 |
| BedrockService API エラー | 3 |
| Handler 認証 | 3 |
| Handler データフロー | 5 |
| Handler 正常系レスポンス | 8 |
| Handler AI エラー | 7 |
| Handler DB エラー | 2 |
| Handler ロギング | 3 |
| **合計** | **55** |

---

## 既存テストへの影響

### `test_strands_service.py` の `TestStrandsServiceStubs`

TASK-0062 完了後、以下の既存テストは**削除が必要**:

- **TC-STUB-002** (`test_get_learning_advice_raises_not_implemented`): `get_learning_advice()` が本実装されるため
- **TC-STUB-003** (`test_not_implemented_error_message_contains_phase3`): 同上

### `test_handler_ai_service_factory.py` のスタブテスト

`advice_handler` の 501 スタブを検証するテストが存在する場合は削除が必要。

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 54 | 98.2% |
| 🟡 黄信号 | 1 | 1.8% |
| 🔴 赤信号 | 0 | 0% |

**品質評価**: 高品質（青信号 98%、赤信号なし）

### 黄信号の理由

| TC ID | 理由 |
|-------|------|
| TC-STR-ADV-013 | Strands SDK 経由の `ClientError (ThrottlingException)` のレート制限マッピングは SDK の例外伝搬方式に依存。`_is_rate_limit_error()` のフォールバック文字列マッチに依存する可能性がある。 |

### 信頼性根拠

全テストケースが以下の確定情報に基づいている:
- 既存 `bedrock.py` L220-267 の `get_learning_advice()` 実装コード
- 既存 `strands_service.py` の `generate_cards()` / `grade_answer()` パターン
- 既存 `handler.py` の `grade_ai_handler` パターン
- `ai_service.py` の AIService Protocol / 例外階層 / LearningAdvice dataclass 定義
- `models/advice.py` の LearningAdviceResponse Pydantic モデル定義
- `review_service.py` の `get_review_summary()` 実装
- `services/prompts/advice.py` の `get_advice_prompt()` 実装
- `template.yaml` の `AdviceFunction` 定義

---

## 依存関係

```
TASK-0056 (ReviewService) ──────┐
                                 ├── TASK-0062 (本タスク) ──> TASK-0063 (Phase 3 統合テスト)
TASK-0061 (アドバイスモデル) ────┘
```

---

*作成日*: 2026-02-24
*タスク*: TASK-0062 TDD Requirements Phase
*信頼性*: 🔵 54件 (98.2%) / 🟡 1件 (1.8%) / 🔴 0件 (0%)

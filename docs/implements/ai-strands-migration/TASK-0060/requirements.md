# TASK-0060: POST /reviews/{card_id}/grade-ai エンドポイント - TDD Requirements

## 概要

本ドキュメントは TASK-0060 の TDD Red フェーズで作成するテストケースの詳細要件を定義する。
対象は `grade_ai_handler` Lambda ハンドラーの本実装（スタブからの置き換え）。
カード取得、AI 採点呼び出し、GradeAnswerResponse 形式でのレスポンス返却フローを検証する。

**関連要件**: REQ-SM-003（回答採点/AI 評価）、REQ-SM-403（Pydantic v2）、REQ-SM-404（テストカバレッジ 80%）

---

## 構造的前提: 独立 Lambda ハンドラー

`grade_ai_handler` は `app` (APIGatewayHttpResolver) を経由しない**独立 Lambda 関数**である。template.yaml で `Handler: api.handler.grade_ai_handler` として定義されており、API Gateway HTTP API v2 イベントを直接受け取る。

- `@app.post(...)` デコレータは使用しない
- `app.current_event` は使用できない
- レスポンスは Lambda プロキシ統合形式の dict（`statusCode`, `headers`, `body`）

---

## 1. ユーザー認証（JWT 抽出）

### 1.1 設計要件

- **REQ-AUTH-001** 🔵: `event.requestContext.authorizer.jwt.claims.sub` から `user_id` を抽出すること。
  - *根拠*: 既存 `get_user_id_from_context()` の JWT Authorizer パス（handler.py L122-123）、api-endpoints.md 認証仕様
- **REQ-AUTH-002** 🔵: `requestContext.authorizer.claims.sub` (REST API パス) からも `user_id` を抽出できること。
  - *根拠*: 既存 `get_user_id_from_context()` の REST API パス（handler.py L125-126）
- **REQ-AUTH-003** 🔵: `requestContext.authorizer.sub` (直接アクセスパス) からも `user_id` を抽出できること。
  - *根拠*: 既存 `get_user_id_from_context()` の直接アクセスパス（handler.py L128-129）
- **REQ-AUTH-004** 🔵: 認証情報が取得できない場合は HTTP 401 を返すこと。
  - *根拠*: api-endpoints.md エラーコード仕様、既存 `get_user_id_from_context()` の UnauthorizedError
- **REQ-AUTH-005** 🔵: dev 環境では Authorization ヘッダーから JWT を直接デコードするフォールバックを提供すること。
  - *根拠*: 既存 `get_user_id_from_context()` の dev フォールバック（handler.py L136-146）

### 1.2 テストケース: 認証

**ファイル**: `backend/tests/unit/test_handler_grade_ai.py`

| TC ID | テスト名 | 入力 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-060-AUTH-001 | `test_grade_ai_returns_401_when_no_authorizer` | `requestContext.authorizer` が空 | HTTP 401, `{"error": "Unauthorized"}` | 🔵 |
| TC-060-AUTH-002 | `test_grade_ai_returns_401_when_no_sub_claim` | `authorizer.jwt.claims` に `sub` がない | HTTP 401, `{"error": "Unauthorized"}` | 🔵 |
| TC-060-AUTH-003 | `test_grade_ai_extracts_user_id_from_jwt_claims` | `authorizer.jwt.claims.sub = "user-123"` | 正常処理に進み、CardService に `user_id="user-123"` が渡される | 🔵 |

---

## 2. パスパラメータ取得

### 2.1 設計要件

- **REQ-PATH-001** 🔵: `event.pathParameters.cardId` から `card_id` を取得すること（camelCase キー）。
  - *根拠*: template.yaml の API ルート `/reviews/{cardId}/grade-ai`
- **REQ-PATH-002** 🔵: `pathParameters` が null または `cardId` が欠損の場合は HTTP 400 を返すこと。
  - *根拠*: 防御的プログラミング、api-endpoints.md のバリデーションエラー 400

### 2.2 テストケース: パスパラメータ

| TC ID | テスト名 | 入力 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-060-PATH-001 | `test_grade_ai_extracts_card_id_from_path_params` | `pathParameters.cardId = "card-abc"` | CardService.get_card に `card_id="card-abc"` が渡される | 🔵 |
| TC-060-PATH-002 | `test_grade_ai_returns_400_when_card_id_missing` | `pathParameters` が null | HTTP 400 | 🔵 |

---

## 3. リクエストバリデーション

### 3.1 設計要件

- **REQ-BODY-001** 🔵: `event.body` を JSON パースし、`GradeAnswerRequest` でバリデーションすること。
  - *根拠*: api-endpoints.md の POST /reviews/{card_id}/grade-ai リクエスト仕様、TASK-0059 の GradeAnswerRequest
- **REQ-BODY-002** 🔵: `event.body` が null または無効な JSON の場合は HTTP 400 を返すこと。
  - *根拠*: 既存 handler.py の `json.JSONDecodeError` ハンドリングパターン
- **REQ-BODY-003** 🔵: `GradeAnswerRequest` の `ValidationError` (Pydantic) は HTTP 400 に変換すること。
  - *根拠*: 既存 handler.py の `submit_review`, `create_card` 等のパターン（L400-405, L561-567）
- **REQ-BODY-004** 🔵: `user_answer` が空文字列の場合は HTTP 400 を返すこと。
  - *根拠*: GradeAnswerRequest の `min_length=1` 制約（TASK-0059）
- **REQ-BODY-005** 🔵: `user_answer` が空白のみの場合は HTTP 400 を返すこと。
  - *根拠*: GradeAnswerRequest の `validate_user_answer` バリデータ（TASK-0059）
- **REQ-BODY-006** 🔵: `user_answer` が 2000 文字超の場合は HTTP 400 を返すこと。
  - *根拠*: GradeAnswerRequest の `max_length=2000` 制約（TASK-0059）

### 3.2 テストケース: リクエストバリデーション

| TC ID | テスト名 | 入力 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-060-VAL-001 | `test_grade_ai_returns_400_when_body_is_null` | `event.body = None` | HTTP 400 | 🔵 |
| TC-060-VAL-002 | `test_grade_ai_returns_400_when_body_is_invalid_json` | `event.body = "not json"` | HTTP 400 | 🔵 |
| TC-060-VAL-003 | `test_grade_ai_returns_400_when_user_answer_empty` | `{"user_answer": ""}` | HTTP 400 | 🔵 |
| TC-060-VAL-004 | `test_grade_ai_returns_400_when_user_answer_whitespace_only` | `{"user_answer": "   "}` | HTTP 400 | 🔵 |
| TC-060-VAL-005 | `test_grade_ai_returns_400_when_user_answer_too_long` | `{"user_answer": "a" * 2001}` | HTTP 400 | 🔵 |
| TC-060-VAL-006 | `test_grade_ai_returns_400_when_user_answer_missing` | `{}` (フィールド未指定) | HTTP 400 | 🔵 |

---

## 4. カード取得と所有権チェック

### 4.1 設計要件

- **REQ-CARD-001** 🔵: `card_service.get_card(user_id, card_id)` でカードを取得すること。
  - *根拠*: dataflow.md 機能2 回答採点フロー Step 2「CardService 経由でカードの front と back を取得」
- **REQ-CARD-002** 🔵: `CardNotFoundError` が raise された場合は HTTP 404 を返すこと。
  - *根拠*: api-endpoints.md エラーコード 404「カードが見つからない / 他ユーザーのカード」
- **REQ-CARD-003** 🔵: 取得したカードの `.front` と `.back` 属性を AI 採点に渡すこと。Card は Pydantic BaseModel であり、`.front` / `.back` で直接アクセスする。
  - *根拠*: Card モデル定義（card.py L72-85）、dataflow.md の `Card(front, back)`

### 4.2 テストケース: カード関連

| TC ID | テスト名 | 条件 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-060-CARD-001 | `test_grade_ai_returns_404_when_card_not_found` | `card_service.get_card` が `CardNotFoundError` を raise | HTTP 404, `{"error": "Not Found"}` | 🔵 |
| TC-060-CARD-002 | `test_grade_ai_passes_card_front_back_to_ai_service` | カード取得成功 | `ai_service.grade_answer` に `card_front=card.front`, `card_back=card.back` が渡される | 🔵 |
| TC-060-CARD-003 | `test_grade_ai_returns_404_for_other_users_card` | 異なる user_id でのカード取得 → `CardNotFoundError` | HTTP 404 | 🔵 |

---

## 5. AI 採点呼び出し

### 5.1 設計要件

- **REQ-AI-001** 🔵: `create_ai_service()` ファクトリーを使用して AI サービスを取得すること。
  - *根拠*: 既存 `generate_cards` エンドポイントのパターン（handler.py L317）、TASK-0056 要件
- **REQ-AI-002** 🔵: `ai_service.grade_answer(card_front, card_back, user_answer, language)` を呼び出すこと。
  - *根拠*: AIService Protocol の grade_answer シグネチャ（ai_service.py L133-151）
- **REQ-AI-003** 🔵: `language` パラメータはクエリパラメータ `event.queryStringParameters.language` から取得し、デフォルトは `"ja"` とすること。
  - *根拠*: TASK-0060.md L125「language = request.args.get("language", "ja")」、api-endpoints.md

### 5.2 テストケース: AI 採点呼び出し

| TC ID | テスト名 | 条件 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-060-AI-001 | `test_grade_ai_calls_create_ai_service_factory` | 正常リクエスト | `create_ai_service()` が 1 回呼ばれる | 🔵 |
| TC-060-AI-002 | `test_grade_ai_passes_correct_args_to_grade_answer` | `user_answer="東京"`, card.front="日本の首都は？", card.back="東京" | `grade_answer(card_front="日本の首都は？", card_back="東京", user_answer="東京", language="ja")` | 🔵 |
| TC-060-AI-003 | `test_grade_ai_passes_language_param_to_grade_answer` | `queryStringParameters.language = "en"` | `grade_answer(..., language="en")` が呼ばれる | 🔵 |
| TC-060-AI-004 | `test_grade_ai_uses_default_language_ja` | `queryStringParameters` なし | `grade_answer(..., language="ja")` が呼ばれる | 🔵 |

---

## 6. レスポンス構築

### 6.1 設計要件

- **REQ-RES-001** 🔵: 成功時は HTTP 200 を返すこと。
  - *根拠*: api-endpoints.md「レスポンス（成功 200）」
- **REQ-RES-002** 🔵: レスポンスボディは `GradeAnswerResponse` の `model_dump()` 結果であること。
  - *根拠*: api-endpoints.md レスポンス仕様、TASK-0059 の GradeAnswerResponse
- **REQ-RES-003** 🔵: レスポンスに `grade` (0-5), `reasoning`, `card_front`, `card_back`, `grading_info` が含まれること。
  - *根拠*: api-endpoints.md レスポンスフィールド定義
- **REQ-RES-004** 🔵: `grading_info` に `model_used` と `processing_time_ms` が含まれること。
  - *根拠*: api-endpoints.md の grading_info 仕様
- **REQ-RES-005** 🔵: Content-Type ヘッダーは `application/json` であること。
  - *根拠*: 既存ハンドラーの JSON レスポンスパターン

### 6.2 テストケース: 正常系レスポンス

| TC ID | テスト名 | 条件 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-060-RES-001 | `test_grade_ai_success_returns_200` | 正常リクエスト + カード存在 + AI 成功 | HTTP 200 | 🔵 |
| TC-060-RES-002 | `test_grade_ai_success_response_contains_grade` | AI が grade=4 を返す | `response.body.grade == 4` | 🔵 |
| TC-060-RES-003 | `test_grade_ai_success_response_contains_reasoning` | AI が reasoning="Correct" を返す | `response.body.reasoning == "Correct"` | 🔵 |
| TC-060-RES-004 | `test_grade_ai_success_response_contains_card_front_back` | card.front="Q", card.back="A" | `response.body.card_front == "Q"`, `response.body.card_back == "A"` | 🔵 |
| TC-060-RES-005 | `test_grade_ai_success_response_contains_grading_info` | AI が model_used="test-model", processing_time_ms=500 を返す | `response.body.grading_info.model_used == "test-model"` | 🔵 |
| TC-060-RES-006 | `test_grade_ai_success_response_is_json` | 正常リクエスト | Content-Type が `application/json` | 🔵 |
| TC-060-RES-007 | `test_grade_ai_success_full_e2e_flow` | 認証 -> カード取得 -> AI 採点 -> レスポンス返却の一連フロー | 全フィールドが正しく返される | 🔵 |

---

## 7. AI エラーハンドリング

### 7.1 設計要件

- **REQ-ERR-001** 🔵: `AIServiceError` (及びサブクラス) は `_map_ai_error_to_http()` を使用して HTTP レスポンスに変換すること。
  - *根拠*: 既存 `generate_cards` エンドポイントのパターン（handler.py L346-349）、TASK-0056 要件
- **REQ-ERR-002** 🔵: `_map_ai_error_to_http()` の返す `Response` オブジェクトを Lambda レスポンス dict 形式に変換すること。
  - *根拠*: 独立 Lambda は dict 形式のレスポンスが必要
- **REQ-ERR-003** 🔵: `AITimeoutError` → HTTP 504 にマッピングされること。
  - *根拠*: `_map_ai_error_to_http()` の実装（handler.py L74-80）、api-endpoints.md エラーコード
- **REQ-ERR-004** 🔵: `AIRateLimitError` → HTTP 429 にマッピングされること。
  - *根拠*: `_map_ai_error_to_http()` の実装（handler.py L81-86）
- **REQ-ERR-005** 🔵: `AIProviderError` → HTTP 503 にマッピングされること。
  - *根拠*: `_map_ai_error_to_http()` の実装（handler.py L88-93）
- **REQ-ERR-006** 🔵: `AIParseError` → HTTP 500 にマッピングされること。
  - *根拠*: `_map_ai_error_to_http()` の実装（handler.py L95-100）
- **REQ-ERR-007** 🔵: `AIInternalError` / その他の `AIServiceError` → HTTP 500 にマッピングされること。
  - *根拠*: `_map_ai_error_to_http()` の実装（handler.py L102-106）
- **REQ-ERR-008** 🔵: `AIProviderError` (ファクトリー初期化失敗) → HTTP 503 にマッピングされること。`create_ai_service()` 自体が `AIProviderError` を raise する場合。
  - *根拠*: ai_service.py L198「raise AIProviderError」、TC-056-013 のテストパターン
- **REQ-ERR-009** 🔵: 予期しない例外（`Exception`）は HTTP 500 にマッピングし、ログに `exception` レベルで記録すること。
  - *根拠*: TASK-0060.md L181-186「except Exception as e: logger.exception(...)」

### 7.2 テストケース: AI エラーハンドリング

| TC ID | テスト名 | 条件 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-060-ERR-001 | `test_grade_ai_returns_504_on_ai_timeout` | `grade_answer` が `AITimeoutError` を raise | HTTP 504, `{"error": "AI service timeout"}` | 🔵 |
| TC-060-ERR-002 | `test_grade_ai_returns_429_on_ai_rate_limit` | `grade_answer` が `AIRateLimitError` を raise | HTTP 429, `{"error": "AI service rate limit exceeded"}` | 🔵 |
| TC-060-ERR-003 | `test_grade_ai_returns_503_on_ai_provider_error` | `grade_answer` が `AIProviderError` を raise | HTTP 503, `{"error": "AI service unavailable"}` | 🔵 |
| TC-060-ERR-004 | `test_grade_ai_returns_500_on_ai_parse_error` | `grade_answer` が `AIParseError` を raise | HTTP 500, `{"error": "AI service response parse error"}` | 🔵 |
| TC-060-ERR-005 | `test_grade_ai_returns_500_on_ai_internal_error` | `grade_answer` が `AIInternalError` を raise | HTTP 500, `{"error": "AI service error"}` | 🔵 |
| TC-060-ERR-006 | `test_grade_ai_returns_503_on_factory_init_failure` | `create_ai_service()` が `AIProviderError` を raise | HTTP 503, `{"error": "AI service unavailable"}` | 🔵 |
| TC-060-ERR-007 | `test_grade_ai_returns_500_on_unexpected_exception` | `grade_answer` が `RuntimeError` を raise | HTTP 500, `{"error": "Internal Server Error"}` | 🔵 |

---

## 8. ロギング

### 8.1 設計要件

- **REQ-LOG-001** 🔵: 採点リクエスト受信時に `logger.info` で `card_id`, `user_id`, `user_answer_length` を記録すること。
  - *根拠*: TASK-0060.md ロギング仕様 L204-209
- **REQ-LOG-002** 🔵: 採点成功時に `logger.info` で `card_id`, `user_id`, `grade`, `model_used`, `processing_time_ms` を記録すること。
  - *根拠*: TASK-0060.md ロギング仕様、既存 generate_cards の成功ログパターン（handler.py L324-326）
- **REQ-LOG-003** 🔵: AI エラー発生時に `logger.warning` または `logger.error` で記録すること。
  - *根拠*: 既存 generate_cards の AI エラーログパターン（handler.py L348）
- **REQ-LOG-004** 🔵: 予期しない例外発生時に `logger.exception` で記録すること。
  - *根拠*: TASK-0060.md L182「logger.exception(...)」

### 8.2 テストケース: ロギング

| TC ID | テスト名 | 条件 | 期待結果 | 信頼性 |
|-------|---------|------|---------|--------|
| TC-060-LOG-001 | `test_grade_ai_logs_request_info` | 正常リクエスト | `logger.info` が `card_id`, `user_id`, `user_answer_length` を含む引数で呼ばれる | 🔵 |
| TC-060-LOG-002 | `test_grade_ai_logs_success_info` | AI 採点成功 | `logger.info` が `grade` を含む引数で呼ばれる | 🔵 |
| TC-060-LOG-003 | `test_grade_ai_logs_ai_error` | AI エラー発生 | `logger.warning` または `logger.error` が呼ばれる | 🔵 |

---

## 9. template.yaml との整合性

### 9.1 確認要件

- **REQ-CFG-001** 🔵: `ReviewsGradeAiFunction` が template.yaml に定義されており、Handler が `api.handler.grade_ai_handler` であること。
  - *根拠*: TASK-0056 で既に作成済み（TC-056-020 で検証済み）
- **REQ-CFG-002** 🔵: イベントルートが `POST /reviews/{cardId}/grade-ai` であること。
  - *根拠*: TASK-0056 で既に作成済み（TC-056-021 で検証済み）

**備考**: template.yaml の設定検証は TASK-0056 (TC-056-016 ~ TC-056-025) で既にテスト済みのため、TASK-0060 では追加テスト不要。

---

## テストイベント構築ヘルパー

### テスト共通ヘルパー

テストファイル内で以下のヘルパー関数を定義し、テストイベントの構築を簡潔にする。

```python
def _make_grade_ai_event(
    card_id: str = "card-123",
    body: dict | None = None,
    user_id: str = "test-user-id",
    query_params: dict | None = None,
    authorizer: dict | None = None,
) -> dict:
    """grade_ai_handler 用の API Gateway HTTP API v2 イベントを構築する。"""
    if authorizer is None:
        authorizer = {
            "jwt": {
                "claims": {"sub": user_id},
                "scopes": ["openid", "profile"],
            }
        }
    event = {
        "version": "2.0",
        "routeKey": "POST /reviews/{cardId}/grade-ai",
        "rawPath": f"/reviews/{card_id}/grade-ai",
        "rawQueryString": "",
        "body": json.dumps(body) if body is not None else None,
        "pathParameters": {"cardId": card_id},
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api-id",
            "authorizer": authorizer,
            "http": {"method": "POST"},
            "requestId": "test-request-id",
            "routeKey": "POST /reviews/{cardId}/grade-ai",
            "stage": "$default",
        },
        "headers": {"content-type": "application/json"},
        "isBase64Encoded": False,
    }
    if query_params:
        event["queryStringParameters"] = query_params
    return event
```

### モックパターン

```python
@pytest.fixture
def mock_card_service():
    """CardService のモック。card.front / card.back をモック Card で返す。"""
    with patch("api.handler.card_service") as mock:
        mock_card = MagicMock()
        mock_card.front = "日本の首都は？"
        mock_card.back = "東京"
        mock.get_card.return_value = mock_card
        yield mock

@pytest.fixture
def mock_ai_service():
    """create_ai_service のモック。GradingResult を返す。"""
    with patch("api.handler.create_ai_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.grade_answer.return_value = GradingResult(
            grade=4,
            reasoning="Correct with minor hesitation",
            model_used="test-model",
            processing_time_ms=500,
        )
        mock_factory.return_value = mock_service
        yield mock_factory, mock_service
```

---

## テストファイル構成サマリー

### 新規作成ファイル

| ファイル | テストクラス | TC 数 |
|---------|------------|-------|
| `backend/tests/unit/test_handler_grade_ai.py` | `TestGradeAiHandlerAuth` | 3 |
| | `TestGradeAiHandlerPathParams` | 2 |
| | `TestGradeAiHandlerValidation` | 6 |
| | `TestGradeAiHandlerCardErrors` | 3 |
| | `TestGradeAiHandlerAICall` | 4 |
| | `TestGradeAiHandlerSuccess` | 7 |
| | `TestGradeAiHandlerAIErrors` | 7 |
| | `TestGradeAiHandlerLogging` | 3 |

### 実装ファイル修正

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/api/handler.py` | `grade_ai_handler` スタブを本実装に置き換え。必要に応じて `_get_user_id_from_event()` ヘルパーを追加。 |

### テスト合計

| カテゴリ | 件数 |
|---------|------|
| 認証テスト | 3 |
| パスパラメータテスト | 2 |
| バリデーションテスト | 6 |
| カード関連テスト | 3 |
| AI 呼び出しテスト | 4 |
| 正常系レスポンステスト | 7 |
| AI エラーテスト | 7 |
| ロギングテスト | 3 |
| **合計** | **35** |

---

## 既存テストへの影響

### `test_handler_ai_service_factory.py` の `TestStubHandlers`

TASK-0060 完了後、以下の既存テストは**修正が必要**:

- **TC-056-014** (`test_grade_ai_handler_returns_501`): `grade_ai_handler` が 501 ではなく本実装の動作をするようになるため、このテストは削除するか、本実装を検証するテストに置き換える。

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 35 | 100% |
| 🟡 黄信号 | 0 | 0% |
| 🔴 赤信号 | 0 | 0% |

**品質評価**: 高品質（青信号 100%、赤信号なし）

### 信頼性根拠

全テストケースが以下の確定情報に基づいている:
- `api-endpoints.md` の POST /reviews/{card_id}/grade-ai 仕様
- `dataflow.md` の機能2: 回答採点フロー
- 既存 `handler.py` の `generate_cards` / `_map_ai_error_to_http()` パターン
- 既存 `card_service.py` の `get_card()` / `CardNotFoundError` 仕様
- 既存 `ai_service.py` の Protocol / 例外階層定義
- `template.yaml` の `ReviewsGradeAiFunction` 定義
- TASK-0059 で作成済みの `GradeAnswerRequest` / `GradeAnswerResponse` モデル

---

## 依存関係

```
TASK-0056 (AIServiceFactory 統合) ──┐
                                     ├── TASK-0060 (本タスク) ──> TASK-0063 (Phase 3 統合テスト)
TASK-0059 (採点モデル・AI実装) ─────┘
```

---

*作成日*: 2026-02-24
*タスク*: TASK-0060 TDD Requirements Phase
*信頼性*: 🔵 35件 (100%) / 🟡 0件 (0%) / 🔴 0件 (0%)

# TASK-0060: POST /reviews/{card_id}/grade-ai エンドポイント - Tasknote

## タスク概要

TASK-0060 は handler.py の `grade_ai_handler` スタブ関数を本実装に置き換えるタスク。カード取得、AI 採点呼び出し、GradeAnswerResponse 形式でのレスポンス返却の一連のフローを実装する。

**重要な構造的観点**: `grade_ai_handler` は `app` (APIGatewayHttpResolver) 経由のルーティングではなく、**独立した Lambda 関数**として template.yaml に定義されている。つまり `@app.post(...)` デコレータではなく、生の Lambda イベントを直接受け取る関数として実装する。

**実装ファイル**:
1. `backend/src/api/handler.py` - `grade_ai_handler` の本実装（スタブ置き換え）

**テストファイル**:
- `backend/tests/unit/test_handler_grade_ai.py` - 新規テストファイル

---

## 現在のスタブ実装

```python
def grade_ai_handler(event: dict, context: Any) -> dict:
    """POST /reviews/{cardId}/grade-ai のスタブハンドラー。

    TASK-0057 で本実装予定。現在は 501 Not Implemented を返す。
    """
    return {
        "statusCode": 501,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": "Not implemented"}),
    }
```

template.yaml での定義:
```yaml
ReviewsGradeAiFunction:
    Type: AWS::Serverless::Function
    Properties:
      Handler: api.handler.grade_ai_handler
      Timeout: 60
      MemorySize: 512
    Events:
      GradeAi:
        Type: HttpApi
        Properties:
          Path: /reviews/{cardId}/grade-ai
          Method: POST
```

---

## 実装の流れ（TDD）

### Phase 1: TDD Red - テストケース定義

#### テストファイル: `backend/tests/unit/test_handler_grade_ai.py`

**テストカテゴリ**:
- A: 正常系テスト（カード取得 -> AI 採点 -> レスポンス返却）
- B: バリデーションエラーテスト（GradeAnswerRequest）
- C: カード関連エラーテスト（404）
- D: AI エラーハンドリングテスト（504/429/503/500）
- E: 認証エラーテスト（401）
- F: ロギングテスト

### Phase 2: TDD Green - 実装

#### `grade_ai_handler` の本実装

```python
def grade_ai_handler(event: dict, context: Any) -> dict:
    """POST /reviews/{cardId}/grade-ai の Lambda ハンドラー。

    AI を使用してユーザーの回答を採点する。
    独立 Lambda 関数として、API Gateway HttpApi から直接呼び出される。
    """
    # 1. ユーザー認証（JWT claims から user_id 取得）
    # 2. パスパラメータから card_id 取得
    # 3. リクエストボディのパース・バリデーション (GradeAnswerRequest)
    # 4. CardService.get_card(user_id, card_id) でカード取得
    # 5. create_ai_service().grade_answer() で AI 採点
    # 6. GradeAnswerResponse 構築
    # 7. エラーハンドリング (_map_ai_error_to_http パターン)
```

### Phase 3: TDD Refactor - リファクタリング

- テストカバレッジ 80% 以上確認
- ドキュメント・docstring 整備

---

## 重要な実装パターン

### パターン 1: 独立 Lambda ハンドラー（app 不使用）

`grade_ai_handler` は **`app` (APIGatewayHttpResolver) を使用しない**。生の Lambda イベントを受け取り、レスポンス辞書を直接返す。

これは `generate_cards` エンドポイント（`@app.post("/cards/generate")` でルーティング）とは異なるパターン。

**イベント構造（API Gateway HTTP API v2）**:
```python
event = {
    "version": "2.0",
    "routeKey": "POST /reviews/{cardId}/grade-ai",
    "rawPath": "/reviews/card-123/grade-ai",
    "body": '{"user_answer": "東京"}',
    "pathParameters": {"cardId": "card-123"},
    "requestContext": {
        "authorizer": {
            "jwt": {
                "claims": {"sub": "user-123"}
            }
        },
        "http": {"method": "POST"}
    },
    "headers": {"content-type": "application/json"}
}
```

**レスポンス構造**:
```python
{
    "statusCode": 200,
    "headers": {"Content-Type": "application/json"},
    "body": json.dumps({...})
}
```

### パターン 2: ユーザー認証（JWT claims 直接抽出）

`get_user_id_from_context()` は `app.current_event` に依存するため、独立 Lambda では使用できない。代わりに、イベントの `requestContext.authorizer.jwt.claims.sub` から直接 `user_id` を抽出する。

**dev 環境フォールバック**: `get_user_id_from_context()` と同様に、dev 環境では Authorization ヘッダーから JWT を直接デコードするフォールバックが必要。

```python
def _get_user_id_from_event(event: dict) -> str | None:
    """Lambda イベントから user_id を抽出する。"""
    try:
        claims = event.get("requestContext", {}).get("authorizer", {})
        if claims and "jwt" in claims:
            return claims["jwt"]["claims"]["sub"]
        if claims and "claims" in claims:
            return claims["claims"]["sub"]
        if claims and "sub" in claims:
            return claims["sub"]
    except (KeyError, TypeError, AttributeError):
        pass

    # Dev environment fallback
    if os.environ.get("ENVIRONMENT") == "dev":
        auth_header = (event.get("headers") or {}).get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            payload = token.split(".")[1]
            payload += "=" * (4 - len(payload) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(payload))
            return decoded.get("sub")

    return None
```

### パターン 3: カード取得と所有権チェック

`CardService.get_card(user_id, card_id)` は **user_id をパーティションキーとして使用する**ため、他ユーザーのカードにはアクセスできない。カードが見つからない場合は `CardNotFoundError` を raise する。

```python
card = card_service.get_card(user_id, card_id)
# Card オブジェクトは .front と .back 属性を持つ（Pydantic モデル）
card_front = card.front
card_back = card.back
```

**注意**: Card モデルは Pydantic BaseModel のサブクラスであり、`card.front` / `card.back` で直接アクセスする（`card.get("front")` ではない）。TASK-0060.md のサンプルコードでは `card.get("front")` と書かれているが、これは誤り。

### パターン 4: AI サービスファクトリー呼び出し

`generate_cards` エンドポイントと同じパターンで `create_ai_service()` を使用する。

```python
ai_service = create_ai_service()
grading_result = ai_service.grade_answer(
    card_front=card_front,
    card_back=card_back,
    user_answer=request_data.user_answer,
    language=language,  # クエリパラメータまたはデフォルト "ja"
)
```

### パターン 5: エラーハンドリング

既存の `_map_ai_error_to_http()` は `Response` オブジェクトを返すが、独立 Lambda ハンドラーではレスポンス辞書が必要。2 つのアプローチが考えられる:

**アプローチ A**: `_map_ai_error_to_http()` の結果を辞書に変換する
```python
response = _map_ai_error_to_http(e)
return {
    "statusCode": response.status_code,
    "headers": {"Content-Type": "application/json"},
    "body": response.body,
}
```

**アプローチ B**: 独立したエラーマッピングヘルパーを作成する
```python
def _make_error_response(status_code: int, error_message: str) -> dict:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": error_message}),
    }
```

アプローチ A が既存コード再利用の観点から望ましい。

### パターン 6: language パラメータの取得

独立 Lambda では `request.args.get()` が使えない。イベントの `queryStringParameters` から取得する。

```python
query_params = event.get("queryStringParameters") or {}
language = query_params.get("language", "ja")
```

### パターン 7: レスポンス構築

```python
from models.grading import GradeAnswerResponse

response_data = GradeAnswerResponse(
    grade=grading_result.grade,
    reasoning=grading_result.reasoning,
    card_front=card_front,
    card_back=card_back,
    grading_info={
        "model_used": grading_result.model_used,
        "processing_time_ms": grading_result.processing_time_ms,
    },
)

return {
    "statusCode": 200,
    "headers": {"Content-Type": "application/json"},
    "body": json.dumps(response_data.model_dump()),
}
```

---

## card_id の取得方法

template.yaml の API ルートは `/reviews/{cardId}/grade-ai` と定義されている。pathParameters のキーは `cardId`（camelCase）。

```python
card_id = (event.get("pathParameters") or {}).get("cardId")
if not card_id:
    return _make_error_response(400, "card_id is required")
```

---

## 依存関係の整理

### 使用するモジュール/関数

| モジュール | 関数/クラス | 用途 |
|-----------|------------|------|
| `models.grading` | `GradeAnswerRequest` | リクエストバリデーション |
| `models.grading` | `GradeAnswerResponse` | レスポンス構築 |
| `services.card_service` | `CardService`, `CardNotFoundError` | カード取得 |
| `services.ai_service` | `create_ai_service` | AI サービスファクトリー |
| `services.ai_service` | `AIServiceError` 階層 | エラーハンドリング |
| `api.handler` | `_map_ai_error_to_http()` | AI エラーの HTTP マッピング |
| `aws_lambda_powertools` | `Logger` | ロギング |
| `pydantic` | `ValidationError` | バリデーションエラー捕捉 |

### CardService の初期化

`grade_ai_handler` は独立 Lambda 関数のため、ハンドラーモジュールのグローバル変数 `card_service = CardService()` をそのまま使用できる。モジュールレベルで既に初期化されている。

---

## テスト戦略

### テストイベント作成パターン

既存の `conftest.py` の `api_gateway_event` フィクスチャは `app.resolve()` 経由のテスト用。独立 Lambda の場合はイベントを直接構築して `grade_ai_handler(event, context)` を呼び出す。

```python
def _make_grade_ai_event(
    card_id: str = "card-123",
    body: dict | None = None,
    user_id: str = "test-user-id",
    query_params: dict | None = None,
) -> dict:
    event = {
        "version": "2.0",
        "routeKey": "POST /reviews/{cardId}/grade-ai",
        "rawPath": f"/reviews/{card_id}/grade-ai",
        "body": json.dumps(body) if body else None,
        "pathParameters": {"cardId": card_id},
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {"sub": user_id}
                }
            },
            "http": {"method": "POST"},
        },
        "headers": {"content-type": "application/json"},
    }
    if query_params:
        event["queryStringParameters"] = query_params
    return event
```

### モック戦略

| 対象 | モック方法 |
|------|----------|
| CardService.get_card | `patch("api.handler.card_service.get_card")` |
| create_ai_service | `patch("api.handler.create_ai_service")` |
| Logger | ログ内容検証時のみ `patch("api.handler.logger")` |

---

## ロギング仕様

全リクエストで以下を構造化ログ出力:

| フィールド | タイミング | 説明 |
|-----------|----------|------|
| `user_id` | 常時 | ユーザー ID |
| `card_id` | 常時 | カード ID |
| `user_answer_length` | 採点前 | 回答の文字数 |
| `grade` | 成功時 | AI 採点結果 (0-5) |
| `processing_time_ms` | 成功時 | AI 処理時間 |
| `model_used` | 成功時 | 使用 AI モデル名 |

---

## エラーコードまとめ

| HTTP Status | 条件 | レスポンスボディ |
|-------------|------|----------------|
| 200 | 正常系 | `GradeAnswerResponse` |
| 400 | ValidationError / body パース失敗 / card_id 欠損 | `{"error": "..."}` |
| 401 | JWT から user_id 取得不可 | `{"error": "Unauthorized"}` |
| 404 | CardNotFoundError | `{"error": "Not Found"}` |
| 429 | AIRateLimitError | `{"error": "AI service rate limit exceeded"}` |
| 500 | AIParseError / AIInternalError | `{"error": "AI service ..."}` |
| 503 | AIProviderError | `{"error": "AI service unavailable"}` |
| 504 | AITimeoutError | `{"error": "AI service timeout"}` |

---

## 注意事項と制約

### 1. 独立 Lambda vs app ルーティング

`grade_ai_handler` は `app.resolve()` を経由しない。`@app.post(...)` デコレータは使用しない。生の Lambda イベント・レスポンスで実装する。

### 2. Card モデルは Pydantic BaseModel

`card.front` / `card.back` でアクセスする。`card.get("front")` ではない。

### 3. 全メソッドは同期

`async def` は使用しない。`create_ai_service().grade_answer()` は同期呼び出し。

### 4. pathParameters のキー名

template.yaml で `/reviews/{cardId}/grade-ai` と定義されているため、キーは **`cardId`**（camelCase）。

### 5. 既存の _map_ai_error_to_http() の再利用

`_map_ai_error_to_http()` は `Response` オブジェクトを返す。独立 Lambda のレスポンス形式（dict）に変換する必要がある。

### 6. dev 環境での JWT フォールバック

SAM local ではJWT Authorizer が動作しないため、`get_user_id_from_context()` と同等の dev 環境フォールバックが必要。

---

## ファイル構造と依存関係

### 修正ファイル

```
backend/src/api/handler.py
├── grade_ai_handler() - 【スタブ → 本実装に置き換え】
└── (必要に応じて) _get_user_id_from_event() - 【新規追加ヘルパー】
```

### 新規テストファイル

```
backend/tests/unit/test_handler_grade_ai.py
├── TestGradeAiHandlerSuccess (正常系)
├── TestGradeAiHandlerValidation (バリデーション)
├── TestGradeAiHandlerCardErrors (カード関連)
├── TestGradeAiHandlerAIErrors (AI エラー)
├── TestGradeAiHandlerAuth (認証)
└── TestGradeAiHandlerLogging (ロギング)
```

---

## 完了基準

1. [ ] POST /reviews/{card_id}/grade-ai がリクエストを受け付ける
2. [ ] カードの存在確認とユーザー認可チェックが動作する
3. [ ] AI 採点結果が GradeAnswerResponse 形式で返却される
4. [ ] 全エラーコードが正しい HTTP ステータスにマッピングされている
5. [ ] テストカバレッジ 80% 以上

---

## 参考リソース

### 設計文書
- `docs/design/ai-strands-migration/api-endpoints.md` - POST /reviews/{card_id}/grade-ai 仕様
- `docs/design/ai-strands-migration/dataflow.md` - 機能2: 回答採点フロー
- `docs/tasks/ai-strands-migration/TASK-0060.md` - タスク定義

### 既存実装の参照
- `backend/src/api/handler.py` - generate_cards() パターン、_map_ai_error_to_http()
- `backend/src/models/grading.py` - GradeAnswerRequest/Response (TASK-0059)
- `backend/src/services/ai_service.py` - create_ai_service()、GradingResult
- `backend/src/services/card_service.py` - CardService.get_card()、CardNotFoundError
- `backend/tests/unit/test_handler_ai_service_factory.py` - 既存ハンドラーテストパターン
- `backend/tests/conftest.py` - api_gateway_event フィクスチャ、lambda_context フィクスチャ

### 依存タスク
- TASK-0056: handler.py AIServiceFactory 統合 + template.yaml 更新（`_map_ai_error_to_http()` 等）
- TASK-0059: 回答採点モデル・プロンプト・AI実装（GradeAnswerRequest/Response、grade_answer()）

### 後続タスク
- TASK-0063: Phase 3 統合テスト

---

**タスク作成日**: 2026-02-24
**タスク期限**: Phase 3 完了前
**推定工数**: 8 時間
**関連者**: Backend Team

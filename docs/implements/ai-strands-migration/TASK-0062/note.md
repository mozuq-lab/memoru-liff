# TASK-0062: 学習アドバイス AI 実装 + GET /advice エンドポイント - Tasknote

## タスク概要

TASK-0062 は以下の 3 つのコンポーネントを実装するタスク:

1. **StrandsAIService.get_learning_advice()**: 現在の `NotImplementedError` スタブを本実装に置き換え
2. **BedrockAIService.get_learning_advice()**: 既に実装済み（bedrock.py L220-267）- テスト追加のみ
3. **advice_handler Lambda**: 現在の 501 スタブを本実装に置き換え

**重要な構造的観点**: `advice_handler` は `grade_ai_handler` と同様に `app` (APIGatewayHttpResolver) 経由のルーティングではなく、**独立した Lambda 関数**として template.yaml に定義されている。

**実装ファイル**:
1. `backend/src/services/strands_service.py` - `get_learning_advice()` の本実装
2. `backend/src/api/handler.py` - `advice_handler` の本実装（スタブ置き換え）

**テストファイル**:
- `backend/tests/unit/test_strands_service.py` - get_learning_advice テスト追加
- `backend/tests/unit/test_bedrock.py` - get_learning_advice テスト追加
- `backend/tests/unit/test_handler_advice.py` - 新規テストファイル

---

## タスクファイルと実際のコードベースの乖離

### 乖離 1: async vs sync

**タスクファイル**: `async def get_learning_advice(...)` + `asyncio.wait_for(...)` を使用
**実際のコードベース**: **全 AI サービスメソッドは同期 (sync)**。`generate_cards()`, `grade_answer()` いずれも `def` (not `async def`)。`asyncio` は一切使用されていない。

**結論**: 同期メソッドとして実装する。

### 乖離 2: BedrockAIService は既に実装済み

**タスクファイル**: BedrockAIService の `get_learning_advice()` も新規実装が必要かのように記載
**実際のコードベース**: `bedrock.py` L220-267 で `get_learning_advice()` は**既に完全に実装されている**。`_parse_json_response()` を使用し、`_invoke_with_retry()` でリトライ付きの Bedrock 呼び出しを行っている。

**結論**: BedrockAIService はテスト追加のみ。実装変更は不要。

### 乖離 3: handler.py のルーティング方式

**タスクファイル**: `@app.get("/advice")` デコレータでルーティングする Flask 風コードを示している
**実際のコードベース**: `advice_handler` は `grade_ai_handler` と同じ**独立 Lambda 関数**。template.yaml で `Handler: api.handler.advice_handler` として定義。生の API Gateway HTTP API v2 イベントを直接受け取る。

**結論**: `grade_ai_handler` と同じパターンで実装する。

### 乖離 4: review_summary の型

**タスクファイル**: `ReviewSummary` オブジェクトを直接渡す記述
**実際のコードベース**: `AIService` Protocol の `get_learning_advice()` は `review_summary: dict` を受け取る。`get_advice_prompt()` も `Union[dict, ReviewSummary]` を受け取る。BedrockService の実装済み `get_learning_advice()` も `review_summary: dict` を受け取る。

**結論**: `review_summary: dict` として受け取る。handler 側で `ReviewSummary` の `__dict__` 属性または `dataclasses.asdict()` で dict に変換して渡す。

### 乖離 5: エラーハンドリング

**タスクファイル**: `asyncio.TimeoutError`, `json.JSONDecodeError` を直接捕捉
**実際のコードベース**: StrandsAIService は `TimeoutError`, `ConnectionError`, `RuntimeError` 等を `AITimeoutError`, `AIProviderError`, `AIServiceError` にマッピングする共通パターンを使用。BedrockService は `_invoke_with_retry()` が例外変換を行う。

**結論**: 既存のエラーマッピングパターンに従う。

### 乖離 6: StrandsAIService の Agent 呼び出し方式

**タスクファイル**: `self.client.agents.create(name=..., system_prompt=...)` + `await self._invoke_agent(agent, prompt)` を使用
**実際のコードベース**: StrandsAIService は `Agent(model=self.model)` でインスタンスを作成し、`agent(prompt)` で同期呼び出し。`self.client` は存在しない。

**結論**: 既存の `generate_cards()` / `grade_answer()` と同じ Agent 呼び出しパターンを使用。

---

## 現在のスタブ実装

### StrandsAIService.get_learning_advice() (strands_service.py L384-400)

```python
def get_learning_advice(
    self,
    review_summary: dict,
    language: Language = "ja",
) -> LearningAdvice:
    """学習アドバイスを取得する（Phase 3 で実装予定のスタブ）."""
    raise NotImplementedError(
        "get_learning_advice is not implemented yet (Phase 3)"
    )
```

### BedrockService.get_learning_advice() (bedrock.py L220-267) - 実装済み

```python
def get_learning_advice(
    self,
    review_summary: dict,
    language: Language = "ja",
) -> LearningAdvice:
    start_time = time.time()
    prompt = get_advice_prompt(review_summary=review_summary, language=language)
    response_text = self._invoke_with_retry(prompt)
    data = self._parse_json_response(
        response_text,
        required_fields=["advice_text", "weak_areas", "recommendations"],
        context="advice",
    )
    advice_text = str(data["advice_text"])
    weak_areas = list(data["weak_areas"])
    recommendations = list(data["recommendations"])
    processing_time_ms = int((time.time() - start_time) * 1000)
    return LearningAdvice(
        advice_text=advice_text,
        weak_areas=weak_areas,
        recommendations=recommendations,
        model_used=self.model_id,
        processing_time_ms=processing_time_ms,
    )
```

### advice_handler (handler.py L746-755)

```python
def advice_handler(event: dict, context: Any) -> dict:
    """GET /advice のスタブハンドラー。

    TASK-0061 で本実装予定。現在は 501 Not Implemented を返す。
    """
    return {
        "statusCode": 501,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": "Not implemented"}),
    }
```

### template.yaml 定義

```yaml
AdviceFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: !Sub memoru-advice-${Environment}
      CodeUri: src/
      Handler: api.handler.advice_handler
      Description: AI learning advice handler for GET /advice
      Timeout: 60
      MemorySize: 512
    Events:
      Advice:
        Type: HttpApi
        Properties:
          ApiId: !Ref HttpApi
          Path: /advice
          Method: GET
```

---

## 実装の流れ（TDD）

### Phase 1: TDD Red - テストケース定義

#### テストファイル A: `backend/tests/unit/test_strands_service.py` (追加)

TestStrandsAdvice クラスを追加:
- 正常系テスト（LearningAdvice が返る）
- プロンプト引数伝搬テスト
- language パラメータテスト
- パースエラーテスト（不正 JSON、必須フィールド欠損）
- エラーハンドリングテスト（タイムアウト、レート制限、接続エラー、未知例外）
- メタデータテスト（model_used, processing_time_ms）

#### テストファイル B: `backend/tests/unit/test_bedrock.py` (追加)

TestBedrockGetLearningAdvice クラスを追加:
- 正常系テスト（LearningAdvice が返る）
- Markdown コードブロック JSON テスト
- プロンプト引数伝搬テスト
- パースエラーテスト（不正 JSON、必須フィールド欠損）
- API エラーテスト（タイムアウト、レート制限、内部エラー）
- メタデータテスト（model_used, processing_time_ms）

#### テストファイル C: `backend/tests/unit/test_handler_advice.py` (新規)

grade_ai_handler のテストパターンに準拠:
- A: 認証テスト（JWT 抽出、401 エラー）
- B: 正常系テスト（ReviewSummary -> AI -> レスポンス）
- C: AI エラーハンドリングテスト（504/429/503/500）
- D: DB エラーテスト
- E: ロギングテスト

### Phase 2: TDD Green - 実装

#### StrandsAIService.get_learning_advice() の本実装

```python
def get_learning_advice(
    self,
    review_summary: dict,
    language: Language = "ja",
) -> LearningAdvice:
    start_time = time.time()
    try:
        prompt = get_advice_prompt(review_summary=review_summary, language=language)
        agent = Agent(model=self.model)
        response = agent(prompt)
        response_text = str(response)
        advice_text, weak_areas, recommendations = self._parse_advice_result(response_text)
        processing_time_ms = int((time.time() - start_time) * 1000)
        return LearningAdvice(
            advice_text=advice_text,
            weak_areas=weak_areas,
            recommendations=recommendations,
            model_used=self.model_used,
            processing_time_ms=processing_time_ms,
        )
    except AIServiceError:
        raise
    except TimeoutError as e:
        raise AITimeoutError(f"Agent timed out: {e}") from e
    except ConnectionError as e:
        raise AIProviderError(f"Provider connection error: {e}") from e
    except Exception as e:
        # ... 既存エラーマッピングパターン
```

#### advice_handler の本実装

```python
def advice_handler(event: dict, context: Any) -> dict:
    """GET /advice の Lambda ハンドラー。"""
    try:
        # 1. ユーザー認証（JWT claims から user_id 取得）
        user_id = _get_user_id_from_event(event)
        if not user_id:
            return _make_lambda_response(401, {"error": "Unauthorized"})

        # 2. クエリパラメータから language 取得
        language = (event.get("queryStringParameters") or {}).get("language", "ja")

        # 3. ReviewService.get_review_summary() でデータ集計
        summary = review_service.get_review_summary(user_id)

        # 4. dataclasses.asdict() で dict に変換
        import dataclasses
        summary_dict = dataclasses.asdict(summary)

        # 5. AI サービスで学習アドバイス生成
        ai_service = create_ai_service()
        result = ai_service.get_learning_advice(
            review_summary=summary_dict,
            language=language,
        )

        # 6. LearningAdviceResponse 構築
        response = LearningAdviceResponse(
            advice_text=result.advice_text,
            weak_areas=result.weak_areas,
            recommendations=result.recommendations,
            study_stats={
                "total_reviews": summary.total_reviews,
                "average_grade": summary.average_grade,
                "total_cards": summary.total_cards,
                "cards_due_today": summary.cards_due_today,
                "streak_days": summary.streak_days,
            },
            advice_info={
                "model_used": result.model_used,
                "processing_time_ms": result.processing_time_ms,
            },
        )
        return _make_lambda_response(200, response.model_dump(mode="json"))

    except AIServiceError as e:
        ai_response = _map_ai_error_to_http(e)
        return {
            "statusCode": ai_response.status_code,
            "headers": {"Content-Type": "application/json"},
            "body": ai_response.body,
        }
    except Exception as e:
        return _make_lambda_response(500, {"error": "Internal Server Error"})
```

---

## 重要な実装パターン

### パターン 1: 独立 Lambda ハンドラー（grade_ai_handler と同一パターン）

`advice_handler` は `grade_ai_handler` と同様に:
- `app` (APIGatewayHttpResolver) を使用しない
- 生の Lambda イベントを受け取り、レスポンス辞書を直接返す
- `_get_user_id_from_event()` で JWT claims からユーザー ID を取得
- `_make_lambda_response()` でレスポンスを構築
- `_map_ai_error_to_http()` の結果を dict 形式に変換

### パターン 2: ReviewSummary を dict に変換して AI サービスに渡す

```python
import dataclasses
summary = review_service.get_review_summary(user_id)  # ReviewSummary dataclass
summary_dict = dataclasses.asdict(summary)  # dict に変換
result = ai_service.get_learning_advice(review_summary=summary_dict, language=language)
```

`get_advice_prompt()` は `Union[dict, ReviewSummary]` を受け取るため、dict でも ReviewSummary でも動作する。ただし、AIService Protocol は `review_summary: dict` を定義しているため、dict で渡すのが正しい。

### パターン 3: StrandsAIService のエラーマッピング

`generate_cards()` / `grade_answer()` と同一のエラーマッピングパターンを使用:

```python
except AIServiceError:
    raise  # 既にマッピング済み
except TimeoutError as e:
    raise AITimeoutError(f"Agent timed out: {e}") from e
except ConnectionError as e:
    raise AIProviderError(f"Provider connection error: {e}") from e
except Exception as e:
    error_str = str(e)
    if _is_rate_limit_error(e):
        raise AIRateLimitError(f"Rate limit exceeded: {e}") from e
    if "timeout" in error_str.lower() or "timed out" in error_str.lower():
        raise AITimeoutError(f"Agent timed out: {e}") from e
    if "connection" in error_str.lower() or "connect" in type(e).__name__.lower():
        raise AIProviderError(f"Provider connection error: {e}") from e
    raise AIServiceError(f"Unexpected error: {e}") from e
```

### パターン 4: StrandsAIService の JSON パース

`_parse_grading_result()` と同様に、Markdown コードブロックとプレーン JSON の両方に対応するパーサーを作成:

```python
def _parse_advice_result(self, response_text: str) -> tuple[str, list, list]:
    try:
        json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response_text)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_str = response_text.strip()
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise AIParseError(f"Failed to parse JSON response: {e}") from e

    if "advice_text" not in data:
        raise AIParseError("Response missing required 'advice_text' field.")
    if "weak_areas" not in data:
        raise AIParseError("Response missing required 'weak_areas' field.")
    if "recommendations" not in data:
        raise AIParseError("Response missing required 'recommendations' field.")

    return str(data["advice_text"]), list(data["weak_areas"]), list(data["recommendations"])
```

### パターン 5: advice_handler の AI エラー → Lambda レスポンス変換

`grade_ai_handler` と同一パターン:

```python
except AIServiceError as e:
    logger.warning(f"AI service error: {type(e).__name__}: {e}")
    ai_response = _map_ai_error_to_http(e)
    return {
        "statusCode": ai_response.status_code,
        "headers": {"Content-Type": "application/json"},
        "body": ai_response.body,
    }
```

### パターン 6: GET リクエストのため body パースは不要

`grade_ai_handler` は POST で `GradeAnswerRequest` のバリデーションが必要だったが、`advice_handler` は GET リクエストのため:
- リクエストボディのパースは不要
- クエリパラメータ `language` のみ取得
- `GradeAnswerRequest` のような Pydantic バリデーションは不要

---

## 依存関係の整理

### 使用するモジュール/関数

| モジュール | 関数/クラス | 用途 |
|-----------|------------|------|
| `models.advice` | `LearningAdviceResponse` | レスポンス構築 |
| `services.review_service` | `ReviewService`, `review_service` | 学習データ集計 |
| `services.ai_service` | `create_ai_service` | AI サービスファクトリー |
| `services.ai_service` | `AIServiceError` 階層 | エラーハンドリング |
| `services.ai_service` | `LearningAdvice` | AI 結果 dataclass |
| `services.ai_service` | `ReviewSummary` | 集計結果 dataclass |
| `services.prompts.advice` | `get_advice_prompt` | プロンプト生成 |
| `api.handler` | `_get_user_id_from_event()` | JWT 認証 |
| `api.handler` | `_make_lambda_response()` | レスポンス構築 |
| `api.handler` | `_map_ai_error_to_http()` | AI エラーの HTTP マッピング |
| `aws_lambda_powertools` | `Logger` | ロギング |
| `dataclasses` | `asdict` | ReviewSummary -> dict 変換 |

### グローバル変数

handler.py のモジュールレベルで既に初期化されている:
- `review_service = ReviewService()` (L59)
- `logger = Logger()` (L52)

---

## エラーコードまとめ

| HTTP Status | 条件 | レスポンスボディ |
|-------------|------|----------------|
| 200 | 正常系 | `LearningAdviceResponse` |
| 401 | JWT から user_id 取得不可 | `{"error": "Unauthorized"}` |
| 429 | AIRateLimitError | `{"error": "AI service rate limit exceeded"}` |
| 500 | AIParseError / AIInternalError / 予期しない例外 | `{"error": "..."}` |
| 503 | AIProviderError | `{"error": "AI service unavailable"}` |
| 504 | AITimeoutError | `{"error": "AI service timeout"}` |

---

## ロギング仕様

| フィールド | タイミング | 説明 |
|-----------|----------|------|
| `user_id` | 常時 | ユーザー ID |
| `language` | 常時 | 指定言語 |
| `total_reviews` | 成功時 | 総復習回数 |
| `weak_areas_count` | 成功時 | 弱点分野の数 |
| `recommendations_count` | 成功時 | 推奨アクションの数 |
| `model_used` | 成功時 | 使用 AI モデル名 |
| `processing_time_ms` | 成功時 | AI 処理時間 |

---

## テスト戦略

### 既存テストへの影響

#### `test_strands_service.py` の `TestStrandsServiceStubs`

TASK-0062 完了後、以下の既存テストは**修正が必要**:
- **TC-STUB-002** (`test_get_learning_advice_raises_not_implemented`): `get_learning_advice()` が本実装されるため削除
- **TC-STUB-003** (`test_not_implemented_error_message_contains_phase3`): 同上、削除

#### `test_handler_ai_service_factory.py` のスタブテスト

TASK-0060 完了時と同様に、`advice_handler` の 501 スタブテストがあれば削除が必要。

### テストイベント構築パターン

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

### モック戦略

| 対象 | モック方法 |
|------|----------|
| ReviewService.get_review_summary | `patch("api.handler.review_service")` |
| create_ai_service | `patch("api.handler.create_ai_service")` |
| Logger | ログ内容検証時のみ `patch("api.handler.logger")` |

---

## 注意事項と制約

### 1. BedrockService.get_learning_advice() は既に実装済み

テスト追加のみ。実装コードの変更は不要。

### 2. 全メソッドは同期

`async def` は使用しない。`create_ai_service().get_learning_advice()` は同期呼び出し。

### 3. GET リクエストのため body パースは不要

`advice_handler` はクエリパラメータ `language` のみ受け取る。

### 4. ReviewSummary の dict 変換

`AIService.get_learning_advice(review_summary: dict)` は dict を受け取る。`ReviewSummary` dataclass は `dataclasses.asdict()` で変換する。

### 5. review_service.get_review_summary() のエラーハンドリング

`get_review_summary()` は内部で `ClientError` を捕捉し、エラー時はデフォルト値（全ゼロ）の `ReviewSummary` を返す。つまり、DB エラーでも例外は送出されず、空のサマリーに基づくアドバイスが生成される。

ただし、`review_service` 自体の初期化失敗（テーブル不存在等）による例外は handler の `except Exception` で捕捉する。

### 6. StrandsAIService の import 追加

`get_advice_prompt` を import する必要がある:
```python
from services.prompts import get_advice_prompt
```

---

## 参考リソース

### 設計文書
- `docs/design/ai-strands-migration/api-endpoints.md` - GET /advice 仕様
- `docs/design/ai-strands-migration/dataflow.md` - 機能3: 学習アドバイスフロー
- `docs/tasks/ai-strands-migration/TASK-0062.md` - タスク定義

### 既存実装の参照
- `backend/src/api/handler.py` - grade_ai_handler パターン、_map_ai_error_to_http()、_get_user_id_from_event()、_make_lambda_response()
- `backend/src/services/bedrock.py` - get_learning_advice() 実装済み (L220-267)
- `backend/src/services/strands_service.py` - generate_cards(), grade_answer() パターン
- `backend/src/services/ai_service.py` - Protocol, LearningAdvice, ReviewSummary, create_ai_service()
- `backend/src/models/advice.py` - LearningAdviceResponse Pydantic モデル
- `backend/src/services/review_service.py` - get_review_summary() (L342-438)
- `backend/src/services/prompts/advice.py` - get_advice_prompt(), ADVICE_SYSTEM_PROMPT
- `backend/tests/unit/test_handler_grade_ai.py` - handler テストパターン
- `backend/tests/unit/test_strands_service.py` - StrandsAIService テストパターン
- `backend/tests/unit/test_bedrock.py` - BedrockService テストパターン
- `backend/tests/conftest.py` - lambda_context フィクスチャ

### 依存タスク
- TASK-0056: CardService / ReviewService 実装
- TASK-0061: 学習データ集計 + アドバイスモデル・プロンプト（ReviewSummary, LearningAdviceResponse, get_advice_prompt）

### 後続タスク
- TASK-0063: Phase 3 統合テスト

---

**タスク作成日**: 2026-02-24
**推定工数**: 8 時間

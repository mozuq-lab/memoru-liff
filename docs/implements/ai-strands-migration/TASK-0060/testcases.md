# TASK-0060: POST /reviews/{card_id}/grade-ai エンドポイント - Test Cases

## 概要

`grade_ai_handler` Lambda ハンドラーの本実装に対するテストケース定義。

**テストファイル**: `backend/tests/unit/test_handler_grade_ai.py`（新規作成）

---

## 構造的前提（CRITICAL）

`grade_ai_handler` は `app` (APIGatewayHttpResolver) を経由しない**独立 Lambda 関数**である。

- `@app.post(...)` デコレータは使用しない
- 生の API Gateway HTTP API v2 イベントを直接受け取る
- レスポンスは Lambda プロキシ統合形式の dict（`statusCode`, `headers`, `body`）
- `pathParameters` のキーは `cardId`（camelCase、template.yaml の `/reviews/{cardId}/grade-ai` に対応）
- `queryStringParameters` から `language` を取得（`request.args` ではない）
- Card は Pydantic BaseModel であり `.front` / `.back` で直接アクセス（`.get("front")` ではない）
- ユーザー認証は `event.requestContext.authorizer.jwt.claims.sub` から直接抽出
- `_map_ai_error_to_http()` は `Response` オブジェクトを返すため、独立 Lambda 用に dict 変換が必要

---

## テスト共通ヘルパー

### イベント構築ヘルパー

```python
import json
from unittest.mock import patch, MagicMock

import pytest

from services.ai_service import (
    GradingResult,
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIInternalError,
    AIParseError,
    AIProviderError,
)
from services.card_service import CardNotFoundError


def _make_grade_ai_event(
    card_id: str = "card-123",
    body: dict | None = None,
    user_id: str = "test-user-id",
    query_params: dict | None = None,
    authorizer: dict | None = None,
) -> dict:
    """grade_ai_handler 用の API Gateway HTTP API v2 イベントを構築する。"""
    if body is None:
        body = {"user_answer": "東京"}
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

### モックフィクスチャ

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
            reasoning="Correct answer with good understanding",
            model_used="test-model",
            processing_time_ms=500,
        )
        mock_factory.return_value = mock_service
        yield mock_factory, mock_service
```

---

## テストカテゴリ A: 認証テスト（TestGradeAiHandlerAuth）

### TC-060-AUTH-001: `test_grade_ai_returns_401_when_no_authorizer` 🔵

- **目的**: authorizer が空の場合に HTTP 401 を返すことを確認
- **入力**: `requestContext.authorizer` が空辞書 `{}`
- **期待結果**: `statusCode == 401`, `body == {"error": "Unauthorized"}`
- **信頼性**: 🔵 青信号 - `get_user_id_from_context()` の既存パターン（handler.py L110-148）、api-endpoints.md 認証仕様
- **モック**: `mock_card_service`, `mock_ai_service`（呼ばれないが安全のため）
- **検証方法**:
  ```python
  event = _make_grade_ai_event(authorizer={})
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 401
  body = json.loads(response["body"])
  assert body["error"] == "Unauthorized"
  ```

### TC-060-AUTH-002: `test_grade_ai_returns_401_when_no_sub_claim` 🔵

- **目的**: JWT claims に `sub` がない場合に HTTP 401 を返すことを確認
- **入力**: `authorizer.jwt.claims` に `sub` キーなし（`{"jwt": {"claims": {"iss": "test"}}}`）
- **期待結果**: `statusCode == 401`, `body == {"error": "Unauthorized"}`
- **信頼性**: 🔵 青信号 - JWT claims 構造は API Gateway HTTP API v2 仕様で確定
- **検証方法**:
  ```python
  event = _make_grade_ai_event(authorizer={"jwt": {"claims": {"iss": "test"}}})
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 401
  ```

### TC-060-AUTH-003: `test_grade_ai_extracts_user_id_from_jwt_claims` 🔵

- **目的**: `authorizer.jwt.claims.sub` から `user_id` を正しく抽出し、CardService に渡すことを確認
- **入力**: `authorizer.jwt.claims.sub = "user-abc-123"`
- **期待結果**: `card_service.get_card` が `user_id="user-abc-123"` で呼ばれる
- **信頼性**: 🔵 青信号 - 既存 `get_user_id_from_context()` の HTTP API パス（handler.py L122-123）
- **モック**: `mock_card_service`, `mock_ai_service`
- **検証方法**:
  ```python
  event = _make_grade_ai_event(user_id="user-abc-123")
  response = grade_ai_handler(event, lambda_context)
  mock_card_service.get_card.assert_called_once_with("user-abc-123", "card-123")
  ```

---

## テストカテゴリ B: パスパラメータテスト（TestGradeAiHandlerPathParams）

### TC-060-PATH-001: `test_grade_ai_extracts_card_id_from_path_params` 🔵

- **目的**: `pathParameters.cardId` から `card_id` を正しく取得し、CardService に渡すことを確認
- **入力**: `pathParameters.cardId = "card-xyz-789"`
- **期待結果**: `card_service.get_card` が `card_id="card-xyz-789"` で呼ばれる
- **信頼性**: 🔵 青信号 - template.yaml `/reviews/{cardId}/grade-ai` のキー名は camelCase で確定
- **モック**: `mock_card_service`, `mock_ai_service`
- **検証方法**:
  ```python
  event = _make_grade_ai_event(card_id="card-xyz-789")
  response = grade_ai_handler(event, lambda_context)
  mock_card_service.get_card.assert_called_once_with("test-user-id", "card-xyz-789")
  ```

### TC-060-PATH-002: `test_grade_ai_returns_400_when_card_id_missing` 🔵

- **目的**: `pathParameters` が null の場合に HTTP 400 を返すことを確認
- **入力**: `event["pathParameters"] = None`
- **期待結果**: `statusCode == 400`
- **信頼性**: 🔵 青信号 - 防御的プログラミング、api-endpoints.md バリデーションエラー 400
- **検証方法**:
  ```python
  event = _make_grade_ai_event()
  event["pathParameters"] = None
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 400
  ```

---

## テストカテゴリ C: リクエストバリデーションテスト（TestGradeAiHandlerValidation）

### TC-060-VAL-001: `test_grade_ai_returns_400_when_body_is_null` 🔵

- **目的**: `event.body` が null の場合に HTTP 400 を返すことを確認
- **入力**: `event["body"] = None`
- **期待結果**: `statusCode == 400`
- **信頼性**: 🔵 青信号 - 既存 handler.py の `json.JSONDecodeError` ハンドリングパターン（L307-312）
- **モック**: `mock_card_service`, `mock_ai_service`（呼ばれないことも検証可）
- **検証方法**:
  ```python
  event = _make_grade_ai_event()
  event["body"] = None
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 400
  ```

### TC-060-VAL-002: `test_grade_ai_returns_400_when_body_is_invalid_json` 🔵

- **目的**: `event.body` が不正な JSON の場合に HTTP 400 を返すことを確認
- **入力**: `event["body"] = "not json"`
- **期待結果**: `statusCode == 400`
- **信頼性**: 🔵 青信号 - 既存 handler.py の json.JSONDecodeError パターン
- **検証方法**:
  ```python
  event = _make_grade_ai_event()
  event["body"] = "not json"
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 400
  ```

### TC-060-VAL-003: `test_grade_ai_returns_400_when_user_answer_empty` 🔵

- **目的**: `user_answer` が空文字列の場合に HTTP 400 を返すことを確認
- **入力**: `{"user_answer": ""}`
- **期待結果**: `statusCode == 400`
- **信頼性**: 🔵 青信号 - GradeAnswerRequest の `min_length=1` 制約（grading.py L17）
- **検証方法**:
  ```python
  event = _make_grade_ai_event(body={"user_answer": ""})
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 400
  ```

### TC-060-VAL-004: `test_grade_ai_returns_400_when_user_answer_whitespace_only` 🔵

- **目的**: `user_answer` が空白のみの場合に HTTP 400 を返すことを確認
- **入力**: `{"user_answer": "   "}`
- **期待結果**: `statusCode == 400`
- **信頼性**: 🔵 青信号 - GradeAnswerRequest の `validate_user_answer` バリデータ（grading.py L23-28）
- **検証方法**:
  ```python
  event = _make_grade_ai_event(body={"user_answer": "   "})
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 400
  ```

### TC-060-VAL-005: `test_grade_ai_returns_400_when_user_answer_too_long` 🔵

- **目的**: `user_answer` が 2000 文字超の場合に HTTP 400 を返すことを確認
- **入力**: `{"user_answer": "a" * 2001}`
- **期待結果**: `statusCode == 400`
- **信頼性**: 🔵 青信号 - GradeAnswerRequest の `max_length=2000` 制約（grading.py L18）
- **検証方法**:
  ```python
  event = _make_grade_ai_event(body={"user_answer": "a" * 2001})
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 400
  ```

### TC-060-VAL-006: `test_grade_ai_returns_400_when_user_answer_missing` 🔵

- **目的**: `user_answer` フィールドが未指定の場合に HTTP 400 を返すことを確認
- **入力**: `{}`（空オブジェクト）
- **期待結果**: `statusCode == 400`
- **信頼性**: 🔵 青信号 - GradeAnswerRequest の `user_answer` は必須フィールド（`...` = Required）
- **検証方法**:
  ```python
  event = _make_grade_ai_event(body={})
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 400
  ```

---

## テストカテゴリ D: カード関連テスト（TestGradeAiHandlerCardErrors）

### TC-060-CARD-001: `test_grade_ai_returns_404_when_card_not_found` 🔵

- **目的**: `CardNotFoundError` が raise された場合に HTTP 404 を返すことを確認
- **入力**: 正常リクエスト、`card_service.get_card` が `CardNotFoundError` を raise
- **期待結果**: `statusCode == 404`, `body == {"error": "Not Found"}`
- **信頼性**: 🔵 青信号 - api-endpoints.md エラーコード 404「カードが見つからない」、CardService.get_card() 仕様
- **モック**: `mock_ai_service`
- **検証方法**:
  ```python
  with patch("api.handler.card_service") as mock_cs:
      mock_cs.get_card.side_effect = CardNotFoundError("Card not found")
      event = _make_grade_ai_event()
      response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 404
  body = json.loads(response["body"])
  assert body["error"] == "Not Found"
  ```

### TC-060-CARD-002: `test_grade_ai_passes_card_front_back_to_ai_service` 🔵

- **目的**: 取得したカードの `.front` と `.back` が AI サービスに正しく渡されることを確認
- **入力**: `card.front = "日本の首都は？"`, `card.back = "東京"`
- **期待結果**: `ai_service.grade_answer` が `card_front="日本の首都は？"`, `card_back="東京"` で呼ばれる
- **信頼性**: 🔵 青信号 - Card モデル（Pydantic BaseModel）の `.front` / `.back` 属性アクセスで確定。dataflow.md の `Card(front, back)` フロー
- **モック**: `mock_card_service`, `mock_ai_service`
- **検証方法**:
  ```python
  event = _make_grade_ai_event(body={"user_answer": "東京"})
  response = grade_ai_handler(event, lambda_context)
  mock_service.grade_answer.assert_called_once_with(
      card_front="日本の首都は？",
      card_back="東京",
      user_answer="東京",
      language="ja",
  )
  ```

### TC-060-CARD-003: `test_grade_ai_returns_404_for_other_users_card` 🔵

- **目的**: 他ユーザーのカードにアクセスした場合（CardNotFoundError）に HTTP 404 を返すことを確認
- **入力**: `user_id="user-other"` で `card_service.get_card` が `CardNotFoundError` を raise
- **期待結果**: `statusCode == 404`
- **信頼性**: 🔵 青信号 - CardService.get_card() は user_id をパーティションキーとして使用するため、他ユーザーのカードは CardNotFoundError になる
- **検証方法**:
  ```python
  with patch("api.handler.card_service") as mock_cs:
      mock_cs.get_card.side_effect = CardNotFoundError("Card not found")
      event = _make_grade_ai_event(user_id="user-other", card_id="card-owned-by-someone-else")
      response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 404
  ```

---

## テストカテゴリ E: AI 採点呼び出しテスト（TestGradeAiHandlerAICall）

### TC-060-AI-001: `test_grade_ai_calls_create_ai_service_factory` 🔵

- **目的**: `create_ai_service()` ファクトリーが 1 回呼ばれることを確認
- **入力**: 正常リクエスト
- **期待結果**: `create_ai_service()` が exactly 1 回呼ばれる
- **信頼性**: 🔵 青信号 - 既存 `generate_cards` エンドポイントのパターン（handler.py L317）
- **モック**: `mock_card_service`, `mock_ai_service`
- **検証方法**:
  ```python
  event = _make_grade_ai_event()
  response = grade_ai_handler(event, lambda_context)
  mock_factory.assert_called_once()
  ```

### TC-060-AI-002: `test_grade_ai_passes_correct_args_to_grade_answer` 🔵

- **目的**: `grade_answer()` に正しい引数が渡されることを確認
- **入力**: `user_answer="東京"`, `card.front="日本の首都は？"`, `card.back="東京"`, language デフォルト "ja"
- **期待結果**: `grade_answer(card_front="日本の首都は？", card_back="東京", user_answer="東京", language="ja")`
- **信頼性**: 🔵 青信号 - AIService Protocol の grade_answer シグネチャ（ai_service.py L133-151）
- **検証方法**:
  ```python
  event = _make_grade_ai_event(body={"user_answer": "東京"})
  response = grade_ai_handler(event, lambda_context)
  mock_service.grade_answer.assert_called_once_with(
      card_front="日本の首都は？",
      card_back="東京",
      user_answer="東京",
      language="ja",
  )
  ```

### TC-060-AI-003: `test_grade_ai_passes_language_param_to_grade_answer` 🔵

- **目的**: クエリパラメータ `language=en` が AI サービスに渡されることを確認
- **入力**: `queryStringParameters = {"language": "en"}`
- **期待結果**: `grade_answer(..., language="en")` が呼ばれる
- **信頼性**: 🔵 青信号 - api-endpoints.md の language パラメータ仕様、独立 Lambda は `queryStringParameters` から取得
- **モック**: `mock_card_service`, `mock_ai_service`
- **検証方法**:
  ```python
  event = _make_grade_ai_event(query_params={"language": "en"})
  response = grade_ai_handler(event, lambda_context)
  mock_service.grade_answer.assert_called_once()
  call_kwargs = mock_service.grade_answer.call_args[1]
  assert call_kwargs["language"] == "en"
  ```

### TC-060-AI-004: `test_grade_ai_uses_default_language_ja` 🔵

- **目的**: `queryStringParameters` なしの場合にデフォルト `"ja"` が使われることを確認
- **入力**: `queryStringParameters` キーなし
- **期待結果**: `grade_answer(..., language="ja")` が呼ばれる
- **信頼性**: 🔵 青信号 - TASK-0060.md L125「language デフォルト "ja"」、api-endpoints.md
- **検証方法**:
  ```python
  event = _make_grade_ai_event()  # query_params なし
  response = grade_ai_handler(event, lambda_context)
  call_kwargs = mock_service.grade_answer.call_args[1]
  assert call_kwargs["language"] == "ja"
  ```

---

## テストカテゴリ F: 正常系レスポンステスト（TestGradeAiHandlerSuccess）

### TC-060-RES-001: `test_grade_ai_success_returns_200` 🔵

- **目的**: 正常系で HTTP 200 が返ることを確認
- **入力**: 正常リクエスト + カード存在 + AI 採点成功
- **期待結果**: `statusCode == 200`
- **信頼性**: 🔵 青信号 - api-endpoints.md「レスポンス（成功 200）」
- **モック**: `mock_card_service`, `mock_ai_service`
- **検証方法**:
  ```python
  event = _make_grade_ai_event()
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 200
  ```

### TC-060-RES-002: `test_grade_ai_success_response_contains_grade` 🔵

- **目的**: レスポンスに `grade` フィールドが正しく含まれることを確認
- **入力**: AI が `grade=4` を返す（GradingResult のモック）
- **期待結果**: `response body の grade == 4`
- **信頼性**: 🔵 青信号 - GradeAnswerResponse モデル定義（grading.py L45-49）
- **検証方法**:
  ```python
  event = _make_grade_ai_event()
  response = grade_ai_handler(event, lambda_context)
  body = json.loads(response["body"])
  assert body["grade"] == 4
  ```

### TC-060-RES-003: `test_grade_ai_success_response_contains_reasoning` 🔵

- **目的**: レスポンスに `reasoning` フィールドが正しく含まれることを確認
- **入力**: AI が `reasoning="Correct answer with good understanding"` を返す
- **期待結果**: `response body の reasoning == "Correct answer with good understanding"`
- **信頼性**: 🔵 青信号 - GradeAnswerResponse モデル定義（grading.py L51-53）
- **検証方法**:
  ```python
  body = json.loads(response["body"])
  assert body["reasoning"] == "Correct answer with good understanding"
  ```

### TC-060-RES-004: `test_grade_ai_success_response_contains_card_front_back` 🔵

- **目的**: レスポンスに `card_front` と `card_back` が含まれることを確認
- **入力**: `card.front="日本の首都は？"`, `card.back="東京"`
- **期待結果**: `body の card_front == "日本の首都は？"`, `card_back == "東京"`
- **信頼性**: 🔵 青信号 - GradeAnswerResponse の card_front / card_back フィールド（grading.py L55-62）
- **検証方法**:
  ```python
  body = json.loads(response["body"])
  assert body["card_front"] == "日本の首都は？"
  assert body["card_back"] == "東京"
  ```

### TC-060-RES-005: `test_grade_ai_success_response_contains_grading_info` 🔵

- **目的**: レスポンスの `grading_info` に `model_used` と `processing_time_ms` が含まれることを確認
- **入力**: AI が `model_used="test-model"`, `processing_time_ms=500` を返す
- **期待結果**: `body の grading_info["model_used"] == "test-model"`, `grading_info["processing_time_ms"] == 500`
- **信頼性**: 🔵 青信号 - api-endpoints.md の grading_info 仕様、GradeAnswerResponse 定義（grading.py L63-66）
- **検証方法**:
  ```python
  body = json.loads(response["body"])
  assert body["grading_info"]["model_used"] == "test-model"
  assert body["grading_info"]["processing_time_ms"] == 500
  ```

### TC-060-RES-006: `test_grade_ai_success_response_is_json` 🔵

- **目的**: Content-Type ヘッダーが `application/json` であることを確認
- **入力**: 正常リクエスト
- **期待結果**: `response["headers"]["Content-Type"] == "application/json"`
- **信頼性**: 🔵 青信号 - 既存スタブのレスポンスパターン（handler.py L608）、REST API 標準
- **検証方法**:
  ```python
  response = grade_ai_handler(event, lambda_context)
  assert response["headers"]["Content-Type"] == "application/json"
  ```

### TC-060-RES-007: `test_grade_ai_success_full_e2e_flow` 🔵

- **目的**: 認証 -> カード取得 -> AI 採点 -> レスポンス返却の一連フローが正しく動作することを確認
- **入力**: `user_id="e2e-user"`, `card_id="e2e-card"`, `user_answer="パリ"`, `card.front="フランスの首都は？"`, `card.back="パリ"`, AI returns `grade=5, reasoning="Perfect match"`
- **期待結果**: 全フィールドが正しく返される
- **信頼性**: 🔵 青信号 - dataflow.md 機能2: 回答採点フロー全体
- **モック**: card_service（カスタム front/back）, ai_service（カスタム GradingResult）
- **検証方法**:
  ```python
  with patch("api.handler.card_service") as mock_cs, \
       patch("api.handler.create_ai_service") as mock_factory:
      mock_card = MagicMock()
      mock_card.front = "フランスの首都は？"
      mock_card.back = "パリ"
      mock_cs.get_card.return_value = mock_card

      mock_service = MagicMock()
      mock_service.grade_answer.return_value = GradingResult(
          grade=5,
          reasoning="Perfect match",
          model_used="claude-3-haiku",
          processing_time_ms=350,
      )
      mock_factory.return_value = mock_service

      event = _make_grade_ai_event(
          user_id="e2e-user",
          card_id="e2e-card",
          body={"user_answer": "パリ"},
      )
      response = grade_ai_handler(event, lambda_context)

  assert response["statusCode"] == 200
  body = json.loads(response["body"])
  assert body["grade"] == 5
  assert body["reasoning"] == "Perfect match"
  assert body["card_front"] == "フランスの首都は？"
  assert body["card_back"] == "パリ"
  assert body["grading_info"]["model_used"] == "claude-3-haiku"
  assert body["grading_info"]["processing_time_ms"] == 350
  mock_cs.get_card.assert_called_once_with("e2e-user", "e2e-card")
  mock_service.grade_answer.assert_called_once_with(
      card_front="フランスの首都は？",
      card_back="パリ",
      user_answer="パリ",
      language="ja",
  )
  ```

---

## テストカテゴリ G: AI エラーハンドリングテスト（TestGradeAiHandlerAIErrors）

### TC-060-ERR-001: `test_grade_ai_returns_504_on_ai_timeout` 🔵

- **目的**: `AITimeoutError` が HTTP 504 にマッピングされることを確認
- **入力**: `grade_answer` が `AITimeoutError("timeout")` を raise
- **期待結果**: `statusCode == 504`, `body == {"error": "AI service timeout"}`
- **信頼性**: 🔵 青信号 - `_map_ai_error_to_http()` 実装（handler.py L74-80）
- **モック**: `mock_card_service`, `mock_ai_service`（side_effect で例外設定）
- **検証方法**:
  ```python
  mock_service.grade_answer.side_effect = AITimeoutError("timeout")
  event = _make_grade_ai_event()
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 504
  body = json.loads(response["body"])
  assert body["error"] == "AI service timeout"
  ```

### TC-060-ERR-002: `test_grade_ai_returns_429_on_ai_rate_limit` 🔵

- **目的**: `AIRateLimitError` が HTTP 429 にマッピングされることを確認
- **入力**: `grade_answer` が `AIRateLimitError("rate limit")` を raise
- **期待結果**: `statusCode == 429`, `body == {"error": "AI service rate limit exceeded"}`
- **信頼性**: 🔵 青信号 - `_map_ai_error_to_http()` 実装（handler.py L81-86）
- **検証方法**:
  ```python
  mock_service.grade_answer.side_effect = AIRateLimitError("rate limit")
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 429
  body = json.loads(response["body"])
  assert body["error"] == "AI service rate limit exceeded"
  ```

### TC-060-ERR-003: `test_grade_ai_returns_503_on_ai_provider_error` 🔵

- **目的**: `AIProviderError` が HTTP 503 にマッピングされることを確認
- **入力**: `grade_answer` が `AIProviderError("provider down")` を raise
- **期待結果**: `statusCode == 503`, `body == {"error": "AI service unavailable"}`
- **信頼性**: 🔵 青信号 - `_map_ai_error_to_http()` 実装（handler.py L88-93）
- **検証方法**:
  ```python
  mock_service.grade_answer.side_effect = AIProviderError("provider down")
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 503
  body = json.loads(response["body"])
  assert body["error"] == "AI service unavailable"
  ```

### TC-060-ERR-004: `test_grade_ai_returns_500_on_ai_parse_error` 🔵

- **目的**: `AIParseError` が HTTP 500 にマッピングされることを確認
- **入力**: `grade_answer` が `AIParseError("invalid json")` を raise
- **期待結果**: `statusCode == 500`, `body == {"error": "AI service response parse error"}`
- **信頼性**: 🔵 青信号 - `_map_ai_error_to_http()` 実装（handler.py L95-100）
- **検証方法**:
  ```python
  mock_service.grade_answer.side_effect = AIParseError("invalid json")
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 500
  body = json.loads(response["body"])
  assert body["error"] == "AI service response parse error"
  ```

### TC-060-ERR-005: `test_grade_ai_returns_500_on_ai_internal_error` 🔵

- **目的**: `AIInternalError` が HTTP 500 にマッピングされることを確認
- **入力**: `grade_answer` が `AIInternalError("internal failure")` を raise
- **期待結果**: `statusCode == 500`, `body == {"error": "AI service error"}`
- **信頼性**: 🔵 青信号 - `_map_ai_error_to_http()` 実装（handler.py L102-106）
- **検証方法**:
  ```python
  mock_service.grade_answer.side_effect = AIInternalError("internal failure")
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 500
  body = json.loads(response["body"])
  assert body["error"] == "AI service error"
  ```

### TC-060-ERR-006: `test_grade_ai_returns_503_on_factory_init_failure` 🔵

- **目的**: `create_ai_service()` 自体が `AIProviderError` を raise した場合に HTTP 503 を返すことを確認
- **入力**: `create_ai_service()` が `AIProviderError("Failed to initialize")` を raise
- **期待結果**: `statusCode == 503`, `body == {"error": "AI service unavailable"}`
- **信頼性**: 🔵 青信号 - ai_service.py L198「raise AIProviderError」、TC-056-013 のテストパターン
- **モック**: `mock_card_service`, `create_ai_service` の `side_effect` を設定
- **検証方法**:
  ```python
  with patch("api.handler.card_service") as mock_cs, \
       patch("api.handler.create_ai_service") as mock_factory:
      mock_card = MagicMock()
      mock_card.front = "Q"
      mock_card.back = "A"
      mock_cs.get_card.return_value = mock_card
      mock_factory.side_effect = AIProviderError("Failed to initialize AI service")

      event = _make_grade_ai_event()
      response = grade_ai_handler(event, lambda_context)

  assert response["statusCode"] == 503
  body = json.loads(response["body"])
  assert body["error"] == "AI service unavailable"
  ```

### TC-060-ERR-007: `test_grade_ai_returns_500_on_unexpected_exception` 🔵

- **目的**: 予期しない例外（`RuntimeError` 等）が HTTP 500 にマッピングされることを確認
- **入力**: `grade_answer` が `RuntimeError("unexpected")` を raise
- **期待結果**: `statusCode == 500`, `body == {"error": "Internal Server Error"}`
- **信頼性**: 🔵 青信号 - TASK-0060.md L181-186 の `except Exception as e` パターン
- **検証方法**:
  ```python
  mock_service.grade_answer.side_effect = RuntimeError("unexpected")
  event = _make_grade_ai_event()
  response = grade_ai_handler(event, lambda_context)
  assert response["statusCode"] == 500
  body = json.loads(response["body"])
  assert body["error"] == "Internal Server Error"
  ```

---

## テストカテゴリ H: ロギングテスト（TestGradeAiHandlerLogging）

### TC-060-LOG-001: `test_grade_ai_logs_request_info` 🔵

- **目的**: 採点リクエスト受信時に `logger.info` で `card_id`, `user_id`, `user_answer_length` を記録することを確認
- **入力**: 正常リクエスト（`user_answer="テスト回答"`, 5文字）
- **期待結果**: `logger.info` が `card_id`, `user_id`, `user_answer_length` を含むキーワード引数で呼ばれる
- **信頼性**: 🔵 青信号 - TASK-0060.md ロギング仕様 L204-209、既存 generate_cards のログパターン（handler.py L295）
- **モック**: `mock_card_service`, `mock_ai_service`, `patch("api.handler.logger")`
- **検証方法**:
  ```python
  with patch("api.handler.logger") as mock_logger:
      event = _make_grade_ai_event(body={"user_answer": "テスト回答"})
      response = grade_ai_handler(event, lambda_context)

  # logger.info が呼ばれた引数を検証
  info_calls = mock_logger.info.call_args_list
  # リクエストログの存在確認（具体的な引数形式は実装次第）
  assert any(
      "card_id" in str(call) or "card-123" in str(call)
      for call in info_calls
  )
  ```

### TC-060-LOG-002: `test_grade_ai_logs_success_info` 🔵

- **目的**: 採点成功時に `logger.info` で `grade` を含む情報を記録することを確認
- **入力**: 正常リクエスト + AI 採点成功（`grade=4`）
- **期待結果**: `logger.info` が `grade` を含む引数で呼ばれる
- **信頼性**: 🔵 青信号 - 既存 generate_cards の成功ログパターン（handler.py L324-326）
- **検証方法**:
  ```python
  with patch("api.handler.logger") as mock_logger:
      event = _make_grade_ai_event()
      response = grade_ai_handler(event, lambda_context)

  info_calls = mock_logger.info.call_args_list
  assert any("grade" in str(call) or "4" in str(call) for call in info_calls)
  ```

### TC-060-LOG-003: `test_grade_ai_logs_ai_error` 🔵

- **目的**: AI エラー発生時に `logger.warning` または `logger.error` で記録することを確認
- **入力**: `grade_answer` が `AITimeoutError` を raise
- **期待結果**: `logger.warning` または `logger.error` が呼ばれる
- **信頼性**: 🔵 青信号 - 既存 generate_cards の AI エラーログパターン（handler.py L348）
- **モック**: `mock_card_service`, `mock_ai_service`（side_effect）, `patch("api.handler.logger")`
- **検証方法**:
  ```python
  with patch("api.handler.logger") as mock_logger:
      mock_service.grade_answer.side_effect = AITimeoutError("timeout")
      event = _make_grade_ai_event()
      response = grade_ai_handler(event, lambda_context)

  assert mock_logger.warning.called or mock_logger.error.called
  ```

---

## テストファイル構成サマリー

### ファイル: `backend/tests/unit/test_handler_grade_ai.py`

| テストクラス | TC ID 範囲 | TC 数 |
|------------|-----------|-------|
| `TestGradeAiHandlerAuth` | TC-060-AUTH-001 ~ 003 | 3 |
| `TestGradeAiHandlerPathParams` | TC-060-PATH-001 ~ 002 | 2 |
| `TestGradeAiHandlerValidation` | TC-060-VAL-001 ~ 006 | 6 |
| `TestGradeAiHandlerCardErrors` | TC-060-CARD-001 ~ 003 | 3 |
| `TestGradeAiHandlerAICall` | TC-060-AI-001 ~ 004 | 4 |
| `TestGradeAiHandlerSuccess` | TC-060-RES-001 ~ 007 | 7 |
| `TestGradeAiHandlerAIErrors` | TC-060-ERR-001 ~ 007 | 7 |
| `TestGradeAiHandlerLogging` | TC-060-LOG-001 ~ 003 | 3 |
| **合計** | | **35** |

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

- **handler.py**: 既存 `_map_ai_error_to_http()` 実装（L62-107）、`get_user_id_from_context()` パターン（L110-148）
- **grading.py**: `GradeAnswerRequest` / `GradeAnswerResponse` の Pydantic モデル定義（TASK-0059 で作成済み）
- **ai_service.py**: `AIService` Protocol の `grade_answer()` シグネチャ（L133-151）、`GradingResult` dataclass（L38-44）、例外階層（L72-105）、`create_ai_service()` ファクトリー（L171-198）
- **card_service.py**: `CardService.get_card()` メソッド（L183-202）、`CardNotFoundError`（L24-27）
- **template.yaml**: `ReviewsGradeAiFunction` 定義（Handler, Path `/reviews/{cardId}/grade-ai`）
- **api-endpoints.md**: POST /reviews/{card_id}/grade-ai の仕様
- **dataflow.md**: 機能2: 回答採点フロー
- **test_handler_ai_service_factory.py**: 既存テストパターン参照

---

## 既存テストへの影響

### `test_handler_ai_service_factory.py` の `TestStubHandlers`

TASK-0060 完了後、以下の既存テストは**修正が必要**:

- **TC-056-014** (`test_grade_ai_handler_returns_501`): `grade_ai_handler` がスタブ 501 ではなく本実装の動作をするようになるため、このテストは削除するか、条件付きスキップに変更する。

---

## モック戦略まとめ

| 対象 | パッチパス | 用途 |
|------|----------|------|
| `CardService` (グローバル変数) | `api.handler.card_service` | `get_card()` の返り値/例外を制御 |
| `create_ai_service` (ファクトリー) | `api.handler.create_ai_service` | AI サービスの返り値/例外を制御 |
| `Logger` | `api.handler.logger` | ログ出力内容の検証（ロギングテストのみ） |

**重要**: `card_service` はモジュールレベルのグローバル変数（handler.py L57）であるため、`patch("api.handler.card_service")` でパッチする。`create_ai_service` はインポートされた関数なので `patch("api.handler.create_ai_service")` でパッチする。

---

## 依存関係

```
TASK-0056 (AIServiceFactory 統合) ──┐
                                     ├── TASK-0060 (本タスク) ──> TASK-0063 (Phase 3 統合テスト)
TASK-0059 (採点モデル・AI実装) ─────┘
```

---

*作成日*: 2026-02-24
*タスク*: TASK-0060 TDD Testcases Phase
*信頼性*: 🔵 35件 (100%) / 🟡 0件 (0%) / 🔴 0件 (0%)

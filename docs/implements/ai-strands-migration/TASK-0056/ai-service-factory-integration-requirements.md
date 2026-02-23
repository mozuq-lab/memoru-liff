# TASK-0056: handler.py AIServiceFactory 統合 + template.yaml 更新 - TDD 要件定義書

**タスクID**: TASK-0056
**要件名**: ai-strands-migration
**機能名**: handler.py AIServiceFactory 統合 + template.yaml 更新
**作成日**: 2026-02-23
**タイプ**: TDD (Red -> Green -> Refactor)

---

## 1. 機能の概要

### 何をする機能か 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義書・アーキテクチャ設計 architecture.md「AIサービス抽象化レイヤー」・API仕様 api-endpoints.md「template.yaml 追加設定」より*

handler.py の BedrockService 直接参照を `create_ai_service()` ファクトリ経由に変更し、AI サービス抽象化を完成させる。同時に template.yaml にフィーチャーフラグ（`USE_STRANDS`）・新環境変数・新 API ルートを追加し、後続タスクで実装する回答採点/学習アドバイス機能の基盤を準備する。

### どのような問題を解決するか 🔵

**信頼性**: 🔵 *要件定義 REQ-SM-102/103 フィーチャーフラグ制御・REQ-SM-201 旧新実装共存要件より*

- handler.py が `BedrockService` に直接依存しており、Strands Agents SDK への切替ができない
- template.yaml に `USE_STRANDS` フィーチャーフラグがなく、環境ごとの AI 実装切替が不可能
- 新 API エンドポイント（`/reviews/{cardId}/grade-ai`, `/advice`）のルート定義がない
- エラーハンドリングが Bedrock 固有例外に依存しており、統一例外階層を活用していない

### 想定されるユーザー 🔵

**信頼性**: 🔵 *既存ユーザストーリーより*

- **開発者**: フィーチャーフラグで Bedrock / Strands を切替えてテスト
- **エンドユーザー**: 既存の `/cards/generate` エンドポイントの動作に変更なし
- **運用者**: CloudFormation パラメータでフラグを制御

### システム内での位置づけ 🔵

**信頼性**: 🔵 *architecture.md「アーキテクチャパターン」セクション・overview.md「Phase 1: 基盤構築」最終タスクより*

Phase 1（基盤構築）の最終統合タスク。以下を結合する:
- TASK-0053 で定義した AIService Protocol + 例外階層
- TASK-0054 で分離したプロンプトモジュール
- TASK-0055 で Protocol 準拠にした BedrockAIService
- これらを handler.py + template.yaml + env.json で統合

後続タスクのブロック対象:
- TASK-0057: StrandsAIService 基本実装
- TASK-0058: カード生成 API 互換性検証
- TASK-0060: POST /reviews/{cardId}/grade-ai エンドポイント
- TASK-0062: GET /advice エンドポイント

**参照した EARS 要件**: REQ-SM-001, REQ-SM-002, REQ-SM-102, REQ-SM-103, REQ-SM-201, REQ-SM-401, REQ-SM-402, REQ-SM-405
**参照した設計文書**: architecture.md「コンポーネント構成」「エラーハンドリング」、api-endpoints.md「template.yaml 追加設定」

---

## 2. 入力・出力の仕様

### 2.1 handler.py の改修

#### import パス変更 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義・ai_service.py 実装コードより*

**現在（入力）**:
```python
from services.bedrock import (
    BedrockService,
    BedrockTimeoutError,
    BedrockRateLimitError,
    BedrockInternalError,
    BedrockParseError,
)
```

**変更後（出力）**:
```python
from services.ai_service import (
    create_ai_service,
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIInternalError,
    AIParseError,
    AIProviderError,
)
```

#### グローバル変数変更 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義・handler.py L57 の `bedrock_service = BedrockService()` より*

**現在**: `bedrock_service = BedrockService()` （モジュールレベルのグローバルインスタンス）
**変更後**: `bedrock_service` 変数を削除。`generate_cards()` 関数内で `ai_service = create_ai_service()` を呼び出す。

#### generate_cards エンドポイント改修 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義・handler.py L241-316・api-endpoints.md「POST /cards/generate」より*

**入力**: `GenerateCardsRequest` Pydantic モデル（変更なし）

| フィールド | 型 | 必須 | バリデーション |
|-----------|------|------|--------------|
| `input_text` | str | Yes | 10-2000文字 |
| `card_count` | int | No | 1-10, default=5 |
| `difficulty` | str | No | "easy"/"medium"/"hard", default="medium" |
| `language` | str | No | "ja"/"en", default="ja" |

**出力**: `GenerateCardsResponse` Pydantic モデル（変更なし）

```json
{
  "generated_cards": [
    {"front": "...", "back": "...", "suggested_tags": [...]}
  ],
  "generation_info": {
    "input_length": 150,
    "model_used": "anthropic.claude-3-haiku-20240307-v1:0",
    "processing_time_ms": 3500
  }
}
```

**変更内容**: AI サービス呼び出しの差し替え

| 項目 | 旧実装 | 新実装 |
|------|--------|--------|
| サービス取得 | `bedrock_service` (グローバル) | `create_ai_service()` (関数内) |
| 例外: タイムアウト | `BedrockTimeoutError` -> 504 | `AITimeoutError` -> 504 |
| 例外: レート制限 | `BedrockRateLimitError` -> 429 | `AIRateLimitError` -> 429 |
| 例外: 内部エラー | `BedrockInternalError` -> 502 | `AIInternalError` -> 502 |
| 例外: 解析エラー | `BedrockParseError` -> 500 | `AIParseError` -> 500 |
| 例外: プロバイダー | (なし) | `AIProviderError` -> 503 |
| 例外: 汎用 | (なし) | `AIServiceError` -> 500 |

#### _map_ai_error_to_http() ヘルパー関数 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義・architecture.md「エラーハンドリング」セクションより*

**入力**: `AIServiceError` インスタンス
**出力**: `Response` オブジェクト（AWS Lambda Powertools）

| 例外クラス | HTTP ステータス | エラーメッセージ |
|-----------|---------------|-----------------|
| `AITimeoutError` | 504 | "AI service timeout" |
| `AIRateLimitError` | 429 | "AI service rate limit exceeded" |
| `AIProviderError` | 503 | "AI service unavailable" |
| `AIParseError` | 500 | "AI service response parse error" |
| `AIInternalError` | 500 | "AI service error" |
| `AIServiceError` (汎用) | 500 | "AI service error" |

レスポンスフォーマット:
```json
{
  "error": "<エラーメッセージ>"
}
```

Content-Type: `application/json`

### 2.2 template.yaml の改修

#### UseStrands パラメータ追加 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義・api-endpoints.md「template.yaml 追加設定」・要件 REQ-SM-102/103 より*

**入力（新規パラメータ定義）**:

| パラメータ名 | 型 | デフォルト値 | 許可値 | 説明 |
|-------------|------|------------|--------|------|
| `UseStrands` | String | "false" | "true", "false" | Strands Agents SDK 使用フラグ |

#### ShouldUseStrands コンディション追加 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義より*

```yaml
ShouldUseStrands: !Equals [!Ref UseStrands, "true"]
```

#### Globals 環境変数追加 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義・api-endpoints.md「新規環境変数」セクションより*

| 環境変数名 | 値 | 説明 |
|-----------|------|------|
| `USE_STRANDS` | `!Ref UseStrands` | フィーチャーフラグ参照 |
| `OLLAMA_HOST` | `!If [ShouldUseStrands, "http://ollama:11434", ""]` | Ollama ホスト（条件付き） |
| `OLLAMA_MODEL` | `!If [ShouldUseStrands, "neural-chat", ""]` | Ollama モデル名（条件付き） |

#### Global タイムアウト更新 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義・api-endpoints.md「Lambda タイムアウト設定」・要件 REQ-SM-401 より*

| 項目 | 旧値 | 新値 | 理由 |
|------|------|------|------|
| `Globals.Function.Timeout` | 30 | 60 | Strands SDK 処理時間対応 |

#### 新 API ルート（Lambda 関数）追加 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義・api-endpoints.md「新規 API ルート」・要件 REQ-SM-003/004 より*

**注意**: 現行 handler.py は `APIGatewayHttpResolver` を使用した単一 Lambda 関数（`ApiFunction`）でルーティングを実施している。新 API ルートは **既存の `ApiFunction` に Events として追加** するのが既存パターンに整合する設計である。ただしタスク定義では別 Lambda 関数として定義しているため、タスク定義に準拠して新 Lambda 関数を定義する。

##### ReviewsGradeAiFunction 🔵

| 項目 | 値 |
|------|------|
| Type | AWS::Serverless::Function |
| FunctionName | `!Sub memoru-grade-ai-${Environment}` |
| CodeUri | src/ |
| Handler | api.handler.grade_ai_handler |
| Timeout | 60 |
| MemorySize | 512 |
| Event Path | `/reviews/{cardId}/grade-ai` |
| Event Method | POST |
| Event Type | HttpApi |
| ApiId | `!Ref HttpApi` |

##### AdviceFunction 🔵

| 項目 | 値 |
|------|------|
| Type | AWS::Serverless::Function |
| FunctionName | `!Sub memoru-advice-${Environment}` |
| CodeUri | src/ |
| Handler | api.handler.advice_handler |
| Timeout | 60 |
| MemorySize | 512 |
| Event Path | `/advice` |
| Event Method | GET |
| Event Type | HttpApi |
| ApiId | `!Ref HttpApi` |

##### LogGroups 🔵

- `ReviewsGradeAiFunctionLogGroup`: RetentionInDays = `!If [IsProd, 90, 14]`
- `AdviceFunctionLogGroup`: RetentionInDays = `!If [IsProd, 90, 14]`

##### Outputs 🔵

- `ReviewsGradeAiFunctionArn`: Grade AI Lambda ARN
- `AdviceFunctionArn`: Advice Lambda ARN

### 2.3 env.json の改修

#### 既存関数への環境変数追加 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義・既存 env.json 構造より*

以下の関数に環境変数を追加:
- `ApiFunction`
- `LineWebhookFunction`
- `DuePushJobFunction`

追加する環境変数:

| 変数名 | ローカル開発値 |
|--------|---------------|
| `USE_STRANDS` | `"false"` |
| `OLLAMA_HOST` | `"http://localhost:11434"` |
| `OLLAMA_MODEL` | `"neural-chat"` |

#### 新規関数の環境変数定義 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義・template.yaml 新リソース定義に対応*

以下の新規関数エントリを追加:
- `ReviewsGradeAiFunction`
- `AdviceFunction`

各関数に必要な環境変数:

| 変数名 | 値 |
|--------|------|
| `ENVIRONMENT` | `"dev"` |
| `USERS_TABLE` | `"memoru-users-dev"` |
| `CARDS_TABLE` | `"memoru-cards-dev"` |
| `REVIEWS_TABLE` | `"memoru-reviews-dev"` |
| `KEYCLOAK_ISSUER` | `"http://localhost:8180/realms/memoru"` |
| `BEDROCK_MODEL_ID` | `"global.anthropic.claude-haiku-4-5-20251001-v1:0"` |
| `LOG_LEVEL` | `"DEBUG"` |
| `DYNAMODB_ENDPOINT_URL` | `"http://dynamodb-local:8000"` |
| `AWS_ENDPOINT_URL` | `"http://dynamodb-local:8000"` |
| `USE_STRANDS` | `"false"` |
| `OLLAMA_HOST` | `"http://localhost:11434"` |
| `OLLAMA_MODEL` | `"neural-chat"` |

### 2.4 handler.py スタブハンドラー追加 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義「Notes」セクション - 新 API ルートは定義のみ、ハンドラー実装は後続タスク*

新 Lambda 関数 (`ReviewsGradeAiFunction`, `AdviceFunction`) が参照する `grade_ai_handler` と `advice_handler` は、handler.py にスタブとして追加する必要がある。SAM ビルド・デプロイが失敗しないよう最低限のエントリーポイントを提供する。

```python
def grade_ai_handler(event: dict, context: LambdaContext) -> dict:
    """Stub handler for AI grading endpoint (implemented in TASK-0060)."""
    return {
        "statusCode": 501,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": "Not implemented"}),
    }

def advice_handler(event: dict, context: LambdaContext) -> dict:
    """Stub handler for learning advice endpoint (implemented in TASK-0062)."""
    return {
        "statusCode": 501,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"error": "Not implemented"}),
    }
```

**参照した EARS 要件**: REQ-SM-002, REQ-SM-003, REQ-SM-004, REQ-SM-102, REQ-SM-103, REQ-SM-401, REQ-SM-402
**参照した設計文書**: api-endpoints.md 全エンドポイント仕様、architecture.md「ディレクトリ構造」

---

## 3. 制約条件

### パフォーマンス要件 🔵

**信頼性**: 🔵 *NFR-SM-001・REQ-SM-401・api-endpoints.md「Lambda タイムアウト設定」より*

- Lambda タイムアウト: 60 秒（Globals レベル）
- カード生成レスポンス目標: 30 秒以内（既存ベースライン維持）
- `create_ai_service()` は同期呼び出し（Lambda Powertools の `APIGatewayHttpResolver` は同期ハンドラー）

### セキュリティ要件 🔵

**信頼性**: 🔵 *NFR-SM-101・既存 template.yaml IAM ポリシーより*

- 新 Lambda 関数に `bedrock:InvokeModel` IAM 権限を付与
- 新 Lambda 関数は `HttpApi` イベントで JwtAuthorizer を継承（認証必須）
- `KEYCLOAK_ISSUER` 環境変数を新関数にも設定

### 互換性要件 🔵

**信頼性**: 🔵 *REQ-SM-402・REQ-SM-405 より*

- **API レスポンス互換**: `GenerateCardsResponse` 形式は変更なし
- **既存テスト保護**: 既存の 260+ バックエンドテストが全て通過すること
- **テストカバレッジ**: 80% 以上を維持（REQ-SM-404）
- **後方互換**: `USE_STRANDS` のデフォルト値は `"false"`（既存 Bedrock 動作を保持）

### アーキテクチャ制約 🔵

**信頼性**: 🔵 *architecture.md「アーキテクチャパターン」・既存実装パターンより*

- Python 3.12 ランタイム
- AWS SAM (Serverless Application Model) テンプレート
- AWS Lambda Powertools (`APIGatewayHttpResolver`, `Logger`, `Tracer`)
- Pydantic v2 モデル
- `create_ai_service()` はリクエスト単位で呼び出し（グローバルインスタンス化しない）

### template.yaml 制約 🔵

**信頼性**: 🔵 *既存 template.yaml 構造より*

- HttpApi 型イベント（REST API ではなく HTTP API）
- `!Ref HttpApi` でAPI ID を参照
- Conditions は `!Equals` で定義
- YAML インデント: 2スペース
- `sam validate` でバリデーション通過が必須

**参照した EARS 要件**: NFR-SM-001, NFR-SM-101, REQ-SM-401, REQ-SM-402, REQ-SM-404, REQ-SM-405
**参照した設計文書**: architecture.md「技術的制約」、api-endpoints.md「Lambda タイムアウト設定」

---

## 4. 想定される使用例

### 4.1 基本的な使用パターン

#### UC-01: generate_cards が Factory 経由で Bedrock を使用（USE_STRANDS=false） 🔵

**信頼性**: 🔵 *REQ-SM-103・既存 generate_cards 実装より*

**前提条件**: `USE_STRANDS=false`（デフォルト）
**アクション**: `POST /cards/generate` に有効なリクエストを送信
**期待結果**:
1. `create_ai_service()` が呼び出され、`BedrockService` インスタンスを返す
2. `BedrockService.generate_cards()` が実行される
3. HTTP 200 + `GenerateCardsResponse` 形式のレスポンス

#### UC-02: generate_cards が Factory 経由で Strands を使用（USE_STRANDS=true） 🔵

**信頼性**: 🔵 *REQ-SM-102・create_ai_service() 実装より*

**前提条件**: `USE_STRANDS=true`
**アクション**: `POST /cards/generate` に有効なリクエストを送信
**期待結果**:
1. `create_ai_service()` が呼び出され、`StrandsAIService` インスタンスを返す
2. `StrandsAIService.generate_cards()` が実行される
3. HTTP 200 + `GenerateCardsResponse` 形式のレスポンス（`model_used` は Strands モデル名）

#### UC-03: 新 API ルートのスタブレスポンス 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義「Notes」より*

**前提条件**: template.yaml に新 Lambda 関数が定義済み
**アクション A**: `POST /reviews/{cardId}/grade-ai`
**期待結果 A**: HTTP 501 + `{"error": "Not implemented"}`

**アクション B**: `GET /advice`
**期待結果 B**: HTTP 501 + `{"error": "Not implemented"}`

### 4.2 エラーケース

#### EC-01: AI タイムアウトエラー 🔵

**信頼性**: 🔵 *architecture.md「エラーハンドリング」・api-endpoints.md エラーコード定義より*

**前提条件**: AI サービスが `AITimeoutError` を送出
**期待結果**: HTTP 504 + `{"error": "AI service timeout"}`

#### EC-02: AI レート制限エラー 🔵

**信頼性**: 🔵 *同上*

**前提条件**: AI サービスが `AIRateLimitError` を送出
**期待結果**: HTTP 429 + `{"error": "AI service rate limit exceeded"}`

#### EC-03: AI プロバイダーエラー 🔵

**信頼性**: 🔵 *同上*

**前提条件**: AI サービスが `AIProviderError` を送出
**期待結果**: HTTP 503 + `{"error": "AI service unavailable"}`

#### EC-04: AI 解析エラー 🔵

**信頼性**: 🔵 *同上*

**前提条件**: AI サービスが `AIParseError` を送出
**期待結果**: HTTP 500 + `{"error": "AI service response parse error"}`

#### EC-05: AI 内部エラー / 汎用エラー 🔵

**信頼性**: 🔵 *同上*

**前提条件**: AI サービスが `AIInternalError` または `AIServiceError` を送出
**期待結果**: HTTP 500 + `{"error": "AI service error"}`

### 4.3 エッジケース

#### EDGE-01: BedrockService の例外が AIServiceError 階層で捕捉される 🔵

**信頼性**: 🔵 *TASK-0055 で実施済みの多重継承により保証*

**前提条件**: `USE_STRANDS=false`、Bedrock が `BedrockTimeoutError` を送出
**期待結果**: `BedrockTimeoutError` は `AITimeoutError` のサブクラス（多重継承）なので `_map_ai_error_to_http()` で HTTP 504 にマッピングされる

#### EDGE-02: create_ai_service() の初期化失敗 🔵

**信頼性**: 🔵 *ai_service.py `create_ai_service()` 実装の except ブロックより*

**前提条件**: AI サービスの初期化中に例外発生
**期待結果**: `AIProviderError` が送出される -> `_map_ai_error_to_http()` -> HTTP 503

#### EDGE-03: template.yaml のパラメータ省略時 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義・CloudFormation パラメータ仕様より*

**前提条件**: `UseStrands` パラメータを指定せずにデプロイ
**期待結果**: デフォルト値 `"false"` が適用され、既存動作を維持

**参照した EARS 要件**: REQ-SM-102, REQ-SM-103, REQ-SM-003, REQ-SM-004, EDGE-SM-001, EDGE-SM-002
**参照した設計文書**: api-endpoints.md 全エラーコード定義、architecture.md「エラーハンドリング」

---

## 5. EARS 要件・設計文書との対応関係

### 参照したユーザストーリー
- US-1: カード生成 Strands 移行（`generate_cards` ファクトリ統合部分）
- US-2: 回答 AI 採点（API ルート定義のみ）
- US-3: 学習アドバイス（API ルート定義のみ）

### 参照した機能要件
- **REQ-SM-001**: Strands Agents SDK 統合 -> ファクトリ経由で Strands 選択可能に
- **REQ-SM-002**: カード生成の Strands 移行 -> `generate_cards` の抽象化完了
- **REQ-SM-003**: 回答採点機能 -> API ルート定義（スタブハンドラー）
- **REQ-SM-004**: 学習アドバイス機能 -> API ルート定義（スタブハンドラー）
- **REQ-SM-102**: USE_STRANDS=true で Strands 使用
- **REQ-SM-103**: USE_STRANDS=false で boto3 フォールバック
- **REQ-SM-201**: 新旧実装の共存

### 参照した非機能要件
- **NFR-SM-001**: カード生成 30 秒以内
- **NFR-SM-101**: IAM 最小権限
- **NFR-SM-201**: Lambda Powertools 構造化ロギング

### 参照した制約要件
- **REQ-SM-401**: Lambda タイムアウト機能別設定（60秒共通）
- **REQ-SM-402**: API レスポンス形式互換性
- **REQ-SM-404**: テストカバレッジ 80% 以上
- **REQ-SM-405**: 既存 260+ テスト保護

### 参照した Edge ケース
- **EDGE-SM-001**: Strands Agent タイムアウト処理
- **EDGE-SM-002**: Ollama 未起動時のエラーメッセージ
- **EDGE-SM-003**: フィーチャーフラグ切替時のリクエスト完走

### 参照した受け入れ基準
- handler.py が AIServiceFactory 経由で AI サービスを取得している
- template.yaml のタイムアウトが 60 秒に更新されている
- USE_STRANDS パラメータが template.yaml に追加されている
- 新環境変数が template.yaml に定義されている
- 新 API ルートが template.yaml に定義されている
- env.json に新環境変数が追加されている
- 既存テストが全て通過する
- テストカバレッジが 80% 以上

### 参照した設計文書

| 文書 | 参照セクション |
|------|---------------|
| **architecture.md** | システム概要、アーキテクチャパターン、AIサービス抽象化レイヤー、エラーハンドリング、ディレクトリ構造、技術的制約 |
| **api-endpoints.md** | POST /cards/generate、POST /reviews/{card_id}/grade-ai、GET /advice、Lambda タイムアウト設定、template.yaml 追加設定 |
| **requirements.md** | REQ-SM-001~006, REQ-SM-102/103, REQ-SM-201, REQ-SM-401~405, NFR-SM-001, NFR-SM-101/201 |
| **handler.py** | L41-47 (imports), L57 (bedrock_service), L241-316 (generate_cards) |
| **ai_service.py** | AIService Protocol, create_ai_service factory, 例外階層 |
| **template.yaml** | Globals, Parameters, Conditions, Resources (ApiFunction, LineWebhookFunction, DuePushJobFunction), Outputs |
| **env.json** | ApiFunction, LineWebhookFunction, DuePushJobFunction 環境変数 |
| **bedrock.py** | BedrockServiceError 多重継承（TASK-0055 改修済み） |
| **conftest.py** | api_gateway_event, lambda_context フィクスチャ |

---

## 6. テスト対象の概要

### テストカテゴリ 🔵

**信頼性**: 🔵 *TASK-0056 タスク定義「単体テスト要件」・note.md テストケースより*

| # | カテゴリ | テスト数 | 対象 |
|---|---------|---------|------|
| A | AIServiceFactory 統合 | 2 | handler.py の create_ai_service() 呼び出し |
| B | エラーマッピング | 5 | _map_ai_error_to_http() の各例外タイプ |
| C | 後方互換性 | 1 | generate_cards レスポンス形式 |
| D | template.yaml 設定 | 6 | パラメータ、コンディション、タイムアウト、環境変数、APIルート |
| E | env.json 設定 | 2 | 既存・新規関数の環境変数 |
| F | スタブハンドラー | 2 | grade_ai_handler, advice_handler の 501 レスポンス |
| **合計** | | **18** | |

### テストファイル

- `backend/tests/unit/test_handler_ai_service_factory.py` (新規作成)

### テストフィクスチャ

既存の `conftest.py` フィクスチャを使用:
- `api_gateway_event`: API Gateway HTTP API v2 イベント生成
- `lambda_context`: Lambda コンテキストモック

---

## 信頼性レベルサマリー

| 項目 | 信頼性 | 根拠 |
|------|--------|------|
| handler.py import 変更 | 🔵 | TASK-0056 定義・ai_service.py 実装 |
| handler.py グローバル変数削除 | 🔵 | TASK-0056 定義・Factory パターン設計 |
| generate_cards ファクトリ統合 | 🔵 | TASK-0056 定義・REQ-SM-002/402 |
| _map_ai_error_to_http() | 🔵 | architecture.md エラーハンドリング・api-endpoints.md |
| template.yaml UseStrands パラメータ | 🔵 | TASK-0056 定義・REQ-SM-102/103 |
| template.yaml ShouldUseStrands | 🔵 | TASK-0056 定義 |
| template.yaml タイムアウト 60s | 🔵 | REQ-SM-401・api-endpoints.md |
| template.yaml 環境変数追加 | 🔵 | TASK-0056 定義・api-endpoints.md |
| template.yaml 新 Lambda 関数 | 🔵 | TASK-0056 定義・api-endpoints.md |
| template.yaml LogGroups | 🔵 | 既存パターン（ApiFunctionLogGroup 等） |
| template.yaml Outputs | 🔵 | 既存パターン（ApiFunctionArn 等） |
| env.json 既存関数更新 | 🔵 | TASK-0056 定義 |
| env.json 新規関数追加 | 🔵 | TASK-0056 定義 |
| スタブハンドラー (501) | 🔵 | TASK-0056 Notes「ハンドラーは後続タスクで実装」 |
| 後方互換性 | 🔵 | REQ-SM-402/405 |
| テストカバレッジ 80%+ | 🔵 | REQ-SM-404 |

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 16 | 100% |
| 🟡 黄信号 | 0 | 0% |
| 🔴 赤信号 | 0 | 0% |

**総合品質**: ✅ **高品質** (100% 青信号)

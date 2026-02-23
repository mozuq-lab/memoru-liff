# TDD Red フェーズ記録: TASK-0056 handler.py AIServiceFactory 統合

## 作成日時

2026-02-23

## 作成したテストケース一覧

| ID | カテゴリ | テスト名 | 失敗理由 | 信頼性 |
|----|---------|---------|---------|--------|
| TC-056-001 | A: Factory 統合 | generate_cards のファクトリ呼び出し確認 | `api.handler` に `create_ai_service` 属性なし | 🔵 |
| TC-056-002 | A: Factory 統合 | ファクトリ生成サービスへの引数伝播確認 | `api.handler` に `create_ai_service` 属性なし | 🔵 |
| TC-056-003 | B: エラーマッピング | AITimeoutError → 504 | `_map_ai_error_to_http` が handler.py に存在しない | 🔵 |
| TC-056-004 | B: エラーマッピング | AIRateLimitError → 429 | `_map_ai_error_to_http` が handler.py に存在しない | 🔵 |
| TC-056-005 | B: エラーマッピング | AIProviderError → 503 | `_map_ai_error_to_http` が handler.py に存在しない | 🔵 |
| TC-056-006 | B: エラーマッピング | AIParseError → 500 | `_map_ai_error_to_http` が handler.py に存在しない | 🔵 |
| TC-056-007 | B: エラーマッピング | AIInternalError → 500 | `_map_ai_error_to_http` が handler.py に存在しない | 🔵 |
| TC-056-008 | B: エラーマッピング | AIServiceError → 500 (汎用) | `_map_ai_error_to_http` が handler.py に存在しない | 🔵 |
| TC-056-009 | B: エラーマッピング | 全レスポンス application/json 確認 | `_map_ai_error_to_http` が handler.py に存在しない | 🔵 |
| TC-056-010 | C: 互換性 | generate_cards レスポンス後方互換性 | `api.handler` に `create_ai_service` 属性なし | 🔵 |
| TC-056-011 | C: 互換性 | generate_cards AITimeoutError → 504 | `api.handler` に `create_ai_service` 属性なし | 🔵 |
| TC-056-012 | C: 互換性 | generate_cards AIRateLimitError → 429 | `api.handler` に `create_ai_service` 属性なし | 🔵 |
| TC-056-013 | C: 互換性 | generate_cards AIProviderError → 503 | `api.handler` に `create_ai_service` 属性なし | 🔵 |
| TC-056-014 | D: スタブ | grade_ai_handler → 501 | `grade_ai_handler` が handler.py に存在しない | 🔵 |
| TC-056-015 | D: スタブ | advice_handler → 501 | `advice_handler` が handler.py に存在しない | 🔵 |
| TC-056-016 | E: template.yaml | UseStrands パラメータ定義 | template.yaml に `UseStrands` パラメータなし | 🔵 |
| TC-056-017 | E: template.yaml | ShouldUseStrands コンディション | template.yaml に `Conditions` セクションなし | 🔵 |
| TC-056-018 | E: template.yaml | Global タイムアウト 60 秒 | template.yaml の Timeout が 30（60 ではない） | 🔵 |
| TC-056-019 | E: template.yaml | USE_STRANDS 環境変数定義 | Globals の環境変数に `USE_STRANDS` なし | 🔵 |
| TC-056-020 | E: template.yaml | 新 Lambda 関数定義 | `ReviewsGradeAiFunction`, `AdviceFunction` なし | 🔵 |
| TC-056-021 | E: template.yaml | 新 Lambda イベントルート | 新関数が存在しないため検証不可 | 🔵 |
| TC-056-022 | E: template.yaml | 新 LogGroup 定義 | `ReviewsGradeAiFunctionLogGroup` 等なし | 🔵 |
| TC-056-023 | E: template.yaml | 新 Outputs 定義 | `ReviewsGradeAiFunctionArn` 等なし | 🔵 |
| TC-056-024 | F: env.json | 既存関数の新環境変数 | env.json の既存関数に `USE_STRANDS` 等なし | 🔵 |
| TC-056-025 | F: env.json | 新規関数の環境変数 | env.json に `ReviewsGradeAiFunction` 等なし | 🔵 |
| TC-056-026 | G: エッジケース | BedrockTimeoutError → 504（多重継承） | `_map_ai_error_to_http` が handler.py に存在しない | 🔵 |
| TC-056-027 | G: エッジケース | BedrockRateLimitError → 429（多重継承） | `_map_ai_error_to_http` が handler.py に存在しない | 🔵 |

## テスト実行結果

```
27 failed in 0.75s
```

- **全 27 テスト: FAILED**（意図通りの失敗）
- **既存テスト: 322 passed**（影響なし）

## 失敗理由の分類

### カテゴリ A, C（Factory 統合・互換性）: AttributeError
```
AttributeError: <module 'api.handler'> does not have the attribute 'create_ai_service'
```
handler.py がまだ `BedrockService` 直接参照を使用しているため。

### カテゴリ B, G（エラーマッピング・エッジケース）: ImportError
```
ImportError: cannot import name '_map_ai_error_to_http' from 'api.handler'
```
`_map_ai_error_to_http()` 関数がまだ handler.py に存在しないため。

### カテゴリ D（スタブハンドラー）: ImportError
```
ImportError: cannot import name 'grade_ai_handler' from 'api.handler'
ImportError: cannot import name 'advice_handler' from 'api.handler'
```
スタブハンドラーがまだ handler.py に存在しないため。

### カテゴリ E（template.yaml）: AssertionError
- `UseStrands` パラメータなし
- `Conditions` セクションなし
- `Timeout: 30`（60 ではない）
- `USE_STRANDS` 環境変数なし
- `ReviewsGradeAiFunction`, `AdviceFunction` なし
- 対応する LogGroup, Outputs なし

### カテゴリ F（env.json）: AssertionError
- 既存関数に `USE_STRANDS`, `OLLAMA_HOST`, `OLLAMA_MODEL` なし
- `ReviewsGradeAiFunction`, `AdviceFunction` エントリなし

## テストファイル

`backend/tests/unit/test_handler_ai_service_factory.py`

## 技術的注意事項

- template.yaml の YAML パース: CloudFormation 固有タグ (`!Ref`, `!Sub`, `!If`, `!Equals` 等) を処理するために `_CFnLoader` カスタムローダーを定義した
- `yaml.safe_load` ではこれらのタグが処理できず `ConstructorError` になるため

## Green フェーズで実装すべき内容

### handler.py の変更

1. **import 変更**: `from services.bedrock import BedrockService, ...` を削除し、`from services.ai_service import create_ai_service, AIServiceError, AITimeoutError, AIRateLimitError, AIInternalError, AIParseError, AIProviderError` に置換
2. **グローバル変数削除**: `bedrock_service = BedrockService()` を削除
3. **`_map_ai_error_to_http()` 関数追加**: 5 種類の例外を HTTP ステータスにマッピング
   - `AITimeoutError` → 504, "AI service timeout"
   - `AIRateLimitError` → 429, "AI service rate limit exceeded"
   - `AIProviderError` → 503, "AI service unavailable"
   - `AIParseError` → 500, "AI service response parse error"
   - `AIInternalError` / `AIServiceError` → 500, "AI service error"
4. **`generate_cards()` 改修**: `bedrock_service.generate_cards()` → `create_ai_service().generate_cards()`、エラーハンドリングを `_map_ai_error_to_http()` 経由に変更
5. **スタブハンドラー追加**:
   - `grade_ai_handler(event, context)` → `{"statusCode": 501, "headers": {"Content-Type": "application/json"}, "body": "{\"error\": \"Not implemented\"}"}`
   - `advice_handler(event, context)` → 同形式

### template.yaml の変更

1. `Globals.Function.Timeout: 60`（30 から変更）
2. `Parameters` に `UseStrands` 追加（Type: String, Default: "false", AllowedValues: ["true", "false"]）
3. `Conditions` に `ShouldUseStrands: !Equals [!Ref UseStrands, "true"]` 追加
4. `Globals.Function.Environment.Variables` に `USE_STRANDS: !Ref UseStrands`, `OLLAMA_HOST`, `OLLAMA_MODEL` 追加
5. `ReviewsGradeAiFunction` 追加（Handler: api.handler.grade_ai_handler, Timeout: 60, MemorySize: 512, Path: /reviews/{cardId}/grade-ai, Method: POST）
6. `AdviceFunction` 追加（Handler: api.handler.advice_handler, Timeout: 60, MemorySize: 512, Path: /advice, Method: GET）
7. `ReviewsGradeAiFunctionLogGroup`, `AdviceFunctionLogGroup` 追加
8. `ReviewsGradeAiFunctionArn`, `AdviceFunctionArn` を Outputs に追加

### env.json の変更

1. 既存 3 関数（ApiFunction, LineWebhookFunction, DuePushJobFunction）に `USE_STRANDS: "false"`, `OLLAMA_HOST: "http://localhost:11434"`, `OLLAMA_MODEL: "neural-chat"` 追加
2. `ReviewsGradeAiFunction`, `AdviceFunction` の設定ブロックを追加

# TDD 開発メモ: handler-ai-service-factory-integration

## 概要

- 機能名: handler.py AIServiceFactory 統合 + template.yaml 更新
- 開発開始: 2026-02-23
- 現在のフェーズ: **完了**（Red → Green → Refactor）

## 関連ファイル

- 元タスクファイル: `docs/tasks/ai-strands-migration/TASK-0056.md`
- 要件定義: `docs/implements/ai-strands-migration/TASK-0056/ai-service-factory-integration-requirements.md`
- テストケース定義: `docs/implements/ai-strands-migration/TASK-0056/testcases.md`
- 実装ファイル: `backend/src/api/handler.py`
- テストファイル: `backend/tests/unit/test_handler_ai_service_factory.py`（新規作成）
- Red フェーズ記録: `docs/implements/ai-strands-migration/TASK-0056/handler-ai-service-factory-integration-red-phase.md`

## Red フェーズ（失敗するテスト作成）

### 作成日時

2026-02-23

### テストケース概要

全 27 テストケースを 7 カテゴリで実装:
- **A: Factory 統合** (2 テスト): `create_ai_service()` の呼び出し確認、引数伝播確認
- **B: エラーマッピング** (7 テスト): `_map_ai_error_to_http()` の各例外タイプ → HTTP ステータスマッピング確認
- **C: 互換性** (4 テスト): `generate_cards` エンドポイントの後方互換性、各エラーハンドリング統合確認
- **D: スタブハンドラー** (2 テスト): `grade_ai_handler`, `advice_handler` の 501 レスポンス確認
- **E: template.yaml** (8 テスト): UseStrands パラメータ、コンディション、タイムアウト、新 Lambda 関数、LogGroup、Outputs
- **F: env.json** (2 テスト): 既存関数の新環境変数、新規関数の設定
- **G: エッジケース** (2 テスト): Bedrock 例外の多重継承による AIServiceError 階層経由マッピング

### テスト実行結果

```bash
cd backend && pytest tests/unit/test_handler_ai_service_factory.py -v
# 27 failed in 0.75s（意図通りの失敗）

cd backend && pytest tests/unit/ --ignore=tests/unit/test_handler_ai_service_factory.py -q
# 322 passed in 13.73s（既存テストへの影響なし）
```

### 主な失敗内容

1. `AttributeError: api.handler does not have the attribute 'create_ai_service'`
   - handler.py がまだ `BedrockService` 直接参照を使用している
2. `ImportError: cannot import name '_map_ai_error_to_http' from 'api.handler'`
   - エラーマッピング関数が未実装
3. `ImportError: cannot import name 'grade_ai_handler'/'advice_handler' from 'api.handler'`
   - スタブハンドラーが未実装
4. `AssertionError: 'UseStrands' not in parameters` 等
   - template.yaml に新設定が未追加
5. `AssertionError: 'USE_STRANDS' not in func_vars` 等
   - env.json に新環境変数が未追加

### 技術的ポイント

- CloudFormation タグ処理: `yaml.safe_load` では `!Ref`, `!Sub`, `!Equals` 等を処理できないため、テスト内でカスタム `_CFnLoader` を定義
- 全テストメソッドは同期（`def`）- `async def` は不要
- 既存 conftest.py の `api_gateway_event`, `lambda_context` フィクスチャを使用
- 信頼性レベル: 全 27 テストが 🔵（要件定義書から直接確定）

### 次のフェーズへの要求事項

Greenフェーズで以下を実装:

**handler.py**:
1. import を `create_ai_service` + AI*Error クラスに変更
2. `bedrock_service = BedrockService()` グローバル変数を削除
3. `_map_ai_error_to_http(error)` 関数を追加
4. `generate_cards()` を factory パターンに改修
5. `grade_ai_handler(event, context)` スタブを追加
6. `advice_handler(event, context)` スタブを追加

**template.yaml**:
1. `Globals.Function.Timeout: 60`
2. `UseStrands` パラメータ追加
3. `ShouldUseStrands` コンディション追加
4. `USE_STRANDS`, `OLLAMA_HOST`, `OLLAMA_MODEL` 環境変数追加
5. `ReviewsGradeAiFunction`, `AdviceFunction` 追加
6. 対応する LogGroup, Outputs 追加

**env.json**:
1. 既存 3 関数に `USE_STRANDS`, `OLLAMA_HOST`, `OLLAMA_MODEL` 追加
2. `ReviewsGradeAiFunction`, `AdviceFunction` エントリを追加

## Refactor フェーズ（品質改善）

### 実施日時

2026-02-23

### 改善内容

1. **`_map_ai_error_to_http` の冗長ブランチ除去**: `AIInternalError` と汎用 else が同一レスポンスを返す重複を除去。ガード節スタイルに統一
2. **`generate_cards` の例外ハンドリング簡潔化**: 再インスタンス化を廃止し、`AIServiceError` 基底クラスで一括キャッチして元の例外オブジェクトをそのまま `_map_ai_error_to_http` に渡す
3. **成功時のログ追加**: モデル種別・カード枚数・処理時間のメトリクスログを追加
4. **スタブハンドラーのセクション分離**: 専用コメントセクションを設け、後続タスク番号（TASK-0057, TASK-0060）を明記
5. **未使用 import の削除**: `BadRequestError`, `LineApiError`, `UserSettingsResponse` の 3 件を削除
6. **日本語コメント強化**: 各エラー種別の意味と HTTP ステータス対応をインラインコメントで明示

### テスト実行結果

```
405 passed in 15.05s（全テスト通過）
```

### 品質評価

✅ **高品質**: セキュリティ・パフォーマンス上の重大課題なし。全テスト通過。

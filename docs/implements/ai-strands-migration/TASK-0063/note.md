# TASK-0063: Phase 3 統合テスト - 調査ノート

## 1. タスクファイルと実コードベースの乖離

TASK-0063.md のテストコードは**擬似コード**であり、実際のコードベースと複数の乖離がある。

### 1.1 存在しない API / パターン

| タスクファイルの記述 | 実際のコードベース |
|---|---|
| `test_client.post("/cards/generate", ...)` | `test_client` は存在しない。`app.resolve(event, context)` でテストする |
| `test_client.post("/reviews/{card_id}/grade-ai", ...)` | `grade_ai_handler(event, context)` を直接呼び出す |
| `test_client.get("/advice", ...)` | `advice_handler(event, context)` を直接呼び出す |
| `get_test_token(user_id)` | 存在しない。conftest.py の `api_gateway_event()` fixture で JWT claims をモックする |
| `get_ai_service()` | 存在しない。`create_ai_service()` が正しいファクトリ関数名 |
| `from services.exceptions import AITimeoutError` | `from services.ai_service import AITimeoutError` が正しいインポートパス |
| `BedrockAIService` | `BedrockService` が正しいクラス名（`services.bedrock` モジュール） |
| `StrandsAIService.generate_card` | メソッド名は `generate_cards`（複数形） |
| `request_data = {"topic": "Japanese", ...}` | 正しいリクエスト形式は `{"input_text": "...", "card_count": 3, "difficulty": "medium", "language": "ja"}` |

### 1.2 エンドポイントのルーティング構造

3 つの AI エンドポイントは**異なるルーティング方式**を使用しており、テスト方法も異なる。

| エンドポイント | ルーティング方式 | テスト呼び出し方法 |
|---|---|---|
| `POST /cards/generate` | `APIGatewayHttpResolver` (`@app.post()`) | `handler(event, context)` → `app.resolve()` 経由 |
| `POST /reviews/{cardId}/grade-ai` | 独立 Lambda 関数 | `grade_ai_handler(event, context)` 直接呼び出し |
| `GET /advice` | 独立 Lambda 関数 | `advice_handler(event, context)` 直接呼び出し |

### 1.3 イベント形式の違い

- `POST /cards/generate`: conftest の `api_gateway_event()` fixture でイベント生成。`app.resolve()` で処理される。
- `grade_ai_handler` / `advice_handler`: `pathParameters.cardId`（camelCase）や `requestContext.authorizer.jwt.claims.sub` を持つ生の API Gateway HTTP API v2 イベントを直接受け取る。既存テストの `_make_grade_ai_event()` / `_make_advice_event()` ヘルパーがある。

## 2. 既存テストのカバレッジ分析

### 2.1 現在のテスト数: 636 テスト

### 2.2 フィーチャーフラグ関連の既存テスト

**`test_handler_ai_service_factory.py` (27 テスト)** - TASK-0056 由来:
- カテゴリ A: ファクトリ統合テスト（`create_ai_service()` 呼び出し確認、引数伝播確認）
- カテゴリ B: `_map_ai_error_to_http()` エラーマッピング（全 6 例外タイプ）
- カテゴリ C: `generate_cards` エンドポイント互換性（レスポンス構造、エラーハンドリング）
- カテゴリ D: スタブハンドラー（`grade_ai_handler` が 501 でないこと確認）
- カテゴリ E-F: `template.yaml` / `env.json` 設定検証
- カテゴリ G: Bedrock 例外の多重継承マッピング

**`test_migration_compat.py` (31 テスト)** - TASK-0058 由来:
- Category 1: API レスポンス形式一致（Strands vs Bedrock GenerationResult 構造比較）
- Category 2: エラーハンドリング互換性（全エラータイプ、エラーマッピングテーブル完全性）
- Category 3: フィーチャーフラグ切替テスト（`create_ai_service()` の true/false/unset/explicit override）
- Category 4: GenerationResult 有効性（AIService Protocol 適合性）
- Category 5: 移行エッジケース（空カード、不完全データ、Markdown JSON、"AI生成" タグ）
- Category 6: 既存テスト保護（`pytest.main()` による既存テスト一括実行）

**`test_handler_grade_ai.py` (35 テスト)** - TASK-0060 由来:
- 認証、パスパラメータ、バリデーション、カードエラー、AI 呼び出し、正常系レスポンス、AI エラーハンドリング（全 5 例外タイプ + ファクトリ初期化失敗 + 予期しない例外）、ロギング

**`test_handler_advice.py` (28 テスト)** - TASK-0062 由来:
- 認証、データフロー、正常系レスポンス、AI エラーハンドリング（全 5 例外タイプ + ファクトリ初期化失敗 + 予期しない例外）、DB エラー、ロギング

### 2.3 既にカバー済みの領域

| テスト観点 | カバー済み？ | 既存テストファイル |
|---|---|---|
| `create_ai_service()` フラグ切替（true/false/unset） | YES | `test_migration_compat.py` TC-FLAG-001〜005 |
| `_map_ai_error_to_http()` 全例外タイプ | YES | `test_handler_ai_service_factory.py` カテゴリ B, `test_migration_compat.py` TC-ERROR |
| `generate_cards` エンドポイント → ファクトリ使用 | YES | `test_handler_ai_service_factory.py` カテゴリ A |
| `generate_cards` エンドポイント → AI エラーハンドリング | YES | `test_handler_ai_service_factory.py` カテゴリ C |
| `grade_ai_handler` → ファクトリ使用 | YES | `test_handler_grade_ai.py` TC-060-AI-001 |
| `grade_ai_handler` → 全 AI エラーハンドリング | YES | `test_handler_grade_ai.py` TC-060-ERR-001〜007 |
| `advice_handler` → ファクトリ使用 | YES | `test_handler_advice.py` TC-062-FLOW-002 |
| `advice_handler` → 全 AI エラーハンドリング | YES | `test_handler_advice.py` TC-062-ERR-001〜007 |
| Bedrock 例外の多重継承マッピング | YES | `test_handler_ai_service_factory.py` カテゴリ G, `test_migration_compat.py` TC-ERROR-007 |
| AIService Protocol 適合性 | YES | `test_migration_compat.py` TC-RESULT-003 |
| `template.yaml` / `env.json` 設定検証 | YES | `test_handler_ai_service_factory.py` カテゴリ E-F |

### 2.4 未カバーの領域（統合テストとして必要なもの）

| テスト観点 | 説明 | 重要度 |
|---|---|---|
| **フラグ切替 × 全 3 エンドポイント一貫性** | `USE_STRANDS` 切替が `generate_cards`, `grade_ai_handler`, `advice_handler` の全てで一貫して動作することを 1 テストクラスで横断的に検証 | High |
| **全 3 エンドポイント × 全 5 AI エラーの横断テスト** | 各エンドポイントが同じ AI エラーに対して同じ HTTP ステータスを返すことの横断的一貫性 | High |
| **エンドポイント E2E フロー比較** | 3 つのエンドポイントの E2E フローが全て create_ai_service → AI呼び出し → レスポンス変換の統一パターンに従うことの確認 | Medium |
| **既存テスト 636+ 保護** | 全テストスイート実行による回帰テスト | High |
| **フラグ切替時の全エンドポイント応答整合性** | USE_STRANDS=true/false の両方で全 3 エンドポイントが 200 を返すことの統合検証 | High |

## 3. テスト実装上の重要な注意点

### 3.1 モジュールインポートとパッチ対象

- `create_ai_service` のパッチ: `api.handler.create_ai_service` （handler.py 内でインポート済みのシンボル）
- `card_service` のパッチ: `api.handler.card_service` （モジュールレベルグローバル変数）
- `review_service` のパッチ: `api.handler.review_service` （モジュールレベルグローバル変数）
- `StrandsAIService` のパッチ: `services.strands_service.Agent` + `services.strands_service.BedrockModel`
- `BedrockService` のパッチ: `services.bedrock.boto3.client`

### 3.2 conftest.py の環境変数

conftest.py は `USE_STRANDS` を設定していない。`os.getenv("USE_STRANDS", "false")` のデフォルトで BedrockService が使われる。テストで USE_STRANDS を切り替える場合は `patch.dict(os.environ, ...)` を使用する。

### 3.3 テスト信頼性

テストは全てモックベース。実際の AI サービス（Bedrock/Strands）は呼び出さない。テストの価値は「フラグ切替 → 正しいサービスインスタンス → ハンドラーからの統一レスポンス」の統合フローにある。

## 4. 統合テストの設計方針

### 重複を避ける
既存テストが個別にカバー済みの以下は **再テストしない**:
- `_map_ai_error_to_http()` の個別マッピング（既に 27+ テストでカバー済み）
- 個別エンドポイントの認証、バリデーション、パスパラメータ
- `create_ai_service()` の個別フラグ動作（既に 5 テストでカバー済み）

### 統合テストとしての付加価値
以下の **横断的・cross-component** テストに集中する:
1. **フラグ切替一貫性**: 同一のフラグ設定が全 3 エンドポイントに一貫して反映されること
2. **エラーハンドリング一貫性**: 全 3 エンドポイントが同一の AI エラーに対して同一の HTTP ステータスを返すこと
3. **E2E フロー統合**: 各エンドポイントの auth → service → AI → response の完全フロー
4. **回帰保護**: 636+ 既存テストが全て PASS すること

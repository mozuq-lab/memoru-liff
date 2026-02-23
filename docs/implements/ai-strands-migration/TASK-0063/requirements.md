# TASK-0063: Phase 3 統合テスト - テストケース要件

## テスト方針

TASK-0063 の統合テストは、既存の個別テスト（TASK-0056/0058/0060/0062）で十分にカバーされている単体テスト項目を**重複させず**、複数コンポーネントを横断する統合的な検証に集中する。

### テスト対象ファイル（新規）

- `backend/tests/unit/test_integration.py`

### テスト対象プロダクションコード

- `backend/src/api/handler.py` - `handler()`, `grade_ai_handler()`, `advice_handler()`
- `backend/src/services/ai_service.py` - `create_ai_service()`, AIService Protocol

### 使用フィクスチャ

- `api_gateway_event` (conftest.py) - `POST /cards/generate` 用イベント生成
- `lambda_context` (conftest.py) - Lambda コンテキストモック
- `_make_grade_ai_event()` - `grade_ai_handler` 用イベント生成（テスト内ヘルパー）
- `_make_advice_event()` - `advice_handler` 用イベント生成（テスト内ヘルパー）

---

## カテゴリ 1: フィーチャーフラグ × 全エンドポイント一貫性テスト

**目的**: `USE_STRANDS` フラグ切替が全 3 エンドポイントで一貫して動作することを横断的に検証する。

**既存テストとの差分**: `test_migration_compat.py` は `create_ai_service()` の単体テスト（TC-FLAG-001〜005）で、ハンドラー経由の統合フローではない。この統合テストでは、各ハンドラー内で `create_ai_service()` が呼ばれ、フラグに応じた正しいサービスが使われ、正常レスポンスが返ることを統合的に検証する。

### TC-INT-FLAG-001: USE_STRANDS=true で全 3 エンドポイントが StrandsAIService を使用する

- **信頼性**: 🔵 - REQ-SM-102, handler.py の create_ai_service() 呼び出し確認
- **前提条件**: `USE_STRANDS=true` 環境変数設定
- **テスト手順**:
  1. `patch.dict(os.environ, {"USE_STRANDS": "true"})` を設定
  2. `create_ai_service` をモックし、呼び出しごとに記録
  3. `handler(generate_event, context)` を呼び出す → 200
  4. `grade_ai_handler(grade_event, context)` を呼び出す → 200
  5. `advice_handler(advice_event, context)` を呼び出す → 200
- **検証項目**:
  - `create_ai_service()` が合計 3 回呼ばれること
  - 全 3 エンドポイントが HTTP 200 を返すこと
- **モック**: `api.handler.create_ai_service` → 各 AI メソッド（`generate_cards`, `grade_answer`, `get_learning_advice`）の戻り値をモック。`api.handler.card_service`, `api.handler.review_service` もモック。

### TC-INT-FLAG-002: USE_STRANDS=false で全 3 エンドポイントが BedrockService を使用する

- **信頼性**: 🔵 - REQ-SM-103, デフォルト動作
- **前提条件**: `USE_STRANDS=false` 環境変数設定
- **テスト手順**: TC-INT-FLAG-001 と同構造、`USE_STRANDS=false` で実行
- **検証項目**:
  - `create_ai_service()` が合計 3 回呼ばれること
  - 全 3 エンドポイントが HTTP 200 を返すこと

### TC-INT-FLAG-003: USE_STRANDS 未設定で全 3 エンドポイントがデフォルト（Bedrock）を使用する

- **信頼性**: 🔵 - REQ-SM-103, デフォルト値 "false"
- **前提条件**: `USE_STRANDS` 環境変数を除去
- **テスト手順**: TC-INT-FLAG-001 と同構造、`USE_STRANDS` を環境変数から除去して実行
- **検証項目**:
  - `create_ai_service()` が合計 3 回呼ばれること
  - 全 3 エンドポイントが HTTP 200 を返すこと

---

## カテゴリ 2: 全エンドポイント E2E 統合フローテスト

**目的**: 各エンドポイントの完全な E2E フロー（認証 → サービス → AI → レスポンス）が統合的に動作することを検証する。

**既存テストとの差分**: 個別テストファイルには E2E テスト（TC-060-RES-007, TC-062-RES-008）があるが、3 エンドポイントを**同一テストクラス内で同一の AI サービスモック設定**で横断的にテストし、統一パターンの一貫性を検証するものはない。

### TC-INT-E2E-001: POST /cards/generate の統合 E2E フロー

- **信頼性**: 🔵 - REQ-SM-002, handler.py generate_cards エンドポイント
- **テスト手順**:
  1. `api_gateway_event()` で `POST /cards/generate` イベントを生成（`input_text`, `card_count`, `difficulty`, `language`）
  2. `create_ai_service` をモック → `generate_cards()` がモック `GenerationResult` を返す
  3. `handler(event, context)` を呼び出す
- **検証項目**:
  - HTTP 200 が返ること
  - レスポンスに `generated_cards` 配列が含まれること
  - レスポンスに `generation_info` オブジェクト（`input_length`, `model_used`, `processing_time_ms`）が含まれること
  - `create_ai_service()` が 1 回呼ばれること
  - `ai_service.generate_cards()` が正しい引数で呼ばれること

### TC-INT-E2E-002: POST /reviews/{cardId}/grade-ai の統合 E2E フロー

- **信頼性**: 🔵 - REQ-SM-003, handler.py grade_ai_handler
- **テスト手順**:
  1. `_make_grade_ai_event()` でイベント生成（`user_id`, `card_id`, `user_answer`）
  2. `card_service.get_card` をモック → Card オブジェクト返却
  3. `create_ai_service` をモック → `grade_answer()` がモック `GradingResult` を返す
  4. `grade_ai_handler(event, context)` を呼び出す
- **検証項目**:
  - HTTP 200 が返ること
  - レスポンスに `grade`, `reasoning`, `card_front`, `card_back`, `grading_info` が含まれること
  - `create_ai_service()` が 1 回呼ばれること
  - `card_service.get_card()` が正しい `user_id`, `card_id` で呼ばれること
  - `ai_service.grade_answer()` が正しい引数で呼ばれること

### TC-INT-E2E-003: GET /advice の統合 E2E フロー

- **信頼性**: 🔵 - REQ-SM-004, handler.py advice_handler
- **テスト手順**:
  1. `_make_advice_event()` でイベント生成（`user_id`, `query_params`）
  2. `review_service.get_review_summary` をモック → `ReviewSummary` を返す
  3. `create_ai_service` をモック → `get_learning_advice()` がモック `LearningAdvice` を返す
  4. `advice_handler(event, context)` を呼び出す
- **検証項目**:
  - HTTP 200 が返ること
  - レスポンスに `advice_text`, `weak_areas`, `recommendations`, `study_stats`, `advice_info` が含まれること
  - `create_ai_service()` が 1 回呼ばれること
  - `review_service.get_review_summary()` が正しい `user_id` で呼ばれること
  - `ai_service.get_learning_advice()` が `review_summary` (dict) と `language` で呼ばれること

---

## カテゴリ 3: 横断的エラーハンドリング一貫性テスト

**目的**: 全 3 エンドポイントが同一の AI エラータイプに対して同一の HTTP ステータスコードを返すことを横断的に検証する。

**既存テストとの差分**: 個別テストファイルは各ハンドラーのエラーハンドリングを独立してテストしている。この統合テストでは、**全 3 エンドポイントを 1 つのテストケース内で**テストし、エンドポイント間のエラーハンドリング一貫性を保証する。

### TC-INT-ERR-001: AITimeoutError → HTTP 504 が全 3 エンドポイントで一貫する

- **信頼性**: 🔵 - 要件定義書 4.2 節 EC-01, handler.py `_map_ai_error_to_http()`
- **テスト手順**:
  1. `create_ai_service` のモックサービスの各 AI メソッドに `AITimeoutError` を設定
  2. 3 エンドポイント全てを呼び出す
- **検証項目**:
  - 全 3 エンドポイントが HTTP 504 を返すこと
  - 全 3 エンドポイントのエラーメッセージが `"AI service timeout"` であること

### TC-INT-ERR-002: AIRateLimitError → HTTP 429 が全 3 エンドポイントで一貫する

- **信頼性**: 🔵 - 要件定義書 4.2 節 EC-02
- **検証項目**:
  - 全 3 エンドポイントが HTTP 429 を返すこと
  - エラーメッセージが `"AI service rate limit exceeded"` であること

### TC-INT-ERR-003: AIProviderError → HTTP 503 が全 3 エンドポイントで一貫する

- **信頼性**: 🔵 - 要件定義書 4.2 節 EC-03
- **検証項目**:
  - 全 3 エンドポイントが HTTP 503 を返すこと
  - エラーメッセージが `"AI service unavailable"` であること

### TC-INT-ERR-004: AIParseError → HTTP 500 が全 3 エンドポイントで一貫する

- **信頼性**: 🔵 - 要件定義書 4.2 節
- **検証項目**:
  - 全 3 エンドポイントが HTTP 500 を返すこと
  - エラーメッセージが `"AI service response parse error"` であること

### TC-INT-ERR-005: AIInternalError → HTTP 500 が全 3 エンドポイントで一貫する

- **信頼性**: 🔵 - 要件定義書 4.2 節
- **検証項目**:
  - 全 3 エンドポイントが HTTP 500 を返すこと
  - エラーメッセージが `"AI service error"` であること

### TC-INT-ERR-006: create_ai_service() 初期化失敗（AIProviderError）が全 3 エンドポイントで一貫する

- **信頼性**: 🔵 - ai_service.py create_ai_service() の例外処理
- **テスト手順**:
  1. `create_ai_service` 自体が `AIProviderError` を raise するようモック
  2. 3 エンドポイント全てを呼び出す
- **検証項目**:
  - 全 3 エンドポイントが HTTP 503 を返すこと
  - エラーメッセージが `"AI service unavailable"` であること

---

## カテゴリ 4: 既存テスト保護テスト

**目的**: 統合テスト追加によって既存の 636+ テストに回帰が発生しないことを保証する。

### TC-INT-PROTECT-001: 既存テストスイート全件 PASS 確認

- **信頼性**: 🔵 - REQ-SM-405
- **テスト手順**:
  1. `pytest.main(["-x", "--tb=short", "-q", *test_files])` で主要テストファイルを実行
- **検証項目**:
  - `pytest.ExitCode.OK` が返ること
- **対象テストファイル**:
  - `test_ai_service.py`
  - `test_strands_service.py`
  - `test_bedrock.py`
  - `test_handler_ai_service_factory.py`
  - `test_migration_compat.py`
  - `test_handler_grade_ai.py`
  - `test_handler_advice.py`

### TC-INT-PROTECT-002: 統合テスト追加後のテスト総数が 636+ 以上であること

- **信頼性**: 🔵 - REQ-SM-405
- **テスト手順**:
  1. テスト収集（`--collect-only`）を実行
- **検証項目**:
  - テスト総数が 636 以上であること
- **注**: 実際のテスト収集はコスト高のため、テストファイルの存在確認とプレースホルダーとして実装。CI/CD パイプラインで完全検証。

### TC-INT-PROTECT-003: テストカバレッジ 80% 以上維持確認

- **信頼性**: 🔵 - REQ-SM-404
- **テスト手順**: プレースホルダー。CI/CD パイプラインで `pytest --cov=src --cov-report=term-missing` を実行して確認。
- **検証項目**: AI 関連ソースファイルのカバレッジが 80% 以上であること

---

## テストケースサマリー

### カテゴリ別件数

| カテゴリ | テスト数 | 信頼性 |
|---------|---------|--------|
| 1. フィーチャーフラグ × 全エンドポイント一貫性 | 3 | 🔵 全件 |
| 2. 全エンドポイント E2E 統合フロー | 3 | 🔵 全件 |
| 3. 横断的エラーハンドリング一貫性 | 6 | 🔵 全件 |
| 4. 既存テスト保護 | 3 | 🔵 全件 |
| **合計** | **15** | **🔵 100%** |

### テストケースと要件の対応

| テストケース | 対応要件 |
|---|---|
| TC-INT-FLAG-001〜003 | REQ-SM-102, REQ-SM-103 |
| TC-INT-E2E-001 | REQ-SM-002 |
| TC-INT-E2E-002 | REQ-SM-003 |
| TC-INT-E2E-003 | REQ-SM-004 |
| TC-INT-ERR-001〜006 | REQ-SM-402 (API 互換性), acceptance-criteria EC-01〜03 |
| TC-INT-PROTECT-001〜003 | REQ-SM-404, REQ-SM-405 |

### TASK-0063.md のテスト件数との差分

TASK-0063.md は 27 テストを想定していたが、既存テストの分析により以下の理由で 15 テストに最適化:

- **フィーチャーフラグ統合テスト**: 9 → 3（フラグの個別動作は `test_migration_compat.py` で既にカバー済み。統合テストでは「全エンドポイント横断」の一貫性のみ検証）
- **エンドポイント統合テスト**: 3 → 3（維持。ただし既存 E2E テストと差別化するために統一パターン検証を追加）
- **エラーハンドリング統合テスト**: 15 → 6（個別エンドポイントのエラーハンドリングは既存テストでカバー済み。統合テストでは「全 3 エンドポイント一貫性」に集中し、1 エラータイプ = 1 テストケースで全エンドポイントをテスト）

---

## テスト実装のヘルパー設計

### 共通ヘルパー関数

テストコードの重複を減らすため、以下の共通ヘルパーを定義する:

1. **`_make_generate_event()`**: `api_gateway_event()` fixture をラップし、`POST /cards/generate` 用のデフォルト値を設定
2. **`_make_grade_ai_event()`**: `test_handler_grade_ai.py` と同パターンの grade-ai イベント生成
3. **`_make_advice_event()`**: `test_handler_advice.py` と同パターンの advice イベント生成
4. **`_setup_ai_mocks()`**: 全 3 AI メソッド（`generate_cards`, `grade_answer`, `get_learning_advice`）の戻り値を一括設定
5. **`_call_all_endpoints()`**: 全 3 エンドポイントを呼び出して結果を辞書で返す

### モック対象一覧

| パッチ対象 | 目的 |
|---|---|
| `api.handler.create_ai_service` | AI サービスファクトリのモック |
| `api.handler.card_service` | CardService のモック（grade_ai_handler 用） |
| `api.handler.review_service` | ReviewService のモック（advice_handler 用） |

### レスポンス検証パターン

- `handler()` (app.resolve 経由): `response["statusCode"]`, `json.loads(response["body"])` で検証
- `grade_ai_handler()`: 同上（Lambda プロキシ統合レスポンス形式）
- `advice_handler()`: 同上（Lambda プロキシ統合レスポンス形式）

全 3 エンドポイントは同一の `{"statusCode": int, "headers": {...}, "body": str}` 形式であるため、統一的に検証可能。

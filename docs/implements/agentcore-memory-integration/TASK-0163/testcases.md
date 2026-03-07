# TASK-0163: SessionManager ファクトリ実装 - テストケース一覧

**タスクID**: TASK-0163
**テストファイル**: `backend/tests/unit/test_tutor_session_factory.py`
**対象ファイル**: `backend/src/services/tutor_session_factory.py`

---

## テスト共通設定

### モック対象

| モック対象 | インポートパス | 理由 |
|-----------|--------------|------|
| `MemoryClient` | `bedrock_agentcore.memory.MemoryClient` | 外部 SDK のためモック化 |
| `AgentCoreMemorySessionManager` | `bedrock_agentcore.memory.integrations.strands.session_manager.AgentCoreMemorySessionManager` | 外部 SDK のためモック化 |
| `AgentCoreMemoryConfig` | `bedrock_agentcore.memory.integrations.strands.config.AgentCoreMemoryConfig` | 外部 SDK のためモック化 |
| `DynamoDBSessionManager` | `services.tutor_session_manager.DynamoDBSessionManager` | TASK-0164 で実装予定のためモック化 |

### テストフィクスチャ

- 各テストの `setUp` / `tearDown` で `tutor_session_factory._agentcore_client = None` にリセットする（シングルトン状態のクリア）
- 環境変数は `unittest.mock.patch.dict(os.environ, ...)` で制御する
- 遅延インポートのモック化には `unittest.mock.patch` を使用する

### 共通テストデータ

| パラメータ | 値 |
|-----------|-----|
| `session_id` | `"tutor_test-session-001"` |
| `user_id` | `"user-001"` |
| `AGENTCORE_MEMORY_ID` | `"test-memory-id"` |
| `TUTOR_SESSIONS_TABLE` | `"memoru-tutor-sessions-dev"` |

---

## 正常系テストケース

### TC-001-01: TUTOR_SESSION_BACKEND=agentcore + AGENTCORE_MEMORY_ID 設定時に AgentCoreMemorySessionManager が返される

**Given**:
- 環境変数 `TUTOR_SESSION_BACKEND` が `"agentcore"` に設定されている
- 環境変数 `AGENTCORE_MEMORY_ID` が `"test-memory-id"` に設定されている
- `MemoryClient`, `AgentCoreMemorySessionManager`, `AgentCoreMemoryConfig` がモック化されている

**When**:
- `create_tutor_session_manager("tutor_test-session-001", "user-001")` を呼び出す

**Then**:
- `AgentCoreMemoryConfig` が以下の引数で呼び出される:
  - `memory_id="test-memory-id"`
  - `session_id="tutor_test-session-001"`
  - `actor_id="user-001"`
- `AgentCoreMemorySessionManager` が `config` と `memory_client` を引数に呼び出される
- 戻り値が `AgentCoreMemorySessionManager` のモックインスタンスである

---

### TC-001-02: TUTOR_SESSION_BACKEND=dynamodb で DynamoDBSessionManager が返される

**Given**:
- 環境変数 `TUTOR_SESSION_BACKEND` が `"dynamodb"` に設定されている
- `DynamoDBSessionManager` がモック化されている

**When**:
- `create_tutor_session_manager("tutor_test-session-001", "user-001")` を呼び出す

**Then**:
- `DynamoDBSessionManager` が以下の引数で呼び出される:
  - `table_name="memoru-tutor-sessions-dev"`（デフォルト値）
  - `session_id="tutor_test-session-001"`
  - `user_id="user-001"`
- 戻り値が `DynamoDBSessionManager` のモックインスタンスである

---

### TC-103-01: ENVIRONMENT=dev + TUTOR_SESSION_BACKEND 未設定で DynamoDBSessionManager が返される

**Given**:
- 環境変数 `ENVIRONMENT` が `"dev"` に設定されている
- 環境変数 `TUTOR_SESSION_BACKEND` が設定されていない
- `DynamoDBSessionManager` がモック化されている

**When**:
- `create_tutor_session_manager("tutor_test-session-001", "user-001")` を呼び出す

**Then**:
- バックエンドが自動的に `"dynamodb"` と判定される
- `DynamoDBSessionManager` のモックインスタンスが返される

---

### TC-103-02: ENVIRONMENT=prod + TUTOR_SESSION_BACKEND 未設定で AgentCoreMemorySessionManager が返される

**Given**:
- 環境変数 `ENVIRONMENT` が `"prod"` に設定されている
- 環境変数 `TUTOR_SESSION_BACKEND` が設定されていない
- 環境変数 `AGENTCORE_MEMORY_ID` が `"test-memory-id"` に設定されている
- `MemoryClient`, `AgentCoreMemorySessionManager`, `AgentCoreMemoryConfig` がモック化されている

**When**:
- `create_tutor_session_manager("tutor_test-session-001", "user-001")` を呼び出す

**Then**:
- バックエンドが自動的に `"agentcore"` と判定される
- `AgentCoreMemorySessionManager` のモックインスタンスが返される

---

### TC-103-03: ENVIRONMENT=dev + TUTOR_SESSION_BACKEND=agentcore で明示指定が環境自動選択より優先される

**Given**:
- 環境変数 `ENVIRONMENT` が `"dev"` に設定されている
- 環境変数 `TUTOR_SESSION_BACKEND` が `"agentcore"` に設定されている
- 環境変数 `AGENTCORE_MEMORY_ID` が `"test-memory-id"` に設定されている
- `MemoryClient`, `AgentCoreMemorySessionManager`, `AgentCoreMemoryConfig` がモック化されている

**When**:
- `create_tutor_session_manager("tutor_test-session-001", "user-001")` を呼び出す

**Then**:
- 環境変数 `TUTOR_SESSION_BACKEND=agentcore` の明示指定が `ENVIRONMENT=dev` の自動選択ロジックより優先される
- `AgentCoreMemorySessionManager` のモックインスタンスが返される

---

## 異常系テストケース

### TC-001-E01: TUTOR_SESSION_BACKEND が不正な値の場合に ValueError が発生する

**Given**:
- 環境変数 `TUTOR_SESSION_BACKEND` が `"invalid"` に設定されている

**When**:
- `create_tutor_session_manager("tutor_test-session-001", "user-001")` を呼び出す

**Then**:
- `ValueError` が送出される
- エラーメッセージに `"Unknown TUTOR_SESSION_BACKEND: invalid"` が含まれる

---

### TC-001-E02: TUTOR_SESSION_BACKEND=agentcore + AGENTCORE_MEMORY_ID 未設定で TutorAIServiceError が発生する

**Given**:
- 環境変数 `TUTOR_SESSION_BACKEND` が `"agentcore"` に設定されている
- 環境変数 `AGENTCORE_MEMORY_ID` が設定されていない（または空文字列）

**When**:
- `create_tutor_session_manager("tutor_test-session-001", "user-001")` を呼び出す

**Then**:
- `TutorAIServiceError` が送出される
- エラーメッセージに `"AGENTCORE_MEMORY_ID is required for agentcore backend"` が含まれる

---

## シングルトンテストケース

### TC-SINGLETON-01: _get_agentcore_client() が複数回呼ばれても同一インスタンスを返す

**Given**:
- `MemoryClient` がモック化されている
- `tutor_session_factory._agentcore_client` が `None` にリセットされている

**When**:
- `_get_agentcore_client()` を 2 回呼び出す

**Then**:
- 1 回目と 2 回目の戻り値が同一オブジェクト（`is` で一致）である
- `MemoryClient()` コンストラクタは 1 回だけ呼び出される（`assert_called_once`）

---

## テストケースサマリー

| カテゴリ | テストID | テスト内容 | 期待結果 |
|---------|----------|----------|---------|
| 正常系 | TC-001-01 | agentcore バックエンド選択 | AgentCoreMemorySessionManager 返却 |
| 正常系 | TC-001-02 | dynamodb バックエンド選択 | DynamoDBSessionManager 返却 |
| 正常系 | TC-103-01 | dev 環境の自動選択 | DynamoDBSessionManager 返却 |
| 正常系 | TC-103-02 | prod 環境のデフォルト | AgentCoreMemorySessionManager 返却 |
| 正常系 | TC-103-03 | 明示指定が環境自動選択より優先 | AgentCoreMemorySessionManager 返却 |
| 異常系 | TC-001-E01 | 不正な値で ValueError | ValueError 送出 |
| 異常系 | TC-001-E02 | AGENTCORE_MEMORY_ID 未設定 | TutorAIServiceError 送出 |
| シングルトン | TC-SINGLETON-01 | 同一インスタンス返却 | MemoryClient() は 1 回だけ呼出 |

**合計**: 8 テストケース（正常系 5 / 異常系 2 / シングルトン 1）

# TASK-0163: SessionManager ファクトリ実装 - 詳細要件定義

**タスクID**: TASK-0163
**作成日**: 2026-03-07
**関連要件**: REQ-001, REQ-101, REQ-102, REQ-103, REQ-104, REQ-403, NFR-001
**実装ファイル**: `backend/src/services/tutor_session_factory.py`
**テストファイル**: `backend/tests/unit/test_tutor_session_factory.py`

---

## 1. 概要

`TUTOR_SESSION_BACKEND` 環境変数に基づいて適切な SessionManager 実装を返すファクトリ関数 `create_tutor_session_manager()` を実装する。AgentCoreMemoryClient のシングルトン初期化（コールドスタート最適化）を含む。

---

## 2. ファクトリ関数仕様

### 2.1 関数シグネチャ

```python
def create_tutor_session_manager(
    session_id: str,
    user_id: str,
    backend: str | None = None,
) -> SessionManager:
```

**引数**:

| 引数 | 型 | 必須 | 説明 |
|------|-----|------|------|
| `session_id` | `str` | Yes | チューターセッション ID（例: `"tutor_xxxx-xxxx"`） |
| `user_id` | `str` | Yes | ユーザー ID（AgentCore の `actor_id` として使用） |
| `backend` | `str \| None` | No | 明示的なバックエンド指定。`None` の場合は環境変数から自動判定 |

**戻り値**: Strands SDK `SessionManager` インターフェース準拠の実装

**例外**:

| 例外 | 条件 |
|------|------|
| `ValueError` | `backend` が `"agentcore"` / `"dynamodb"` 以外の不正な値 |
| `TutorAIServiceError` | `backend="agentcore"` 時に `AGENTCORE_MEMORY_ID` 環境変数が未設定 |

### 2.2 動作仕様

1. `backend` 引数が `None` の場合、環境変数からバックエンドを自動判定する（2.3 参照）
2. `backend` 引数が明示指定されている場合、環境変数の値よりも優先する
3. バックエンドに応じた SessionManager インスタンスを生成して返す
4. Logger でバックエンド選択結果をログ出力する

### 2.3 バックエンド選択ロジック

`backend` 引数が `None` の場合の判定フロー:

```
backend 引数が None?
+-- No  --> 引数の値をそのまま使用
+-- Yes --> TUTOR_SESSION_BACKEND 環境変数を参照
    +-- "agentcore" --> AgentCoreMemorySessionManager
    +-- "dynamodb"  --> DynamoDBSessionManager
    +-- その他の値  --> ValueError
    +-- 未設定（空文字列含む）
        +-- ENVIRONMENT 環境変数を参照
            +-- "dev"   --> DynamoDBSessionManager（自動選択）
            +-- その他  --> AgentCoreMemorySessionManager（デフォルト）
```

**判定ルールの詳細**:

| 優先度 | 条件 | 結果 |
|--------|------|------|
| 1 | `backend` 引数が明示指定 | 引数の値に従う |
| 2 | `TUTOR_SESSION_BACKEND` 環境変数が設定済み | 環境変数の値に従う |
| 3 | `ENVIRONMENT=dev` かつ `TUTOR_SESSION_BACKEND` 未設定 | `dynamodb` を自動選択 |
| 4 | `ENVIRONMENT` が `dev` 以外かつ `TUTOR_SESSION_BACKEND` 未設定 | `agentcore` をデフォルト選択 |

---

## 3. 各バックエンドの生成仕様

### 3.1 agentcore バックエンド

`AgentCoreMemorySessionManager` を生成する。

**前提条件**: `AGENTCORE_MEMORY_ID` 環境変数が設定されていること

**生成手順**:
1. `AGENTCORE_MEMORY_ID` 環境変数を取得する
2. 未設定の場合は `TutorAIServiceError` を送出する
3. `_get_agentcore_client()` でシングルトンの `MemoryClient` を取得する
4. `AgentCoreMemoryConfig` を生成する（`memory_id`, `session_id`, `actor_id`）
5. `AgentCoreMemorySessionManager` を生成して返す（`config`, `memory_client`）

**SDK インポートパス**:

| クラス | インポートパス |
|--------|--------------|
| `MemoryClient` | `from bedrock_agentcore.memory import MemoryClient` |
| `AgentCoreMemorySessionManager` | `from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager` |
| `AgentCoreMemoryConfig` | `from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig` |

**AgentCoreMemoryConfig の構成**:

```python
AgentCoreMemoryConfig(
    memory_id=memory_id,       # AGENTCORE_MEMORY_ID 環境変数
    session_id=session_id,     # 引数の session_id
    actor_id=user_id,          # 引数の user_id
)
```

**AgentCoreMemorySessionManager の構成**:

```python
AgentCoreMemorySessionManager(
    config,                            # AgentCoreMemoryConfig インスタンス
    memory_client=_get_agentcore_client(),  # シングルトン MemoryClient
)
```

### 3.2 dynamodb バックエンド

`DynamoDBSessionManager` を生成する。

**生成手順**:
1. `TUTOR_SESSIONS_TABLE` 環境変数を取得する（デフォルト: `"memoru-tutor-sessions-dev"`）
2. `DynamoDBSessionManager` を生成して返す

**DynamoDBSessionManager の構成**:

```python
DynamoDBSessionManager(
    table_name=table_name,    # TUTOR_SESSIONS_TABLE 環境変数
    session_id=session_id,    # 引数の session_id
    user_id=user_id,          # 引数の user_id
)
```

**インポートパス**: `from services.tutor_session_manager import DynamoDBSessionManager`

> **注意**: `DynamoDBSessionManager` は TASK-0164 で実装するため、このタスクのテストではモック化が必要。

---

## 4. シングルトンパターン仕様

### 4.1 `_get_agentcore_client()` 関数

```python
_agentcore_client: MemoryClient | None = None

def _get_agentcore_client() -> MemoryClient:
    global _agentcore_client
    if _agentcore_client is None:
        from bedrock_agentcore.memory import MemoryClient
        _agentcore_client = MemoryClient()
    return _agentcore_client
```

**要件**:

| 項目 | 仕様 |
|------|------|
| 初期化タイミング | 初回呼び出し時（遅延初期化） |
| インスタンス数 | Lambda プロセス内で 1 つ（シングルトン） |
| スコープ | モジュールレベルのグローバル変数 `_agentcore_client` |
| 再利用 | 2 回目以降の呼び出しでは既存インスタンスを返す |
| コールドスタート最適化 | Lambda グローバルスコープで 1 回だけ AWS API 接続を行い、以降のリクエストで再利用する（REQ-403, NFR-001） |

### 4.2 遅延インポート

以下のクラスはすべて関数内で遅延インポートする（コールドスタート最適化のため）:

- `MemoryClient`
- `AgentCoreMemorySessionManager`
- `AgentCoreMemoryConfig`
- `DynamoDBSessionManager`
- `TutorAIServiceError`

---

## 5. 環境変数一覧

| 環境変数 | 用途 | デフォルト値 | 必須条件 |
|----------|------|-------------|----------|
| `TUTOR_SESSION_BACKEND` | バックエンド選択 | 未設定（自動判定） | No |
| `AGENTCORE_MEMORY_ID` | AgentCore Memory ID | なし | agentcore バックエンド選択時に必須 |
| `ENVIRONMENT` | 実行環境（dev/prod/staging） | `"prod"` | No |
| `TUTOR_SESSIONS_TABLE` | DynamoDB テーブル名 | `"memoru-tutor-sessions-dev"` | No |

---

## 6. エラーケース仕様

### 6.1 不正な TUTOR_SESSION_BACKEND 値

- **条件**: `backend` が `"agentcore"` / `"dynamodb"` 以外の値
- **例外**: `ValueError(f"Unknown TUTOR_SESSION_BACKEND: {backend}")`
- **関連**: EDGE-004

### 6.2 AGENTCORE_MEMORY_ID 未設定

- **条件**: `backend="agentcore"` かつ `AGENTCORE_MEMORY_ID` 環境変数が未設定または空文字列
- **例外**: `TutorAIServiceError("AGENTCORE_MEMORY_ID is required for agentcore backend")`
- **エラー型のインポート**: `from services.tutor_ai_service import TutorAIServiceError`
- **関連**: EDGE-002

---

## 7. ログ出力仕様

`aws_lambda_powertools.Logger` を使用してバックエンド選択のログを出力する。

```python
from aws_lambda_powertools import Logger

logger = Logger()
```

ログ出力ポイント:
- バックエンド選択結果（info レベル）
- 環境自動選択が行われた場合（info レベル）

---

## 8. テストケース一覧

### 8.1 正常系

| テストID | テスト内容 | 環境変数設定 | 期待結果 |
|----------|----------|-------------|---------|
| TC-001-01 | agentcore バックエンド選択 | `TUTOR_SESSION_BACKEND=agentcore`, `AGENTCORE_MEMORY_ID=test-id` | `AgentCoreMemorySessionManager` インスタンスが返される |
| TC-001-02 | dynamodb バックエンド選択 | `TUTOR_SESSION_BACKEND=dynamodb` | `DynamoDBSessionManager` インスタンスが返される |
| TC-103-01 | dev 環境の自動選択 | `ENVIRONMENT=dev`, `TUTOR_SESSION_BACKEND` 未設定 | `DynamoDBSessionManager` が返される |
| TC-103-02 | prod 環境のデフォルト | `ENVIRONMENT=prod`, `TUTOR_SESSION_BACKEND` 未設定 | `AgentCoreMemorySessionManager` が返される |
| TC-103-03 | 明示指定が環境自動選択より優先 | `ENVIRONMENT=dev`, `TUTOR_SESSION_BACKEND=agentcore`, `AGENTCORE_MEMORY_ID=test-id` | `AgentCoreMemorySessionManager` が返される |

### 8.2 異常系

| テストID | テスト内容 | 環境変数設定 | 期待結果 |
|----------|----------|-------------|---------|
| TC-001-E01 | 不正な値で ValueError | `TUTOR_SESSION_BACKEND=invalid` | `ValueError("Unknown TUTOR_SESSION_BACKEND: invalid")` |
| TC-001-E02 | AGENTCORE_MEMORY_ID 未設定エラー | `TUTOR_SESSION_BACKEND=agentcore`, `AGENTCORE_MEMORY_ID` 未設定 | `TutorAIServiceError` |

### 8.3 シングルトン

| テストID | テスト内容 | 条件 | 期待結果 |
|----------|----------|------|---------|
| TC-SINGLETON-01 | MemoryClient が 1 回だけ初期化される | `_get_agentcore_client()` を複数回呼び出し | 同一インスタンスが返される。`MemoryClient()` コンストラクタは 1 回だけ呼ばれる |

### 8.4 テスト時の注意事項

- **外部パッケージのモック化**: `AgentCoreMemorySessionManager`, `AgentCoreMemoryConfig`, `MemoryClient` はすべてモック化する
- **DynamoDBSessionManager のモック化**: TASK-0164 で実装するため stub/mock で代替する
- **シングルトンのリセット**: テストの `setUp` / `tearDown` で `tutor_session_factory._agentcore_client = None` にリセットする
- **環境変数の管理**: `unittest.mock.patch.dict(os.environ, ...)` で環境変数を制御する

---

## 9. 受け入れ基準 対応表

| 完了条件 | 関連要件 | 関連テストケース |
|----------|---------|----------------|
| `create_tutor_session_manager(session_id, user_id)` ファクトリ関数が実装されている | REQ-001 | TC-001-01, TC-001-02 |
| `TUTOR_SESSION_BACKEND=agentcore` で `AgentCoreMemorySessionManager` が返される | REQ-101 | TC-001-01 |
| `TUTOR_SESSION_BACKEND=dynamodb` で `DynamoDBSessionManager` が返される | REQ-102 | TC-001-02 |
| `ENVIRONMENT=dev` かつ未設定時に自動的に `dynamodb` が選択される | REQ-103 | TC-103-01 |
| `ENVIRONMENT=prod` かつ未設定時に自動的に `agentcore` が選択される | REQ-104 | TC-103-02 |
| 不正な値で `ValueError` が発生する | EDGE-004 | TC-001-E01 |
| `AGENTCORE_MEMORY_ID` 未設定で agentcore 選択時に `TutorAIServiceError` が発生する | EDGE-002 | TC-001-E02 |
| `AgentCoreMemoryClient` がシングルトンで初期化される | REQ-403, NFR-001 | TC-SINGLETON-01 |
| テストカバレッジ 80% 以上 | NFR-302 | 全テストケース |

---

## 10. 実装時の参考パターン

既存の `create_tutor_ai_service()` ファクトリ関数（`backend/src/services/tutor_ai_service.py`）のパターンを踏襲する:

- 環境変数に基づく実装の切り替え
- 引数による明示指定が環境変数より優先
- 初期化失敗時は適切な例外でラップ
- 遅延インポートによるコールドスタート最適化

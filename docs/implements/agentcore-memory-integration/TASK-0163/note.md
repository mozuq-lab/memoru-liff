# TASK-0163: SessionManager ファクトリ実装 - コンテキストノート

## 技術スタック概要

- **言語**: Python 3.12
- **フレームワーク**: AWS SAM (Lambda, API Gateway, DynamoDB)
- **ライブラリ**: AWS Lambda Powertools / Pydantic v2 / Strands Agents SDK
- **AI モデル**: Amazon Bedrock (Claude Haiku 4.5) / Ollama (dev環境)
- **新規依存**: `bedrock-agentcore-sdk-python` (`bedrock-agentcore[strands-agents]`)

## 開発ルール

- タスクごとにコミットする（複数タスクをまとめない）
- タスク完了時は個別タスクファイルの完了条件チェックボックスを更新
- テストカバレッジ 80% 以上を目標
- コミットメッセージ形式: `TASK-XXXX: タスク名`
- AWS リソースのデプロイはユーザーが手動で実行

## 関連する既存実装パターン

### ファクトリパターン (`create_tutor_ai_service()`)

ファイル: `backend/src/services/tutor_ai_service.py`

- `USE_STRANDS` 環境変数に基づき `BedrockTutorAIService` / `StrandsTutorAIService` を返す
- 引数 `use_strands: bool | None = None` で明示指定可能、`None` の場合は環境変数から読み取り
- 初期化失敗時は `TutorAIServiceError` を送出
- このパターンを踏襲して `create_tutor_session_manager()` を実装する

```python
def create_tutor_ai_service(
    use_strands: bool | None = None,
) -> BedrockTutorAIService | StrandsTutorAIService:
    if use_strands is None:
        use_strands = os.getenv("USE_STRANDS", "false").lower() == "true"
    try:
        if use_strands:
            return StrandsTutorAIService()
        else:
            return BedrockTutorAIService()
    except TutorAIServiceError:
        raise
    except Exception as e:
        raise TutorAIServiceError(f"Failed to initialize tutor AI service: {e}") from e
```

### DI パターン (`TutorService.__init__`)

ファイル: `backend/src/services/tutor_service.py`

- コンストラクタで `ai_service` を受け取り、`None` の場合はファクトリ関数で生成
- `dynamodb_resource` もオプション引数でテスト時に注入可能

```python
def __init__(
    self,
    table_name: str | None = None,
    dynamodb_resource: Any | None = None,
    ai_service: Any | None = None,
):
    self.ai_service = ai_service if ai_service is not None else create_tutor_ai_service()
```

## 実装ファイルパス

### 新規作成

| ファイル | 概要 |
|---------|------|
| `backend/src/services/tutor_session_factory.py` | SessionManager ファクトリ関数 + AgentCoreMemoryClient シングルトン |

### テストファイル

| ファイル | 概要 |
|---------|------|
| `backend/tests/unit/test_tutor_session_factory.py` | ファクトリ関数のユニットテスト |

## SDK の実際の API 名とインポートパス

設計文書では `AgentCoreMemoryClient` と記載されているが、実際の SDK API 名は異なる:

| 設計文書の名前 | 実際の API 名 | インポートパス |
|--------------|-------------|--------------|
| `AgentCoreMemoryClient` | `MemoryClient` | `from bedrock_agentcore.memory import MemoryClient` |
| `AgentCoreMemorySessionManager` | `AgentCoreMemorySessionManager` | `from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager` |
| `AgentCoreMemoryConfig` | `AgentCoreMemoryConfig` | `from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig` |

### シングルトン初期化の修正

設計文書のコード:
```python
from bedrock_agentcore.memory import AgentCoreMemoryClient
_agentcore_client = AgentCoreMemoryClient()
```

実際の実装:
```python
from bedrock_agentcore.memory import MemoryClient
_agentcore_client = MemoryClient()
```

## ファクトリ関数の設計

### バックエンド選択ロジック

```
TUTOR_SESSION_BACKEND 設定済み?
+-- "agentcore" --> AgentCoreMemorySessionManager
+-- "dynamodb"  --> DynamoDBSessionManager
+-- その他      --> ValueError
+-- 未設定
    +-- ENVIRONMENT?
        +-- "dev"   --> DynamoDBSessionManager（自動選択）
        +-- その他  --> AgentCoreMemorySessionManager（デフォルト）
```

### 関数シグネチャ

```python
def create_tutor_session_manager(
    session_id: str,
    user_id: str,
    backend: str | None = None,
) -> SessionManager:
```

### AgentCoreMemoryClient シングルトン

```python
_agentcore_client: MemoryClient | None = None

def _get_agentcore_client() -> MemoryClient:
    global _agentcore_client
    if _agentcore_client is None:
        from bedrock_agentcore.memory import MemoryClient
        _agentcore_client = MemoryClient()
    return _agentcore_client
```

## テストケース一覧

| ID | テスト内容 | 条件 |
|----|----------|------|
| TC-001-01 | agentcore バックエンド選択 | `TUTOR_SESSION_BACKEND=agentcore`, `AGENTCORE_MEMORY_ID=test-id` |
| TC-001-02 | dynamodb バックエンド選択 | `TUTOR_SESSION_BACKEND=dynamodb` |
| TC-001-E01 | 不正な値で ValueError | `TUTOR_SESSION_BACKEND=invalid` |
| TC-001-E02 | AGENTCORE_MEMORY_ID 未設定エラー | `TUTOR_SESSION_BACKEND=agentcore`, `AGENTCORE_MEMORY_ID` 未設定 |
| TC-103-01 | dev 環境の自動選択 | `ENVIRONMENT=dev`, `TUTOR_SESSION_BACKEND` 未設定 |
| TC-103-02 | prod 環境のデフォルト | `ENVIRONMENT=prod`, `TUTOR_SESSION_BACKEND` 未設定 |
| TC-103-03 | 明示指定が環境自動選択より優先 | `ENVIRONMENT=dev`, `TUTOR_SESSION_BACKEND=agentcore` |
| シングルトン | AgentCoreMemoryClient が1回だけ初期化される | 複数回呼び出しでも同一インスタンス |

## 注意事項

1. **DynamoDBSessionManager は TASK-0164 で実装する**: このタスクでは stub/mock で代替する。ファクトリ関数内の `from services.tutor_session_manager import DynamoDBSessionManager` は実際のクラスが存在しないため、テストではモック化が必要。

2. **AgentCoreMemorySessionManager は外部パッケージ**: `bedrock-agentcore-sdk-python` のクラスなのでモック化してテストする。

3. **シングルトンのテスト時の注意**: グローバル変数 `_agentcore_client` のリセットが必要。テストの `setUp` / `tearDown` で `tutor_session_factory._agentcore_client = None` にリセットする。

4. **エラー型**: agentcore バックエンドで `AGENTCORE_MEMORY_ID` 未設定時は `TutorAIServiceError` を送出する（`from services.tutor_ai_service import TutorAIServiceError`）。

5. **遅延インポート**: `AgentCoreMemorySessionManager`, `AgentCoreMemoryConfig`, `MemoryClient`, `DynamoDBSessionManager` はすべて関数内で遅延インポートする（コールドスタート最適化のため）。

6. **Logger**: `aws_lambda_powertools.Logger` を使用してバックエンド選択のログを出力する。

7. **環境変数**: `TUTOR_SESSIONS_TABLE` のデフォルト値は `"memoru-tutor-sessions-dev"`（既存の `TutorService` と同じ）。

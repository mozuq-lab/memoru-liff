# TASK-0064 設定作業実行

## 作業概要

- **タスクID**: TASK-0064
- **作業内容**: Ollama プロバイダー + docker-compose 統合
- **実行日時**: 2026-02-24
- **実行者**: Claude Code (claude-sonnet-4-6)

## 設計文書参照

- **参照文書**:
  - `docs/tasks/ai-strands-migration/TASK-0064.md`
  - `docs/design/ai-strands-migration/architecture.md`
- **関連タスク**: TASK-0057 (Strands Agents SDK 統合), TASK-0065 (全体統合テスト)

## 実行した作業

### 1. docker-compose.yaml に Ollama サービス追加

**変更ファイル**: `backend/docker-compose.yaml`

既存の services セクション（dynamodb-local, dynamodb-admin, setup-tables, keycloak）に `ollama` サービスを追加した。
また volumes セクションに `ollama-data` を追加した。

追加した Ollama サービス定義:

```yaml
ollama:
  image: ollama/ollama:latest
  container_name: memoru-ollama
  ports:
    - "11434:11434"
  environment:
    - OLLAMA_HOST=0.0.0.0:11434
  volumes:
    - ollama-data:/root/.ollama
  networks:
    - memoru-network
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
    interval: 10s
    timeout: 5s
    retries: 5
    start_period: 30s
```

追加した volumes エントリ:

```yaml
volumes:
  ollama-data:
    name: memoru-ollama-data
```

### 2. env.json の OLLAMA_HOST および OLLAMA_MODEL を修正

**変更ファイル**: `backend/env.json`

SAM local は Docker コンテナ内で Lambda を実行するため、`localhost` ではホストマシンに到達できない。
ユーザーがネイティブ Ollama (v0.16.3, localhost:11434) を使用している現状を考慮し、
`host.docker.internal` を使用してホストマシンの Ollama にアクセスするよう設定した。

| 項目 | 変更前 | 変更後 |
|------|--------|--------|
| OLLAMA_HOST | `http://localhost:11434` | `http://host.docker.internal:11434` |
| OLLAMA_MODEL | `neural-chat` | `llama3.2` |

変更対象 Lambda Function: ApiFunction, LineWebhookFunction, DuePushJobFunction, ReviewsGradeAiFunction, AdviceFunction (全5関数)

**利用パターン**:
- **ネイティブ Ollama（現在の推奨）**: `OLLAMA_HOST=http://host.docker.internal:11434`
- **Docker Ollama（docker-compose 経由）**: USE_STRANDS=true かつ docker compose ネットワーク内から `http://ollama:11434`

### 3. Makefile にコマンド追加

**変更ファイル**: `backend/Makefile`

追加したターゲット:

```makefile
local-ollama: ## Start local Ollama (Docker)
    docker compose up -d ollama
    @echo "Waiting for Ollama service to be ready..."
    @echo "Ollama: http://localhost:11434"

local-ollama-pull: ## Pull Ollama model
    docker compose exec ollama ollama pull $${OLLAMA_MODEL:-llama3.2}
    @echo "Model downloaded successfully"

local-ollama-stop: ## Stop local Ollama
    docker compose stop ollama

local-ollama-logs: ## Show Ollama logs
    docker compose logs -f ollama
```

更新した既存ターゲット:

```makefile
local-all: local-db local-keycloak local-ollama ## Start all local services
```

.PHONY 宣言に `local-ollama`, `local-ollama-pull`, `local-ollama-stop`, `local-ollama-logs` を追加した。

### 4. docker-compose 構成検証

```bash
cd backend && docker compose config > /dev/null && echo "docker-compose.yaml is valid"
# 出力: docker-compose.yaml is valid
```

YAML の有効性を確認済み。

### 5. strands_service.py の ENVIRONMENT=dev 分岐確認

`backend/src/services/strands_service.py` を確認し、以下の実装が既に存在することを確認した:

```python
def _create_model(self) -> tuple[object, str]:
    if self.environment == "dev":
        ollama_host = os.getenv("OLLAMA_HOST", _DEFAULT_OLLAMA_HOST)
        ollama_model = os.getenv("OLLAMA_MODEL", _DEFAULT_OLLAMA_MODEL)
        model = OllamaModel(
            host=ollama_host,
            model_id=ollama_model,
        )
        return model, _MODEL_USED_OLLAMA
    else:
        bedrock_model_id = os.getenv("BEDROCK_MODEL_ID", _DEFAULT_BEDROCK_MODEL_ID)
        model = BedrockModel(model_id=bedrock_model_id)
        return model, _MODEL_USED_BEDROCK
```

デフォルト値も確認済み:
- `_DEFAULT_OLLAMA_HOST = "http://localhost:11434"`
- `_DEFAULT_OLLAMA_MODEL = "llama3.2"`

## 作業結果

- [x] `backend/docker-compose.yaml` に Ollama サービスが追加されている
- [x] `backend/env.json` の OLLAMA_HOST が `http://host.docker.internal:11434` に設定されている
- [x] `backend/env.json` の OLLAMA_MODEL が `llama3.2` に設定されている (全5関数)
- [x] `backend/Makefile` に `local-ollama` コマンドが追加されている
- [x] `backend/Makefile` に `local-ollama-pull` コマンドが追加されている
- [x] `backend/Makefile` に `local-ollama-stop` コマンドが追加されている
- [x] `backend/Makefile` に `local-ollama-logs` コマンドが追加されている
- [x] `make local-all` コマンドで全サービス（DynamoDB, Keycloak, Ollama）が起動するよう更新された
- [x] `docker compose config` による YAML 有効性確認済み
- [x] `strands_service.py` の ENVIRONMENT=dev 分岐が正しく実装されていることを確認済み

## 初回セットアップ手順

```bash
# 1. 全ローカルサービス起動（DynamoDB + Keycloak + Ollama）
cd backend && make local-all

# 2. ネイティブ Ollama を使用している場合（推奨）
#    → env.json の OLLAMA_HOST=http://host.docker.internal:11434 で自動的にホストの Ollama に接続

# 3. Docker Ollama を使用する場合
#    → llama3.2 モデルをダウンロード（初回のみ、数分～数十分かかる）
make local-ollama-pull

# 4. Ollama API の応答確認
curl http://localhost:11434/api/tags

# 5. SAM ローカル API 起動時に USE_STRANDS=true を有効化して動作確認
#    env.json の USE_STRANDS を "true" に変更してから:
make local-api
```

## 注意事項

- macOS では Docker コンテナ内から GPU にアクセスできないため、ネイティブ Ollama（ホストインストール）を推奨
- Docker Ollama と ネイティブ Ollama を切り替える場合は `env.json` の `OLLAMA_HOST` を変更する:
  - ネイティブ Ollama: `http://host.docker.internal:11434`
  - Docker Ollama: `http://ollama:11434` (SAM local のコンテナからの接続)
- `USE_STRANDS` は現在 `"false"` のまま。AI 機能を有効化する際は `"true"` に変更する

## 次のステップ

- `/tsumiki:direct-verify` を実行して設定を確認
- TASK-0065: 全体統合テスト + 品質確認

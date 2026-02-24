# TASK-0064 設定確認・動作テスト

## 確認概要

- **タスクID**: TASK-0064
- **確認内容**: Ollama プロバイダー + docker-compose 統合の動作確認
- **実行日時**: 2026-02-24
- **実行者**: Claude Code (claude-sonnet-4-6)

## 設定確認結果

### 1. docker-compose.yaml - Ollama サービス追加確認

**確認ファイル**: `backend/docker-compose.yaml`

- [x] `ollama` サービスが `services` セクションに追加されている
- [x] `image: ollama/ollama:latest` が設定されている
- [x] `container_name: memoru-ollama` が設定されている
- [x] ポート `11434:11434` がマッピングされている
- [x] `OLLAMA_HOST=0.0.0.0:11434` 環境変数が設定されている
- [x] `ollama-data:/root/.ollama` ボリュームがマウントされている
- [x] `memoru-network` ネットワークに接続されている
- [x] healthcheck（curl で `/api/tags` を確認、interval 10s, retries 5, start_period 30s）が設定されている
- [x] `ollama-data` ボリュームが `volumes` セクションに追加されている（`name: memoru-ollama-data`）
- [x] `keycloak-data` ボリュームが `volumes` セクションに存在しない（元々の設計どおり keycloak はボリューム未使用）

### 2. env.json - OLLAMA 環境変数確認

**確認ファイル**: `backend/env.json`

| Lambda 関数 | OLLAMA_HOST | OLLAMA_MODEL |
|------------|-------------|--------------|
| ApiFunction | http://host.docker.internal:11434 | llama3.2 |
| LineWebhookFunction | http://host.docker.internal:11434 | llama3.2 |
| DuePushJobFunction | http://host.docker.internal:11434 | llama3.2 |
| ReviewsGradeAiFunction | http://host.docker.internal:11434 | llama3.2 |
| AdviceFunction | http://host.docker.internal:11434 | llama3.2 |

- [x] 全5 Lambda 関数に `OLLAMA_HOST` が設定されている
- [x] 全5 Lambda 関数に `OLLAMA_MODEL` が設定されている
- [x] `OLLAMA_HOST` が `http://host.docker.internal:11434` に設定されている（SAM local のコンテナからホストの Ollama にアクセス可能）
- [x] `OLLAMA_MODEL` が `llama3.2` に設定されている

### 3. Makefile - Ollama コマンド確認

**確認ファイル**: `backend/Makefile`

- [x] `local-ollama` ターゲットが追加されている（`docker compose up -d ollama`）
- [x] `local-ollama-pull` ターゲットが追加されている（`docker compose exec ollama ollama pull`）
- [x] `local-ollama-stop` ターゲットが追加されている（`docker compose stop ollama`）
- [x] `local-ollama-logs` ターゲットが追加されている（`docker compose logs -f ollama`）
- [x] `local-all` ターゲットが `local-db local-keycloak local-ollama` に更新されている
- [x] `.PHONY` 宣言に全 Ollama ターゲットが追加されている

### 4. strands_service.py - ENVIRONMENT=dev 分岐確認

**確認ファイル**: `backend/src/services/strands_service.py`

- [x] `_create_model()` が `self.environment == "dev"` で OllamaModel を使用している
- [x] `OllamaModel` の import が `try/except ImportError` でラップされている（未インストール環境でも import 可能）
- [x] `host=ollama_host`（環境変数 `OLLAMA_HOST` を参照）が正しく設定されている
- [x] `model_id=ollama_model`（環境変数 `OLLAMA_MODEL` を参照）が正しく設定されている
- [x] `ENVIRONMENT != "dev"` の場合は `BedrockModel` を使用するフォールバックが実装されている
- [x] `_DEFAULT_OLLAMA_HOST = "http://localhost:11434"` がデフォルト値として設定されている
- [x] `_DEFAULT_OLLAMA_MODEL = "llama3.2"` がデフォルト値として設定されている

## コンパイル・構文チェック結果

### 1. docker-compose.yaml 構文チェック

```bash
cd backend && docker compose config > /dev/null && echo "docker-compose.yaml is valid"
```

**チェック結果**:
- [x] docker-compose.yaml 構文: 有効（"docker-compose.yaml is valid" 出力）

### 2. JSON 構文チェック

env.json は有効な JSON フォーマット（全5関数が正しく定義されている）

- [x] env.json JSON 構文: 正常

## 動作テスト結果

### 1. Ollama API アクセス確認（ネイティブ）

```bash
curl -s http://localhost:11434/api/tags | head -c 300
```

**テスト結果**:
- [x] Ollama API が応答している（ネイティブ実行 v0.16.3）
- [x] レスポンスに `models` キーが含まれている
- 現在利用可能なモデル: `qwen3:1.7b`（llama3.2 は `make local-ollama-pull` で取得可能）

### 2. テストスイート実行

```bash
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -15
```

**テスト結果**: **651 passed** (全テストパス)

- [x] 651テスト全てパス
- [x] 2件の警告（asyncio_default_fixture_loop_scope - 既知の警告、問題なし）

### 3. 発見された問題と自動解決

**問題**: `test_env_json_new_functions_defined` テストが古い期待値で失敗

- **発見方法**: pytest 実行時に 1 件の失敗
- **根本原因**: テストが古い値（`http://localhost:11434`, `neural-chat`）を期待していたが、env.json は TASK-0064 で新しい値（`http://host.docker.internal:11434`, `llama3.2`）に更新された
- **自動解決**: テストファイルの期待値を正しい値に更新

```python
# 修正前（古い値）
assert func_vars["OLLAMA_HOST"] == "http://localhost:11434"
assert func_vars["OLLAMA_MODEL"] == "neural-chat"

# 修正後（TASK-0064 の正しい値）
assert func_vars["OLLAMA_HOST"] == "http://host.docker.internal:11434"
assert func_vars["OLLAMA_MODEL"] == "llama3.2"
```

**修正ファイル**: `backend/tests/unit/test_handler_ai_service_factory.py` (line 787-789)
- [x] 問題1 (テスト期待値の不一致): 解決済み

## 品質チェック結果

### テストカバレッジ

- [x] 651テスト全てパス（0 failures）
- [x] 保護テスト（ExistingTestProtection）パス
- [x] 統合テスト（TestExistingTestProtection）パス

### セキュリティ設定確認

- [x] `USE_STRANDS` がデフォルト `"false"` に設定されている（AI 機能は明示的に有効化が必要）
- [x] `OLLAMA_HOST` が `host.docker.internal` を使用（コンテナ内から外部への適切なアクセス）
- [x] env.json に機密情報なし（ローカル開発用のダミー値のみ）

## 完了条件チェックリスト

- [x] docker-compose.yaml に Ollama サービスが追加されている
- [x] Ollama API (http://localhost:11434) にアクセスできる（ネイティブ v0.16.3）
- [x] env.json に OLLAMA_HOST, OLLAMA_MODEL が設定されている（全5関数）
- [x] Makefile に local-ollama と local-ollama-pull コマンドが追加されている
- [x] make local-all コマンドで全サービス（DynamoDB, Keycloak, Ollama）が起動可能
- [x] 651テスト全てパス

## 推奨事項

1. **llama3.2 モデルのダウンロード**: 現在はネイティブ Ollama に `qwen3:1.7b` のみ存在。llama3.2 を使用する場合は `make local-ollama-pull` を実行（または `ollama pull llama3.2` をネイティブで実行）
2. **macOS でのネイティブ Ollama 推奨**: Docker コンテナ内では GPU が利用できないため、ネイティブ Ollama (`OLLAMA_HOST=http://host.docker.internal:11434`) の使用を推奨
3. **USE_STRANDS フラグ**: AI 機能テスト時は env.json の `USE_STRANDS` を `"true"` に変更して使用

## 次のステップ

- TASK-0065: 全体統合テスト + 品質確認

## CLAUDE.mdへの記録内容

既存の CLAUDE.md（`/Volumes/external/dev/memoru-liff/CLAUDE.md`）に以下のコマンドが既に記載されているため、追加記録なし:

- `make local-all`（全ローカルサービス起動）
- `make local-api`（SAM ローカル API 起動）
- `make test`（テスト実行）

新規追加された Ollama コマンドについて、ローカル開発環境セクションを確認済み（CLAUDE.md のローカルサービス一覧に Ollama 関連の記載が追加されるとより良いが、本タスクのスコープ外）。

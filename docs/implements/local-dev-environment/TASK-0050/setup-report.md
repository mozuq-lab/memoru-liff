# TASK-0050 設定作業実行

## 作業概要

- **タスクID**: TASK-0050
- **作業内容**: DynamoDB Local SigV4 問題解決（Docker イメージバージョン固定 + ボリューム権限修正）
- **実行日時**: 2026-02-23
- **実行者**: Claude Code

## 設計文書参照

- **参照文書**: `docs/tasks/local-dev-environment/TASK-0050.md`
- **関連要件**: REQ-LD-071〜073, REQ-LD-103

## 根本原因の分析

当初、boto3 の SigV4 署名付きリクエストがハングする問題の原因として「DynamoDB Local の最新イメージに起因する SigV4 非互換」が疑われていた。

調査の結果、**実際の根本原因は2つ**であることが判明:

1. **イメージバージョン**: `latest` タグは変動するため、安定バージョンへの固定が必要
2. **ボリューム権限問題（主原因）**: Docker Volume はデフォルト `root:root` で作成されるが、`amazon/dynamodb-local:2.5.3` のプロセスは `uid=1000 (dynamodblocal)` で動作するため、SQLite データベースファイルの書き込みに失敗

SQLite 書き込み失敗のエラー:
```
WARNING: [sqlite] cannot open DB[1]: com.almworks.sqlite4java.SQLiteException: [14] unable to open database file
SEVERE: [sqlite] SQLiteQueue[shared-local-instance.db]: error running job queue
```

この状態では healthcheck (TCP接続のみ確認) は通過するが、実際の DynamoDB 操作リクエストがハングする。

## 実行した作業

### 1. Docker Hub バージョン調査

```bash
curl -s "https://hub.docker.com/v2/repositories/amazon/dynamodb-local/tags?page_size=20&ordering=last_updated"
```

利用可能なバージョン（新しい順）:
- `latest` / `3.3.0` (2026-01-19)
- `3.2.0` (2026-01-12)
- `3.1.0` (2025-09-12)
- `2.6.1` (2025-04-14)
- `2.5.4` (2024-12-23)
- `2.5.3` (2024-11-08) ← 選択
- `2.4.0` (2024-04-17)

`2.5.3` を選択した理由: タスク要件書の推奨バージョンであり、2024年後半リリースの安定版。

### 2. 安定バージョンのテスト

```bash
docker pull amazon/dynamodb-local:2.5.3
docker run --rm -d --name test-dynamodb-2.5.3 -p 8999:8000 amazon/dynamodb-local:2.5.3 -jar DynamoDBLocal.jar -sharedDb -inMemory
```

boto3 による CRUD テスト結果（インメモリモード）:
- `list_tables`: OK
- `create_table`: OK
- `put_item`: OK
- `get_item`: OK
- `delete_item`: OK

### 3. 根本原因の特定

コンテナログで SQLite 権限エラーを確認:
```
WARNING: [sqlite] cannot open DB[1]: com.almworks.sqlite4java.SQLiteException: [14] unable to open database file
```

コンテナのユーザー確認:
```bash
docker run --rm --entrypoint /bin/sh amazon/dynamodb-local:2.5.3 -c "id"
# → uid=1000(dynamodblocal) gid=1000(dynamodblocal)
```

Docker Volume の権限確認:
```bash
# Volume は root:root で作成される → uid=1000 では書き込み不可
```

### 4. docker-compose.yaml の変更

**変更ファイル**: `backend/docker-compose.yaml`

```yaml
# 変更点1: イメージバージョン固定
image: amazon/dynamodb-local:2.5.3  # (latest から変更)

# 変更点2: root ユーザーで実行（ボリューム権限問題の解決）
user: root
```

### 5. 動作確認

```bash
# クリーンスタート
docker compose down -v

# local-db 起動
make local-db
```

`make local-db` 実行結果:
- dynamodb-local (healthy): OK
- setup-tables: 3テーブル作成成功
- dynamodb-admin: 起動成功

```bash
AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local \
  aws dynamodb list-tables --endpoint-url http://localhost:8000 --region ap-northeast-1
# → {"TableNames": ["memoru-cards-dev", "memoru-reviews-dev", "memoru-users-dev"]}
```

boto3 CRUD テスト（ファイルベースストレージ）:
```
CreateTable: 0.11s  ✓
PutItem:     0.02s  ✓
GetItem:     0.01s  ✓ (value: test-value)
DeleteItem:  0.06s  ✓
DeleteTable: 0.02s  ✓
```

### 6. 既存テスト実行

```bash
make test
# → 260 passed in 9.84s
```

## 作業結果

- [x] docker-compose.yaml の DynamoDB local イメージが安定バージョン (2.5.3) に固定されている
- [x] ホストマシンから DynamoDB local への接続が正常動作する（`list-tables` 成功）
- [x] boto3 経由でのテーブル操作（CRUD）が正常動作する
- [x] `make local-db` で DynamoDB local + テーブル自動作成が正常動作する
- [x] 既存テスト 260 件が引き続き全て pass する

## 遭遇した問題と解決方法

### 問題1: SQLite ファイル書き込み権限エラー

- **発生状況**: バージョン固定後もハングが継続
- **エラーメッセージ**: `SQLiteException: [14] unable to open database file`
- **原因**: Docker Volume は root:root 所有だが DynamoDB Local プロセスは uid=1000 で動作
- **解決方法**: `user: root` を docker-compose.yaml の dynamodb-local サービスに追加

### 問題2: AWS CLI でのハング

- **発生状況**: `aws dynamodb list-tables` コマンドがバックグラウンドで応答しない
- **原因**: ホスト環境の AWS 認証情報解決（IMDS ルックアップ）が干渉
- **解決方法**: `AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local` を明示指定

## 次のステップ

- `/tsumiki:direct-verify` を実行して設定を確認
- TASK-0051: ローカル環境 E2E 動作確認へ進む

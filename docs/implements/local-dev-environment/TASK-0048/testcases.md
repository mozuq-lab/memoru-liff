# TASK-0048: ローカル開発環境 基盤構築 - テストケース

**作成日**: 2026-02-23
**タスクID**: TASK-0048
**タスクタイプ**: DIRECT（手動確認中心）

## テストケース一覧

TASK-0048 は DIRECT タスク（環境構築）のため、自動テストではなく手動確認が中心。

### TC-01: インポートパス統一 🔵

**確認方法**: 既存テスト 251 件の全パス
**結果**: ✅ Pass

### TC-02: SAM Local ルーティング 🔵

**確認方法**: `make local-api` で起動後、各エンドポイントにリクエスト送信
**対象**: `/users/me`, `/cards`, `/reviews` 等
**結果**: ✅ Pass（ルーティングが正常動作）

### TC-03: DynamoDB 接続設定 🔵

**確認方法**: env.json に `DYNAMODB_ENDPOINT_URL` を設定し、SAM local からのアクセス確認
**結果**: ✅ Pass（環境変数定義のみ。実際の接続は TASK-0050 で検証）

### TC-04: Keycloak 起動 🔵

**確認方法**: `make local-keycloak` → `http://localhost:8180/health/ready` で確認
**結果**: ✅ Pass

### TC-05: テストユーザーログイン 🔵

**確認方法**: Keycloak ログイン画面で test-user / test-password-123 でログイン
**結果**: ✅ Pass

### TC-06: 開発コマンド 🔵

**確認方法**: `make local-all` で全サービスが起動することを確認
**結果**: ✅ Pass

### TC-07: フロントエンド設定 🔵

**確認方法**: `.env.development` と `.env.example` の CLIENT_ID が `liff-client` であることを確認
**結果**: ✅ Pass

### TC-08: JWT フォールバック実装 🔵

**確認方法**: handler.py L84-98 にコードが存在することを確認（テスト検証は TASK-0049）
**結果**: ✅ Pass（コード存在確認のみ）

### TC-09: 既存テスト全パス 🔵

**確認方法**: `cd backend && make test`
**結果**: ✅ 251 tests passed

## サマリー

| カテゴリ | テスト数 | Pass | Fail |
|---------|---------|------|------|
| 手動確認 | 8 | 8 | 0 |
| 自動テスト | 1 (既存251件) | 1 | 0 |
| **合計** | 9 | 9 | 0 |

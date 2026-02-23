# ローカル開発環境構築 コンテキストノート

**作成日**: 2026-02-22

## プロジェクト概要

LINE ベースの暗記カードアプリケーション「Memoru」のローカル開発環境を、LINE 環境なしでも全機能の動作確認ができるよう構築する。

## 技術スタック

### バックエンド
- Python 3.12 / AWS SAM (Lambda, API Gateway, DynamoDB)
- AWS Lambda Powertools (APIGatewayHttpResolver)
- boto3 (DynamoDB 接続)

### フロントエンド
- React + TypeScript / Vite
- oidc-client-ts (Keycloak OIDC 連携)

### ローカル開発インフラ
- Docker Compose (DynamoDB local, Keycloak)
- SAM CLI (`sam local start-api`)
- Keycloak 24.0 (dev モード、H2 組み込み DB)
- DynamoDB Local (amazon/dynamodb-local:latest)

## 関連ファイル

### 設定ファイル
- `backend/docker-compose.yaml` - Docker Compose 定義
- `backend/env.json` - SAM local 環境変数
- `backend/template.yaml` - SAM テンプレート
- `backend/Makefile` - ローカル開発コマンド
- `infrastructure/keycloak/realm-local.json` - Keycloak ローカル realm 設定
- `frontend/.env.development` - フロントエンド開発環境設定

### ソースコード
- `backend/src/api/handler.py` - API ハンドラー（ルーティング・認証）
- `backend/src/services/user_service.py` - ユーザーサービス（DynamoDB 接続）
- `backend/src/services/card_service.py` - カードサービス（DynamoDB 接続）
- `backend/src/services/review_service.py` - レビューサービス（DynamoDB 接続）

### テスト
- `backend/tests/` - 251 テスト（全 pass）
- `frontend/src/` - 256 テスト（全 pass）

## アーキテクチャ

```
[Browser :3000] → [Vite Dev Server] → [Keycloak :8180] (認証)
                                    → [SAM Local :8080] (API)
                                        → [DynamoDB Local :8000] (DB)
```

## 既知の制約

1. SAM local は API Gateway JWT Authorizer を適用しない
2. SAM local の `--env-vars` は template.yaml に定義された変数のみ渡す
3. DynamoDB local は SigV4 署名付きリクエストでハングする問題あり（調査中）
4. Keycloak dev モードは H2 組み込み DB（再起動でデータリセット）

## テストユーザー

| ユーザー | パスワード | 用途 |
|---------|-----------|------|
| test-user | test-password-123 | 一般ユーザー |
| test-admin | admin-password-123 | 管理者 |

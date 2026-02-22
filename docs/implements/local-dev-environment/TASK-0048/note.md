# TASK-0048: ローカル開発環境 基盤構築 - コンテキストノート

**作成日**: 2026-02-23
**タスクID**: TASK-0048
**タスクタイプ**: DIRECT

## 技術スタック

- **バックエンド**: Python 3.12, AWS SAM (Lambda, API Gateway, DynamoDB)
- **フロントエンド**: React + TypeScript, Vite, LIFF SDK, oidc-client-ts
- **認証**: Keycloak (Docker), OIDC + PKCE
- **ローカルインフラ**: Docker Compose (DynamoDB local, Keycloak, DynamoDB Admin)

## 実装対象

TASK-0048 は以下の基盤構築を実施:

1. **インポートパス統一** (REQ-LD-001〜003): SAM ランタイム互換の絶対インポートに統一
2. **SAM local ルーティング修正** (REQ-LD-011〜012): Powertools の rawPath 解決問題を stage プレフィックス前置で解決
3. **DynamoDB 接続設定** (REQ-LD-021〜022): `DYNAMODB_ENDPOINT_URL` 環境変数による接続先制御
4. **Keycloak Docker セットアップ** (REQ-LD-031〜034): realm-local.json, テストユーザー, dev モード起動
5. **開発コマンド** (REQ-LD-041〜043): Makefile に local-keycloak, local-all, local-api 追加
6. **フロントエンド設定** (REQ-LD-051〜052): .env.development の CLIENT_ID 修正
7. **JWT フォールバック実装コード** (REQ-LD-061〜064): handler.py に dev 環境限定フォールバック追加（テスト検証は TASK-0049）

## 関連ファイル

### 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `infrastructure/keycloak/realm-local.json` | 新規作成 - ローカル用 realm 設定 |
| `backend/docker-compose.yaml` | Keycloak サービス追加 |
| `backend/src/api/handler.py` | SAM local ルーティング修正 + dev 環境 JWT フォールバック |
| `backend/env.json` | KEYCLOAK_ISSUER ポート修正, DYNAMODB_ENDPOINT_URL 追加 |
| `backend/Makefile` | local-keycloak, local-all, local-api コマンド追加 |
| `backend/template.yaml` | DYNAMODB_ENDPOINT_URL, AWS_ENDPOINT_URL 環境変数定義 |
| `frontend/.env.development` | VITE_KEYCLOAK_CLIENT_ID 修正 |
| `frontend/.env.example` | VITE_KEYCLOAK_CLIENT_ID 修正 |
| `backend/src/services/*.py` | DYNAMODB_ENDPOINT_URL 対応 |
| `backend/src/**/*.py` | 絶対インポートに統一 |
| `backend/tests/**/*.py` | 絶対インポートに統一 |

## 注意事項

- JWT フォールバックは `ENVIRONMENT=dev` 限定。本番環境では API Gateway が JWT 検証済み
- SAM local は `--env-vars` で template.yaml に定義された変数のみ Lambda に渡す
- Keycloak dev モードは再起動でデータリセット（realm-local.json で再インポート）
- DynamoDB local の SigV4 ハング問題は TASK-0050 で解決予定

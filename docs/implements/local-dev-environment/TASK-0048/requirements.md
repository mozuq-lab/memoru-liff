# TASK-0048: ローカル開発環境 基盤構築 - 要件詳細

**作成日**: 2026-02-23
**タスクID**: TASK-0048
**タスクタイプ**: DIRECT

## 要件一覧

### 1. インポートパス統一 (REQ-LD-001〜003) 🔵

SAM ランタイムでは `CodeUri: src/` が Python パスルートになるため、`from models.xxx` 形式の絶対インポートに統一する。

- ソースコード: `from ..xxx` → `from models.xxx`, `from services.xxx`
- テストコード: conftest.py で `sys.path` に `src/` を追加
- `backend/src/requirements.txt` を配置

### 2. SAM Local ルーティング修正 (REQ-LD-011〜012) 🔵

Powertools が `rawPath[len("/"+stage):]` でパスを切り詰めるため、SAM local（stage プレフィックスなし）で不正なパスになる問題を修正。

- `stage != "$default"` かつ rawPath が `/{stage}` で始まらない場合、rawPath に `/{stage}` を前置
- 本番環境（`stage="$default"`）ではスキップ

### 3. DynamoDB 接続設定 (REQ-LD-021〜022) 🔵

SAM local が `AWS_ENDPOINT_URL` をフィルタするため、専用環境変数で接続先を制御。

- `DYNAMODB_ENDPOINT_URL` → `AWS_ENDPOINT_URL` のフォールバック
- `template.yaml` の Globals に空文字で定義

### 4. Keycloak Docker セットアップ (REQ-LD-031〜034) 🔵

LINE Login なしで認証フローを確認できるよう Keycloak を Docker で起動。

- `docker-compose.yaml` に Keycloak サービス（ポート 8180）
- `realm-local.json`: LINE IdP 削除、ユーザー名/パスワードログイン有効化
- テストユーザー: test-user / test-password-123, test-admin / admin-password-123

### 5. 開発コマンド (REQ-LD-041〜043) 🔵

- `make local-keycloak`: Keycloak 起動
- `make local-all`: DynamoDB local + Keycloak 一括起動
- `make local-api`: SAM local API をポート 8080 で起動

### 6. フロントエンド設定 (REQ-LD-051〜052) 🔵

- `.env.development`: `VITE_KEYCLOAK_CLIENT_ID=liff-client`
- `.env.example`: 同上

### 7. JWT フォールバック実装 (REQ-LD-061〜064) 🔵

`handler.py` の `get_user_id_from_context()` に dev 環境限定フォールバックを追加。

- Authorization ヘッダーの JWT payload を base64url デコード
- `sub` クレームからユーザー ID を抽出
- `ENVIRONMENT=dev` 以外では無効
- 署名検証なし（dev 環境限定のため）

## 完了条件

- [x] バックエンドソースコードが絶対インポートに統一されている
- [x] SAM local で全エンドポイントにルーティングが正常動作する
- [x] DynamoDB 接続が DYNAMODB_ENDPOINT_URL 環境変数で制御できる
- [x] docker-compose.yaml に Keycloak サービスが定義されている
- [x] realm-local.json にテストユーザーが含まれている
- [x] Makefile に local-keycloak, local-all, local-api コマンドが存在する
- [x] frontend/.env.development の CLIENT_ID が liff-client である
- [x] JWT フォールバック実装コードが handler.py に存在する
- [x] 既存テスト 251 件が全て pass する

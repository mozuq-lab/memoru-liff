# Memoru LIFF

LINE ベースの暗記カードアプリケーション。SRS (Spaced Repetition System) による効率的な学習を実現。

## 概要

Memoru は LINE LIFF (LINE Front-end Framework) を活用した暗記カードアプリです。主な機能：

- AI によるカード自動生成（Strands Agents SDK / Amazon Bedrock）
- AI による回答採点・学習アドバイス
- SM-2 アルゴリズムによる復習スケジューリング
- LINE 通知による復習リマインダー
- Keycloak + LINE Login による認証

## 技術スタック

### バックエンド
- Python 3.12
- AWS SAM (Lambda, API Gateway, DynamoDB)
- AWS Lambda Powertools
- Strands Agents SDK / Amazon Bedrock (Claude) — ファクトリーパターンで切り替え
- Pydantic v2

### フロントエンド
- React 19 + TypeScript 5.x
- Vite 7
- Tailwind CSS 4
- LIFF SDK
- oidc-client-ts
- React Router v7

### 認証
- Keycloak (ECS/Fargate)
- OIDC + PKCE

## ディレクトリ構成

```
memoru-liff/
├── .github/workflows/     # CI/CD パイプライン
├── .kiro/                 # cc-sdd Spec-Driven Development
│   ├── steering/          # プロジェクトコンテキスト（tech, product, structure）
│   ├── specs/             # 機能別仕様（requirements, design, tasks）
│   └── settings/          # テンプレート・ルール
├── backend/               # バックエンド (AWS SAM)
│   ├── src/
│   │   ├── api/           # Lambda ハンドラー（APIGatewayHttpResolver）
│   │   ├── models/        # Pydantic モデル
│   │   ├── services/      # ビジネスロジック層
│   │   ├── utils/         # ユーティリティ
│   │   ├── webhook/       # LINE Webhook ハンドラー
│   │   └── jobs/          # スケジュール実行 Lambda
│   ├── tests/             # テスト (unit / integration)
│   └── template.yaml      # SAM テンプレート
├── frontend/              # フロントエンド (React LIFF)
│   ├── src/
│   │   ├── components/    # UI コンポーネント
│   │   ├── config/        # 設定（OIDC 等）
│   │   ├── contexts/      # React Context
│   │   ├── hooks/         # カスタムフック
│   │   ├── pages/         # ページコンポーネント
│   │   ├── services/      # API サービス
│   │   ├── styles/        # スタイル
│   │   ├── types/         # TypeScript 型定義
│   │   └── utils/         # ユーティリティ
│   └── e2e/               # E2E テスト (Playwright)
├── infrastructure/        # インフラ IaC
│   ├── keycloak/          # Keycloak ECS/Fargate
│   └── liff-hosting/      # CloudFront + S3
└── docs/                  # ドキュメント
    ├── spec/              # 要件定義
    ├── design/            # 設計文書
    └── tasks/             # タスク管理
```

## 開発環境セットアップ

### 前提条件

- Python 3.12+（テスト実行用。SAM ビルドは Docker コンテナで実行されるため不要）
- Node.js 20+
- AWS CLI v2
- AWS SAM CLI
- Docker（ローカル開発用・SAM ビルド用）

### 初回セットアップ

```bash
# バックエンド依存関係
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt

# フロントエンド依存関係
cd ../frontend
npm install
```

### ローカル開発環境の起動

LINE 環境なしでも動作確認できるよう、Keycloak を Docker で起動してユーザー名/パスワード認証が可能です。

```bash
# 1. 全ローカルサービス起動（DynamoDB + Keycloak + Ollama）
cd backend && make local-all

# 2. Keycloak の起動を待つ（初回は約60秒）

# 3. バックエンド API 起動（別ターミナル）
cd backend && make local-api

# 4. フロントエンド起動（別ターミナル）
cd frontend && npm run dev

# 5. ブラウザで http://localhost:3000 にアクセス
#    → Keycloak ログイン画面にリダイレクト
#    → test-user / test-password-123 でログイン
```

#### ローカルサービス一覧

| サービス | URL | 用途 |
|---------|-----|------|
| フロントエンド | http://localhost:3000 | React アプリ |
| バックエンド API | http://localhost:8080 | SAM Local API |
| Keycloak | http://localhost:8180 | 認証サーバー |
| Keycloak 管理コンソール | http://localhost:8180/admin | admin / admin |
| DynamoDB Local | http://localhost:8000 | データベース |
| DynamoDB Admin | http://localhost:8001 | DB 管理 UI |
| Ollama | http://localhost:11434 | AI 推論（ローカル LLM） |

#### テストユーザー

| ユーザー名 | パスワード | ロール |
|-----------|-----------|--------|
| test-user | test-password-123 | user |
| test-admin | admin-password-123 | user, admin |

#### サービス停止

```bash
cd backend && make local-all-stop
```

## 開発コマンド

### バックエンド

```bash
cd backend

# ローカルサービス
make local-all            # 全サービス起動（DynamoDB + Keycloak + Ollama）
make local-all-stop       # 全サービス停止
make local-api            # SAM Local API 起動（ポート 8080）
make local-db             # DynamoDB Local のみ起動
make local-keycloak       # Keycloak のみ起動
make local-ollama         # Ollama のみ起動
make local-ollama-pull    # Ollama モデル取得

# ビルド・デプロイ
make build                # SAM ビルド（Docker コンテナで Python 3.12）
make deploy-dev           # 開発環境デプロイ
make deploy-staging       # ステージング環境デプロイ
make deploy-prod          # 本番環境デプロイ

# テスト・品質
make test                 # 全テスト実行（カバレッジ付き）
make test-unit            # ユニットテストのみ
make test-integration     # 統合テストのみ
make lint                 # ruff + mypy
make format               # コードフォーマット

# デバッグ
make list-tables          # DynamoDB テーブル一覧（ローカル）
make scan-users           # users テーブルスキャン
make scan-cards           # cards テーブルスキャン
```

### フロントエンド

```bash
cd frontend

npm run dev               # Vite 開発サーバー（ポート 3000）
npm run build             # TypeScript チェック + Vite ビルド
npm run type-check        # 型チェック（tsc --noEmit）
npm run lint              # ESLint
npm run test              # Vitest ユニットテスト
npm run test:watch        # Vitest ウォッチモード
npm run test:coverage     # カバレッジレポート
npm run test:e2e          # Playwright E2E テスト
npm run test:e2e:ui       # E2E テスト（UI モード）
npm run test:e2e:headed   # E2E テスト（ブラウザ表示）
```

### インフラ

```bash
# Keycloak デプロイ（AWS）
cd infrastructure/keycloak && make deploy-dev

# LIFF ホスティング デプロイ
cd infrastructure/liff-hosting && make deploy-dev
```

## デプロイ

### 環境変数 (Secrets Manager)

以下のシークレットを AWS Secrets Manager に作成してください：

- `memoru-{env}-line-credentials` - LINE Channel Secret と Access Token
  ```json
  {
    "channel_secret": "your-channel-secret",
    "channel_access_token": "your-channel-access-token"
  }
  ```

### 手動デプロイ

```bash
# バックエンド
cd backend

# 開発環境
make deploy-dev

# ステージング環境
make deploy-staging

# 本番環境
make deploy-prod
```

```bash
# フロントエンド
cd frontend
npm run build

# S3 にアップロード
aws s3 sync dist s3://your-bucket-name --delete

# CloudFront キャッシュ無効化
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*"
```

### CI/CD

GitHub Actions (`deploy.yml`) で CI/CD が設定されています。

- **Push 時** (`backend/**`, `frontend/**` の変更): テストのみ実行（バックエンド pytest + フロントエンド type-check/test/build）
- **手動トリガー** (`workflow_dispatch`): テスト + デプロイ（dev / staging / prod を選択可能）

#### 必要な GitHub Secrets/Variables

**Secrets:**
- `AWS_DEPLOY_ROLE_ARN` - OIDC 認証用 IAM ロール ARN

**Variables (環境別):**
- `API_URL` - バックエンド API URL
- `LIFF_ID` - LINE LIFF ID
- `KEYCLOAK_URL` - Keycloak URL
- `KEYCLOAK_REALM` - Keycloak Realm 名
- `KEYCLOAK_CLIENT_ID` - Keycloak クライアント ID
- `FRONTEND_BUCKET` - フロントエンド用 S3 バケット名
- `CLOUDFRONT_DISTRIBUTION_ID` - CloudFront Distribution ID

## 監視

本番環境では CloudWatch による監視が自動設定されます。

### ダッシュボード

- `memoru-prod-dashboard` - Lambda, API Gateway, DynamoDB のメトリクス

### アラート

- Lambda エラー率が閾値を超過
- API Gateway 5xx エラー率が閾値を超過
- DynamoDB スロットリング検出

アラートは SNS トピック `memoru-prod-alerts` に通知されます。

## API エンドポイント

### ユーザー

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/users/me` | 現在のユーザー情報取得 |
| PUT | `/users/me/settings` | ユーザー設定更新 |
| POST | `/users/link-line` | LINE アカウント連携 |
| POST | `/users/me/unlink-line` | LINE アカウント連携解除 |

### カード

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/cards` | カード一覧取得 |
| POST | `/cards` | カード作成 |
| GET | `/cards/{cardId}` | カード詳細取得 |
| PUT | `/cards/{cardId}` | カード更新 |
| DELETE | `/cards/{cardId}` | カード削除 |
| GET | `/cards/due` | 復習期限カード取得 |
| POST | `/cards/generate` | AI カード生成 |

### デッキ

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/decks` | デッキ作成 |
| GET | `/decks` | デッキ一覧取得 |
| PUT | `/decks/{deckId}` | デッキ更新 |
| DELETE | `/decks/{deckId}` | デッキ削除 |

### 復習

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/reviews/{cardId}` | 復習結果送信 |
| POST | `/reviews/{cardId}/undo` | 復習取り消し |
| POST | `/reviews/{cardId}/grade-ai` | AI による回答採点 |

### AI・学習

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/advice` | 学習アドバイス取得 |

### Webhook

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/webhook/line` | LINE Webhook |

## トラブルシューティング

### SAM ビルドが失敗する（Python バージョン不一致）

ホストマシンに Python 3.12 がない場合（例: Python 3.13 のみインストール済み）、`sam build` が失敗します。
`Makefile` の `build` ターゲットは `--use-container` を使用しているため、Docker が起動していれば自動的に解決されます。

```bash
# Docker が起動していることを確認
docker ps

# SAM ビルド（Docker コンテナで Python 3.12 を使用）
cd backend && make build
```

### DynamoDB Local に接続できない

`make local-db` でテーブルが正しく作成されているか確認:

```bash
aws dynamodb list-tables --endpoint-url http://localhost:8000 --region ap-northeast-1
# 期待結果: memoru-users-dev, memoru-cards-dev, memoru-reviews-dev, memoru-decks-dev
```

### Keycloak が起動しない

初回起動は約60秒かかります。ヘルスチェックで確認:

```bash
curl -s http://localhost:8180/health/ready
# 期待結果: {"status": "UP", ...}
```

起動しない場合は Docker ログを確認:

```bash
cd backend && docker compose logs keycloak
```

### JWT フォールバックが動作しない（SAM local）

SAM local では API Gateway の JWT Authorizer が適用されないため、`ENVIRONMENT=dev` 設定時に JWT フォールバックが有効になります。`env.json` に以下が設定されていることを確認してください:

```json
{
  "ApiFunction": {
    "ENVIRONMENT": "dev"
  }
}
```

## ライセンス

MIT License

# Memoru LIFF

LINE ベースの暗記カードアプリケーション。SRS (Spaced Repetition System) による効率的な学習を実現。

## 概要

Memoru は LINE LIFF (LINE Front-end Framework) を活用した暗記カードアプリです。主な機能：

- AI によるカード自動生成（Amazon Bedrock）
- SM-2 アルゴリズムによる復習スケジューリング
- LINE 通知による復習リマインダー
- Keycloak + LINE Login による認証

## 技術スタック

### バックエンド
- Python 3.12
- AWS SAM (Lambda, API Gateway, DynamoDB)
- AWS Lambda Powertools
- Amazon Bedrock (Claude)

### フロントエンド
- React 18 + TypeScript
- Vite
- LIFF SDK
- oidc-client-ts
- Tailwind CSS

### 認証
- Keycloak (ECS/Fargate)
- OIDC + PKCE

## ディレクトリ構成

```
memoru-liff/
├── .github/workflows/     # CI/CD パイプライン
├── backend/               # バックエンド (AWS SAM)
│   ├── src/               # Lambda 関数ソース
│   ├── tests/             # テスト
│   └── template.yaml      # SAM テンプレート
├── frontend/              # フロントエンド (React LIFF)
│   ├── src/
│   │   ├── components/    # 共通コンポーネント
│   │   ├── contexts/      # React Context
│   │   ├── hooks/         # カスタムフック
│   │   ├── pages/         # ページコンポーネント
│   │   ├── services/      # API サービス
│   │   └── types/         # TypeScript 型定義
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

- Python 3.12+
- Node.js 20+
- AWS CLI v2
- AWS SAM CLI
- Docker (ローカル開発用)

### バックエンド

```bash
cd backend

# Python 仮想環境のセットアップ
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 依存関係インストール
pip install -r requirements.txt
pip install -r requirements-dev.txt

# テスト実行
make test

# ローカル API 起動
make local-api
```

### フロントエンド

```bash
cd frontend

# 依存関係インストール
npm install

# 開発サーバー起動
npm run dev

# テスト実行
npm run test

# 型チェック
npm run type-check

# E2E テスト
npm run test:e2e
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
sam build
sam deploy --config-env dev

# ステージング環境
sam deploy --config-env staging

# 本番環境
sam deploy --config-env prod
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

### CI/CD デプロイ

GitHub Actions で自動デプロイが設定されています。

1. `main` ブランチへのプッシュで開発環境にデプロイ
2. 手動トリガー (`workflow_dispatch`) で任意の環境にデプロイ可能

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

## テスト

### バックエンド

```bash
cd backend

# 全テスト実行
make test

# カバレッジレポート
pytest tests/ -v --cov=src --cov-report=html
```

### フロントエンド

```bash
cd frontend

# ユニットテスト
npm run test

# E2E テスト
npm run test:e2e

# E2E テスト (UI モード)
npm run test:e2e:ui
```

## API ドキュメント

API エンドポイント一覧：

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/users/me` | 現在のユーザー情報取得 |
| PUT | `/users/me` | ユーザー情報更新 |
| GET | `/cards` | カード一覧取得 |
| POST | `/cards` | カード作成 |
| GET | `/cards/{cardId}` | カード詳細取得 |
| PUT | `/cards/{cardId}` | カード更新 |
| DELETE | `/cards/{cardId}` | カード削除 |
| GET | `/cards/due` | 復習期限カード取得 |
| POST | `/reviews` | 復習結果送信 |
| GET | `/reviews/stats` | 復習統計取得 |
| POST | `/cards/generate` | AI カード生成 |
| POST | `/webhook/line` | LINE Webhook |

## ライセンス

MIT License

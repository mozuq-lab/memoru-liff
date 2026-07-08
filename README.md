# Memoru LIFF

LINE ベースの暗記カードアプリケーション。SRS (Spaced Repetition System) による効率的な学習を実現。

## 概要

Memoru は LINE LIFF (LINE Front-end Framework) を活用した暗記カードアプリです。主な機能：

- AI によるカード自動生成（Strands Agents SDK / Amazon Bedrock）
- URL からのカード自動生成（LINE に URL を送信 → SQS ワーカーで非同期生成・プレビュー配信）
- AI による回答採点・学習アドバイス・カード内容の AI 補足
- AI チューター（フリートーク・クイズ・弱点克服の3モード対話学習）
- SM-2 アルゴリズムによる復習スケジューリング
- LINE 通知による復習リマインダー
- OIDC 認証（Keycloak / Cognito 切り替え対応）

## 技術スタック

### バックエンド
- Python 3.12
- AWS SAM (Lambda, API Gateway, DynamoDB, SQS)
- AWS Lambda Powertools
- Strands Agents SDK / Amazon Bedrock (Claude) — ファクトリーパターンで切り替え
- Bedrock AgentCore Memory SDK — SessionManager による会話履歴管理
- Pydantic v2

### フロントエンド
- React 19 + TypeScript 5.x
- Vite 7
- Tailwind CSS 4
- LIFF SDK
- oidc-client-ts
- React Router v7

### 認証
- OIDC + PKCE（Keycloak / Cognito 切り替え対応）
- ローカル開発: Keycloak (Docker)

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
│   │   └── jobs/          # スケジュール実行 Lambda + SQS ワーカー
│   ├── tests/             # テスト (unit / integration)
│   └── template.yaml      # SAM テンプレート
├── frontend/              # フロントエンド (React LIFF)
│   ├── src/
│   │   ├── components/    # UI コンポーネント
│   │   ├── config/        # 設定（OIDC 等）
│   │   ├── constants/     # 共有定数
│   │   ├── contexts/      # React Context
│   │   ├── hooks/         # カスタムフック
│   │   ├── pages/         # ページコンポーネント
│   │   ├── services/      # API サービス
│   │   ├── styles/        # スタイル
│   │   ├── types/         # TypeScript 型定義
│   │   └── utils/         # ユーティリティ
│   └── e2e/               # E2E テスト (Playwright)
├── infrastructure/        # インフラ IaC
│   ├── cdk/               # AWS CDK プロジェクト（Cognito / Keycloak / LIFF Hosting）
│   └── keycloak/          # ローカル開発用 Keycloak 設定
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
- AWS CDK CLI (`npm install -g aws-cdk`)
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

### インフラ（CDK）

```bash
cd infrastructure/cdk

# 初回のみ: CDK Bootstrap
npx cdk bootstrap

# スタック一覧確認
npx cdk ls

# 開発環境デプロイ（推奨デプロイ順）
npx cdk deploy MemoruCognitoDev
npx cdk deploy MemoruKeycloakDev
npx cdk deploy MemoruLiffHostingDev

# 全 dev スタック一括デプロイ
npx cdk deploy MemoruCognitoDev MemoruKeycloakDev MemoruLiffHostingDev

# CloudFormation テンプレート生成（デプロイせず確認）
npx cdk synth
```

## デプロイ

> **環境別手順書**: 開発環境は [deployment-guide-dev.md](docs/deployment-guide-dev.md)、本番環境は [deployment-guide-prod.md](docs/deployment-guide-prod.md) を参照。
> public リポジトリのため、実環境固有の値（ドメイン・証明書 ARN・UserPool ID 等）は Git にコミットせず、GitHub Environments とローカル環境変数から外部注入する。

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

# 必須: OIDC 値を環境変数で設定（未設定なら fail-fast）
export OIDC_ISSUER="https://cognito-idp.ap-northeast-1.amazonaws.com/<UserPoolId>"
export OIDC_AUDIENCE="<UserPool Client ID>"
# 任意: LINE_CHANNEL_ID / USE_STRANDS / TUTOR_SESSION_BACKEND / AGENTCORE_MEMORY_ID / BEDROCK_MODEL_ID

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

# S3 にアップロード（バケット名は CDK スタック出力を参照）
aws s3 sync dist s3://memoru-liff-hosting-{env} --delete

# CloudFront キャッシュ無効化（Distribution ID は CDK スタック出力を参照）
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*"
```

### CI/CD

GitHub Actions で CI/CD が設定されています。

**PR 時** (`ci.yml`): 以下の 3 job を実行

- Backend Tests: ruff + mypy + pytest（カバレッジ付き）
- Frontend Tests: type-check + Vitest
- Infrastructure (CDK) Tests: build + Jest + `cdk synth --all`

**main への push 時** (`deploy.yml`, `backend/**` / `frontend/**` の変更): テストのみ実行（バックエンド pytest + フロントエンド type-check/test/build）

**手動トリガー** (`workflow_dispatch`): テスト + デプロイ（dev / staging / prod を選択可能）

#### 必要な GitHub Secrets/Variables

> **方針（public リポジトリ）**: 実環境固有の値はリポジトリにコミットせず、**GitHub Environments（環境別 Variables / Secrets）** に登録する。`deploy-backend` job はこれらの Variables から `--parameter-overrides` を組み立てて `sam deploy` に渡す。必須 Variables が未設定の場合は job が fail する。詳細は [本番デプロイ手順書](docs/deployment-guide-prod.md) を参照。

**Secrets:**
- `AWS_DEPLOY_ROLE_ARN` - OIDC 認証用 IAM ロール ARN

**Variables (環境別) — バックエンドデプロイ用:**
- `OIDC_ISSUER`（必須） - OIDC Issuer URL（Cognito: `https://cognito-idp.<region>.amazonaws.com/<UserPoolId>`）
- `OIDC_AUDIENCE`（必須） - OIDC Audience（Cognito の場合は UserPool Client ID）
- `LINE_CHANNEL_ID`（任意） - LINE ID トークン検証用 Channel ID
- `USE_STRANDS`（任意） - Strands Agents SDK 有効化（prod は `true` 推奨）
- `TUTOR_SESSION_BACKEND` / `AGENTCORE_MEMORY_ID` / `BEDROCK_MODEL_ID`（任意）

**Variables (環境別) — フロントエンドデプロイ用:**
- `API_URL` - バックエンド API URL
- `LIFF_ID` - LINE LIFF ID
- `OIDC_AUTHORITY` - OIDC プロバイダ Authority URL
- `OIDC_CLIENT_ID` - OIDC クライアント ID
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

> **AI 系エンドポイントの非同期化（ai-async-jobs）**: 下表で ⏳ を付した AI 系エンドポイント
> （生成・URL生成・補足・AI採点・アドバイス・チューター開始/送信）は、API Gateway の 30 秒
> 統合タイムアウトを超える処理を捌くため `202 Accepted` + `job_id` を返し、実処理は SQS ワーカーが
> 実行します。クライアントは `GET /ai-jobs/{jobId}` をポーリングして結果を取得します。
> 設計: [`docs/design/ai-async-jobs/`](docs/design/ai-async-jobs/architecture.md)。

### カード

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/cards` | カード一覧取得 |
| POST | `/cards` | カード作成 |
| GET | `/cards/{cardId}` | カード詳細取得 |
| PUT | `/cards/{cardId}` | カード更新 |
| DELETE | `/cards/{cardId}` | カード削除 |
| GET | `/cards/due` | 復習期限カード取得 |
| POST | `/cards/generate` | AI カード生成 ⏳ |
| POST | `/cards/generate-from-url` | URL からの AI カード生成 ⏳ |
| POST | `/cards/refine` | カード内容の AI 補足（表面・裏面の改善） ⏳ |

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
| POST | `/reviews/{cardId}/grade-ai` | AI による回答採点 ⏳ |

### 統計

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/stats` | 基本統計サマリー取得 |
| GET | `/stats/weak-cards` | 苦手カード一覧取得 |
| GET | `/stats/forecast` | 復習予測取得 |

### AI チューター

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/tutor/sessions` | チューターセッション開始 ⏳ |
| GET | `/tutor/sessions` | セッション一覧取得 |
| GET | `/tutor/sessions/{sessionId}` | セッション詳細取得 |
| POST | `/tutor/sessions/{sessionId}/messages` | メッセージ送信 ⏳ |
| DELETE | `/tutor/sessions/{sessionId}` | セッション終了 |

### AI・学習

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/advice` | 学習アドバイス取得 ⏳ |

### AI ジョブ（ai-async-jobs）

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/ai-jobs/{jobId}` | AI 非同期ジョブの状態・結果取得（ポーリング用。所有者以外・不存在は 404） |

### ブラウザプロファイル（準備中）

認証付きページ取得（AgentCore Browser 連携）用のプロファイル管理 API。バックエンドのブラウザ連携は現在無効化されており、`profile_id` 指定の URL カード生成は 501 を返す。

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/browser-profiles` | プロファイル一覧取得 |
| POST | `/browser-profiles` | プロファイル作成 |
| DELETE | `/browser-profiles/{profileId}` | プロファイル削除 |

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
# 期待結果: memoru-users-dev, memoru-cards-dev, memoru-reviews-dev, memoru-decks-dev,
#           memoru-tutor-sessions-dev, memoru-browser-profiles-dev, memoru-processed-events-dev,
#           memoru-ai-jobs-dev
```

テーブルが不足している場合は `make local-db` を再実行すると、既存テーブルはそのままに不足分だけが作成されます。

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

### AI 系エンドポイント・URL カード生成がローカルで同期実行される

SAM local は SQS → Lambda トリガーを再現できないため、本番で SQS 非同期化している処理はローカルでは `env.json` の `*_WORKER_MODE: "inline"` により受付ハンドラー内で同期実行されます（動作確認の操作感は同じです）。

- **AI 系 REST エンドポイント**（生成・URL生成・補足・AI採点・アドバイス・チューター開始/送信）: `AI_JOB_WORKER_MODE: "inline"`。submit ハンドラーがジョブ登録後にその場で AI 実行して結果を書き込み 202 を返すため、フロントの 1 回目のポーリング（`GET /ai-jobs/{jobId}`）で `completed` が返ります（本番と同一コードパス）。
- **LINE の URL カード生成**（Webhook 経由）: `URL_WORKER_MODE: "inline"`。Webhook 内で同期実行されます。

本番挙動どおりに SQS キューやワーカーの動作（可視性タイムアウト・DLQ 等）をローカルで検証したい場合は、LocalStack を導入して各 `*_QUEUE_URL` を設定します（詳細は [docs/design/ai-async-jobs/architecture.md](docs/design/ai-async-jobs/architecture.md) §7 を参照）。

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

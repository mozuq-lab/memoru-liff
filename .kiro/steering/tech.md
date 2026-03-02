# Technology Stack

## Architecture

サーバーレスアーキテクチャ。バックエンドは AWS SAM (Lambda + API Gateway + DynamoDB) で構成し、フロントエンドは React SPA を S3 + CloudFront でホスティング。認証は OIDC + PKCE フロー（Keycloak / Cognito 切り替え対応）。

## Core Technologies

### Backend
- **Language**: Python 3.12
- **Framework**: AWS SAM (Serverless Application Model)
- **Runtime**: AWS Lambda (arm64)
- **API**: API Gateway HTTP API v2 + Lambda Powertools `APIGatewayHttpResolver`
- **Database**: Amazon DynamoDB
- **AI**: Amazon Bedrock (Claude) / Strands Agents SDK（ファクトリーパターンで切り替え）

### Frontend
- **Language**: TypeScript (strict mode)
- **Framework**: React 19
- **Build**: Vite 7
- **Styling**: Tailwind CSS 4
- **Routing**: React Router v7

### Authentication
- **Provider**: OIDC + PKCE（Keycloak / Cognito 環境変数で切り替え）
- **Client**: oidc-client-ts
- **LINE 連携**: LIFF SDK

## Key Libraries

### Backend
- **aws-lambda-powertools**: ロギング、トレーシング、イベントハンドリング
- **pydantic**: リクエスト/レスポンスバリデーション、モデル定義
- **strands-agents**: AI エージェント SDK（Bedrock 直接呼び出しとの切り替え可能）
- **boto3**: AWS サービス SDK (DynamoDB, Secrets Manager, Bedrock)

### Frontend
- **@line/liff**: LINE LIFF SDK
- **oidc-client-ts**: OIDC 認証クライアント
- **date-fns**: 日付操作

## Development Standards

### Type Safety
- **Frontend**: TypeScript strict mode (`strict: true`, `noUnusedLocals`, `noUnusedParameters`)
- **Backend**: Pydantic モデルによる実行時バリデーション、mypy による静的型検査

### Code Quality
- **Frontend**: ESLint (flat config) + typescript-eslint + react-hooks + react-refresh
- **Backend**: ruff (lint + format) + mypy

### Testing
- **Frontend**: Vitest + Testing Library (ユニット)、Playwright (E2E)
- **Backend**: pytest + pytest-cov、moto (AWS モック)
- **テスト配置**: テストファイルはソースコードと同階層の `__tests__/` ディレクトリに配置

## Development Environment

### Required Tools
- Node.js 20+
- Python 3.12+（テスト実行用）
- AWS CLI v2 + AWS SAM CLI
- Docker（ローカル DynamoDB, Keycloak, SAM ビルド用）

### Common Commands
```bash
# Backend
cd backend && make local-all       # 全ローカルサービス起動 (DynamoDB + Keycloak + Ollama)
cd backend && make local-api       # SAM Local API 起動
cd backend && make test            # テスト実行
cd backend && make build           # SAM ビルド (Docker コンテナ)
cd backend && make lint            # ruff + mypy

# Frontend
cd frontend && npm run dev         # Vite 開発サーバー (port 3000)
cd frontend && npm run test        # Vitest ユニットテスト
cd frontend && npm run test:e2e    # Playwright E2E
cd frontend && npm run build       # TypeScript チェック + Vite ビルド
```

## Key Technical Decisions

- **サーバーレス**: Lambda + DynamoDB によるスケーラブルでコスト効率の高い構成
- **SM-2 アルゴリズム**: 科学的根拠に基づく間隔反復。カード単位で ease_factor, interval, repetitions を管理
- **AI サービスファクトリー**: `USE_STRANDS` 環境変数で Bedrock 直接呼び出し / Strands Agent を切り替え
- **JWT フォールバック**: SAM Local では JWT Authorizer が適用されないため、dev 環境で Authorization ヘッダーから直接デコード
- **Vite プロキシ**: 開発時に `/api` リクエストを SAM Local (port 8080) にプロキシ

---
_Document standards and patterns, not every dependency_

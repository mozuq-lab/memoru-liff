# Memoru LIFF - Claude Code ガイドライン

> 共通ルールは `AGENTS.md` にも記載。Claude Code は CLAUDE.md のみ自動読み込みするため、必要な情報はここに集約。

## プロジェクト概要

LINE ベースの暗記カードアプリケーション。SRS (Spaced Repetition System) による効率的な学習を実現。

## 技術スタック

### バックエンド
- Python 3.12 / AWS SAM (Lambda, API Gateway, DynamoDB)
- AWS Lambda Powertools / Pydantic v2
- Strands Agents SDK / Amazon Bedrock (Claude)
- Bedrock AgentCore Memory SDK (SessionManager)

### フロントエンド
- React 19 + TypeScript 5.x / Vite 7 / Tailwind CSS 4
- LIFF SDK / oidc-client-ts / React Router v7

### インフラ
- AWS CDK v2 (TypeScript) — Cognito / Keycloak / LIFF Hosting

### 認証
- OIDC + PKCE（Keycloak / Cognito 切り替え対応）

## ディレクトリ構成

```
backend/src/
├── api/           # Lambda ハンドラー (APIGatewayHttpResolver)
├── models/        # Pydantic モデル
├── services/      # ビジネスロジック層
├── utils/         # ユーティリティ
├── webhook/       # LINE Webhook ハンドラー
└── jobs/          # スケジュール実行 Lambda

frontend/src/
├── components/    # UI コンポーネント
├── contexts/      # React Context
├── hooks/         # カスタムフック
├── pages/         # ページコンポーネント
├── services/      # API サービス
├── types/         # TypeScript 型定義
└── utils/         # ユーティリティ

infrastructure/cdk/
├── bin/app.ts             # CDK App エントリポイント
└── lib/
    ├── cognito-stack.ts      # Cognito UserPool (OIDC + PKCE)
    ├── keycloak-stack.ts     # Keycloak (VPC + ECS/Fargate + RDS + ALB)
    └── liff-hosting-stack.ts # LIFF Hosting (S3 + CloudFront + OAC)

docs/
├── spec/{要件名}/    # 要件定義
├── design/{要件名}/  # 設計文書
└── tasks/{要件名}/   # タスクファイル
```

## 開発コマンド

```bash
# バックエンド
cd backend
make local-all          # 全ローカルサービス起動 (DynamoDB + Keycloak + Ollama)
make local-all-stop     # 全停止
make local-api          # SAM Local API (ポート 8080)
make test               # pytest + カバレッジ
make lint               # ruff + mypy

# フロントエンド
cd frontend
npm run dev             # Vite 開発サーバー (ポート 3000)
npm run test            # Vitest
npm run type-check      # tsc --noEmit
npm run build           # TypeScript チェック + Vite ビルド

# インフラ (CDK)
cd infrastructure/cdk
npx cdk ls              # スタック一覧
npx cdk synth           # CloudFormation テンプレート生成
npx cdk deploy <Stack>  # デプロイ（ユーザーが手動実行）
npm run build           # TypeScript コンパイル
```

## 開発ルール

### コミット
- **タスクごとにコミットする**（複数タスクをまとめない）
- Phase 完了時は概要コミットも可

### タスクファイル更新ルール
タスク完了時は以下を更新:
1. **個別タスクファイル**: 完了条件の `[ ]` を `[x]` に変更
2. **概要ファイル**（存在する場合）: タスク一覧の状態列を更新

### 注意事項
- AWS リソースのデプロイはユーザーが手動で実行
- LINE Developer Console の設定はユーザーが手動で実行
- テストカバレッジ 80% 以上を目標とする

## Tsumiki ワークフロー

Claude Code では Tsumiki プラグインの Kairo ワークフローも使用できる。

### タスク実装の流れ

1. **タスクファイルの確認**: `docs/tasks/{要件名}/TASK-XXXX.md` を読む
2. **タスクタイプに応じた実装**:
   - **TDD タスク**: `/tsumiki:tdd-red` → `/tsumiki:tdd-green` → `/tsumiki:tdd-refactor`
   - **DIRECT タスク**: `/tsumiki:direct-setup` → `/tsumiki:direct-verify`
3. **タスクファイルの更新**: 完了条件のチェックボックスを `[x]` に更新
4. **タスク完了後にコミット**

### コミットメッセージ形式

```
TASK-XXXX: タスク名

- 実装内容1
- 実装内容2

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

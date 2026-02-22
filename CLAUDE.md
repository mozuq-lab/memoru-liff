# Memoru LIFF - Claude Code 開発ガイドライン

## プロジェクト概要

LINE ベースの暗記カードアプリケーション。SRS (Spaced Repetition System) による効率的な学習を実現。

## 開発ワークフロー

### Tsumiki ワークフローの使用

このプロジェクトでは Tsumiki プラグインの Kairo ワークフローを使用して開発を進める。

#### タスク実装の流れ

1. **タスクファイルの確認**: `docs/tasks/{要件名}/TASK-XXXX.md` を読む
2. **タスクタイプに応じた実装**:
   - **TDD タスク**: `/tsumiki:tdd-red` → `/tsumiki:tdd-green` → `/tsumiki:tdd-refactor`
   - **DIRECT タスク**: `/tsumiki:direct-setup` → `/tsumiki:direct-verify`
3. **タスクファイルの更新**: 完了条件のチェックボックスを `[x]` に更新
4. **タスク完了後にコミット**

#### タスクファイル更新ルール

タスク完了時は以下のファイルを更新する:

1. **個別タスクファイル** (`TASK-XXXX.md`):
   - 完了条件の `[ ]` を `[x]` に変更
2. **概要ファイル** (`overview.md`):
   - タスク一覧の状態列を更新 (`[ ]` → `[x]` または `[~]`)
   - Phase完了条件のチェックボックスを更新

### コミットルール

- **タスクごとにコミットする**（複数タスクをまとめない）
- コミットメッセージ形式:
  ```
  TASK-XXXX: タスク名

  - 実装内容1
  - 実装内容2

  🤖 Generated with [Claude Code](https://claude.com/claude-code)

  Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
  ```
- Phase 完了時は概要コミットも可

### 現在の進捗

#### memoru-liff（初期実装）
- [~] Phase 1: 基盤インフラ構築 (TASK-0001 ~ TASK-0005) - IaCテンプレート作成完了、デプロイ待ち
- [x] Phase 2: バックエンド実装 (TASK-0006 ~ TASK-0011)
- [x] Phase 3: フロントエンド実装 (TASK-0012 ~ TASK-0019)
- [x] Phase 4: 統合テスト (TASK-0020 ~ TASK-0022)

#### code-review-remediation（コードレビュー修正 第1弾）
- [x] Phase 1: Critical修正 (TASK-0023 ~ TASK-0029) - API契約統一、認証フロー、セキュリティ
- [x] Phase 2: High修正 (TASK-0030 ~ TASK-0041) - datetime統一、トークンリフレッシュ、インフラ最適化

#### code-review-fixes-v2（コードレビュー修正 第2弾）
- [x] Phase 1: Critical修正 (TASK-0042 ~ TASK-0043) - APIルート統一、card_countトランザクション
- [x] Phase 2: High修正 (TASK-0044 ~ TASK-0047) - LINE連携検証、DTO統一、通知TZ、設定統一

## 技術スタック

### バックエンド
- Python 3.12
- AWS SAM (Lambda, API Gateway, DynamoDB)
- AWS Lambda Powertools
- Pydantic v2

### フロントエンド
- React + TypeScript
- Vite
- LIFF SDK
- oidc-client-ts

### 認証
- Keycloak (ECS/Fargate)
- OIDC + PKCE

### AI
- Amazon Bedrock (Claude)

## ディレクトリ構成

```
memoru-liff/
├── docs/
│   ├── spec/memoru-liff/      # 要件定義
│   ├── design/memoru-liff/    # 設計文書
│   └── tasks/memoru-liff/     # タスクファイル
├── infrastructure/
│   ├── keycloak/              # Keycloak IaC
│   └── liff-hosting/          # CloudFront + S3 IaC
├── backend/
│   ├── src/                   # Lambda関数ソース
│   ├── tests/                 # テスト
│   └── template.yaml          # SAMテンプレート
└── frontend/                  # React LIFF アプリ
    ├── src/
    │   ├── components/        # 共通コンポーネント
    │   ├── contexts/          # React Context
    │   ├── hooks/             # カスタムフック
    │   ├── pages/             # ページコンポーネント
    │   ├── services/          # APIサービス
    │   └── types/             # TypeScript型定義
    └── vite.config.ts         # Vite設定
```

## ローカル開発環境

LINE 環境なしでも動作確認できるよう、Keycloak を Docker で起動してローカル認証を行う。

### 起動手順

```bash
# 1. 全ローカルサービス起動（DynamoDB + Keycloak）
cd backend && make local-all

# 2. Keycloak 起動待ち（初回は約20秒）
#    http://localhost:8180/health/ready で確認

# 3. バックエンド API 起動（別ターミナル）
cd backend && make local-api

# 4. フロントエンド起動（別ターミナル）
cd frontend && npm run dev

# 5. ブラウザで http://localhost:3000 にアクセス
#    → Keycloak ログイン画面 → test-user / test-password-123
```

### ローカルサービス一覧

| サービス | URL | 用途 |
|---------|-----|------|
| Vite | http://localhost:3000 | フロントエンド |
| SAM Local API | http://localhost:8080 | バックエンド API |
| Keycloak | http://localhost:8180 | 認証（admin/admin で管理コンソール） |
| DynamoDB Local | http://localhost:8000 | データベース |
| DynamoDB Admin | http://localhost:8001 | DB 管理 UI |

### テストユーザー

| ユーザー名 | パスワード | ロール |
|-----------|-----------|--------|
| test-user | test-password-123 | user |
| test-admin | admin-password-123 | user, admin |

### 停止

```bash
cd backend && make local-all-stop
```

## 開発コマンド

### バックエンド

```bash
cd backend

# ローカルDynamoDB起動
make local-db

# ローカルKeycloak起動
make local-keycloak

# 全ローカルサービス起動
make local-all

# SAMビルド
make build

# ローカルAPI起動（ポート8080）
make local-api

# テスト実行
make test

# デプロイ（開発環境）
make deploy-dev
```

### フロントエンド

```bash
cd frontend

# 依存関係インストール
npm install

# 開発サーバー起動（ポート3000）
npm run dev

# ビルド
npm run build

# 型チェック
npm run type-check
```

### インフラ

```bash
# Keycloak デプロイ（AWS）
cd infrastructure/keycloak && make deploy-dev

# LIFF ホスティング デプロイ
cd infrastructure/liff-hosting && make deploy-dev
```

## 注意事項

- AWS リソースのデプロイはユーザーが手動で実行
- LINE Developer Console の設定はユーザーが手動で実行
- Secrets Manager への認証情報登録はユーザーが手動で実行
- テストカバレッジ 80% 以上を目標とする

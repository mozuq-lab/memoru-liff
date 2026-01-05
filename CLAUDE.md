# Memoru LIFF - Claude Code 開発ガイドライン

## プロジェクト概要

LINE ベースの暗記カードアプリケーション。SRS (Spaced Repetition System) による効率的な学習を実現。

## 開発ワークフロー

### Tsumiki ワークフローの使用

このプロジェクトでは Tsumiki プラグインの Kairo ワークフローを使用して開発を進める。

#### タスク実装の流れ

1. **タスクファイルの確認**: `docs/tasks/memoru-liff/TASK-XXXX.md` を読む
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

- [~] Phase 1: 基盤インフラ構築 (TASK-0001 ~ TASK-0005) - IaCテンプレート作成完了、デプロイ待ち
- [x] Phase 2: バックエンド実装 (TASK-0006 ~ TASK-0011)
- [ ] Phase 3: フロントエンド実装 (TASK-0012 ~ TASK-0019)
- [ ] Phase 4: 統合テスト (TASK-0020 ~ TASK-0022)

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
└── frontend/                  # React LIFF アプリ (未作成)
```

## 開発コマンド

### バックエンド

```bash
cd backend

# ローカルDynamoDB起動
make local-db

# SAMビルド
make build

# ローカルAPI起動
make local-api

# テスト実行
make test

# デプロイ（開発環境）
make deploy-dev
```

### インフラ

```bash
# Keycloak デプロイ
cd infrastructure/keycloak && make deploy-dev

# LIFF ホスティング デプロイ
cd infrastructure/liff-hosting && make deploy-dev
```

## 注意事項

- AWS リソースのデプロイはユーザーが手動で実行
- LINE Developer Console の設定はユーザーが手動で実行
- Secrets Manager への認証情報登録はユーザーが手動で実行
- テストカバレッジ 80% 以上を目標とする

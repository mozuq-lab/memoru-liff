# Memoru LIFF - AI Agent ガイドライン

全 AI エージェント（Cursor, Codex, GitHub Copilot, Claude Code 等）共通の開発ガイドライン。
ワークフロー固有の手順（cc-sdd, Spec kit, Tsumiki 等）はそれぞれの設定ファイルを参照すること。

## プロジェクト概要

LINE ベースの暗記カードアプリケーション。SRS (Spaced Repetition System) による効率的な学習を実現。

### プロジェクトコンテキストの参照先

以下のファイルが存在する場合、プロジェクトの技術情報として参照できる:

- `.kiro/steering/` — 技術スタック・ディレクトリ構成・コーディング規約（cc-sdd 使用時）
- `.specify/memory/constitution.md` — プロジェクト憲法・開発原則（Spec kit 使用時）
- `README.md` — ローカル開発環境・デプロイ手順・API 一覧

## 共通開発ルール

### 言語

- 思考は英語、レスポンスは日本語で生成
- プロジェクトファイル（要件定義、設計、タスク等）は仕様の target language に従う

### コミット

- **タスクごとにコミットする**（複数タスクをまとめない）
- Phase 完了時は概要コミットも可

### タスクファイル更新ルール

タスク完了時は以下のファイルを更新する:

1. **個別タスクファイル**:
   - 完了条件の `[ ]` を `[x]` に変更
2. **概要ファイル**（存在する場合）:
   - タスク一覧の状態列を更新 (`[ ]` → `[x]` または `[~]`)

### 自律的実行

- ユーザーの指示に忠実に従い、その範囲内で自律的に行動する
- 必要なコンテキストを収集し、1回の実行で作業を完遂する
- 質問は、必須情報が欠落しているか、指示が重大に曖昧な場合のみ

## 注意事項

- AWS リソースのデプロイはユーザーが手動で実行
- LINE Developer Console の設定はユーザーが手動で実行
- Secrets Manager への認証情報登録はユーザーが手動で実行
- テストカバレッジ 80% 以上を目標とする

## 現在の進捗

### memoru-liff（初期実装）
- [~] Phase 1: 基盤インフラ構築 (TASK-0001 ~ TASK-0005) - IaCテンプレート作成完了、デプロイ待ち
- [x] Phase 2: バックエンド実装 (TASK-0006 ~ TASK-0011)
- [x] Phase 3: フロントエンド実装 (TASK-0012 ~ TASK-0019)
- [x] Phase 4: 統合テスト (TASK-0020 ~ TASK-0022)

### code-review-remediation（コードレビュー修正 第1弾）
- [x] Phase 1: Critical修正 (TASK-0023 ~ TASK-0029)
- [x] Phase 2: High修正 (TASK-0030 ~ TASK-0041)

### code-review-fixes-v2（コードレビュー修正 第2弾）
- [x] Phase 1: Critical修正 (TASK-0042 ~ TASK-0043)
- [x] Phase 2: High修正 (TASK-0044 ~ TASK-0047)

### local-dev-environment（ローカル開発環境構築）
- [x] Phase 1: 残タスク解決 (TASK-0049 ~ TASK-0051)

### ai-strands-migration（AI Strands SDK 移行）
- [x] Phase 1 ~ Phase 4: 完了（784テスト全通過、カバレッジ 80.04%）

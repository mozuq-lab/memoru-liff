# AgentCore Memory 統合 — コンテキストノート

## 技術スタック

### バックエンド
- Python 3.12 / AWS SAM (Lambda, API Gateway, DynamoDB)
- AWS Lambda Powertools / Pydantic v2
- Strands Agents SDK / Amazon Bedrock (Claude)
- モデル: `global.anthropic.claude-haiku-4-5-20251001-v1:0` (デフォルト)
- 環境変数 `TUTOR_MODEL_ID` / `BEDROCK_MODEL_ID` でモデル指定可能

### フロントエンド
- React 19 + TypeScript 5.x / Vite 7 / Tailwind CSS 4
- LIFF SDK / oidc-client-ts / React Router v7

### インフラ
- AWS CDK v2 (TypeScript) — Cognito / Keycloak / LIFF Hosting
- AWS SAM — Lambda / API Gateway / DynamoDB

### 認証
- OIDC + PKCE（Keycloak / Cognito 切り替え対応）

## 開発ルール

- タスクごとにコミットする（複数タスクをまとめない）
- タスク完了時は個別タスクファイルの完了条件チェックボックスを更新
- テストカバレッジ 80% 以上を目標
- AWS リソースのデプロイはユーザーが手動で実行
- コミットメッセージ形式: `TASK-XXXX: タスク名`

## 関連ファイル

### AI Tutor サービス層

| ファイル | 概要 |
|----------|------|
| `backend/src/services/tutor_ai_service.py` | AI サービス層。`BedrockTutorAIService`（Bedrock Messages API 直接呼び出し）と `StrandsTutorAIService`（Strands Agents SDK）の 2 バックエンドを提供。`create_tutor_ai_service()` ファクトリで `USE_STRANDS` 環境変数に基づき切り替え。`generate_response(system_prompt, messages)` で会話履歴全体を受け取り、応答と関連カード ID を返す。 |
| `backend/src/services/tutor_service.py` | ビジネスロジック層。`TutorService` クラスがセッションライフサイクル（start / send_message / end / list / get）を管理。DynamoDB の `tutor_sessions` テーブルに会話履歴（`messages` リスト）を全件保存し、毎回全履歴を AI に渡す方式。セッションタイムアウト（30分）、メッセージ上限（20往復）、TTL（7日）を管理。 |
| `backend/src/services/prompts/tutor.py` | モード別システムプロンプト（free_talk / quiz / weak_point）。デッキ名・カードコンテキスト・弱点カード情報を埋め込み。大規模デッキは 100 枚で切り詰め。 |
| `backend/src/models/tutor.py` | Pydantic モデル定義。`TutorMessage`, `TutorSessionResponse`, `StartSessionRequest`, `SendMessageRequest`, `SendMessageResponse`, `SessionListResponse`, `LearningMode` 型。 |
| `backend/src/api/handlers/tutor_handler.py` | API ルートハンドラー。`POST /tutor/sessions`, `POST /tutor/sessions/{sessionId}/messages`, `DELETE /tutor/sessions/{sessionId}`, `GET /tutor/sessions`, `GET /tutor/sessions/{sessionId}` の 5 エンドポイント。エラーハンドリング（404, 409, 422, 429, 504, 500）を実装。 |
| `backend/tests/unit/test_tutor_ai_service.py` | `BedrockTutorAIService` と `StrandsTutorAIService` のユニットテスト。初期化、`generate_response`、関連カード抽出、`clean_response_text`、ファクトリ関数のテスト。 |

### インフラ

| ファイル | 概要 |
|----------|------|
| `backend/template.yaml` | SAM テンプレート。`TutorSessionsTable`（DynamoDB）を定義。PK: `user_id`, SK: `session_id`。GSI: `user_id-status-index`。`TutorModelId` パラメータで Tutor 専用モデル指定可能。Lambda タイムアウト: 120 秒（グローバル設定）。 |

### 関連 AI サービス（参考）

| ファイル | 概要 |
|----------|------|
| `backend/src/services/bedrock.py` | 既存のカード生成 AI サービス（`BedrockService`）。boto3 直接呼び出し。Tutor とは別系統。 |

## 既存設計文書

AI Tutor 専用の spec/design/tasks ディレクトリは存在しない。AI Tutor の仕様は以下に記載:

- `docs/feature-backlog.md` セクション 4「AI チューター（インタラクティブ学習）」— AgentCore Memory 統合の設計方針、SessionManager ファクトリパターン、環境変数定義、DynamoDB フォールバック戦略を詳述

関連する既存要件の設計文書:

- `docs/spec/ai-strands-migration/` — Strands Agents SDK 移行の要件定義・コンテキストノート
- `docs/design/ai-strands-migration/` — Strands Agents SDK 移行のアーキテクチャ・API・データフロー設計
- `docs/tasks/ai-strands-migration/` — TASK-0052 〜 TASK-0065（Strands 移行タスク一覧）

## 現在の実装状況

### 会話履歴管理方法（現在: DynamoDB 自前管理）

現在の AI Tutor は DynamoDB テーブル `memoru-tutor-sessions-{env}` に会話履歴を全件保存する方式で動作している:

1. **セッション開始** (`start_session`):
   - デッキのカードを取得し、システムプロンプトを構築
   - AI に挨拶メッセージを生成させる
   - DynamoDB にセッションアイテムを作成（`messages` リストに挨拶メッセージを格納、`system_prompt` も保存）

2. **メッセージ送信** (`send_message`):
   - DynamoDB からセッションアイテムを取得
   - `messages` リスト全件を `[{"role": ..., "content": ...}]` 形式に変換
   - ユーザーメッセージを追加
   - `ai_service.generate_response(system_prompt, conversation)` に全履歴を渡す
   - AI 応答を受け取り、ユーザーメッセージと AI メッセージを `messages` に追記して DynamoDB を更新

3. **課題**:
   - 会話が長くなると DynamoDB アイテムサイズ（400KB 上限）に近づく
   - 全履歴を毎回 AI に渡すため、コンテキストウィンドウとトークンコストが線形に増加
   - セッション間の学習傾向の継続（長期メモリ）が未実装

### Strands Agent の利用状況

- `StrandsTutorAIService` は Strands `Agent` を毎回新規生成し、`messages` パラメータに過去の会話履歴を渡す
- `SessionManager` は未使用（Agent に `session_manager` を注入していない）
- dev 環境: `OllamaModel` (ローカル LLM)、prod 環境: `BedrockModel`

## 注意事項

### AgentCore Memory 統合に関する技術的注意点

1. **feature-backlog.md の設計方針との整合性**:
   - `TUTOR_SESSION_BACKEND` 環境変数で `agentcore` / `dynamodb` を切り替えるファクトリパターンが仕様として定義済み
   - Strands SDK の `SessionManager` インターフェースを活用し、Agent 側のコード変更なしで切り替え可能とする方針
   - `AgentCoreMemorySessionManager`（`bedrock-agentcore-sdk-python`）を本番用、`DynamoDBSessionManager` をフォールバック/ローカル用とする

2. **既存実装からの移行ポイント**:
   - 現在の `TutorService.send_message()` は会話履歴を自前で管理し `generate_response()` に全件渡している
   - AgentCore Memory 統合後は `SessionManager` が履歴管理を担うため、`TutorService` の履歴管理ロジックをリファクタリングする必要がある
   - `TutorService` のセッションメタデータ管理（status, message_count, timeout, TTL）は引き続き DynamoDB で管理する（AgentCore Memory はメッセージ履歴のみ担当）

3. **ローカル開発との整合性**:
   - dev 環境は `OllamaModel` を使用しており AgentCore Memory は利用不可
   - ローカル開発パス: `TUTOR_SESSION_BACKEND=dynamodb` + `USE_STRANDS=true` + `OllamaModel` + DynamoDB Local
   - 既存の `create_tutor_ai_service()` ファクトリとの一貫性を保つ

4. **Lambda コールドスタート**:
   - AgentCore Memory クライアントの初期化がコールドスタートに加算される
   - `SessionManager` を Lambda のグローバルスコープで初期化し、ハンドラ間で再利用すること

5. **コスト見積もり**:
   - AgentCore Memory: 約 $0.01/セッション（20 イベント + 10 取得）。月 100 セッションで約 $1
   - DynamoDB: 既存テーブルのオンデマンド課金で追加コストは微小

6. **将来の拡張**:
   - AgentCore Memory の `summaryMemoryStrategy` で古い会話を自動要約し、コンテキスト圧縮が可能
   - セマンティック検索で過去セッションの学習傾向を活用可能（AgentCore 限定機能）

7. **必要な追加依存パッケージ**:
   - `bedrock-agentcore-sdk-python` — AgentCore Memory クライアント + Strands SessionManager 統合

8. **IAM ポリシー追加**:
   - AgentCore Memory API へのアクセス権限を Lambda 実行ロールに追加する必要がある
   - `AGENTCORE_MEMORY_ID` 環境変数を SAM テンプレートのパラメータとして追加する必要がある

9. **API インターフェースの変更**:
   - API エンドポイント自体は変更不要（バックエンドの切り替えは内部実装のみ）
   - セッション履歴の復元は `SessionManager` が内部で自動処理する

10. **テスト戦略**:
    - `SessionManager` をモックしたユニットテスト
    - DynamoDB フォールバックの `DynamoDBSessionManager` 実装のテスト
    - AgentCore Memory 統合テスト（AgentCore 利用可能な環境でのみ実行）

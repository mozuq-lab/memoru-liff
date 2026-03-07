# AgentCore Memory 統合 要件定義書

## 概要

AI チューター機能の会話履歴管理を、現在の DynamoDB 自前管理方式から Strands SDK の `SessionManager` インターフェースに移行する。本番環境では AgentCore Memory（短期メモリ）を使用し、ローカル開発・フォールバック用に DynamoDB ベースの `SessionManager` 実装を提供する。環境変数 `TUTOR_SESSION_BACKEND` による切り替えファクトリパターンを導入し、Agent 側のコード変更なしでバックエンドを差し替え可能にする。

なお、ブランチレビューで指摘されていた Critical/High 問題（バリデーション失敗時のセッション消失、HTTP ステータスコード不整合）はコミット `b6715cd` で修正済みのため、本要件のスコープ外とする。

## 関連文書

- **ヒアリング記録**: [interview-record.md](interview-record.md)
- **ユーザストーリー**: [user-stories.md](user-stories.md)
- **受け入れ基準**: [acceptance-criteria.md](acceptance-criteria.md)
- **コンテキストノート**: [note.md](note.md)
- **PRD**: [feature-backlog.md](../../../docs/feature-backlog.md) セクション4「AI チューター」

## 機能要件（EARS記法）

**【信頼性レベル凡例】**:
- 🔵 **青信号**: PRD・設計文書・ユーザヒアリングを参考にした確実な要件
- 🟡 **黄信号**: PRD・設計文書・ユーザヒアリングから妥当な推測による要件
- 🔴 **赤信号**: PRD・設計文書・ユーザヒアリングにない推測による要件

### 通常要件

- REQ-001: システムは `create_tutor_session_manager()` ファクトリ関数を提供し、`TUTOR_SESSION_BACKEND` 環境変数に基づいて適切な `SessionManager` 実装を返さなければならない 🔵 *feature-backlog.md セクション4 SessionManager ファクトリより*
- REQ-002: システムは `AgentCoreMemorySessionManager` を本番環境のデフォルト会話履歴バックエンドとして使用しなければならない 🔵 *feature-backlog.md セクション4・ユーザヒアリングより*
- REQ-003: システムは `DynamoDBSessionManager`（Strands `SessionManager` インターフェース準拠）をフォールバック・ローカル開発用バックエンドとして提供しなければならない 🔵 *feature-backlog.md セクション4・ユーザヒアリングより*
- REQ-004: システムは Strands `Agent` に `session_manager` と `session_id` を注入し、会話履歴の保存・復元を `SessionManager` に委譲しなければならない 🔵 *feature-backlog.md セクション4 Agent 生成コード例より*
- REQ-005: システムは `AGENTCORE_MEMORY_ID` 環境変数を SAM テンプレートのパラメータとして受け取り、AgentCore Memory クライアントに渡さなければならない 🔵 *feature-backlog.md 環境変数一覧より*
- REQ-006: システムは既存の API エンドポイント（POST/GET/DELETE /tutor/sessions, POST /tutor/sessions/{sessionId}/messages）のインターフェースを変更してはならない 🔵 *ユーザヒアリング「API 変更不要」より*
- REQ-007: システムはセッションメタデータ（status, message_count, mode, deck_id, timeout, TTL）を引き続き DynamoDB `tutor_sessions` テーブルで管理しなければならない 🔵 *feature-backlog.md「セッションメタデータはアプリ側で管理」より*

### 条件付き要件

- REQ-101: `TUTOR_SESSION_BACKEND=agentcore` の場合、システムは `bedrock-agentcore-sdk-python` の `AgentCoreMemorySessionManager` を使用しなければならない 🔵 *feature-backlog.md ファクトリコード例より*
- REQ-102: `TUTOR_SESSION_BACKEND=dynamodb` の場合、システムは自前の `DynamoDBSessionManager` を使用しなければならない 🔵 *feature-backlog.md ファクトリコード例より*
- REQ-103: `ENVIRONMENT=dev` かつ `TUTOR_SESSION_BACKEND` が未設定の場合、システムは自動的に `dynamodb` バックエンドを選択しなければならない 🔵 *ユーザヒアリング「dev → 自動的に dynamodb」より*
- REQ-104: `ENVIRONMENT` が `dev` 以外かつ `TUTOR_SESSION_BACKEND` が未設定の場合、システムは `agentcore` バックエンドをデフォルトとして選択しなければならない 🔵 *feature-backlog.md「agentcore（デフォルト / 本番）」より*
- REQ-105: バリデーション失敗時（デッキ不存在等）、システムは既存のアクティブセッションを消失させてはならない 🔵 *ブランチレビュー C-1 指摘事項より（b6715cd で修正済み。リファクタリング時に退行しないこと）*

### 状態要件

- REQ-201: セッションが `active` 状態にある場合、システムは `SessionManager` を通じて会話履歴を取得し、AI に渡さなければならない 🟡 *feature-backlog.md「SessionManager が内部で自動処理」から妥当な推測*
- REQ-202: セッションが `ended` または `timed_out` 状態にある場合、システムはメッセージ送信を拒否しなければならない 🔵 *既存実装・tutor_service.py のタイムアウト/終了チェックより*

### オプション要件

- REQ-301: システムは将来的に `summaryMemoryStrategy` による古い会話の自動要約・コンテキスト圧縮を導入してもよい 🔵 *feature-backlog.md「将来的に長期メモリ戦略を追加」より*
- REQ-302: システムは将来的にセマンティック検索による過去セッションの学習傾向活用を導入してもよい 🔵 *feature-backlog.md「セマンティック検索で活用可能（AgentCore のみ）」より*

### 制約要件

- REQ-401: システムは `bedrock-agentcore-sdk-python` パッケージを新規依存として追加しなければならない 🔵 *feature-backlog.md 前提条件より*
- REQ-402: システムは Lambda 実行ロールに AgentCore Memory API へのアクセス権限を追加しなければならない 🟡 *AgentCore Memory 利用に必要な IAM 権限として妥当な推測*
- REQ-403: システムは `SessionManager` を Lambda のグローバルスコープで初期化し、ハンドラ間で再利用しなければならない 🔵 *feature-backlog.md「Lambda のグローバルスコープで初期化」より*
- REQ-404: Memory ID は CDK/SAM で事前に作成し、環境変数 `AGENTCORE_MEMORY_ID` として Lambda に注入しなければならない 🔵 *ユーザヒアリング「CDK/SAM で手動作成」より*
- REQ-405: 既存のセッションデータの移行は不要とする（TTL 7日で自然消滅） 🔵 *ユーザヒアリング「データ移行不要」より*

## 非機能要件

### パフォーマンス

- NFR-001: AgentCore Memory クライアントの初期化は Lambda グローバルスコープで行い、コールドスタートへの影響を最小化しなければならない 🔵 *feature-backlog.md「コールドスタート対策」より*
- NFR-002: `SessionManager` バックエンドの切り替えによるレスポンス時間の増加は 500ms 以内でなければならない 🟡 *feature-backlog.md のレスポンス時間要件から妥当な推測*
- NFR-003: AgentCore Memory のコストは約 $0.01/セッション（20イベント + 10取得）以内であること 🔵 *feature-backlog.md コスト見積もりより*

### セキュリティ

- NFR-101: AgentCore Memory API へのアクセスは Lambda 実行ロールの IAM ポリシーで制御しなければならない 🟡 *AWS セキュリティベストプラクティスから妥当な推測*
- NFR-102: `AGENTCORE_MEMORY_ID` は環境変数として管理し、コードにハードコードしてはならない 🔵 *feature-backlog.md 環境変数一覧より*

### 可用性

- NFR-201: AgentCore Memory が利用不可の場合、`TutorAIServiceError` を返し、適切なエラーメッセージをユーザーに表示しなければならない 🟡 *既存エラーハンドリングパターンから妥当な推測*

### テスタビリティ

- NFR-301: `SessionManager` はモック化可能なインターフェースとして設計し、ユニットテストで差し替え可能でなければならない 🔵 *既存の DI パターン・テスト戦略より*
- NFR-302: テストカバレッジは 80% 以上を維持しなければならない 🔵 *CLAUDE.md 開発ルールより*

## Edge ケース

### エラー処理

- EDGE-001: AgentCore Memory への接続失敗時、`TutorAIServiceError` でラップして HTTP 503 を返す 🟡 *既存エラーハンドリングパターンから妥当な推測*
- EDGE-002: `AGENTCORE_MEMORY_ID` 環境変数が未設定で `agentcore` バックエンドが選択された場合、起動時にエラーログを出力し `TutorAIServiceError` を発生させる 🟡 *設定ミス防止として妥当な推測*
- EDGE-003: `SessionManager` が返す会話履歴が空の場合（新規セッション）、正常に初回メッセージを処理する 🟡 *既存実装の空メッセージチェックから妥当な推測*
- EDGE-004: `TUTOR_SESSION_BACKEND` に不正な値が設定された場合、`ValueError` を発生させる 🔵 *feature-backlog.md ファクトリコード `raise ValueError` より*

### 境界値

- EDGE-101: セッション当たりの最大メッセージ数（20往復）到達時、SessionManager バックエンドに関わらず正しくセッションを終了する 🔵 *既存実装のメッセージ上限チェックより*
- EDGE-102: 大規模デッキ（100枚以上）のコンテキスト切り詰めは SessionManager 統合後も正常に動作する 🔵 *既存実装のコンテキスト切り詰めロジックより*
- EDGE-103: system_prompt の最大長（150,000文字）は SessionManager バックエンドに関わらず適用される 🔵 *既存実装の `_MAX_SYSTEM_PROMPT_CHARS` 定数より*

# AgentCore Memory 統合 設計ヒアリング記録

**作成日**: 2026-03-07
**ヒアリング実施**: step4 既存情報ベースの差分ヒアリング

## ヒアリング目的

既存の要件定義・設計文書・実装を確認し、AgentCore Memory 統合の技術設計に必要な不明点や設計判断を明確化するためのヒアリングを実施しました。

## 質問と回答

### Q1: 設計の作業規模

**カテゴリ**: 優先順位
**背景**: 設計文書の詳細度を決定するため

**回答**: フル設計（推奨）

**信頼性への影響**:
- 全設計項目（アーキテクチャ、データフロー、型定義、ヒアリング記録）を包括的に作成

---

### Q2: 既存実装の詳細分析の要否

**カテゴリ**: 既存設計確認
**背景**: Strands SDK の SessionManager インターフェースや AgentCore SDK の詳細を把握するため

**回答**: 必要

**信頼性への影響**:
- Strands SessionManager のメソッドシグネチャ（`initialize`, `append_message`, `sync_agent`, `close()`）が確定
- Agent コンストラクタが `session_manager` + `agent_id`（`session_id` ではない）を受け取ることが判明
- `AgentCoreMemorySessionManager` が `AgentCoreMemoryConfig(memory_id, session_id, actor_id, batch_size)` で初期化されることが確定
- これにより、ファクトリ設計の信頼性が 🟡 → 🔵 に向上

---

### Q3: SessionManager 初期化戦略

**カテゴリ**: アーキテクチャ
**背景**: `AgentCoreMemorySessionManager` は `session_id` を Config に含むため、リクエストごとに生成が必要。feature-backlog の「グローバルスコープで初期化」方針との調整が必要

**回答**: クライアントのみグローバル（推奨）
- `AgentCoreMemoryClient` をグローバルスコープで初期化（重い処理は1回）
- `SessionManager` はリクエストごとに `session_id` 付きで生成（軽量）

**信頼性への影響**:
- REQ-403（グローバルスコープ初期化）の実装方針が明確化
- コールドスタート最適化と session_id 要件の両立方法が確定（信頼性: 🔵）

---

### Q4: DynamoDB 設計方針

**カテゴリ**: データモデル
**背景**: DynamoDBSessionManager の会話履歴保存先について。メタデータと会話履歴を分離するか、既存の messages フィールドを流用するか

**回答**:
- DynamoDB バックエンド時: 既存 `tutor_sessions` テーブルの `messages` フィールドを流用
- AgentCore バックエンド時: 会話履歴は AgentCore Memory が管理、DynamoDB はメタデータのみ

**質問の経緯**:
1. 初回質問でユーザーから「メタデータと会話履歴を分けるメリットがあるか」「AgentCore Memory を使う場合の考慮点」を逆質問された
2. メリット・デメリット比較と AgentCore バックエンド時の自然な分離を説明
3. ユーザーが「バックエンドに応じた自然な分離」方針に同意

**信頼性への影響**:
- DynamoDB スキーマ変更が不要であることが確定
- バックエンドごとの会話履歴管理方式が明確化（信頼性: 🔵）

---

### Q5: リファクタリング範囲

**カテゴリ**: 影響範囲
**背景**: セッション開始時の挨拶メッセージ生成も SessionManager 経由にするか、send_message のみか

**回答**: 全て SessionManager 経由（推奨）
- `start_session` の挨拶メッセージ生成も SessionManager 付き Agent で実行
- `send_message` の応答生成も SessionManager 経由
- 一貫性の高い実装

**信頼性への影響**:
- TutorService のリファクタリング範囲が明確化
- REQ-004（Agent への SessionManager 注入）の適用範囲が全メソッドに確定（信頼性: 🔵）

---

### Q6: IAM ポリシー管理方式

**カテゴリ**: セキュリティ
**背景**: AgentCore Memory API へのアクセス権限をどのレベルで管理するか

**回答**: SAM テンプレートで管理（推奨）
- `template.yaml` の Lambda 実行ロールに AgentCore Memory ポリシーを追加

**信頼性への影響**:
- REQ-402（IAM ポリシー追加）の実装方針が確定（信頼性: 🔵）

---

## 技術調査結果（バックグラウンドエージェント）

### Strands SDK SessionManager インターフェース調査

- **SessionManager メソッド**: `initialize(agent, session_id)`, `append_message(message, agent)`, `sync_agent(agent)`, `close()`
- **Agent コンストラクタ**: `session_manager` + `agent_id` パラメータ（`session_id` ではなく `agent_id`）
- **AgentCoreMemoryConfig**: `memory_id`, `session_id`, `actor_id`, `batch_size`, `region_name`
- **Context Manager サポート**: `with` ブロックで `close()` を自動実行
- **batch_size**: デフォルト 1（即時フラッシュ）。`> 1` の場合は `close()` が必須

### feature-backlog.md セクション4 調査

- **ファクトリコード例**: `create_tutor_session_manager()` の完全なコード例を確認
- **インポートパス**: `bedrock_agentcore.memory.integrations.strands` からの import を確認
- **コスト見積もり**: $0.01/セッション（20イベント + 10取得）
- **将来拡張**: `summaryMemoryStrategy`、セマンティック検索

---

## ヒアリング結果サマリー

### 確認できた事項
- SessionManager 初期化戦略: クライアントのみグローバル、SessionManager はリクエスト毎
- DynamoDB 設計: 既存 messages フィールド流用（DynamoDB バックエンド時）
- リファクタリング範囲: start_session / send_message とも SessionManager 経由
- IAM 管理: SAM テンプレートで管理
- Strands Agent は `agent_id` を使用（`session_id` ではない）
- AgentCoreMemorySessionManager は Config 内に `session_id` を含む

### 設計方針の決定事項
- `AgentCoreMemoryClient` シングルトンパターンでコールドスタート最適化
- バックエンドに応じた自然な会話履歴分離（AgentCore: AWS 管理、DynamoDB: 既存テーブル）
- Context Manager パターンの推奨（batch_size=1 でも安全のため）
- `agent_id` は固定値 `"tutor"` を使用

### 残課題
- AgentCore Memory の具体的な IAM ポリシーアクション名（`bedrock-agentcore:*` の詳細化）
- `get_session` での会話履歴取得方法（SessionManager からの読み取り API の詳細）
- DynamoDBSessionManager の Strands SessionManager 全メソッド準拠の実装詳細

### 信頼性レベル分布

**ヒアリング前**:
- 🔵 青信号: 12件
- 🟡 黄信号: 8件
- 🔴 赤信号: 2件

**ヒアリング後**:
- 🔵 青信号: 20件 (+8)
- 🟡 黄信号: 2件 (-6)
- 🔴 赤信号: 0件 (-2)

## 関連文書

- **アーキテクチャ設計**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **型定義**: [interfaces.py](interfaces.py)
- **要件定義**: [requirements.md](../../spec/agentcore-memory-integration/requirements.md)
- **要件ヒアリング記録**: [interview-record.md](../../spec/agentcore-memory-integration/interview-record.md)

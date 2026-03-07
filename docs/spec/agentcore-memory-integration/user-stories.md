# AgentCore Memory 統合 ユーザストーリー

**作成日**: 2026-03-07
**関連要件定義**: [requirements.md](requirements.md)
**ヒアリング記録**: [interview-record.md](interview-record.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: PRD・設計文書・ユーザヒアリングを参考にした確実なストーリー
- 🟡 **黄信号**: PRD・設計文書・ユーザヒアリングから妥当な推測によるストーリー
- 🔴 **赤信号**: PRD・設計文書・ユーザヒアリングにない推測によるストーリー

---

## エピック1: SessionManager ファクトリとバックエンド切り替え

### ストーリー 1.1: 環境変数によるバックエンド切り替え 🔵

**信頼性**: 🔵 *feature-backlog.md セクション4 SessionManager ファクトリ・ユーザヒアリング Q5 より*

**私は** 運用担当者 **として**
**環境変数 `TUTOR_SESSION_BACKEND` を設定するだけで会話履歴のバックエンドを切り替えたい**
**そうすることで** インフラ構成に応じて最適なバックエンドを選択できる

**関連要件**: REQ-001, REQ-101, REQ-102

**詳細シナリオ**:
1. SAM テンプレートまたは環境変数で `TUTOR_SESSION_BACKEND` を設定
2. Lambda 起動時に `create_tutor_session_manager()` が環境変数を読み取る
3. 値に応じて `AgentCoreMemorySessionManager` または `DynamoDBSessionManager` を生成
4. Strands Agent に `session_manager` として注入

**前提条件**:
- `agentcore` 選択時: `AGENTCORE_MEMORY_ID` 環境変数が設定されていること
- `dynamodb` 選択時: `TUTOR_SESSIONS_TABLE` 環境変数が設定されていること

**制約事項**:
- 不正な値の場合は `ValueError` を発生させる
- Agent 側のコードは変更不要（SessionManager インターフェースで抽象化）

**優先度**: Must Have

---

### ストーリー 1.2: ローカル開発の自動バックエンド選択 🔵

**信頼性**: 🔵 *ユーザヒアリング Q10「dev → 自動的に dynamodb」より*

**私は** 開発者 **として**
**ローカル開発時に `TUTOR_SESSION_BACKEND` を明示設定せずとも自動的に DynamoDB バックエンドが選択されるようにしたい**
**そうすることで** ローカル開発環境のセットアップが簡単になる

**関連要件**: REQ-103, REQ-104

**詳細シナリオ**:
1. `ENVIRONMENT=dev` を設定して SAM Local API を起動
2. `TUTOR_SESSION_BACKEND` は未設定
3. ファクトリが `ENVIRONMENT=dev` を検出し、自動的に `dynamodb` を選択
4. DynamoDB Local で会話履歴が管理される

**前提条件**:
- DynamoDB Local が起動していること（`make local-all`）
- `ENVIRONMENT=dev` が設定されていること

**優先度**: Must Have

---

## エピック2: AgentCore Memory 統合

### ストーリー 2.1: AgentCore Memory による会話履歴管理 🔵

**信頼性**: 🔵 *feature-backlog.md セクション4・ユーザヒアリング Q3 より*

**私は** 学習者 **として**
**AI チューターとの会話がセッション内で保持されてほしい**
**そうすることで** 前の質問の文脈を踏まえた回答を得られる

**関連要件**: REQ-002, REQ-004, REQ-005

**詳細シナリオ**:
1. ユーザーがデッキを選んでチューターセッションを開始
2. 会話が AgentCore Memory の短期メモリに自動保存される
3. 追加質問を送信すると、SessionManager が過去の会話を自動復元
4. AI が文脈を踏まえた回答を返す

**前提条件**:
- `TUTOR_SESSION_BACKEND=agentcore` が設定されている
- `AGENTCORE_MEMORY_ID` が設定されている
- Lambda 実行ロールに AgentCore Memory API のアクセス権限がある

**制約事項**:
- セッション当たり最大 20 往復（既存制限を維持）
- AgentCore Memory のコストは約 $0.01/セッション

**優先度**: Must Have

---

### ストーリー 2.2: Memory ID のインフラ管理 🔵

**信頼性**: 🔵 *ユーザヒアリング Q9「CDK/SAM で手動作成」より*

**私は** インフラ管理者 **として**
**AgentCore Memory の Memory ID を CDK/SAM で管理したい**
**そうすることで** インフラの一元管理と環境ごとの設定の明確化ができる

**関連要件**: REQ-005, REQ-404

**詳細シナリオ**:
1. CDK/SAM で AgentCore Memory リソースを作成
2. 生成された Memory ID を SAM テンプレートのパラメータに設定
3. Lambda 環境変数 `AGENTCORE_MEMORY_ID` として注入
4. `create_tutor_session_manager()` が Memory ID を使用して SessionManager を初期化

**前提条件**:
- AgentCore Memory が利用可能な AWS リージョンでのデプロイ

**優先度**: Must Have

---

## エピック3: DynamoDB SessionManager（フォールバック）

### ストーリー 3.1: DynamoDB ベースの SessionManager 実装 🔵

**信頼性**: 🔵 *feature-backlog.md セクション4「DynamoDB バックエンド（フォールバック用）」より*

**私は** 開発者 **として**
**DynamoDB で動作する SessionManager 実装を使いたい**
**そうすることで** ローカル開発や AgentCore 未対応環境でも AI チューターが動作する

**関連要件**: REQ-003, REQ-102

**詳細シナリオ**:
1. Strands SDK の `SessionManager` インターフェースを実装した `DynamoDBSessionManager` クラスを作成
2. 既存の `tutor_sessions` テーブルの `messages` フィールドを利用
3. Agent に `session_manager` として注入
4. 会話履歴の保存・復元が SessionManager 経由で行われる

**前提条件**:
- `tutor_sessions` DynamoDB テーブルが存在すること

**制約事項**:
- DynamoDB アイテムサイズ上限 400KB の制約あり
- 既存テーブルスキーマとの互換性を維持

**優先度**: Must Have

---

## ストーリーマップ

```
エピック1: SessionManager ファクトリとバックエンド切り替え
├── ストーリー 1.1 (🔵 Must Have) — 環境変数によるバックエンド切り替え
└── ストーリー 1.2 (🔵 Must Have) — ローカル開発の自動バックエンド選択

エピック2: AgentCore Memory 統合
├── ストーリー 2.1 (🔵 Must Have) — AgentCore Memory による会話履歴管理
└── ストーリー 2.2 (🔵 Must Have) — Memory ID のインフラ管理

エピック3: DynamoDB SessionManager（フォールバック）
└── ストーリー 3.1 (🔵 Must Have) — DynamoDB ベースの SessionManager 実装

```

## 信頼性レベルサマリー

- 🔵 青信号: 5件 (100%)
- 🟡 黄信号: 0件 (0%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: 高品質 — すべてのストーリーが PRD・設計文書・ユーザヒアリングに基づいている

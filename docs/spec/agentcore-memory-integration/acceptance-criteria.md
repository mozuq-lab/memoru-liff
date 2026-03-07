# AgentCore Memory 統合 受け入れ基準

**作成日**: 2026-03-07
**関連要件定義**: [requirements.md](requirements.md)
**関連ユーザストーリー**: [user-stories.md](user-stories.md)
**ヒアリング記録**: [interview-record.md](interview-record.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: PRD・設計文書・ユーザヒアリングを参考にした確実な基準
- 🟡 **黄信号**: PRD・設計文書・ユーザヒアリングから妥当な推測による基準
- 🔴 **赤信号**: PRD・設計文書・ユーザヒアリングにない推測による基準

---

## REQ-001: SessionManager ファクトリ 🔵

**信頼性**: 🔵 *feature-backlog.md ファクトリコード例・ユーザヒアリング Q5 より*

### Given（前提条件）
- `TUTOR_SESSION_BACKEND` 環境変数が設定されている
- 必要な依存パッケージがインストールされている

### When（実行条件）
- `create_tutor_session_manager()` が呼び出される

### Then（期待結果）
- 環境変数の値に応じた `SessionManager` 実装が返される
- `agentcore` → `AgentCoreMemorySessionManager`
- `dynamodb` → `DynamoDBSessionManager`

### テストケース

#### 正常系

- [ ] **TC-001-01**: `TUTOR_SESSION_BACKEND=agentcore` で AgentCoreMemorySessionManager が返される 🔵
  - **入力**: 環境変数 `TUTOR_SESSION_BACKEND=agentcore`, `AGENTCORE_MEMORY_ID=test-memory-id`
  - **期待結果**: `AgentCoreMemorySessionManager` インスタンスが返される
  - **信頼性**: 🔵 *feature-backlog.md ファクトリコード例より*

- [ ] **TC-001-02**: `TUTOR_SESSION_BACKEND=dynamodb` で DynamoDBSessionManager が返される 🔵
  - **入力**: 環境変数 `TUTOR_SESSION_BACKEND=dynamodb`
  - **期待結果**: `DynamoDBSessionManager` インスタンスが返される
  - **信頼性**: 🔵 *feature-backlog.md ファクトリコード例より*

#### 異常系

- [ ] **TC-001-E01**: 不正な値で ValueError が発生する 🔵
  - **入力**: 環境変数 `TUTOR_SESSION_BACKEND=invalid`
  - **期待結果**: `ValueError("Unknown TUTOR_SESSION_BACKEND: invalid")` が発生
  - **信頼性**: 🔵 *feature-backlog.md ファクトリコード `raise ValueError` より*

- [ ] **TC-001-E02**: `agentcore` 選択時に `AGENTCORE_MEMORY_ID` 未設定でエラー 🟡
  - **入力**: 環境変数 `TUTOR_SESSION_BACKEND=agentcore`, `AGENTCORE_MEMORY_ID` 未設定
  - **期待結果**: `TutorAIServiceError` が発生（設定ミスを明示）
  - **信頼性**: 🟡 *設定ミス防止として妥当な推測*

---

## REQ-103: dev 環境の自動 dynamodb 選択 🔵

**信頼性**: 🔵 *ユーザヒアリング Q10 より*

### Given（前提条件）
- `ENVIRONMENT=dev` が設定されている
- `TUTOR_SESSION_BACKEND` は未設定

### When（実行条件）
- `create_tutor_session_manager()` が呼び出される

### Then（期待結果）
- `DynamoDBSessionManager` が返される

### テストケース

#### 正常系

- [ ] **TC-103-01**: dev 環境で未設定時に dynamodb が選択される 🔵
  - **入力**: `ENVIRONMENT=dev`, `TUTOR_SESSION_BACKEND` 未設定
  - **期待結果**: `DynamoDBSessionManager` インスタンスが返される
  - **信頼性**: 🔵 *ユーザヒアリング Q10 より*

- [ ] **TC-103-02**: prod 環境で未設定時に agentcore が選択される 🔵
  - **入力**: `ENVIRONMENT=prod`, `TUTOR_SESSION_BACKEND` 未設定
  - **期待結果**: `AgentCoreMemorySessionManager` インスタンスが返される
  - **信頼性**: 🔵 *feature-backlog.md「agentcore（デフォルト）」より*

- [ ] **TC-103-03**: dev 環境でも明示的に agentcore を指定できる 🟡
  - **入力**: `ENVIRONMENT=dev`, `TUTOR_SESSION_BACKEND=agentcore`
  - **期待結果**: `AgentCoreMemorySessionManager` インスタンスが返される
  - **信頼性**: 🟡 *明示指定は環境自動選択より優先するのが妥当*

---

## REQ-004: Agent への SessionManager 注入 🔵

**信頼性**: 🔵 *feature-backlog.md Agent 生成コード例より*

### Given（前提条件）
- `SessionManager` が初期化されている
- セッション ID が確定している

### When（実行条件）
- `StrandsTutorAIService.generate_response()` が呼び出される

### Then（期待結果）
- Strands `Agent` が `session_manager` と `session_id` パラメータ付きで生成される
- 会話履歴の保存・復元が SessionManager 経由で行われる

### テストケース

#### 正常系

- [ ] **TC-004-01**: Agent に SessionManager が注入される 🔵
  - **入力**: system_prompt + messages + session_id
  - **期待結果**: `Agent(model=..., system_prompt=..., session_manager=..., session_id=...)` で生成される
  - **信頼性**: 🔵 *feature-backlog.md Agent 生成コード例より*

- [ ] **TC-004-02**: マルチターン会話で履歴が正しく復元される 🟡
  - **入力**: 3往復の会話後に4回目のメッセージを送信
  - **期待結果**: SessionManager が過去3往復の履歴を復元し、文脈を踏まえた回答が返される
  - **信頼性**: 🟡 *SessionManager の動作として妥当な推測*

#### 異常系

- [ ] **TC-004-E01**: SessionManager が接続エラーを返した場合 🟡
  - **入力**: AgentCore Memory への接続が失敗
  - **期待結果**: `TutorAIServiceError` でラップされたエラーが返される
  - **信頼性**: 🟡 *既存エラーハンドリングパターンから妥当な推測*

---

## REQ-003: DynamoDBSessionManager 🔵

**信頼性**: 🔵 *feature-backlog.md セクション4「DynamoDB バックエンド」より*

### Given（前提条件）
- `tutor_sessions` DynamoDB テーブルが存在する
- `TUTOR_SESSION_BACKEND=dynamodb` が設定されている

### When（実行条件）
- セッション内でメッセージが送受信される

### Then（期待結果）
- 会話履歴が DynamoDB テーブルの `messages` フィールドに保存される
- Strands `SessionManager` インターフェースに準拠する

### テストケース

#### 正常系

- [ ] **TC-003-01**: 新規セッションでメッセージが保存される 🔵
  - **入力**: 新しい session_id でメッセージ送信
  - **期待結果**: `messages` フィールドに user/assistant メッセージが保存される
  - **信頼性**: 🔵 *既存実装のメッセージ保存パターンより*

- [ ] **TC-003-02**: 既存セッションの履歴が復元される 🔵
  - **入力**: 既存の session_id でメッセージ送信
  - **期待結果**: 過去の会話履歴が復元された状態で AI が応答する
  - **信頼性**: 🔵 *既存実装の会話復元パターンより*

- [ ] **TC-003-03**: SessionManager インターフェースに準拠している 🔵
  - **入力**: DynamoDBSessionManager のクラス定義
  - **期待結果**: Strands SDK の SessionManager の必須メソッドがすべて実装されている
  - **信頼性**: 🔵 *feature-backlog.md「SessionManager インターフェース」より*

#### 境界値

- [ ] **TC-003-B01**: 20往復のメッセージ上限到達時 🔵
  - **入力**: 20往復のメッセージ後に追加メッセージ送信
  - **期待結果**: セッションが自動終了し、適切なエラーレスポンスが返される
  - **信頼性**: 🔵 *既存実装のメッセージ上限チェックより*

---

## REQ-006: API 互換性維持 🔵

**信頼性**: 🔵 *ユーザヒアリング Q7 より*

### Given（前提条件）
- SessionManager 統合後のバックエンド

### When（実行条件）
- フロントエンドが既存 API エンドポイントを呼び出す

### Then（期待結果）
- リクエスト・レスポンスの形式が変更前と同一

### テストケース

#### 正常系

- [ ] **TC-006-01**: POST /tutor/sessions のレスポンス形式が変わらない 🔵
  - **入力**: `{"deck_id": "xxx", "mode": "free_talk"}`
  - **期待結果**: `{"session_id": "...", "initial_message": "...", ...}` が返される
  - **信頼性**: 🔵 *既存 API 仕様・ユーザヒアリングより*

- [ ] **TC-006-02**: POST /tutor/sessions/{id}/messages のレスポンス形式が変わらない 🔵
  - **入力**: `{"message": "質問"}`
  - **期待結果**: `{"reply": "...", "related_cards": [...]}` が返される
  - **信頼性**: 🔵 *既存 API 仕様・ユーザヒアリングより*

- [ ] **TC-006-03**: GET /tutor/sessions のレスポンス形式が変わらない 🔵
  - **入力**: GET リクエスト
  - **期待結果**: 既存の SessionListResponse 形式
  - **信頼性**: 🔵 *既存 API 仕様より*

---

## 非機能要件テスト

### NFR-001: コールドスタート最適化 🔵

**信頼性**: 🔵 *feature-backlog.md「Lambda のグローバルスコープで初期化」より*

- [ ] **TC-NFR-001-01**: SessionManager のグローバル初期化 🔵
  - **測定項目**: SessionManager がハンドラ外（グローバルスコープ）で初期化されていること
  - **目標値**: コード構造上の検証（コードレビュー）
  - **信頼性**: 🔵 *feature-backlog.md より*

### NFR-301: テスタビリティ 🔵

**信頼性**: 🔵 *既存 DI パターン・CLAUDE.md テストカバレッジ目標より*

- [ ] **TC-NFR-301-01**: SessionManager のモック化 🔵
  - **検証内容**: テストで SessionManager をモックに差し替え可能であること
  - **期待結果**: ユニットテストが SessionManager の実装に依存せず動作する
  - **信頼性**: 🔵 *既存テストパターンより*

- [ ] **TC-NFR-301-02**: テストカバレッジ 80% 以上 🔵
  - **測定項目**: 新規追加コードのテストカバレッジ
  - **目標値**: 80% 以上
  - **信頼性**: 🔵 *CLAUDE.md 開発ルールより*

---

## Edge ケーステスト

### EDGE-001: AgentCore Memory 接続失敗 🟡

**信頼性**: 🟡 *既存エラーハンドリングパターンから妥当な推測*

- [ ] **TC-EDGE-001-01**: AgentCore Memory 接続タイムアウト 🟡
  - **条件**: AgentCore Memory API がタイムアウトする
  - **期待結果**: `TutorAIServiceError` が返され、HTTP 503 がクライアントに返される
  - **信頼性**: 🟡 *既存エラーハンドリングから推測*

### EDGE-004: 不正な TUTOR_SESSION_BACKEND 値 🔵

**信頼性**: 🔵 *feature-backlog.md ファクトリコード `raise ValueError` より*

- [ ] **TC-EDGE-004-01**: 不正なバックエンド値 🔵
  - **条件**: `TUTOR_SESSION_BACKEND=redis` など不正な値
  - **期待結果**: `ValueError` が発生する
  - **信頼性**: 🔵 *feature-backlog.md より*

---

## テストケースサマリー

### カテゴリ別件数

| カテゴリ | 正常系 | 異常系 | 境界値 | 合計 |
|---------|--------|--------|--------|------|
| 機能要件 | 11 | 3 | 1 | 15 |
| 非機能要件 | 3 | 0 | 0 | 3 |
| Edge ケース | 0 | 2 | 0 | 2 |
| **合計** | **14** | **5** | **1** | **20** |

### 信頼性レベル分布

- 🔵 青信号: 16件 (80%)
- 🟡 黄信号: 4件 (20%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: 高品質

### 優先度別テストケース

- **Must Have**: 20件
- **Should Have**: 0件
- **Could Have**: 0件

---

## テスト実施計画

### Phase 1: ファクトリ・バックエンド切り替えテスト
- REQ-001, REQ-103
- TC-001-01 ~ TC-001-E02, TC-103-01 ~ TC-103-03
- 優先度: Must Have

### Phase 2: SessionManager 統合テスト
- REQ-003, REQ-004
- TC-003-01 ~ TC-003-B01, TC-004-01 ~ TC-004-E01
- 優先度: Must Have

### Phase 3: API 互換性・バグ修正テスト
- REQ-006, REQ-501, REQ-502
- TC-006-01 ~ TC-006-03, TC-501-01 ~ TC-502-01
- 優先度: Must Have

### Phase 4: 非機能・Edge ケーステスト
- NFR-001, NFR-301, EDGE-001, EDGE-004
- TC-NFR-001-01 ~ TC-EDGE-004-01
- 優先度: Must Have

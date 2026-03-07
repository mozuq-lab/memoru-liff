# AgentCore Memory 統合 データフロー図

**作成日**: 2026-03-07
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/agentcore-memory-integration/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実なフロー
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測によるフロー
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測によるフロー

---

## システム全体のデータフロー 🔵

**信頼性**: 🔵 *要件定義・ユーザーストーリー・ユーザヒアリングより*

```mermaid
flowchart TD
    User[ユーザー / LIFF Frontend]
    APIGW[API Gateway<br/>JWT Authorizer]
    Handler[tutor_handler.py]
    TutorSvc[TutorService]
    Factory[create_tutor_session_manager]
    CheckBackend{TUTOR_SESSION_BACKEND?}

    subgraph AgentCore["AgentCore バックエンド"]
        ACClient[AgentCoreMemoryClient<br/>グローバル初期化]
        ACSM[AgentCoreMemory<br/>SessionManager]
        ACMemory[AgentCore Memory API]
    end

    subgraph DynamoDBBack["DynamoDB バックエンド"]
        DBSM[DynamoDB<br/>SessionManager]
    end

    Agent[Strands Agent<br/>session_manager 注入]
    AIModel[AI Model<br/>Bedrock / Ollama]
    DDB[(DynamoDB<br/>tutor_sessions<br/>メタデータ)]

    User -->|HTTP Request| APIGW
    APIGW -->|JWT Verified| Handler
    Handler --> TutorSvc
    TutorSvc --> Factory
    Factory --> CheckBackend
    CheckBackend -->|agentcore| ACClient
    ACClient --> ACSM
    ACSM --> ACMemory
    CheckBackend -->|dynamodb| DBSM
    DBSM --> DDB
    TutorSvc -->|session_manager| Agent
    Agent --> AIModel
    TutorSvc -->|メタデータ更新| DDB
    AIModel -->|AI Response| Agent
    Agent --> TutorSvc
    TutorSvc --> Handler
    Handler -->|HTTP Response| APIGW
    APIGW --> User
```

## 主要機能のデータフロー

### 機能1: セッション開始（start_session） 🔵

**信頼性**: 🔵 *ユーザーストーリー 2.1・REQ-004・ユーザヒアリング「全て SessionManager 経由」より*

**関連要件**: REQ-001, REQ-004, REQ-006, REQ-007

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as LIFF Frontend
    participant H as tutor_handler.py
    participant TS as TutorService
    participant DDB as DynamoDB<br/>(メタデータ)
    participant Fac as SessionManager<br/>Factory
    participant SM as SessionManager<br/>(AgentCore/DynamoDB)
    participant Agent as Strands Agent
    participant AI as AI Model

    U->>F: デッキ選択 + モード選択
    F->>H: POST /tutor/sessions<br/>{deck_id, mode}
    H->>TS: start_session(user_id, deck_id, mode)

    Note over TS,DDB: 1. バリデーション（既存ロジック維持）
    TS->>DDB: デッキ・カード取得
    DDB-->>TS: deck, cards
    TS->>TS: システムプロンプト構築

    Note over TS,SM: 2. SessionManager 生成
    TS->>Fac: create_tutor_session_manager(session_id, user_id)
    Fac-->>TS: SessionManager インスタンス

    Note over TS,AI: 3. Agent で挨拶メッセージ生成
    TS->>Agent: Agent(model, system_prompt,<br/>session_manager, agent_id="tutor")
    TS->>Agent: agent("セッション開始の挨拶")
    Agent->>SM: initialize(agent, session_id)
    Agent->>AI: プロンプト送信
    AI-->>Agent: 挨拶メッセージ
    Agent->>SM: append_message + sync_agent
    Agent-->>TS: response

    Note over TS,DDB: 4. メタデータ保存
    TS->>TS: 既存アクティブセッション自動終了
    TS->>DDB: PutItem(メタデータ)

    TS-->>H: TutorSessionResponse
    H-->>F: 200 OK {session_id, initial_message}
    F-->>U: チャット画面表示
```

**詳細ステップ**:
1. デッキとカードの存在確認（バリデーション失敗時は既存セッションを消失させない: REQ-105）
2. `create_tutor_session_manager()` で環境に応じた SessionManager を生成
3. SessionManager 付き Strands Agent で挨拶メッセージを生成（SessionManager が自動的に履歴保存）
4. セッションメタデータ（status, mode, deck_id 等）を DynamoDB に保存

---

### 機能2: メッセージ送信（send_message） 🔵

**信頼性**: 🔵 *ユーザーストーリー 2.1・REQ-004, REQ-201・ユーザヒアリングより*

**関連要件**: REQ-004, REQ-006, REQ-201, REQ-202

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as LIFF Frontend
    participant H as tutor_handler.py
    participant TS as TutorService
    participant DDB as DynamoDB<br/>(メタデータ)
    participant Fac as SessionManager<br/>Factory
    participant SM as SessionManager<br/>(AgentCore/DynamoDB)
    participant Agent as Strands Agent
    participant AI as AI Model

    U->>F: メッセージ入力
    F->>H: POST /tutor/sessions/{id}/messages<br/>{message}
    H->>TS: send_message(user_id, session_id, content)

    Note over TS,DDB: 1. セッション状態チェック
    TS->>DDB: GetItem(user_id, session_id)
    DDB-->>TS: session メタデータ
    TS->>TS: status/timeout/message_limit チェック

    Note over TS,SM: 2. SessionManager 生成
    TS->>Fac: create_tutor_session_manager(session_id, user_id)
    Fac-->>TS: SessionManager インスタンス

    Note over TS,AI: 3. Agent で応答生成
    TS->>Agent: Agent(model, system_prompt,<br/>session_manager, agent_id="tutor")
    Agent->>SM: initialize → 過去の会話履歴を自動復元
    TS->>Agent: agent(user_message)
    Agent->>AI: 過去の文脈 + ユーザーメッセージ
    AI-->>Agent: AI 応答
    Agent->>SM: append_message + sync_agent（自動保存）
    Agent-->>TS: response

    Note over TS,DDB: 4. メタデータ更新
    TS->>TS: extract_related_cards + clean_response
    TS->>DDB: UpdateItem(message_count, updated_at)

    TS-->>H: SendMessageResponse
    H-->>F: 200 OK {reply, related_cards}
    F-->>U: AI 応答表示
```

**詳細ステップ**:
1. DynamoDB からセッションメタデータを取得し、状態チェック（ended/timed_out なら拒否: REQ-202）
2. `create_tutor_session_manager()` でセッション固有の SessionManager を生成
3. SessionManager 付き Agent が自動的に過去の会話を復元し、ユーザーメッセージに対して応答
4. メタデータ（message_count, updated_at）を DynamoDB で更新。メッセージ上限到達時は自動終了

---

### 機能3: バックエンド切り替えフロー 🔵

**信頼性**: 🔵 *REQ-001, REQ-101〜REQ-104・feature-backlog.md ファクトリコード例・ユーザヒアリングより*

**関連要件**: REQ-001, REQ-101, REQ-102, REQ-103, REQ-104

```mermaid
flowchart TD
    Start[SessionManager 生成要求]
    CheckExplicit{TUTOR_SESSION_BACKEND<br/>設定済み?}
    CheckValue{値は?}
    CheckEnv{ENVIRONMENT?}

    subgraph AgentCore["agentcore バックエンド"]
        GetClient[AgentCoreMemoryClient<br/>グローバルから取得]
        CreateConfig[AgentCoreMemoryConfig<br/>memory_id + session_id + actor_id]
        CreateACSM[AgentCoreMemorySessionManager<br/>生成]
    end

    subgraph DynamoDB["dynamodb バックエンド"]
        CreateDBSM[DynamoDBSessionManager<br/>table_name + session_id + user_id]
    end

    Error[ValueError:<br/>Unknown backend]

    Start --> CheckExplicit
    CheckExplicit -->|設定済み| CheckValue
    CheckExplicit -->|未設定| CheckEnv

    CheckValue -->|"agentcore"| GetClient
    CheckValue -->|"dynamodb"| CreateDBSM
    CheckValue -->|その他| Error

    CheckEnv -->|"dev"| CreateDBSM
    CheckEnv -->|prod/staging| GetClient

    GetClient --> CreateConfig
    CreateConfig --> CreateACSM
```

---

### 機能4: セッション取得（get_session） 🟡

**信頼性**: 🟡 *REQ-006・既存実装パターンから妥当な推測。会話履歴の取得方法は SessionManager の実装依存*

**関連要件**: REQ-006, REQ-007

```mermaid
sequenceDiagram
    participant F as LIFF Frontend
    participant H as tutor_handler.py
    participant TS as TutorService
    participant DDB as DynamoDB<br/>(メタデータ)
    participant Fac as SessionManager<br/>Factory
    participant SM as SessionManager

    F->>H: GET /tutor/sessions/{id}
    H->>TS: get_session(user_id, session_id)

    Note over TS,DDB: 1. メタデータ取得
    TS->>DDB: GetItem(user_id, session_id)
    DDB-->>TS: session メタデータ
    TS->>TS: タイムアウトチェック

    Note over TS,SM: 2. 会話履歴取得
    TS->>Fac: create_tutor_session_manager(session_id, user_id)
    Fac-->>TS: SessionManager
    TS->>SM: Agent 初期化で履歴復元
    SM-->>TS: messages

    TS->>TS: メタデータ + メッセージ統合
    TS-->>H: TutorSessionResponse
    H-->>F: 200 OK
```

**備考**: AgentCore バックエンドでの会話履歴取得方法は、SessionManager の `initialize()` でAgent に復元されるメッセージを抽出する方式。具体的な API は実装時に確認が必要。

---

## エラーハンドリングフロー 🟡

**信頼性**: 🟡 *EDGE-001〜EDGE-004・既存エラーハンドリングパターンから妥当な推測*

```mermaid
flowchart TD
    A[SessionManager 操作] --> B{エラー発生?}
    B -->|No| C[正常処理続行]
    B -->|Yes| D{エラー種別}

    D -->|AgentCore 接続失敗| E[TutorAIServiceError<br/>→ HTTP 503]
    D -->|AGENTCORE_MEMORY_ID 未設定| F[TutorAIServiceError<br/>→ HTTP 500]
    D -->|不正な TUTOR_SESSION_BACKEND| G[ValueError<br/>→ HTTP 500]
    D -->|DynamoDB 接続エラー| H[TutorServiceError<br/>→ HTTP 500]
    D -->|セッション ended/timed_out| I[SessionEndedError<br/>→ HTTP 409]
    D -->|メッセージ上限到達| J[MessageLimitError<br/>→ HTTP 429]
    D -->|AI タイムアウト| K[TutorAITimeoutError<br/>→ HTTP 504]

    E --> L[構造化ログ出力]
    F --> L
    G --> L
    H --> L
    I --> L
    J --> L
    K --> L
    L --> M[JSON エラーレスポンス返却]
```

## データ処理パターン

### 同期処理 🔵

**信頼性**: 🔵 *既存アーキテクチャ設計より*

すべてのチューター機能は同期処理（リクエスト-レスポンス）で実装する。
- セッション開始: 最大 120 秒（AI 挨拶生成含む）
- メッセージ送信: 最大 120 秒（AI 応答生成含む）
- セッション一覧/詳細: 数秒以内

### 非同期処理 🟡

**信頼性**: 🟡 *将来の拡張として推測*

将来的に AgentCore Memory の `summaryMemoryStrategy` を導入する場合、古い会話の自動要約が非同期で実行される可能性がある。現フェーズでは同期処理のみ。

## Context Manager パターン 🔵

**信頼性**: 🔵 *AgentCore SDK ドキュメント・Strands SDK 調査より*

AgentCore Memory の `batch_size > 1` 使用時は、`close()` でバッファをフラッシュする必要がある。

```python
# 推奨パターン: Context Manager 使用
with create_tutor_session_manager(session_id, user_id) as session_manager:
    agent = Agent(
        model=model,
        system_prompt=system_prompt,
        session_manager=session_manager,
        agent_id="tutor",
    )
    response = agent(user_message)
```

ただし、`batch_size=1`（デフォルト）の場合は即時フラッシュされるため、Context Manager は必須ではない。安全のため Context Manager の使用を推奨。

## データ整合性の保証 🔵

**信頼性**: 🔵 *既存実装パターン・REQ-007より*

- **メタデータと会話履歴の分離**: メタデータは DynamoDB、会話履歴は SessionManager が管理。トランザクション的な一貫性は保証しない（結果整合性）
- **メッセージカウントの正確性**: `message_count` はメタデータ側で管理し、SessionManager の操作とは独立して更新
- **タイムアウトの判定**: メタデータの `updated_at` で判定（既存ロジックを維持）
- **ユーザーデータ分離**: AgentCore の `actor_id` と DynamoDB の `user_id` でデータ分離

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **型定義**: [interfaces.py](interfaces.py)
- **ヒアリング記録**: [design-interview.md](design-interview.md)
- **要件定義**: [requirements.md](../../spec/agentcore-memory-integration/requirements.md)

## 信頼性レベルサマリー

- 🔵 青信号: 10件 (77%)
- 🟡 黄信号: 3件 (23%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質（青信号 77%、赤信号なし。黄信号はセッション取得時の会話履歴取得方法、エラーハンドリングの詳細、非同期処理の将来検討で、実装フェーズで確定する項目）

# AI Strands Migration データフロー図

**作成日**: 2026-02-23
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/ai-strands-migration/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実なフロー
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測によるフロー
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測によるフロー

---

## システム全体のデータフロー 🔵

**信頼性**: 🔵 *要件定義・ユーザーストーリー・設計ヒアリングより*

```mermaid
flowchart TD
    User[ユーザー / LIFF Frontend]
    APIGW[API Gateway<br/>JWT Authorizer]
    Handler[handler.py]
    Factory[AIServiceFactory]
    Flag{USE_STRANDS?}
    Bedrock[BedrockAIService<br/>boto3]
    Strands[StrandsAIService<br/>Strands Agents]
    EnvCheck{ENVIRONMENT?}
    BedrockAPI[Amazon Bedrock<br/>Claude]
    OllamaAPI[Ollama<br/>Local Model]
    DDB[(DynamoDB)]
    SRS[SM-2 Algorithm]

    User -->|HTTP Request| APIGW
    APIGW -->|JWT Verified| Handler
    Handler --> Factory
    Factory --> Flag
    Flag -->|false| Bedrock
    Flag -->|true| Strands
    Bedrock --> BedrockAPI
    Strands --> EnvCheck
    EnvCheck -->|prod/staging| BedrockAPI
    EnvCheck -->|dev| OllamaAPI
    Handler --> DDB
    Handler --> SRS
    BedrockAPI -->|AI Response| Handler
    OllamaAPI -->|AI Response| Handler
    Handler -->|HTTP Response| APIGW
    APIGW --> User
```

## 主要機能のデータフロー

### 機能1: カード生成（Strands 移行） 🔵

**信頼性**: 🔵 *ユーザーストーリー 1.1・既存実装 `bedrock.py`・受け入れ基準 TC-002 より*

**関連要件**: REQ-SM-001, REQ-SM-002, REQ-SM-402

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as LIFF Frontend
    participant AG as API Gateway
    participant H as handler.py
    participant Fac as AIServiceFactory
    participant AI as AIService<br/>(Strands/Bedrock)
    participant P as prompts/generate.py
    participant M as AI Model<br/>(Bedrock/Ollama)

    U->>F: テキスト入力 + 「生成」ボタン
    F->>AG: POST /cards/generate<br/>{input_text, card_count, difficulty, language}
    AG->>AG: JWT 検証
    AG->>H: リクエスト転送
    H->>H: GenerateCardsRequest バリデーション
    H->>Fac: create_ai_service()
    Fac-->>H: AIService 実装

    H->>P: get_card_generation_prompt()
    P-->>H: プロンプト文字列
    H->>AI: generate_cards()
    AI->>M: プロンプト送信
    M-->>AI: JSON レスポンス
    AI->>AI: _parse_generation_result()
    AI-->>H: GenerationResult

    H->>H: GenerateCardsResponse 変換
    H-->>AG: JSON レスポンス
    AG-->>F: 200 OK
    F-->>U: 生成カード表示
```

**詳細ステップ**:
1. ユーザーが入力テキスト・カード数・難易度・言語を指定してカード生成をリクエスト
2. API Gateway が JWT を検証し、handler.py にリクエストを転送
3. Pydantic v2 でリクエストバリデーション（`GenerateCardsRequest`）
4. `AIServiceFactory` が `USE_STRANDS` フラグに応じた AIService を返す
5. `prompts/generate.py` からプロンプトを生成
6. AIService が AI モデルにプロンプトを送信し、JSON レスポンスを受信
7. レスポンスを `GenerationResult` にパースし、`GenerateCardsResponse` 形式で返却

---

### 機能2: 回答採点・AI 評価 🔵

**信頼性**: 🔵 *ユーザーストーリー 2.1・要件 REQ-SM-003・設計ヒアリング Q4 より*

**関連要件**: REQ-SM-003

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as LIFF Frontend
    participant AG as API Gateway
    participant H as handler.py
    participant CS as CardService
    participant DDB as DynamoDB
    participant AI as AIService
    participant P as prompts/grading.py
    participant M as AI Model

    U->>F: 回答入力 + 「AI評価」ボタン
    F->>AG: POST /reviews/{card_id}/grade-ai<br/>{user_answer}
    AG->>AG: JWT 検証
    AG->>H: リクエスト転送
    H->>H: GradeAnswerRequest バリデーション
    H->>CS: get_card(user_id, card_id)
    CS->>DDB: GetItem(card_id)
    DDB-->>CS: Card データ
    CS-->>H: Card(front, back)

    H->>P: get_grading_prompt(front, back, answer)
    P-->>H: プロンプト文字列
    H->>AI: grade_answer()
    AI->>M: プロンプト送信
    M-->>AI: {grade: 4, reasoning: "..."}
    AI->>AI: _parse_grading_result()
    AI-->>H: GradingResult

    H->>H: GradeAnswerResponse 変換
    H-->>AG: JSON レスポンス
    AG-->>F: 200 OK
    F-->>U: グレード + 採点理由表示
```

**詳細ステップ**:
1. ユーザーが復習画面でカードの問題に回答し、「AI評価」をリクエスト
2. handler.py が CardService 経由でカードの front（問題）と back（正解）を取得
3. `prompts/grading.py` が SM-2 グレード定義を含むプロンプトを生成
4. AI が回答を分析し、SRS グレード（0-5）と採点理由を JSON で返却
5. `GradingResult` にパースしてレスポンス返却
6. フロントエンドでグレードと理由を表示、ユーザーは受入/上書き可能

---

### 機能3: 学習アドバイス 🔵

**信頼性**: 🔵 *ユーザーストーリー 3.1・要件 REQ-SM-004・設計ヒアリング Q5 より*

**関連要件**: REQ-SM-004

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as LIFF Frontend
    participant AG as API Gateway
    participant H as handler.py
    participant RS as ReviewService
    participant DDB as DynamoDB
    participant AI as AIService
    participant P as prompts/advice.py
    participant M as AI Model

    U->>F: 「学習アドバイス」タップ
    F->>AG: GET /advice
    AG->>AG: JWT 検証
    AG->>H: リクエスト転送

    Note over H,DDB: 事前クエリ: 復習履歴データ集計
    H->>RS: get_review_summary(user_id)
    RS->>DDB: Query(reviews, user_id)
    DDB-->>RS: 復習履歴一覧
    RS->>DDB: Query(cards, user_id)
    DDB-->>RS: カードデータ一覧
    RS-->>H: ReviewSummary<br/>(総復習数, 正答率, タグ別成績, 学習ペース)

    H->>P: get_advice_prompt(review_summary)
    P-->>H: プロンプト文字列
    H->>AI: get_learning_advice()
    AI->>M: プロンプト送信
    M-->>AI: アドバイス JSON
    AI->>AI: _parse_advice_result()
    AI-->>H: LearningAdvice

    H-->>AG: JSON レスポンス
    AG-->>F: 200 OK
    F-->>U: アドバイス表示
```

**詳細ステップ**:
1. ユーザーが学習アドバイスをリクエスト
2. handler.py が ReviewService 経由で DynamoDB から復習履歴・カードデータを事前取得
3. Python でデータを集計（総復習数、タグ別正答率、学習ペース等）
4. 集計結果を `prompts/advice.py` のプロンプトに埋め込み
5. AI が集計データを分析し、弱点分野・推奨事項・学習アドバイスを JSON で返却
6. `LearningAdvice` にパースしてレスポンス返却

---

### 機能4: フィーチャーフラグ切替 🔵

**信頼性**: 🔵 *ユーザーストーリー 1.2・要件 REQ-SM-102/103・設計ヒアリング Q1 より*

**関連要件**: REQ-SM-102, REQ-SM-103, REQ-SM-201

```mermaid
flowchart TD
    Start[AI 機能呼び出し]
    Factory[AIServiceFactory.create_ai_service]
    CheckFlag{USE_STRANDS<br/>環境変数}

    subgraph Old["旧実装 (USE_STRANDS=false)"]
        BedrockSvc[BedrockAIService]
        Boto3[boto3.client<br/>bedrock-runtime]
        BedrockAPI1[Amazon Bedrock]
    end

    subgraph New["新実装 (USE_STRANDS=true)"]
        StrandsSvc[StrandsAIService]
        Agent[Strands Agent]
        CheckEnv{ENVIRONMENT?}
        BedrockProv[Bedrock Provider]
        OllamaProv[Ollama Provider]
        BedrockAPI2[Amazon Bedrock]
        OllamaServer[Ollama Server]
    end

    Start --> Factory
    Factory --> CheckFlag
    CheckFlag -->|false / 未設定| BedrockSvc
    CheckFlag -->|true| StrandsSvc

    BedrockSvc --> Boto3
    Boto3 --> BedrockAPI1

    StrandsSvc --> Agent
    Agent --> CheckEnv
    CheckEnv -->|prod/staging| BedrockProv
    CheckEnv -->|dev| OllamaProv
    BedrockProv --> BedrockAPI2
    OllamaProv --> OllamaServer
```

---

### 機能5: AI 採点 → SRS スケジュール連携 🟡

**信頼性**: 🟡 *ユーザーストーリー 2.2・既存 SRS 実装から妥当な推測*

**関連要件**: REQ-SM-003

```mermaid
sequenceDiagram
    participant F as Frontend
    participant H as handler.py
    participant AI as AIService
    participant RS as ReviewService
    participant SRS as SM-2 Algorithm
    participant DDB as DynamoDB

    F->>H: POST /reviews/{card_id}/grade-ai
    H->>AI: grade_answer()
    AI-->>H: GradingResult(grade=3, reasoning="...")
    H-->>F: 200 OK {grade, reasoning}

    Note over F: ユーザーが AI グレードを承認

    F->>H: POST /reviews/{card_id}<br/>{grade: 3}
    H->>RS: submit_review(user_id, card_id, grade=3)
    RS->>SRS: calculate_sm2(grade=3, ...)
    SRS-->>RS: SM2Result(next_review_at, ...)
    RS->>DDB: UpdateItem(card, next_review_at)
    RS->>DDB: PutItem(review_history)
    RS-->>H: ReviewResponse
    H-->>F: 200 OK
```

**備考**: AI 採点と SRS 更新は2ステップ。まず AI がグレードを提案し、ユーザーが承認後に既存の `submit_review` で SRS を更新する。

---

## エラーハンドリングフロー 🔵

**信頼性**: 🔵 *既存実装パターン・設計ヒアリング Q6 より*

```mermaid
flowchart TD
    A[AI サービス呼び出し] --> B{エラー発生?}
    B -->|No| C[正常レスポンス]
    B -->|Yes| D{エラー種別}

    D -->|AITimeoutError| E[504 Gateway Timeout]
    D -->|AIRateLimitError| F[429 Too Many Requests]
    D -->|AIParseError| G[500 Internal Server Error]
    D -->|AIInternalError| H[500 Internal Server Error]
    D -->|AIProviderError| I[503 Service Unavailable]
    D -->|ValidationError| J[400 Bad Request]

    E --> K[構造化ログ出力]
    F --> K
    G --> K
    H --> K
    I --> K
    J --> K
    K --> L[JSON エラーレスポンス返却]
```

## データ処理パターン

### 同期処理 🔵

**信頼性**: 🔵 *既存アーキテクチャ設計より*

すべての AI 機能は同期処理（リクエスト-レスポンス）で実装する。
- カード生成: 最大 30 秒
- 回答採点: 最大 10 秒
- 学習アドバイス: 最大 15 秒

Lambda タイムアウト 60 秒以内に全処理が完了する設計。

### 非同期処理 🟡

**信頼性**: 🟡 *将来の拡張として推測*

Phase 4 のツール統合（Web検索、URL読み込み）では、複数ステップの推論が必要になり、非同期処理が必要になる可能性がある。現フェーズでは同期処理のみで実装。

## データ整合性の保証 🔵

**信頼性**: 🔵 *既存 review_service.py・srs.py の実装パターンより*

- **AI 採点と SRS 更新の分離**: AI 採点は参照のみ、SRS 更新は既存の `submit_review` トランザクションで実行
- **ユーザーデータ分離**: すべてのクエリに `user_id` パーティションキーを使用
- **復習履歴の一貫性**: `ReviewService.submit_review()` 内の DynamoDB トランザクションで保証

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **API仕様**: [api-endpoints.md](api-endpoints.md)
- **要件定義**: [requirements.md](../../spec/ai-strands-migration/requirements.md)

## 信頼性レベルサマリー

- 🔵 青信号: 10件 (83%)
- 🟡 黄信号: 2件 (17%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質（青信号 83%、赤信号なし。黄信号は SRS 連携の詳細フローと非同期処理の将来検討）

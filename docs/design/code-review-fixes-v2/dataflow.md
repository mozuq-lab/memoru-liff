# code-review-fixes-v2 データフロー図

**作成日**: 2026-02-17
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/code-review-fixes-v2/requirements.md)

**【信頼性レベル凡例】**:

- 🔵 **青信号**: 要件定義書・設計文書・ユーザヒアリング・コード分析から確実なフロー
- 🟡 **黄信号**: 要件定義書・設計文書から妥当な推測によるフロー
- 🔴 **赤信号**: 要件定義書・設計文書にない推測によるフロー

---

## 修正対象のデータフロー一覧

本設計では既存のデータフローを修正するため、**変更前後の差分** を示す。

---

## 1. LINE 連携フロー（H-01: 本人性検証追加） 🔵

**信頼性**: 🔵 *H-01: ユーザヒアリングで LIFF IDトークン + LINE API 検証に決定*

**関連要件**: REQ-V2-021〜023

### Before（現行: line_user_id 直接送信）

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant L as LIFF App
    participant SDK as LIFF SDK
    participant API as API Gateway
    participant H as Lambda Handler
    participant DB as DynamoDB

    U->>L: LINE連携ボタン押下
    L->>SDK: liff.getProfile()
    SDK-->>L: profile.userId
    L->>API: POST /users/link-line {line_user_id}
    API->>H: handler.link_line()
    H->>DB: UpdateItem(user_id, line_user_id)
    DB-->>H: 更新完了
    H-->>API: {success, message}
    API-->>L: レスポンス
```

### After（修正後: IDトークン検証）

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant L as LIFF App
    participant SDK as LIFF SDK
    participant API as API Gateway
    participant H as Lambda Handler
    participant LS as LineService
    participant LINE as LINE API
    participant DB as DynamoDB

    U->>L: LINE連携ボタン押下
    L->>SDK: liff.getIDToken()
    SDK-->>L: id_token (JWT)
    L->>API: POST /users/link-line {id_token}
    API->>H: handler.link_line()
    H->>LS: verify_id_token(id_token)
    LS->>LINE: POST /oauth2/v2.1/verify {id_token, client_id}
    LINE-->>LS: {sub: line_user_id, ...}
    LS-->>H: line_user_id
    H->>DB: UpdateItem(user_id, line_user_id)
    DB-->>H: 更新完了
    H->>DB: GetItem(user_id)
    DB-->>H: User データ
    H-->>API: {success, data: User}
    API-->>L: User 型レスポンス
```

**変更ポイント**:
1. フロントエンド: `liff.getProfile()` → `liff.getIDToken()` 🔵
2. リクエスト: `{line_user_id}` → `{id_token}` 🔵
3. サーバー: LINE API で ID トークン検証を追加 🔵
4. レスポンス: `{success, message}` → `{success, data: User}` (H-02) 🔵

---

## 2. カード作成フロー（CR-02: トランザクション修正） 🔵

**信頼性**: 🔵 *CR-02: card_service.py のコード分析で確認*

**関連要件**: REQ-V2-011〜014

### Before（現行: card_count 問題あり）

```mermaid
sequenceDiagram
    participant H as Handler
    participant CS as CardService
    participant DB as DynamoDB

    H->>CS: create_cards(user_id, cards)
    CS->>DB: TransactWriteItems
    Note over DB: Update users SET card_count = card_count + 1
    Note over DB: card_count未存在時エラー
    Note over DB: Put cards
    Note over DB: Put reviews
    DB-->>CS: 成功 or TransactionCanceledException
    CS-->>H: 一律 CardLimitExceededError
```

### After（修正後: 安全なトランザクション）

```mermaid
sequenceDiagram
    participant H as Handler
    participant US as UserService
    participant CS as CardService
    participant DB as DynamoDB

    H->>US: get_or_create_user(user_id)
    US->>DB: GetItem(user_id)
    alt ユーザー未存在
        US->>DB: PutItem(user_id, card_count=0, timezone='Asia/Tokyo')
    end
    DB-->>US: User
    US-->>H: User

    H->>CS: create_cards(user_id, cards)
    CS->>DB: TransactWriteItems
    Note over DB: Update users SET card_count = if_not_exists(card_count, 0) + 1
    Note over DB: Condition: if_not_exists(card_count, 0) < 2000
    Note over DB: Put cards
    Note over DB: Put reviews
    DB-->>CS: 成功 or TransactionCanceledException

    alt TransactionCanceledException
        CS->>CS: CancellationReasons 解析
        alt ConditionalCheckFailed (index 0)
            CS-->>H: CardLimitExceededError
        else その他
            CS-->>H: InternalError
        end
    end
    CS-->>H: 作成されたカード
```

**変更ポイント**:
1. ハンドラーで `get_or_create_user()` を事前呼び出し 🔵
2. `if_not_exists(card_count, :zero)` で安全な加算 🔵
3. `CancellationReasons` で正確なエラー分類 🔵

---

## 3. カード削除フロー（CR-02: card_count 減算追加） 🔵

**信頼性**: 🔵 *CR-02: delete_card() の card_count 未減算を確認*

**関連要件**: REQ-V2-013

### Before（現行: card_count 未減算）

```mermaid
sequenceDiagram
    participant H as Handler
    participant CS as CardService
    participant DB as DynamoDB

    H->>CS: delete_card(user_id, card_id)
    CS->>DB: DeleteItem(cards)
    CS->>DB: DeleteItem(reviews)
    Note over DB: card_count は減算されない
    CS-->>H: 削除完了
```

### After（修正後: トランザクションで減算）

```mermaid
sequenceDiagram
    participant H as Handler
    participant CS as CardService
    participant DB as DynamoDB

    H->>CS: delete_card(user_id, card_id)
    CS->>DB: TransactWriteItems
    Note over DB: Delete cards (ConditionExpression: attribute_exists)
    Note over DB: Delete reviews
    Note over DB: Update users SET card_count = card_count - 1
    Note over DB: Condition: card_count > 0
    DB-->>CS: 成功
    CS-->>H: 削除完了
```

---

## 4. 通知送信フロー（H-03: 時刻判定追加） 🔵

**信頼性**: 🔵 *H-03: notification_service.py のコード分析で確認*

**関連要件**: REQ-V2-041〜042, REQ-V2-111〜112

### Before（現行: 日付チェックのみ）

```mermaid
sequenceDiagram
    participant EB as EventBridge
    participant L as Lambda
    participant NS as NotificationService
    participant DB as DynamoDB
    participant LINE as LINE API

    EB->>L: 5分ごと起動
    L->>NS: process_notifications()
    NS->>DB: Scan(users, filter=line_user_id exists)
    DB-->>NS: linked_users

    loop 各ユーザー
        NS->>NS: last_notified_date == today?
        alt 未通知
            NS->>DB: Query(reviews, due <= now)
            DB-->>NS: due_count
            alt due_count > 0
                NS->>LINE: Push Message
            end
        end
    end
```

### After（修正後: タイムゾーン + 時刻チェック追加）

```mermaid
sequenceDiagram
    participant EB as EventBridge
    participant L as Lambda
    participant NS as NotificationService
    participant DB as DynamoDB
    participant LINE as LINE API

    EB->>L: 5分ごと起動
    L->>NS: process_notifications()
    NS->>DB: Scan(users, filter=line_user_id exists)
    DB-->>NS: linked_users

    loop 各ユーザー
        NS->>NS: last_notified_date == today?
        alt 未通知
            NS->>NS: should_notify(user, current_utc)?
            Note over NS: user.timezone (default: Asia/Tokyo)
            Note over NS: ローカル時刻 vs notification_time
            Note over NS: ±5分の精度で判定
            alt 通知時刻と一致
                NS->>DB: Query(reviews, due <= now)
                DB-->>NS: due_count
                alt due_count > 0
                    NS->>LINE: Push Message
                end
            end
        end
    end
```

**変更ポイント**:
1. `should_notify()` メソッド追加（タイムゾーン変換 + 時刻比較） 🔵
2. users テーブルの `timezone` 属性参照 🔵
3. デフォルトタイムゾーン `Asia/Tokyo` 🔵

---

## 5. API ルーティングフロー（CR-01: 3レイヤー統一） 🔵

**信頼性**: 🔵 *CR-01: コード分析で確認*

**関連要件**: REQ-V2-001〜004

### 修正後の統一されたルーティング

```mermaid
flowchart LR
    subgraph Frontend
        A1["api.ts: PUT /users/me/settings"]
        A2["api.ts: POST /reviews/{cardId}"]
        A3["api.ts: POST /users/link-line"]
    end

    subgraph SAM["SAM Template"]
        B1["Path: /users/me/settings"]
        B2["Path: /reviews/{cardId}"]
        B3["Path: /users/link-line"]
    end

    subgraph Handler
        C1["@app.put('/users/me/settings')"]
        C2["@app.post('/reviews/<card_id>')"]
        C3["@app.post('/users/link-line')"]
    end

    A1 --> B1 --> C1
    A2 --> B2 --> C2
    A3 --> B3 --> C3
```

---

## エラーハンドリングフロー 🔵

**信頼性**: 🔵 *CR-02, H-01 のエラー分類設計より*

### card_count トランザクションエラー分類

```mermaid
flowchart TD
    A[TransactWriteItems 実行] --> B{結果}
    B -->|成功| C[カード作成完了]
    B -->|TransactionCanceledException| D{CancellationReasons 解析}
    D -->|"reasons[0].Code == ConditionalCheckFailed"| E[CardLimitExceededError<br/>409 Conflict]
    D -->|その他のエラー| F[InternalError<br/>500 Internal Server Error]
    D -->|CancellationReasons なし| F
```

### LINE ID トークン検証エラー分類

```mermaid
flowchart TD
    A["POST /users/link-line {id_token}"] --> B{id_token 存在?}
    B -->|なし| C[400 Bad Request<br/>id_token is required]
    B -->|あり| D[LINE API /oauth2/v2.1/verify]
    D --> E{検証結果}
    E -->|200 OK| F[line_user_id 取得 → 連携確定]
    E -->|400/401| G[401 Unauthorized<br/>ID token verification failed]
```

---

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **API 仕様**: [api-endpoints.md](api-endpoints.md)
- **要件定義**: [requirements.md](../../spec/code-review-fixes-v2/requirements.md)
- **既存データフロー**: [dataflow.md](../memoru-liff/dataflow.md)

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 12件 | 100% |
| 🟡 黄信号 | 0件 | 0% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（全フローが青信号）

# deck-review-fixes データフロー図

**作成日**: 2026-03-01
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/deck-review-fixes/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実なフロー
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測によるフロー
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測によるフロー

---

## フロー1: デッキ別カード一覧表示（H-1 / REQ-001） 🔵

**信頼性**: 🔵 *レビュー H-1・ユーザーストーリー 1.1 より*

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant DP as DecksPage
    participant CP as CardsPage
    participant CC as CardsContext
    participant API as API Gateway
    participant CS as CardService
    participant DB as DynamoDB

    U->>DP: デッキをタップ
    DP->>CP: navigate("/cards?deck_id=xxx")
    CP->>CP: useSearchParams() で deck_id 取得
    CP->>CC: fetchCards(deckId)
    CC->>API: GET /cards?deck_id=xxx
    API->>CS: list_cards(user_id, deck_id=xxx)
    CS->>DB: Query(PK=user_id) + FilterExpression(deck_id=xxx)
    DB-->>CS: 該当カード一覧
    CS-->>API: CardListResponse
    API-->>CC: JSON レスポンス
    CC-->>CP: cards 状態更新
    CP-->>U: デッキ名ヘッダー + フィルタされたカード一覧表示
```

**詳細ステップ**:
1. DecksPage でデッキタップ → `/cards?deck_id=xxx` に遷移
2. CardsPage が `useSearchParams()` で `deck_id` を読み取り
3. CardsContext の `fetchCards(deckId)` を呼び出し
4. バックエンド `GET /cards?deck_id=xxx` はフィルタ対応済み
5. deck_id 指定時はページヘッダーにデッキ名を表示（REQ-101）
6. deck_id なしの場合は従来通り全カード表示（REQ-102）

---

## フロー2: カード deck_id 解除（H-2 / REQ-002） 🔵

**信頼性**: 🔵 *レビュー H-2・ユーザーストーリー 2.1 より*

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant CDP as CardDetailPage
    participant DS as DeckSelector
    participant API as API Gateway
    participant CS as CardService
    participant DB as DynamoDB

    U->>CDP: カード詳細画面を開く
    CDP->>DS: 現在の deck_id を渡す
    U->>DS: 「未分類」を選択
    DS-->>CDP: selectedDeckId = null
    U->>CDP: 保存ボタン押下
    CDP->>API: PUT /cards/:id { "deck_id": null }
    API->>CS: update_card(user_id, card_id, deck_id=None)
    Note over CS: deck_id=None → sentinel ではなく<br/>明示的 null と判定
    CS->>DB: UpdateExpression: "REMOVE deck_id"
    DB-->>CS: 更新成功
    CS-->>API: 更新されたカード
    API-->>CDP: 200 OK
    CDP->>CDP: fetchDecks() 呼び出し（L-4）
```

**3層修正の流れ**:
1. **フロントエンド型定義**: `UpdateCardRequest.deck_id` を `string | null` に変更
2. **フロントエンド送信**: CardDetailPage が `{ deck_id: null }` を API に送信
3. **バックエンド処理**: `card_service.py` が `deck_id=None` を検出 → `REMOVE deck_id`

**null vs 未送信の区別**:
```
{ "deck_id": null }     → REMOVE deck_id（明示的クリア）
{ "front": "updated" }  → deck_id 変更なし（未送信）
{ "deck_id": "deck-1" } → SET deck_id = "deck-1"（値変更）
```

---

## フロー3: デッキ作成（アトミック検証）（H-3, H-4 / REQ-003, REQ-004） 🔵

**信頼性**: 🔵 *追加レビュー H-3, H-4・ヒアリング回答より*

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant FE as フロントエンド
    participant API as API Gateway
    participant DH as decks_handler
    participant DS as DeckService
    participant DB as DynamoDB

    U->>FE: デッキ作成フォーム送信
    FE->>API: POST /decks { "name": "新デッキ" }
    API->>DH: create_deck_handler()
    DH->>DS: create_deck(user_id, "新デッキ")
    DS->>DB: Query(PK=user_id, Select=COUNT)
    DB-->>DS: count = 49
    Note over DS: 楽観的チェック OK (49 < 50)
    DS->>DB: PutItem(ConditionExpression=<br/>"attribute_not_exists(user_id) AND<br/>attribute_not_exists(deck_id)")
    DB-->>DS: 成功
    DS->>DB: Query(PK=user_id, Select=COUNT)
    DB-->>DS: count = 50
    Note over DS: 作成後チェック OK (50 <= 50)
    DS-->>DH: Deck オブジェクト
    DH-->>API: HTTP 201
    API-->>FE: デッキ作成成功
    FE-->>U: 成功表示
```

**上限超過時のフロー**:
```mermaid
sequenceDiagram
    participant DS as DeckService
    participant DB as DynamoDB
    participant DH as decks_handler

    DS->>DB: Query(PK=user_id, Select=COUNT)
    DB-->>DS: count = 50
    Note over DS: 楽観的チェック NG (50 >= 50)
    DS-->>DH: DeckLimitExceededError
    DH-->>DH: HTTP 409 Conflict レスポンス生成
```

**レース検出時のフロー**:
```mermaid
sequenceDiagram
    participant DS as DeckService
    participant DB as DynamoDB

    DS->>DB: PutItem（成功）
    DS->>DB: Query(PK=user_id, Select=COUNT)
    DB-->>DS: count = 51
    Note over DS: レース検出 (51 > 50)
    DS->>DB: DeleteItem（ロールバック）
    DS-->>DS: DeckLimitExceededError
```

---

## フロー4: デッキフィールドクリア（M-3 / REQ-105, REQ-106） 🔵

**信頼性**: 🔵 *レビュー M-3 より*

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant DFM as DeckFormModal
    participant DC as DecksContext
    participant API as API Gateway
    participant DS as DeckService
    participant DB as DynamoDB

    U->>DFM: description を空にして保存
    DFM->>DFM: 差分検出: description 変更あり
    DFM->>DC: updateDeck(deckId, { description: null })
    DC->>API: PUT /decks/:id { "description": null }
    API->>DS: update_deck(user_id, deck_id, description=None)
    Note over DS: description=None → REMOVE
    DS->>DB: UpdateExpression: "REMOVE description SET updated_at = :t"
    DB-->>DS: 更新成功
    DS-->>API: 200 OK
    API-->>DC: 更新レスポンス
    DC-->>DFM: 成功
```

---

## フロー5: 復習対象カード数の正確な取得（M-1 / REQ-005） 🔵

**信頼性**: 🔵 *レビュー M-1 より*

```mermaid
sequenceDiagram
    participant FE as フロントエンド
    participant API as API Gateway
    participant RS as ReviewService
    participant DB as DynamoDB

    FE->>API: GET /cards/due?deck_id=xxx&limit=10
    API->>RS: get_due_cards(user_id, limit=10, deck_id=xxx)
    RS->>DB: Query(user_id, FilterExpression=<br/>deck_id=xxx AND next_review_at<=now)
    DB-->>RS: 20件の復習対象カード
    Note over RS: total_due_count = 20（全件）
    Note over RS: cards = 先頭10件（limit適用）
    RS-->>API: { cards: [...10件], total_due_count: 20 }
    API-->>FE: JSON レスポンス
    FE-->>FE: 「残り20件」と表示
```

**修正のポイント**: `total_due_count` は limit 適用前の全件数を返す。limit は返却するカードの件数のみに影響する。

---

## フロー6: handler.py ルーター分割（L-2 / REQ-401） 🔵

**信頼性**: 🔵 *ヒアリング回答（ルーター分割方式）より*

```mermaid
flowchart TD
    A[Lambda 呼び出し] --> B[handler.py<br/>lambda_handler]
    B --> C[APIGatewayHttpResolver]
    C --> D{URL パス}
    D -->|/users/*| E[user_handler.py<br/>Router]
    D -->|/cards/*| F[cards_handler.py<br/>Router]
    D -->|/decks/*| G[decks_handler.py<br/>Router]
    D -->|/reviews/*| H[review_handler.py<br/>Router]
    D -->|/cards/generate| I[ai_handler.py<br/>Router]

    E --> J[UserService]
    F --> K[CardService]
    G --> L[DeckService]
    H --> M[ReviewService]
    I --> N[AIService]

    subgraph shared.py
        O[get_user_id_from_context]
        P[_map_ai_error_to_http]
    end

    E -.-> O
    F -.-> O
    G -.-> O
    H -.-> O
    I -.-> O
    I -.-> P
```

**エンドポイント分配**:

| ファイル | エンドポイント | ルート数 |
|---------|---------------|---------|
| `user_handler.py` | `/users/me`, `/users/link-line`, `/users/me/settings`, `/users/me/unlink-line` | 4 |
| `cards_handler.py` | `/cards` (GET/POST), `/cards/<id>` (GET/PUT/DELETE) | 5 |
| `decks_handler.py` | `/decks` (GET/POST), `/decks/<id>` (PUT/DELETE) | 4 |
| `review_handler.py` | `/cards/due` (GET), `/reviews/<id>` (POST), `/reviews/<id>/undo` (POST) | 3 |
| `ai_handler.py` | `/cards/generate` (POST) | 1 |

---

## フロー7: DeckFormModal 差分送信（M-4 / REQ-202） 🔵

**信頼性**: 🔵 *レビュー M-4 より*

```mermaid
flowchart TD
    A[DeckFormModal 開く<br/>initialValues 保存] --> B[ユーザーがフィールド編集]
    B --> C[保存ボタン押下]
    C --> D{各フィールド比較}
    D -->|name 変更あり| E[payload.name = newName]
    D -->|description 変更あり| F{空文字?}
    F -->|空文字| G[payload.description = null]
    F -->|値あり| H[payload.description = newDesc]
    D -->|color 変更あり| I{選択解除?}
    I -->|選択解除| J[payload.color = null]
    I -->|値あり| K[payload.color = newColor]
    D -->|変更なし| L[payload に含めない]
    E --> M[updateDeck API 呼び出し]
    G --> M
    H --> M
    J --> M
    K --> M
    L --> M
```

---

## フロー8: CardDetailPage デッキ変更後の更新（L-4 / REQ-203） 🔵

**信頼性**: 🔵 *レビュー L-4 より*

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant CDP as CardDetailPage
    participant CC as CardsContext
    participant DC as DecksContext
    participant API as API Gateway

    U->>CDP: デッキ変更 → 保存
    CDP->>CC: updateCard(cardId, { deck_id: newDeckId })
    CC->>API: PUT /cards/:id
    API-->>CC: 200 OK
    CC-->>CDP: 更新成功
    CDP->>DC: fetchDecks()
    DC->>API: GET /decks（card_count/due_count 再取得）
    API-->>DC: デッキ一覧（更新されたカウント）
    DC-->>DC: decks 状態更新
```

**効果**: デッキの `card_count` / `due_count` が即座に反映され、DecksPage やホーム画面の DeckSummary に正確な値が表示される。

---

## エラーハンドリングフロー 🔵

**信頼性**: 🔵 *既存実装パターン・要件定義書 EDGE-001〜003 より*

```mermaid
flowchart TD
    A[エラー発生] --> B{エラー種別}
    B -->|DeckLimitExceededError| C[409 Conflict<br/>H-3 修正]
    B -->|ConditionalCheckFailedException| D[DeckLimitExceededError に変換<br/>H-4 修正]
    B -->|DeckNotFoundError| E[404 Not Found]
    B -->|CardNotFoundError| F[404 Not Found]
    B -->|ValidationError| G[400 Bad Request]
    B -->|UnauthorizedError| H[401 Unauthorized]

    C --> I[エラーメッセージ返却]
    D --> C
    E --> I
    F --> I
    G --> I
    H --> I
    I --> J[フロントエンドでエラー表示]
```

---

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **設計ヒアリング記録**: [design-interview.md](design-interview.md)
- **要件定義**: [requirements.md](../../spec/deck-review-fixes/requirements.md)
- **受け入れ基準**: [acceptance-criteria.md](../../spec/deck-review-fixes/acceptance-criteria.md)

## 信頼性レベルサマリー

- 🔵 青信号: 8件 (100%)
- 🟡 黄信号: 0件 (0%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質

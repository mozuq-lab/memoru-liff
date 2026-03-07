# Auto Study Notes データフロー図

**作成日**: 2026-03-07
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/auto-study-notes/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実なフロー
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測によるフロー
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測によるフロー

---

## 主要機能のデータフロー

### フロー1: 要約ノート生成（キャッシュミス） 🔵

**信頼性**: 🔵 *ユーザーストーリー1.1・REQ-ASN-001・REQ-ASN-021より*

**関連要件**: REQ-ASN-001, REQ-ASN-021, REQ-ASN-031〜034, REQ-ASN-051

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as フロントエンド
    participant A as API Gateway
    participant H as StudyNotesHandler
    participant S as StudyNotesService
    participant AI as AIService
    participant Cards as cards テーブル
    participant Reviews as reviews テーブル
    participant Cache as study-notes テーブル
    participant Bedrock as Amazon Bedrock

    U->>F: 「要約ノートを生成」タップ
    F->>A: POST /study-notes/generate
    A->>A: JWT認証 + レート制限チェック
    A->>H: リクエスト転送
    H->>S: generate_or_get(user_id, source_type, source_id)

    S->>Cache: キャッシュ確認 (GetItem)
    Cache-->>S: キャッシュなし / is_stale=true

    S->>Cards: デッキのカード取得 (Query by deck_id)
    Cards-->>S: カード一覧 (front, back, tags)
    S->>S: カード数バリデーション (5枚以上)

    opt カード数 > 100枚
        S->>Reviews: ease_factor取得 (BatchGetItem)
        Reviews-->>S: ease_factor
        S->>S: ease_factor昇順ソートで上位100枚を選択
    end

    S->>AI: generate_study_notes(cards)
    AI->>Bedrock: プロンプト + カード内容
    Bedrock-->>AI: Markdown形式の要約ノート
    AI-->>S: StudyNotesResult

    S->>Cache: キャッシュ保存 (PutItem)
    S-->>H: 要約ノートレスポンス
    H-->>A: 200 OK + JSON
    A-->>F: レスポンス
    F->>F: react-markdown でレンダリング
    F-->>U: 要約ノート表示
```

**詳細ステップ**:
1. ユーザーがデッキ詳細画面で「要約ノートを生成」ボタンをタップ
2. フロントエンドが `POST /study-notes/generate` を呼び出し
3. API Gatewayが JWT認証とレート制限（10req/min）をチェック
4. StudyNotesService がキャッシュを確認（キャッシュなし or is_stale=true）
5. cards テーブルからデッキのカード一覧を取得
6. カード数バリデーション（5枚未満は拒否、100枚超はease_factor昇順で上位100枚を選択）
7. AIService.generate_study_notes() で Bedrock Claude に要約生成を依頼
8. 生成結果を study-notes テーブルにキャッシュ保存
9. フロントエンドが react-markdown で Markdown をレンダリング

---

### フロー2: 要約ノート取得（キャッシュヒット） 🔵

**信頼性**: 🔵 *ユーザーストーリー2.1・REQ-ASN-023より*

**関連要件**: REQ-ASN-023, NFR-ASN-002

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as フロントエンド
    participant A as API Gateway
    participant H as StudyNotesHandler
    participant S as StudyNotesService
    participant Cache as study-notes テーブル

    U->>F: デッキ詳細画面を開く
    F->>A: GET /study-notes?source_type=deck&source_id={deck_id}
    A->>H: リクエスト転送
    H->>S: get_cached(user_id, source_type, source_id)

    S->>Cache: キャッシュ確認 (GetItem)
    Cache-->>S: キャッシュあり (is_stale=false)

    S-->>H: キャッシュされた要約ノート
    H-->>A: 200 OK + JSON
    A-->>F: レスポンス (500ms以内)
    F->>F: react-markdown でレンダリング
    F-->>U: 要約ノート即時表示
```

---

### フロー3: キャッシュ無効化（カードCRUD時） 🔵

**信頼性**: 🔵 *REQ-ASN-022・設計ヒアリング「同期的フラグ更新」選択より*

**関連要件**: REQ-ASN-022, REQ-ASN-103

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as フロントエンド
    participant H as CardHandler
    participant CS as CardService
    participant Cards as cards テーブル
    participant Cache as study-notes テーブル

    U->>F: カードを追加/更新/削除
    F->>H: POST/PUT/DELETE /cards
    H->>CS: カード操作実行

    CS->>Cards: カードの書き込み
    Cards-->>CS: 成功

    CS->>Cache: is_stale=true に更新 (UpdateItem)
    Note over CS,Cache: source_type=deck, source_id=deck_id
    Note over CS,Cache: タグのキャッシュも無効化

    CS-->>H: 操作完了
    H-->>F: レスポンス
    F-->>U: 操作結果表示
```

**詳細ステップ**:
1. ユーザーがカードのCRUD操作を実行
2. CardService がカードの書き込みを完了
3. 同一トランザクション内で study-notes テーブルの `is_stale` フラグを `true` に更新
4. カードの `deck_id` に紐づくキャッシュと、カードの `tags` に紐づくキャッシュの両方を無効化
5. カード更新時にdeck_idやtagsが変更された場合は、旧値のキャッシュも無効化

---

### フロー4: 無効化後の再生成通知 🟡

**信頼性**: 🟡 *REQ-ASN-103・UX設計として妥当な推測*

**補足（EDGE-ASN-003）**: AWS LambdaはAPI Gatewayのコネクション切断後も実行を継続するため、フロー1の生成中にユーザーがページを離脱しても、生成結果はキャッシュに保存される。次回アクセス時にはフロー2（キャッシュヒット）で即座に表示される。

**関連要件**: REQ-ASN-103

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as フロントエンド
    participant A as API Gateway
    participant S as StudyNotesService
    participant Cache as study-notes テーブル

    U->>F: デッキ詳細画面を開く
    F->>A: GET /study-notes?source_type=deck&source_id={deck_id}
    A->>S: get_cached(user_id, deck, deck_id)

    S->>Cache: キャッシュ確認 (GetItem)
    Cache-->>S: キャッシュあり (is_stale=true)

    S-->>A: is_stale=true + 古い要約ノート
    A-->>F: レスポンス
    F->>F: 古い要約 + 「要約が古くなっています」通知表示
    F-->>U: 再生成ボタン付きの通知表示

    opt ユーザーが再生成を選択
        U->>F: 「再生成」タップ
        Note over F,S: フロー1 の要約ノート生成フローを実行
    end
```

---

### フロー5: カード数不足エラー 🔵

**信頼性**: 🔵 *REQ-ASN-101・ヒアリングQ5より*

**関連要件**: REQ-ASN-101

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant F as フロントエンド
    participant S as StudyNotesService
    participant Cards as cards テーブル

    U->>F: 「要約ノートを生成」タップ
    F->>S: generate_or_get(user_id, deck, deck_id)

    S->>Cards: デッキのカード取得
    Cards-->>S: 3枚のカード

    S->>S: カード数チェック: 3 < 5
    S-->>F: 400 INSUFFICIENT_CARDS
    F-->>U: 「5枚以上のカードが必要です」表示
```

---

## エラーハンドリングフロー 🟡

**信頼性**: 🟡 *既存AIエラーハンドリング・EDGE-ASN-001から妥当な推測*

```mermaid
flowchart TD
    A[要約ノート生成リクエスト] --> B{認証チェック}
    B -->|未認証| C[401 Unauthorized]
    B -->|認証OK| D{レート制限チェック}
    D -->|超過| E[429 Rate Limit Exceeded]
    D -->|OK| F{カード数チェック}
    F -->|0-4枚| G[400 INSUFFICIENT_CARDS]
    F -->|5-100枚| H[全カードで生成]
    F -->|101枚以上| I[代表100枚を選択して生成]
    H --> J{AI生成}
    I --> J
    J -->|タイムアウト| K[504 AI_TIMEOUT]
    J -->|プロバイダーエラー| L[503 AI_PROVIDER_ERROR]
    J -->|成功| M[キャッシュ保存 + 200 OK]
    K --> N[リトライボタン表示]
    L --> N
```

## フロントエンド状態管理 🟡

**信頼性**: 🟡 *既存Reactパターンから妥当な推測*

```mermaid
stateDiagram-v2
    [*] --> idle: 画面初期化
    idle --> loading: GET /study-notes
    loading --> cached: キャッシュヒット (is_stale=false)
    loading --> stale: キャッシュあり (is_stale=true)
    loading --> empty: キャッシュなし
    loading --> error: エラー発生

    cached --> [*]: 要約ノート表示

    stale --> generating: 「再生成」タップ
    stale --> [*]: 古い要約を表示

    empty --> generating: 「生成」タップ
    empty --> [*]: 生成ボタン表示

    generating --> cached: 生成成功
    generating --> error: 生成失敗

    error --> generating: リトライ
    error --> [*]: エラー表示
```

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **DBスキーマ**: [database-schema.md](database-schema.md)
- **API仕様**: [api-endpoints.md](api-endpoints.md)
- **型定義（バックエンド）**: [interfaces.py](interfaces.py)
- **型定義（フロントエンド）**: [interfaces.ts](interfaces.ts)

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 5件 | 71% |
| 🟡 黄信号 | 2件 | 29% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（青信号が71%、赤信号なし）

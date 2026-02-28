# review-undo データフロー図

**作成日**: 2026-02-28
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/review-undo/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実なフロー
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測によるフロー
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測によるフロー

---

## 全体フロー概要 🔵

**信頼性**: 🔵 *要件定義・ユーザヒアリングより*

```mermaid
flowchart TD
    A[復習セッション開始] --> B[カード表示・採点]
    B -->|採点完了 or スキップ| C{全カード処理済み?}
    C -->|No| B
    C -->|Yes| D[完了画面: 結果一覧表示]
    D --> E{ユーザーアクション}
    E -->|ホームに戻る| F[ホーム画面]
    E -->|取り消しボタン| G[Undo API呼び出し]
    G -->|成功| H[カード復習UIで再採点]
    G -->|失敗| I[エラー表示 → 完了画面]
    H -->|再採点完了| D
```

## 1. 復習セッション（採点結果保持フロー） 🔵

**信頼性**: 🔵 *既存review-flow dataflow.md・要件定義REQ-013より*

**関連要件**: REQ-013

既存の復習フローに「採点結果の保持」を追加。

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant RP as ReviewPage
    participant API as API Client
    participant BE as Backend API

    Note over RP: 既存フロー: カード表示→フリップ→採点
    U->>RP: グレード選択
    RP->>API: POST /reviews/{cardId}
    API->>BE: submitReview(cardId, grade)
    BE-->>API: ReviewResponse {card_id, grade, previous, updated, reviewed_at}
    API-->>RP: ReviewResponse

    Note over RP: 【新規】結果を保存
    RP->>RP: reviewResults に追加<br/>{cardId, front, grade, nextReviewDate, type: 'graded'}

    RP->>RP: moveToNext()
```

**スキップ時**:

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant RP as ReviewPage

    U->>RP: スキップボタン
    Note over RP: 【新規】スキップを記録
    RP->>RP: reviewResults に追加<br/>{cardId, front, type: 'skipped'}
    RP->>RP: moveToNext()
```

## 2. 完了画面表示フロー 🔵

**信頼性**: 🔵 *要件定義REQ-001〜004・ユーザヒアリングより*

**関連要件**: REQ-001, REQ-002, REQ-003, REQ-004

```mermaid
sequenceDiagram
    participant RP as ReviewPage
    participant RC as ReviewComplete
    participant RRI as ReviewResultItem

    RP->>RC: results={reviewResults}, onUndo, isUndoing

    loop 各結果
        RC->>RRI: result, onUndo, isUndoing
        alt type === 'graded'
            RRI->>RRI: カード表面テキスト表示<br/>グレード表示（色分け）<br/>次回復習日表示<br/>取り消しボタン表示
        else type === 'skipped'
            RRI->>RRI: カード表面テキスト表示<br/>「スキップ」表示<br/>取り消しボタンなし
        else type === 'undone'
            RRI->>RRI: カード表面テキスト表示<br/>「取り消し済み」表示<br/>取り消しボタンなし
        end
    end
```

## 3. 取り消し（Undo）フロー 🔵

**信頼性**: 🔵 *要件定義REQ-005〜008・設計ヒアリングより*

**関連要件**: REQ-005, REQ-006, REQ-007, REQ-008, REQ-101

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant RC as ReviewComplete
    participant RP as ReviewPage
    participant API as API Client
    participant BE as Backend API
    participant DB as DynamoDB Cards

    U->>RC: 取り消しボタン押下
    RC->>RP: onUndo(index)
    RP->>RP: setIsUndoing(true)

    RP->>API: POST /reviews/{cardId}/undo
    API->>BE: undo_review(userId, cardId)

    Note over BE: 1. カード取得・所有権確認
    BE->>DB: GetItem(userId, cardId)
    DB-->>BE: Card (with review_history)

    Note over BE: 2. review_history最新エントリ取得
    BE->>BE: lastEntry = review_history[-1]
    BE->>BE: previous_ef = lastEntry.ease_factor_before
    BE->>BE: previous_interval = lastEntry.interval_before

    Note over BE: 3. SRSパラメータ復元
    BE->>DB: UpdateItem<br/>ease_factor = previous_ef<br/>interval = previous_interval<br/>repetitions = repetitions - 1<br/>next_review_at = recalculate<br/>review_history = history[:-1]
    DB-->>BE: Success

    Note over BE: 4. reviewsテーブルは保持（削除しない）

    BE-->>API: UndoReviewResponse
    API-->>RP: UndoReviewResponse

    RP->>RP: setIsUndoing(false)
    RP->>RP: reviewResults[index].type = 'undone'

    Note over RP: 再採点モードへ切替
    RP->>RP: setRegradeCardIndex(index)
    RP->>RP: setIsComplete(false)
    RP->>RP: setIsFlipped(false)
```

## 4. 再採点フロー 🔵

**信頼性**: 🔵 *要件定義REQ-007, REQ-008, REQ-203・ユーザヒアリングより*

**関連要件**: REQ-007, REQ-008, REQ-103, REQ-203

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant RP as ReviewPage
    participant FC as FlipCard
    participant GB as GradeButtons
    participant API as API Client
    participant BE as Backend API

    Note over RP: 再採点モード (regradeCardIndex !== null)
    Note over RP: 対象カードの情報で表示

    RP->>FC: front, back, isFlipped=false
    U->>FC: タップでフリップ
    FC-->>RP: onFlip()
    RP->>RP: setIsFlipped(true)
    RP->>GB: onGrade, disabled

    U->>GB: グレード選択
    GB-->>RP: onGrade(grade)

    RP->>API: POST /reviews/{cardId}
    API->>BE: submitReview(cardId, grade)
    BE-->>API: ReviewResponse
    API-->>RP: ReviewResponse

    Note over RP: 結果更新
    RP->>RP: reviewResults[index] を更新<br/>{grade, nextReviewDate, type: 'graded'}

    Note over RP: 完了画面に戻る
    RP->>RP: setRegradeCardIndex(null)
    RP->>RP: setIsComplete(true)
```

## 5. エラーハンドリングフロー 🟡

**信頼性**: 🟡 *一般的なエラーハンドリングから妥当な推測*

**関連要件**: REQ-102, EDGE-001, EDGE-002

### Undo APIエラー

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant RP as ReviewPage
    participant API as API Client

    U->>RP: 取り消しボタン押下
    RP->>API: POST /reviews/{cardId}/undo
    API-->>RP: Error (ネットワークエラー等)

    RP->>RP: setIsUndoing(false)
    RP->>RP: エラーメッセージ表示
    Note over RP: 完了画面に留まる<br/>結果一覧は変更なし
```

### 再採点APIエラー

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant RP as ReviewPage
    participant API as API Client

    Note over RP: 再採点モード
    U->>RP: グレード選択
    RP->>API: POST /reviews/{cardId}
    API-->>RP: Error

    RP->>RP: エラーメッセージ表示
    Note over RP: カードは取り消し済み状態のまま<br/>完了画面に戻る
    RP->>RP: setRegradeCardIndex(null)
    RP->>RP: setIsComplete(true)
    Note over RP: 該当カードは 'undone' のまま表示
```

## 6. バックエンドUndo処理詳細 🔵

**信頼性**: 🔵 *既存review_service.py・srs.py実装より*

### SRSパラメータ復元ロジック

```mermaid
flowchart TD
    A[undo_review 開始] --> B[カード取得 + 所有権確認]
    B --> C{review_history あり?}
    C -->|No| D[400 Bad Request: 取り消し対象なし]
    C -->|Yes| E[最新エントリ取得]
    E --> F[previous値を抽出]
    F --> G[SRSパラメータ復元]
    G --> G1["ease_factor = entry.ease_factor_before"]
    G --> G2["interval = entry.interval_before"]
    G --> G3["repetitions = max(0, repetitions - 1)"]
    G --> G4["next_review_at = 再計算"]
    G1 --> H[review_history から最新エントリ削除]
    G2 --> H
    G3 --> H
    G4 --> H
    H --> I[DynamoDB UpdateItem]
    I --> J[UndoReviewResponse 返却]
```

### repetitions の復元 🟡

**信頼性**: 🟡 *SM-2アルゴリズムの動作から妥当な推測*

review_historyにはrepetitions_beforeが保存されていないため、以下のロジックで復元する:
- グレード0-2の場合（repetitions=0にリセット）: 元のrepetitionsを正確に復元できない
- グレード3-5の場合（repetitions+1）: `repetitions - 1` で復元

**対策**: review_historyエントリに `repetitions_before` と `repetitions_after` を追加保存する。

### next_review_at の復元 🟡

**信頼性**: 🟡 *SM-2アルゴリズムの動作から妥当な推測*

review_historyにはnext_review_at_beforeが保存されていないため:
- 復元したintervalから `now + timedelta(days=interval)` で再計算する
- 完全な復元ではないが、実用上問題ない（undoの直後に再採点するため）

**対策**: review_historyエントリに `next_review_at_before` を追加保存する。

## 7. 状態遷移図 🔵

**信頼性**: 🔵 *要件定義・ユーザヒアリングより*

```mermaid
stateDiagram-v2
    [*] --> Loading: ページ表示
    Loading --> Empty: カード0枚
    Loading --> Reviewing: カードあり
    Loading --> Error: 取得失敗

    Reviewing --> Reviewing: 採点/スキップ → 次カード
    Reviewing --> Complete: 全カード処理済み

    Complete --> Undoing: 取り消しボタン
    Undoing --> Regrading: Undo API成功
    Undoing --> Complete: Undo API失敗

    Regrading --> Complete: 再採点完了
    Regrading --> Complete: 再採点エラー（undoneのまま戻る）

    Complete --> [*]: ホームに戻る
    Empty --> [*]: 戻る
    Error --> Loading: リトライ
```

## 8. データテーブル 🔵

**信頼性**: 🔵 *既存実装・要件定義より*

### フロントエンド状態

| 状態 | 型 | 初期値 | 説明 |
|------|-----|--------|------|
| reviewResults | SessionCardResult[] | [] | セッション中の全結果 |
| regradeCardIndex | number \| null | null | 再採点中のカードindex |
| isUndoing | boolean | false | undo API呼び出し中 |
| undoingIndex | number \| null | null | undo中のカードindex |

### SessionCardResult

| フィールド | 型 | 説明 |
|-----------|-----|------|
| cardId | string | カードID |
| front | string | カード表面テキスト |
| grade | number \| null | 採点グレード（スキップ時はnull） |
| nextReviewDate | string \| null | 次回復習日（ISO日付） |
| type | 'graded' \| 'skipped' \| 'undone' | 結果タイプ |

### API入出力

| エンドポイント | メソッド | 入力 | 出力 | 説明 |
|---------------|---------|------|------|------|
| /reviews/{cardId}/undo | POST | なし | UndoReviewResponse | SRSパラメータ復元 |
| /reviews/{cardId} | POST | {grade} | ReviewResponse | 採点（既存） |

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **型定義**: [interfaces.ts](interfaces.ts)
- **API仕様**: [api-endpoints.md](api-endpoints.md)
- **要件定義**: [requirements.md](../../spec/review-undo/requirements.md)

## 信頼性レベルサマリー

- 🔵 青信号: 9件 (75%)
- 🟡 黄信号: 3件 (25%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質

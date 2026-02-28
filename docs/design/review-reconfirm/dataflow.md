# review-reconfirm データフロー図

**作成日**: 2026-02-28
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/review-reconfirm/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実なフロー
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測によるフロー
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測によるフロー

---

## 全体フロー概要 🔵

**信頼性**: 🔵 *要件定義書 REQ-001~005, REQ-502より*

```mermaid
flowchart TD
    Start[セッション開始] --> Fetch[カード取得 API]
    Fetch --> HasCards{カードあり?}
    HasCards -->|No| Empty[カードなし画面]
    HasCards -->|Yes| ShowCard[カード表示]

    ShowCard --> IsReconfirm{再確認カード?}
    IsReconfirm -->|No| ShowGrade[6段階評価 + スキップ表示]
    IsReconfirm -->|Yes| ShowBadge[「再確認」バッジ表示]
    ShowBadge --> ShowReconfirm[「覚えた」「覚えていない」表示]

    ShowGrade --> UserGrade[ユーザーが評価]
    UserGrade --> CheckGrade{grade 0-2?}

    CheckGrade -->|Yes| SubmitSM2[SM-2 API呼び出し]
    SubmitSM2 --> AddResult[結果をreviewResultsに追加]
    AddResult --> AddQueue[reconfirmQueue末尾に追加]
    AddQueue --> NextCard

    CheckGrade -->|No| SubmitSM2_Normal[SM-2 API呼び出し]
    SubmitSM2_Normal --> AddResult_Normal[結果をreviewResultsに追加]
    AddResult_Normal --> NextCard

    ShowGrade --> UserSkip[ユーザーがスキップ]
    UserSkip --> AddSkip[スキップ結果を追加]
    AddSkip --> NextCard

    ShowReconfirm --> Remembered[「覚えた」選択]
    Remembered --> RemoveQueue[reconfirmQueueから除外]
    RemoveQueue --> UpdateResult[結果をreconfirmedに更新]
    UpdateResult --> NextCard

    ShowReconfirm --> Forgotten[「覚えていない」選択]
    Forgotten --> ReAddQueue[reconfirmQueue末尾に再追加]
    ReAddQueue --> NextCard

    NextCard[次のカード判定] --> HasNormal{通常カードあり?}
    HasNormal -->|Yes| ShowCard
    HasNormal -->|No| HasReconfirm{reconfirmQueue非空?}
    HasReconfirm -->|Yes| DequeueReconfirm[reconfirmQueueから先頭取出し]
    DequeueReconfirm --> ShowCard
    HasReconfirm -->|No| Complete[セッション完了]

    Complete --> ShowComplete[ReviewComplete表示]
```

## 通常評価フロー（grade 0-2） 🔵

**信頼性**: 🔵 *要件定義書 REQ-001, ユーザーストーリー1.1より*

**関連要件**: REQ-001, REQ-005

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant RP as ReviewPage
    participant GB as GradeButtons
    participant API as reviewsApi
    participant BE as バックエンド

    U->>RP: カード表面を見る
    U->>RP: タップで裏面表示
    RP->>GB: 通常モード表示（6段階 + スキップ）
    U->>GB: grade 0-2を選択
    GB->>RP: onGrade(grade)

    RP->>API: submitReview(cardId, grade)
    API->>BE: POST /reviews/{cardId}
    BE-->>API: ReviewResponse (interval=1, next_review_at=翌日)
    API-->>RP: ReviewResponse

    RP->>RP: reviewResults.push({type: 'graded', grade, ...})
    RP->>RP: reconfirmQueue.push({cardId, front, back, originalGrade: grade})
    RP->>RP: moveToNext()
```

**詳細ステップ**:
1. ユーザーがカードの表面を見る
2. タップで裏面を確認する
3. 6段階評価（0-5）とスキップボタンが表示される
4. quality 0, 1, または 2 を選択する
5. SM-2 API が呼び出される（interval=1, next_review_at=翌日 に設定）
6. 結果が `reviewResults` に追加される
7. カードが `reconfirmQueue` の末尾に追加される
8. 次のカードに進む

## 通常評価フロー（grade 3-5） 🔵

**信頼性**: 🔵 *要件定義書 REQ-103より*

**関連要件**: REQ-103

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant RP as ReviewPage
    participant GB as GradeButtons
    participant API as reviewsApi
    participant BE as バックエンド

    U->>GB: grade 3-5を選択
    GB->>RP: onGrade(grade)

    RP->>API: submitReview(cardId, grade)
    API->>BE: POST /reviews/{cardId}
    BE-->>API: ReviewResponse (通常のSM-2計算)
    API-->>RP: ReviewResponse

    RP->>RP: reviewResults.push({type: 'graded', grade, ...})
    Note over RP: reconfirmQueueには追加しない
    RP->>RP: moveToNext()
```

## 再確認フロー（「覚えた」） 🔵

**信頼性**: 🔵 *要件定義書 REQ-003, REQ-005, REQ-101, REQ-102より*

**関連要件**: REQ-003, REQ-005, REQ-101, REQ-102

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant RP as ReviewPage
    participant Badge as ReconfirmBadge
    participant GB as GradeButtons

    RP->>Badge: 「再確認」バッジ表示
    RP->>RP: isReconfirmMode = true
    U->>RP: カード表面を見る
    U->>RP: タップで裏面表示
    RP->>GB: 再確認モード表示（「覚えた」「覚えていない」のみ）
    Note over GB: スキップボタン非表示

    U->>GB: 「覚えた」を選択
    GB->>RP: onReconfirmRemembered()

    Note over RP: API呼び出しなし
    Note over RP: SM-2再計算なし
    RP->>RP: reconfirmQueueから現在のカードを除外
    RP->>RP: reviewResultsの該当カードを更新
    Note over RP: type: 'reconfirmed', reconfirmResult: 'remembered'
    RP->>RP: moveToNext()
```

**詳細ステップ**:
1. 再確認キューからカードが取り出される
2. 「再確認」バッジが表示される
3. カード表面 → 裏面確認 の通常フロー
4. 「覚えた」「覚えていない」の2択が表示される（スキップなし）
5. 「覚えた」を選択
6. API呼び出しなし、SM-2再計算なし
7. 再確認キューからカードを除外
8. `reviewResults`の該当カードを `type: 'reconfirmed'` に更新
9. 次のカードに進む

## 再確認フロー（「覚えていない」） 🔵

**信頼性**: 🔵 *要件定義書 REQ-004より*

**関連要件**: REQ-004

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant RP as ReviewPage
    participant GB as GradeButtons

    U->>GB: 「覚えていない」を選択
    GB->>RP: onReconfirmForgotten()

    Note over RP: API呼び出しなし
    Note over RP: next_review_at更新なし
    RP->>RP: 現在のカードをreconfirmQueue末尾に再追加
    RP->>RP: moveToNext()
```

**詳細ステップ**:
1. 「覚えていない」を選択
2. API呼び出しなし、復習日更新なし
3. 現在のカードが再確認キューの末尾に再追加される
4. 次のカードに進む（別のカードがあれば先にそちらを表示）

## カード進行判定フロー（moveToNext拡張） 🔵

**信頼性**: 🔵 *要件定義書 REQ-502・ヒアリングQ5回答より*

**関連要件**: REQ-502

```mermaid
flowchart TD
    MoveToNext[moveToNext 呼び出し] --> CheckRegrade{regradeモード?}
    CheckRegrade -->|Yes| SetComplete[isComplete = true]

    CheckRegrade -->|No| CheckNormal{currentIndex + 1 < cards.length?}
    CheckNormal -->|Yes| NextNormal[currentIndex++]
    NextNormal --> SetNormalMode[isReconfirmMode = false]
    SetNormalMode --> ResetFlip[isFlipped = false]

    CheckNormal -->|No| CheckQueue{reconfirmQueue.length > 0?}
    CheckQueue -->|Yes| Dequeue[reconfirmQueueから先頭を取出し]
    Dequeue --> SetReconfirm[isReconfirmMode = true]
    SetReconfirm --> ShowReconfirmCard[再確認カードを表示]
    ShowReconfirmCard --> ResetFlip

    CheckQueue -->|No| SetComplete
```

## Undo連携フロー 🔵

**信頼性**: 🔵 *要件定義書 REQ-404・ヒアリングQ4回答より*

**関連要件**: REQ-404

```mermaid
sequenceDiagram
    participant U as ユーザー
    participant RC as ReviewComplete
    participant RP as ReviewPage
    participant API as reviewsApi
    participant BE as バックエンド

    Note over RC: 完了画面表示中
    U->>RC: quality 0-2カードの「取り消し」を押す
    RC->>RP: onUndo(index)

    RP->>API: undoReview(cardId)
    API->>BE: POST /reviews/{cardId}/undo
    BE-->>API: UndoReviewResponse (SM-2復元)
    API-->>RP: UndoReviewResponse

    RP->>RP: reviewResults[index].type = 'undone'
    RP->>RP: reconfirmQueueから該当カードを除去
    RP->>RP: regradeCardIndex = index (再評価モード)

    Note over RP: 再評価画面表示
    U->>RP: 新しいgradeを選択

    alt grade 0-2
        RP->>API: submitReview(cardId, grade)
        RP->>RP: 再びreconfirmQueueに追加
    else grade 3-5
        RP->>API: submitReview(cardId, grade)
        Note over RP: reconfirmQueueには追加しない
    end

    RP->>RP: isComplete = true (完了画面に戻る)
```

## 完了画面表示フロー 🔵

**信頼性**: 🔵 *要件定義書 REQ-501・ヒアリングQ3回答より*

**関連要件**: REQ-501

```mermaid
flowchart TD
    Complete[セッション完了] --> ShowResults[ReviewComplete表示]
    ShowResults --> ForEach[各reviewResultをループ]

    ForEach --> CheckType{result.type?}

    CheckType -->|graded, grade 3-5| ShowNormal[通常表示: grade色バッジ + 次回復習日]
    CheckType -->|skipped| ShowSkip[スキップ表示: グレーバッジ]
    CheckType -->|reconfirmed| ShowReconfirm[再確認表示: grade色バッジ + 覚えた✔]
    CheckType -->|undone| ShowUndone[取消表示: 青矢印バッジ]

    ShowNormal --> ShowUndo[Undoボタン表示]
    ShowReconfirm --> ShowUndo
```

**再確認カードの完了画面表示**:
- 元の評価（例: quality 2）のバッジを色付きで表示
- 「覚えた✔」のサブラベルを追加表示
- Undoボタンを表示（取り消し可能）

## 状態遷移図 🔵

**信頼性**: 🔵 *要件定義書 REQ-001~004より*

```mermaid
stateDiagram-v2
    [*] --> 通常復習中: カード取得完了

    通常復習中 --> 通常復習中: grade 3-5 (SM-2 API + 次のカード)
    通常復習中 --> 通常復習中: grade 0-2 (SM-2 API + reconfirmQueue追加 + 次のカード)
    通常復習中 --> 通常復習中: スキップ (次のカード)

    通常復習中 --> 再確認中: 通常カード消化完了 & reconfirmQueue非空

    再確認中 --> 再確認中: 「覚えていない」(キュー末尾に再追加 + 次のカード)
    再確認中 --> 再確認中: 「覚えた」(キューから除外 + 次のカード) ※キューに他のカードあり

    再確認中 --> セッション完了: 「覚えた」(最後の再確認カード)
    通常復習中 --> セッション完了: 最後のカード & reconfirmQueue空

    セッション完了 --> 再評価中: Undo操作
    再評価中 --> セッション完了: 再評価完了
```

## セッション中断時の動作 🔵

**信頼性**: 🔵 *要件定義書 REQ-201, EDGE-001より*

```mermaid
flowchart TD
    Session[セッション中] --> Close[アプリを閉じる]
    Close --> LostState[再確認キュー状態が失われる]
    LostState --> NextDay[翌日]
    NextDay --> DueCards[カードが復習対象として再登場]
    DueCards --> Note[SM-2がquality 0-2でinterval=1を設定済みのため]
```

再確認ループの状態はセッション内のフロントエンド状態のみで管理し、セッション終了時にリセットされる。SM-2が最初のquality 0-2評価時にinterval=1（翌日）を設定済みのため、翌日に通常の復習対象として再登場する。

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **要件定義**: [requirements.md](../../spec/review-reconfirm/requirements.md)
- **ユーザストーリー**: [user-stories.md](../../spec/review-reconfirm/user-stories.md)
- **受け入れ基準**: [acceptance-criteria.md](../../spec/review-reconfirm/acceptance-criteria.md)

## 信頼性レベルサマリー

- 🔵 青信号: 10件 (100%)
- 🟡 黄信号: 0件 (0%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質

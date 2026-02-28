# TASK-0081 TDD Requirements: 型定義拡張 + ReviewPageコアロジック実装

**作成日**: 2026-02-28
**タスク**: TASK-0081
**タスクタイプ**: TDD
**対象ファイル**:
- `frontend/src/types/card.ts` (型定義拡張)
- `frontend/src/pages/ReviewPage.tsx` (状態管理 + ハンドラ + ロジック拡張)
**テストファイル**: `frontend/src/pages/__tests__/ReviewPage.test.tsx`

---

## 1. 実装スコープ

このタスクは再確認ループ機能の **ロジック基盤** を構築する。UIコンポーネントの変更(GradeButtons, ReconfirmBadge等)は TASK-0082 で対応するため、本タスクではロジックとハンドラの実装・テストに集中する。

### 変更しないもの
- バックエンドAPI (REQ-403)
- SM-2アルゴリズム (REQ-401)
- GradeButtons コンポーネント (TASK-0082)
- ReconfirmBadge コンポーネント (TASK-0082)
- ReviewComplete / ReviewResultItem (TASK-0082 以降)

---

## 2. 型定義拡張 (frontend/src/types/card.ts)

### REQ-TDD-001: SessionCardResultType に 'reconfirmed' を追加

**要件参照**: REQ-001, REQ-501, architecture.md

**現状**:
```typescript
export type SessionCardResultType = 'graded' | 'skipped' | 'undone';
```

**変更後**:
```typescript
export type SessionCardResultType = 'graded' | 'skipped' | 'undone' | 'reconfirmed';
```

**テスト方針**: TypeScript 型レベルの検証。`'reconfirmed'` を代入して型エラーが出ないことを確認する。

---

### REQ-TDD-002: SessionCardResult に reconfirmResult フィールドを追加

**要件参照**: REQ-003, REQ-501, architecture.md

**現状**:
```typescript
export interface SessionCardResult {
  cardId: string;
  front: string;
  grade?: number;
  nextReviewDate?: string;
  type: SessionCardResultType;
}
```

**変更後**:
```typescript
export interface SessionCardResult {
  cardId: string;
  front: string;
  grade?: number;
  nextReviewDate?: string;
  type: SessionCardResultType;
  reconfirmResult?: 'remembered';
}
```

**テスト方針**: `reconfirmResult: 'remembered'` を含むオブジェクトが SessionCardResult として有効なことを確認する。既存コードで `reconfirmResult` を指定していない箇所が壊れないことも確認する。

---

### REQ-TDD-003: ReconfirmCard インターフェースの新規追加

**要件参照**: REQ-001, architecture.md

**新規追加**:
```typescript
export interface ReconfirmCard {
  cardId: string;
  front: string;
  back: string;
  originalGrade: number;  // 0, 1, or 2
}
```

**テスト方針**: `ReconfirmCard` 型のオブジェクトを作成し、4つの必須フィールド(cardId, front, back, originalGrade)が全て必要であることを型レベルで確認する。

---

## 3. ReviewPage 状態管理拡張 (frontend/src/pages/ReviewPage.tsx)

### REQ-TDD-010: reconfirmQueue state の追加

**要件参照**: REQ-001, REQ-201, architecture.md

**追加内容**:
```typescript
const [reconfirmQueue, setReconfirmQueue] = useState<ReconfirmCard[]>([]);
```

**テスト方針**: 初期状態で reconfirmQueue が空配列であること(カード評価前に再確認キューが空であること)を、既存テストの動作が変わらないことで間接的に検証する。

---

### REQ-TDD-011: isReconfirmMode state の追加

**要件参照**: REQ-002, architecture.md

**追加内容**:
```typescript
const [isReconfirmMode, setIsReconfirmMode] = useState<boolean>(false);
```

**テスト方針**: 初期状態で isReconfirmMode が false であること。通常カード消化後に再確認キューがある場合に true に切り替わること。

---

### REQ-TDD-012: currentReconfirmCard 導出値

**要件参照**: architecture.md

**追加内容**:
```typescript
const currentReconfirmCard = reconfirmQueue.length > 0 ? reconfirmQueue[0] : null;
```

**テスト方針**: reconfirmQueue の先頭要素が現在の再確認カードとして使用されること。ハンドラテストで間接的に検証する。

---

## 4. handleGrade 拡張: quality 0-2 でキュー追加

### REQ-TDD-020: Normal mode - quality 0-2 で reconfirmQueue に追加

**要件参照**: REQ-001, REQ-103, TC-001-01, TC-001-02, TC-001-03, dataflow.md

**変更箇所**: handleGrade 内の Normal mode ブロック、API 成功後

**ロジック**:
```
API 成功後:
  既存: reviewResults に結果追加、reviewedCount++、moveToNext()
  追加: grade < 3 の場合、reconfirmQueue 末尾に {cardId, front, back, originalGrade: grade} を追加
```

**テストケース**:

#### TC-TDD-020-01: quality 0 選択時に reconfirmQueue に追加される
- **前提**: カードが表示されている
- **操作**: quality 0 を選択
- **検証**: SM-2 API が呼ばれる AND reconfirmQueue に該当カードが追加される
- **検証方法**: 全通常カードを消化後に再確認モードに入ることで間接検証。具体的には、1枚のカードを quality 0 で評価すると、完了画面に遷移せず再確認カードが表示される状態になる(ただし UI は TASK-0082 で実装するため、本タスクでは moveToNext で isReconfirmMode = true になることをテスト)

#### TC-TDD-020-02: quality 1 選択時に reconfirmQueue に追加される
- **前提**: カードが表示されている
- **操作**: quality 1 を選択
- **検証**: reconfirmQueue に該当カードが追加される(TC-TDD-020-01 と同様の検証方法)

#### TC-TDD-020-03: quality 2 選択時に reconfirmQueue に追加される
- **前提**: カードが表示されている
- **操作**: quality 2 を選択
- **検証**: reconfirmQueue に該当カードが追加される

#### TC-TDD-020-04: quality 3 選択時に reconfirmQueue に追加されない
- **前提**: カードが表示されている(1枚のみ)
- **操作**: quality 3 を選択
- **検証**: reconfirmQueue に追加されない。セッションが直接完了する(isComplete = true)
- **要件参照**: TC-001-B01, REQ-103

#### TC-TDD-020-05: quality 4 選択時に reconfirmQueue に追加されない
- **前提**: カードが表示されている(1枚のみ)
- **操作**: quality 4 を選択
- **検証**: セッションが直接完了する(既存テストで既に検証済み。既存テストが引き続きパスすることが検証)

#### TC-TDD-020-06: quality 5 選択時に reconfirmQueue に追加されない
- **前提**: カードが表示されている(1枚のみ)
- **操作**: quality 5 を選択
- **検証**: セッションが直接完了する(既存テストで既に検証済み)

---

### REQ-TDD-021: Regrade mode - quality 0-2 で reconfirmQueue に追加

**要件参照**: REQ-001, REQ-404, TC-404-02, dataflow.md

**変更箇所**: handleGrade 内の Regrade mode ブロック、API 成功後

**ロジック**:
```
Regrade mode の API 成功後:
  既存: reviewResults 更新、reviewedCount++
  追加: grade < 3 の場合、reconfirmQueue 末尾に {cardId, front, back, originalGrade: grade} を追加
         (cards 配列から該当カードの front/back を取得)
```

**テストケース**:

#### TC-TDD-021-01: Undo 後の regrade quality 0-2 で reconfirmQueue に追加
- **前提**: カードを quality 4 で評価 -> 完了画面 -> Undo -> 再採点モード
- **操作**: quality 2 で再評価
- **検証**: reconfirmQueue にカードが追加される(完了画面に戻った後の状態で検証)
- **要件参照**: TC-404-02, EDGE-202

#### TC-TDD-021-02: Undo 後の regrade quality 3+ で reconfirmQueue に追加されない
- **前提**: カードを quality 4 で評価 -> 完了画面 -> Undo -> 再採点モード
- **操作**: quality 4 で再評価
- **検証**: reconfirmQueue にカードが追加されない(完了画面に戻り、通常の完了状態)
- **要件参照**: TC-404-03, EDGE-203

---

## 5. handleReconfirmRemembered: 「覚えた」ハンドラ

### REQ-TDD-030: handleReconfirmRemembered の実装

**要件参照**: REQ-003, TC-003-01, TC-003-02, dataflow.md

**新規ハンドラ**:
```typescript
const handleReconfirmRemembered = useCallback(() => {
  if (currentReconfirmCard === null) return;

  // 1. reconfirmQueue から先頭を除外
  setReconfirmQueue((prev) => prev.slice(1));

  // 2. reviewResults の該当カードを更新
  setReviewResults((prev) =>
    prev.map((r) =>
      r.cardId === currentReconfirmCard.cardId
        ? { ...r, type: 'reconfirmed' as const, reconfirmResult: 'remembered' as const }
        : r
    )
  );

  // 3. 次のカードへ（API呼び出しなし）
  moveToNext();
}, [currentReconfirmCard, moveToNext]);
```

**テストケース**:

#### TC-TDD-030-01: 「覚えた」選択でカードがキューから除外される
- **前提**: quality 0-2 で評価済みのカードが再確認キューにある。通常カードが全て消化済みで再確認モードに入っている
- **操作**: handleReconfirmRemembered を呼び出す
- **検証**: reconfirmQueue から該当カードが除外され、キューが空ならセッション完了に遷移する
- **実装テスト方法**: 1枚のカードを quality 0 で評価 -> 全通常カード消化 -> 再確認モード -> handleReconfirmRemembered 呼び出し -> isComplete = true

#### TC-TDD-030-02: 「覚えた」選択で API が呼ばれない
- **前提**: 再確認モードでカードが表示中
- **操作**: handleReconfirmRemembered を呼び出す
- **検証**: mockSubmitReview が追加呼び出しされない(呼び出し回数が変わらない)
- **要件参照**: REQ-003(SM-2再計算・API呼び出しなし)

#### TC-TDD-030-03: reviewResults が 'reconfirmed' に更新される
- **前提**: quality 2 で評価されたカード -> 再確認モード
- **操作**: handleReconfirmRemembered を呼び出す
- **検証**: reviewResults 内の該当カードの type が 'reconfirmed' に更新される
- **検証方法**: 完了画面で結果を確認(ReviewComplete に渡される results を検証)

#### TC-TDD-030-04: reviewResults に reconfirmResult: 'remembered' が設定される
- **前提**: quality 1 で評価されたカード -> 再確認モード
- **操作**: handleReconfirmRemembered を呼び出す
- **検証**: reviewResults 内の該当カードに reconfirmResult: 'remembered' が含まれる
- **検証方法**: TC-TDD-030-03 と同時に検証可能

---

## 6. handleReconfirmForgotten: 「覚えていない」ハンドラ

### REQ-TDD-040: handleReconfirmForgotten の実装

**要件参照**: REQ-004, TC-004-01, TC-004-02, TC-004-03, dataflow.md

**新規ハンドラ**:
```typescript
const handleReconfirmForgotten = useCallback(() => {
  if (currentReconfirmCard === null) return;

  // 1. 現在のカードを reconfirmQueue の末尾に再追加
  setReconfirmQueue((prev) => [...prev.slice(1), currentReconfirmCard]);

  // 2. 次のカードへ（API呼び出しなし）
  moveToNext();
}, [currentReconfirmCard, moveToNext]);
```

**テストケース**:

#### TC-TDD-040-01: 「覚えていない」選択でカードがキュー末尾に追加される
- **前提**: 再確認キューにカードが1枚ある状態で再確認モード
- **操作**: handleReconfirmForgotten を呼び出す
- **検証**: カードがキュー末尾に再追加され、セッションは完了しない(キューが空にならない)
- **要件参照**: REQ-004, REQ-402(ループ回数上限なし)

#### TC-TDD-040-02: 「覚えていない」選択で API が呼ばれない
- **前提**: 再確認モードでカードが表示中
- **操作**: handleReconfirmForgotten を呼び出す
- **検証**: mockSubmitReview が追加呼び出しされない
- **要件参照**: REQ-004, REQ-202(復習日更新なし)

#### TC-TDD-040-03: 複数回「覚えていない」-> 「覚えた」のフロー
- **前提**: 1枚のカードが再確認キューにある
- **操作**: 「覚えていない」を2回選択 -> 「覚えた」を1回選択
- **検証**: 3回目の操作後にキューが空になりセッション完了。API は quality 0-2 の初回評価時の1回のみ呼ばれる
- **要件参照**: TC-004-03, EDGE-102

---

## 7. moveToNext 拡張: カード進行ロジック

### REQ-TDD-050: moveToNext の拡張

**要件参照**: REQ-502, dataflow.md

**変更後のロジック**:
```
moveToNext() 呼び出し:
  1. isFlipped = false (既存)
  2. regradeCardIndex !== null の場合:
     -> isComplete = true (再採点後は必ず完了へ)
  3. currentIndex < cards.length - 1 の場合:
     -> currentIndex++, isReconfirmMode = false (次の通常カード)
  4. reconfirmQueue.length > 0 の場合:
     -> isReconfirmMode = true (再確認キューへ)
  5. else:
     -> isComplete = true (完了)
```

**テストケース**:

#### TC-TDD-050-01: 通常カード残り有り -> 次の通常カードへ
- **前提**: 3枚のカードのうち1枚目を評価済み
- **操作**: moveToNext (handleGrade 内で自動呼出し)
- **検証**: 2枚目のカードが表示される。isReconfirmMode = false
- **検証方法**: 既存テストで検証済み(テストケース5/10)。既存テストがパスすることが検証

#### TC-TDD-050-02: 通常カード全消化 + reconfirmQueue 非空 -> 再確認モード遷移
- **前提**: 1枚のカードを quality 0 で評価(reconfirmQueue に1件追加される)
- **操作**: moveToNext (handleGrade 内で自動呼出し。最後の通常カード)
- **検証**: isReconfirmMode = true。isComplete = false(完了しない)
- **検証方法**: セッションが完了画面に遷移しないことを確認

#### TC-TDD-050-03: 通常カード全消化 + reconfirmQueue 空 -> セッション完了
- **前提**: 1枚のカードを quality 5 で評価(reconfirmQueue は空)
- **操作**: moveToNext
- **検証**: isComplete = true
- **検証方法**: 既存テスト(テストケース7)で検証済み。既存テストがパスすることが検証

#### TC-TDD-050-04: 再確認キュー消化後 -> セッション完了
- **前提**: 再確認キューに1枚、handleReconfirmRemembered で除外
- **操作**: moveToNext (handleReconfirmRemembered 内で自動呼出し)
- **検証**: reconfirmQueue が空になり isComplete = true
- **検証方法**: セッション完了画面が表示される

---

## 8. handleUndo 拡張: 再確認キューとの連携

### REQ-TDD-060: handleUndo の拡張

**要件参照**: REQ-404, TC-404-01, TC-404-02, TC-404-03, dataflow.md

**変更箇所**: handleUndo 内、API 成功後のブロック

**追加ロジック**:
```typescript
// 既存のロジックに追加:
setReconfirmQueue((prev) =>
  prev.filter((rc) => rc.cardId !== result.cardId)
);

// isReconfirmMode リセット:
setIsReconfirmMode(false);
```

**テストケース**:

#### TC-TDD-060-01: Undo 時に reconfirmQueue から該当カードが除去される
- **前提**: 1枚のカードを quality 1 で評価(reconfirmQueue に追加済み) -> 他のカードも全て評価して完了
- **操作**: 完了画面で quality 1 のカードを Undo
- **検証**: reconfirmQueue から該当カードが除去される。regradeMode に入る
- **検証方法**: Undo 後に regrade で quality 4 を選択 -> 完了画面に戻る -> 再確認カードとして表示されない(セッション完了のまま)

#### TC-TDD-060-02: Undo 後の regrade quality 0-2 で再び reconfirmQueue に追加
- **前提**: TC-TDD-060-01 の続き。regrade モード
- **操作**: quality 2 で再評価
- **検証**: reconfirmQueue に再び追加される
- **検証方法**: REQ-TDD-021 の TC-TDD-021-01 と同一。完了画面に戻る際に reconfirmQueue の状態を間接検証

#### TC-TDD-060-03: Undo 後の regrade quality 3+ で reconfirmQueue に追加されない
- **前提**: TC-TDD-060-01 の続き。regrade モード
- **操作**: quality 4 で再評価
- **検証**: reconfirmQueue に追加されない。通常の完了画面に戻る
- **検証方法**: REQ-TDD-021 の TC-TDD-021-02 と同一

---

## 9. 統合テストシナリオ

### TC-TDD-INT-01: 通常カード3枚 + quality 0-2 が1枚 -> 再確認ループ -> 完了

**フロー**:
1. カード1を quality 0 で評価 -> reconfirmQueue: [card-1]
2. カード2を quality 4 で評価 -> reconfirmQueue: [card-1] (変化なし)
3. カード3を quality 5 で評価 -> 通常カード全消化、reconfirmQueue 非空 -> isReconfirmMode = true
4. 再確認: card-1 で handleReconfirmRemembered -> reconfirmQueue: [] -> isComplete = true
5. 完了画面表示

**検証**:
- submitReview が3回呼ばれる(card-1, card-2, card-3)
- 完了画面に「3枚のカードを復習しました」と表示
- card-1 の reviewResult.type が 'reconfirmed'
- card-1 の reviewResult.reconfirmResult が 'remembered'

---

### TC-TDD-INT-02: 全カード quality 0-2 -> 再確認ループで全て「覚えた」-> 完了

**フロー**:
1. カード1を quality 0 で評価
2. カード2を quality 1 で評価
3. カード3を quality 2 で評価 -> 通常カード全消化、reconfirmQueue: [card-1, card-2, card-3]
4. 再確認: card-1 「覚えた」-> reconfirmQueue: [card-2, card-3]
5. 再確認: card-2 「覚えた」-> reconfirmQueue: [card-3]
6. 再確認: card-3 「覚えた」-> reconfirmQueue: [] -> isComplete = true

**検証**:
- submitReview が3回呼ばれる
- 完了画面に「3枚のカードを復習しました」と表示
- 全カードの reviewResult.type が 'reconfirmed'
- **要件参照**: EDGE-101

---

### TC-TDD-INT-03: 「覚えていない」-> キュー末尾再追加 -> 「覚えた」-> 完了

**フロー**:
1. カード1(1枚のみ)を quality 0 で評価 -> reconfirmQueue: [card-1]
2. 再確認: card-1 「覚えていない」-> reconfirmQueue: [card-1] (末尾に再追加)
3. 再確認: card-1 「覚えていない」-> reconfirmQueue: [card-1]
4. 再確認: card-1 「覚えた」-> reconfirmQueue: [] -> isComplete = true

**検証**:
- submitReview が1回のみ呼ばれる(最初の quality 0 評価時)
- 再確認中は API 呼び出しなし
- **要件参照**: EDGE-102, REQ-402

---

### TC-TDD-INT-04: Undo -> regrade quality 0-2 -> 再確認ループ -> 完了

**フロー**:
1. カード1(1枚のみ)を quality 4 で評価 -> isComplete = true, reconfirmQueue: []
2. 完了画面で Undo -> regradeMode, reconfirmQueue: []
3. regrade: quality 1 -> reconfirmQueue: [card-1], isComplete = true
4. (次のタスク以降で) 再確認ループが発生する想定

**検証**:
- undoReview API が1回呼ばれる
- submitReview が2回呼ばれる(初回 quality 4 + regrade quality 1)

---

## 10. エッジケーステスト

### TC-TDD-EDGE-01: reconfirmQueue が空の時に handleReconfirmRemembered を呼んでも何も起きない

**前提**: reconfirmQueue が空(currentReconfirmCard === null)
**操作**: handleReconfirmRemembered を呼び出す
**検証**: 状態が変化しない。エラーが発生しない

---

### TC-TDD-EDGE-02: reconfirmQueue が空の時に handleReconfirmForgotten を呼んでも何も起きない

**前提**: reconfirmQueue が空
**操作**: handleReconfirmForgotten を呼び出す
**検証**: 状態が変化しない。エラーが発生しない

---

### TC-TDD-EDGE-03: 複数カードが reconfirmQueue にある時の「覚えた」で先頭のみ除外

**前提**: reconfirmQueue: [card-1, card-2, card-3]
**操作**: handleReconfirmRemembered
**検証**: reconfirmQueue: [card-2, card-3]。card-1 のみ除外される

---

### TC-TDD-EDGE-04: Undo 対象カードが reconfirmQueue に存在しない場合(quality 3-5 の Undo)

**前提**: quality 4 で評価したカードを Undo(reconfirmQueue に該当カードは元々ない)
**操作**: handleUndo
**検証**: reconfirmQueue.filter は空振りするが、エラーは発生しない。既存 Undo フローが正常動作する

---

## 11. 既存テストの互換性要件

以下の既存テストが引き続き全てパスしなければならない:

| テストケース | 概要 | 影響分析 |
|---|---|---|
| テストケース1 | ローディング表示 | 影響なし |
| テストケース2 | カード表示 | 影響なし |
| テストケース3 | 空状態表示 | 影響なし |
| テストケース4 | フリップ操作 | 影響なし |
| テストケース5 | 採点送信(quality 4) | **要注意**: quality 4 は reconfirmQueue に追加しない。既存動作を維持 |
| テストケース6 | スキップ | 影響なし。スキップ時は reconfirmQueue に追加しない |
| テストケース7 | 復習完了(quality 5, 1枚) | **要注意**: quality 5 は reconfirmQueue に追加しない。1枚の場合 moveToNext で isComplete = true になる既存動作を維持 |
| テストケース8 | APIエラー(初期読み込み) | 影響なし |
| テストケース9 | APIエラー(採点送信) | 影響なし |
| テストケース10 | 進捗バー更新 | **要注意**: quality 4 での進捗更新。影響なし |
| 統合テスト | 3枚全評価 | **要注意**: quality 4,5 のみで評価。reconfirmQueue は空のまま。既存動作を維持 |
| エッジケース: 1枚 | quality 3 で即完了 | **要注意**: quality 3 は reconfirmQueue に追加しない。既存動作を維持 |
| エッジケース: 全スキップ | 全カードスキップ | 影響なし |
| Undoフロー: 正常系 | Undo + regrade(quality 5) | **要注意**: regrade quality 5 は reconfirmQueue に追加しない。handleUndo の reconfirmQueue.filter は空振り(元々追加されていない) |
| Undoフロー: エラー系 | Undo API エラー | 影響なし |

**結論**: 既存テストは全て quality 3-5 またはスキップを使用しているため、reconfirmQueue への追加は発生せず、既存動作に影響しない。

---

## 12. テストケースサマリー

### 新規テストケース一覧

| ID | カテゴリ | テスト内容 | 要件参照 |
|---|---|---|---|
| TC-TDD-020-01 | キュー追加 | quality 0 でキュー追加 | REQ-001, TC-001-01 |
| TC-TDD-020-02 | キュー追加 | quality 1 でキュー追加 | REQ-001, TC-001-02 |
| TC-TDD-020-03 | キュー追加 | quality 2 でキュー追加 | REQ-001, TC-001-03 |
| TC-TDD-020-04 | キュー非追加 | quality 3 でキュー非追加 | REQ-103, TC-001-B01 |
| TC-TDD-020-05 | キュー非追加 | quality 4 でキュー非追加 | REQ-103 |
| TC-TDD-020-06 | キュー非追加 | quality 5 でキュー非追加 | REQ-103 |
| TC-TDD-021-01 | Undo+regrade | regrade quality 0-2 でキュー追加 | REQ-404, TC-404-02 |
| TC-TDD-021-02 | Undo+regrade | regrade quality 3+ でキュー非追加 | REQ-404, TC-404-03 |
| TC-TDD-030-01 | 覚えた | キューから除外 | REQ-003, TC-003-01 |
| TC-TDD-030-02 | 覚えた | API 呼び出しなし | REQ-003, TC-003-02 |
| TC-TDD-030-03 | 覚えた | type = 'reconfirmed' 更新 | REQ-003, REQ-501 |
| TC-TDD-030-04 | 覚えた | reconfirmResult = 'remembered' | REQ-003, REQ-501 |
| TC-TDD-040-01 | 覚えていない | キュー末尾に再追加 | REQ-004, TC-004-01 |
| TC-TDD-040-02 | 覚えていない | API 呼び出しなし | REQ-004, TC-004-02 |
| TC-TDD-040-03 | 覚えていない | 複数回ループ後に覚えた | REQ-004, TC-004-03 |
| TC-TDD-050-02 | moveToNext | reconfirmQueue 非空 -> 再確認モード | REQ-502 |
| TC-TDD-050-04 | moveToNext | 再確認キュー消化後 -> 完了 | REQ-502 |
| TC-TDD-060-01 | Undo連携 | キューから除去 | REQ-404, TC-404-01 |
| TC-TDD-INT-01 | 統合 | 通常3枚 + 再確認1枚 | REQ-001~003, REQ-502 |
| TC-TDD-INT-02 | 統合 | 全カード再確認 | EDGE-101 |
| TC-TDD-INT-03 | 統合 | 覚えていない複数回 | EDGE-102, REQ-402 |
| TC-TDD-INT-04 | 統合 | Undo -> regrade -> 再確認 | REQ-404, EDGE-202 |
| TC-TDD-EDGE-01 | エッジ | 空キューで覚えた呼び出し | 防御的プログラミング |
| TC-TDD-EDGE-02 | エッジ | 空キューで覚えていない呼び出し | 防御的プログラミング |
| TC-TDD-EDGE-03 | エッジ | 複数カードキューで先頭のみ除外 | REQ-003 |
| TC-TDD-EDGE-04 | エッジ | quality 3-5 の Undo でキュー空振り | REQ-404 |

**合計**: 26 テストケース (新規)
**既存テスト**: 20+ テストケース (互換性維持)

---

## 13. テスト実装上の注意点

### 13.1 テスト手法

本タスクはロジックのみの実装であり、UI コンポーネント(GradeButtons の「覚えた」「覚えていない」ボタン等)は TASK-0082 で実装する。そのため、テストでは以下のアプローチを取る:

1. **既存の UI 操作でテスト可能な範囲**: quality 0-2 でのキュー追加判定、moveToNext の遷移ロジック等は、既存の GradeButtons を使って quality 0-2 を選択し、その後の状態(完了画面に遷移するかしないか等)で間接検証する

2. **ハンドラの直接テスト**: handleReconfirmRemembered / handleReconfirmForgotten は UI ボタンが未実装のため、ReviewPage コンポーネントから props 経由で公開するか、テスト用のヘルパーを使って呼び出す。具体的には:
   - ReviewPage が子コンポーネントに渡す props を通じて間接的にテストする
   - または、テスト内で act() を使って state を操作する

3. **moveToNext の間接検証**: moveToNext は handleGrade / handleReconfirmRemembered / handleReconfirmForgotten 内で呼ばれるため、これらのハンドラを通じて間接検証する

### 13.2 モック戦略

既存のモック構成をそのまま維持する:
- `mockGetDueCards`: カード取得 API
- `mockSubmitReview`: 採点 API
- `mockUndoReview`: Undo API

再確認ハンドラは API 呼び出しを行わないため、追加モックは不要。

### 13.3 テスト用データ

既存の `mockDueCards` (3枚)を基本として使用。必要に応じて1枚のみのケースも設定する。

---

## 14. 完了条件チェックリスト

- [ ] ReconfirmCard 型が card.ts に定義されている(cardId, front, back, originalGrade)
- [ ] SessionCardResultType に 'reconfirmed' が追加されている
- [ ] SessionCardResult に reconfirmResult?: 'remembered' が追加されている
- [ ] ReviewPage に reconfirmQueue state が追加されている
- [ ] ReviewPage に isReconfirmMode state が追加されている
- [ ] ReviewPage に currentReconfirmCard 導出値が追加されている
- [ ] handleGrade: Normal mode で quality 0-2 の場合 reconfirmQueue に追加される
- [ ] handleGrade: Normal mode で quality 3-5 の場合 reconfirmQueue に追加されない
- [ ] handleGrade: Regrade mode で quality 0-2 の場合 reconfirmQueue に追加される
- [ ] handleGrade: Regrade mode で quality 3-5 の場合 reconfirmQueue に追加されない
- [ ] handleReconfirmRemembered: キューから先頭除外、reviewResults を 'reconfirmed' に更新、API 呼び出しなし
- [ ] handleReconfirmForgotten: キュー末尾に再追加、API 呼び出しなし
- [ ] moveToNext: 通常カード消化後に reconfirmQueue 非空なら isReconfirmMode = true
- [ ] moveToNext: 通常カード消化後に reconfirmQueue 空なら isComplete = true
- [ ] moveToNext: 再確認キュー消化後に isComplete = true
- [ ] handleUndo: reconfirmQueue から該当カードを除去
- [ ] handleUndo: isReconfirmMode をリセット
- [ ] 既存テスト全件パス
- [ ] 新規テスト全件パス
- [ ] TypeScript コンパイルエラーなし

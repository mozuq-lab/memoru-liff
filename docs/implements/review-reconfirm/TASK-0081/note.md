# TASK-0081 実装ノート：型定義拡張 + ReviewPageコアロジック実装

**作成日**: 2026-02-28
**タスク**: 再確認ループのコアロジック（型定義 + ReviewPageの状態管理と処理）の実装
**ステータス**: 計画・分析段階

---

## 1. タスク概要

このタスクは review-reconfirm 機能の**フェーズ1（基盤構築）**の中核を担います。以下の2つの主要な実装を行います：

1. **型定義の拡張**: `SessionCardResultType` に `'reconfirmed'` を追加、`ReconfirmCard` インターフェースの新規作成
2. **ReviewPageの状態管理拡張**: `reconfirmQueue` と `isReconfirmMode` の状態追加、ハンドラロジックの実装

**重要な特性**:
- 再確認キューはセッション内フロントエンド状態のみで管理（バックエンドAPI呼び出しなし）
- quality 0-2 評価時のみキューに追加（quality 3-5では追加しない）
- Undo連携が必須（キューからの除去とregrade時の再追加判定）
- 現在の ReviewPage の `useState` フラットパターンを維持

---

## 2. 実装の依存関係と構造

### 実装順序

```
① 型定義拡張 (frontend/src/types/card.ts)
   └─ ReconfirmCard, SessionCardResultType更新

② ReviewPage状態追加 (frontend/src/pages/ReviewPage.tsx)
   └─ reconfirmQueue, isReconfirmMode state

③ handleGrade拡張
   └─ quality 0-2でreconfirmQueue末尾に追加
   └─ regradeモード対応

④ handleReconfirmRemembered/Forgotten
   └─ キュー操作のロジック

⑤ moveToNext拡張
   └─ 通常カード → 再確認キュー → 完了の遷移

⑥ handleUndo拡張
   └─ reconfirmQueueからの該当カード除去
```

### 外部依存関係

- **GradeButtons**: `onReconfirmRemembered` / `onReconfirmForgotten` の props 追加待ち（TASK-0082）
- **ReviewComplete** / **ReviewResultItem**: 再確認結果表示対応（TASK-0082以降）
- **ReconfirmBadge**: 新規コンポーネント（TASK-0082以降）

このタスクで実装するのは**ロジックのみ**。UIレンダリングは次タスク以降で実装。

---

## 3. 詳細実装ガイド

### 3.1 型定義の拡張（frontend/src/types/card.ts）

**現状**:
```typescript
type SessionCardResultType = 'graded' | 'skipped' | 'undone';

interface SessionCardResult {
  cardId: string;
  front: string;
  grade?: number;
  nextReviewDate?: string;
  type: SessionCardResultType;
}
```

**変更内容**:
```typescript
// 1. SessionCardResultType を拡張
type SessionCardResultType = 'graded' | 'skipped' | 'undone' | 'reconfirmed';

// 2. SessionCardResult に reconfirmResult フィールド追加
interface SessionCardResult {
  cardId: string;
  front: string;
  grade?: number;
  nextReviewDate?: string;
  type: SessionCardResultType;
  reconfirmResult?: 'remembered';  // 「覚えた」を選択した場合
}

// 3. ReconfirmCard インターフェース新規追加
interface ReconfirmCard {
  cardId: string;
  front: string;
  back: string;
  originalGrade: number;  // quality 0, 1, or 2
}
```

**信頼性**: 🔵 *設計文書 architecture.md・要件定義書 REQ-001, REQ-501より*

**テスト対象**:
- `ReconfirmCard` が必須フィールド 4個を持つ
- `SessionCardResultType` に `'reconfirmed'` が含まれる
- `SessionCardResult` で `reconfirmResult?: 'remembered'` が存在する

---

### 3.2 ReviewPage状態管理の拡張

**現状**:
```typescript
const [cards, setCards] = useState<DueCard[]>([]);
const [currentIndex, setCurrentIndex] = useState(0);
const [isFlipped, setIsFlipped] = useState(false);
const [isSubmitting, setIsSubmitting] = useState(false);
const [reviewedCount, setReviewedCount] = useState(0);
const [isComplete, setIsComplete] = useState(false);
const [reviewResults, setReviewResults] = useState<SessionCardResult[]>([]);
const [isLoading, setIsLoading] = useState(true);
const [error, setError] = useState<string | null>(null);
const [regradeCardIndex, setRegradeCardIndex] = useState<number | null>(null);
const [isUndoing, setIsUndoing] = useState(false);
const [undoingIndex, setUndoingIndex] = useState<number | null>(null);
```

**追加する state**:
```typescript
// 再確認キュー管理
const [reconfirmQueue, setReconfirmQueue] = useState<ReconfirmCard[]>([]);

// 現在のカードが再確認モードかどうか
const [isReconfirmMode, setIsReconfirmMode] = useState<boolean>(false);

// 補助（derived state）: 再確認キューの先頭カード
const currentReconfirmCard = reconfirmQueue.length > 0 ? reconfirmQueue[0] : null;
```

**信頼性**: 🔵 *設計文書 architecture.md・ヒアリング回答（useState維持）より*

---

### 3.3 handleGrade拡張（quality 0-2でキュー追加）

**現状**:
```typescript
const handleGrade = useCallback(async (grade: number) => {
  // Regrade mode
  if (regradeCardIndex !== null) {
    const result = reviewResults[regradeCardIndex];
    setIsSubmitting(true);
    setError(null);
    try {
      const response = await reviewsApi.submitReview(result.cardId, grade);
      setReviewResults((prev) =>
        prev.map((r, i) =>
          i === regradeCardIndex
            ? { ...r, grade, nextReviewDate: response.updated.due_date, type: 'graded' as const }
            : r
        )
      );
      setReviewedCount((prev) => prev + 1);
    } catch {
      setError('再採点の送信に失敗しました');
    } finally {
      setIsSubmitting(false);
      setRegradeCardIndex(null);
      setIsComplete(true);
    }
    return;
  }

  // Normal mode
  const currentCard = cards[currentIndex];
  setIsSubmitting(true);
  setError(null);
  try {
    const response = await reviewsApi.submitReview(currentCard.card_id, grade);
    setReviewResults((prev) => [
      ...prev,
      {
        cardId: currentCard.card_id,
        front: currentCard.front,
        grade,
        nextReviewDate: response.updated.due_date,
        type: 'graded' as const,
      },
    ]);
    setReviewedCount((prev) => prev + 1);
    moveToNext();
  } catch {
    setError('採点の送信に失敗しました');
  } finally {
    setIsSubmitting(false);
  }
}, [cards, currentIndex, moveToNext, regradeCardIndex, reviewResults]);
```

**変更内容**: normal mode で API 成功後に **grade が 0-2 の場合のみ** reconfirmQueue に追加

**実装パターン**:
```typescript
// Normal mode の API 成功後
try {
  const response = await reviewsApi.submitReview(currentCard.card_id, grade);

  // 既存の結果追加
  setReviewResults((prev) => [
    ...prev,
    {
      cardId: currentCard.card_id,
      front: currentCard.front,
      grade,
      nextReviewDate: response.updated.due_date,
      type: 'graded' as const,
    },
  ]);

  // ★ 再確認キュー追加判定（quality 0-2 の場合）
  if (grade < 3) {
    setReconfirmQueue((prev) => [
      ...prev,
      {
        cardId: currentCard.card_id,
        front: currentCard.front,
        back: currentCard.back,
        originalGrade: grade,
      },
    ]);
  }

  setReviewedCount((prev) => prev + 1);
  moveToNext();
} catch {
  setError('採点の送信に失敗しました');
}
```

**regrade mode での拡張**: `regradeCardIndex !== null` 時にも同じロジックを適用

```typescript
// Regrade mode
if (regradeCardIndex !== null) {
  const result = reviewResults[regradeCardIndex];
  const regradeCard = cards.find((c) => c.card_id === result.cardId);

  setIsSubmitting(true);
  setError(null);
  try {
    const response = await reviewsApi.submitReview(result.cardId, grade);

    setReviewResults((prev) =>
      prev.map((r, i) =>
        i === regradeCardIndex
          ? { ...r, grade, nextReviewDate: response.updated.due_date, type: 'graded' as const }
          : r
      )
    );

    // ★ 再確認キュー追加判定（quality 0-2 の場合）
    if (grade < 3 && regradeCard) {
      setReconfirmQueue((prev) => [
        ...prev,
        {
          cardId: regradeCard.card_id,
          front: regradeCard.front,
          back: regradeCard.back,
          originalGrade: grade,
        },
      ]);
    }

    setReviewedCount((prev) => prev + 1);
  } catch {
    setError('再採点の送信に失敗しました');
  } finally {
    setIsSubmitting(false);
    setRegradeCardIndex(null);
    setIsComplete(true);
  }
}
```

**信頼性**: 🔵 *要件定義書 REQ-001, REQ-103・データフロー図より*

**テスト対象**:
- quality 0 選択時にreconfirmQueueに追加
- quality 1 選択時にreconfirmQueueに追加
- quality 2 選択時にreconfirmQueueに追加
- quality 3 選択時にreconfirmQueueに追加**されない**
- quality 4-5 選択時にreconfirmQueueに追加**されない**
- regradeモードでも同じ判定を実行

---

### 3.4 handleReconfirmRemembered（「覚えた」ハンドラ）

**新規ハンドラ実装**:

```typescript
const handleReconfirmRemembered = useCallback(() => {
  if (currentReconfirmCard === null) return;

  // 1. reconfirmQueue から先頭を除外
  setReconfirmQueue((prev) => prev.slice(1));

  // 2. reviewResults の該当カードを更新
  //    - type: 'reconfirmed'
  //    - reconfirmResult: 'remembered'
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

**重要ポイント**:
- **API呼び出しなし** ✓
- SM-2 再計算なし ✓
- reviewResults の type を `'reconfirmed'` に更新 ✓
- `reconfirmResult: 'remembered'` を設定 ✓

**信頼性**: 🔵 *要件定義書 REQ-003・データフロー図より*

**テスト対象**:
- handleReconfirmRemembered でカードがキューから除外される
- handleReconfirmRemembered で API が呼ばれない
- reviewResults が 'reconfirmed' に更新される
- reviewResults に reconfirmResult: 'remembered' が設定される

---

### 3.5 handleReconfirmForgotten（「覚えていない」ハンドラ）

**新規ハンドラ実装**:

```typescript
const handleReconfirmForgotten = useCallback(() => {
  if (currentReconfirmCard === null) return;

  // 1. 現在のカードを reconfirmQueue の末尾に再追加
  setReconfirmQueue((prev) => [...prev.slice(1), currentReconfirmCard]);

  // 2. 次のカードへ（API呼び出しなし）
  moveToNext();
}, [currentReconfirmCard, moveToNext]);
```

**詳細説明**:
- `prev.slice(1)`: 先頭を除いたキュー
- `[...prev.slice(1), currentReconfirmCard]`: 末尾に再追加

**重要ポイント**:
- **API呼び出しなし** ✓
- next_review_at は更新**しない**（最初の quality 0-2 評価時に既に設定済み）✓
- キュー末尾に再追加 ✓

**信頼性**: 🔵 *要件定義書 REQ-004・データフロー図より*

**テスト対象**:
- handleReconfirmForgotten でカードがキュー末尾に追加される
- handleReconfirmForgotten で API が呼ばれない
- 複数回「覚えていない」→「覚えた」のフロー

---

### 3.6 moveToNext拡張（カード進行ロジック）

**現状**:
```typescript
const moveToNext = useCallback(() => {
  setIsFlipped(false);
  if (currentIndex >= cards.length - 1) {
    setIsComplete(true);
  } else {
    setCurrentIndex((prev) => prev + 1);
  }
}, [currentIndex, cards.length]);
```

**変更内容**: reconfirmQueue の処理を追加

```typescript
const moveToNext = useCallback(() => {
  setIsFlipped(false);

  // regradeモード終了時はそのまま完了
  if (regradeCardIndex !== null) {
    setIsComplete(true);
    return;
  }

  // 通常カードが残っているか確認
  if (currentIndex < cards.length - 1) {
    // 次の通常カードがある
    setCurrentIndex((prev) => prev + 1);
    setIsReconfirmMode(false);
    return;
  }

  // 通常カード終了、再確認キューを確認
  if (reconfirmQueue.length > 0) {
    // 再確認モードに切り替え
    setIsReconfirmMode(true);
    setCurrentIndex(cards.length);  // 進捗表示用（オプション）
    return;
  }

  // 両方なし → セッション完了
  setIsComplete(true);
}, [currentIndex, cards.length, regradeCardIndex, reconfirmQueue.length]);
```

**状態遷移図**:
```
moveToNext() 呼び出し
  ├─ regradeCardIndex !== null
  │   └─ → isComplete = true（再採点後は必ず完了へ）
  │
  ├─ currentIndex < cards.length - 1
  │   └─ → currentIndex++, isReconfirmMode = false（次の通常カード）
  │
  ├─ reconfirmQueue.length > 0
  │   └─ → isReconfirmMode = true（再確認キューへ）
  │
  └─ else
      └─ → isComplete = true（完了）
```

**重要ポイント**:
- 通常カードと再確認カードは**同一キューで流れる**（REQ-502）
  - 実装上は通常カードを先に消化してから再確認キューに進む
- `isReconfirmMode` で UI が切り替わる（GradeButtons の判定用）
- `isFlipped` は 0 にリセット

**信頼性**: 🔵 *要件定義書 REQ-502・データフロー図より*

**テスト対象**:
- 通常カード完了後にreconfirmQueueから取り出す
- reconfirmQueue空の場合にセッション完了

---

### 3.7 handleUndo拡張（再確認キューとの連携）

**現状**:
```typescript
const handleUndo = useCallback(async (index: number) => {
  const result = reviewResults[index];
  setIsUndoing(true);
  setUndoingIndex(index);
  setError(null);
  try {
    await reviewsApi.undoReview(result.cardId);
    setReviewResults((prev) =>
      prev.map((r, i) =>
        i === index ? { ...r, type: 'undone' as const } : r
      )
    );
    setReviewedCount((prev) => Math.max(0, prev - 1));
    setRegradeCardIndex(index);
    setIsComplete(false);
    setIsFlipped(false);
  } catch {
    setError('取り消しに失敗しました');
  } finally {
    setIsUndoing(false);
    setUndoingIndex(null);
  }
}, [reviewResults]);
```

**変更内容**: reconfirmQueue からの除去処理を追加

```typescript
const handleUndo = useCallback(async (index: number) => {
  const result = reviewResults[index];
  setIsUndoing(true);
  setUndoingIndex(index);
  setError(null);
  try {
    await reviewsApi.undoReview(result.cardId);

    setReviewResults((prev) =>
      prev.map((r, i) =>
        i === index ? { ...r, type: 'undone' as const } : r
      )
    );

    // ★ 再確認キューから該当カードを除去
    setReconfirmQueue((prev) =>
      prev.filter((rc) => rc.cardId !== result.cardId)
    );

    setReviewedCount((prev) => Math.max(0, prev - 1));
    setRegradeCardIndex(index);
    setIsComplete(false);
    setIsFlipped(false);
  } catch {
    setError('取り消しに失敗しました');
  } finally {
    setIsUndoing(false);
    setUndoingIndex(null);
  }
}, [reviewResults]);
```

**重要ポイント**:
- Undo 後は regradeMode に入る（既存ロジック）
- regradeMode での再評価が quality 0-2 なら、また reconfirmQueue に追加される
  - これは handleGrade の拡張ロジック（3.3 参照）で自動的に処理される

**信頼性**: 🔵 *要件定義書 REQ-404・ヒアリングQ4回答より*

**テスト対象**:
- Undo時にreconfirmQueueから該当カードが除去される
- Undo後のregrade quality 0-2で再びキューに追加
- Undo後のregrade quality 3+ではキューに追加されない

---

## 4. 状態遷移の全体図

```
【セッション開始】
    ↓
┌─ cards 取得
│   isLoading = true
│   ↓ API完了
│   isLoading = false
│
├─ 通常モード（isReconfirmMode = false）
│   ├─ currentIndex < cards.length-1
│   │   ├─ grade 0-2 → SM-2 API → reconfirmQueue末尾に追加 → moveToNext
│   │   ├─ grade 3-5 → SM-2 API → 次のカード（キューには追加しない）
│   │   └─ skip → 次のカード
│   │
│   └─ currentIndex >= cards.length-1（最後のカード）
│       ├─ grade/skip → moveToNext
│       │   ↓ reconfirmQueue.length > 0
│       │   └─ isReconfirmMode = true
│       │   ↓ reconfirmQueue.length = 0
│       │   └─ isComplete = true
│
├─ 再確認モード（isReconfirmMode = true）
│   ├─ 「覚えた」→ キューから除外 → moveToNext
│   │   ├─ キューに他のカードあり → 次の再確認カード
│   │   └─ キューが空 → isComplete = true
│   │
│   └─ 「覚えていない」→ キュー末尾に再追加 → moveToNext
│       └─ 別のカードがあれば先に表示 → キューに戻ってくる
│
├─ Undo（完了画面から）
│   ├─ API成功
│   ├─ reviewResults[index].type = 'undone'
│   ├─ reconfirmQueue から除去
│   ├─ regradeCardIndex = index
│   ├─ isComplete = false
│   │   ↓ 再採点モードで表示
│   │
│   └─ 再採点
│       ├─ grade 0-2 → reconfirmQueue に追加
│       ├─ grade 3-5 → 追加しない
│       └─ isComplete = true（完了画面に戻る）

【セッション完了】
```

---

## 5. テスト戦略

### 5.1 ユニットテスト対象

**型定義テスト** (`card.ts`):
```typescript
- ReconfirmCard インターフェースが正しく定義されている
- SessionCardResultType に 'reconfirmed' が含まれている
- SessionCardResult に reconfirmResult フィールドがある
```

**State管理テスト** (`ReviewPage`):
```typescript
describe('再確認キュー追加テスト', () => {
  it('quality 0選択時にreconfirmQueueに追加される', ...)
  it('quality 1選択時にreconfirmQueueに追加される', ...)
  it('quality 2選択時にreconfirmQueueに追加される', ...)
  it('quality 3選択時にreconfirmQueueに追加されない', ...)
  it('quality 4-5選択時にreconfirmQueueに追加されない', ...)
});

describe('「覚えた」ハンドラテスト', () => {
  it('handleReconfirmRememberedでカードがキューから除外される', ...)
  it('handleReconfirmRememberedでAPIが呼ばれない', ...)
  it('reviewResultsが"reconfirmed"に更新される', ...)
});

describe('「覚えていない」ハンドラテスト', () => {
  it('handleReconfirmForgottenでカードがキュー末尾に追加される', ...)
  it('handleReconfirmForgottenでAPIが呼ばれない', ...)
  it('複数回「覚えていない」→「覚えた」のフロー', ...)
});

describe('moveToNext拡張テスト', () => {
  it('通常カード完了後にreconfirmQueueから取り出す', ...)
  it('reconfirmQueue空の場合にセッション完了', ...)
});

describe('Undo連携テスト', () => {
  it('Undo時にreconfirmQueueから除去される', ...)
  it('Undo後のregrade quality 0-2で再びキューに追加', ...)
  it('Undo後のregrade quality 3+ではキューに追加されない', ...)
});
```

### 5.2 既存テストとの互換性

**現在の ReviewPage.test.tsx** は以下のテストケースを含みます：
- テストケース1-7: 基本的なカード表示・採点・完了フロー
- テストケース8-10: エラーハンドリング・進捗表示
- 戻るボタン: ナビゲーション
- 統合テスト: 3枚中2枚採点・1枚スキップ
- エッジケース: カード1枚のみ、全カードスキップ
- Undoフロー: 正常系・エラー系

**このタスクの実装で保証すべき事項**:
- ✅ 既存テストが引き続き通る（再確認機能を追加しても通常の grade 3-5 フローは変わらない）
- ✅ 新規テスト（上記5.1）が全て通る
- ✅ 統合テスト：quality 0-2 → 再確認キューに追加 → 次のカード という流れが正常に動く

---

## 6. 実装上の注意点

### 6.1 依存性の管理

**moveToNext の依存配列**:
```typescript
const moveToNext = useCallback(() => {
  // ...
}, [currentIndex, cards.length, regradeCardIndex, reconfirmQueue.length]);
```

- `reconfirmQueue` ではなく `reconfirmQueue.length` を依存に含める（参照の変更を避ける）
- または useCallback を使わずに useEffect で管理することも検討

### 6.2 currentReconfirmCard の導出

```typescript
// derived state として再計算
const currentReconfirmCard = reconfirmQueue.length > 0 ? reconfirmQueue[0] : null;
```

- state ではなく、毎回の render で計算する方が安全
- 再確認モード中に reconfirmQueue[0] を正確に取得できる

### 6.3 isReconfirmMode と currentIndex の関係

```
// 再確認モード中の currentIndex について
- オプション1: currentIndex = cards.length（進捗表示時に「通常カード数 / 通常カード数」と表示）
- オプション2: currentIndex をそのまま（進捗表示は変わらない）

実装上はオプション2を推奨（シンプル、既存ロジックへの影響最小）
ReviewProgress の表示は normal カード のみを対象とする
```

### 6.4 リセット処理

**セッション開始時・Undo操作時**:
```typescript
// fetchCards 後、または handleUndo 前に必ず初期化
setReconfirmQueue([]);
setIsReconfirmMode(false);
```

---

## 7. 実装ファイル一覧

| ファイル | 変更内容 | 行数目安 |
|---------|---------|--------|
| `frontend/src/types/card.ts` | SessionCardResultType + ReconfirmCard + 型拡張 | +15行 |
| `frontend/src/pages/ReviewPage.tsx` | state追加（reconfirmQueue, isReconfirmMode）、4つのハンドラ、moveToNext拡張、handleUndo拡張 | +100行 |
| `frontend/src/pages/__tests__/ReviewPage.test.tsx` | テストケース追加（TC-001-01～TC-404-03、EDGE-101, EDGE-102） | +200行 |

---

## 8. 完了条件チェックリスト

- [ ] ReconfirmCard型とSessionCardResultType拡張が定義されている
- [ ] reconfirmQueue / isReconfirmMode のstate管理が実装されている
- [ ] quality 0-2評価時にreconfirmQueue末尾にカードが追加される
- [ ] quality 3-5評価時にreconfirmQueueに追加されない
- [ ] handleReconfirmRemembered: API呼び出しなし、キューから除外、結果更新
- [ ] handleReconfirmForgotten: API呼び出しなし、キュー末尾に再追加
- [ ] moveToNext: 通常カード消化後にreconfirmQueueから取り出す
- [ ] Undo時にreconfirmQueueから該当カードが除去される
- [ ] Undo後の再評価（regrade）でquality 0-2選択時に再びキューに追加される
- [ ] 全テストが通る（既存 + 新規）

---

## 9. 次タスクへの引き継ぎ

**TASK-0082: UIコンポーネント実装** では以下を実装：

- **GradeButtons** の拡張：
  - `isReconfirmMode` props 追加
  - 再確認モード時は「覚えた」「覚えていない」の2択のみ
  - `onReconfirmRemembered` / `onReconfirmForgotten` props 追加
  - スキップボタン非表示化（再確認モード時）

- **ReconfirmBadge** 新規コンポーネント：
  - 「再確認」バッジの表示

- **ReviewComplete** / **ReviewResultItem** の拡張：
  - 再確認結果の表示（grade色 + 「覚えた✔」）
  - Undo ボタンの再確認カード対応

---

## 10. 参考資料

| 資料 | パス | 参照個所 |
|------|------|---------|
| 要件定義書 | `docs/spec/review-reconfirm/requirements.md` | REQ-001~005, REQ-103, REQ-201~203, REQ-401~404 |
| アーキテクチャ | `docs/design/review-reconfirm/architecture.md` | 状態管理設計、ReconfirmCard型、moveToNext拡張 |
| データフロー | `docs/design/review-reconfirm/dataflow.md` | フロー図、状態遷移 |
| 受け入れ基準 | `docs/spec/review-reconfirm/acceptance-criteria.md` | TC-001-01～TC-404-03、EDGE-001～102 |
| 既存設計（review-flow） | `docs/design/review-flow/architecture.md` | 既存ハンドラパターン、状態管理パターン |
| 既存設計（review-undo） | `docs/design/review-undo/architecture.md` | Undo機能との統合 |

---

## 11. 実装時の疑問点・判断ポイント

### Q1: reconfirmQueue と currentIndex の同期

**Q**: 再確認モード中、currentIndex はどの値を持つべき？

**A**:
- オプション1: `cards.length`（再確認カード=追加カードという意味）
- オプション2: そのまま（currentIndex は通常カード用）

**推奨**: オプション2。理由：
- 既存ロジックへの影響最小
- 再確認カードと通常カードを区別したいなら `isReconfirmMode` フラグで十分
- ReviewProgress は通常カードのみを分母とする（REQ-502）

### Q2: handleReconfirmRemembered/Forgotten から moveToNext を呼ぶ順序

**Q**: setReconfirmQueue の後に moveToNext を呼んでも大丈夫？

**A**: ✅ 大丈夫。理由：
- React の setState は非同期だが、同じ render cycle 内で複数の setState は batch される
- moveToNext 内で reconfirmQueue.length を読むときは、既に更新されている

### Q3: Undo後の regrade で isReconfirmMode をリセットすべき？

**Q**: regradeCardIndex がセットされるとき、isReconfirmMode をリセット？

**A**: ✅ リセットすべき。現在の実装を確認：
```typescript
setRegradeCardIndex(index);
setIsComplete(false);
```

isReconfirmMode もリセット：
```typescript
setRegradeCardIndex(index);
setIsReconfirmMode(false);  // ← 追加
setIsComplete(false);
```

理由：再採点モードは通常の6段階評価UI。再確認2択ではない。

### Q4: sessionStorage/localStorage への永続化は？

**Q**: セッション中にアプリが閉じられたとき、reconfirmQueue は？

**A**: 🔵 確定。要件定義書 REQ-201, EDGE-001 より：

> 再確認ループの状態はセッション内のフロントエンド状態のみで管理し、セッション終了時にリセットされなければならない

つまり：
- 永続化**しない** ✓
- アプリ閉じるとreconfirmQueueは失われる
- SM-2がquality 0-2でinterval=1を設定済みなので翌日に再表示される

---

## 12. まとめ

TASK-0081 は review-reconfirm 機能の**ロジック基盤**を構築するタスクです。以下の3点が核です：

1. **型定義**: ReconfirmCard インターフェース + SessionCardResultType 拡張
2. **状態管理**: reconfirmQueue + isReconfirmMode state
3. **ハンドラロジック**: grade拡張 + 2つの再確認ハンドラ + moveToNext拡張 + Undo拡張

実装は**フロントエンド state のみ**。API呼び出しはありません。既存の `useState` パターンを維持し、10個の完了条件を満たす必要があります。

次タスク（TASK-0082）で UI コンポーネントが実装され、最終的な再確認ループが完成します。


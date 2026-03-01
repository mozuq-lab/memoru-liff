# TASK-0081 テストケース定義: 型定義拡張 + ReviewPageコアロジック実装

**作成日**: 2026-02-28
**タスク**: TASK-0081
**テストファイル**: `frontend/src/pages/__tests__/ReviewPage.test.tsx`
**テスト対象ファイル**:
- `frontend/src/types/card.ts` (型定義拡張)
- `frontend/src/pages/ReviewPage.tsx` (状態管理 + ハンドラ + ロジック拡張)

---

## テスト方針

### テスト手法

TASK-0081 はロジックのみの実装であり、UI コンポーネント (GradeButtons の「覚えた」「覚えていない」ボタン等) は TASK-0082 で実装する。そのため以下のアプローチを取る。

1. **既存 UI 操作で検証可能な範囲**: quality 0-2 でのキュー追加判定や moveToNext の遷移ロジックは、既存の GradeButtons (aria-label `0 - 全く覚えていない` 等) を使って quality 0-2 を選択し、その後の状態 (完了画面に遷移するかしないか等) で間接検証する。
2. **ハンドラの直接テスト**: `handleReconfirmRemembered` / `handleReconfirmForgotten` は UI ボタンが未実装のため、ReviewPage が子コンポーネントに渡す props を通じて間接的にテストするか、内部 state を参照して検証する。具体的なテスト実装方法は tdd-red フェーズで決定する。
3. **moveToNext の間接検証**: moveToNext は handleGrade / handleReconfirmRemembered / handleReconfirmForgotten 内で呼ばれるため、これらのハンドラを通じて間接検証する。

### モック戦略

既存のモック構成をそのまま維持する:

```typescript
const mockGetDueCards = vi.fn();
const mockSubmitReview = vi.fn();
const mockUndoReview = vi.fn();

vi.mock('@/services/api', () => ({
  cardsApi: { getDueCards: (...args: unknown[]) => mockGetDueCards(...args) },
  reviewsApi: {
    submitReview: (...args: unknown[]) => mockSubmitReview(...args),
    undoReview: (...args: unknown[]) => mockUndoReview(...args),
  },
}));
```

再確認ハンドラは API 呼び出しを行わないため、追加モックは不要。

### テスト用データ

既存の `mockDueCards` (3 枚) を基本として使用。1 枚のみのケースも必要に応じて設定する。

```typescript
const mockDueCards = [
  { card_id: 'card-1', front: '質問1', back: '解答1', overdue_days: 0 },
  { card_id: 'card-2', front: '質問2', back: '解答2', overdue_days: 1 },
  { card_id: 'card-3', front: '質問3', back: '解答3', overdue_days: 2 },
];
```

---

## テストケース一覧

### 1. 再確認キュー追加テスト (handleGrade 拡張 - Normal mode)

**describe**: `再確認キュー追加: Normal mode`
**要件参照**: REQ-001, REQ-103, TC-001-01 ~ TC-001-B01

#### TC-TDD-020-01: quality 0 選択時に reconfirmQueue に追加される

- **ID**: TC-TDD-020-01
- **テスト名**: `quality 0 選択時に再確認キューに追加され、通常カード消化後に再確認モードに遷移する`
- **前提条件**: カード 1 枚のみ (mockGetDueCards で 1 枚返却)
- **操作手順**:
  1. カード表示を待つ
  2. カードをフリップ (click on `カード表面を表示中`)
  3. quality 0 ボタンを押す (`aria-label: "0 - 全く覚えていない"`)
- **期待結果**:
  - `mockSubmitReview` が `(cardId, 0)` で呼ばれる
  - 完了画面 (`復習完了!`) に**遷移しない** (再確認キューに追加されたため)
  - `isReconfirmMode = true` の状態に遷移する
- **検証方法**: 完了テキストが表示されないことで間接検証。カード 1 枚のみの場合、quality 3-5 なら即完了するが、quality 0 では完了しない。
- **要件参照**: REQ-001, TC-001-01

#### TC-TDD-020-02: quality 1 選択時に reconfirmQueue に追加される

- **ID**: TC-TDD-020-02
- **テスト名**: `quality 1 選択時に再確認キューに追加され、通常カード消化後に再確認モードに遷移する`
- **前提条件**: カード 1 枚のみ
- **操作手順**:
  1. カード表示を待つ
  2. カードをフリップ
  3. quality 1 ボタンを押す (`aria-label: "1 - 間違えた"`)
- **期待結果**:
  - `mockSubmitReview` が `(cardId, 1)` で呼ばれる
  - 完了画面に遷移しない
- **検証方法**: TC-TDD-020-01 と同様
- **要件参照**: REQ-001, TC-001-02

#### TC-TDD-020-03: quality 2 選択時に reconfirmQueue に追加される

- **ID**: TC-TDD-020-03
- **テスト名**: `quality 2 選択時に再確認キューに追加され、通常カード消化後に再確認モードに遷移する`
- **前提条件**: カード 1 枚のみ
- **操作手順**:
  1. カード表示を待つ
  2. カードをフリップ
  3. quality 2 ボタンを押す (`aria-label: "2 - 間違えたが見覚えあり"`)
- **期待結果**:
  - `mockSubmitReview` が `(cardId, 2)` で呼ばれる
  - 完了画面に遷移しない
- **検証方法**: TC-TDD-020-01 と同様
- **要件参照**: REQ-001, TC-001-03

#### TC-TDD-020-04: quality 3 選択時に reconfirmQueue に追加されない

- **ID**: TC-TDD-020-04
- **テスト名**: `quality 3 選択時に再確認キューに追加されず、セッションが直接完了する`
- **前提条件**: カード 1 枚のみ
- **操作手順**:
  1. カード表示を待つ
  2. カードをフリップ
  3. quality 3 ボタンを押す (`aria-label: "3 - 難しかったが正解"`)
- **期待結果**:
  - `mockSubmitReview` が呼ばれる
  - 完了画面 (`復習完了!`) が表示される (reconfirmQueue は空のまま)
- **検証方法**: 完了テキストの表示で検証。既存エッジケーステストと同等。
- **要件参照**: REQ-103, TC-001-B01

#### TC-TDD-020-05: quality 4 選択時に reconfirmQueue に追加されない

- **ID**: TC-TDD-020-05
- **テスト名**: `quality 4 選択時に再確認キューに追加されず、セッションが直接完了する`
- **前提条件**: カード 1 枚のみ
- **操作手順**:
  1. カード表示を待つ
  2. カードをフリップ
  3. quality 4 ボタンを押す (`aria-label: "4 - やや迷ったが正解"`)
- **期待結果**:
  - 完了画面 (`復習完了!`) が表示される
- **検証方法**: 既存テスト (テストケース 5/7) で既に検証済み。既存テストがパスすることで確認。
- **要件参照**: REQ-103

#### TC-TDD-020-06: quality 5 選択時に reconfirmQueue に追加されない

- **ID**: TC-TDD-020-06
- **テスト名**: `quality 5 選択時に再確認キューに追加されず、セッションが直接完了する`
- **前提条件**: カード 1 枚のみ
- **操作手順**:
  1. カード表示を待つ
  2. カードをフリップ
  3. quality 5 ボタンを押す (`aria-label: "5 - 完璧"`)
- **期待結果**:
  - 完了画面 (`復習完了!`) が表示される
- **検証方法**: 既存テスト (テストケース 7) で既に検証済み。既存テストがパスすることで確認。
- **要件参照**: REQ-103

---

### 2. 再確認キュー追加テスト (handleGrade 拡張 - Regrade mode)

**describe**: `再確認キュー追加: Regrade mode`
**要件参照**: REQ-001, REQ-404, TC-404-02, TC-404-03

#### TC-TDD-021-01: Undo 後の regrade quality 0-2 で reconfirmQueue に追加

- **ID**: TC-TDD-021-01
- **テスト名**: `Undo 後の再採点で quality 2 を選択すると再確認キューにカードが追加される`
- **前提条件**: カード 1 枚を quality 4 で評価済み -> 完了画面 -> Undo -> 再採点モード
- **操作手順**:
  1. カード 1 枚を quality 4 で評価して完了画面に遷移
  2. Undo ボタン (`aria-label: "質問1 の採点を取り消す"`) をクリック
  3. 再採点モードでカードをフリップ
  4. quality 2 ボタンを押す (`aria-label: "2 - 間違えたが見覚えあり"`)
- **期待結果**:
  - `mockSubmitReview` が 2 回呼ばれる (初回 quality 4 + regrade quality 2)
  - reconfirmQueue にカードが追加される (完了画面に戻った後の状態で検証)
- **検証方法**: regrade 後の完了画面の状態で間接検証。regrade 後は isComplete = true になるため完了画面に戻るが、reconfirmQueue の内容は結果表示で確認可能。
- **要件参照**: REQ-404, TC-404-02, EDGE-202

#### TC-TDD-021-02: Undo 後の regrade quality 3+ で reconfirmQueue に追加されない

- **ID**: TC-TDD-021-02
- **テスト名**: `Undo 後の再採点で quality 4 を選択すると再確認キューに追加されない`
- **前提条件**: カード 1 枚を quality 4 で評価済み -> 完了画面 -> Undo -> 再採点モード
- **操作手順**:
  1. カード 1 枚を quality 4 で評価して完了画面に遷移
  2. Undo ボタンをクリック
  3. 再採点モードでカードをフリップ
  4. quality 4 ボタンを押す
- **期待結果**:
  - 通常の完了画面に戻る (`復習完了!` が表示)
  - reconfirmQueue にカードが追加されない
- **検証方法**: 既存 Undo テストと同等。完了画面が正常に表示されることで確認。
- **要件参照**: REQ-404, TC-404-03, EDGE-203

---

### 3. 「覚えた」ハンドラテスト (handleReconfirmRemembered)

**describe**: `handleReconfirmRemembered: 「覚えた」ハンドラ`
**要件参照**: REQ-003, TC-003-01, TC-003-02

#### TC-TDD-030-01: 「覚えた」選択でカードがキューから除外され、セッション完了する

- **ID**: TC-TDD-030-01
- **テスト名**: `再確認モードで「覚えた」を選択するとカードがキューから除外され、キューが空ならセッション完了する`
- **前提条件**:
  - カード 1 枚を quality 0 で評価 -> 通常カード全消化 -> 再確認モード (isReconfirmMode = true)
  - reconfirmQueue に 1 枚のカードがある状態
- **操作手順**:
  1. カード 1 枚を quality 0 で評価
  2. 再確認モードに遷移 (通常カード消化完了)
  3. handleReconfirmRemembered を呼び出す
- **期待結果**:
  - reconfirmQueue から該当カードが除外される
  - reconfirmQueue が空になるため isComplete = true
  - 完了画面 (`復習完了!`) が表示される
- **検証方法**: 完了画面表示で検証
- **要件参照**: REQ-003, TC-003-01

#### TC-TDD-030-02: 「覚えた」選択で API が呼ばれない

- **ID**: TC-TDD-030-02
- **テスト名**: `再確認モードで「覚えた」を選択しても submitReview API が追加呼び出しされない`
- **前提条件**: TC-TDD-030-01 と同じ
- **操作手順**:
  1. カード 1 枚を quality 0 で評価 (この時点で submitReview 1 回呼び出し)
  2. 再確認モードに遷移
  3. handleReconfirmRemembered を呼び出す
- **期待結果**:
  - `mockSubmitReview` の呼び出し回数が 1 回のまま (再確認時に追加呼び出しなし)
- **検証方法**: `expect(mockSubmitReview).toHaveBeenCalledTimes(1)` で検証
- **要件参照**: REQ-003, TC-003-02

#### TC-TDD-030-03: reviewResults が 'reconfirmed' type に更新される

- **ID**: TC-TDD-030-03
- **テスト名**: `「覚えた」選択後に reviewResults の該当カードの type が 'reconfirmed' に更新される`
- **前提条件**: TC-TDD-030-01 と同じ
- **操作手順**:
  1. カード 1 枚を quality 2 で評価
  2. 再確認モードに遷移
  3. handleReconfirmRemembered を呼び出す
  4. 完了画面を確認
- **期待結果**:
  - reviewResults 内の該当カードの type が `'reconfirmed'` に更新されている
  - reconfirmResult が `'remembered'` に設定されている
- **検証方法**: 完了画面の ReviewComplete に渡される results の内容で検証 (TASK-0082 で UI 表示が実装されるため、本タスクでは内部状態の検証に留まる場合がある)
- **要件参照**: REQ-003, REQ-501

#### TC-TDD-030-04: reviewResults に reconfirmResult: 'remembered' が設定される

- **ID**: TC-TDD-030-04
- **テスト名**: `「覚えた」選択後に reviewResults の該当カードに reconfirmResult: 'remembered' が設定される`
- **前提条件**: TC-TDD-030-01 と同じ
- **操作手順**: TC-TDD-030-03 と同一フロー
- **期待結果**:
  - reviewResults 内の該当カードに `reconfirmResult: 'remembered'` が含まれる
- **検証方法**: TC-TDD-030-03 と統合して検証可能
- **要件参照**: REQ-003, REQ-501

> **実装メモ**: TC-TDD-030-03 と TC-TDD-030-04 は同一テスト内でまとめて検証してもよい。

---

### 4. 「覚えていない」ハンドラテスト (handleReconfirmForgotten)

**describe**: `handleReconfirmForgotten: 「覚えていない」ハンドラ`
**要件参照**: REQ-004, TC-004-01, TC-004-02, TC-004-03

#### TC-TDD-040-01: 「覚えていない」選択でカードがキュー末尾に再追加される

- **ID**: TC-TDD-040-01
- **テスト名**: `再確認モードで「覚えていない」を選択するとカードがキュー末尾に再追加され、セッションが完了しない`
- **前提条件**:
  - カード 1 枚を quality 0 で評価 -> 再確認モード
  - reconfirmQueue にカードが 1 枚ある状態
- **操作手順**:
  1. カード 1 枚を quality 0 で評価
  2. 再確認モードに遷移
  3. handleReconfirmForgotten を呼び出す
- **期待結果**:
  - カードが reconfirmQueue 末尾に再追加される
  - セッションは完了しない (isComplete = false のまま)
  - キューが空にならないため再確認モードが継続する
- **検証方法**: 完了テキストが表示されないことで検証
- **要件参照**: REQ-004, TC-004-01, REQ-402 (ループ回数上限なし)

#### TC-TDD-040-02: 「覚えていない」選択で API が呼ばれない

- **ID**: TC-TDD-040-02
- **テスト名**: `再確認モードで「覚えていない」を選択しても submitReview API が追加呼び出しされない`
- **前提条件**: TC-TDD-040-01 と同じ
- **操作手順**:
  1. カード 1 枚を quality 0 で評価 (submitReview 1 回)
  2. 再確認モードに遷移
  3. handleReconfirmForgotten を呼び出す
- **期待結果**:
  - `mockSubmitReview` の呼び出し回数が 1 回のまま
- **検証方法**: `expect(mockSubmitReview).toHaveBeenCalledTimes(1)` で検証
- **要件参照**: REQ-004, TC-004-02, REQ-202

#### TC-TDD-040-03: 複数回「覚えていない」-> 「覚えた」のフロー

- **ID**: TC-TDD-040-03
- **テスト名**: `「覚えていない」を2回選択した後「覚えた」を選択するとセッションが完了する`
- **前提条件**: カード 1 枚のみを quality 0 で評価 -> 再確認モード
- **操作手順**:
  1. カード 1 枚を quality 0 で評価
  2. 再確認モードに遷移
  3. handleReconfirmForgotten を呼び出す (1 回目)
  4. handleReconfirmForgotten を呼び出す (2 回目)
  5. handleReconfirmRemembered を呼び出す
- **期待結果**:
  - 3 回目の操作後にキューが空になりセッション完了 (isComplete = true)
  - `mockSubmitReview` は quality 0 評価時の 1 回のみ呼ばれる
  - 完了画面 (`復習完了!`) が表示される
- **検証方法**: 完了テキスト表示 + API 呼び出し回数で検証
- **要件参照**: REQ-004, TC-004-03, EDGE-102, REQ-402

---

### 5. moveToNext 拡張テスト

**describe**: `moveToNext 拡張: カード進行ロジック`
**要件参照**: REQ-502

#### TC-TDD-050-01: 通常カード残りあり -> 次の通常カードへ (既存動作維持)

- **ID**: TC-TDD-050-01
- **テスト名**: `通常カードが残っている場合、次の通常カードに進む`
- **前提条件**: 3 枚のカードのうち 1 枚目を評価済み
- **操作手順**:
  1. カード 1 をフリップして quality 4 で評価
- **期待結果**:
  - 2 枚目のカード (`質問2`) が表示される
  - isReconfirmMode = false (通常モードのまま)
- **検証方法**: 既存テスト (テストケース 5) がパスすることで確認
- **要件参照**: REQ-502

#### TC-TDD-050-02: 通常カード全消化 + reconfirmQueue 非空 -> 再確認モード遷移

- **ID**: TC-TDD-050-02
- **テスト名**: `通常カードを全て消化し、再確認キューが非空の場合、再確認モードに遷移する`
- **前提条件**: カード 1 枚を quality 0 で評価 (reconfirmQueue に 1 件追加される)
- **操作手順**:
  1. カード 1 枚を quality 0 で評価
  2. moveToNext が呼ばれる (handleGrade 内)
- **期待結果**:
  - isReconfirmMode = true に遷移
  - isComplete = false (完了しない)
  - 完了画面に遷移しない
- **検証方法**: 完了テキストが表示されないことで検証 (TC-TDD-020-01 と同一のテストで共検証)
- **要件参照**: REQ-502

#### TC-TDD-050-03: 通常カード全消化 + reconfirmQueue 空 -> セッション完了 (既存動作維持)

- **ID**: TC-TDD-050-03
- **テスト名**: `通常カードを全て消化し、再確認キューが空の場合、セッションが完了する`
- **前提条件**: カード 1 枚を quality 5 で評価 (reconfirmQueue は空のまま)
- **操作手順**:
  1. カード 1 枚を quality 5 で評価
- **期待結果**:
  - isComplete = true
  - 完了画面 (`復習完了!`) が表示される
- **検証方法**: 既存テスト (テストケース 7) がパスすることで確認
- **要件参照**: REQ-502

#### TC-TDD-050-04: 再確認キュー消化後 -> セッション完了

- **ID**: TC-TDD-050-04
- **テスト名**: `再確認キューのカードを全て「覚えた」で消化するとセッションが完了する`
- **前提条件**: reconfirmQueue にカードが 1 枚あり、handleReconfirmRemembered で除外
- **操作手順**:
  1. カード 1 枚を quality 0 で評価 -> 再確認モード遷移
  2. handleReconfirmRemembered を呼び出す
- **期待結果**:
  - reconfirmQueue が空になり isComplete = true
  - 完了画面 (`復習完了!`) が表示される
- **検証方法**: TC-TDD-030-01 と同一テストで共検証
- **要件参照**: REQ-502

---

### 6. Undo 連携テスト (handleUndo 拡張)

**describe**: `handleUndo 拡張: 再確認キューとの連携`
**要件参照**: REQ-404, TC-404-01 ~ TC-404-03

#### TC-TDD-060-01: Undo 時に reconfirmQueue から該当カードが除去される

- **ID**: TC-TDD-060-01
- **テスト名**: `Undo 時に再確認キューから該当カードが除去される`
- **前提条件**:
  - カード 2 枚。カード 1 を quality 1 で評価 (reconfirmQueue に追加)。カード 2 を quality 4 で評価。完了画面に遷移。
- **操作手順**:
  1. カード 1 を quality 1 で評価
  2. カード 2 を quality 4 で評価 -> 完了画面
  3. カード 1 の Undo ボタンをクリック
- **期待結果**:
  - `mockUndoReview` が呼ばれる
  - reconfirmQueue から card-1 が除去される
  - regrade モードに入る (`再採点` テキスト表示)
- **検証方法**: Undo 後に regrade で quality 4 を選択 -> 完了画面に戻る際に reconfirmQueue が空であることを確認 (セッションが正常完了する)
- **要件参照**: REQ-404, TC-404-01

#### TC-TDD-060-02: Undo 後の regrade quality 0-2 で再び reconfirmQueue に追加

- **ID**: TC-TDD-060-02
- **テスト名**: `Undo 後の再採点で quality 0-2 を選択すると再び再確認キューに追加される`
- **前提条件**: TC-TDD-060-01 の続き
- **操作手順**:
  1. カード 1 枚を quality 1 で評価 -> 完了画面
  2. Undo -> regrade モード
  3. quality 2 で再評価
- **期待結果**:
  - reconfirmQueue に再びカードが追加される
  - `mockSubmitReview` が 2 回呼ばれる (初回 quality 1 + regrade quality 2)
- **検証方法**: TC-TDD-021-01 と同一のテストで共検証可能
- **要件参照**: REQ-404, TC-404-02

#### TC-TDD-060-03: Undo 後の regrade quality 3+ で reconfirmQueue に追加されない

- **ID**: TC-TDD-060-03
- **テスト名**: `Undo 後の再採点で quality 3+ を選択すると再確認キューに追加されず、正常完了する`
- **前提条件**: TC-TDD-060-01 の続き
- **操作手順**:
  1. カード 1 枚を quality 1 で評価 -> 完了画面
  2. Undo -> regrade モード
  3. quality 4 で再評価
- **期待結果**:
  - reconfirmQueue にカードが追加されない
  - 通常の完了画面に戻る (`復習完了!` が表示)
- **検証方法**: 完了テキストが正常表示されることで検証
- **要件参照**: REQ-404, TC-404-03

---

### 7. 統合テスト

**describe**: `統合テスト: 再確認ループフロー`

#### TC-TDD-INT-01: 通常カード 3 枚 + quality 0-2 が 1 枚 -> 再確認ループ -> 完了

- **ID**: TC-TDD-INT-01
- **テスト名**: `3枚中1枚がquality 0で評価され、再確認ループ後にセッションが完了する`
- **前提条件**: 3 枚のカード (mockDueCards 3 枚)
- **操作手順**:
  1. カード 1 を quality 0 で評価 -> reconfirmQueue: [card-1]
  2. カード 2 を quality 4 で評価 -> reconfirmQueue: [card-1] (変化なし)
  3. カード 3 を quality 5 で評価 -> 通常カード全消化、reconfirmQueue 非空 -> isReconfirmMode = true
  4. 再確認: card-1 で handleReconfirmRemembered -> reconfirmQueue: [] -> isComplete = true
  5. 完了画面表示
- **期待結果**:
  - `mockSubmitReview` が 3 回呼ばれる (card-1, card-2, card-3)
  - 完了画面に「3枚のカードを復習しました」と表示
  - card-1 の reviewResult.type が `'reconfirmed'`
  - card-1 の reviewResult.reconfirmResult が `'remembered'`
- **要件参照**: REQ-001 ~ 003, REQ-502

#### TC-TDD-INT-02: 全カード quality 0-2 -> 再確認ループで全て「覚えた」-> 完了

- **ID**: TC-TDD-INT-02
- **テスト名**: `全3枚がquality 0-2で評価され、全て再確認「覚えた」でセッションが完了する`
- **前提条件**: 3 枚のカード
- **操作手順**:
  1. カード 1 を quality 0 で評価
  2. カード 2 を quality 1 で評価
  3. カード 3 を quality 2 で評価 -> reconfirmQueue: [card-1, card-2, card-3]
  4. 再確認: card-1 「覚えた」-> reconfirmQueue: [card-2, card-3]
  5. 再確認: card-2 「覚えた」-> reconfirmQueue: [card-3]
  6. 再確認: card-3 「覚えた」-> reconfirmQueue: [] -> isComplete = true
- **期待結果**:
  - `mockSubmitReview` が 3 回呼ばれる
  - 完了画面に「3枚のカードを復習しました」と表示
  - 全カードの reviewResult.type が `'reconfirmed'`
- **要件参照**: EDGE-101

#### TC-TDD-INT-03: 「覚えていない」-> キュー末尾再追加 -> 「覚えた」-> 完了

- **ID**: TC-TDD-INT-03
- **テスト名**: `1枚のカードで「覚えていない」を2回選択後「覚えた」でセッションが完了する`
- **前提条件**: カード 1 枚のみ
- **操作手順**:
  1. カード 1 を quality 0 で評価 -> reconfirmQueue: [card-1]
  2. 再確認: card-1 「覚えていない」-> reconfirmQueue: [card-1]
  3. 再確認: card-1 「覚えていない」-> reconfirmQueue: [card-1]
  4. 再確認: card-1 「覚えた」-> reconfirmQueue: [] -> isComplete = true
- **期待結果**:
  - `mockSubmitReview` が 1 回のみ呼ばれる (最初の quality 0 評価時)
  - 再確認中は API 呼び出しなし
  - 完了画面が表示される
- **要件参照**: EDGE-102, REQ-402

#### TC-TDD-INT-04: Undo -> regrade quality 0-2 -> 再確認ループ -> 完了

- **ID**: TC-TDD-INT-04
- **テスト名**: `Undo後のregradeでquality 1を選択すると再確認キューに追加される`
- **前提条件**: カード 1 枚のみ
- **操作手順**:
  1. カード 1 を quality 4 で評価 -> isComplete = true, reconfirmQueue: []
  2. 完了画面で Undo -> regradeMode, reconfirmQueue: []
  3. regrade: quality 1 -> reconfirmQueue: [card-1], isComplete = true
- **期待結果**:
  - `mockUndoReview` が 1 回呼ばれる
  - `mockSubmitReview` が 2 回呼ばれる (初回 quality 4 + regrade quality 1)
  - reconfirmQueue にカードが追加される
- **要件参照**: REQ-404, EDGE-202

---

### 8. エッジケーステスト

**describe**: `エッジケース: 再確認ループ`

#### TC-TDD-EDGE-01: reconfirmQueue が空の時に handleReconfirmRemembered を呼んでも何も起きない

- **ID**: TC-TDD-EDGE-01
- **テスト名**: `再確認キューが空の時にhandleReconfirmRememberedを呼んでも状態が変化しない`
- **前提条件**: reconfirmQueue が空 (currentReconfirmCard === null)
- **操作手順**:
  1. handleReconfirmRemembered を呼び出す (キュー空の状態で)
- **期待結果**:
  - 状態が変化しない
  - エラーが発生しない
  - API が呼ばれない
- **検証方法**: 呼び出し前後で画面状態が変わらないことを確認
- **要件参照**: 防御的プログラミング

#### TC-TDD-EDGE-02: reconfirmQueue が空の時に handleReconfirmForgotten を呼んでも何も起きない

- **ID**: TC-TDD-EDGE-02
- **テスト名**: `再確認キューが空の時にhandleReconfirmForgottenを呼んでも状態が変化しない`
- **前提条件**: reconfirmQueue が空
- **操作手順**:
  1. handleReconfirmForgotten を呼び出す (キュー空の状態で)
- **期待結果**:
  - 状態が変化しない
  - エラーが発生しない
- **検証方法**: TC-TDD-EDGE-01 と同様
- **要件参照**: 防御的プログラミング

#### TC-TDD-EDGE-03: 複数カードが reconfirmQueue にある時の「覚えた」で先頭のみ除外

- **ID**: TC-TDD-EDGE-03
- **テスト名**: `再確認キューに複数カードがある時「覚えた」で先頭のみ除外される`
- **前提条件**: reconfirmQueue: [card-1, card-2, card-3] (3 枚全て quality 0-2 で評価済み)
- **操作手順**:
  1. 3 枚全てを quality 0-2 で評価
  2. 再確認モードに遷移
  3. handleReconfirmRemembered を呼び出す
- **期待結果**:
  - reconfirmQueue: [card-2, card-3] (card-1 のみ除外)
  - セッションは完了しない (残り 2 枚)
  - 次の再確認カードは card-2
- **検証方法**: card-1 の「覚えた」後にセッションが完了しないことで検証 (TC-TDD-INT-02 と組み合わせ可能)
- **要件参照**: REQ-003

#### TC-TDD-EDGE-04: Undo 対象カードが reconfirmQueue に存在しない場合

- **ID**: TC-TDD-EDGE-04
- **テスト名**: `quality 3-5で評価したカードのUndoで再確認キューのfilterが空振りしてもエラーが起きない`
- **前提条件**: quality 4 で評価したカードを Undo (reconfirmQueue に該当カードは元々ない)
- **操作手順**:
  1. カード 1 枚を quality 4 で評価
  2. 完了画面で Undo
- **期待結果**:
  - reconfirmQueue.filter は空振りするがエラーは発生しない
  - 既存 Undo フローが正常動作する (再採点モードに遷移)
- **検証方法**: 既存 Undo テストがパスすることで確認。追加エラーが発生しないことを検証。
- **要件参照**: REQ-404

---

## 9. 既存テスト互換性要件

以下の既存テストが引き続き全てパスしなければならない。

| テストケース | 概要 | 影響分析 |
|---|---|---|
| テストケース 1 | ローディング表示 | 影響なし |
| テストケース 2 | カード表示 | 影響なし |
| テストケース 3 | 空状態表示 | 影響なし |
| テストケース 4 | フリップ操作 | 影響なし |
| テストケース 5 | 採点送信 (quality 4) | quality 4 は reconfirmQueue に追加しない。既存動作維持 |
| テストケース 6 | スキップ | 影響なし。スキップ時は reconfirmQueue に追加しない |
| テストケース 7 | 復習完了 (quality 5, 1 枚) | quality 5 は reconfirmQueue に追加しない。既存動作維持 |
| テストケース 8 | API エラー (初期読み込み) | 影響なし |
| テストケース 9 | API エラー (採点送信) | 影響なし |
| テストケース 10 | 進捗バー更新 | quality 4 での進捗更新。影響なし |
| 統合テスト | 3 枚全評価 | quality 4, 5 のみで評価。reconfirmQueue は空のまま。既存動作維持 |
| エッジケース: 1 枚 | quality 3 で即完了 | quality 3 は reconfirmQueue に追加しない。既存動作維持 |
| エッジケース: 全スキップ | 全カードスキップ | 影響なし |
| Undo フロー: 正常系 | Undo + regrade (quality 5) | regrade quality 5 は reconfirmQueue に追加しない。handleUndo の filter は空振り |
| Undo フロー: エラー系 | Undo API エラー | 影響なし |

**結論**: 既存テストは全て quality 3-5 またはスキップを使用しているため、reconfirmQueue への追加は発生せず、既存動作に影響しない。

---

## テストケースサマリー

### 新規テストケース一覧

| ID | カテゴリ | テスト内容 | 要件参照 | describe ブロック |
|---|---|---|---|---|
| TC-TDD-020-01 | キュー追加 | quality 0 でキュー追加 | REQ-001, TC-001-01 | 再確認キュー追加: Normal mode |
| TC-TDD-020-02 | キュー追加 | quality 1 でキュー追加 | REQ-001, TC-001-02 | 再確認キュー追加: Normal mode |
| TC-TDD-020-03 | キュー追加 | quality 2 でキュー追加 | REQ-001, TC-001-03 | 再確認キュー追加: Normal mode |
| TC-TDD-020-04 | キュー非追加 | quality 3 でキュー非追加 | REQ-103, TC-001-B01 | 再確認キュー追加: Normal mode |
| TC-TDD-020-05 | キュー非追加 | quality 4 でキュー非追加 | REQ-103 | 再確認キュー追加: Normal mode |
| TC-TDD-020-06 | キュー非追加 | quality 5 でキュー非追加 | REQ-103 | 再確認キュー追加: Normal mode |
| TC-TDD-021-01 | Undo+regrade | regrade quality 0-2 でキュー追加 | REQ-404, TC-404-02 | 再確認キュー追加: Regrade mode |
| TC-TDD-021-02 | Undo+regrade | regrade quality 3+ でキュー非追加 | REQ-404, TC-404-03 | 再確認キュー追加: Regrade mode |
| TC-TDD-030-01 | 覚えた | キューから除外 + 完了 | REQ-003, TC-003-01 | handleReconfirmRemembered |
| TC-TDD-030-02 | 覚えた | API 呼び出しなし | REQ-003, TC-003-02 | handleReconfirmRemembered |
| TC-TDD-030-03 | 覚えた | type = 'reconfirmed' 更新 | REQ-003, REQ-501 | handleReconfirmRemembered |
| TC-TDD-030-04 | 覚えた | reconfirmResult = 'remembered' | REQ-003, REQ-501 | handleReconfirmRemembered |
| TC-TDD-040-01 | 覚えていない | キュー末尾に再追加 | REQ-004, TC-004-01 | handleReconfirmForgotten |
| TC-TDD-040-02 | 覚えていない | API 呼び出しなし | REQ-004, TC-004-02 | handleReconfirmForgotten |
| TC-TDD-040-03 | 覚えていない | 複数回ループ後に覚えた | REQ-004, TC-004-03 | handleReconfirmForgotten |
| TC-TDD-050-02 | moveToNext | reconfirmQueue 非空 -> 再確認モード | REQ-502 | moveToNext 拡張 |
| TC-TDD-050-04 | moveToNext | 再確認キュー消化後 -> 完了 | REQ-502 | moveToNext 拡張 |
| TC-TDD-060-01 | Undo 連携 | キューから除去 | REQ-404, TC-404-01 | handleUndo 拡張 |
| TC-TDD-060-02 | Undo 連携 | Undo -> regrade 0-2 -> 再追加 | REQ-404, TC-404-02 | handleUndo 拡張 |
| TC-TDD-060-03 | Undo 連携 | Undo -> regrade 3+ -> 非追加 | REQ-404, TC-404-03 | handleUndo 拡張 |
| TC-TDD-INT-01 | 統合 | 通常 3 枚 + 再確認 1 枚 | REQ-001~003, REQ-502 | 統合テスト |
| TC-TDD-INT-02 | 統合 | 全カード再確認 | EDGE-101 | 統合テスト |
| TC-TDD-INT-03 | 統合 | 覚えていない複数回 | EDGE-102, REQ-402 | 統合テスト |
| TC-TDD-INT-04 | 統合 | Undo -> regrade -> 再確認 | REQ-404, EDGE-202 | 統合テスト |
| TC-TDD-EDGE-01 | エッジ | 空キューで覚えた呼び出し | 防御的プログラミング | エッジケース |
| TC-TDD-EDGE-02 | エッジ | 空キューで覚えていない呼び出し | 防御的プログラミング | エッジケース |
| TC-TDD-EDGE-03 | エッジ | 複数カードキューで先頭のみ除外 | REQ-003 | エッジケース |
| TC-TDD-EDGE-04 | エッジ | quality 3-5 の Undo でキュー空振り | REQ-404 | エッジケース |

### カテゴリ別件数

| カテゴリ | 件数 |
|---|---|
| キュー追加 (Normal mode) | 6 |
| キュー追加 (Regrade mode) | 2 |
| 「覚えた」ハンドラ | 4 |
| 「覚えていない」ハンドラ | 3 |
| moveToNext 拡張 | 2 |
| Undo 連携 | 3 |
| 統合テスト | 4 |
| エッジケース | 4 |
| **合計** | **28** |

### テスト構造 (describe ブロック)

```
describe('ReviewPage')
  // ... 既存テスト (変更なし) ...

  // --- TASK-0081: 再確認ループ コアロジック ---

  describe('再確認キュー追加: Normal mode')
    it('quality 0 選択時に...')           // TC-TDD-020-01
    it('quality 1 選択時に...')           // TC-TDD-020-02
    it('quality 2 選択時に...')           // TC-TDD-020-03
    it('quality 3 選択時に...')           // TC-TDD-020-04
    it('quality 4 選択時に...')           // TC-TDD-020-05
    it('quality 5 選択時に...')           // TC-TDD-020-06

  describe('再確認キュー追加: Regrade mode')
    it('Undo後 regrade quality 2 ...')    // TC-TDD-021-01
    it('Undo後 regrade quality 4 ...')    // TC-TDD-021-02

  describe('handleReconfirmRemembered: 「覚えた」ハンドラ')
    it('キューから除外 + 完了')            // TC-TDD-030-01
    it('API 呼び出しなし')                 // TC-TDD-030-02
    it('type reconfirmed + remembered')   // TC-TDD-030-03, 030-04

  describe('handleReconfirmForgotten: 「覚えていない」ハンドラ')
    it('キュー末尾に再追加')               // TC-TDD-040-01
    it('API 呼び出しなし')                 // TC-TDD-040-02
    it('複数回ループ後に覚えた')           // TC-TDD-040-03

  describe('moveToNext 拡張')
    it('reconfirmQueue 非空 -> 再確認')    // TC-TDD-050-02
    it('再確認キュー消化後 -> 完了')       // TC-TDD-050-04

  describe('handleUndo 拡張: 再確認キュー連携')
    it('キューから除去')                   // TC-TDD-060-01
    it('regrade 0-2 -> 再追加')           // TC-TDD-060-02
    it('regrade 3+ -> 非追加')            // TC-TDD-060-03

  describe('統合テスト: 再確認ループフロー')
    it('3枚中1枚 quality 0 -> 再確認')    // TC-TDD-INT-01
    it('全カード quality 0-2 -> 再確認')   // TC-TDD-INT-02
    it('覚えていない複数回 -> 覚えた')     // TC-TDD-INT-03
    it('Undo -> regrade -> 再確認')       // TC-TDD-INT-04

  describe('エッジケース: 再確認ループ')
    it('空キューで覚えた呼び出し')         // TC-TDD-EDGE-01
    it('空キューで覚えていない呼び出し')   // TC-TDD-EDGE-02
    it('複数カードキュー先頭のみ除外')     // TC-TDD-EDGE-03
    it('quality 3-5 Undo でキュー空振り') // TC-TDD-EDGE-04
```

---

## 実装メモ

### 重複テストの統合候補

以下のテストケースはフロー上重複するため、実装時に統合を検討する:

- **TC-TDD-030-03 + TC-TDD-030-04**: reviewResults の type と reconfirmResult を同一テスト内で検証
- **TC-TDD-050-02 + TC-TDD-020-01**: moveToNext の再確認モード遷移は quality 0-2 でのキュー追加テストで間接検証済み
- **TC-TDD-050-04 + TC-TDD-030-01**: 再確認キュー消化後の完了は「覚えた」テストで間接検証済み
- **TC-TDD-060-02 + TC-TDD-021-01**: Undo 後 regrade でのキュー追加は同一シナリオ

### ハンドラ呼び出し方法の検討

`handleReconfirmRemembered` / `handleReconfirmForgotten` は TASK-0082 で UI ボタンが追加されるまで直接的な UI 操作でテストできない。tdd-red フェーズでは以下のいずれかの方法で対応する:

1. **ReviewPage が子コンポーネントに渡す props を spy**: ReviewPage の render 結果から GradeButtons 等に渡される props を検証
2. **テスト専用の公開方法**: ReviewPage に ref を通じて内部ハンドラを公開 (非推奨)
3. **状態変化の間接検証**: quality 0-2 で評価後の画面状態 (完了に遷移しないこと) で再確認キューの存在を推測的に検証

推奨は方法 1 または方法 3。tdd-red フェーズで具体的に決定する。

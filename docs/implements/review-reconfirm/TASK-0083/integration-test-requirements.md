# TASK-0083 TDD Requirements: 統合テスト・動作確認

**作成日**: 2026-02-28
**タスク**: TASK-0083
**タスクタイプ**: TDD
**テストファイル**: `frontend/src/pages/__tests__/ReviewPage.integration.test.tsx` (新規作成)

---

## 1. 機能の概要

### 1.1 何をする機能か 🔵

**信頼性**: 🔵 *TASK-0083.md、受け入れ基準、要件定義書より*

TASK-0081（コアロジック）と TASK-0082（UIコンポーネント）で実装された再確認ループ機能の **エンドツーエンド統合テスト** を実施する。個別のユニットテストでは検証しきれない、複数コンポーネント・複数ステップにまたがるフロー全体の整合性を検証する。

### 1.2 解決する問題 🔵

**信頼性**: 🔵 *TASK-0083.md より*

- TASK-0081 のコアロジックと TASK-0082 の UI コンポーネントが正しく連携していることの保証
- 既存の復習機能（quality 3-5 フロー、スキップ、Undo）に回帰がないことの保証
- エッジケース（全カード再確認、無限ループ、混在フロー）での安定動作の保証
- TypeScript 型チェックの通過保証

### 1.3 想定されるユーザー 🔵

**信頼性**: 🔵 *ユーザーストーリーより*

- 開発者（テスト実行・品質保証）
- CI/CD パイプライン（自動テスト実行）

### 1.4 システム内での位置づけ 🔵

**信頼性**: 🔵 *overview.md、architecture.md より*

review-reconfirm 機能の Phase 1 最終タスク。TASK-0081（コアロジック完了）→ TASK-0082（UI完了）→ **TASK-0083（統合テスト・最終検証）** という流れの最終ステップ。

- **参照した EARS 要件**: REQ-001〜005, REQ-101〜103, REQ-201〜203, REQ-401〜404, REQ-501〜502
- **参照した設計文書**: `docs/design/review-reconfirm/architecture.md`, `docs/design/review-reconfirm/dataflow.md`

---

## 2. テストスコープの定義

### 2.1 TASK-0081/0082 で既にカバー済みの範囲 🔵

**信頼性**: 🔵 *既存テスト実装より*

以下は `frontend/src/pages/__tests__/ReviewPage.test.tsx` で既にカバーされている:

| カテゴリ | テスト件数 | カバー範囲 |
|---------|----------|-----------|
| 型定義検証 | 3件 | ReconfirmCard, SessionCardResultType, SessionCardResult の型コンパイル確認 |
| キュー追加 Normal mode | 6件 | quality 0-5 の各ケースでのキュー追加/非追加判定 |
| キュー追加 Regrade mode | 2件 | Undo 後の再採点でのキュー追加/非追加判定 |
| handleReconfirmRemembered | 3件 | キュー除外、API 非呼び出し、reviewResults 更新 |
| handleReconfirmForgotten | 3件 | キュー末尾再追加、API 非呼び出し、複数回ループ |
| moveToNext 拡張 | 2件 | 再確認モード遷移、キュー消化後の完了 |
| handleUndo 拡張 | 3件 | キュー除去、regrade quality 0-2、regrade quality 3+ |
| 統合テスト（基本） | 4件 | 3枚中1枚再確認、全3枚再確認、覚えていないループ、Undo→regrade |
| エッジケース | 4件 | 空キュー安全性、先頭のみ除外、quality 3-5 Undo 空振り |

以下は `frontend/src/components/__tests__/` で既にカバーされている:
- `GradeButtons.test.tsx`: 通常モード 6 段階表示、再確認モード 2 択表示、コールバック呼び出し
- `ReconfirmBadge.test.tsx`: バッジ表示/非表示、スタイリング
- `ReviewComplete.test.tsx`: 再確認結果表示、通常結果表示
- `ReviewResultItem.test.tsx`: 再確認結果アイコン（覚えた✔）表示

### 2.2 TASK-0083 で新規にカバーする範囲 🔵

**信頼性**: 🔵 *TASK-0083.md 完了条件より*

TASK-0083 では、既存テストでは検証しきれない以下の **横断的な統合テスト** を新規追加する:

1. **UI を含む完全な E2E フローテスト**: ユーザーの実際の操作（クリック）を模擬し、画面表示の変化を最初から最後まで追跡するシナリオテスト
2. **複合エッジケーステスト**: 通常カードと再確認カードが混在する複雑なフロー
3. **Undo 統合テスト**: UI 操作を含む Undo → 再確認キュー除去 → regrade の完全フロー
4. **回帰テスト確認**: 既存テスト全通過、型チェック通過の最終確認

---

## 3. 入力・出力の仕様

### 3.1 テスト入力（テストデータ） 🔵

**信頼性**: 🔵 *既存テスト実装パターンより*

```typescript
// 基本テストデータ: 3枚のカード
const mockDueCards = [
  { card_id: 'card-1', front: '質問1', back: '解答1', overdue_days: 0 },
  { card_id: 'card-2', front: '質問2', back: '解答2', overdue_days: 1 },
  { card_id: 'card-3', front: '質問3', back: '解答3', overdue_days: 2 },
];

// 1枚のみのテストデータ
const singleCard = [
  { card_id: 'card-1', front: '質問1', back: '解答1', overdue_days: 0 },
];

// モック API レスポンス
const mockReviewResponse = (cardId: string, grade: number) => ({
  card_id: cardId,
  grade,
  previous: { ease_factor: 2.5, interval: 1, repetitions: 0, due_date: null },
  updated: { ease_factor: 2.6, interval: 1, repetitions: 1, due_date: '2026-03-01' },
  reviewed_at: '2026-02-28T10:00:00Z',
});

const mockUndoResponse = (cardId: string) => ({
  card_id: cardId,
  restored: { ease_factor: 2.5, interval: 1, repetitions: 0, due_date: '2026-02-28' },
  undone_at: '2026-02-28T10:01:00Z',
});
```

### 3.2 テスト出力（期待結果） 🔵

**信頼性**: 🔵 *受け入れ基準 TC-001〜004, EDGE-001/101/102, TC-404-01〜03 より*

| シナリオ | 期待される画面表示 | API 呼び出し回数 |
|---------|------------------|----------------|
| 通常→再確認→覚えた→完了 | 完了画面に遷移、「覚えた✔」表示 | submitReview: 3回、undoReview: 0回 |
| 全カード再確認→全覚えた | 完了画面、全カードに「覚えた✔」 | submitReview: 3回 |
| 覚えていないループ | ループ中は同一カード再表示 | submitReview: 1回（初回のみ） |
| Undo→regrade quality 0-2 | 再確認ループ再開 | submitReview: 2回、undoReview: 1回 |
| Undo→regrade quality 3+ | 通常完了 | submitReview: 2回、undoReview: 1回 |

- **参照した EARS 要件**: REQ-001, REQ-003, REQ-004, REQ-103, REQ-404
- **参照した設計文書**: `docs/design/review-reconfirm/dataflow.md`

---

## 4. 制約条件

### 4.1 テスト環境制約 🔵

**信頼性**: 🔵 *既存テスト構成より*

- **テストフレームワーク**: Vitest + React Testing Library + userEvent
- **レンダリング**: `MemoryRouter` でラップ（react-router-dom の依存）
- **API モック**: vi.mock でモジュールレベルモック（既存パターンを踏襲）
- **非同期処理**: `waitFor` + `userEvent.setup()` で非同期操作を待機

### 4.2 テストファイル配置制約 🟡

**信頼性**: 🟡 *既存ファイル構成からの妥当な推測*

- **新規テストファイル**: `frontend/src/pages/__tests__/ReviewPage.integration.test.tsx`
- **理由**: 既存の `ReviewPage.test.tsx` は既に大きく（約 1650 行）、統合テストを分離することで可読性と保守性を向上させる
- **代替案**: 既存ファイルに追記することも可能だが、テストの種類（ユニット vs 統合）を明確に分離する方が望ましい

### 4.3 テストカバレッジ制約 🔵

**信頼性**: 🔵 *CLAUDE.md より*

- **カバレッジ目標**: 80% 以上
- **型チェック**: `npm run type-check` (tsc --noEmit) で型エラーなし
- **全テスト通過**: `npm test` で既存テストを含む全テストが通過すること

### 4.4 API 呼び出し制約 🔵

**信頼性**: 🔵 *要件定義書 REQ-003, REQ-004, NFR-001 より*

- 再確認ハンドラ（覚えた/覚えていない）では **API 呼び出しが発生しない** ことをテストで検証する必要がある
- SM-2 API 呼び出しは最初の quality 0-2 評価時のみ

- **参照した EARS 要件**: REQ-003, REQ-004, REQ-401, REQ-403, NFR-001
- **参照した設計文書**: `docs/design/review-reconfirm/architecture.md` - 技術的制約

---

## 5. 統合テストケース定義

### 5.1 E2E フロー統合テスト（TC-INT）

#### TC-INT-001: 通常復習 → quality 0-2 → 再確認表示 → 覚えた → 完了（フルフロー） 🔵

**信頼性**: 🔵 *受け入れ基準 TC-001-01〜03, TC-002-01, TC-003-01, TC-101-01, TC-102-01, TC-501-01 より*

**目的**: TASK-0081 のコアロジックと TASK-0082 の UI が連携して動作することをフルフローで検証する

**前提条件**:
- 3枚のカードが存在

**操作手順**:
1. ReviewPage をレンダリング、カード1の表面「質問1」が表示されるまで待機
2. カード1をフリップ → quality 0 を選択 → SM-2 API 呼び出し確認
3. カード2をフリップ → quality 4 を選択 → SM-2 API 呼び出し確認
4. カード3をフリップ → quality 5 を選択 → SM-2 API 呼び出し確認
5. 再確認モードに遷移: 「再確認」バッジが表示されることを確認
6. カード1（再確認）の表面が表示されることを確認
7. カード1をフリップ → 「覚えた」「覚えていない」の 2 択が表示されることを確認
8. 通常の 6 段階評価ボタンが非表示であることを確認
9. スキップボタンが非表示であることを確認
10. 「覚えた」を選択
11. 完了画面に遷移: 「3枚のカードを復習しました」表示を確認
12. カード1の結果に元の評価と「覚えた✔」が表示されることを確認

**検証ポイント**:
- submitReview が 3 回のみ呼び出される（再確認中は API 呼び出しなし）
- 再確認バッジ表示（ReconfirmBadge の統合確認）
- 2 択ボタン表示（GradeButtons の再確認モード統合確認）
- 完了画面の再確認結果表示（ReviewComplete + ReviewResultItem の統合確認）

**テスト上の注意**:
- 再確認カード表示時のボタン: `screen.getByRole('button', { name: '覚えた' })`
- 再確認バッジ: `screen.getByText('再確認')` で確認

---

#### TC-INT-002: 通常復習 → quality 0-2 → 再確認 → 覚えていない → 覚えた → 完了 🔵

**信頼性**: 🔵 *受け入れ基準 TC-004-01〜03 より*

**目的**: 「覚えていない」→ キュー末尾再追加 → 再度表示 → 「覚えた」のフルフローを検証

**前提条件**:
- 1枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 0 を選択
2. 再確認モード: カード1の「再確認」バッジ付き表示を確認
3. カード1をフリップ → 「覚えていない」を選択
4. 再度カード1が表示されることを確認（「再確認」バッジ付き）
5. カード1をフリップ → 「覚えた」を選択
6. 完了画面に遷移

**検証ポイント**:
- submitReview が 1 回のみ（初回評価時のみ）
- 「覚えていない」後に同じカードが再表示される
- 2 回目の表示でも「再確認」バッジ + 2 択ボタンが正しく表示される

---

#### TC-INT-003: 通常カードと再確認カードの混在フロー 🟡

**信頼性**: 🟡 *REQ-502 から妥当な推測*

**目的**: 通常カードが残っている間は再確認カードが表示されず、通常カード全消化後に再確認カードが順番に表示されることを検証

**前提条件**:
- 3枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 1 を選択（再確認キューに追加）
2. カード2の表面が表示される（再確認カードではなく通常カード）
3. 「再確認」バッジが表示されていないことを確認
4. カード2をフリップ → quality 0 を選択（再確認キューに追加）
5. カード3の表面が表示される（通常カード）
6. 「再確認」バッジが表示されていないことを確認
7. カード3をフリップ → quality 4 を選択（通常完了、再確認キューに追加されない）
8. 再確認モードに遷移: カード1が表示される（FIFO順）
9. 「再確認」バッジが表示されることを確認
10. カード1をフリップ → 「覚えた」を選択
11. カード2が表示される（再確認カード）
12. カード2をフリップ → 「覚えた」を選択
13. 完了画面に遷移

**検証ポイント**:
- 通常カード消化中は再確認バッジが非表示
- 再確認キューは FIFO 順（card-1 → card-2）
- submitReview は 3 回のみ

---

### 5.2 エッジケーステスト（TC-EDGE）

#### TC-EDGE-001: 全カードが quality 0-2 → 全て再確認ループ → 全て覚えた → 完了 🟡

**信頼性**: 🟡 *受け入れ基準 EDGE-101 より、UI 統合の妥当な推測*

**目的**: 全カードが再確認キューに入り、再確認フェーズで全て「覚えた」で完了する E2E フロー

**前提条件**:
- 3枚のカードが存在

**操作手順**:
1. カード1〜3 を全て quality 0-2 で評価（各カードでフリップ → 評価）
2. 再確認モード: カード1（「再確認」バッジ）→ フリップ → 「覚えた」
3. カード2（「再確認」バッジ）→ フリップ → 「覚えた」
4. カード3（「再確認」バッジ）→ フリップ → 「覚えた」
5. 完了画面に遷移

**検証ポイント**:
- submitReview は 3 回のみ
- 全カードの結果に「覚えた✔」が表示される
- 「3枚のカードを復習しました」表示

---

#### TC-EDGE-002: 無限ループ（同一カードで「覚えていない」を複数回繰り返す） 🔵

**信頼性**: 🔵 *受け入れ基準 EDGE-102、REQ-402 より*

**目的**: 「覚えていない」を複数回選択してもアプリが正常に動作し続けることを検証

**前提条件**:
- 1枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 0 を選択
2. 再確認: カード1をフリップ → 「覚えていない」（1回目）
3. 再確認: カード1をフリップ → 「覚えていない」（2回目）
4. 再確認: カード1をフリップ → 「覚えていない」（3回目）
5. 再確認: カード1をフリップ → 「覚えた」（4回目の表示）
6. 完了画面に遷移

**検証ポイント**:
- 4回目の表示でも「再確認」バッジ + 2 択ボタンが正常に表示される
- submitReview は 1 回のみ
- エラーやクラッシュが発生しない
- 最終的に完了画面に正しく遷移する

---

#### TC-EDGE-003: 複数カードの再確認キューで「覚えていない」が混在するフロー 🟡

**信頼性**: 🟡 *EDGE-101, EDGE-102 の組み合わせから妥当な推測*

**目的**: 複数カードが再確認キューにある状態で、一部を「覚えていない」、一部を「覚えた」とする混在フローの検証

**前提条件**:
- 2枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 0 を選択（再確認キュー: [card-1]）
2. カード2をフリップ → quality 1 を選択（再確認キュー: [card-1, card-2]）
3. 再確認: カード1をフリップ → 「覚えていない」（キュー: [card-2, card-1]）
4. 再確認: カード2をフリップ → 「覚えた」（キュー: [card-1]）
5. 再確認: カード1をフリップ → 「覚えた」（キュー: []）
6. 完了画面に遷移

**検証ポイント**:
- 「覚えていない」のカードが後ろに回り、別のカードが先に表示される
- キューの FIFO 順序が正しく維持される
- submitReview は 2 回のみ

---

### 5.3 Undo 統合テスト（TC-UNDO）

#### TC-UNDO-001: quality 0-2 評価 → 完了 → Undo → regrade quality 3+ → 通常完了 🔵

**信頼性**: 🔵 *受け入れ基準 TC-404-01, TC-404-03 より*

**目的**: quality 0-2 で再確認キューに入ったカードを Undo し、quality 3+ で再評価して再確認キューから除去されることを検証

**前提条件**:
- 1枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 0 を選択
2. 再確認: カード1をフリップ → 「覚えた」を選択
3. 完了画面に遷移
4. 完了画面で「取り消し」ボタンをクリック → Undo API 呼び出し
5. 再採点モード: カード1が表示される
6. カード1をフリップ → quality 4 を選択
7. 完了画面に戻る

**検証ポイント**:
- undoReview API が 1 回呼び出される
- submitReview が 2 回呼び出される（初回 quality 0 + regrade quality 4）
- 再評価後に再確認ループに入らない（直接完了画面）
- 完了画面のカード1の結果が通常の graded 表示（「覚えた✔」なし）

---

#### TC-UNDO-002: quality 0-2 評価 → 完了 → Undo → regrade quality 0-2 → 再確認ループ → 覚えた → 完了 🟡

**信頼性**: 🟡 *受け入れ基準 TC-404-02 より、UI フロー全体は妥当な推測*

**目的**: Undo 後の再評価で再び quality 0-2 を選択した場合、再確認ループに再度入ることを検証

**前提条件**:
- 1枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 4 を選択
2. 完了画面に遷移
3. 完了画面で「取り消し」ボタンをクリック → Undo API 呼び出し
4. 再採点モード: カード1が表示される
5. カード1をフリップ → quality 2 を選択 → submitReview API 呼び出し
6. 再確認キューにカード1が追加される
7. 完了画面 → 再確認ループ: カード1が「再確認」バッジ付きで表示される
8. カード1をフリップ → 「覚えた」を選択
9. 完了画面に遷移

**検証ポイント**:
- undoReview API が 1 回呼び出される
- submitReview が 2 回呼び出される（初回 quality 4 + regrade quality 2）
- regrade 後に再確認ループが発生する
- 最終的に完了画面で「覚えた✔」が表示される

**テスト上の注意**:
- regrade 後の moveToNext で isComplete = true になるが、reconfirmQueue が非空なので再確認ループに自動遷移するかの挙動を確認する必要がある
- 既存実装では regradeMode の場合 moveToNext は即 isComplete = true にする設計。reconfirmQueue に追加されたカードは完了画面から再確認に遷移するフローではなく、次回のセッション開始時に再確認キューが処理される可能性がある
- **実装の確認が必要**: regrade 後に reconfirmQueue が非空の場合の moveToNext の挙動

---

#### TC-UNDO-003: 複数カード中の 1 枚を Undo → regrade → 他の再確認カードへの影響なし 🟡

**信頼性**: 🟡 *REQ-404、EDGE-201 から妥当な推測*

**目的**: 複数カードがある場合に、1 枚の Undo が他のカードの再確認状態に影響しないことを検証

**前提条件**:
- 3枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 0 を選択（再確認キュー: [card-1]）
2. カード2をフリップ → quality 4 を選択
3. カード3をフリップ → quality 1 を選択（再確認キュー: [card-1, card-3]）
4. 再確認: カード1をフリップ → 「覚えた」（再確認キュー: [card-3]）
5. 再確認: カード3をフリップ → 「覚えた」（再確認キュー: []）
6. 完了画面に遷移
7. カード1の「取り消し」ボタンをクリック → Undo API
8. 再採点モード: カード1をフリップ → quality 5 を選択
9. 完了画面に戻る

**検証ポイント**:
- カード3の結果は「覚えた✔」のまま変わらない
- カード1のみが regrade される
- reconfirmQueue から card-1 のみが除去され、card-3 に影響しない

---

### 5.4 回帰テスト（TC-REG）

#### TC-REG-001: quality 3-5 のみのフローが変更なく動作する 🟡

**信頼性**: 🟡 *既存テスト維持の妥当な推測*

**目的**: 再確認機能追加後も、quality 3-5 で評価した場合の従来フローに変更がないことを検証

**前提条件**:
- 3枚のカードが存在

**操作手順**:
1. カード1〜3 を全て quality 4 で評価
2. 完了画面に遷移

**検証ポイント**:
- 「再確認」バッジが一度も表示されない
- 「覚えた」「覚えていない」ボタンが表示されない
- 通常の 6 段階評価が全カードで表示される
- submitReview が 3 回呼び出される
- 完了画面に「3枚のカードを復習しました」表示

---

#### TC-REG-002: スキップフローが変更なく動作する 🟡

**信頼性**: 🟡 *既存テスト維持の妥当な推測*

**目的**: スキップ操作が再確認機能の影響を受けないことを検証

**前提条件**:
- 3枚のカードが存在

**操作手順**:
1. カード1をフリップ → スキップ
2. カード2をフリップ → スキップ
3. カード3をフリップ → スキップ
4. 完了画面に遷移

**検証ポイント**:
- submitReview が呼び出されない
- 再確認キューにカードが追加されない
- 完了画面に「0枚のカードを復習しました」表示

---

#### TC-REG-003: quality 0-2 + スキップの混在フロー 🟡

**信頼性**: 🟡 *REQ-001, REQ-103 から妥当な推測*

**目的**: quality 0-2 とスキップが混在する場合の動作を検証

**前提条件**:
- 3枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 1 を選択（再確認キュー: [card-1]）
2. カード2をフリップ → スキップ（再確認キューに追加されない）
3. カード3をフリップ → スキップ
4. 再確認モード: カード1が表示される
5. カード1をフリップ → 「覚えた」を選択
6. 完了画面に遷移

**検証ポイント**:
- submitReview が 1 回呼び出される（カード1の quality 1 のみ）
- スキップされたカードは再確認キューに入らない
- 完了画面に「1枚のカードを復習しました」表示

---

#### TC-REG-004: TypeScript 型チェック通過 🔵

**信頼性**: 🔵 *CLAUDE.md テストカバレッジ要件より*

**目的**: 再確認機能追加後の TypeScript strict mode での型エラーがないことを確認

**実行コマンド**: `npm run type-check`

**検証ポイント**:
- tsc --noEmit が exit code 0 で完了する
- 型エラーが 0 件

---

#### TC-REG-005: 全テスト通過 🔵

**信頼性**: 🔵 *CLAUDE.md テスト要件より*

**目的**: 既存テストを含む全フロントエンドテストが通過することを確認

**実行コマンド**: `cd frontend && npm test`

**検証ポイント**:
- 全テストスイートが passed
- 失敗テストが 0 件

---

## 6. EARS 要件・設計文書との対応関係

### 参照した要件

- **ユーザストーリー**: ストーリー1.1（想起失敗カードの再確認）、ストーリー1.2（セッション内学習完結）
- **機能要件**: REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-101, REQ-102, REQ-103, REQ-201, REQ-202, REQ-203, REQ-401, REQ-402, REQ-403, REQ-404, REQ-501, REQ-502
- **非機能要件**: NFR-001, NFR-002
- **Edge ケース**: EDGE-001, EDGE-101, EDGE-102, EDGE-201, EDGE-202, EDGE-203
- **受け入れ基準**: TC-001-01〜03, TC-002-01〜02, TC-003-01〜02, TC-004-01〜03, TC-101-01〜02, TC-102-01, TC-404-01〜03, TC-501-01〜02, TC-EDGE-001-01, TC-EDGE-101-01, TC-EDGE-102-01

### 参照した設計文書

- **アーキテクチャ**: `docs/design/review-reconfirm/architecture.md` - コンポーネント構成、状態管理設計、Undo 連携設計
- **データフロー**: `docs/design/review-reconfirm/dataflow.md` - 全体フロー、通常評価フロー、再確認フロー、moveToNext フロー、Undo 連携フロー
- **型定義**: `frontend/src/types/card.ts` - SessionCardResultType, SessionCardResult, ReconfirmCard
- **実装コード**: `frontend/src/pages/ReviewPage.tsx` - 状態管理、ハンドラ実装
- **UI コンポーネント**: `frontend/src/components/GradeButtons.tsx`, `frontend/src/components/ReconfirmBadge.tsx`, `frontend/src/components/ReviewComplete.tsx`, `frontend/src/components/ReviewResultItem.tsx`

---

## 7. テストケースサマリー

### 新規テストケース一覧

| ID | カテゴリ | テスト内容 | 要件参照 | 信頼性 |
|---|---|---|---|---|
| TC-INT-001 | E2E フロー | 通常→再確認→覚えた→完了（フルフロー） | REQ-001〜003, TC-001〜003, TC-101, TC-102, TC-501 | 🔵 |
| TC-INT-002 | E2E フロー | 通常→再確認→覚えていない→覚えた→完了 | REQ-004, TC-004-01〜03 | 🔵 |
| TC-INT-003 | E2E フロー | 通常カードと再確認カードの混在フロー | REQ-502 | 🟡 |
| TC-EDGE-001 | エッジケース | 全カード quality 0-2 → 全再確認 → 全覚えた | EDGE-101 | 🟡 |
| TC-EDGE-002 | エッジケース | 無限ループ（覚えていない 3 回 → 覚えた） | EDGE-102, REQ-402 | 🔵 |
| TC-EDGE-003 | エッジケース | 複数カード混在（覚えた + 覚えていない） | EDGE-101, EDGE-102 | 🟡 |
| TC-UNDO-001 | Undo 統合 | Undo → regrade quality 3+ → 通常完了 | TC-404-01, TC-404-03, EDGE-201 | 🔵 |
| TC-UNDO-002 | Undo 統合 | Undo → regrade quality 0-2 → 再確認ループ | TC-404-02, EDGE-202 | 🟡 |
| TC-UNDO-003 | Undo 統合 | 複数カードの Undo で他カードに影響なし | REQ-404, EDGE-201 | 🟡 |
| TC-REG-001 | 回帰テスト | quality 3-5 のみのフロー（変更なし） | REQ-103 | 🟡 |
| TC-REG-002 | 回帰テスト | スキップフロー（変更なし） | 既存機能 | 🟡 |
| TC-REG-003 | 回帰テスト | quality 0-2 + スキップ混在 | REQ-001, REQ-103 | 🟡 |
| TC-REG-004 | 回帰テスト | TypeScript 型チェック通過 | CLAUDE.md | 🔵 |
| TC-REG-005 | 回帰テスト | 全テスト通過 | CLAUDE.md | 🔵 |

### カテゴリ別件数

| カテゴリ | 件数 |
|---------|------|
| E2E フロー統合テスト | 3件 |
| エッジケーステスト | 3件 |
| Undo 統合テスト | 3件 |
| 回帰テスト | 5件 |
| **合計** | **14件** |

### 信頼性レベル分布

- 🔵 青信号: 6件 (43%)
- 🟡 黄信号: 8件 (57%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質（赤信号なし、黄信号は既存パターンからの妥当な推測のみ）

---

## 8. テスト実装上の注意点

### 8.1 ヘルパー関数の共通化 🟡

**信頼性**: 🟡 *テスト実装効率化の妥当な推測*

統合テストでは複数カードの評価操作を繰り返すため、以下のヘルパー関数を作成する:

```typescript
/**
 * カードをフリップして指定の quality で評価する
 */
const flipAndGrade = async (user: UserEvent, grade: number) => {
  const card = screen.getByRole('button', { name: /カード(表面|裏面)を表示中/ });
  if (card.getAttribute('aria-label')?.includes('表面')) {
    await user.click(card);
  }
  const gradeButton = screen.getByLabelText(new RegExp(`^${grade} -`));
  await user.click(gradeButton);
};

/**
 * 再確認カードをフリップして「覚えた」を選択する
 */
const flipAndRemember = async (user: UserEvent) => {
  const card = screen.getByRole('button', { name: /カード(表面|裏面)を表示中/ });
  if (card.getAttribute('aria-label')?.includes('表面')) {
    await user.click(card);
  }
  const rememberedButton = screen.getByRole('button', { name: '覚えた' });
  await user.click(rememberedButton);
};

/**
 * 再確認カードをフリップして「覚えていない」を選択する
 */
const flipAndForget = async (user: UserEvent) => {
  const card = screen.getByRole('button', { name: /カード(表面|裏面)を表示中/ });
  if (card.getAttribute('aria-label')?.includes('表面')) {
    await user.click(card);
  }
  const forgottenButton = screen.getByRole('button', { name: '覚えていない' });
  await user.click(forgottenButton);
};
```

### 8.2 非同期処理の待機パターン 🔵

**信頼性**: 🔵 *既存テスト実装パターンより*

```typescript
// API 呼び出し後の状態更新を待機
await waitFor(() => {
  expect(screen.getByText('質問2')).toBeInTheDocument();
});

// 再確認モード遷移の待機
await waitFor(() => {
  expect(screen.getByText('再確認')).toBeInTheDocument();
});

// 完了画面遷移の待機
await waitFor(() => {
  expect(screen.getByText(/枚のカードを復習しました/)).toBeInTheDocument();
});
```

### 8.3 モック構成 🔵

**信頼性**: 🔵 *既存テスト実装パターンより*

既存のモック構成をそのまま再利用する。新規モックの追加は不要。

```typescript
vi.mock('react-router-dom', async () => { /* 既存パターン */ });
vi.mock('@/services/api', () => { /* 既存パターン */ });
```

### 8.4 回帰テストの実行方法 🔵

**信頼性**: 🔵 *CLAUDE.md より*

```bash
# 全テスト実行
cd frontend && npm test

# TypeScript 型チェック
cd frontend && npm run type-check
```

---

## 9. 完了条件チェックリスト

- [ ] TC-INT-001〜003: E2E フロー統合テストが通る
- [ ] TC-EDGE-001〜003: エッジケーステストが通る
- [ ] TC-UNDO-001〜003: Undo 統合テストが通る
- [ ] TC-REG-001〜003: 回帰テスト（フロー別）が通る
- [ ] TC-REG-004: `npm run type-check` で型エラーなし
- [ ] TC-REG-005: `npm test` で全テスト通過（既存 + 新規）
- [ ] TASK-0083.md の完了条件チェックボックスを `[x]` に更新
- [ ] overview.md の TASK-0083 状態列を更新

---

## 10. 実装除外事項

以下は TASK-0083 のスコープ外とする:

- **手動テスト**: ローカル環境での手動操作テストは開発者が任意で実施。本タスクは自動テストの追加に集中する
- **E2E テスト（Playwright 等）**: ブラウザベースの E2E テストは現在のプロジェクトスコープ外。React Testing Library による統合テストで代替する
- **パフォーマンステスト**: NFR-001, NFR-002 のパフォーマンス要件は自動テストでの定量的検証が困難なため、手動確認に委ねる
- **セッション中断テスト（EDGE-001）**: アプリ終了 → 翌日の再表示はフロントエンドの自動テストで検証困難なため、手動確認に委ねる（SM-2 が interval=1 を設定済みのため理論的に保証）

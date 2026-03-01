# TASK-0083 TDD Requirements: 統合テスト・動作確認

**作成日**: 2026-02-28
**タスク**: TASK-0083
**タスクタイプ**: TDD
**フェーズ**: Phase 1 - review-reconfirm 実装（最終タスク）
**推定工数**: 2時間
**テストファイル**: `frontend/src/pages/__tests__/ReviewPage.integration.test.tsx` (新規作成)

---

## 1. 機能の概要（EARS要件定義書・設計文書ベース）

### 1.1 何をする機能か 🔵

**信頼性**: 🔵 *TASK-0083.md 完了条件、受け入れ基準 TC-001〜004, EDGE-001/101/102, TC-404-01〜03 より*

TASK-0081（コアロジック: 型定義拡張 + ReviewPage 状態管理 + ハンドラ実装）と TASK-0082（UIコンポーネント: GradeButtons 2択対応 + ReconfirmBadge + ReviewComplete/ReviewResultItem 拡張）で実装された再確認ループ機能の **エンドツーエンド統合テスト** を実施する。

個別のユニットテスト（TASK-0081: 26件, TASK-0082: 各コンポーネントテスト）では検証しきれない、以下の横断的テストを新規追加する:

1. **UI を含む完全な E2E フローテスト**: ユーザーの実際の操作（フリップ → 評価 → 再確認 → 覚えた/覚えていない → 完了）を模擬し、画面表示の変化を最初から最後まで追跡するシナリオテスト
2. **複合エッジケーステスト**: 全カード再確認、無限ループ、通常カードと再確認カードの混在フロー
3. **Undo 統合テスト**: UI 操作を含む Undo → 再確認キュー除去 → regrade の完全フロー
4. **回帰テスト確認**: 既存テスト全通過、TypeScript 型チェック通過

### 1.2 どのような問題を解決するか 🔵

**信頼性**: 🔵 *TASK-0083.md タスク概要より*

- TASK-0081 のコアロジックと TASK-0082 の UI コンポーネントが正しく連携していることの保証
- 既存の復習機能（quality 3-5 フロー、スキップ、Undo）に回帰がないことの保証
- エッジケース（全カード再確認、無限ループ、混在フロー）での安定動作の保証
- TypeScript strict mode での型チェック通過保証

### 1.3 想定されるユーザー 🔵

**信頼性**: 🔵 *ユーザーストーリーより*

- 開発者（テスト実行・品質保証）
- CI/CD パイプライン（自動テスト実行）

### 1.4 システム内での位置づけ 🔵

**信頼性**: 🔵 *overview.md タスク依存関係、architecture.md スコープより*

review-reconfirm 機能の Phase 1 最終タスク。TASK-0081（コアロジック完了）→ TASK-0082（UI完了）→ **TASK-0083（統合テスト・最終検証）** という流れの最終ステップ。このタスク完了により Phase 1 が完了する。

- **参照した EARS 要件**: REQ-001〜005, REQ-101〜103, REQ-201〜203, REQ-401〜404, REQ-501〜502
- **参照した設計文書**: `docs/design/review-reconfirm/architecture.md` - システム概要, `docs/design/review-reconfirm/dataflow.md` - 全体フロー

---

## 2. TASK-0081/0082 で既にカバー済みの範囲

### 2.1 ReviewPage.test.tsx（TASK-0081）で既にカバー済み 🔵

**信頼性**: 🔵 *既存テスト実装より確認*

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

### 2.2 コンポーネントテスト（TASK-0082）で既にカバー済み 🔵

**信頼性**: 🔵 *既存テスト実装より確認*

| ファイル | テスト件数 | カバー範囲 |
|---------|----------|-----------|
| `GradeButtons.test.tsx` | 11件 | 通常モード 6 段階表示、再確認モード 2 択表示、コールバック呼び出し、disabled 状態、44px タップ領域 |
| `ReconfirmBadge.test.tsx` | 5件 | 「再確認」テキスト表示、背景色/テキスト色/形状スタイリング |
| `ReviewComplete.test.tsx` | 6件 | 再確認カウント計上、graded + reconfirmed 混在表示、全カード reconfirmed |
| `ReviewResultItem.test.tsx` | - | 再確認結果アイコン（覚えた✔）表示 |

### 2.3 TASK-0083 で新規にカバーする範囲 🔵

**信頼性**: 🔵 *TASK-0083.md 完了条件より*

既存テストは個別のロジック・コンポーネント単位のテストであるため、以下の **横断的な統合テスト** を新規追加する:

1. **UI を含む E2E フローテスト**: 再確認バッジ表示 + 2択ボタン表示 + フリップ操作 + 完了画面表示を一連のシナリオとして検証
2. **複合エッジケーステスト**: 通常カードと再確認カードが混在する複雑なフロー、複数カードでの「覚えていない」混在
3. **Undo 統合テスト**: UI 操作を含む Undo → 再確認キュー除去 → regrade → 完了の完全フロー
4. **回帰テスト確認**: 既存テスト全通過、TypeScript 型チェック通過の最終確認

---

## 3. 入力・出力の仕様（EARS機能要件・TypeScript型定義ベース）

### 3.1 テスト入力（テストデータ） 🔵

**信頼性**: 🔵 *既存テスト実装パターン（ReviewPage.test.tsx 32-36行目）より*

```typescript
// 基本テストデータ: 3枚のカード（既存モックデータと同一）
const mockDueCards = [
  { card_id: 'card-1', front: '質問1', back: '解答1', overdue_days: 0 },
  { card_id: 'card-2', front: '質問2', back: '解答2', overdue_days: 1 },
  { card_id: 'card-3', front: '質問3', back: '解答3', overdue_days: 2 },
];

// 1枚のみのテストデータ
const singleCardData = {
  due_cards: [mockDueCards[0]],
  total_due_count: 1,
  next_due_date: null,
};

// 2枚のテストデータ
const twoCardData = {
  due_cards: [mockDueCards[0], mockDueCards[1]],
  total_due_count: 2,
  next_due_date: null,
};

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
| 通常→再確認→覚えた→完了 | 完了画面に遷移、「覚えた✔」表示、「再確認」バッジ表示あり | submitReview: 3回、undoReview: 0回 |
| 全カード再確認→全覚えた | 完了画面、全カードに「覚えた✔」 | submitReview: 3回 |
| 覚えていないループ→覚えた | ループ中は同一カード再表示、最終的に完了画面 | submitReview: 1回（初回のみ） |
| 混在フロー（覚えた+覚えていない） | キュー FIFO 順序維持、最終的に完了画面 | submitReview: カード枚数分 |
| Undo→regrade quality 3+ | 通常完了（再確認ループなし） | submitReview: 2回、undoReview: 1回 |
| Undo→regrade quality 0-2 | 再確認ループ再開 | submitReview: 2回、undoReview: 1回 |
| quality 3-5 のみ（回帰テスト） | 従来通り完了画面（再確認バッジなし） | submitReview: カード枚数分 |
| スキップのみ（回帰テスト） | 完了画面（0枚復習） | submitReview: 0回 |

### 3.3 UI 要素の識別方法 🔵

**信頼性**: 🔵 *既存テスト実装パターンより*

```typescript
// カードフリップ操作
screen.getByRole('button', { name: /カード表面を表示中/ })  // 表面クリックでフリップ

// 通常モード: 6段階評価ボタン
screen.getByLabelText('0 - 全く覚えていない')
screen.getByLabelText('1 - 間違えた')
screen.getByLabelText('2 - 間違えたが見覚えあり')
screen.getByLabelText('3 - 難しかったが正解')
screen.getByLabelText('4 - やや迷ったが正解')
screen.getByLabelText('5 - 完璧')

// 再確認モード: 2択ボタン
screen.getByRole('button', { name: '覚えた' })
screen.getByRole('button', { name: '覚えていない' })

// 再確認バッジ
screen.getByText('再確認')

// スキップ
screen.getByLabelText('スキップ')

// 完了画面
screen.getByText('復習完了!')
screen.getByText('3枚のカードを復習しました')

// Undo
screen.getByLabelText('質問1 の採点を取り消す')

// 再採点モード
screen.getByText('再採点')
```

- **参照した EARS 要件**: REQ-001〜005, REQ-101, REQ-102, REQ-501
- **参照した設計文書**: `frontend/src/types/card.ts` - SessionCardResult, ReconfirmCard

---

## 4. 制約条件（EARS非機能要件・アーキテクチャ設計ベース）

### 4.1 テスト環境制約 🔵

**信頼性**: 🔵 *既存テスト構成（ReviewPage.test.tsx 1-6行目）より*

- **テストフレームワーク**: Vitest + React Testing Library + userEvent
- **レンダリング**: `MemoryRouter` でラップ（react-router-dom の依存）
- **API モック**: `vi.mock` でモジュールレベルモック（既存パターン踏襲）
- **非同期処理**: `waitFor` + `userEvent.setup()` で非同期操作を待機

### 4.2 テストファイル配置 🟡

**信頼性**: 🟡 *既存ファイル構成からの妥当な推測*

- **新規テストファイル**: `frontend/src/pages/__tests__/ReviewPage.integration.test.tsx`
- **理由**: 既存の `ReviewPage.test.tsx` は既に大きく（約 1650 行）、統合テストを分離することで可読性と保守性を向上させる
- **代替案**: 既存ファイルに追記も可能だが、テストの種類（ユニット vs 統合）を明確に分離する方が保守しやすい

### 4.3 テストカバレッジ制約 🔵

**信頼性**: 🔵 *CLAUDE.md テスト要件より*

- **カバレッジ目標**: 80% 以上
- **型チェック**: `npm run type-check` (tsc --noEmit) で型エラーなし
- **全テスト通過**: `npm test` で既存テストを含む全テストが通過すること

### 4.4 API 呼び出し制約 🔵

**信頼性**: 🔵 *要件定義書 REQ-003, REQ-004, NFR-001 より*

- 再確認ハンドラ（覚えた/覚えていない）では **API 呼び出しが発生しない** ことを各テストで検証
- SM-2 API 呼び出しは最初の quality 0-2 評価時のみ
- submitReview の呼び出し回数を各テストケースで厳密に検証する

### 4.5 既存テストとの共存制約 🔵

**信頼性**: 🔵 *既存テスト実装より*

- 既存の `ReviewPage.test.tsx` に含まれる統合テスト（TC-TDD-INT-01〜04, TC-TDD-EDGE-01〜04）は削除しない
- 新規テストファイルは既存テストと独立して実行可能であること
- モック設定パターンは既存テストと同一にする（`vi.mock` のパス、モック関数名）

- **参照した EARS 要件**: REQ-003, REQ-004, REQ-401, REQ-403, NFR-001
- **参照した設計文書**: `docs/design/review-reconfirm/architecture.md` - 技術的制約

---

## 5. 統合テストケース定義

### 5.1 E2E フロー統合テスト（TC-INT）

#### TC-INT-001: 通常復習 → quality 0-2 → 再確認バッジ + 2択表示 → 覚えた → 完了画面表示（フルフロー） 🔵

**信頼性**: 🔵 *受け入れ基準 TC-001-01〜03, TC-002-01, TC-003-01〜02, TC-101-01, TC-102-01, TC-501-01 より*

**目的**: TASK-0081 のコアロジックと TASK-0082 の UI（ReconfirmBadge, GradeButtons 2択, ReviewComplete, ReviewResultItem）が連携して動作することをフルフローで検証する

**前提条件**:
- 3枚のカードが存在（mockDueCards）

**操作手順**:
1. ReviewPage をレンダリング、カード1の表面「質問1」が表示されるまで待機
2. カード1をフリップ → quality 0 を選択 → `submitReview('card-1', 0)` が呼ばれることを確認
3. カード2が表示される → 「再確認」バッジが表示されていないことを確認
4. カード2をフリップ → quality 4 を選択 → `submitReview('card-2', 4)` が呼ばれることを確認
5. カード3が表示される → カード3をフリップ → quality 5 を選択
6. 再確認モードに遷移:
   - 「再確認」バッジ（`screen.getByText('再確認')`）が表示されることを確認
   - カード1の表面「質問1」が表示されることを確認
7. カード1をフリップ → 裏面「解答1」が表示される
8. 「覚えた」「覚えていない」の 2 択ボタンが表示されることを確認
9. 通常の 6 段階評価ボタン（0-5）が非表示であることを確認
10. スキップボタンが非表示であることを確認
11. 「覚えた」を選択
12. 完了画面に遷移: 「復習完了!」「3枚のカードを復習しました」が表示されることを確認

**検証ポイント**:
- `mockSubmitReview` が 3 回のみ呼び出される（再確認中は API 呼び出しなし）
- 再確認バッジ表示が正しい（ReconfirmBadge の統合確認）
- 2 択ボタンが再確認モードで正しく表示される（GradeButtons の再確認モード統合確認）
- 通常カード表示中に再確認バッジが表示されないこと

---

#### TC-INT-002: 通常復習 → quality 0-2 → 再確認 → 覚えていない → 再表示 → 覚えた → 完了 🔵

**信頼性**: 🔵 *受け入れ基準 TC-004-01〜03 より*

**目的**: 「覚えていない」→ キュー末尾再追加 → 再度表示 → 「覚えた」のフルフローを UI 操作含めて検証

**前提条件**:
- 1枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 0 を選択
2. 再確認モード: 「再確認」バッジが表示されることを確認
3. カード1をフリップ → 「覚えていない」を選択
4. 再度カード1が表示されることを確認（「再確認」バッジ付き）
5. カード1をフリップ → 「覚えた」を選択
6. 完了画面に遷移

**検証ポイント**:
- `mockSubmitReview` が 1 回のみ（初回評価時のみ）
- 「覚えていない」後に同じカードが再表示される（「質問1」が再表示）
- 2 回目の表示でも「再確認」バッジ + 2 択ボタンが正しく表示される
- 最終的に完了画面に正しく遷移する

---

#### TC-INT-003: 通常カードと再確認カードの混在フロー（FIFO順序確認） 🟡

**信頼性**: 🟡 *REQ-502（通常カードと再確認カードは同一キューで順番に流れる）から妥当な推測*

**目的**: 通常カードが残っている間は再確認カードが表示されず、通常カード全消化後に再確認カードが FIFO 順で表示されることを検証

**前提条件**:
- 3枚のカードが存在（mockDueCards）

**操作手順**:
1. カード1をフリップ → quality 1 を選択（再確認キュー: [card-1]）
2. カード2が表示される → 「再確認」バッジが表示されていないことを確認
3. カード2をフリップ → quality 0 を選択（再確認キュー: [card-1, card-2]）
4. カード3が表示される → 「再確認」バッジが表示されていないことを確認
5. カード3をフリップ → quality 4 を選択（通常完了、再確認キューに追加されない）
6. 再確認モード遷移: カード1（「質問1」）が表示される（FIFO 先頭）
7. 「再確認」バッジが表示されることを確認
8. カード1をフリップ → 「覚えた」を選択
9. カード2（「質問2」）が表示される（FIFO 2番目）
10. 「再確認」バッジが表示されることを確認
11. カード2をフリップ → 「覚えた」を選択
12. 完了画面に遷移

**検証ポイント**:
- 通常カード消化中は「再確認」バッジが非表示
- 再確認キューは FIFO 順（card-1 → card-2）
- `mockSubmitReview` は 3 回のみ
- 完了画面に「3枚のカードを復習しました」表示

---

### 5.2 エッジケーステスト（TC-EDGE）

#### TC-EDGE-001: 全カードが quality 0-2 → 全て再確認ループ → 全て覚えた → 完了 🟡

**信頼性**: 🟡 *受け入れ基準 EDGE-101 より、UI 統合確認は妥当な推測*

**目的**: 全カードが再確認キューに入り、再確認フェーズで全て「覚えた」で完了する E2E フローを UI 操作含めて検証

**前提条件**:
- 3枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 0 を選択
2. カード2をフリップ → quality 1 を選択
3. カード3をフリップ → quality 2 を選択
4. 再確認モード: カード1（「再確認」バッジ）→ フリップ → 「覚えた」
5. カード2（「再確認」バッジ）→ フリップ → 「覚えた」
6. カード3（「再確認」バッジ）→ フリップ → 「覚えた」
7. 完了画面に遷移

**検証ポイント**:
- `mockSubmitReview` は 3 回のみ
- 全再確認カードに「再確認」バッジが表示される
- 完了画面に「3枚のカードを復習しました」表示
- 再確認フェーズ中に 6 段階ボタンが一度も表示されない

---

#### TC-EDGE-002: 無限ループ（同一カードで「覚えていない」を 3 回繰り返し → 4回目に覚えた） 🔵

**信頼性**: 🔵 *受け入れ基準 EDGE-102、REQ-402（再確認ループ回数上限なし）より*

**目的**: 「覚えていない」を複数回選択してもアプリが正常に動作し続け、UI が崩れないことを検証

**前提条件**:
- 1枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 0 を選択
2. 再確認: 「覚えていない」（1回目）
3. 再確認: 「覚えていない」（2回目）
4. 再確認: 「覚えていない」（3回目）
5. 4回目の表示で「再確認」バッジ + 2 択ボタンが正常に表示されることを確認
6. 再確認: 「覚えた」（4回目の表示）
7. 完了画面に遷移

**検証ポイント**:
- 4回目の表示でも「再確認」バッジ + 2 択ボタンが正常
- `mockSubmitReview` は 1 回のみ
- エラーやクラッシュが発生しない
- 最終的に完了画面に正しく遷移する

---

#### TC-EDGE-003: 複数カードの再確認キューで「覚えた」と「覚えていない」が混在するフロー 🟡

**信頼性**: 🟡 *EDGE-101, EDGE-102 の組み合わせから妥当な推測*

**目的**: 複数カードが再確認キューにある状態で、一部を「覚えていない」、一部を「覚えた」とする混在フローでキュー順序が正しく維持されることの検証

**前提条件**:
- 2枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 0 を選択（再確認キュー: [card-1]）
2. カード2をフリップ → quality 1 を選択（再確認キュー: [card-1, card-2]）
3. 再確認: カード1 → 「覚えていない」（キュー: [card-2, card-1]）
4. 再確認: カード2 → 「覚えた」（キュー: [card-1]）
5. 再確認: カード1 → 「覚えた」（キュー: []）
6. 完了画面に遷移

**検証ポイント**:
- 「覚えていない」のカードが後ろに回り、別のカード（card-2）が先に表示される
- 手順3の後に「質問2」が表示されることで FIFO 順序を確認
- 手順4の後に「質問1」が再表示されることを確認
- `mockSubmitReview` は 2 回のみ

---

### 5.3 Undo 統合テスト（TC-UNDO）

#### TC-UNDO-001: quality 0-2 評価 → 再確認覚えた → 完了 → Undo → regrade quality 3+ → 通常完了 🔵

**信頼性**: 🔵 *受け入れ基準 TC-404-01, TC-404-03, EDGE-201 より*

**目的**: quality 0-2 で再確認キューに入り「覚えた」済みのカードを Undo し、quality 3+ で再評価して再確認キューに入らないことを検証

**前提条件**:
- 1枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 0 を選択
2. 再確認: カード1 → 「覚えた」を選択
3. 完了画面に遷移
4. 完了画面で「質問1 の採点を取り消す」ボタンをクリック → `mockUndoReview('card-1')` が呼ばれることを確認
5. 再採点モード:「再採点」テキストが表示されることを確認
6. カード1をフリップ → quality 4 を選択
7. 完了画面に戻る

**検証ポイント**:
- `mockUndoReview` が 1 回呼び出される
- `mockSubmitReview` が 2 回呼び出される（初回 quality 0 + regrade quality 4）
- 再評価後に再確認ループに入らない（直接完了画面）
- 「再確認」バッジが再評価後に表示されない

---

#### TC-UNDO-002: quality 4 評価 → 完了 → Undo → regrade quality 0-2 → 再確認ループ → 覚えた → 完了 🟡

**信頼性**: 🟡 *受け入れ基準 TC-404-02, EDGE-202 より、regrade 後の再確認遷移フローは実装確認が必要*

**目的**: Undo 後の再評価で quality 0-2 を選択した場合、再確認ループに再度入ることを検証

**前提条件**:
- 1枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 4 を選択
2. 完了画面に遷移
3. 完了画面で「取り消し」ボタンをクリック → Undo API 呼び出し
4. 再採点モード: カード1が表示される
5. カード1をフリップ → quality 2 を選択 → submitReview API 呼び出し
6. 再確認キューにカード1が追加される → 再確認ループに遷移するかを確認

**検証ポイント**:
- `mockUndoReview` が 1 回呼び出される
- `mockSubmitReview` が 2 回呼び出される（初回 quality 4 + regrade quality 2）
- regrade 後に再確認キューにカードが追加されること

**テスト上の注意**:
- 既存実装では regradeMode の場合、moveToNext は即 `isComplete = true` にする設計
- regrade 後に reconfirmQueue が非空の場合のフロー挙動を確認する必要がある
- 既存の TC-TDD-021-01 テストでは submitReview 2回の呼び出しまでを検証済み

---

#### TC-UNDO-003: 複数カード中の 1 枚を Undo → regrade → 他の再確認カードの結果に影響なし 🟡

**信頼性**: 🟡 *REQ-404、EDGE-201 から妥当な推測*

**目的**: 複数カードがある場合に、1 枚の Undo が他のカードの再確認結果に影響しないことを検証

**前提条件**:
- 3枚のカードが存在

**操作手順**:
1. カード1をフリップ → quality 0 を選択（再確認キュー: [card-1]）
2. カード2をフリップ → quality 4 を選択
3. カード3をフリップ → quality 1 を選択（再確認キュー: [card-1, card-3]）
4. 再確認: カード1 → 「覚えた」（再確認キュー: [card-3]）
5. 再確認: カード3 → 「覚えた」（再確認キュー: []）
6. 完了画面に遷移
7. カード1の「取り消し」ボタンをクリック → Undo API
8. 再採点モード: カード1をフリップ → quality 5 を選択
9. 完了画面に戻る

**検証ポイント**:
- カード3の結果は変更されない（reconfirmed のまま）
- カード1のみが regrade される
- reconfirmQueue から card-1 のみが除去され、card-3 に影響しない
- `mockUndoReview` が 1 回呼び出される

---

### 5.4 回帰テスト（TC-REG）

#### TC-REG-001: quality 3-5 のみのフローが変更なく動作する 🟡

**信頼性**: 🟡 *既存テスト維持の妥当な推測、REQ-103 より*

**目的**: 再確認機能追加後も、quality 3-5 で評価した場合の従来フローに変更がないことを検証

**前提条件**:
- 3枚のカードが存在

**操作手順**:
1. カード1〜3 を全て quality 4 でフリップ → 評価
2. 完了画面に遷移

**検証ポイント**:
- 「再確認」バッジが一度も表示されない
- 「覚えた」「覚えていない」ボタンが表示されない
- 通常の 6 段階評価が全カードで表示される
- `mockSubmitReview` が 3 回呼び出される
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
- `mockSubmitReview` が呼び出されない
- 再確認キューにカードが追加されない（「再確認」バッジ非表示）
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
- `mockSubmitReview` が 1 回呼び出される（カード1の quality 1 のみ）
- スキップされたカードは再確認キューに入らない
- 完了画面に「1枚のカードを復習しました」表示

---

#### TC-REG-004: TypeScript 型チェック通過 🔵

**信頼性**: 🔵 *CLAUDE.md テストカバレッジ要件より*

**目的**: 再確認機能追加後の TypeScript strict mode での型エラーがないことを確認

**実行コマンド**: `cd frontend && npm run type-check`

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
- 新規統合テストファイルも含めて全通過

---

## 6. テスト実装上の注意点

### 6.1 ヘルパー関数の共通化 🟡

**信頼性**: 🟡 *テスト実装効率化の妥当な推測*

統合テストでは複数カードの評価操作を繰り返すため、以下のヘルパー関数を作成する:

```typescript
/**
 * カードが表示されるまで待機する
 */
const waitForCard = async (cardFront: string) => {
  await waitFor(() => {
    expect(screen.getByText(cardFront)).toBeInTheDocument();
  });
};

/**
 * カードをフリップして指定の quality で評価する
 */
const flipAndGrade = async (user: ReturnType<typeof userEvent.setup>, grade: number) => {
  await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
  const gradeLabels: Record<number, string> = {
    0: '0 - 全く覚えていない',
    1: '1 - 間違えた',
    2: '2 - 間違えたが見覚えあり',
    3: '3 - 難しかったが正解',
    4: '4 - やや迷ったが正解',
    5: '5 - 完璧',
  };
  await user.click(screen.getByLabelText(gradeLabels[grade]));
};

/**
 * 再確認カードで「覚えた」を選択する
 */
const clickRemembered = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: '覚えた' }));
};

/**
 * 再確認カードで「覚えていない」を選択する
 */
const clickForgotten = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: '覚えていない' }));
};

/**
 * カードをフリップしてスキップする
 */
const flipAndSkip = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
  await user.click(screen.getByLabelText('スキップ'));
};
```

### 6.2 非同期処理の待機パターン 🔵

**信頼性**: 🔵 *既存テスト実装パターン（ReviewPage.test.tsx）より*

```typescript
// API 呼び出し後の次カード表示を待機
await waitFor(() => {
  expect(screen.getByText('質問2')).toBeInTheDocument();
});

// 再確認モード遷移の待機
await waitFor(() => {
  expect(screen.getByText('再確認')).toBeInTheDocument();
});

// 完了画面遷移の待機
await waitFor(() => {
  expect(screen.getByText('復習完了!')).toBeInTheDocument();
});

// 再採点モードの待機
await waitFor(() => {
  expect(screen.getByText('再採点')).toBeInTheDocument();
});
```

### 6.3 モック構成 🔵

**信頼性**: 🔵 *既存テスト実装パターンより*

既存のモック構成をそのまま再利用する。新規モックの追加は不要。

```typescript
// react-router-dom モック（既存パターン）
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

// API モック（既存パターン）
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

### 6.4 回帰テストの実行方法 🔵

**信頼性**: 🔵 *CLAUDE.md より*

```bash
# 全テスト実行
cd frontend && npm test

# TypeScript 型チェック
cd frontend && npm run type-check
```

---

## 7. EARS 要件・設計文書との対応関係

### 参照したユーザストーリー
- ストーリー1.1: 想起失敗カードの再確認
- ストーリー1.2: セッション内学習完結

### 参照した機能要件
- **通常要件**: REQ-001, REQ-002, REQ-003, REQ-004, REQ-005
- **条件付き要件**: REQ-101, REQ-102, REQ-103
- **状態要件**: REQ-201, REQ-202, REQ-203
- **制約要件**: REQ-401, REQ-402, REQ-403, REQ-404
- **UI要件**: REQ-501, REQ-502

### 参照した非機能要件
- NFR-001: 再確認ループのフロントエンドメモリ内完結
- NFR-002: 再確認カード表示切替速度

### 参照した Edge ケース
- EDGE-001: セッション中断
- EDGE-101: 全カード想起失敗
- EDGE-102: 無限ループ
- EDGE-201: Undo 時の再確認キュー除去
- EDGE-202: Undo 後 quality 0-2 再評価
- EDGE-203: Undo 後 quality 3-5 再評価

### 参照した受け入れ基準
- TC-001-01〜03, TC-002-01〜02, TC-003-01〜02, TC-004-01〜03
- TC-101-01〜02, TC-102-01
- TC-404-01〜03
- TC-501-01〜02
- TC-EDGE-001-01, TC-EDGE-101-01, TC-EDGE-102-01

### 参照した設計文書
- **アーキテクチャ**: `docs/design/review-reconfirm/architecture.md` - コンポーネント構成、状態管理設計、Undo 連携設計
- **データフロー**: `docs/design/review-reconfirm/dataflow.md` - 全体フロー、moveToNext フロー、Undo 連携フロー
- **型定義**: `frontend/src/types/card.ts` - SessionCardResultType, SessionCardResult, ReconfirmCard
- **実装コード**: `frontend/src/pages/ReviewPage.tsx` - 状態管理、ハンドラ実装
- **UI コンポーネント**: `frontend/src/components/GradeButtons.tsx`, `frontend/src/components/ReconfirmBadge.tsx`, `frontend/src/components/ReviewComplete.tsx`, `frontend/src/components/ReviewResultItem.tsx`
- **既存テスト**: `frontend/src/pages/__tests__/ReviewPage.test.tsx` - テストパターン参照

---

## 8. テストケースサマリー

### 新規テストケース一覧

| ID | カテゴリ | テスト内容 | 要件参照 | 信頼性 |
|---|---|---|---|---|
| TC-INT-001 | E2E フロー | 通常→再確認バッジ+2択→覚えた→完了画面（フルフロー） | REQ-001〜003, TC-001〜003, TC-101, TC-102, TC-501 | 🔵 |
| TC-INT-002 | E2E フロー | 通常→再確認→覚えていない→覚えた→完了 | REQ-004, TC-004-01〜03 | 🔵 |
| TC-INT-003 | E2E フロー | 通常カードと再確認カードの混在フロー（FIFO順序） | REQ-502 | 🟡 |
| TC-EDGE-001 | エッジケース | 全カード quality 0-2 → 全再確認 → 全覚えた | EDGE-101 | 🟡 |
| TC-EDGE-002 | エッジケース | 無限ループ（覚えていない 3 回 → 覚えた） | EDGE-102, REQ-402 | 🔵 |
| TC-EDGE-003 | エッジケース | 複数カード混在（覚えた + 覚えていない） | EDGE-101, EDGE-102 | 🟡 |
| TC-UNDO-001 | Undo 統合 | Undo → regrade quality 3+ → 通常完了 | TC-404-01, TC-404-03, EDGE-201 | 🔵 |
| TC-UNDO-002 | Undo 統合 | Undo → regrade quality 0-2 → 再確認ループ | TC-404-02, EDGE-202 | 🟡 |
| TC-UNDO-003 | Undo 統合 | 複数カードの Undo で他カード結果に影響なし | REQ-404, EDGE-201 | 🟡 |
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

**品質評価**: ✅ 高品質（赤信号なし、黄信号は全て既存パターン・要件の組み合わせからの妥当な推測のみ）

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

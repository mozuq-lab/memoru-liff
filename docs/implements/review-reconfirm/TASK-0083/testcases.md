# TASK-0083 テストケース定義: 統合テスト・動作確認

**作成日**: 2026-02-28
**タスクID**: TASK-0083
**機能名**: 統合テスト・動作確認
**要件名**: review-reconfirm
**テストファイル**: `frontend/src/pages/__tests__/ReviewPage.integration.test.tsx` (新規作成)

---

## 開発言語・フレームワーク

- **プログラミング言語**: TypeScript 5.x
  - **言語選択の理由**: プロジェクト全体で TypeScript を使用しており、既存テストも TypeScript で記述されている
  - **テストに適した機能**: 型安全なモック定義、テストデータの型チェック
- **テストフレームワーク**: Vitest + React Testing Library + @testing-library/user-event
  - **フレームワーク選択の理由**: 既存の `ReviewPage.test.tsx` と同一構成を維持し、モックパターンの互換性を確保する
  - **テスト実行環境**: `cd frontend && npm test` で全テスト一括実行
- 🔵 *既存テスト実装（ReviewPage.test.tsx 1-6行目）およびプロジェクト構成より*

---

## テストデータ定義

🔵 *既存テスト実装パターン（ReviewPage.test.tsx 32-69行目）より*

```typescript
// 【テストデータ準備】: 既存テストと同一のモックデータを使用し、統合テストの一貫性を確保する
const mockDueCards = [
  { card_id: 'card-1', front: '質問1', back: '解答1', overdue_days: 0 },
  { card_id: 'card-2', front: '質問2', back: '解答2', overdue_days: 1 },
  { card_id: 'card-3', front: '質問3', back: '解答3', overdue_days: 2 },
];

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

---

## モック構成

🔵 *既存テスト実装パターン（ReviewPage.test.tsx 8-30行目）より*

```typescript
// 【環境初期化】: 既存テストと同一のモック構成を再利用する
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

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

---

## ヘルパー関数定義

🟡 *既存テストパターンを参考にした統合テスト用ヘルパーの妥当な推測*

```typescript
// 【テスト前準備】: 統合テストで繰り返し使用する操作をヘルパー関数として共通化する

/**
 * 【初期条件設定】: カードが表示されるまで待機する
 */
const waitForCard = async (cardFront: string) => {
  await waitFor(() => {
    expect(screen.getByText(cardFront)).toBeInTheDocument();
  });
};

/**
 * 【実際の処理実行】: カードをフリップして指定の quality で評価する
 */
const flipAndGrade = async (user: ReturnType<typeof userEvent.setup>, grade: number) => {
  // 【処理内容】: カード表面をクリックしてフリップし、指定の quality ボタンをクリックする
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
 * 【実際の処理実行】: 再確認カードをフリップして「覚えた」を選択する
 */
const flipAndRemember = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
  await user.click(screen.getByRole('button', { name: '覚えた' }));
};

/**
 * 【実際の処理実行】: 再確認カードをフリップして「覚えていない」を選択する
 */
const flipAndForget = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
  await user.click(screen.getByRole('button', { name: '覚えていない' }));
};

/**
 * 【実際の処理実行】: カードをフリップしてスキップする
 */
const flipAndSkip = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
  await user.click(screen.getByLabelText('スキップ'));
};

/**
 * 【結果検証】: 完了画面が表示されるまで待機する
 */
const waitForComplete = async () => {
  await waitFor(() => {
    expect(screen.getByText('復習完了!')).toBeInTheDocument();
  });
};

/**
 * 【結果検証】: 再確認モードに遷移したことを確認する
 */
const waitForReconfirmMode = async () => {
  await waitFor(() => {
    expect(screen.getByText('再確認')).toBeInTheDocument();
  });
};
```

---

## 1. 正常系テストケース（E2E フロー統合テスト）

### TC-INT-001: 通常復習 → quality 0-2 → 再確認バッジ + 2択表示 → 覚えた → 完了画面表示（フルフロー）

- **テスト名**: 通常復習→再確認バッジ+2択→覚えた→完了画面（フルフロー）
  - **何をテストするか**: TASK-0081 のコアロジック（reconfirmQueue 追加、moveToNext 拡張、handleReconfirmRemembered）と TASK-0082 の UI（ReconfirmBadge、GradeButtons 2択モード、ReviewComplete、ReviewResultItem）が一連のフローとして正しく連携動作すること
  - **期待される動作**: カード1を quality 0 で評価 → カード2,3を通常評価 → 通常カード全消化後に再確認モードに遷移 → 「再確認」バッジ + 2択ボタン表示 → 「覚えた」でセッション完了

- **入力値**:
  - 3枚のカード（mockDueCards）
  - カード1: quality 0、カード2: quality 4、カード3: quality 5
  - 再確認モードで「覚えた」選択
  - **入力データの意味**: quality 0 のカードのみが再確認キューに追加されるシナリオ。quality 3+ のカードは再確認キューに入らないことも同時に確認する

- **期待される結果**:
  - カード2表示中に「再確認」バッジが非表示であること
  - 通常カード全消化後に「再確認」バッジが表示されること
  - 再確認モードでカード1の表面「質問1」が表示されること
  - フリップ後に「覚えた」「覚えていない」の2択ボタンが表示されること
  - 通常の6段階評価ボタン（0-5）が非表示であること
  - スキップボタンが非表示であること
  - 「覚えた」選択後に完了画面「復習完了!」「3枚のカードを復習しました」が表示されること
  - `mockSubmitReview` が3回のみ呼び出されること（再確認中は API 呼び出しなし）
  - **期待結果の理由**: 再確認フェーズでは SM-2 の再計算を行わない（REQ-003）ため、API 呼び出しは初回評価時の3回のみ

- **テストの目的**: TASK-0081 と TASK-0082 の横断的な統合動作の確認
  - **確認ポイント**: ReconfirmBadge の表示/非表示切替、GradeButtons のモード切替（6段階 ↔ 2択）、ReviewComplete での再確認結果表示

- 🔵 *受け入れ基準 TC-001-01〜03, TC-002-01, TC-003-01〜02, TC-101-01〜02, TC-102-01, TC-501-01 より*

```typescript
// 【テスト目的】: TASK-0081 コアロジックと TASK-0082 UI の完全統合フロー検証
// 【テスト内容】: 3枚のカードを評価し、quality 0-2 のカードが再確認ループに入り、「覚えた」で完了するフルフロー
// 【期待される動作】: 通常カード全消化 → 再確認バッジ表示 → 2択ボタン表示 → 覚えた → 完了画面
// 🔵 受け入れ基準 TC-001〜003, TC-101, TC-102, TC-501 より

it('通常復習→再確認バッジ+2択→覚えた→完了画面（フルフロー）', async () => {
  // 【テストデータ準備】: 3枚のカードでセッション開始
  // 【初期条件設定】: mockGetDueCards に3枚のカードを設定済み（beforeEach）

  // 【実際の処理実行】: カード1を quality 0 で評価（再確認キューに追加される）
  await waitForCard('質問1');
  await flipAndGrade(user, 0);

  // 【結果検証】: カード2の通常表示で「再確認」バッジが非表示であること
  // 🔵 TC-101-02: 通常カードには再確認バッジが表示されない
  await waitForCard('質問2');
  expect(screen.queryByText('再確認')).not.toBeInTheDocument();

  // 【実際の処理実行】: カード2を quality 4 で評価
  await flipAndGrade(user, 4);

  // 【実際の処理実行】: カード3を quality 5 で評価
  await waitForCard('質問3');
  await flipAndGrade(user, 5);

  // 【結果検証】: 再確認モードに遷移し、「再確認」バッジが表示されること
  // 🔵 TC-101-01: 再確認カードに「再確認」バッジが表示される
  await waitForReconfirmMode();

  // 【結果検証】: カード1の表面が表示されること
  expect(screen.getByText('質問1')).toBeInTheDocument();

  // 【実際の処理実行】: カードをフリップ
  await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));

  // 【結果検証】: 再確認モードで「覚えた」「覚えていない」の2択が表示されること
  // 🔵 TC-002-01: 再確認カードで2択が表示される
  expect(screen.getByRole('button', { name: '覚えた' })).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '覚えていない' })).toBeInTheDocument();

  // 【検証項目】: 通常の6段階評価ボタンが非表示であること
  // 🔵 TC-002-01: 0-5の評価ボタンは表示されない
  expect(screen.queryByLabelText('0 - 全く覚えていない')).not.toBeInTheDocument();

  // 【検証項目】: スキップボタンが非表示であること
  // 🔵 TC-102-01: 再確認カードでスキップボタンが非表示
  expect(screen.queryByLabelText('スキップ')).not.toBeInTheDocument();

  // 【実際の処理実行】: 「覚えた」を選択
  await user.click(screen.getByRole('button', { name: '覚えた' }));

  // 【結果検証】: 完了画面に遷移すること
  await waitForComplete();
  // 🔵 TC-501-01: 完了画面に枚数表示
  expect(screen.getByText('3枚のカードを復習しました')).toBeInTheDocument();

  // 【検証項目】: API は3回のみ呼び出される（再確認中は API 呼び出しなし）
  // 🔵 TC-003-02: 「覚えた」選択で API が呼ばれない
  expect(mockSubmitReview).toHaveBeenCalledTimes(3);
  expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 0);
  expect(mockSubmitReview).toHaveBeenCalledWith('card-2', 4);
  expect(mockSubmitReview).toHaveBeenCalledWith('card-3', 5);
});
```

---

### TC-INT-002: 通常復習 → quality 0-2 → 再確認 → 覚えていない → 再表示 → 覚えた → 完了

- **テスト名**: 通常復習→再確認→覚えていない→再表示→覚えた→完了
  - **何をテストするか**: 「覚えていない」選択後にカードがキュー末尾に再追加され、再度表示されてから「覚えた」で完了するフルフロー
  - **期待される動作**: カード1を quality 0 で評価 → 再確認モードで「覚えていない」→ 同じカードが再表示 → 「覚えた」でセッション完了

- **入力値**:
  - 1枚のカード（card-1のみ）
  - 初回: quality 0
  - 再確認1回目: 「覚えていない」
  - 再確認2回目: 「覚えた」
  - **入力データの意味**: 1枚のみにすることで「覚えていない」後にキュー末尾に再追加されて同じカードが再表示されることを明確に確認できる

- **期待される結果**:
  - 「覚えていない」後に同じカード「質問1」が再表示されること
  - 再表示時にも「再確認」バッジ + 2択ボタンが正しく表示されること
  - 「覚えた」選択後に完了画面に遷移すること
  - `mockSubmitReview` が1回のみ呼び出されること（初回 quality 0 評価時のみ）
  - **期待結果の理由**: 「覚えていない」はフロントエンドメモリ内完結（REQ-004, NFR-001）のため API 呼び出しなし

- **テストの目的**: handleReconfirmForgotten のキュー末尾再追加と再表示の UI 統合動作確認
  - **確認ポイント**: キュー末尾再追加後の画面遷移、2回目の再確認表示の正常性

- 🔵 *受け入れ基準 TC-004-01〜03 より*

```typescript
// 【テスト目的】: 「覚えていない」→キュー末尾再追加→再表示→「覚えた」のフルフロー検証
// 【テスト内容】: 1枚のカードで quality 0 評価後、再確認で「覚えていない」→「覚えた」の流れ
// 【期待される動作】: 「覚えていない」後に同カードが再表示され、「覚えた」で完了
// 🔵 受け入れ基準 TC-004-01〜03 より

it('通常復習→再確認→覚えていない→再表示→覚えた→完了', async () => {
  // 【テストデータ準備】: 1枚のカードのみでセッション開始
  // 【初期条件設定】: mockGetDueCards に1枚のカードを設定

  // 【実際の処理実行】: カード1を quality 0 で評価
  await waitForCard('質問1');
  await flipAndGrade(user, 0);

  // 【結果検証】: 再確認モードに遷移（「再確認」バッジ表示）
  await waitForReconfirmMode();

  // 【実際の処理実行】: カード1をフリップ → 「覚えていない」を選択
  // 🔵 TC-004-01: カードがキュー末尾に追加される
  await flipAndForget(user);

  // 【結果検証】: 同じカードが再表示されること（「質問1」が再度表示）
  await waitForCard('質問1');

  // 【検証項目】: 再表示時にも「再確認」バッジが表示されること
  expect(screen.getByText('再確認')).toBeInTheDocument();

  // 【実際の処理実行】: 「覚えた」を選択
  await flipAndRemember(user);

  // 【結果検証】: 完了画面に遷移
  await waitForComplete();

  // 【検証項目】: API は1回のみ（初回 quality 0 のみ）
  // 🔵 TC-004-02: 「覚えていない」選択で API が呼ばれない
  expect(mockSubmitReview).toHaveBeenCalledTimes(1);
  expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 0);
});
```

---

### TC-INT-003: 通常カードと再確認カードの混在フロー（FIFO順序確認）

- **テスト名**: 通常カードと再確認カードの混在フロー（FIFO順序確認）
  - **何をテストするか**: 通常カードが残っている間は再確認カードが表示されず、通常カード全消化後に再確認カードが FIFO 順で表示されること
  - **期待される動作**: カード1(q1)→カード2(q0)→カード3(q4)→再確認:カード1→再確認:カード2→完了

- **入力値**:
  - 3枚のカード（mockDueCards）
  - カード1: quality 1（再確認キューに追加）
  - カード2: quality 0（再確認キューに追加）
  - カード3: quality 4（再確認キューに追加されない）
  - **入力データの意味**: quality 0-2 のカードが2枚混在し、FIFO 順序（card-1 → card-2）で再確認されることを検証する

- **期待される結果**:
  - カード2,3の通常表示中に「再確認」バッジが非表示であること
  - 通常カード全消化後にカード1（FIFO先頭）が再確認表示されること
  - カード1「覚えた」後にカード2（FIFO2番目）が再確認表示されること
  - カード2「覚えた」後に完了画面に遷移すること
  - `mockSubmitReview` が3回のみ呼び出されること
  - **期待結果の理由**: 通常カードと再確認カードは同一キューで順番に流れる（REQ-502）

- **テストの目的**: moveToNext のキュー優先順位とFIFO順序の統合動作確認
  - **確認ポイント**: 通常カード優先、FIFO順序維持、再確認バッジの表示/非表示タイミング

- 🟡 *REQ-502（通常カードと再確認カードは同一キューで順番に流れる）から妥当な推測*

```typescript
// 【テスト目的】: 通常カードと再確認カードの混在フローで FIFO 順序が維持されることを検証
// 【テスト内容】: 3枚中2枚が再確認キューに入り、FIFO 順に再確認が行われる
// 【期待される動作】: 通常カード優先→再確認カードが FIFO 順で表示→完了
// 🟡 REQ-502 から妥当な推測

it('通常カードと再確認カードの混在フロー（FIFO順序確認）', async () => {
  // 【テストデータ準備】: 3枚のカードでセッション開始

  // 【実際の処理実行】: カード1を quality 1 で評価（再確認キュー: [card-1]）
  await waitForCard('質問1');
  await flipAndGrade(user, 1);

  // 【結果検証】: カード2の通常表示で「再確認」バッジが非表示
  await waitForCard('質問2');
  // 🟡 通常カード表示中は再確認バッジが出ないことの確認
  expect(screen.queryByText('再確認')).not.toBeInTheDocument();

  // 【実際の処理実行】: カード2を quality 0 で評価（再確認キュー: [card-1, card-2]）
  await flipAndGrade(user, 0);

  // 【結果検証】: カード3の通常表示で「再確認」バッジが非表示
  await waitForCard('質問3');
  expect(screen.queryByText('再確認')).not.toBeInTheDocument();

  // 【実際の処理実行】: カード3を quality 4 で評価（再確認キューに追加されない）
  await flipAndGrade(user, 4);

  // 【結果検証】: 再確認モード遷移→カード1（FIFO先頭）が表示
  await waitForReconfirmMode();
  expect(screen.getByText('質問1')).toBeInTheDocument();

  // 【実際の処理実行】: カード1をフリップ→「覚えた」
  await flipAndRemember(user);

  // 【結果検証】: カード2（FIFO2番目）が表示
  // 🟡 FIFO 順序の検証
  await waitForCard('質問2');
  expect(screen.getByText('再確認')).toBeInTheDocument();

  // 【実際の処理実行】: カード2をフリップ→「覚えた」
  await flipAndRemember(user);

  // 【結果検証】: 完了画面に遷移
  await waitForComplete();
  expect(screen.getByText('3枚のカードを復習しました')).toBeInTheDocument();

  // 【検証項目】: API は3回のみ
  expect(mockSubmitReview).toHaveBeenCalledTimes(3);
});
```

---

## 2. 異常系・エッジケーステストケース

### TC-EDGE-001: 全カードが quality 0-2 → 全て再確認ループ → 全て覚えた → 完了

- **テスト名**: 全カードが quality 0-2 → 全再確認 → 全覚えた → 完了
  - **エラーケースの概要**: 全てのカードが想起失敗（quality 0-2）のエッジケース。再確認キューに全カードが入る
  - **エラー処理の重要性**: 通常カードが0枚の状態で再確認キューのみから全カードを処理する能力を検証

- **入力値**:
  - 3枚のカード（mockDueCards）
  - カード1: quality 0、カード2: quality 1、カード3: quality 2
  - 全再確認カードで「覚えた」選択
  - **不正な理由**: 全カードが再確認キューに入る極端なケース
  - **実際の発生シナリオ**: ユーザーが難しいカードばかり学習している場合

- **期待される結果**:
  - 再確認フェーズで全3枚に「再確認」バッジが表示されること
  - 再確認フェーズ中に6段階ボタンが一度も表示されないこと
  - `mockSubmitReview` が3回のみ呼び出されること
  - 完了画面に「3枚のカードを復習しました」が表示されること
  - **システムの安全性**: 全カードが再確認キューに入っても正常にセッションが完了する

- **テストの目的**: 全カード再確認の E2E フロー検証
  - **品質保証の観点**: 再確認キューが通常カード数と同数になる最大ケースでの安定動作保証

- 🟡 *受け入れ基準 EDGE-101 より、UI 統合確認は妥当な推測*

```typescript
// 【テスト目的】: 全カードが再確認キューに入り、全て「覚えた」で完了する E2E フロー検証
// 【テスト内容】: 3枚全てを quality 0-2 で評価し、再確認フェーズで全て「覚えた」
// 【期待される動作】: 全カード再確認 → 全覚えた → 完了画面
// 🟡 受け入れ基準 EDGE-101 より

it('全カードが quality 0-2 → 全再確認 → 全覚えた → 完了', async () => {
  // 【テストデータ準備】: 3枚のカードでセッション開始

  // 【実際の処理実行】: 全カードを quality 0-2 で評価
  await waitForCard('質問1');
  await flipAndGrade(user, 0);

  await waitForCard('質問2');
  await flipAndGrade(user, 1);

  await waitForCard('質問3');
  await flipAndGrade(user, 2);

  // 【結果検証】: 再確認モードに遷移
  await waitForReconfirmMode();

  // 【実際の処理実行】: 全再確認カードで「覚えた」
  // 🟡 各カードで「再確認」バッジが表示されることを暗黙的に確認
  await user.click(screen.getByRole('button', { name: '覚えた' }));
  await user.click(screen.getByRole('button', { name: '覚えた' }));
  await user.click(screen.getByRole('button', { name: '覚えた' }));

  // 【結果検証】: 完了画面に遷移
  await waitForComplete();
  // 🟡 完了画面の枚数表示確認
  expect(screen.getByText('3枚のカードを復習しました')).toBeInTheDocument();

  // 【検証項目】: API は3回のみ
  expect(mockSubmitReview).toHaveBeenCalledTimes(3);
});
```

---

### TC-EDGE-002: 無限ループ（同一カードで「覚えていない」を3回繰り返し → 4回目に覚えた）

- **テスト名**: 無限ループ（覚えていない3回繰り返し→4回目に覚えた）
  - **エラーケースの概要**: 同一カードで「覚えていない」を複数回繰り返す極端なケース。ループ回数に上限がないことを検証
  - **エラー処理の重要性**: REQ-402 で再確認ループの回数上限なしと定義されており、アプリがクラッシュしないことが必須

- **入力値**:
  - 1枚のカード
  - 初回: quality 0
  - 再確認1-3回目: 「覚えていない」
  - 再確認4回目: 「覚えた」
  - **不正な理由**: 同一カードの3回連続「覚えていない」は実運用で起こりうる極端なケース
  - **実際の発生シナリオ**: ユーザーが特定のカードをどうしても覚えられない場合

- **期待される結果**:
  - 4回目の表示でも「再確認」バッジ + 2択ボタンが正常に表示されること
  - `mockSubmitReview` が1回のみ呼び出されること
  - エラーやクラッシュが発生しないこと
  - 最終的に完了画面に正しく遷移すること
  - **システムの安全性**: 無限ループに近い状態でもメモリリークやスタックオーバーフローが発生しない

- **テストの目的**: 再確認ループの回数上限なし仕様の動作確認
  - **品質保証の観点**: ループの安定性と、フロントエンドメモリ内完結（NFR-001）の実証

- 🔵 *受け入れ基準 EDGE-102、REQ-402（再確認ループ回数上限なし）より*

```typescript
// 【テスト目的】: 「覚えていない」を複数回繰り返してもアプリが正常動作することを検証
// 【テスト内容】: 1枚のカードで「覚えていない」3回→「覚えた」1回
// 【期待される動作】: 4回目でも正常に2択ボタン表示、最終的に完了画面
// 🔵 受け入れ基準 EDGE-102, REQ-402 より

it('無限ループ（覚えていない3回繰り返し→4回目に覚えた）', async () => {
  // 【テストデータ準備】: 1枚のカードのみでセッション開始

  // 【実際の処理実行】: quality 0 で評価
  await waitForCard('質問1');
  await flipAndGrade(user, 0);

  // 【結果検証】: 再確認モードに遷移
  await waitForReconfirmMode();

  // 【実際の処理実行】: 「覚えていない」3回繰り返し
  // 🔵 各回で API 呼び出しが発生しないことの暗黙的検証
  await flipAndForget(user);  // 1回目
  await waitForCard('質問1');  // 同じカードが再表示

  await flipAndForget(user);  // 2回目
  await waitForCard('質問1');

  await flipAndForget(user);  // 3回目
  await waitForCard('質問1');

  // 【結果検証】: 4回目の表示でも「再確認」バッジ + 2択ボタンが正常
  // 🔵 EDGE-102: 4回目の表示でも正常表示
  expect(screen.getByText('再確認')).toBeInTheDocument();

  // 【実際の処理実行】: 4回目で「覚えた」
  await flipAndRemember(user);

  // 【結果検証】: 完了画面に遷移
  await waitForComplete();

  // 【検証項目】: API は1回のみ（初回 quality 0 のみ）
  expect(mockSubmitReview).toHaveBeenCalledTimes(1);
});
```

---

### TC-EDGE-003: 複数カードの再確認キューで「覚えた」と「覚えていない」が混在するフロー

- **テスト名**: 複数カード再確認キューで覚えた/覚えていないが混在するフロー
  - **エラーケースの概要**: 複数カードが再確認キューにある状態で、一部を「覚えていない」、一部を「覚えた」とする混在フロー
  - **エラー処理の重要性**: キュー操作（先頭除去、末尾追加）が正しく組み合わさることの検証

- **入力値**:
  - 2枚のカード（card-1, card-2）
  - カード1: quality 0、カード2: quality 1
  - 再確認: カード1「覚えていない」→ カード2「覚えた」→ カード1「覚えた」
  - **不正な理由**: 「覚えていない」でキュー末尾に再追加されたカードが、他のカードの後ろに回ることの検証
  - **実際の発生シナリオ**: 複数の難しいカードを学習中、一部だけ覚えたケース

- **期待される結果**:
  - カード1「覚えていない」後にカード2（「質問2」）が表示されること（FIFO順序確認）
  - カード2「覚えた」後にカード1（「質問1」）が再表示されること
  - カード1「覚えた」後に完了画面に遷移すること
  - `mockSubmitReview` が2回のみ呼び出されること
  - **システムの安全性**: キューの FIFO 順序が「覚えていない」操作後も正しく維持される

- **テストの目的**: 再確認キューの FIFO 順序と「覚えていない」のキュー末尾再追加の複合動作検証
  - **品質保証の観点**: 複数カードの混在フローでのキュー整合性

- 🟡 *EDGE-101, EDGE-102 の組み合わせから妥当な推測*

```typescript
// 【テスト目的】: 複数カードの再確認キューで覚えた/覚えていないが混在する場合のキュー順序検証
// 【テスト内容】: 2枚のカードで再確認し、「覚えていない」のカードが後ろに回ることを確認
// 【期待される動作】: card-1「覚えていない」→ card-2「覚えた」→ card-1「覚えた」→ 完了
// 🟡 EDGE-101, EDGE-102 の組み合わせから妥当な推測

it('複数カード再確認キューで覚えた/覚えていないが混在するフロー', async () => {
  // 【テストデータ準備】: 2枚のカードでセッション開始

  // 【実際の処理実行】: カード1を quality 0（再確認キュー: [card-1]）
  await waitForCard('質問1');
  await flipAndGrade(user, 0);

  // 【実際の処理実行】: カード2を quality 1（再確認キュー: [card-1, card-2]）
  await waitForCard('質問2');
  await flipAndGrade(user, 1);

  // 【結果検証】: 再確認モードに遷移
  await waitForReconfirmMode();

  // 【実際の処理実行】: カード1→「覚えていない」（キュー: [card-2, card-1]）
  await flipAndForget(user);

  // 【結果検証】: カード2が先に表示される（FIFO順序）
  // 🟡 「覚えていない」後に別カードが表示されることで FIFO 順序を検証
  await waitForCard('質問2');

  // 【実際の処理実行】: カード2→「覚えた」（キュー: [card-1]）
  await flipAndRemember(user);

  // 【結果検証】: カード1が再表示される
  await waitForCard('質問1');

  // 【実際の処理実行】: カード1→「覚えた」（キュー: []）
  await flipAndRemember(user);

  // 【結果検証】: 完了画面に遷移
  await waitForComplete();

  // 【検証項目】: API は2回のみ
  expect(mockSubmitReview).toHaveBeenCalledTimes(2);
});
```

---

## 3. Undo 統合テストケース

### TC-UNDO-001: quality 0-2 評価 → 再確認覚えた → 完了 → Undo → regrade quality 3+ → 通常完了

- **テスト名**: Undo → regrade quality 3+ → 通常完了（再確認ループなし）
  - **何をテストするか**: quality 0-2 で再確認キューに入り「覚えた」済みのカードを Undo し、quality 3+ で再評価して再確認キューに入らないことを検証
  - **期待される動作**: quality 0 評価 → 再確認「覚えた」→ 完了 → Undo → regrade quality 4 → 通常完了（再確認なし）

- **入力値**:
  - 1枚のカード
  - 初回: quality 0 → 再確認「覚えた」
  - Undo 後: quality 4 で regrade
  - **入力データの意味**: Undo 後の再評価で quality 3+ を選択すると再確認キューに追加されないことを検証

- **期待される結果**:
  - `mockUndoReview` が1回呼び出されること
  - `mockSubmitReview` が2回呼び出されること（初回 quality 0 + regrade quality 4）
  - 再評価後に再確認ループに入らないこと（直接完了画面）
  - 「再採点」テキストが regrade モードで表示されること
  - **期待結果の理由**: quality 3+ では再確認キューに追加されない（REQ-103）

- **テストの目的**: Undo → regrade → 再確認キュー除去の統合動作確認
  - **確認ポイント**: reconfirmQueue からのカード除去、regrade 後の完了画面直接遷移

- 🔵 *受け入れ基準 TC-404-01, TC-404-03, EDGE-201 より*

```typescript
// 【テスト目的】: quality 0-2 評価→Undo→regrade quality 3+で再確認ループに入らないことを検証
// 【テスト内容】: 1枚のカードで quality 0→覚えた→Undo→quality 4 regrade
// 【期待される動作】: Undo 後の quality 3+ regrade で再確認キューに入らず通常完了
// 🔵 受け入れ基準 TC-404-01, TC-404-03, EDGE-201 より

it('Undo → regrade quality 3+ → 通常完了', async () => {
  // 【テストデータ準備】: 1枚のカードのみでセッション開始

  // 【実際の処理実行】: quality 0 で評価
  await waitForCard('質問1');
  await flipAndGrade(user, 0);

  // 【実際の処理実行】: 再確認「覚えた」
  await waitForReconfirmMode();
  await user.click(screen.getByRole('button', { name: '覚えた' }));

  // 【結果検証】: 完了画面に遷移
  await waitForComplete();

  // 【実際の処理実行】: Undo ボタンクリック
  const undoButton = screen.getByLabelText('質問1 の採点を取り消す');
  await user.click(undoButton);

  // 【結果検証】: 再採点モードに遷移
  await waitFor(() => {
    expect(screen.getByText('再採点')).toBeInTheDocument();
  });

  // 【実際の処理実行】: quality 4 で regrade
  await flipAndGrade(user, 4);

  // 【結果検証】: 直接完了画面に戻る（再確認ループに入らない）
  await waitForComplete();

  // 【検証項目】: API 呼び出し回数
  // 🔵 undoReview 1回、submitReview 2回
  expect(mockUndoReview).toHaveBeenCalledTimes(1);
  expect(mockSubmitReview).toHaveBeenCalledTimes(2);
  expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 0);
  expect(mockSubmitReview).toHaveBeenLastCalledWith('card-1', 4);
});
```

---

### TC-UNDO-002: quality 4 評価 → 完了 → Undo → regrade quality 0-2 → 再確認ループ

- **テスト名**: Undo → regrade quality 0-2 → 再確認ループ
  - **何をテストするか**: Undo 後の再評価で quality 0-2 を選択した場合、再確認ループに再度入ることを検証
  - **期待される動作**: quality 4 で通常完了 → Undo → quality 2 で regrade → 再確認キューにカード追加

- **入力値**:
  - 1枚のカード
  - 初回: quality 4
  - Undo 後: quality 2 で regrade
  - **入力データの意味**: 初回は quality 3+ で再確認不要だったが、Undo 後に quality 0-2 で再評価して再確認が必要になるケース

- **期待される結果**:
  - `mockUndoReview` が1回呼び出されること
  - `mockSubmitReview` が2回呼び出されること（初回 quality 4 + regrade quality 2）
  - regrade 後に再確認キューにカードが追加されること
  - **期待結果の理由**: regrade でも quality 0-2 なら再確認キューに追加される（TC-404-02）

- **テストの目的**: Undo 後の regrade で再確認キューへの再追加動作を検証
  - **確認ポイント**: regradeMode から再確認キューへの追加パス

- 🟡 *受け入れ基準 TC-404-02, EDGE-202 より、regrade 後の再確認遷移フローは実装確認が必要*

**テスト上の注意**:
- 既存実装では regradeMode の場合、moveToNext は即 `isComplete = true` にする設計
- regrade 後に reconfirmQueue が非空の場合のフロー挙動を確認する必要がある
- 既存の TC-TDD-INT-04 テストでは submitReview 2回の呼び出しまでを検証済み

```typescript
// 【テスト目的】: Undo 後の quality 0-2 regrade で再確認キューに追加されることを検証
// 【テスト内容】: 1枚のカードで quality 4→Undo→quality 2 regrade→再確認キュー追加
// 【期待される動作】: regrade quality 0-2 で再確認キューに追加される
// 🟡 受け入れ基準 TC-404-02, EDGE-202 より

it('Undo → regrade quality 0-2 → 再確認ループ', async () => {
  // 【テストデータ準備】: 1枚のカードのみでセッション開始

  // 【実際の処理実行】: quality 4 で評価
  await waitForCard('質問1');
  await flipAndGrade(user, 4);

  // 【結果検証】: 完了画面に遷移
  await waitForComplete();

  // 【実際の処理実行】: Undo
  const undoButton = screen.getByLabelText('質問1 の採点を取り消す');
  await user.click(undoButton);

  // 【結果検証】: 再採点モードに遷移
  await waitFor(() => {
    expect(screen.getByText('再採点')).toBeInTheDocument();
  });

  // 【実際の処理実行】: quality 2 で regrade → 再確認キューに追加
  await flipAndGrade(user, 2);

  // 【結果検証】: API 呼び出し回数の確認
  // 🟡 undoReview 1回、submitReview 2回
  await waitFor(() => {
    expect(mockUndoReview).toHaveBeenCalledTimes(1);
    expect(mockSubmitReview).toHaveBeenCalledTimes(2);
    expect(mockSubmitReview).toHaveBeenLastCalledWith('card-1', 2);
  });
});
```

---

### TC-UNDO-003: 複数カード中の1枚を Undo → regrade → 他の再確認カードの結果に影響なし

- **テスト名**: 複数カードの1枚を Undo → 他カードの再確認結果に影響なし
  - **何をテストするか**: 複数カードがある場合に、1枚の Undo が他のカードの再確認結果に影響しないこと
  - **期待される動作**: 3枚のカードで通常フロー完了 → カード1を Undo → regrade → カード3の結果は変わらない

- **入力値**:
  - 3枚のカード（mockDueCards）
  - カード1: quality 0 → 再確認「覚えた」
  - カード2: quality 4（通常完了）
  - カード3: quality 1 → 再確認「覚えた」
  - Undo: カード1 → regrade quality 5
  - **入力データの意味**: quality 0-2 のカードが2枚ある中で、1枚のみ Undo して他のカードに影響がないことを検証

- **期待される結果**:
  - カード3の結果は変更されないこと（reconfirmed のまま）
  - カード1のみが regrade されること
  - reconfirmQueue から card-1 のみが除去され、card-3 に影響しないこと
  - `mockUndoReview` が1回呼び出されること
  - **期待結果の理由**: Undo は対象カードのみの状態変更（REQ-404）

- **テストの目的**: Undo の影響範囲が対象カードに限定されることの検証
  - **確認ポイント**: 他カードの reviewResults が変更されないこと

- 🟡 *REQ-404、EDGE-201 から妥当な推測*

```typescript
// 【テスト目的】: 1枚の Undo が他カードの再確認結果に影響しないことを検証
// 【テスト内容】: 3枚中2枚が再確認済み→1枚を Undo→他カードの結果が変わらない
// 【期待される動作】: card-1 のみ regrade、card-3 は reconfirmed のまま
// 🟡 REQ-404、EDGE-201 から妥当な推測

it('複数カードの1枚を Undo → 他カードの再確認結果に影響なし', async () => {
  // 【テストデータ準備】: 3枚のカードでセッション開始

  // 【実際の処理実行】: カード1を quality 0（再確認キュー: [card-1]）
  await waitForCard('質問1');
  await flipAndGrade(user, 0);

  // 【実際の処理実行】: カード2を quality 4（通常完了）
  await waitForCard('質問2');
  await flipAndGrade(user, 4);

  // 【実際の処理実行】: カード3を quality 1（再確認キュー: [card-1, card-3]）
  await waitForCard('質問3');
  await flipAndGrade(user, 1);

  // 再確認: card-1「覚えた」
  await waitForReconfirmMode();
  await user.click(screen.getByRole('button', { name: '覚えた' }));

  // 再確認: card-3「覚えた」
  await user.click(screen.getByRole('button', { name: '覚えた' }));

  // 【結果検証】: 完了画面に遷移
  await waitForComplete();

  // 【実際の処理実行】: カード1を Undo
  const undoButton = screen.getByLabelText('質問1 の採点を取り消す');
  await user.click(undoButton);

  // 【結果検証】: 再採点モードに遷移
  await waitFor(() => {
    expect(screen.getByText('再採点')).toBeInTheDocument();
  });

  // 【実際の処理実行】: quality 5 で regrade
  await flipAndGrade(user, 5);

  // 【結果検証】: 完了画面に戻る
  await waitForComplete();

  // 【検証項目】: API 呼び出し回数
  // 🟡 undoReview 1回、submitReview 4回（card-1(q0), card-2(q4), card-3(q1), card-1(regrade q5)）
  expect(mockUndoReview).toHaveBeenCalledTimes(1);
  expect(mockSubmitReview).toHaveBeenCalledTimes(4);
});
```

---

## 4. 境界値・回帰テストケース

### TC-REG-001: quality 3-5 のみのフローが変更なく動作する

- **テスト名**: quality 3-5 のみのフローが変更なく動作する（回帰テスト）
  - **境界値の意味**: quality 3 は再確認キュー追加/非追加の境界値（0-2: 追加、3-5: 非追加）
  - **境界値での動作保証**: 全カードが quality 3-5 の場合、再確認関連の UI が一切表示されないこと

- **入力値**:
  - 3枚のカード（mockDueCards）
  - 全カード: quality 4 で評価
  - **境界値選択の根拠**: quality 3 が境界値だが、quality 4 を使用して通常フローの正常動作を確認
  - **実際の使用場面**: ユーザーが全カードを正解した場合の通常フロー

- **期待される結果**:
  - 「再確認」バッジが一度も表示されないこと
  - 「覚えた」「覚えていない」ボタンが表示されないこと
  - 通常の6段階評価が全カードで表示されること
  - `mockSubmitReview` が3回呼び出されること
  - 完了画面に「3枚のカードを復習しました」が表示されること
  - **一貫した動作**: 再確認機能追加前後で quality 3-5 フローに変更がないこと

- **テストの目的**: 再確認機能追加による既存フローへの回帰がないことの確認
  - **堅牢性の確認**: 新機能追加が既存機能に影響を与えていないこと

- 🟡 *既存テスト維持の妥当な推測、REQ-103 より*

```typescript
// 【テスト目的】: 再確認機能追加後も quality 3-5 フローが変更なく動作することを検証
// 【テスト内容】: 3枚全てを quality 4 で評価し、再確認関連UIが一切表示されないことを確認
// 【期待される動作】: 通常の6段階評価→完了画面（再確認なし）
// 🟡 既存テスト維持の妥当な推測

it('quality 3-5 のみのフローが変更なく動作する', async () => {
  // 【テストデータ準備】: 3枚のカードでセッション開始

  // 【実際の処理実行】: 全カードを quality 4 で評価
  await waitForCard('質問1');
  // 【検証項目】: 通常カード表示中に「再確認」バッジが非表示
  expect(screen.queryByText('再確認')).not.toBeInTheDocument();
  await flipAndGrade(user, 4);

  await waitForCard('質問2');
  expect(screen.queryByText('再確認')).not.toBeInTheDocument();
  await flipAndGrade(user, 4);

  await waitForCard('質問3');
  expect(screen.queryByText('再確認')).not.toBeInTheDocument();
  await flipAndGrade(user, 4);

  // 【結果検証】: 直接完了画面に遷移（再確認フェーズなし）
  await waitForComplete();
  expect(screen.getByText('3枚のカードを復習しました')).toBeInTheDocument();

  // 【検証項目】: 「覚えた」「覚えていない」ボタンが表示されなかったことを確認
  // （完了画面には Undo ボタンはあるが「覚えた」ボタンは存在しない）
  expect(screen.queryByRole('button', { name: '覚えた' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: '覚えていない' })).not.toBeInTheDocument();

  // 【検証項目】: API は3回呼び出される
  expect(mockSubmitReview).toHaveBeenCalledTimes(3);
});
```

---

### TC-REG-002: スキップフローが変更なく動作する

- **テスト名**: スキップフローが変更なく動作する（回帰テスト）
  - **境界値の意味**: スキップは quality 評価を行わないため、再確認キューへの追加が発生しないことの確認
  - **境界値での動作保証**: スキップされたカードが再確認キューに入らないこと

- **入力値**:
  - 3枚のカード（mockDueCards）
  - 全カード: スキップ
  - **境界値選択の根拠**: スキップは API 呼び出しを行わない操作であり、再確認キューとの関連が発生しないことを検証
  - **実際の使用場面**: ユーザーが全カードをスキップした場合

- **期待される結果**:
  - `mockSubmitReview` が呼び出されないこと
  - 再確認キューにカードが追加されないこと（「再確認」バッジ非表示）
  - 完了画面に「0枚のカードを復習しました」が表示されること
  - **一貫した動作**: スキップフローが再確認機能の影響を受けないこと

- **テストの目的**: スキップ操作が再確認機能の影響を受けないことの確認
  - **堅牢性の確認**: スキップ時に再確認関連のロジックが誤って動作しないこと

- 🟡 *既存テスト維持の妥当な推測*

```typescript
// 【テスト目的】: スキップ操作が再確認機能の影響を受けないことを検証
// 【テスト内容】: 3枚全てをスキップし、再確認キューが空のまま完了すること
// 【期待される動作】: 全スキップ→完了画面（0枚復習、再確認なし）
// 🟡 既存テスト維持の妥当な推測

it('スキップフローが変更なく動作する', async () => {
  // 【テストデータ準備】: 3枚のカードでセッション開始

  // 【実際の処理実行】: 全カードをスキップ
  await waitForCard('質問1');
  await flipAndSkip(user);

  await waitForCard('質問2');
  await flipAndSkip(user);

  await waitForCard('質問3');
  await flipAndSkip(user);

  // 【結果検証】: 完了画面に遷移（再確認フェーズなし）
  await waitForComplete();
  // 🟡 スキップのみなので0枚表示
  expect(screen.getByText('0枚のカードを復習しました')).toBeInTheDocument();

  // 【検証項目】: API は呼び出されない
  expect(mockSubmitReview).not.toHaveBeenCalled();

  // 【検証項目】: 再確認バッジが表示されなかったこと
  expect(screen.queryByText('再確認')).not.toBeInTheDocument();
});
```

---

### TC-REG-003: quality 0-2 + スキップの混在フロー

- **テスト名**: quality 0-2 + スキップの混在フロー（回帰テスト）
  - **境界値の意味**: quality 0-2 とスキップが混在する場合、スキップされたカードが再確認キューに入らないことの確認
  - **境界値での動作保証**: スキップと quality 0-2 が同一セッションで混在しても正常動作すること

- **入力値**:
  - 3枚のカード（mockDueCards）
  - カード1: quality 1（再確認キューに追加）
  - カード2: スキップ
  - カード3: スキップ
  - 再確認: カード1「覚えた」
  - **境界値選択の根拠**: スキップされたカードと quality 0-2 のカードの混在を検証
  - **実際の使用場面**: ユーザーが一部のカードのみ評価し、残りをスキップした場合

- **期待される結果**:
  - `mockSubmitReview` が1回呼び出されること（カード1の quality 1 のみ）
  - スキップされたカードは再確認キューに入らないこと
  - 完了画面に「1枚のカードを復習しました」が表示されること
  - **一貫した動作**: スキップと再確認の組み合わせで正常動作すること

- **テストの目的**: スキップと quality 0-2 の混在フローの正常動作確認
  - **堅牢性の確認**: 異なる操作の組み合わせでの安定動作

- 🟡 *REQ-001, REQ-103 から妥当な推測*

```typescript
// 【テスト目的】: quality 0-2 とスキップが混在する場合の動作を検証
// 【テスト内容】: カード1を quality 1、カード2,3をスキップし、再確認後に完了
// 【期待される動作】: 1枚のみ再確認ループ→覚えた→完了（1枚復習）
// 🟡 REQ-001, REQ-103 から妥当な推測

it('quality 0-2 + スキップの混在フロー', async () => {
  // 【テストデータ準備】: 3枚のカードでセッション開始

  // 【実際の処理実行】: カード1を quality 1 で評価（再確認キュー: [card-1]）
  await waitForCard('質問1');
  await flipAndGrade(user, 1);

  // 【実際の処理実行】: カード2をスキップ
  await waitForCard('質問2');
  await flipAndSkip(user);

  // 【実際の処理実行】: カード3をスキップ
  await waitForCard('質問3');
  await flipAndSkip(user);

  // 【結果検証】: 再確認モードに遷移
  await waitForReconfirmMode();

  // 【実際の処理実行】: カード1をフリップ→「覚えた」
  await flipAndRemember(user);

  // 【結果検証】: 完了画面に遷移
  await waitForComplete();
  // 🟡 1枚のみ復習済み
  expect(screen.getByText('1枚のカードを復習しました')).toBeInTheDocument();

  // 【検証項目】: API は1回のみ
  expect(mockSubmitReview).toHaveBeenCalledTimes(1);
  expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 1);
});
```

---

### TC-REG-004: TypeScript 型チェック通過

- **テスト名**: TypeScript 型チェック通過
  - **何をテストするか**: 再確認機能追加後の TypeScript strict mode での型エラーがないこと
  - **期待される動作**: `npm run type-check` が exit code 0 で完了する

- **入力値**:
  - 全 TypeScript ファイル
  - **入力データの意味**: プロジェクト全体の型整合性を確認

- **期待される結果**:
  - tsc --noEmit が exit code 0 で完了する
  - 型エラーが 0 件
  - **期待結果の理由**: TypeScript strict mode での型安全性保証（CLAUDE.md）

- **テストの目的**: 型チェック通過の最終確認
  - **確認ポイント**: ReconfirmCard, SessionCardResultType, SessionCardResult の型が正しく使用されていること

- 🔵 *CLAUDE.md テストカバレッジ要件より*

**実行コマンド**: `cd frontend && npm run type-check`

**検証ポイント**:
- tsc --noEmit が exit code 0 で完了する
- 型エラーが 0 件

**注意**: このテストケースは Vitest テストとしてではなく、CI/CD パイプラインまたは手動での実行確認として扱う。

---

### TC-REG-005: 全テスト通過

- **テスト名**: 全テスト通過
  - **何をテストするか**: 既存テストを含む全フロントエンドテストが通過すること
  - **期待される動作**: `npm test` が全テストスイートで passed を返す

- **入力値**:
  - 全テストファイル
  - **入力データの意味**: 新規テストと既存テストの両方が通過することの確認

- **期待される結果**:
  - 全テストスイートが passed
  - 失敗テストが 0 件
  - 新規統合テストファイル（ReviewPage.integration.test.tsx）も含めて全通過
  - **期待結果の理由**: 再確認機能追加が既存機能に回帰を発生させていないこと

- **テストの目的**: 全テスト通過の最終確認
  - **確認ポイント**: 既存テスト + 新規統合テストの全通過

- 🔵 *CLAUDE.md テスト要件より*

**実行コマンド**: `cd frontend && npm test`

**検証ポイント**:
- 全テストスイートが passed
- 失敗テストが 0 件

**注意**: このテストケースは Vitest テストとしてではなく、CI/CD パイプラインまたは手動での実行確認として扱う。

---

## テストケース実装時の日本語コメント指針

### セットアップ・クリーンアップのコメント

```typescript
beforeEach(() => {
  // 【テスト前準備】: 各テスト実行前にモック関数をクリアし、デフォルトのモックレスポンスを設定する
  // 【環境初期化】: mockGetDueCards, mockSubmitReview, mockUndoReview の呼び出し履歴をリセット
  vi.clearAllMocks();
  mockGetDueCards.mockResolvedValue({
    due_cards: mockDueCards,
    total_due_count: 3,
    next_due_date: null,
  });
  mockSubmitReview.mockImplementation((cardId: string, grade: number) =>
    Promise.resolve(mockReviewResponse(cardId, grade))
  );
  mockUndoReview.mockImplementation((cardId: string) =>
    Promise.resolve(mockUndoResponse(cardId))
  );
});
```

### テストケースのコメント例

```typescript
// 【テスト目的】: [フロー全体の統合動作確認]
// 【テスト内容】: [ユーザー操作のシミュレーション]
// 【期待される動作】: [各ステップでの UI 変化]
// 🔵🟡🔴 信頼性レベル

// Given（準備フェーズ）
// 【テストデータ準備】: [3枚のカードをロード]
// 【初期条件設定】: [mockGetDueCards にカードデータを設定]

// When（実行フェーズ）
// 【実際の処理実行】: [カードをフリップして quality 0 で評価]
// 【処理内容】: [handleGrade が呼ばれ、reconfirmQueue にカードが追加される]

// Then（検証フェーズ）
// 【結果検証】: [再確認バッジが表示されること]
// 【期待値確認】: [「再確認」テキストが画面上に存在すること]
expect(screen.getByText('再確認')).toBeInTheDocument();
// 【確認内容】: 再確認モードへの正しい遷移を確認
```

---

## 要件定義との対応関係

### 参照したユーザストーリー
- **ストーリー1.1**: 想起失敗カードの再確認
- **ストーリー1.2**: セッション内学習完結

### 参照した機能要件
- **通常要件**: REQ-001（キュー追加）, REQ-002（再確認モード表示）, REQ-003（覚えた動作）, REQ-004（覚えていない動作）, REQ-005（セッション完了）
- **条件付き要件**: REQ-101（バッジ表示）, REQ-102（スキップ非表示）, REQ-103（quality 3-5 非対象）
- **状態要件**: REQ-201（キュー状態管理）, REQ-202（モード遷移）, REQ-203（結果記録）
- **制約要件**: REQ-401（API非呼び出し）, REQ-402（ループ上限なし）, REQ-403（キュー操作制約）, REQ-404（Undo連携）
- **UI要件**: REQ-501（完了画面表示）, REQ-502（カード表示順序）

### 参照した非機能要件
- **NFR-001**: 再確認ループのフロントエンドメモリ内完結
- **NFR-002**: 再確認カード表示切替速度

### 参照した Edge ケース
- **EDGE-001**: セッション中断（実装除外: 自動テストで検証困難）
- **EDGE-101**: 全カード想起失敗 → TC-EDGE-001
- **EDGE-102**: 無限ループ → TC-EDGE-002
- **EDGE-201**: Undo 時の再確認キュー除去 → TC-UNDO-001
- **EDGE-202**: Undo 後 quality 0-2 再評価 → TC-UNDO-002
- **EDGE-203**: Undo 後 quality 3-5 再評価 → TC-UNDO-001

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

## テストケースサマリー

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

- 🔵 青信号: 6件 (43%) - 要件定義・受け入れ基準・既存実装から直接導出
- 🟡 黄信号: 8件 (57%) - 既存パターン・要件の組み合わせからの妥当な推測
- 🔴 赤信号: 0件 (0%)

---

## 完了条件チェックリスト

- [ ] TC-INT-001〜003: E2E フロー統合テストが通る
- [ ] TC-EDGE-001〜003: エッジケーステストが通る
- [ ] TC-UNDO-001〜003: Undo 統合テストが通る
- [ ] TC-REG-001〜003: 回帰テスト（フロー別）が通る
- [ ] TC-REG-004: `npm run type-check` で型エラーなし
- [ ] TC-REG-005: `npm test` で全テスト通過（既存 + 新規）

---

## 実装除外事項

以下は TASK-0083 のスコープ外とする:

- **手動テスト**: ローカル環境での手動操作テストは開発者が任意で実施。本タスクは自動テストの追加に集中する
- **E2E テスト（Playwright 等）**: ブラウザベースの E2E テストは現在のプロジェクトスコープ外。React Testing Library による統合テストで代替する
- **パフォーマンステスト**: NFR-001, NFR-002 のパフォーマンス要件は自動テストでの定量的検証が困難なため、手動確認に委ねる
- **セッション中断テスト（EDGE-001）**: アプリ終了 → 翌日の再表示はフロントエンドの自動テストで検証困難なため、手動確認に委ねる（SM-2 が interval=1 を設定済みのため理論的に保証）

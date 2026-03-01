/**
 * ReviewPage 統合テスト (TASK-0083)
 *
 * 【テスト目的】: TASK-0081（コアロジック）と TASK-0082（UI コンポーネント）が
 *               一連のフローとして正しく連携動作することをエンドツーエンドで検証する
 *
 * 【テスト対象】:
 *   - E2E フロー統合テスト（TC-INT-001〜003）
 *   - エッジケーステスト（TC-EDGE-001〜003）
 *   - Undo 連携統合テスト（TC-UNDO-001〜003）
 *   - 回帰テスト（TC-REG-001〜003）
 *
 * 【既存テストとの関係】: frontend/src/pages/__tests__/ReviewPage.test.tsx の
 *   既存 62 件のテストとは独立して動作する。削除・変更しない。
 *
 * 【注意】: TC-REG-004（TypeScript 型チェック）と TC-REG-005（全テスト通過）は
 *   Vitest テストとしてではなく、`npm run type-check` および `npm test` の
 *   コマンドライン実行で検証する（本ファイルには含まない）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ReviewPage } from '../ReviewPage';

// ============================================================
// モック設定
// 🔵 既存テスト実装パターン（ReviewPage.test.tsx 8-30行目）より
// ============================================================

/** 【環境初期化】: react-router-dom の useNavigate をモックに置き換える */
const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

/** 【環境初期化】: API サービスをモックに置き換える */
const mockGetDueCards = vi.fn();
const mockSubmitReview = vi.fn();
const mockUndoReview = vi.fn();

vi.mock('@/services/api', () => ({
  cardsApi: {
    getDueCards: (...args: unknown[]) => mockGetDueCards(...args),
  },
  reviewsApi: {
    submitReview: (...args: unknown[]) => mockSubmitReview(...args),
    undoReview: (...args: unknown[]) => mockUndoReview(...args),
  },
}));

// ============================================================
// テストデータ定義
// 🔵 既存テスト実装パターン（ReviewPage.test.tsx 32-36行目）より
// ============================================================

/** 【テストデータ準備】: 3枚のカード（既存テストと同一のモックデータ） */
const mockDueCards = [
  { card_id: 'card-1', front: '質問1', back: '解答1', overdue_days: 0 },
  { card_id: 'card-2', front: '質問2', back: '解答2', overdue_days: 1 },
  { card_id: 'card-3', front: '質問3', back: '解答3', overdue_days: 2 },
];

/** 【テストデータ準備】: submitReview API モックレスポンスのファクトリ関数 */
const mockReviewResponse = (cardId: string, grade: number) => ({
  card_id: cardId,
  grade,
  previous: { ease_factor: 2.5, interval: 1, repetitions: 0, due_date: null },
  updated: { ease_factor: 2.6, interval: 1, repetitions: 1, due_date: '2026-03-01' },
  reviewed_at: '2026-02-28T10:00:00Z',
});

/** 【テストデータ準備】: undoReview API モックレスポンスのファクトリ関数 */
const mockUndoResponse = (cardId: string) => ({
  card_id: cardId,
  restored: { ease_factor: 2.5, interval: 1, repetitions: 0, due_date: '2026-02-28' },
  undone_at: '2026-02-28T10:01:00Z',
});

// ============================================================
// ヘルパー関数定義
// 🟡 既存テストパターンを参考にした統合テスト用ヘルパーの妥当な推測
// ============================================================

/**
 * 【テスト前準備】: ReviewPage をメモリルーターでレンダリングする
 * 🔵 既存テスト実装パターン（ReviewPage.test.tsx 38-44行目）より
 */
const renderReviewPage = () => {
  return render(
    <MemoryRouter>
      <ReviewPage />
    </MemoryRouter>
  );
};

/**
 * 【初期条件設定】: 指定したカード表面テキストが表示されるまで待機する
 * 🔵 既存テストパターンの waitFor 利用から
 */
const waitForCard = async (cardFront: string) => {
  await waitFor(() => {
    expect(screen.getByText(cardFront)).toBeInTheDocument();
  });
};

/**
 * 【実際の処理実行】: カードをフリップして指定の quality で評価する
 * 🔵 要件定義書 3.3 UI 要素の識別方法より
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
 * 【実際の処理実行】: 再確認モードで「覚えた」を選択する
 * 注意: 再確認モードでは GradeButtons はフリップ前から表示されているため
 * フリップ操作不要でボタンをクリックできる（ReviewPage.tsx 391-399行目より）
 * 🔵 ReviewPage.tsx 実装より
 */
const clickRemembered = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: '覚えた' }));
};

/**
 * 【実際の処理実行】: 再確認モードで「覚えていない」を選択する
 * 🔵 ReviewPage.tsx 実装より
 */
const clickForgotten = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: '覚えていない' }));
};

/**
 * 【実際の処理実行】: カードをフリップしてスキップする
 * 🔵 要件定義書 3.3 UI 要素の識別方法より
 */
const flipAndSkip = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
  await user.click(screen.getByLabelText('スキップ'));
};

/**
 * 【結果検証】: 完了画面が表示されるまで待機する
 * 🔵 要件定義書 3.3 UI 要素の識別方法より
 */
const waitForComplete = async () => {
  await waitFor(() => {
    expect(screen.getByText('復習完了!')).toBeInTheDocument();
  });
};

/**
 * 【結果検証】: 再確認モードに遷移したことを確認する
 * 🔵 要件定義書 3.3 UI 要素の識別方法より
 */
const waitForReconfirmMode = async () => {
  await waitFor(() => {
    expect(screen.getByText('再確認')).toBeInTheDocument();
  });
};

// ============================================================
// 統合テストスイート
// ============================================================

describe('ReviewPage 統合テスト', () => {
  let user: ReturnType<typeof userEvent.setup>;

  beforeEach(() => {
    // 【テスト前準備】: 各テスト実行前にモック関数をクリアし、デフォルトのモックレスポンスを設定する
    // 【環境初期化】: mockGetDueCards, mockSubmitReview, mockUndoReview の呼び出し履歴をリセット
    vi.clearAllMocks();
    user = userEvent.setup();

    // 【デフォルト設定】: 3枚のカードを返すデフォルトモックを設定
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

  // ===========================================================
  // 1. E2E フロー統合テスト
  // ===========================================================

  describe('E2Eフロー統合テスト', () => {
    it('TC-INT-001: 通常復習→再確認バッジ+2択→覚えた→完了画面（フルフロー）', async () => {
      // 【テスト目的】: TASK-0081 コアロジックと TASK-0082 UI の完全統合フロー検証
      // 【テスト内容】: 3枚のカードを評価し、quality 0 のカードが再確認ループに入り、「覚えた」で完了するフルフロー
      // 【期待される動作】: 通常カード全消化 → 再確認バッジ表示 → 2択ボタン表示 → 覚えた → 完了画面
      // 🔵 受け入れ基準 TC-001〜003, TC-101, TC-102, TC-501 より

      renderReviewPage();

      // Given: 3枚のカードでセッション開始（beforeEach でデフォルト設定済み）

      // When: カード1を quality 0 で評価（再確認キューに追加される）
      await waitForCard('質問1');
      await flipAndGrade(user, 0);

      // Then: カード2の通常表示で「再確認」バッジが非表示であること
      // 🔵 TC-101-02: 通常カードには再確認バッジが表示されない
      await waitForCard('質問2');
      expect(screen.queryByText('再確認')).not.toBeInTheDocument(); // 【確認内容】: 通常カード表示中は再確認バッジが出ない

      // When: カード2を quality 4 で評価
      await flipAndGrade(user, 4);

      // When: カード3を quality 5 で評価
      await waitForCard('質問3');
      await flipAndGrade(user, 5);

      // Then: 再確認モードに遷移し、「再確認」バッジが表示されること
      // 🔵 TC-101-01: 再確認カードに「再確認」バッジが表示される
      await waitForReconfirmMode();

      // Then: カード1の表面が表示されること
      expect(screen.getByText('質問1')).toBeInTheDocument(); // 【確認内容】: 再確認キューの先頭 card-1 が表示される

      // Then: 再確認モードでフリップ前から「覚えた」「覚えていない」の2択が表示されること
      // 🔵 TC-002-01: 再確認カードで2択が表示される（GradeButtons isReconfirmMode=true で常時表示）
      expect(screen.getByRole('button', { name: '覚えた' })).toBeInTheDocument(); // 【確認内容】: 覚えたボタンが表示されている
      expect(screen.getByRole('button', { name: '覚えていない' })).toBeInTheDocument(); // 【確認内容】: 覚えていないボタンが表示されている

      // Then: 通常の6段階評価ボタンが非表示であること
      // 🔵 TC-002-01: 0-5の評価ボタンは表示されない
      expect(screen.queryByLabelText('0 - 全く覚えていない')).not.toBeInTheDocument(); // 【確認内容】: 6段階ボタンが非表示

      // Then: スキップボタンが非表示であること
      // 🔵 TC-102-01: 再確認カードでスキップボタンが非表示
      expect(screen.queryByLabelText('スキップ')).not.toBeInTheDocument(); // 【確認内容】: スキップボタンが非表示

      // When: 「覚えた」を選択
      await clickRemembered(user);

      // Then: 完了画面に遷移すること
      await waitForComplete();
      // 🔵 TC-501-01: 完了画面に枚数表示
      expect(screen.getByText('3枚のカードを復習しました')).toBeInTheDocument(); // 【確認内容】: 全3枚が復習済みとして計上される

      // Then: API は3回のみ呼び出される（再確認中は API 呼び出しなし）
      // 🔵 TC-003-02: 「覚えた」選択で API が呼ばれない
      expect(mockSubmitReview).toHaveBeenCalledTimes(3); // 【確認内容】: 通常評価の3回のみ
      expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 0); // 【確認内容】: card-1 を quality 0 で評価
      expect(mockSubmitReview).toHaveBeenCalledWith('card-2', 4); // 【確認内容】: card-2 を quality 4 で評価
      expect(mockSubmitReview).toHaveBeenCalledWith('card-3', 5); // 【確認内容】: card-3 を quality 5 で評価
    });

    it('TC-INT-002: 通常復習→再確認→覚えていない→再表示→覚えた→完了', async () => {
      // 【テスト目的】: 「覚えていない」→キュー末尾再追加→再表示→「覚えた」のフルフロー検証
      // 【テスト内容】: 1枚のカードで quality 0 評価後、再確認で「覚えていない」→「覚えた」の流れ
      // 【期待される動作】: 「覚えていない」後に同カードが再表示され、「覚えた」で完了
      // 🔵 受け入れ基準 TC-004-01〜03 より

      // Given: 1枚のカードのみでセッション開始
      mockGetDueCards.mockResolvedValue({
        due_cards: [mockDueCards[0]],
        total_due_count: 1,
        next_due_date: null,
      });

      renderReviewPage();

      // When: カード1を quality 0 で評価
      await waitForCard('質問1');
      await flipAndGrade(user, 0);

      // Then: 再確認モードに遷移（「再確認」バッジ表示）
      await waitForReconfirmMode();
      expect(screen.getByText('再確認')).toBeInTheDocument(); // 【確認内容】: 再確認バッジが表示される

      // When: 「覚えていない」を選択
      // 🔵 TC-004-01: カードがキュー末尾に追加される
      await clickForgotten(user);

      // Then: 同じカードが再表示されること（「質問1」が再度表示）
      await waitForCard('質問1');
      expect(screen.getByText('質問1')).toBeInTheDocument(); // 【確認内容】: 同じカードが再表示される

      // Then: 再表示時にも「再確認」バッジが表示されること
      expect(screen.getByText('再確認')).toBeInTheDocument(); // 【確認内容】: 再表示時も再確認バッジが維持される

      // When: 「覚えた」を選択
      await clickRemembered(user);

      // Then: 完了画面に遷移
      await waitForComplete();

      // Then: API は1回のみ（初回 quality 0 のみ）
      // 🔵 TC-004-02: 「覚えていない」選択で API が呼ばれない
      expect(mockSubmitReview).toHaveBeenCalledTimes(1); // 【確認内容】: 再確認中は API 呼び出しなし
      expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 0); // 【確認内容】: 初回 quality 0 のみ
    });

    it('TC-INT-003: 通常カードと再確認カードの混在フロー（FIFO順序確認）', async () => {
      // 【テスト目的】: 通常カードと再確認カードの混在フローで FIFO 順序が維持されることを検証
      // 【テスト内容】: 3枚中2枚が再確認キューに入り、FIFO 順に再確認が行われる
      // 【期待される動作】: 通常カード優先→再確認カードが FIFO 順で表示→完了
      // 🟡 REQ-502 から妥当な推測

      renderReviewPage();

      // When: カード1を quality 1 で評価（再確認キュー: [card-1]）
      await waitForCard('質問1');
      await flipAndGrade(user, 1);

      // Then: カード2の通常表示で「再確認」バッジが非表示
      await waitForCard('質問2');
      // 🟡 通常カード表示中は再確認バッジが出ないことの確認
      expect(screen.queryByText('再確認')).not.toBeInTheDocument(); // 【確認内容】: 通常カード2表示中は再確認バッジなし

      // When: カード2を quality 0 で評価（再確認キュー: [card-1, card-2]）
      await flipAndGrade(user, 0);

      // Then: カード3の通常表示で「再確認」バッジが非表示
      await waitForCard('質問3');
      expect(screen.queryByText('再確認')).not.toBeInTheDocument(); // 【確認内容】: 通常カード3表示中も再確認バッジなし

      // When: カード3を quality 4 で評価（再確認キューに追加されない）
      await flipAndGrade(user, 4);

      // Then: 再確認モード遷移→カード1（FIFO先頭）が表示
      await waitForReconfirmMode();
      expect(screen.getByText('質問1')).toBeInTheDocument(); // 【確認内容】: FIFO 先頭の card-1 が最初に表示される

      // When: カード1をフリップ→「覚えた」
      await clickRemembered(user);

      // Then: カード2（FIFO2番目）が表示
      // 🟡 FIFO 順序の検証
      await waitForCard('質問2');
      expect(screen.getByText('再確認')).toBeInTheDocument(); // 【確認内容】: 再確認バッジが引き続き表示

      // When: カード2をフリップ→「覚えた」
      await clickRemembered(user);

      // Then: 完了画面に遷移
      await waitForComplete();
      expect(screen.getByText('3枚のカードを復習しました')).toBeInTheDocument(); // 【確認内容】: 全3枚が復習済みとして計上

      // Then: API は3回のみ
      expect(mockSubmitReview).toHaveBeenCalledTimes(3); // 【確認内容】: 通常評価の3回のみ（再確認中はなし）
    });
  });

  // ===========================================================
  // 2. エッジケーステスト
  // ===========================================================

  describe('エッジケーステスト', () => {
    it('TC-EDGE-001: 全カードが quality 0-2 → 全再確認 → 全覚えた → 完了', async () => {
      // 【テスト目的】: 全カードが再確認キューに入り、全て「覚えた」で完了する E2E フロー検証
      // 【テスト内容】: 3枚全てを quality 0-2 で評価し、再確認フェーズで全て「覚えた」
      // 【期待される動作】: 全カード再確認 → 全覚えた → 完了画面
      // 🟡 受け入れ基準 EDGE-101 より

      renderReviewPage();

      // When: 全カードを quality 0-2 で評価
      await waitForCard('質問1');
      await flipAndGrade(user, 0);

      await waitForCard('質問2');
      await flipAndGrade(user, 1);

      await waitForCard('質問3');
      await flipAndGrade(user, 2);

      // Then: 再確認モードに遷移
      await waitForReconfirmMode();

      // Then: 再確認フェーズでは6段階ボタンが表示されないこと
      // 🟡 再確認フェーズ全体を通じて6段階ボタンが一度も表示されないことを確認
      expect(screen.queryByLabelText('0 - 全く覚えていない')).not.toBeInTheDocument(); // 【確認内容】: 6段階ボタンが再確認フェーズで非表示

      // When: 全再確認カードで「覚えた」
      // 🟡 各カードで「再確認」バッジが表示されることを暗黙的に確認
      await clickRemembered(user); // card-1 (FIFO 1番目)
      await clickRemembered(user); // card-2 (FIFO 2番目)
      await clickRemembered(user); // card-3 (FIFO 3番目)

      // Then: 完了画面に遷移
      await waitForComplete();
      // 🟡 完了画面の枚数表示確認
      expect(screen.getByText('3枚のカードを復習しました')).toBeInTheDocument(); // 【確認内容】: 全3枚が復習済みとして計上

      // Then: API は3回のみ
      expect(mockSubmitReview).toHaveBeenCalledTimes(3); // 【確認内容】: 通常評価の3回のみ
    });

    it('TC-EDGE-002: 無限ループ（覚えていない3回繰り返し→4回目に覚えた）', async () => {
      // 【テスト目的】: 「覚えていない」を複数回繰り返してもアプリが正常動作することを検証
      // 【テスト内容】: 1枚のカードで「覚えていない」3回→「覚えた」1回
      // 【期待される動作】: 4回目でも正常に2択ボタン表示、最終的に完了画面
      // 🔵 受け入れ基準 EDGE-102, REQ-402 より

      // Given: 1枚のカードのみでセッション開始
      mockGetDueCards.mockResolvedValue({
        due_cards: [mockDueCards[0]],
        total_due_count: 1,
        next_due_date: null,
      });

      renderReviewPage();

      // When: quality 0 で評価
      await waitForCard('質問1');
      await flipAndGrade(user, 0);

      // Then: 再確認モードに遷移
      await waitForReconfirmMode();

      // When: 「覚えていない」3回繰り返し
      // 🔵 各回で API 呼び出しが発生しないことの暗黙的検証
      await clickForgotten(user);  // 1回目
      await waitForCard('質問1');  // 同じカードが再表示

      await clickForgotten(user);  // 2回目
      await waitForCard('質問1');

      await clickForgotten(user);  // 3回目
      await waitForCard('質問1');

      // Then: 4回目の表示でも「再確認」バッジ + 2択ボタンが正常
      // 🔵 EDGE-102: 4回目の表示でも正常表示
      expect(screen.getByText('再確認')).toBeInTheDocument(); // 【確認内容】: 4回目でも再確認バッジが維持される
      expect(screen.getByRole('button', { name: '覚えた' })).toBeInTheDocument(); // 【確認内容】: 「覚えた」ボタンが正常に表示
      expect(screen.getByRole('button', { name: '覚えていない' })).toBeInTheDocument(); // 【確認内容】: 「覚えていない」ボタンが正常に表示

      // When: 4回目で「覚えた」
      await clickRemembered(user);

      // Then: 完了画面に遷移
      await waitForComplete();

      // Then: API は1回のみ（初回 quality 0 のみ）
      expect(mockSubmitReview).toHaveBeenCalledTimes(1); // 【確認内容】: 再確認ループ中は API 非呼び出し
    });

    it('TC-EDGE-003: 複数カード再確認キューで覚えた/覚えていないが混在するフロー', async () => {
      // 【テスト目的】: 複数カードの再確認キューで覚えた/覚えていないが混在する場合のキュー順序検証
      // 【テスト内容】: 2枚のカードで再確認し、「覚えていない」のカードが後ろに回ることを確認
      // 【期待される動作】: card-1「覚えていない」→ card-2「覚えた」→ card-1「覚えた」→ 完了
      // 🟡 EDGE-101, EDGE-102 の組み合わせから妥当な推測

      // Given: 2枚のカードでセッション開始
      mockGetDueCards.mockResolvedValue({
        due_cards: [mockDueCards[0], mockDueCards[1]],
        total_due_count: 2,
        next_due_date: null,
      });

      renderReviewPage();

      // When: カード1を quality 0（再確認キュー: [card-1]）
      await waitForCard('質問1');
      await flipAndGrade(user, 0);

      // When: カード2を quality 1（再確認キュー: [card-1, card-2]）
      await waitForCard('質問2');
      await flipAndGrade(user, 1);

      // Then: 再確認モードに遷移
      await waitForReconfirmMode();

      // When: カード1→「覚えていない」（キュー: [card-2, card-1]）
      await clickForgotten(user);

      // Then: カード2が先に表示される（FIFO順序）
      // 🟡 「覚えていない」後に別カードが表示されることで FIFO 順序を検証
      await waitForCard('質問2');
      expect(screen.getByText('質問2')).toBeInTheDocument(); // 【確認内容】: card-2 が先に表示される（FIFO 順序維持）

      // When: カード2→「覚えた」（キュー: [card-1]）
      await clickRemembered(user);

      // Then: カード1が再表示される
      await waitForCard('質問1');
      expect(screen.getByText('質問1')).toBeInTheDocument(); // 【確認内容】: card-1 が後で表示される（キュー末尾再追加の確認）

      // When: カード1→「覚えた」（キュー: []）
      await clickRemembered(user);

      // Then: 完了画面に遷移
      await waitForComplete();

      // Then: API は2回のみ
      expect(mockSubmitReview).toHaveBeenCalledTimes(2); // 【確認内容】: 通常評価の2回のみ（再確認中はなし）
    });
  });

  // ===========================================================
  // 3. Undo 連携統合テスト
  // ===========================================================

  describe('Undo連携統合テスト', () => {
    it('TC-UNDO-001: Undo → regrade quality 3+ → 通常完了（再確認ループなし）', async () => {
      // 【テスト目的】: quality 0-2 評価→Undo→regrade quality 3+で再確認ループに入らないことを検証
      // 【テスト内容】: 1枚のカードで quality 0→覚えた→Undo→quality 4 regrade
      // 【期待される動作】: Undo 後の quality 3+ regrade で再確認キューに入らず通常完了
      // 🔵 受け入れ基準 TC-404-01, TC-404-03, EDGE-201 より

      // Given: 1枚のカードのみでセッション開始
      mockGetDueCards.mockResolvedValue({
        due_cards: [mockDueCards[0]],
        total_due_count: 1,
        next_due_date: null,
      });

      renderReviewPage();

      // When: quality 0 で評価
      await waitForCard('質問1');
      await flipAndGrade(user, 0);

      // When: 再確認「覚えた」
      await waitForReconfirmMode();
      await clickRemembered(user);

      // Then: 完了画面に遷移
      await waitForComplete();

      // When: Undo ボタンクリック
      const undoButton = screen.getByLabelText('質問1 を再採点する');
      await user.click(undoButton);

      // Then: 再採点モードに遷移
      await waitFor(() => {
        expect(screen.getByText('再採点')).toBeInTheDocument();
      }); // 【確認内容】: 再採点モードテキストが表示される

      // When: quality 4 で regrade
      await flipAndGrade(user, 4);

      // Then: 直接完了画面に戻る（再確認ループに入らない）
      await waitForComplete();

      // Then: API 呼び出し回数の確認
      // 🔵 undoReview 1回、submitReview 2回
      expect(mockUndoReview).toHaveBeenCalledTimes(1); // 【確認内容】: undoReview が1回呼ばれた
      expect(mockSubmitReview).toHaveBeenCalledTimes(2); // 【確認内容】: 初回 q0 + regrade q4 の2回
      expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 0); // 【確認内容】: 初回 quality 0
      expect(mockSubmitReview).toHaveBeenLastCalledWith('card-1', 4); // 【確認内容】: regrade quality 4
    });

    it('TC-UNDO-002: Undo → regrade quality 0-2 → API 呼び出し確認', async () => {
      // 【テスト目的】: Undo 後の quality 0-2 regrade で API が正しく呼び出されることを検証
      // 【テスト内容】: 1枚のカードで quality 4→Undo→quality 2 regrade→submitReview 2回
      // 【期待される動作】: regrade quality 0-2 で submitReview が呼ばれること
      // 🟡 受け入れ基準 TC-404-02, EDGE-202 より
      //
      // 【テスト上の注意】:
      //   既存実装では regradeMode の場合、handleGrade は submitReview 後に
      //   setIsComplete(true) を呼び出す設計のため、regrade 後のフロー確認は
      //   API 呼び出し確認を主眼とする。

      // Given: 1枚のカードのみでセッション開始
      mockGetDueCards.mockResolvedValue({
        due_cards: [mockDueCards[0]],
        total_due_count: 1,
        next_due_date: null,
      });

      renderReviewPage();

      // When: quality 4 で評価
      await waitForCard('質問1');
      await flipAndGrade(user, 4);

      // Then: 完了画面に遷移
      await waitForComplete();

      // When: Undo
      const undoButton = screen.getByLabelText('質問1 を再採点する');
      await user.click(undoButton);

      // Then: 再採点モードに遷移
      await waitFor(() => {
        expect(screen.getByText('再採点')).toBeInTheDocument();
      }); // 【確認内容】: 再採点テキストが表示される

      // When: quality 2 で regrade → submitReview が呼ばれる
      await flipAndGrade(user, 2);

      // Then: API 呼び出し回数の確認
      // 🟡 undoReview 1回、submitReview 2回
      await waitFor(() => {
        expect(mockUndoReview).toHaveBeenCalledTimes(1); // 【確認内容】: undoReview が1回呼ばれた
        expect(mockSubmitReview).toHaveBeenCalledTimes(2); // 【確認内容】: 初回 q4 + regrade q2 の2回
        expect(mockSubmitReview).toHaveBeenLastCalledWith('card-1', 2); // 【確認内容】: regrade quality 2
      });
    });

    it('TC-UNDO-003: 複数カードの1枚を Undo → 他カードの再確認結果に影響なし', async () => {
      // 【テスト目的】: 1枚の Undo が他カードの再確認結果に影響しないことを検証
      // 【テスト内容】: 3枚中2枚が再確認済み→1枚を Undo→他カードの結果が変わらない
      // 【期待される動作】: card-1 のみ regrade、card-3 は reconfirmed のまま
      // 🟡 REQ-404、EDGE-201 から妥当な推測

      renderReviewPage();

      // When: カード1を quality 0（再確認キュー: [card-1]）
      await waitForCard('質問1');
      await flipAndGrade(user, 0);

      // When: カード2を quality 4（通常完了）
      await waitForCard('質問2');
      await flipAndGrade(user, 4);

      // When: カード3を quality 1（再確認キュー: [card-1, card-3]）
      await waitForCard('質問3');
      await flipAndGrade(user, 1);

      // When: 再確認: card-1「覚えた」
      await waitForReconfirmMode();
      await clickRemembered(user); // card-1

      // When: 再確認: card-3「覚えた」
      await clickRemembered(user); // card-3

      // Then: 完了画面に遷移
      await waitForComplete();

      // When: カード1を Undo
      const undoButton = screen.getByLabelText('質問1 を再採点する');
      await user.click(undoButton);

      // Then: 再採点モードに遷移
      await waitFor(() => {
        expect(screen.getByText('再採点')).toBeInTheDocument();
      }); // 【確認内容】: 再採点テキストが表示される

      // When: quality 5 で regrade
      await flipAndGrade(user, 5);

      // Then: 完了画面に戻る
      await waitForComplete();

      // Then: API 呼び出し回数の確認
      // 🟡 undoReview 1回、submitReview 4回（card-1(q0), card-2(q4), card-3(q1), card-1(regrade q5)）
      expect(mockUndoReview).toHaveBeenCalledTimes(1); // 【確認内容】: undoReview が1回のみ呼ばれた
      expect(mockSubmitReview).toHaveBeenCalledTimes(4); // 【確認内容】: 通常3回 + regrade 1回 = 4回
    });
  });

  // ===========================================================
  // 4. 回帰テスト
  // ===========================================================

  describe('回帰テスト', () => {
    it('TC-REG-001: quality 3-5 のみのフローが変更なく動作する', async () => {
      // 【テスト目的】: 再確認機能追加後も quality 3-5 フローが変更なく動作することを検証
      // 【テスト内容】: 3枚全てを quality 4 で評価し、再確認関連UIが一切表示されないことを確認
      // 【期待される動作】: 通常の6段階評価→完了画面（再確認なし）
      // 🟡 既存テスト維持の妥当な推測

      renderReviewPage();

      // When: 全カードを quality 4 で評価
      await waitForCard('質問1');
      // Then: 通常カード表示中に「再確認」バッジが非表示
      expect(screen.queryByText('再確認')).not.toBeInTheDocument(); // 【確認内容】: カード1表示中は再確認バッジなし
      await flipAndGrade(user, 4);

      await waitForCard('質問2');
      expect(screen.queryByText('再確認')).not.toBeInTheDocument(); // 【確認内容】: カード2表示中は再確認バッジなし
      await flipAndGrade(user, 4);

      await waitForCard('質問3');
      expect(screen.queryByText('再確認')).not.toBeInTheDocument(); // 【確認内容】: カード3表示中は再確認バッジなし
      await flipAndGrade(user, 4);

      // Then: 直接完了画面に遷移（再確認フェーズなし）
      await waitForComplete();
      expect(screen.getByText('3枚のカードを復習しました')).toBeInTheDocument(); // 【確認内容】: 全3枚が通常評価で計上

      // Then: 「覚えた」「覚えていない」ボタンが表示されなかったことを確認
      // （完了画面には Undo ボタンはあるが「覚えた」ボタンは存在しない）
      expect(screen.queryByRole('button', { name: '覚えた' })).not.toBeInTheDocument(); // 【確認内容】: 再確認ボタンが表示されない
      expect(screen.queryByRole('button', { name: '覚えていない' })).not.toBeInTheDocument(); // 【確認内容】: 再確認ボタンが表示されない

      // Then: API は3回呼び出される
      expect(mockSubmitReview).toHaveBeenCalledTimes(3); // 【確認内容】: 通常評価の3回
    });

    it('TC-REG-002: スキップフローが変更なく動作する', async () => {
      // 【テスト目的】: スキップ操作が再確認機能の影響を受けないことを検証
      // 【テスト内容】: 3枚全てをスキップし、再確認キューが空のまま完了すること
      // 【期待される動作】: 全スキップ→完了画面（0枚復習、再確認なし）
      // 🟡 既存テスト維持の妥当な推測

      renderReviewPage();

      // When: 全カードをスキップ
      await waitForCard('質問1');
      await flipAndSkip(user);

      await waitForCard('質問2');
      await flipAndSkip(user);

      await waitForCard('質問3');
      await flipAndSkip(user);

      // Then: 完了画面に遷移（再確認フェーズなし）
      await waitForComplete();
      // 🟡 スキップのみなので0枚表示
      expect(screen.getByText('0枚のカードを復習しました')).toBeInTheDocument(); // 【確認内容】: スキップのため0枚と表示

      // Then: API は呼び出されない
      expect(mockSubmitReview).not.toHaveBeenCalled(); // 【確認内容】: スキップは API 呼び出しなし

      // Then: 再確認バッジが表示されなかったこと
      expect(screen.queryByText('再確認')).not.toBeInTheDocument(); // 【確認内容】: 再確認バッジが一度も表示されない
    });

    it('TC-REG-003: quality 0-2 + スキップの混在フロー', async () => {
      // 【テスト目的】: quality 0-2 とスキップが混在する場合の動作を検証
      // 【テスト内容】: カード1を quality 1、カード2,3をスキップし、再確認後に完了
      // 【期待される動作】: 1枚のみ再確認ループ→覚えた→完了（1枚復習）
      // 🟡 REQ-001, REQ-103 から妥当な推測

      renderReviewPage();

      // When: カード1を quality 1 で評価（再確認キュー: [card-1]）
      await waitForCard('質問1');
      await flipAndGrade(user, 1);

      // When: カード2をスキップ
      await waitForCard('質問2');
      await flipAndSkip(user);

      // When: カード3をスキップ
      await waitForCard('質問3');
      await flipAndSkip(user);

      // Then: 再確認モードに遷移
      await waitForReconfirmMode();
      expect(screen.getByText('質問1')).toBeInTheDocument(); // 【確認内容】: スキップされたカードは再確認キューに入らない（card-1 のみ）

      // When: カード1をフリップ→「覚えた」
      await clickRemembered(user);

      // Then: 完了画面に遷移
      await waitForComplete();
      // 🟡 1枚のみ復習済み
      expect(screen.getByText('1枚のカードを復習しました')).toBeInTheDocument(); // 【確認内容】: 1枚のみ（スキップ2枚は計上されない）

      // Then: API は1回のみ
      expect(mockSubmitReview).toHaveBeenCalledTimes(1); // 【確認内容】: card-1 の quality 1 のみ
      expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 1); // 【確認内容】: card-1 を quality 1 で評価
    });
  });
});

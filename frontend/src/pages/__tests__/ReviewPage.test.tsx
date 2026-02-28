import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ReviewPage } from '../ReviewPage';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

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

const mockDueCards = [
  { card_id: 'card-1', front: '質問1', back: '解答1', overdue_days: 0 },
  { card_id: 'card-2', front: '質問2', back: '解答2', overdue_days: 1 },
  { card_id: 'card-3', front: '質問3', back: '解答3', overdue_days: 2 },
];

const renderReviewPage = () => {
  return render(
    <MemoryRouter>
      <ReviewPage />
    </MemoryRouter>
  );
};

describe('ReviewPage', () => {
  const mockReviewResponse = (cardId: string, grade: number) => ({
    card_id: cardId,
    grade,
    previous: { ease_factor: 2.5, interval: 1, repetitions: 0, due_date: null },
    updated: { ease_factor: 2.6, interval: 1, repetitions: 1, due_date: '2026-03-01' },
    reviewed_at: '2026-02-28T10:00:00Z',
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockGetDueCards.mockResolvedValue({
      due_cards: mockDueCards,
      total_due_count: 3,
      next_due_date: null,
    });
    mockSubmitReview.mockImplementation((cardId: string, grade: number) =>
      Promise.resolve(mockReviewResponse(cardId, grade))
    );
    mockUndoReview.mockResolvedValue({
      card_id: 'card-1',
      restored: { ease_factor: 2.5, interval: 1, repetitions: 0, due_date: '2026-02-28' },
      undone_at: '2026-02-28T10:01:00Z',
    });
  });

  describe('テストケース1: ローディング表示', () => {
    it('API レスポンス前にローディングが表示される', () => {
      mockGetDueCards.mockReturnValue(new Promise(() => {}));
      renderReviewPage();
      expect(screen.getByText('復習カードを読み込み中...')).toBeInTheDocument();
    });
  });

  describe('テストケース2: カード表示', () => {
    it('ローディング完了後に最初のカードの表面が表示される', async () => {
      renderReviewPage();
      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });
    });

    it('進捗が「1 / 3」と表示される', async () => {
      renderReviewPage();
      await waitFor(() => {
        expect(screen.getByText('1 / 3')).toBeInTheDocument();
      });
    });
  });

  describe('テストケース3: 空状態表示', () => {
    it('0枚の場合に空状態メッセージが表示される', async () => {
      mockGetDueCards.mockResolvedValue({
        due_cards: [],
        total_due_count: 0,
        next_due_date: null,
      });
      renderReviewPage();
      await waitFor(() => {
        expect(screen.getByText('復習対象のカードはありません')).toBeInTheDocument();
      });
    });
  });

  describe('テストケース4: フリップ操作', () => {
    it('カードクリックで裏面が表示される', async () => {
      const user = userEvent.setup();
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      const card = screen.getByRole('button', { name: /カード表面を表示中/ });
      await user.click(card);

      expect(screen.getByRole('button', { name: /カード裏面を表示中/ })).toBeInTheDocument();
    });

    it('フリップ後に採点ボタンが表示される', async () => {
      const user = userEvent.setup();
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      const card = screen.getByRole('button', { name: /カード表面を表示中/ });
      await user.click(card);

      expect(screen.getByLabelText('スキップ')).toBeInTheDocument();
    });

    it('フリップ前は採点ボタンが非表示', async () => {
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      expect(screen.queryByLabelText('スキップ')).not.toBeInTheDocument();
    });
  });

  describe('テストケース5: 採点送信', () => {
    it('採点ボタンクリックでAPIが送信される', async () => {
      const user = userEvent.setup();
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // フリップ
      const card = screen.getByRole('button', { name: /カード表面を表示中/ });
      await user.click(card);

      // 採点
      const gradeButton = screen.getByLabelText('4 - やや迷ったが正解');
      await user.click(gradeButton);

      expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 4);
    });

    it('採点後に次のカードに進む', async () => {
      const user = userEvent.setup();
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // フリップ → 採点
      const card = screen.getByRole('button', { name: /カード表面を表示中/ });
      await user.click(card);
      const gradeButton = screen.getByLabelText('4 - やや迷ったが正解');
      await user.click(gradeButton);

      await waitFor(() => {
        expect(screen.getByText('質問2')).toBeInTheDocument();
      });
    });

    it('次のカードは表面から表示される', async () => {
      const user = userEvent.setup();
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // フリップ → 採点
      const card = screen.getByRole('button', { name: /カード表面を表示中/ });
      await user.click(card);
      const gradeButton = screen.getByLabelText('4 - やや迷ったが正解');
      await user.click(gradeButton);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /カード表面を表示中/ })).toBeInTheDocument();
      });
    });
  });

  describe('テストケース6: スキップ', () => {
    it('スキップでAPI送信なしで次のカードに進む', async () => {
      const user = userEvent.setup();
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // フリップ → スキップ
      const card = screen.getByRole('button', { name: /カード表面を表示中/ });
      await user.click(card);
      const skipButton = screen.getByLabelText('スキップ');
      await user.click(skipButton);

      await waitFor(() => {
        expect(screen.getByText('質問2')).toBeInTheDocument();
      });
      expect(mockSubmitReview).not.toHaveBeenCalled();
    });
  });

  describe('テストケース7: 復習完了', () => {
    it('最後のカード採点後に完了画面が表示される', async () => {
      const user = userEvent.setup();
      mockGetDueCards.mockResolvedValue({
        due_cards: [mockDueCards[0]],
        total_due_count: 1,
        next_due_date: null,
      });
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // フリップ → 採点
      const card = screen.getByRole('button', { name: /カード表面を表示中/ });
      await user.click(card);
      const gradeButton = screen.getByLabelText('5 - 完璧');
      await user.click(gradeButton);

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
        expect(screen.getByText('1枚のカードを復習しました')).toBeInTheDocument();
      });
    });
  });

  describe('テストケース8: APIエラー（初期読み込み）', () => {
    it('取得エラー時にエラーメッセージとリトライボタンが表示される', async () => {
      mockGetDueCards.mockRejectedValue(new Error('Network error'));
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('復習カードの取得に失敗しました')).toBeInTheDocument();
      });
      expect(screen.getByText('再試行')).toBeInTheDocument();
    });

    it('リトライボタンで再取得される', async () => {
      const user = userEvent.setup();
      mockGetDueCards.mockRejectedValueOnce(new Error('Network error'));
      mockGetDueCards.mockResolvedValueOnce({
        due_cards: mockDueCards,
        total_due_count: 3,
        next_due_date: null,
      });
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('再試行')).toBeInTheDocument();
      });

      await user.click(screen.getByText('再試行'));

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });
    });
  });

  describe('テストケース9: APIエラー（採点送信）', () => {
    it('採点送信エラー時にエラーメッセージが表示される', async () => {
      const user = userEvent.setup();
      mockSubmitReview.mockRejectedValue(new Error('Submit error'));
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // フリップ → 採点
      const card = screen.getByRole('button', { name: /カード表面を表示中/ });
      await user.click(card);
      const gradeButton = screen.getByLabelText('4 - やや迷ったが正解');
      await user.click(gradeButton);

      await waitFor(() => {
        expect(screen.getByText('採点の送信に失敗しました')).toBeInTheDocument();
      });
    });
  });

  describe('テストケース10: 進捗バー更新', () => {
    it('2枚目で「2 / 3」と表示される', async () => {
      const user = userEvent.setup();
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // カード1をフリップ → 採点 → カード2へ
      const card = screen.getByRole('button', { name: /カード表面を表示中/ });
      await user.click(card);
      const gradeButton = screen.getByLabelText('4 - やや迷ったが正解');
      await user.click(gradeButton);

      await waitFor(() => {
        expect(screen.getByText('2 / 3')).toBeInTheDocument();
      });
    });
  });

  describe('戻るボタン', () => {
    it('戻るボタンクリックでnavigate(-1)が呼ばれる', async () => {
      const user = userEvent.setup();
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      const backButton = screen.getByLabelText('戻る');
      await user.click(backButton);

      expect(mockNavigate).toHaveBeenCalledWith(-1);
    });
  });

  // --- TASK-0072: 統合テスト + エッジケース ---

  describe('統合テスト: 復習セッション全体フロー', () => {
    it('3枚中2枚採点・1枚スキップで完了画面に「2枚」と表示される', async () => {
      const user = userEvent.setup();
      renderReviewPage();

      // カード1: フリップ → 採点(4)
      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('4 - やや迷ったが正解'));

      // カード2: フリップ → スキップ
      await waitFor(() => {
        expect(screen.getByText('質問2')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('スキップ'));

      // カード3: フリップ → 採点(5)
      await waitFor(() => {
        expect(screen.getByText('質問3')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('5 - 完璧'));

      // 完了画面
      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
        expect(screen.getByText('2枚のカードを復習しました')).toBeInTheDocument();
      });

      // API呼び出しの確認
      expect(mockSubmitReview).toHaveBeenCalledTimes(2);
      expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 4);
      expect(mockSubmitReview).toHaveBeenCalledWith('card-3', 5);
    });

    it('完了画面に「ホームに戻る」リンクがある', async () => {
      const user = userEvent.setup();
      mockGetDueCards.mockResolvedValue({
        due_cards: [mockDueCards[0]],
        total_due_count: 1,
        next_due_date: null,
      });
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('5 - 完璧'));

      await waitFor(() => {
        expect(screen.getByText('ホームに戻る')).toBeInTheDocument();
      });
      expect(screen.getByText('ホームに戻る').closest('a')).toHaveAttribute('href', '/');
    });
  });

  describe('エッジケース: カード1枚のみ', () => {
    it('1枚を採点すると即座に完了画面に遷移する', async () => {
      const user = userEvent.setup();
      mockGetDueCards.mockResolvedValue({
        due_cards: [{ card_id: 'card-single', front: '単独質問', back: '単独解答', overdue_days: 0 }],
        total_due_count: 1,
        next_due_date: null,
      });
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('単独質問')).toBeInTheDocument();
      });
      expect(screen.getByText('1 / 1')).toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('3 - 難しかったが正解'));

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
        expect(screen.getByText('1枚のカードを復習しました')).toBeInTheDocument();
      });
    });
  });

  describe('エッジケース: 全カードスキップ', () => {
    it('全カードスキップで完了画面に「0枚」と表示される', async () => {
      const user = userEvent.setup();
      renderReviewPage();

      // カード1: フリップ → スキップ
      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('スキップ'));

      // カード2: フリップ → スキップ
      await waitFor(() => {
        expect(screen.getByText('質問2')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('スキップ'));

      // カード3: フリップ → スキップ
      await waitFor(() => {
        expect(screen.getByText('質問3')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('スキップ'));

      // 完了画面
      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
        expect(screen.getByText('0枚のカードを復習しました')).toBeInTheDocument();
      });

      expect(mockSubmitReview).not.toHaveBeenCalled();
    });
  });

  describe('エッジケース: 初期読み込みエラーからのリトライ', () => {
    it('リトライ成功後にカードが表示される', async () => {
      const user = userEvent.setup();
      mockGetDueCards
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          due_cards: mockDueCards,
          total_due_count: 3,
          next_due_date: null,
        });
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('復習カードの取得に失敗しました')).toBeInTheDocument();
      });

      await user.click(screen.getByText('再試行'));

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });
      expect(mockGetDueCards).toHaveBeenCalledTimes(2);
    });
  });

  describe('アクセシビリティ', () => {
    it('FlipCard に role="button" が設定されている', async () => {
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /カード表面を表示中/ })).toBeInTheDocument();
    });

    it('進捗バーに role="progressbar" が設定されている', async () => {
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });

    it('戻るボタンに aria-label が設定されている', async () => {
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      expect(screen.getByLabelText('戻る')).toBeInTheDocument();
    });

    it('エラーメッセージに role="alert" が設定されている', async () => {
      const user = userEvent.setup();
      mockSubmitReview.mockRejectedValue(new Error('Submit error'));
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('4 - やや迷ったが正解'));

      await waitFor(() => {
        expect(screen.getByRole('alert')).toHaveTextContent('採点の送信に失敗しました');
      });
    });
  });

  // --- TASK-0077: Undo/再採点フロー統合 ---

  describe('Undoフロー: 正常系', () => {
    const gradeAndComplete = async (user: ReturnType<typeof userEvent.setup>) => {
      mockGetDueCards.mockResolvedValue({
        due_cards: [mockDueCards[0]],
        total_due_count: 1,
        next_due_date: null,
      });
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // Flip and grade
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('4 - やや迷ったが正解'));

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });
    };

    it('取り消しボタン押下でUndo APIが呼ばれる', async () => {
      const user = userEvent.setup();
      await gradeAndComplete(user);

      // Click undo button
      const undoButton = screen.getByLabelText('質問1 の採点を取り消す');
      await user.click(undoButton);

      expect(mockUndoReview).toHaveBeenCalledWith('card-1');
    });

    it('Undo成功後に再採点モードに遷移する', async () => {
      const user = userEvent.setup();
      await gradeAndComplete(user);

      // Click undo button
      const undoButton = screen.getByLabelText('質問1 の採点を取り消す');
      await user.click(undoButton);

      // Should show regrade mode with the card
      await waitFor(() => {
        expect(screen.getByText('再採点')).toBeInTheDocument();
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });
    });

    it('再採点モードではスキップボタンが表示されない', async () => {
      const user = userEvent.setup();
      await gradeAndComplete(user);

      const undoButton = screen.getByLabelText('質問1 の採点を取り消す');
      await user.click(undoButton);

      await waitFor(() => {
        expect(screen.getByText('再採点')).toBeInTheDocument();
      });

      // Flip the card
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));

      // Skip button should not be visible in regrade mode
      expect(screen.queryByLabelText('スキップ')).not.toBeInTheDocument();
    });

    it('再採点完了後に結果が更新されて完了画面に戻る', async () => {
      const user = userEvent.setup();
      await gradeAndComplete(user);

      // Undo
      const undoButton = screen.getByLabelText('質問1 の採点を取り消す');
      await user.click(undoButton);

      await waitFor(() => {
        expect(screen.getByText('再採点')).toBeInTheDocument();
      });

      // Flip and regrade
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('5 - 完璧'));

      // Should return to complete screen
      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });

      // submitReview should have been called twice (original + regrade)
      expect(mockSubmitReview).toHaveBeenCalledTimes(2);
      expect(mockSubmitReview).toHaveBeenLastCalledWith('card-1', 5);
    });
  });

  describe('Undoフロー: エラー系', () => {
    const gradeAndComplete = async (user: ReturnType<typeof userEvent.setup>) => {
      mockGetDueCards.mockResolvedValue({
        due_cards: [mockDueCards[0]],
        total_due_count: 1,
        next_due_date: null,
      });
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('4 - やや迷ったが正解'));

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });
    };

    it('Undo APIエラー時に完了画面に留まる', async () => {
      const user = userEvent.setup();
      mockUndoReview.mockRejectedValue(new Error('Undo failed'));
      await gradeAndComplete(user);

      const undoButton = screen.getByLabelText('質問1 の採点を取り消す');
      await user.click(undoButton);

      // Should stay on complete screen with error
      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
        expect(screen.getByRole('alert')).toHaveTextContent('取り消しに失敗しました');
      });
    });

    it('再採点APIエラー時にundone状態のまま完了画面に戻る', async () => {
      const user = userEvent.setup();
      await gradeAndComplete(user);

      // Undo succeeds
      const undoButton = screen.getByLabelText('質問1 の採点を取り消す');
      await user.click(undoButton);

      await waitFor(() => {
        expect(screen.getByText('再採点')).toBeInTheDocument();
      });

      // Regrade fails
      mockSubmitReview.mockRejectedValueOnce(new Error('Regrade failed'));
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('3 - 難しかったが正解'));

      // Should return to complete screen with undone status
      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });

      // The card should show as undone (取り消し済み)
      expect(screen.getByText('取り消し済み')).toBeInTheDocument();
    });
  });
});

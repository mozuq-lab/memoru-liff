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

vi.mock('@/services/api', () => ({
  cardsApi: {
    getDueCards: (...args: unknown[]) => mockGetDueCards(...args),
  },
  reviewsApi: {
    submitReview: (...args: unknown[]) => mockSubmitReview(...args),
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
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetDueCards.mockResolvedValue({
      due_cards: mockDueCards,
      total_due_count: 3,
      next_due_date: null,
    });
    mockSubmitReview.mockResolvedValue(undefined);
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
});

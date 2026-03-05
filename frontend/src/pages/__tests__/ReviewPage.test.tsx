import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ReviewPage } from '../ReviewPage';
import type { ReconfirmCard, SessionCardResultType } from '@/types/card';

const mockNavigate = vi.fn();

// ============================================================
// TASK-0149: 停止トグル修正テスト用モック
// 【テスト前準備】: useSpeech hook をモックして isSpeaking/speak/cancel を制御可能にする
// 【設計方針】: 既存テストへの影響を避けるため isSupported=false をデフォルトとする
//              新しいテストでのみ isSupported=true/isSpeaking=true に上書き
// 🔵 青信号: note.md の useSpeech 仕様 + testcases.md のモック戦略より
// ============================================================

const mockSpeak = vi.fn();
const mockCancel = vi.fn();
// isSpeaking の状態をテストで制御可能にするため、let で宣言
// 既存テストでは false のまま（SpeechButton が非表示）
let mockIsSpeaking = false;
// isSupported をテストで制御可能にする
// 既存テストでは false のまま（SpeechButton が非表示となり既存テストに影響なし）
let mockIsSupported = false;

vi.mock('@/hooks/useSpeech', () => ({
  useSpeech: () => ({
    isSpeaking: mockIsSpeaking,
    isSupported: mockIsSupported,
    speak: mockSpeak,
    cancel: mockCancel,
  }),
}));

// 【テスト前準備】: useAuth hook をモックして userId を提供
// 🔵 青信号: SettingsPage.test.tsx の既存パターンより
vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    user: {
      profile: { sub: 'test-user' },
    },
    isAuthenticated: true,
    isLoading: false,
    logout: vi.fn(),
  }),
}));

// 【テスト前準備】: useSpeechSettings hook をモックして settings を提供
// 🔵 青信号: SettingsPage.test.tsx の既存パターンより
vi.mock('@/hooks/useSpeechSettings', () => ({
  useSpeechSettings: () => ({
    settings: { autoPlay: false, rate: 1 },
    updateSettings: vi.fn(),
  }),
}));

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
      const undoButton = screen.getByLabelText('質問1 を再採点する');
      await user.click(undoButton);

      expect(mockUndoReview).toHaveBeenCalledWith('card-1');
    });

    it('Undo成功後に再採点モードに遷移する', async () => {
      const user = userEvent.setup();
      await gradeAndComplete(user);

      // Click undo button
      const undoButton = screen.getByLabelText('質問1 を再採点する');
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

      const undoButton = screen.getByLabelText('質問1 を再採点する');
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
      const undoButton = screen.getByLabelText('質問1 を再採点する');
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

      const undoButton = screen.getByLabelText('質問1 を再採点する');
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
      const undoButton = screen.getByLabelText('質問1 を再採点する');
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

  // ============================================================
  // TASK-0081: 再確認ループ コアロジック
  // ============================================================

  // --- 型定義のコンパイル確認 (型レベルテスト) ---
  describe('型定義: ReconfirmCard / SessionCardResultType 拡張', () => {
    it("'reconfirmed' を SessionCardResultType として代入できる (型コンパイル確認)", () => {
      // このテストは型レベルの確認。実行時エラーが出なければOK
      const type: SessionCardResultType = 'reconfirmed';
      expect(type).toBe('reconfirmed');
    });

    it('ReconfirmCard インターフェースが4つの必須フィールドを持つ (型コンパイル確認)', () => {
      const card: ReconfirmCard = {
        cardId: 'card-1',
        front: '質問1',
        back: '解答1',
        originalGrade: 0,
      };
      expect(card.cardId).toBe('card-1');
      expect(card.front).toBe('質問1');
      expect(card.back).toBe('解答1');
      expect(card.originalGrade).toBe(0);
    });

    it('SessionCardResult に reconfirmResult フィールドを追加できる (型コンパイル確認)', () => {
      const result = {
        cardId: 'card-1',
        front: '質問1',
        type: 'reconfirmed' as SessionCardResultType,
        reconfirmResult: 'remembered' as const,
      };
      expect(result.reconfirmResult).toBe('remembered');
    });
  });

  // --- 再確認キュー追加: Normal mode ---
  describe('再確認キュー追加: Normal mode', () => {
    // TC-TDD-020-01
    it('quality 0 選択時に再確認キューに追加され、通常カード消化後に再確認モードに遷移する', async () => {
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

      // フリップ → quality 0 で採点
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('0 - 全く覚えていない'));

      // submitReview が card-1, 0 で呼ばれる
      await waitFor(() => {
        expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 0);
      });

      // quality 0 → reconfirmQueue に追加 → 通常カード全消化後に再確認モード遷移
      // 完了画面 (復習完了!) に遷移しない (isReconfirmMode = true になるため)
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });
    });

    // TC-TDD-020-02
    it('quality 1 選択時に再確認キューに追加され、通常カード消化後に再確認モードに遷移する', async () => {
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
      await user.click(screen.getByLabelText('1 - 間違えた'));

      await waitFor(() => {
        expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 1);
      });

      // 完了画面に遷移しない
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });
    });

    // TC-TDD-020-03
    it('quality 2 選択時に再確認キューに追加され、通常カード消化後に再確認モードに遷移する', async () => {
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
      await user.click(screen.getByLabelText('2 - 間違えたが見覚えあり'));

      await waitFor(() => {
        expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 2);
      });

      // 完了画面に遷移しない
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });
    });

    // TC-TDD-020-04
    it('quality 3 選択時に再確認キューに追加されず、セッションが直接完了する', async () => {
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
      await user.click(screen.getByLabelText('3 - 難しかったが正解'));

      // reconfirmQueue には追加されない → 完了画面に遷移
      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });
      expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 3);
    });

    // TC-TDD-020-05
    it('quality 4 選択時に再確認キューに追加されず、セッションが直接完了する', async () => {
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
      await user.click(screen.getByLabelText('4 - やや迷ったが正解'));

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });
    });

    // TC-TDD-020-06
    it('quality 5 選択時に再確認キューに追加されず、セッションが直接完了する', async () => {
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
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });
    });
  });

  // --- 再確認キュー追加: Regrade mode ---
  describe('再確認キュー追加: Regrade mode', () => {
    const gradeAndCompleteWith4 = async (user: ReturnType<typeof userEvent.setup>) => {
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

    // TC-TDD-021-01
    it('Undo 後の再採点で quality 2 を選択すると再確認モードに遷移する', async () => {
      const user = userEvent.setup();
      await gradeAndCompleteWith4(user);

      // Undo
      const undoButton = screen.getByLabelText('質問1 を再採点する');
      await user.click(undoButton);

      await waitFor(() => {
        expect(screen.getByText('再採点')).toBeInTheDocument();
      });

      // regrade: quality 2 → reconfirmQueue に追加 → 再確認モードに遷移
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('2 - 間違えたが見覚えあり'));

      // submitReview が 2 回呼ばれる (初回 quality 4 + regrade quality 2)
      await waitFor(() => {
        expect(mockSubmitReview).toHaveBeenCalledTimes(2);
        expect(mockSubmitReview).toHaveBeenLastCalledWith('card-1', 2);
      });

      // regrade で quality < 3 → 再確認モードに遷移（完了画面ではない）
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
        expect(screen.getByText('再確認')).toBeInTheDocument();
      });

      // 「覚えた」でセッション完了
      const rememberedButton = screen.getByRole('button', { name: '覚えた' });
      await user.click(rememberedButton);

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });
    });

    // TC-TDD-021-02
    it('Undo 後の再採点で quality 4 を選択すると再確認キューに追加されない', async () => {
      const user = userEvent.setup();
      await gradeAndCompleteWith4(user);

      // Undo
      const undoButton = screen.getByLabelText('質問1 を再採点する');
      await user.click(undoButton);

      await waitFor(() => {
        expect(screen.getByText('再採点')).toBeInTheDocument();
      });

      // regrade: quality 4 → reconfirmQueue に追加されない
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('4 - やや迷ったが正解'));

      // 通常の完了画面に戻る
      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });

      expect(mockSubmitReview).toHaveBeenCalledTimes(2);
    });
  });

  // --- handleReconfirmRemembered: 「覚えた」ハンドラ ---
  describe('handleReconfirmRemembered: 「覚えた」ハンドラ', () => {
    // quality 0 で評価して再確認モードに入るヘルパー
    const gradeWithQuality0AndEnterReconfirm = async (user: ReturnType<typeof userEvent.setup>) => {
      mockGetDueCards.mockResolvedValue({
        due_cards: [mockDueCards[0]],
        total_due_count: 1,
        next_due_date: null,
      });
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // quality 0 で評価 → reconfirmQueue に追加 → isReconfirmMode = true
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('0 - 全く覚えていない'));

      // 再確認モードに入る (完了画面ではない)
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });
    };

    // TC-TDD-030-01
    it('再確認モードで「覚えた」を選択するとカードがキューから除外され、キューが空ならセッション完了する', async () => {
      const user = userEvent.setup();
      await gradeWithQuality0AndEnterReconfirm(user);

      // 再確認モードで「覚えた」ボタンをクリック
      // TASK-0082 で UI が実装されるまでは aria-label="覚えた" ボタンが存在しない
      // → このテストは RED フェーズで FAIL することが期待される
      const rememberedButton = screen.getByRole('button', { name: '覚えた' });
      await user.click(rememberedButton);

      // reconfirmQueue が空になる → セッション完了
      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });
    });

    // TC-TDD-030-02
    it('再確認モードで「覚えた」を選択しても submitReview API が追加呼び出しされない', async () => {
      const user = userEvent.setup();
      await gradeWithQuality0AndEnterReconfirm(user);

      // この時点で mockSubmitReview は 1 回呼ばれている (quality 0 の初回評価)
      expect(mockSubmitReview).toHaveBeenCalledTimes(1);

      // 再確認モードで「覚えた」をクリック
      const rememberedButton = screen.getByRole('button', { name: '覚えた' });
      await user.click(rememberedButton);

      // API 追加呼び出しなし
      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });
      expect(mockSubmitReview).toHaveBeenCalledTimes(1);
    });

    // TC-TDD-030-03 + TC-TDD-030-04 (統合)
    it('「覚えた」選択後に reviewResults の type が reconfirmed に、reconfirmResult が remembered に更新される', async () => {
      const user = userEvent.setup();
      // quality 2 で評価 → 再確認モード → 「覚えた」
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
      await user.click(screen.getByLabelText('2 - 間違えたが見覚えあり'));

      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });

      // 「覚えた」ボタンをクリック
      const rememberedButton = screen.getByRole('button', { name: '覚えた' });
      await user.click(rememberedButton);

      // 完了画面で reviewResults に reconfirmed が含まれることを確認
      // TASK-0082 で「再確認済み」バッジなどの UI が実装される
      // RED フェーズでは: 完了画面が表示されること + 「覚えた」ボタンが存在すること を検証
      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });
    });
  });

  // --- handleReconfirmForgotten: 「覚えていない」ハンドラ ---
  describe('handleReconfirmForgotten: 「覚えていない」ハンドラ', () => {
    const gradeWithQuality0AndEnterReconfirm = async (user: ReturnType<typeof userEvent.setup>) => {
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
      await user.click(screen.getByLabelText('0 - 全く覚えていない'));

      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });
    };

    // TC-TDD-040-01
    it('再確認モードで「覚えていない」を選択するとカードがキュー末尾に再追加され、セッションが完了しない', async () => {
      const user = userEvent.setup();
      await gradeWithQuality0AndEnterReconfirm(user);

      // 「覚えていない」ボタンをクリック
      // TASK-0082 で UI が実装されるまではボタンが存在しない → RED フェーズで FAIL
      const forgottenButton = screen.getByRole('button', { name: '覚えていない' });
      await user.click(forgottenButton);

      // カードがキュー末尾に再追加 → セッション完了しない
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });
    });

    // TC-TDD-040-02
    it('再確認モードで「覚えていない」を選択しても submitReview API が追加呼び出しされない', async () => {
      const user = userEvent.setup();
      await gradeWithQuality0AndEnterReconfirm(user);

      // quality 0 評価時の 1 回のみ
      expect(mockSubmitReview).toHaveBeenCalledTimes(1);

      const forgottenButton = screen.getByRole('button', { name: '覚えていない' });
      await user.click(forgottenButton);

      // API 追加呼び出しなし (まだ完了していないので waitFor で少し待つ)
      // 「覚えていない」後は再確認モードが継続するため完了画面は出ない
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });
      expect(mockSubmitReview).toHaveBeenCalledTimes(1);
    });

    // TC-TDD-040-03
    it('「覚えていない」を2回選択した後「覚えた」を選択するとセッションが完了する', async () => {
      const user = userEvent.setup();
      await gradeWithQuality0AndEnterReconfirm(user);

      // 「覚えていない」1回目
      const forgottenButton1 = screen.getByRole('button', { name: '覚えていない' });
      await user.click(forgottenButton1);

      // 「覚えていない」2回目
      const forgottenButton2 = screen.getByRole('button', { name: '覚えていない' });
      await user.click(forgottenButton2);

      // 「覚えた」でセッション完了
      const rememberedButton = screen.getByRole('button', { name: '覚えた' });
      await user.click(rememberedButton);

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });

      // quality 0 評価時の 1 回のみ
      expect(mockSubmitReview).toHaveBeenCalledTimes(1);
    });
  });

  // --- moveToNext 拡張 ---
  describe('moveToNext 拡張: カード進行ロジック', () => {
    // TC-TDD-050-02
    it('通常カードを全て消化し、再確認キューが非空の場合、再確認モードに遷移する', async () => {
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

      // quality 0 → reconfirmQueue 非空 → isReconfirmMode = true
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('0 - 全く覚えていない'));

      // isReconfirmMode = true → 完了しない
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });
    });

    // TC-TDD-050-04
    it('再確認キューのカードを全て「覚えた」で消化するとセッションが完了する', async () => {
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

      // quality 0 → 再確認モード
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('0 - 全く覚えていない'));

      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });

      // 「覚えた」 → reconfirmQueue 空 → isComplete = true
      const rememberedButton = screen.getByRole('button', { name: '覚えた' });
      await user.click(rememberedButton);

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });
    });
  });

  // --- handleUndo 拡張: 再確認キュー連携 ---
  describe('handleUndo 拡張: 再確認キューとの連携', () => {
    // TC-TDD-060-01
    it('Undo 時に再確認キューから該当カードが除去される', async () => {
      const user = userEvent.setup();
      // 2枚のカードを使用: カード1 を quality 1 で評価、カード2 を quality 4 で評価 → 完了
      mockGetDueCards.mockResolvedValue({
        due_cards: [mockDueCards[0], mockDueCards[1]],
        total_due_count: 2,
        next_due_date: null,
      });
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // カード1: quality 1 (reconfirmQueue に追加)
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('1 - 間違えた'));

      // カード2: quality 4 → 完了画面に進む
      // 注意: カード2 表示後にフリップして採点
      await waitFor(() => {
        expect(screen.getByText('質問2')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('4 - やや迷ったが正解'));

      // 通常カード全消化 + reconfirmQueue 非空 → 再確認モード (完了画面ではない)
      // → 再確認モードで「覚えた」をクリックして完了させる
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });

      // 再確認モードで「覚えた」をクリック → 完了
      const rememberedButton = screen.getByRole('button', { name: '覚えた' });
      await user.click(rememberedButton);

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });

      // Undo で card-1 を取り消し
      mockUndoReview.mockResolvedValue({
        card_id: 'card-1',
        restored: { ease_factor: 2.5, interval: 1, repetitions: 0, due_date: '2026-02-28' },
        undone_at: '2026-02-28T10:01:00Z',
      });
      const undoButton = screen.getByLabelText('質問1 を再採点する');
      await user.click(undoButton);

      expect(mockUndoReview).toHaveBeenCalledWith('card-1');

      // Undo 後は regrade モードに入る
      await waitFor(() => {
        expect(screen.getByText('再採点')).toBeInTheDocument();
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // regrade で quality 4 を選択 → reconfirmQueue に追加されない → 完了
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('4 - やや迷ったが正解'));

      // 完了画面に戻る (reconfirmQueue が空のまま)
      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });
    });

    // TC-TDD-060-02 (TC-TDD-021-01 と同一シナリオ)
    it('Undo 後の再採点で quality 0-2 を選択すると再確認モードに遷移する', async () => {
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

      // quality 4 → 完了
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('4 - やや迷ったが正解'));

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });

      // Undo → regrade
      const undoButton = screen.getByLabelText('質問1 を再採点する');
      await user.click(undoButton);

      await waitFor(() => {
        expect(screen.getByText('再採点')).toBeInTheDocument();
      });

      // regrade: quality 1 → reconfirmQueue に再追加 → 再確認モードに遷移
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('1 - 間違えた'));

      await waitFor(() => {
        expect(mockSubmitReview).toHaveBeenCalledTimes(2);
        expect(mockSubmitReview).toHaveBeenLastCalledWith('card-1', 1);
      });

      // 再確認モードに遷移（完了画面ではない）
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
        expect(screen.getByText('再確認')).toBeInTheDocument();
      });

      // 「覚えた」でセッション完了
      const rememberedButton = screen.getByRole('button', { name: '覚えた' });
      await user.click(rememberedButton);

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });
    });

    // TC-TDD-060-03
    it('Undo 後の再採点で quality 3+ を選択すると再確認キューに追加されず、正常完了する', async () => {
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

      // quality 1 → 完了 (再確認モード経由)
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('1 - 間違えた'));

      // 再確認モードで「覚えた」 → 完了
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });
      const rememberedButton = screen.getByRole('button', { name: '覚えた' });
      await user.click(rememberedButton);

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });

      // Undo → regrade
      const undoButton = screen.getByLabelText('質問1 を再採点する');
      await user.click(undoButton);

      await waitFor(() => {
        expect(screen.getByText('再採点')).toBeInTheDocument();
      });

      // regrade: quality 4 → reconfirmQueue に追加されない
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('4 - やや迷ったが正解'));

      // 通常の完了画面に戻る
      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });
    });
  });

  // --- 統合テスト ---
  describe('統合テスト: 再確認ループフロー', () => {
    // TC-TDD-INT-01
    it('3枚中1枚がquality 0で評価され、再確認ループ後にセッションが完了する', async () => {
      const user = userEvent.setup();
      renderReviewPage(); // 3枚 (mockDueCards)

      // カード1: quality 0 → reconfirmQueue: [card-1]
      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('0 - 全く覚えていない'));

      // カード2: quality 4 → reconfirmQueue: [card-1] (変化なし)
      await waitFor(() => {
        expect(screen.getByText('質問2')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('4 - やや迷ったが正解'));

      // カード3: quality 5 → 通常カード全消化 → isReconfirmMode = true
      await waitFor(() => {
        expect(screen.getByText('質問3')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('5 - 完璧'));

      // 再確認モード (完了画面ではない)
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });

      // 再確認: card-1 「覚えた」 → reconfirmQueue: [] → isComplete = true
      const rememberedButton = screen.getByRole('button', { name: '覚えた' });
      await user.click(rememberedButton);

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
        expect(screen.getByText('3枚のカードを復習しました')).toBeInTheDocument();
      });

      // API は 3 回呼ばれる (card-1, card-2, card-3)
      expect(mockSubmitReview).toHaveBeenCalledTimes(3);
      expect(mockSubmitReview).toHaveBeenCalledWith('card-1', 0);
      expect(mockSubmitReview).toHaveBeenCalledWith('card-2', 4);
      expect(mockSubmitReview).toHaveBeenCalledWith('card-3', 5);
    });

    // TC-TDD-INT-02
    it('全3枚がquality 0-2で評価され、全て再確認「覚えた」でセッションが完了する', async () => {
      const user = userEvent.setup();
      renderReviewPage(); // 3枚 (mockDueCards)

      // カード1: quality 0
      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('0 - 全く覚えていない'));

      // カード2: quality 1
      await waitFor(() => {
        expect(screen.getByText('質問2')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('1 - 間違えた'));

      // カード3: quality 2 → 通常カード全消化 → isReconfirmMode = true
      await waitFor(() => {
        expect(screen.getByText('質問3')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('2 - 間違えたが見覚えあり'));

      // reconfirmQueue: [card-1, card-2, card-3]
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });

      // card-1 「覚えた」
      await user.click(screen.getByRole('button', { name: '覚えた' }));

      // card-2 「覚えた」
      await user.click(screen.getByRole('button', { name: '覚えた' }));

      // card-3 「覚えた」 → isComplete = true
      await user.click(screen.getByRole('button', { name: '覚えた' }));

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
        expect(screen.getByText('3枚のカードを復習しました')).toBeInTheDocument();
      });

      expect(mockSubmitReview).toHaveBeenCalledTimes(3);
    });

    // TC-TDD-INT-03
    it('1枚のカードで「覚えていない」を2回選択後「覚えた」でセッションが完了する', async () => {
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

      // quality 0 → reconfirmQueue: [card-1]
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('0 - 全く覚えていない'));

      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });

      // 「覚えていない」1回目 → reconfirmQueue: [card-1]
      await user.click(screen.getByRole('button', { name: '覚えていない' }));

      // 「覚えていない」2回目 → reconfirmQueue: [card-1]
      await user.click(screen.getByRole('button', { name: '覚えていない' }));

      // 「覚えた」 → reconfirmQueue: [] → isComplete = true
      await user.click(screen.getByRole('button', { name: '覚えた' }));

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });

      // submitReview は quality 0 の 1 回のみ
      expect(mockSubmitReview).toHaveBeenCalledTimes(1);
    });

    // TC-TDD-INT-04
    it('Undo後のregradeでquality 1を選択すると再確認モードに遷移し、「覚えた」で完了する', async () => {
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

      // quality 4 → isComplete = true
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('4 - やや迷ったが正解'));

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });

      // Undo → regradeMode
      const undoButton = screen.getByLabelText('質問1 を再採点する');
      await user.click(undoButton);

      await waitFor(() => {
        expect(screen.getByText('再採点')).toBeInTheDocument();
      });

      // regrade: quality 1 → reconfirmQueue に追加 → 再確認モードに遷移
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('1 - 間違えた'));

      // undoReview 1回 + submitReview 2回
      await waitFor(() => {
        expect(mockUndoReview).toHaveBeenCalledTimes(1);
        expect(mockSubmitReview).toHaveBeenCalledTimes(2);
        expect(mockSubmitReview).toHaveBeenLastCalledWith('card-1', 1);
      });

      // 再確認モードに遷移（完了画面ではない）
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
        expect(screen.getByText('再確認')).toBeInTheDocument();
      });

      // 「覚えた」でセッション完了
      const rememberedButton = screen.getByRole('button', { name: '覚えた' });
      await user.click(rememberedButton);

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });
    });
  });

  // --- エッジケース: 再確認ループ ---
  describe('エッジケース: 再確認ループ', () => {
    // TC-TDD-EDGE-01
    it('再確認キューが空の時にhandleReconfirmRememberedを呼んでも状態が変化しない', async () => {
      // reconfirmQueue が空 (通常モードで未採点) の状態で「覚えた」ボタンを探す
      // → ボタン自体が存在しない or 非アクティブのはず
      // RED フェーズでは: 「覚えた」ボタンが通常モードでは表示されないことを確認
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // 通常モードでは「覚えた」ボタンは存在しない
      expect(screen.queryByRole('button', { name: '覚えた' })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: '覚えていない' })).not.toBeInTheDocument();
    });

    // TC-TDD-EDGE-02
    it('再確認キューが空の時にhandleReconfirmForgottenを呼んでも状態が変化しない', async () => {
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // 通常モードでは「覚えていない」ボタンは存在しない
      expect(screen.queryByRole('button', { name: '覚えていない' })).not.toBeInTheDocument();
    });

    // TC-TDD-EDGE-03
    it('再確認キューに複数カードがある時「覚えた」で先頭のみ除外される', async () => {
      const user = userEvent.setup();
      renderReviewPage(); // 3枚

      // 3枚全て quality 0-2 で評価 → reconfirmQueue: [card-1, card-2, card-3]
      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('0 - 全く覚えていない'));

      await waitFor(() => {
        expect(screen.getByText('質問2')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('1 - 間違えた'));

      await waitFor(() => {
        expect(screen.getByText('質問3')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('2 - 間違えたが見覚えあり'));

      // 再確認モード: card-1 「覚えた」
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: '覚えた' }));

      // card-1 のみ除外 → まだ card-2, card-3 が残る → 完了しない
      await waitFor(() => {
        expect(screen.queryByText('復習完了!')).not.toBeInTheDocument();
      });
    });

    // TC-TDD-EDGE-04
    it('quality 3-5で評価したカードのUndoで再確認キューのfilterが空振りしてもエラーが起きない', async () => {
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

      // quality 4 → 完了 (reconfirmQueue は空)
      await user.click(screen.getByRole('button', { name: /カード表面を表示中/ }));
      await user.click(screen.getByLabelText('4 - やや迷ったが正解'));

      await waitFor(() => {
        expect(screen.getByText('復習完了!')).toBeInTheDocument();
      });

      // Undo → reconfirmQueue.filter は空振りするがエラーなし
      const undoButton = screen.getByLabelText('質問1 を再採点する');
      await user.click(undoButton);

      // regrade モードに正常遷移
      await waitFor(() => {
        expect(screen.getByText('再採点')).toBeInTheDocument();
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      expect(mockUndoReview).toHaveBeenCalledWith('card-1');
    });
  });

  // ============================================================
  // TASK-0149: 停止トグル修正 - 失敗テスト (Red フェーズ)
  // 【テスト概要】: ReviewPage の speechProps コールバックが isSpeaking 状態に応じて
  //               cancel() または speak() を正しく呼ぶことを検証する
  // 【現状の問題】: onSpeakFront/onSpeakBack が常に speak() を呼ぶため停止できない
  // 【修正目標】: isSpeaking=true のとき cancel() を呼び、false のとき speak(text) を呼ぶ
  // 🔵 青信号: TASK-0149.md 完了条件 + architecture.md REQ-001 より
  // ============================================================

  describe('TASK-0149: 停止トグル修正 - 通常モード', () => {
    // 【テスト前準備】: 各テスト前に SpeechButton が表示される状態を設定
    // 【環境初期化】: mockIsSpeaking/mockIsSupported をリセットし、モック関数をクリア
    beforeEach(() => {
      // 【テスト前準備】: isSupported=true にして SpeechButton を表示させる
      // 【重要】: FlipCard は speechProps.speechState.isSupported=true のときのみ SpeechButton を描画する
      mockIsSupported = true;
      // 【テスト前準備】: 各テスト開始時に isSpeaking=false（デフォルト停止状態）
      mockIsSpeaking = false;
      // 【テスト前準備】: モック関数をクリアして前のテストの呼び出し履歴を消去
      mockSpeak.mockClear();
      mockCancel.mockClear();
    });

    // 【テスト後処理】: テスト終了後に isSupported/isSpeaking をデフォルト値に戻す
    // 【状態復元】: 既存テストへの影響を防ぐため、各テスト後にモック状態をリセット
    afterEach(() => {
      mockIsSupported = false;
      mockIsSpeaking = false;
    });

    // TC-001: 通常モード - 表面読み上げ中にボタンクリックで cancel() が呼ばれる
    it('TC-001: 通常モード: 表面読み上げ中にボタンをクリックすると cancel() が呼ばれ、speak() は呼ばれない', async () => {
      // 【テスト目的】: isSpeaking=true の状態で表面の読み上げボタンをクリックしたとき、
      //               ReviewPage が生成する onSpeakFront コールバックが cancel() を呼ぶことを確認
      // 【テスト内容】: 発話中の状態を再現し、停止トグル動作を検証する
      // 【期待される動作】: speak() ではなく cancel() が呼ばれ、読み上げが停止する
      // 🔵 青信号: TASK-0149.md 完了条件 + architecture.md REQ-001 より

      const user = userEvent.setup();

      // 【テストデータ準備】: 1枚のカードで通常モードをセットアップ
      // 【初期条件設定】: isSupported=true で SpeechButton が表示される状態
      mockGetDueCards.mockResolvedValue({
        due_cards: [{ card_id: 'card-1', front: '質問1', back: '解答1', overdue_days: 0 }],
        total_due_count: 1,
        next_due_date: null,
      });

      // 【テストデータ準備】: isSpeaking=true（発話中）の状態を設定
      // 【重要】: ReviewPage はコールバック生成時に useSpeech の isSpeaking を参照する
      mockIsSpeaking = true;

      renderReviewPage();

      // 【前提条件確認】: カードが表示されることを確認
      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // 【前提条件確認】: isSpeaking=true の状態で表面の読み上げボタン（停止アイコン）が表示されることを確認
      // SpeechButton は isSpeaking=true のとき aria-label="表面の読み上げを停止" になる
      const frontSpeechButton = screen.getByRole('button', { name: '表面の読み上げを停止' });
      expect(frontSpeechButton).toBeInTheDocument(); // 【確認内容】: SpeechButton が isSupported=true/isSpeaking=true で表示されること 🔵

      // 【実際の処理実行】: 表面の読み上げボタンをクリック
      // 【処理内容】: SpeechButton.onClick → FlipCard.onSpeakFront → ReviewPage の speechProps.onSpeakFront
      await user.click(frontSpeechButton);

      // 【結果検証】: cancel() が1回呼ばれたことを確認
      // 【期待値確認】: REQ-001 により、発話中にボタンをクリックすると停止すべき
      expect(mockCancel).toHaveBeenCalledTimes(1); // 【確認内容】: cancel() が1回呼ばれたこと 🔵

      // 【結果検証】: speak() が呼ばれていないことを確認
      // 【期待値確認】: 発話中のクリックは停止であり、speak() は呼ばれない（停止トグルの核心）
      expect(mockSpeak).not.toHaveBeenCalled(); // 【確認内容】: speak() が呼ばれていないこと 🔵
    });

    // TC-002: 通常モード - 裏面読み上げ中にボタンクリックで cancel() が呼ばれる
    it('TC-002: 通常モード: 裏面読み上げ中にボタンをクリックすると cancel() が呼ばれ、speak() は呼ばれない', async () => {
      // 【テスト目的】: isSpeaking=true の状態で裏面の読み上げボタンをクリックしたとき、
      //               onSpeakBack コールバックが cancel() を呼ぶことを確認
      // 【テスト内容】: 発話中の裏面表示状態を再現する
      // 【期待される動作】: speak() ではなく cancel() が呼ばれ、読み上げが停止する
      // 🔵 青信号: TASK-0149.md 完了条件 + architecture.md REQ-001 より

      const user = userEvent.setup();

      // 【テストデータ準備】: 1枚のカードで通常モードをセットアップ
      mockGetDueCards.mockResolvedValue({
        due_cards: [{ card_id: 'card-1', front: '質問1', back: '解答1', overdue_days: 0 }],
        total_due_count: 1,
        next_due_date: null,
      });

      // 【テストデータ準備】: isSpeaking=true（発話中）の状態を設定
      mockIsSpeaking = true;

      renderReviewPage();

      // 【前提条件確認】: カードが表示されることを確認
      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // 【実際の処理実行】: カードをフリップして裏面を表示
      // 【処理内容】: カードをクリックして isFlipped=true にし、裏面の SpeechButton を表示
      const card = screen.getByRole('button', { name: /カード表面を表示中/ });
      await user.click(card);

      // 【前提条件確認】: isFlipped=true の状態で裏面の読み上げボタン（停止アイコン）が表示されることを確認
      // SpeechButton は isSpeaking=true のとき aria-label="裏面の読み上げを停止" になる
      const backSpeechButton = screen.getByRole('button', { name: '裏面の読み上げを停止' });
      expect(backSpeechButton).toBeInTheDocument(); // 【確認内容】: 裏面の SpeechButton が表示されること 🔵

      // モック関数をクリア（フリップ時に speak が呼ばれた場合の呼び出しをリセット）
      mockSpeak.mockClear();
      mockCancel.mockClear();

      // 【実際の処理実行】: 裏面の読み上げボタンをクリック
      await user.click(backSpeechButton);

      // 【結果検証】: cancel() が1回呼ばれたことを確認
      // 【期待値確認】: REQ-001 により、裏面でも停止トグル動作は同一であるべき
      expect(mockCancel).toHaveBeenCalledTimes(1); // 【確認内容】: cancel() が1回呼ばれたこと 🔵

      // 【結果検証】: speak() が呼ばれていないことを確認
      expect(mockSpeak).not.toHaveBeenCalled(); // 【確認内容】: speak() が呼ばれていないこと 🔵
    });

    // TC-003: 通常モード - 停止中にボタンクリックで speak() が呼ばれる
    it('TC-003: 通常モード: 停止中にボタンをクリックすると speak(text) が呼ばれ、cancel() は呼ばれない', async () => {
      // 【テスト目的】: isSpeaking=false の状態で表面の読み上げボタンをクリックしたとき、
      //               speak(text) が正しいテキストで呼ばれることを確認
      // 【テスト内容】: 停止中の状態から読み上げを開始するシナリオ
      // 【期待される動作】: cancel() ではなく speak(currentCard.front) が呼ばれる
      // 🔵 青信号: TASK-0149.md 基本テスト要件「停止後に再タップ → speak() が呼ばれる」より

      const user = userEvent.setup();

      // 【テストデータ準備】: 1枚のカードで通常モードをセットアップ
      // 【初期条件設定】: isSpeaking=false（停止中）の状態（beforeEach で設定済み）
      mockGetDueCards.mockResolvedValue({
        due_cards: [{ card_id: 'card-1', front: '質問1', back: '解答1', overdue_days: 0 }],
        total_due_count: 1,
        next_due_date: null,
      });

      // 【前提確認】: mockIsSpeaking=false（停止中）のまま
      // mockIsSpeaking は beforeEach で false に設定済み

      renderReviewPage();

      // 【前提条件確認】: カードが表示されることを確認
      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // 【前提条件確認】: isSpeaking=false の状態で表面の読み上げボタン（再生アイコン）が表示されることを確認
      // SpeechButton は isSpeaking=false のとき aria-label="表面を読み上げ" になる
      const frontSpeechButton = screen.getByRole('button', { name: '表面を読み上げ' });
      expect(frontSpeechButton).toBeInTheDocument(); // 【確認内容】: SpeechButton が isSupported=true で表示されること 🔵

      // 【実際の処理実行】: 停止中に表面の読み上げボタンをクリック
      // 【処理内容】: SpeechButton.onClick → FlipCard.onSpeakFront → ReviewPage の speechProps.onSpeakFront
      await user.click(frontSpeechButton);

      // 【結果検証】: speak() が正しいテキスト「質問1」で呼ばれたことを確認
      // 【期待値確認】: 停止中のボタンクリックは新規読み上げ開始であるべき
      expect(mockSpeak).toHaveBeenCalledWith('質問1'); // 【確認内容】: speak() がカード表面テキストで呼ばれたこと 🔵

      // 【結果検証】: cancel() が呼ばれていないことを確認
      // 【期待値確認】: 停止中のクリックは読み上げ開始であり、cancel() は呼ばれない
      expect(mockCancel).not.toHaveBeenCalled(); // 【確認内容】: cancel() が呼ばれていないこと 🔵
    });
  });

  // ============================================================
  // TASK-0160: 参考情報（ReferenceDisplay）統合テスト
  // ============================================================
  describe('参考情報の表示', () => {
    it('カード裏面表示時に参考情報が表示される', async () => {
      const user = userEvent.setup();
      const cardsWithRefs = [
        {
          card_id: 'card-1',
          front: '質問1',
          back: '解答1',
          overdue_days: 0,
          references: [
            { type: 'url' as const, value: 'https://example.com' },
            { type: 'book' as const, value: '参考書籍' },
          ],
        },
      ];
      mockGetDueCards.mockResolvedValue({
        due_cards: cardsWithRefs,
        total_due_count: 1,
        next_due_date: null,
      });

      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // フリップ前は参考情報が表示されない
      expect(screen.queryByTestId('reference-display')).not.toBeInTheDocument();

      // フリップ
      const card = screen.getByRole('button', { name: /カード表面を表示中/ });
      await user.click(card);

      // フリップ後に参考情報が表示される
      await waitFor(() => {
        expect(screen.getByTestId('reference-display')).toBeInTheDocument();
      });
      expect(screen.getByTestId('reference-display-item-0')).toBeInTheDocument();
      expect(screen.getByTestId('reference-display-item-1')).toBeInTheDocument();
    });

    it('参考情報なしカードの裏面でもエラーなく表示される', async () => {
      const user = userEvent.setup();
      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // フリップ
      const card = screen.getByRole('button', { name: /カード表面を表示中/ });
      await user.click(card);

      // 参考情報なしなので reference-display は表示されない
      expect(screen.queryByTestId('reference-display')).not.toBeInTheDocument();
    });

    it('参考情報付きカードで URL がリンクとして表示される', async () => {
      const user = userEvent.setup();
      const cardsWithRefs = [
        {
          card_id: 'card-1',
          front: '質問1',
          back: '解答1',
          overdue_days: 0,
          references: [
            { type: 'url' as const, value: 'https://example.com' },
          ],
        },
      ];
      mockGetDueCards.mockResolvedValue({
        due_cards: cardsWithRefs,
        total_due_count: 1,
        next_due_date: null,
      });

      renderReviewPage();

      await waitFor(() => {
        expect(screen.getByText('質問1')).toBeInTheDocument();
      });

      // フリップ
      const card = screen.getByRole('button', { name: /カード表面を表示中/ });
      await user.click(card);

      await waitFor(() => {
        expect(screen.getByTestId('reference-display-link-0')).toBeInTheDocument();
      });
      const link = screen.getByTestId('reference-display-link-0');
      expect(link).toHaveAttribute('href', 'https://example.com');
      expect(link).toHaveAttribute('target', '_blank');
    });
  });
});

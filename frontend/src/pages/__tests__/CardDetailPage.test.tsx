/**
 * 【テスト概要】: カード詳細・編集画面のテスト
 * 【テスト対象】: CardDetailPage コンポーネント
 * 【テスト対応】: TASK-0017 テストケース1〜9
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { CardDetailPage } from '../CardDetailPage';
import type { Card } from '@/types';

// Navigation モック
vi.mock('@/components/Navigation', () => ({
  Navigation: () => <nav data-testid="navigation">Navigation</nav>,
}));

// cardsApi モック
const mockGetCard = vi.fn();
const mockUpdateCard = vi.fn();
const mockDeleteCard = vi.fn();

vi.mock('@/services/api', () => ({
  cardsApi: {
    getCard: (...args: unknown[]) => mockGetCard(...args),
    updateCard: (...args: unknown[]) => mockUpdateCard(...args),
    deleteCard: (...args: unknown[]) => mockDeleteCard(...args),
  },
}));

// useNavigate モック
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockCard: Card = {
  card_id: 'card-1',
  user_id: 'user-1',
  front: 'テスト質問',
  back: 'テスト回答',
  tags: ['tag1'],
  ease_factor: 2.5,
  interval: 7,
  repetitions: 3,
  next_review_at: '2024-01-20',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-15T00:00:00Z',
};

const renderCardDetailPage = (cardId: string = 'card-1') => {
  return render(
    <MemoryRouter initialEntries={[`/cards/${cardId}`]}>
      <Routes>
        <Route path="/cards/:id" element={<CardDetailPage />} />
        <Route path="/cards" element={<div data-testid="cards-page">Cards Page</div>} />
      </Routes>
    </MemoryRouter>
  );
};

describe('CardDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetCard.mockResolvedValue(mockCard);
    mockUpdateCard.mockResolvedValue(mockCard);
    mockDeleteCard.mockResolvedValue(undefined);

    // 日付のモック（fake timersではなくDateのモック）
    vi.spyOn(Date, 'now').mockReturnValue(new Date('2024-01-15T00:00:00').getTime());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('テストケース1: カード詳細の表示', () => {
    it('カードの表面・裏面が表示される', async () => {
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-front')).toHaveTextContent('テスト質問');
      });
      expect(screen.getByTestId('card-back')).toHaveTextContent('テスト回答');
    });

    it('メタ情報（次回復習日、復習間隔）が表示される', async () => {
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('due-date')).toBeInTheDocument();
      });
      expect(screen.getByTestId('interval')).toHaveTextContent('7日');
    });

    it('APIからカードを取得する', async () => {
      renderCardDetailPage('card-1');

      await waitFor(() => {
        expect(mockGetCard).toHaveBeenCalledWith('card-1');
      });
    });
  });

  describe('テストケース2: 編集モードへの切り替え', () => {
    it('編集ボタンをクリックすると編集フォームが表示される', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });

      const editButton = screen.getByTestId('edit-button');
      await user.click(editButton);

      expect(screen.getByTestId('card-form')).toBeInTheDocument();
    });

    it('編集モードでは編集ボタンが非表示になる', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('edit-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-button'));

      expect(screen.queryByTestId('edit-button')).not.toBeInTheDocument();
    });
  });

  describe('テストケース3: 編集のキャンセル', () => {
    it('キャンセルボタンで表示モードに戻る', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('edit-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-button'));
      expect(screen.getByTestId('card-form')).toBeInTheDocument();

      await user.click(screen.getByTestId('cancel-button'));

      expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      expect(screen.queryByTestId('card-form')).not.toBeInTheDocument();
    });
  });

  describe('テストケース4: カードの保存', () => {
    it('保存成功時に成功メッセージが表示される', async () => {
      const user = userEvent.setup();
      const updatedCard = { ...mockCard, front: '更新された質問' };
      mockUpdateCard.mockResolvedValue(updatedCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('edit-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-button'));

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, '更新された質問');

      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toHaveTextContent('カードを保存しました');
      });
    });

    it('保存成功後に表示モードに戻る', async () => {
      const user = userEvent.setup();
      const updatedCard = { ...mockCard, front: '更新された質問' };
      mockUpdateCard.mockResolvedValue(updatedCard);

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('edit-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-button'));

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, '更新された質問');

      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(screen.getByTestId('card-detail')).toBeInTheDocument();
      });
    });

    it('保存失敗時にエラーメッセージが表示される', async () => {
      const user = userEvent.setup();
      mockUpdateCard.mockRejectedValue(new Error('保存エラー'));

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('edit-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-button'));

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);
      await user.type(frontInput, '更新された質問');

      await user.click(screen.getByTestId('save-button'));

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('カードの保存に失敗しました');
      });
    });
  });

  describe('テストケース5: 空の入力での保存防止', () => {
    it('空の入力では保存ボタンが無効', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('edit-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('edit-button'));

      const frontInput = screen.getByTestId('input-front');
      await user.clear(frontInput);

      expect(screen.getByTestId('save-button')).toBeDisabled();
    });
  });

  describe('テストケース6: 削除確認ダイアログの表示', () => {
    it('削除ボタンで確認ダイアログが表示される', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('delete-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('delete-button'));

      expect(screen.getByTestId('delete-confirm-dialog')).toBeInTheDocument();
      expect(screen.getByText('カードを削除しますか？')).toBeInTheDocument();
      expect(screen.getByText('この操作は取り消せません。')).toBeInTheDocument();
    });
  });

  describe('テストケース7: 削除のキャンセル', () => {
    it('キャンセルボタンでダイアログが閉じる', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('delete-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('delete-button'));
      expect(screen.getByTestId('delete-confirm-dialog')).toBeInTheDocument();

      await user.click(screen.getByTestId('delete-cancel-button'));

      expect(screen.queryByTestId('delete-confirm-dialog')).not.toBeInTheDocument();
    });
  });

  describe('テストケース8: カードの削除', () => {
    it('削除成功時に一覧画面に遷移する', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('delete-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('delete-button'));
      await user.click(screen.getByTestId('delete-confirm-button'));

      await waitFor(() => {
        expect(mockDeleteCard).toHaveBeenCalledWith('card-1');
        expect(mockNavigate).toHaveBeenCalledWith('/cards', { state: { message: 'カードを削除しました' } });
      });
    });

    it('削除失敗時にエラーメッセージが表示される', async () => {
      const user = userEvent.setup();
      mockDeleteCard.mockRejectedValue(new Error('削除エラー'));

      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('delete-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('delete-button'));
      await user.click(screen.getByTestId('delete-confirm-button'));

      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toHaveTextContent('カードの削除に失敗しました');
      });
    });
  });

  describe('テストケース9: 存在しないカードへのアクセス', () => {
    it('カード取得失敗時にエラーが表示される', async () => {
      mockGetCard.mockRejectedValue(new Error('Not Found'));

      renderCardDetailPage('non-existent');

      await waitFor(() => {
        expect(screen.getByText('カードの取得に失敗しました')).toBeInTheDocument();
      });
    });

    it('エラー時に再試行ボタンが表示される', async () => {
      mockGetCard.mockRejectedValue(new Error('Not Found'));

      renderCardDetailPage('non-existent');

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /再試行/ })).toBeInTheDocument();
      });
    });
  });

  describe('ローディング状態', () => {
    it('読み込み中はローディングが表示される', () => {
      mockGetCard.mockImplementation(() => new Promise(() => {})); // 永遠に解決しない

      renderCardDetailPage();

      expect(screen.getByText('カードを読み込み中...')).toBeInTheDocument();
    });
  });

  describe('戻るボタン', () => {
    it('戻るボタンで履歴を戻る', async () => {
      const user = userEvent.setup();
      renderCardDetailPage();

      await waitFor(() => {
        expect(screen.getByTestId('back-button')).toBeInTheDocument();
      });

      await user.click(screen.getByTestId('back-button'));

      expect(mockNavigate).toHaveBeenCalledWith(-1);
    });
  });
});

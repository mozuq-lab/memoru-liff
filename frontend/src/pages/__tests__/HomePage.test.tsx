/**
 * 【テスト概要】: ホーム画面のテスト
 * 【テスト対象】: HomePage コンポーネント
 * 【テスト対応】: TASK-0014 テストケース1〜6
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { HomePage } from '../HomePage';

// CardsContext モック
const mockFetchDueCount = vi.fn();
const mockCardsContext = {
  cards: [],
  isLoading: false,
  error: null,
  fetchCards: vi.fn(),
  addCard: vi.fn(),
  updateCard: vi.fn(),
  deleteCard: vi.fn(),
  dueCount: 5,
  fetchDueCount: mockFetchDueCount,
};

vi.mock('@/contexts/CardsContext', () => ({
  useCardsContext: () => mockCardsContext,
}));

// AuthContext モック
const mockAuthContext = {
  user: {
    access_token: 'test-token',
    expired: false,
    profile: {
      sub: 'user-123',
      name: 'テストユーザー',
      email: 'test@example.com',
    },
  },
  isLoading: false,
  isAuthenticated: true,
  error: null,
  login: vi.fn(),
  logout: vi.fn(),
  refreshToken: vi.fn(),
};

vi.mock('@/contexts/AuthContext', () => ({
  useAuthContext: () => mockAuthContext,
}));

const renderHomePage = () => {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>
  );
};

describe('HomePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCardsContext.isLoading = false;
    mockCardsContext.error = null;
    mockCardsContext.dueCount = 5;
  });

  describe('テストケース1: ホーム画面の表示', () => {
    it('ユーザー名が表示される', () => {
      renderHomePage();
      expect(screen.getByText(/こんにちは、テストユーザーさん/)).toBeInTheDocument();
    });

    it('タイトルが表示される', () => {
      renderHomePage();
      expect(screen.getByRole('heading', { name: 'Memoru' })).toBeInTheDocument();
    });
  });

  describe('テストケース2: 復習待ちカード数表示', () => {
    it('復習待ちカード数が正しく表示される', () => {
      renderHomePage();
      expect(screen.getByTestId('due-count')).toHaveTextContent('5');
    });

    it('復習待ちカード数をAPIから取得する', () => {
      renderHomePage();
      expect(mockFetchDueCount).toHaveBeenCalled();
    });
  });

  describe('テストケース3: 復習待ちカードがない場合', () => {
    beforeEach(() => {
      mockCardsContext.dueCount = 0;
    });

    it('「復習を始める」ボタンが非表示', () => {
      renderHomePage();
      expect(screen.queryByText('復習を始める')).not.toBeInTheDocument();
    });

    it('カードがないメッセージが表示される', () => {
      renderHomePage();
      expect(screen.getByText('復習待ちのカードはありません')).toBeInTheDocument();
    });
  });

  describe('テストケース4: 復習待ちカードがある場合', () => {
    it('「復習を始める」ボタンが表示される', () => {
      mockCardsContext.dueCount = 5;
      renderHomePage();
      expect(screen.getByText('復習を始める')).toBeInTheDocument();
    });

    it('「復習を始める」ボタンがカード一覧へリンクする', () => {
      mockCardsContext.dueCount = 5;
      renderHomePage();
      const link = screen.getByText('復習を始める');
      expect(link).toHaveAttribute('href', '/cards');
    });
  });

  describe('テストケース5: クイックアクション', () => {
    it('カード作成リンクが表示される', () => {
      renderHomePage();
      expect(screen.getByText('カード作成')).toBeInTheDocument();
    });

    it('カード一覧リンクが表示される', () => {
      renderHomePage();
      expect(screen.getByText('カード一覧')).toBeInTheDocument();
    });

    it('カード作成リンクが正しいパスを持つ', () => {
      renderHomePage();
      const link = screen.getByText('カード作成').closest('a');
      expect(link).toHaveAttribute('href', '/generate');
    });
  });

  describe('テストケース6: ローディング状態', () => {
    beforeEach(() => {
      mockCardsContext.isLoading = true;
    });

    it('ローディング中はスピナーが表示される', async () => {
      renderHomePage();
      await waitFor(() => {
        expect(screen.getByText('読み込み中...')).toBeInTheDocument();
      });
    });
  });

  describe('エラー状態', () => {
    beforeEach(() => {
      (mockCardsContext as { error: Error | null }).error = new Error('API Error');
    });

    it('エラー時はエラーメッセージが表示される', () => {
      renderHomePage();
      expect(screen.getByText('データの取得に失敗しました')).toBeInTheDocument();
    });
  });

  describe('ユーザー名がない場合', () => {
    it('デフォルトの「ユーザー」が表示される', () => {
      (mockAuthContext as Record<string, unknown>).user = {
        access_token: 'test-token',
        expired: false,
        profile: {
          sub: 'user-123',
        },
      };
      renderHomePage();
      expect(screen.getByText(/こんにちは、ユーザーさん/)).toBeInTheDocument();
    });
  });
});

/**
 * 【テスト概要】: カード一覧画面のテスト
 * 【テスト対象】: CardsPage コンポーネント
 * 【テスト対応】: TASK-0016 テストケース1〜8
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CardsPage } from '../CardsPage';
import type { Card } from '@/types';

// CardsContext モック
const mockFetchCards = vi.fn();
const mockCardsContext = {
  cards: [] as Card[],
  isLoading: false,
  error: null as Error | null,
  fetchCards: mockFetchCards,
  addCard: vi.fn(),
  updateCard: vi.fn(),
  deleteCard: vi.fn(),
  dueCount: 0,
  fetchDueCount: vi.fn(),
};

vi.mock('@/contexts/CardsContext', () => ({
  useCardsContext: () => mockCardsContext,
}));

const mockCards: Card[] = [
  {
    id: 'card-1',
    user_id: 'user-1',
    front: '質問1',
    back: '回答1',
    tags: [],
    ease_factor: 2.5,
    interval: 1,
    repetitions: 0,
    due_date: '2024-01-15',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    id: 'card-2',
    user_id: 'user-1',
    front: '質問2',
    back: '回答2',
    tags: [],
    ease_factor: 2.5,
    interval: 3,
    repetitions: 1,
    due_date: '2024-01-20',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

const renderCardsPage = (locationState?: { message: string }) => {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/cards', state: locationState }]}>
      <CardsPage />
    </MemoryRouter>
  );
};

describe('CardsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCardsContext.cards = [];
    mockCardsContext.isLoading = false;
    mockCardsContext.error = null;

    // 2024年1月15日を「今日」として固定
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2024-01-15T00:00:00'));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('テストケース1: カード一覧の表示', () => {
    it('カードが表示される', () => {
      mockCardsContext.cards = mockCards;
      renderCardsPage();

      expect(screen.getByText('質問1')).toBeInTheDocument();
      expect(screen.getByText('質問2')).toBeInTheDocument();
    });

    it('カード数が表示される', () => {
      mockCardsContext.cards = mockCards;
      renderCardsPage();

      expect(screen.getByTestId('card-count')).toHaveTextContent('2枚のカード');
    });

    it('初期読み込み時にfetchCardsが呼ばれる', () => {
      renderCardsPage();
      expect(mockFetchCards).toHaveBeenCalled();
    });
  });

  describe('テストケース2: 次回復習日の表示', () => {
    it('復習日が日本語フォーマットで表示される', () => {
      mockCardsContext.cards = mockCards;
      renderCardsPage();

      expect(screen.getByText('次回復習: 1月15日(月)')).toBeInTheDocument();
    });
  });

  describe('テストケース3: 期限切れカードの表示', () => {
    it('期限切れステータスが表示される', () => {
      const overdueCard: Card = {
        ...mockCards[0],
        due_date: '2024-01-14',
      };
      mockCardsContext.cards = [overdueCard];
      renderCardsPage();

      expect(screen.getByTestId('due-status')).toHaveTextContent('期限切れ');
    });
  });

  describe('テストケース4: 今日が復習日のカード', () => {
    it('今日ステータスが表示される', () => {
      const todayCard: Card = {
        ...mockCards[0],
        due_date: '2024-01-15',
      };
      mockCardsContext.cards = [todayCard];
      renderCardsPage();

      expect(screen.getByTestId('due-status')).toHaveTextContent('今日');
    });
  });

  describe('テストケース6: カード詳細への遷移', () => {
    it('カードに詳細画面へのリンクがある', () => {
      mockCardsContext.cards = mockCards;
      renderCardsPage();

      const cardLink = screen.getByTestId('card-item-card-1');
      expect(cardLink).toHaveAttribute('href', '/cards/card-1');
    });
  });

  describe('テストケース7: 空状態の表示', () => {
    it('カードがない場合は空状態が表示される', () => {
      mockCardsContext.cards = [];
      renderCardsPage();

      expect(screen.getByTestId('empty-state')).toBeInTheDocument();
      expect(screen.getByText('カードがありません')).toBeInTheDocument();
    });

    it('カード作成ボタンが表示される', () => {
      mockCardsContext.cards = [];
      renderCardsPage();

      expect(screen.getByText('カードを作成する')).toBeInTheDocument();
    });
  });

  describe('テストケース8: ローディング状態', () => {
    it('読み込み中はローディングが表示される', () => {
      mockCardsContext.isLoading = true;
      renderCardsPage();

      expect(screen.getByText('カードを読み込み中...')).toBeInTheDocument();
    });
  });

  describe('エラー状態', () => {
    it('エラー時はエラーメッセージが表示される', () => {
      mockCardsContext.error = new Error('API Error');
      renderCardsPage();

      expect(screen.getByText('カードの取得に失敗しました')).toBeInTheDocument();
    });
  });

  describe('成功メッセージ', () => {
    it('location.stateからのメッセージが表示される', () => {
      mockCardsContext.cards = mockCards;
      renderCardsPage({ message: '3枚のカードを保存しました' });

      expect(screen.getByTestId('success-message')).toHaveTextContent('3枚のカードを保存しました');
    });
  });
});

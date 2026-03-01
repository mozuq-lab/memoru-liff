/**
 * 【テスト概要】: カード一覧画面のテスト
 * 【テスト対象】: CardsPage コンポーネント
 * 【テスト対応】: TASK-0016 テストケース1〜8
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { CardsPage } from '../CardsPage';
import type { Card } from '@/types';

// CardsContext モック
const mockFetchCards = vi.fn();
const mockFetchDueCards = vi.fn();
const mockCardsContext = {
  cards: [] as Card[],
  dueCards: [] as Card[],
  isLoading: false,
  error: null as Error | null,
  fetchCards: mockFetchCards,
  fetchDueCards: mockFetchDueCards,
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
    card_id: 'card-1',
    user_id: 'user-1',
    front: '質問1',
    back: '回答1',
    tags: [],
    ease_factor: 2.5,
    interval: 1,
    repetitions: 0,
    next_review_at: '2024-01-15',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
  {
    card_id: 'card-2',
    user_id: 'user-1',
    front: '質問2',
    back: '回答2',
    tags: [],
    ease_factor: 2.5,
    interval: 3,
    repetitions: 1,
    next_review_at: '2024-01-20',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  },
];

const renderCardsPage = (locationState?: { message: string }, searchParams?: string) => {
  const path = searchParams ? `/cards?${searchParams}` : '/cards';
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/cards', search: searchParams ? `?${searchParams}` : '', state: locationState }]}>
      <CardsPage />
    </MemoryRouter>
  );
};

describe('CardsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockCardsContext.cards = [];
    mockCardsContext.dueCards = [];
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
        next_review_at: '2024-01-14',
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
        next_review_at: '2024-01-15',
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

  describe('復習開始ボタン', () => {
    it('復習対象タブでカードがある場合に復習開始ボタンが表示される', () => {
      mockCardsContext.dueCards = mockCards;
      renderCardsPage(undefined, 'tab=due');

      expect(screen.getByTestId('start-review-button')).toBeInTheDocument();
      expect(screen.getByTestId('start-review-button')).toHaveAttribute('href', '/review');
    });

    it('復習対象タブでカードが0枚の場合は復習開始ボタンが非表示', () => {
      mockCardsContext.dueCards = [];
      renderCardsPage(undefined, 'tab=due');

      expect(screen.queryByTestId('start-review-button')).not.toBeInTheDocument();
    });

    it('すべてタブでは復習開始ボタンが非表示', () => {
      mockCardsContext.cards = mockCards;
      renderCardsPage();

      expect(screen.queryByTestId('start-review-button')).not.toBeInTheDocument();
    });
  });

  describe('成功メッセージ', () => {
    it('location.stateからのメッセージが表示される', () => {
      mockCardsContext.cards = mockCards;
      renderCardsPage({ message: '3枚のカードを保存しました' });

      expect(screen.getByTestId('success-message')).toHaveTextContent('3枚のカードを保存しました');
    });
  });

  describe('検索・フィルター統合テスト', () => {
    const searchCards: Card[] = [
      {
        card_id: 's1',
        user_id: 'u1',
        front: 'Apple リンゴ',
        back: '赤い果物',
        tags: [],
        ease_factor: 2.5,
        interval: 1,
        repetitions: 0, // new
        next_review_at: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: null,
      },
      {
        card_id: 's2',
        user_id: 'u1',
        front: 'Banana バナナ',
        back: '黄色い果物',
        tags: [],
        ease_factor: 1.8,
        interval: 3,
        repetitions: 2,
        next_review_at: '2024-01-10', // due（期日超過）
        created_at: '2024-01-05T00:00:00Z',
        updated_at: null,
      },
      {
        card_id: 's3',
        user_id: 'u1',
        front: 'Cherry さくらんぼ',
        back: '赤い小さな果物',
        tags: [],
        ease_factor: 3.0,
        interval: 10,
        repetitions: 5,
        next_review_at: '2024-02-01', // learning（未来）
        created_at: '2024-01-10T00:00:00Z',
        updated_at: null,
      },
    ];

    // CP-S01
    it('検索バーが表示される', () => {
      mockCardsContext.cards = searchCards;
      renderCardsPage();

      expect(screen.getByTestId('search-bar-input')).toBeInTheDocument();
    });

    // CP-S02
    it('検索バー入力でカードがフィルタリングされる', () => {
      mockCardsContext.cards = searchCards;
      renderCardsPage();

      const searchInput = screen.getByTestId('search-bar-input');
      fireEvent.change(searchInput, { target: { value: 'Apple' } });

      // highlightQuery により <mark> で分割されるため testid で確認
      expect(screen.getByTestId('card-item-s1')).toBeInTheDocument();
      expect(screen.queryByTestId('card-item-s2')).not.toBeInTheDocument();
      expect(screen.queryByTestId('card-item-s3')).not.toBeInTheDocument();
    });

    // CP-S03
    it('検索0件時に「該当するカードがありません」が表示される', () => {
      mockCardsContext.cards = searchCards;
      renderCardsPage();

      const searchInput = screen.getByTestId('search-bar-input');
      fireEvent.change(searchInput, { target: { value: '存在しないキーワードXYZ' } });

      expect(screen.getByText('該当するカードがありません')).toBeInTheDocument();
    });

    // CP-S04
    it('FilterChipsでカードがフィルタリングされる', () => {
      mockCardsContext.cards = searchCards;
      renderCardsPage();

      // 「新規」フィルタを選択
      fireEvent.click(screen.getByTestId('filter-chip-new'));

      // new（repetitions===0）は s1 のみ
      expect(screen.getByText('Apple リンゴ')).toBeInTheDocument();
      expect(screen.queryByText('Banana バナナ')).not.toBeInTheDocument();
      expect(screen.queryByText('Cherry さくらんぼ')).not.toBeInTheDocument();
    });

    // CP-S05
    it('タブ切替時にフィルター状態がリセットされる', () => {
      mockCardsContext.cards = searchCards;
      mockCardsContext.dueCards = [searchCards[1]]; // Banana のみ due
      renderCardsPage();

      // 検索入力
      const searchInput = screen.getByTestId('search-bar-input');
      fireEvent.change(searchInput, { target: { value: 'Apple' } });
      expect(screen.getByTestId('card-item-s1')).toBeInTheDocument();

      // タブ切替で復習対象へ
      fireEvent.click(screen.getByTestId('tab-due'));

      // リセットされて検索欄が空になる
      expect(screen.getByTestId('search-bar-input')).toHaveValue('');
    });

    // CP-S06
    it('復習対象タブではFilterChipsが非表示', () => {
      mockCardsContext.dueCards = [searchCards[1]];
      renderCardsPage(undefined, 'tab=due');

      expect(screen.queryByTestId('filter-chip-all')).not.toBeInTheDocument();
      expect(screen.queryByTestId('filter-chip-due')).not.toBeInTheDocument();
      expect(screen.queryByTestId('filter-chip-new')).not.toBeInTheDocument();
    });
  });
});

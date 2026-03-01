/**
 * 【テスト概要】: DecksPage コンポーネントのテスト
 * 【テスト対象】: DecksPage コンポーネント
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DecksPage } from '../DecksPage';
import type { Deck, Card } from '@/types';

// DecksContext モック
const mockFetchDecks = vi.fn();
const mockCreateDeck = vi.fn();
const mockUpdateDeck = vi.fn();
const mockDeleteDeck = vi.fn();

const mockDecksContext = {
  decks: [] as Deck[],
  isLoading: false,
  error: null as Error | null,
  fetchDecks: mockFetchDecks,
  createDeck: mockCreateDeck,
  updateDeck: mockUpdateDeck,
  deleteDeck: mockDeleteDeck,
};

vi.mock('@/contexts/DecksContext', () => ({
  useDecksContext: () => mockDecksContext,
}));

// CardsContext モック
const mockFetchCards = vi.fn();
const mockCardsContext = {
  cards: [] as Card[],
  isLoading: false,
  error: null,
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

const makeDeck = (overrides: Partial<Deck> & { deck_id: string; name: string }): Deck => ({
  user_id: 'user-1',
  card_count: 0,
  due_count: 0,
  created_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

const renderDecksPage = () => {
  return render(
    <MemoryRouter>
      <DecksPage />
    </MemoryRouter>
  );
};

describe('DecksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDecksContext.decks = [];
    mockDecksContext.isLoading = false;
    mockDecksContext.error = null;
    mockCardsContext.cards = [];
  });

  describe('初期表示', () => {
    it('fetchDecks と fetchCards が呼ばれる', () => {
      renderDecksPage();
      expect(mockFetchDecks).toHaveBeenCalled();
      expect(mockFetchCards).toHaveBeenCalled();
    });

    it('ページタイトルが表示される', () => {
      renderDecksPage();
      expect(screen.getByTestId('decks-title')).toHaveTextContent('デッキ');
    });

    it('「新規作成」ボタンが表示される', () => {
      renderDecksPage();
      expect(screen.getByTestId('create-deck-button')).toBeInTheDocument();
    });
  });

  describe('デッキ 0 件時', () => {
    it('空状態メッセージが表示される', () => {
      renderDecksPage();
      expect(
        screen.getByText('デッキを作成して学習を整理しましょう')
      ).toBeInTheDocument();
    });
  });

  describe('デッキ一覧表示', () => {
    it('デッキ名が表示される', () => {
      mockDecksContext.decks = [
        makeDeck({ deck_id: 'deck-1', name: '英語', card_count: 10, due_count: 3 }),
      ];
      renderDecksPage();
      expect(screen.getByText('英語')).toBeInTheDocument();
    });

    it('カード数が表示される', () => {
      mockDecksContext.decks = [
        makeDeck({ deck_id: 'deck-1', name: '英語', card_count: 10, due_count: 3 }),
      ];
      renderDecksPage();
      expect(screen.getByText(/10枚/)).toBeInTheDocument();
    });

    it('due 数が表示される', () => {
      mockDecksContext.decks = [
        makeDeck({ deck_id: 'deck-1', name: '英語', card_count: 10, due_count: 3 }),
      ];
      renderDecksPage();
      expect(screen.getByText(/3/)).toBeInTheDocument();
    });

    it('複数デッキが表示される', () => {
      mockDecksContext.decks = [
        makeDeck({ deck_id: 'deck-1', name: '英語' }),
        makeDeck({ deck_id: 'deck-2', name: '数学' }),
        makeDeck({ deck_id: 'deck-3', name: '理科' }),
      ];
      renderDecksPage();
      expect(screen.getByText('英語')).toBeInTheDocument();
      expect(screen.getByText('数学')).toBeInTheDocument();
      expect(screen.getByText('理科')).toBeInTheDocument();
    });

    it('未分類カード数が表示される', () => {
      mockDecksContext.decks = [
        makeDeck({ deck_id: 'deck-1', name: '英語' }),
      ];
      mockCardsContext.cards = [
        { card_id: 'card-1', front: 'Q1', back: 'A1' } as Card,
        { card_id: 'card-2', front: 'Q2', back: 'A2', deck_id: 'deck-1' } as Card,
      ];
      renderDecksPage();
      expect(screen.getByText('未分類')).toBeInTheDocument();
    });
  });

  describe('ローディング状態', () => {
    it('ローディング中にスピナーが表示される', () => {
      mockDecksContext.isLoading = true;
      renderDecksPage();
      expect(screen.getByText(/読み込み中/)).toBeInTheDocument();
    });
  });

  describe('エラー状態', () => {
    it('エラーメッセージが表示される', () => {
      mockDecksContext.error = new Error('取得に失敗');
      renderDecksPage();
      expect(screen.getByText(/失敗/)).toBeInTheDocument();
    });
  });

  describe('デッキ操作', () => {
    it('「新規作成」ボタンクリックでモーダルが開く', async () => {
      renderDecksPage();

      const createButton = screen.getByTestId('create-deck-button');
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(screen.getByText('デッキを作成')).toBeInTheDocument();
      });
    });

    it('編集ボタンクリックでモーダルが開く', async () => {
      mockDecksContext.decks = [
        makeDeck({ deck_id: 'deck-1', name: '英語' }),
      ];
      renderDecksPage();

      const editButton = screen.getByLabelText('英語を編集');
      fireEvent.click(editButton);

      await waitFor(() => {
        expect(screen.getByText('デッキを編集')).toBeInTheDocument();
      });
    });

    it('削除ボタンクリックで確認ダイアログが表示される', async () => {
      mockDecksContext.decks = [
        makeDeck({ deck_id: 'deck-1', name: '英語' }),
      ];
      renderDecksPage();

      const deleteButton = screen.getByLabelText('英語を削除');
      fireEvent.click(deleteButton);

      await waitFor(() => {
        expect(screen.getByText(/削除しますか/)).toBeInTheDocument();
      });
    });
  });
});

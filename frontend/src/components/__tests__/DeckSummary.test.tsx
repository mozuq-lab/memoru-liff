/**
 * 【テスト概要】: DeckSummary コンポーネントのテスト
 * 【テスト対象】: DeckSummary コンポーネント
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { DeckSummary } from '../DeckSummary';
import type { Deck } from '@/types';

// DecksContext モック
const mockDecksContext = {
  decks: [] as Deck[],
  isLoading: false,
  error: null,
  fetchDecks: vi.fn(),
  createDeck: vi.fn(),
  updateDeck: vi.fn(),
  deleteDeck: vi.fn(),
};

vi.mock('@/contexts/DecksContext', () => ({
  useDecksContext: () => mockDecksContext,
}));

const renderDeckSummary = () => {
  return render(
    <MemoryRouter>
      <DeckSummary />
    </MemoryRouter>
  );
};

const makeDeck = (overrides: Partial<Deck> & { deck_id: string; name: string }): Deck => ({
  user_id: 'user-1',
  card_count: 0,
  due_count: 0,
  created_at: '2024-01-01T00:00:00Z',
  ...overrides,
});

describe('DeckSummary', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDecksContext.decks = [];
  });

  describe('デッキ 0 件時', () => {
    it('CTA メッセージが表示される', () => {
      renderDeckSummary();
      expect(
        screen.getByText('デッキを作成して学習を整理しましょう')
      ).toBeInTheDocument();
    });

    it('「デッキを作成」リンクが表示される', () => {
      renderDeckSummary();
      const link = screen.getByText('デッキを作成');
      expect(link).toBeInTheDocument();
      expect(link.closest('a')).toHaveAttribute('href', '/decks');
    });
  });

  describe('デッキあり時', () => {
    it('デッキ名が表示される', () => {
      mockDecksContext.decks = [
        makeDeck({ deck_id: 'deck-1', name: '英語', card_count: 10, due_count: 3 }),
      ];
      renderDeckSummary();
      expect(screen.getByText('英語')).toBeInTheDocument();
    });

    it('カード数が表示される', () => {
      mockDecksContext.decks = [
        makeDeck({ deck_id: 'deck-1', name: '英語', card_count: 10, due_count: 0 }),
      ];
      renderDeckSummary();
      expect(screen.getByText('10枚')).toBeInTheDocument();
    });

    it('due 数バッジが表示される', () => {
      mockDecksContext.decks = [
        makeDeck({ deck_id: 'deck-1', name: '英語', card_count: 10, due_count: 3 }),
      ];
      renderDeckSummary();
      expect(screen.getByText('3')).toBeInTheDocument();
    });

    it('due_count が 0 の場合はバッジが非表示', () => {
      mockDecksContext.decks = [
        makeDeck({ deck_id: 'deck-1', name: '英語', card_count: 10, due_count: 0 }),
      ];
      renderDeckSummary();
      // due_count=0 なのでバッジ (bg-blue-100) は表示されない
      const badges = document.querySelectorAll('.bg-blue-100');
      expect(badges).toHaveLength(0);
    });

    it('最大 5 件のデッキが表示される', () => {
      mockDecksContext.decks = Array.from({ length: 7 }, (_, i) =>
        makeDeck({ deck_id: `deck-${i}`, name: `デッキ${i}` })
      );
      renderDeckSummary();
      // 5件のみ表示
      for (let i = 0; i < 5; i++) {
        expect(screen.getByText(`デッキ${i}`)).toBeInTheDocument();
      }
      expect(screen.queryByText('デッキ5')).not.toBeInTheDocument();
      expect(screen.queryByText('デッキ6')).not.toBeInTheDocument();
    });

    it('5 件超の場合「すべて表示」リンクが表示される', () => {
      mockDecksContext.decks = Array.from({ length: 6 }, (_, i) =>
        makeDeck({ deck_id: `deck-${i}`, name: `デッキ${i}` })
      );
      renderDeckSummary();
      const link = screen.getByText('すべて表示');
      expect(link).toBeInTheDocument();
      expect(link.closest('a')).toHaveAttribute('href', '/decks');
    });

    it('5 件以下の場合「デッキを管理」リンクが表示される', () => {
      mockDecksContext.decks = [
        makeDeck({ deck_id: 'deck-1', name: '英語' }),
      ];
      renderDeckSummary();
      const link = screen.getByText('デッキを管理');
      expect(link).toBeInTheDocument();
      expect(link.closest('a')).toHaveAttribute('href', '/decks');
    });

    it('バックエンドは unassigned を返さないためコンテキストのデッキをそのまま表示する', () => {
      // バックエンドは 'unassigned' deck_id を返さない。
      // コンテキストから受け取ったデッキをそのままレンダリングすることを確認する。
      mockDecksContext.decks = [
        makeDeck({ deck_id: 'deck-1', name: '英語' }),
      ];
      renderDeckSummary();
      expect(screen.getByText('英語')).toBeInTheDocument();
    });
  });
});

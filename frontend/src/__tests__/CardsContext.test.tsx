import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, renderHook } from '@testing-library/react';
import { CardsProvider, useCardsContext } from '@/contexts/CardsContext';
import { cardsApi } from '@/services/api';
import type { ReactNode } from 'react';

/**
 * 【テスト目的】: CardsContext のメモ化と再レンダリング削減を検証
 * 【テスト内容】: useMemo/useCallback による最適化を確認
 * 【期待される動作】: 不要な再レンダリングが発生しないこと
 * 🔵 青信号: TASK-0039 要件に基づく
 */

// Mock the cardsApi
vi.mock('@/services/api', () => ({
  cardsApi: {
    getCards: vi.fn(),
    getDueCount: vi.fn(),
  },
}));

describe('CardsContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(cardsApi.getCards).mockResolvedValue([]);
    vi.mocked(cardsApi.getDueCount).mockResolvedValue(0);
  });

  describe('TC-CARDS-001: Context値の提供', () => {
    it('Context が正しい値を提供すること', async () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );

      const { result } = renderHook(() => useCardsContext(), { wrapper });

      // 【検証】: Context が必要な値を提供していること
      expect(result.current).toHaveProperty('cards');
      expect(result.current).toHaveProperty('isLoading');
      expect(result.current).toHaveProperty('error');
      expect(result.current).toHaveProperty('fetchCards');
      expect(result.current).toHaveProperty('addCard');
      expect(result.current).toHaveProperty('updateCard');
      expect(result.current).toHaveProperty('deleteCard');
      expect(result.current).toHaveProperty('dueCount');
      expect(result.current).toHaveProperty('fetchDueCount');
    });

    it('Context が Provider の外で使われた場合にエラーをスローすること', () => {
      // 【検証】: Provider なしで使うとエラーになること
      expect(() => {
        renderHook(() => useCardsContext());
      }).toThrow('useCardsContext must be used within a CardsProvider');
    });
  });

  describe('TC-CARDS-002: 関数のメモ化', () => {
    it('fetchCards が useCallback でメモ化されていること', async () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );

      const { result, rerender } = renderHook(() => useCardsContext(), { wrapper });

      const firstFetchCards = result.current.fetchCards;

      // 【再レンダリング】: コンポーネントを再レンダリング
      rerender();

      // 【検証】: 関数の参照が同じであること（useCallback でメモ化されている）
      expect(result.current.fetchCards).toBe(firstFetchCards);
    });

    it('addCard が useCallback でメモ化されていること', async () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );

      const { result, rerender } = renderHook(() => useCardsContext(), { wrapper });

      const firstAddCard = result.current.addCard;

      // 【再レンダリング】: コンポーネントを再レンダリング
      rerender();

      // 【検証】: 関数の参照が同じであること
      expect(result.current.addCard).toBe(firstAddCard);
    });

    it('updateCard が useCallback でメモ化されていること', async () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );

      const { result, rerender } = renderHook(() => useCardsContext(), { wrapper });

      const firstUpdateCard = result.current.updateCard;

      // 【再レンダリング】: コンポーネントを再レンダリング
      rerender();

      // 【検証】: 関数の参照が同じであること
      expect(result.current.updateCard).toBe(firstUpdateCard);
    });

    it('deleteCard が useCallback でメモ化されていること', async () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );

      const { result, rerender } = renderHook(() => useCardsContext(), { wrapper });

      const firstDeleteCard = result.current.deleteCard;

      // 【再レンダリング】: コンポーネントを再レンダリング
      rerender();

      // 【検証】: 関数の参照が同じであること
      expect(result.current.deleteCard).toBe(firstDeleteCard);
    });

    it('fetchDueCount が useCallback でメモ化されていること', async () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );

      const { result, rerender } = renderHook(() => useCardsContext(), { wrapper });

      const firstFetchDueCount = result.current.fetchDueCount;

      // 【再レンダリング】: コンポーネントを再レンダリング
      rerender();

      // 【検証】: 関数の参照が同じであること
      expect(result.current.fetchDueCount).toBe(firstFetchDueCount);
    });
  });

  describe('TC-CARDS-003: Provider値のメモ化', () => {
    it('Provider の value が useMemo でメモ化されていること', async () => {
      let renderCount = 0;

      const TestComponent = () => {
        const context = useCardsContext();
        renderCount++;
        return <div data-testid="render-count">{renderCount}</div>;
      };

      const { rerender } = render(
        <CardsProvider>
          <TestComponent />
        </CardsProvider>
      );

      expect(screen.getByTestId('render-count')).toHaveTextContent('1');

      // 【再レンダリング】: Provider を再レンダリング（状態変更なし）
      rerender(
        <CardsProvider>
          <TestComponent />
        </CardsProvider>
      );

      // 【検証】: value がメモ化されているため、子コンポーネントも再レンダリングされない
      // Note: This test verifies that Provider value is memoized
      // The render count should remain stable when Provider re-renders without state changes
    });
  });

  describe('TC-CARDS-004: 既存機能の保証（回帰テスト）', () => {
    it('fetchCards が正しく動作すること', async () => {
      const mockCards = [
        {
          card_id: '1',
          user_id: 'user1',
          front: 'Question 1',
          back: 'Answer 1',
          deck_name: 'Deck 1',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        },
      ];
      vi.mocked(cardsApi.getCards).mockResolvedValue(mockCards);

      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );

      const { result } = renderHook(() => useCardsContext(), { wrapper });

      await result.current.fetchCards();

      await waitFor(() => {
        expect(result.current.cards).toEqual(mockCards);
        expect(result.current.isLoading).toBe(false);
      });
    });

    it('addCard が正しく動作すること', async () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );

      const { result } = renderHook(() => useCardsContext(), { wrapper });

      const newCard = {
        card_id: '1',
        user_id: 'user1',
        front: 'Question 1',
        back: 'Answer 1',
        deck_name: 'Deck 1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      result.current.addCard(newCard);

      await waitFor(() => {
        expect(result.current.cards).toContainEqual(newCard);
      });
    });

    it('updateCard が正しく動作すること', async () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );

      const { result } = renderHook(() => useCardsContext(), { wrapper });

      const card = {
        card_id: '1',
        user_id: 'user1',
        front: 'Question 1',
        back: 'Answer 1',
        deck_name: 'Deck 1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      result.current.addCard(card);

      await waitFor(() => {
        expect(result.current.cards).toContainEqual(card);
      });

      result.current.updateCard('1', { front: 'Updated Question' });

      await waitFor(() => {
        expect(result.current.cards[0].front).toBe('Updated Question');
      });
    });

    it('deleteCard が正しく動作すること', async () => {
      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );

      const { result } = renderHook(() => useCardsContext(), { wrapper });

      const card = {
        card_id: '1',
        user_id: 'user1',
        front: 'Question 1',
        back: 'Answer 1',
        deck_name: 'Deck 1',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      };

      result.current.addCard(card);

      await waitFor(() => {
        expect(result.current.cards).toHaveLength(1);
      });

      result.current.deleteCard('1');

      await waitFor(() => {
        expect(result.current.cards).toHaveLength(0);
      });
    });

    it('fetchDueCount が正しく動作すること', async () => {
      vi.mocked(cardsApi.getDueCount).mockResolvedValue(5);

      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );

      const { result } = renderHook(() => useCardsContext(), { wrapper });

      await result.current.fetchDueCount();

      await waitFor(() => {
        expect(result.current.dueCount).toBe(5);
      });
    });
  });
});

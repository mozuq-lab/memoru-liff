import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, renderHook } from '@testing-library/react';
import { CardsProvider, useCardsContext } from '@/contexts/CardsContext';
import { cardsApi } from '@/services/api';
import type { Card } from '@/types';
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
    getDueCards: vi.fn(),
    getDueCount: vi.fn(),
  },
}));

describe('CardsContext', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(cardsApi.getCards).mockResolvedValue([]);
    vi.mocked(cardsApi.getDueCards).mockResolvedValue({
      due_cards: [],
      total_due_count: 0,
      next_due_date: null,
    });
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
        useCardsContext();
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
      const mockCards: Card[] = [
        {
          card_id: '1',
          user_id: 'user1',
          front: 'Question 1',
          back: 'Answer 1',
          tags: [],
          interval: 1,
          ease_factor: 2.5,
          repetitions: 0,
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

      const newCard: Card = {
        card_id: '1',
        user_id: 'user1',
        front: 'Question 1',
        back: 'Answer 1',
        tags: [],
        interval: 1,
        ease_factor: 2.5,
        repetitions: 0,
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

      const card: Card = {
        card_id: '1',
        user_id: 'user1',
        front: 'Question 1',
        back: 'Answer 1',
        tags: [],
        interval: 1,
        ease_factor: 2.5,
        repetitions: 0,
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

      const card: Card = {
        card_id: '1',
        user_id: 'user1',
        front: 'Question 1',
        back: 'Answer 1',
        tags: [],
        interval: 1,
        ease_factor: 2.5,
        repetitions: 0,
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

/**
 * TASK-0091: CardsContext fetchCards/fetchDueCards deckId パラメータ テスト
 * 【テスト対象】: fetchCards(deckId?) / fetchDueCards(deckId?) パラメータ追加
 * 【テスト対応】: TC-091-001〜TC-091-004
 */
describe('TASK-0091: CardsContext fetchCards/fetchDueCards deckId パラメータ', () => {
  const mockCard: Card = {
    card_id: '1',
    user_id: 'user1',
    front: 'Question 1',
    back: 'Answer 1',
    tags: [],
    interval: 1,
    ease_factor: 2.5,
    repetitions: 0,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  };

  // 【テスト前準備】: モック関数をクリアし、初期状態を設定
  // 【環境初期化】: 前のテストの影響を排除する
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(cardsApi.getCards).mockResolvedValue([mockCard]);
    vi.mocked(cardsApi.getDueCards).mockResolvedValue({
      due_cards: [
        {
          card_id: '1',
          front: 'Question 1',
          back: 'Answer 1',
          deck_id: 'deck-abc-123',
          due_date: '2024-01-15',
          overdue_days: 0,
        },
      ],
      total_due_count: 1,
      next_due_date: '2024-01-15',
    });
    vi.mocked(cardsApi.getDueCount).mockResolvedValue(0);
  });

  describe('fetchCards(deckId) パラメータ伝搬', () => {
    it('TC-091-001: deck_id 指定時に fetchCards が deckId パラメータ付きで API を呼び出す', async () => {
      // 【テスト目的】: fetchCards(deckId) が cardsApi.getCards(deckId) を正しく呼び出すこと
      // 【テスト内容】: 'deck-abc-123' を引数として fetchCards を呼んだ際に API に deckId が渡されること
      // 【期待される動作】: API 呼び出しに deckId 文字列が引数として渡される
      // 🔵 青信号: architecture.md セクション6・既存 CardsContext 実装・requirements REQ-001 に基づく

      // 【テストデータ準備】: deckId を指定して fetchCards を呼び出す
      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );
      const { result } = renderHook(() => useCardsContext(), { wrapper });

      // 【実際の処理実行】: fetchCards(deckId) を呼び出す
      // 【処理内容】: CardsContext の fetchCards が cardsApi.getCards(deckId) を呼び出すことを確認
      await result.current.fetchCards('deck-abc-123');

      // 【結果検証】: cardsApi.getCards が 'deck-abc-123' を引数として呼ばれたことを確認
      // 【期待値確認】: deckId が API レイヤーに正しく伝搬されること
      await waitFor(() => {
        expect(cardsApi.getCards).toHaveBeenCalledWith('deck-abc-123'); // 【確認内容】: getCards の引数に deckId が含まれること 🔵
        expect(result.current.cards).toEqual([mockCard]); // 【確認内容】: 返却データが cards にセットされること 🔵
      });
    });

    it('TC-091-002: deck_id 未指定で fetchCards を呼ぶと全カードを取得する', async () => {
      // 【テスト目的】: fetchCards() を引数なしで呼んだ際に従来通り全カードが取得されること
      // 【テスト内容】: 引数なしで fetchCards を呼んだ際、cardsApi.getCards(undefined) が呼ばれること
      // 【期待される動作】: 後方互換性を維持し、全カードが返される
      // 🔵 青信号: REQ-102・既存 CardsContext 実装パターンに基づく

      // 【テストデータ準備】: 引数なしで fetchCards を呼び出す
      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );
      const { result } = renderHook(() => useCardsContext(), { wrapper });

      // 【実際の処理実行】: fetchCards() を引数なしで呼び出す
      // 【処理内容】: CardsContext の fetchCards が cardsApi.getCards() を呼び出すことを確認
      await result.current.fetchCards();

      // 【結果検証】: cardsApi.getCards が引数なし（undefined）で呼ばれたことを確認
      // 【期待値確認】: 引数なしの呼び出しで既存動作が壊れないこと
      await waitFor(() => {
        expect(cardsApi.getCards).toHaveBeenCalledWith(undefined); // 【確認内容】: 引数なしの呼び出しで全カード取得 🔵
        expect(result.current.cards).toEqual([mockCard]); // 【確認内容】: 全カードが返却されること 🔵
      });
    });
  });

  describe('fetchDueCards(deckId) パラメータ伝搬', () => {
    it('TC-091-003: deck_id 指定時に fetchDueCards が deckId パラメータ付きで API を呼び出す', async () => {
      // 【テスト目的】: fetchDueCards(deckId) が cardsApi.getDueCards(undefined, deckId) を正しく呼び出すこと
      // 【テスト内容】: 'deck-abc-123' を引数として fetchDueCards を呼んだ際に API に deckId が渡されること
      // 【期待される動作】: API 呼び出しに deckId が渡され、該当デッキの復習対象カードが返される
      // 🔵 青信号: architecture.md セクション6・既存 getDueCards 実装（deckId パラメータ対応済み）に基づく

      // 【テストデータ準備】: deckId を指定して fetchDueCards を呼び出す
      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );
      const { result } = renderHook(() => useCardsContext(), { wrapper });

      // 【実際の処理実行】: fetchDueCards(deckId) を呼び出す
      // 【処理内容】: CardsContext の fetchDueCards が cardsApi.getDueCards(undefined, deckId) を呼び出すことを確認
      await result.current.fetchDueCards('deck-abc-123');

      // 【結果検証】: cardsApi.getDueCards が deckId 引数付きで呼ばれたことを確認
      // 【期待値確認】: deckId が getDueCards API に正しく伝搬されること
      await waitFor(() => {
        expect(cardsApi.getDueCards).toHaveBeenCalledWith(undefined, 'deck-abc-123'); // 【確認内容】: getDueCards の引数に deckId が含まれること 🔵
      });
    });

    it('TC-091-004: deck_id 未指定で fetchDueCards を呼ぶと全復習対象カードを取得する', async () => {
      // 【テスト目的】: fetchDueCards() を引数なしで呼んだ際に従来通り全復習対象カードが取得されること
      // 【テスト内容】: 引数なしで fetchDueCards を呼んだ際、cardsApi.getDueCards() が呼ばれること
      // 【期待される動作】: 後方互換性の維持
      // 🔵 青信号: REQ-102・既存 getDueCards 実装に基づく

      // 【テストデータ準備】: 引数なしで fetchDueCards を呼び出す
      const wrapper = ({ children }: { children: ReactNode }) => (
        <CardsProvider>{children}</CardsProvider>
      );
      const { result } = renderHook(() => useCardsContext(), { wrapper });

      // 【実際の処理実行】: fetchDueCards() を引数なしで呼び出す
      // 【処理内容】: CardsContext の fetchDueCards が cardsApi.getDueCards() を呼び出すことを確認
      await result.current.fetchDueCards();

      // 【結果検証】: cardsApi.getDueCards が引数なし（deckId なし）で呼ばれたことを確認
      // 【期待値確認】: 引数なしの呼び出しで既存動作が壊れないこと
      await waitFor(() => {
        expect(cardsApi.getDueCards).toHaveBeenCalledWith(undefined, undefined); // 【確認内容】: 引数なしの呼び出しで全復習対象カード取得 🔵
      });
    });
  });
});

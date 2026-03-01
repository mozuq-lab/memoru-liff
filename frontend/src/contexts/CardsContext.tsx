import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from 'react';
import type { Card, DueCard } from '@/types';
import { cardsApi } from '@/services/api';

interface CardsContextType {
  cards: Card[];
  dueCards: Card[];
  isLoading: boolean;
  error: Error | null;
  // 【TASK-0091】: deckId パラメータ追加（省略時は従来通り全カード取得） 🔵
  fetchCards: (deckId?: string) => Promise<void>;
  fetchDueCards: (deckId?: string) => Promise<void>;
  addCard: (card: Card) => void;
  updateCard: (cardId: string, updates: Partial<Card>) => void;
  deleteCard: (cardId: string) => void;
  dueCount: number;
  fetchDueCount: () => Promise<void>;
}

const CardsContext = createContext<CardsContextType | undefined>(undefined);

interface CardsProviderProps {
  children: ReactNode;
}

const dueCardToCard = (due: DueCard): Card => ({
  card_id: due.card_id,
  user_id: '',
  front: due.front,
  back: due.back,
  deck_id: due.deck_id,
  tags: [],
  next_review_at: due.due_date,
  interval: 0,
  ease_factor: 0,
  repetitions: 0,
  created_at: '',
  updated_at: null,
});

export const CardsProvider = ({ children }: CardsProviderProps) => {
  const [cards, setCards] = useState<Card[]>([]);
  const [dueCards, setDueCards] = useState<Card[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [dueCount, setDueCount] = useState(0);

  /**
   * 【機能概要】: カード一覧を取得してStateを更新する
   * 【実装方針】: deckId が指定された場合はフィルタあり、省略時は全カード取得（後方互換）
   * 【テスト対応】: TC-091-001, TC-091-002
   * 🔵 青信号: architecture.md セクション6・REQ-001・REQ-102 に基づく
   * @param deckId - フィルタするデッキID（省略時は全カード取得）
   */
  const fetchCards = useCallback(async (deckId?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      // 【API呼び出し】: deckId を API レイヤーに伝搬（undefined の場合は全カード取得）
      const data = await cardsApi.getCards(deckId);
      setCards(data);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * 【機能概要】: 復習対象カードを取得してStateを更新する
   * 【実装方針】: deckId が指定された場合はフィルタあり、省略時は全復習対象カード取得（後方互換）
   * 【テスト対応】: TC-091-003, TC-091-004
   * 🔵 青信号: architecture.md セクション6・既存 getDueCards 実装（deckId パラメータ対応済み）に基づく
   * @param deckId - フィルタするデッキID（省略時は全復習対象カード取得）
   */
  const fetchDueCards = useCallback(async (deckId?: string) => {
    setIsLoading(true);
    setError(null);
    try {
      // 【API呼び出し】: limit は undefined、deckId を第2引数として伝搬
      const response = await cardsApi.getDueCards(undefined, deckId);
      setDueCards(response.due_cards.map(dueCardToCard));
      setDueCount(response.total_due_count);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const addCard = useCallback((card: Card) => {
    setCards(prev => [...prev, card]);
  }, []);

  const updateCard = useCallback((cardId: string, updates: Partial<Card>) => {
    setCards(prev => prev.map(card =>
      card.card_id === cardId ? { ...card, ...updates } : card
    ));
  }, []);

  const deleteCard = useCallback((cardId: string) => {
    setCards(prev => prev.filter(card => card.card_id !== cardId));
  }, []);

  const fetchDueCount = useCallback(async () => {
    try {
      const count = await cardsApi.getDueCount();
      setDueCount(count);
    } catch (err) {
      console.error('Failed to fetch due count:', err);
    }
  }, []);

  const value = useMemo(
    () => ({
      cards,
      dueCards,
      isLoading,
      error,
      fetchCards,
      fetchDueCards,
      addCard,
      updateCard,
      deleteCard,
      dueCount,
      fetchDueCount,
    }),
    [cards, dueCards, isLoading, error, fetchCards, fetchDueCards, addCard, updateCard, deleteCard, dueCount, fetchDueCount]
  );

  return (
    <CardsContext.Provider value={value}>
      {children}
    </CardsContext.Provider>
  );
};

export const useCardsContext = (): CardsContextType => {
  const context = useContext(CardsContext);
  if (context === undefined) {
    throw new Error('useCardsContext must be used within a CardsProvider');
  }
  return context;
};

import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from 'react';
import type { Card, DueCard } from '@/types';
import { cardsApi } from '@/services/api';

interface CardsContextType {
  cards: Card[];
  dueCards: Card[];
  isLoading: boolean;
  error: Error | null;
  fetchCards: () => Promise<void>;
  fetchDueCards: () => Promise<void>;
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

  const fetchCards = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await cardsApi.getCards();
      setCards(data);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchDueCards = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await cardsApi.getDueCards();
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

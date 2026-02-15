import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from 'react';
import type { Card } from '@/types';
import { cardsApi } from '@/services/api';

interface CardsContextType {
  cards: Card[];
  isLoading: boolean;
  error: Error | null;
  fetchCards: () => Promise<void>;
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

export const CardsProvider = ({ children }: CardsProviderProps) => {
  const [cards, setCards] = useState<Card[]>([]);
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
      isLoading,
      error,
      fetchCards,
      addCard,
      updateCard,
      deleteCard,
      dueCount,
      fetchDueCount,
    }),
    [cards, isLoading, error, fetchCards, addCard, updateCard, deleteCard, dueCount, fetchDueCount]
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

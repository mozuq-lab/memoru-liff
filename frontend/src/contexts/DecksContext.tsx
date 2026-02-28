import { createContext, useContext, useState, useCallback, useMemo, type ReactNode } from 'react';
import type { Deck, CreateDeckRequest, UpdateDeckRequest } from '@/types';
import { decksApi } from '@/services/api';

interface DecksContextType {
  decks: Deck[];
  isLoading: boolean;
  error: Error | null;
  fetchDecks: () => Promise<void>;
  createDeck: (data: CreateDeckRequest) => Promise<Deck>;
  updateDeck: (id: string, data: UpdateDeckRequest) => Promise<Deck>;
  deleteDeck: (id: string) => Promise<void>;
}

const DecksContext = createContext<DecksContextType | undefined>(undefined);

interface DecksProviderProps {
  children: ReactNode;
}

export const DecksProvider = ({ children }: DecksProviderProps) => {
  const [decks, setDecks] = useState<Deck[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const fetchDecks = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await decksApi.getDecks();
      setDecks(data);
    } catch (err) {
      setError(err as Error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const createDeck = useCallback(async (data: CreateDeckRequest): Promise<Deck> => {
    const deck = await decksApi.createDeck(data);
    await fetchDecks();
    return deck;
  }, [fetchDecks]);

  const updateDeck = useCallback(async (id: string, data: UpdateDeckRequest): Promise<Deck> => {
    const deck = await decksApi.updateDeck(id, data);
    await fetchDecks();
    return deck;
  }, [fetchDecks]);

  const deleteDeck = useCallback(async (id: string): Promise<void> => {
    await decksApi.deleteDeck(id);
    await fetchDecks();
  }, [fetchDecks]);

  const value = useMemo(
    () => ({
      decks,
      isLoading,
      error,
      fetchDecks,
      createDeck,
      updateDeck,
      deleteDeck,
    }),
    [decks, isLoading, error, fetchDecks, createDeck, updateDeck, deleteDeck]
  );

  return (
    <DecksContext.Provider value={value}>
      {children}
    </DecksContext.Provider>
  );
};

export const useDecksContext = (): DecksContextType => {
  const context = useContext(DecksContext);
  if (context === undefined) {
    throw new Error('useDecksContext must be used within a DecksProvider');
  }
  return context;
};

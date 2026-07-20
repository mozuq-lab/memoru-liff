import { createContext, useContext, useState, useCallback, useMemo, useRef, type ReactNode } from 'react';
import type { Card, DueCard } from '@/types';
import { cardsApi } from '@/services/api';
import { toError } from '@/utils/error';

// F-3: AbortError 判定ヘルパー — 中断起因のエラーは error state に入れない
const isAbortError = (err: unknown): boolean =>
  err instanceof DOMException && err.name === 'AbortError';

interface CardsContextType {
  cards: Card[];
  dueCards: Card[];
  // M-32 / M-36: fetchCards と fetchDueCards で isLoading を共有すると、一方の完了で
  //   ローディング表示が早期に消えてちらつく。関心事ごとに loading を分離する。
  //   isLoading は「どちらかが読み込み中」を表す後方互換のための集約フラグ。
  isLoading: boolean;
  isCardsLoading: boolean;
  isDueCardsLoading: boolean;
  error: Error | null;
  // 【TASK-0091】: deckId パラメータ追加（省略時は従来通り全カード取得） 🔵
  fetchCards: (deckId?: string, options?: { signal?: AbortSignal }) => Promise<void>;
  fetchDueCards: (deckId?: string, options?: { signal?: AbortSignal }) => Promise<void>;
  addCard: (card: Card) => void;
  updateCard: (cardId: string, updates: Partial<Card>) => void;
  deleteCard: (cardId: string) => void;
  dueCount: number;
  fetchDueCount: () => Promise<void>;
  // F-8: ページ横断で残留する error をクリアする
  clearError: () => void;
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
  // M-32 / M-36: cards 取得と dueCards 取得で loading を分離する
  const [isCardsLoading, setIsCardsLoading] = useState(false);
  const [isDueCardsLoading, setIsDueCardsLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [dueCount, setDueCount] = useState(0);
  // F-3: 最新リクエスト ID を保持し、古い fetch の結果（タブ/デッキ連続切替時）を破棄する
  const cardsRequestIdRef = useRef(0);
  const dueCardsRequestIdRef = useRef(0);

  /**
   * 【機能概要】: カード一覧を取得してStateを更新する
   * 【実装方針】: deckId が指定された場合はフィルタあり、省略時は全カード取得（後方互換）
   * 【テスト対応】: TC-091-001, TC-091-002
   * 🔵 青信号: architecture.md セクション6・REQ-001・REQ-102 に基づく
   * @param deckId - フィルタするデッキID（省略時は全カード取得）
   */
  const fetchCards = useCallback(async (deckId?: string, options?: { signal?: AbortSignal }) => {
    // F-3: このリクエストの ID を採番。完了時に最新でなければ結果を破棄する
    const requestId = ++cardsRequestIdRef.current;
    // M-32 / M-36: cards 専用の loading フラグのみを操作する
    setIsCardsLoading(true);
    setError(null);
    try {
      // 【API呼び出し】: deckId を API レイヤーに伝搬（undefined の場合は全カード取得）
      // F-3: signal を fetch まで伝播し、古いリクエストを実際にキャンセルする
      const data = await cardsApi.getCards(deckId, { signal: options?.signal });
      // F-3: 中断済み or 後発リクエストが走っている場合は古い結果を破棄
      if (options?.signal?.aborted || requestId !== cardsRequestIdRef.current) return;
      setCards(data);
    } catch (err) {
      if (options?.signal?.aborted || isAbortError(err) || requestId !== cardsRequestIdRef.current) return;
      // 【W-30修正】: 型安全なエラーラッピング
      setError(toError(err));
    } finally {
      // High-2: abort されても最新リクエストであれば必ずローディングを解除する。
      //   ここで aborted を理由に解除をスキップすると、フェッチ中に画面遷移して
      //   unmount 時のクリーンアップが abort した場合に isCardsLoading が
      //   true のまま残留し、CardsProvider が最上位にあるため SPA 内では
      //   回復できなくなる（フルリロードのみ）。requestId ガードにより、
      //   後続リクエストが既に走っている場合の誤解除は起きない
      //  （新リクエスト開始時に ref が更新されるため）。
      if (requestId === cardsRequestIdRef.current) {
        setIsCardsLoading(false);
      }
    }
  }, []);

  /**
   * 【機能概要】: 復習対象カードを取得してStateを更新する
   * 【実装方針】: deckId が指定された場合はフィルタあり、省略時は全復習対象カード取得（後方互換）
   * 【テスト対応】: TC-091-003, TC-091-004
   * 🔵 青信号: architecture.md セクション6・既存 getDueCards 実装（deckId パラメータ対応済み）に基づく
   * @param deckId - フィルタするデッキID（省略時は全復習対象カード取得）
   */
  const fetchDueCards = useCallback(async (deckId?: string, options?: { signal?: AbortSignal }) => {
    // F-3: このリクエストの ID を採番。完了時に最新でなければ結果を破棄する
    const requestId = ++dueCardsRequestIdRef.current;
    // M-32 / M-36: dueCards 専用の loading フラグのみを操作する
    setIsDueCardsLoading(true);
    setError(null);
    try {
      // 【API呼び出し】: limit は undefined、deckId を第2引数として伝搬
      // F-3: signal を fetch まで伝播し、古いリクエストを実際にキャンセルする
      const response = await cardsApi.getDueCards(undefined, deckId, { signal: options?.signal });
      // F-3: 中断済み or 後発リクエストが走っている場合は古い結果を破棄
      if (options?.signal?.aborted || requestId !== dueCardsRequestIdRef.current) return;
      setDueCards(response.due_cards.map(dueCardToCard));
      setDueCount(response.total_due_count);
    } catch (err) {
      if (options?.signal?.aborted || isAbortError(err) || requestId !== dueCardsRequestIdRef.current) return;
      // 【W-30修正】: 型安全なエラーラッピング
      setError(toError(err));
    } finally {
      // High-2: abort されても最新リクエストであれば必ずローディングを解除する
      //   （fetchCards と同じ理由。詳細は fetchCards 側のコメント参照）。
      if (requestId === dueCardsRequestIdRef.current) {
        setIsDueCardsLoading(false);
      }
    }
  }, []);

  // P2: ローカルな mutation も進行中の fetchCards の古いレスポンス（line 84）で
  //     打ち消されないよう世代を進める（DecksContext と同じ競合対策）。
  // P3: 世代を進めると進行中 fetchCards の finally（line 91）が loading を解除できなく
  //     なるため、ここで明示的に解除して残留を防ぐ（mutation 後はローカルデータが最新）。
  const addCard = useCallback((card: Card) => {
    cardsRequestIdRef.current++;
    setIsCardsLoading(false);
    setCards(prev => [...prev, card]);
  }, []);

  const updateCard = useCallback((cardId: string, updates: Partial<Card>) => {
    cardsRequestIdRef.current++;
    setIsCardsLoading(false);
    setCards(prev => prev.map(card =>
      card.card_id === cardId ? { ...card, ...updates } : card
    ));
  }, []);

  const deleteCard = useCallback((cardId: string) => {
    cardsRequestIdRef.current++;
    setIsCardsLoading(false);
    setCards(prev => prev.filter(card => card.card_id !== cardId));
  }, []);

  // F-8: error はページ横断で残留するため、各ページのマウント時に明示的にクリアできるようにする
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const fetchDueCount = useCallback(async () => {
    try {
      const count = await cardsApi.getDueCount();
      setDueCount(count);
    } catch (err) {
      // L-26: console.error のみでは UI が失敗を検知できないため error state へも反映する。
      //   HomePage の `if (error)` 分岐がデータ取得失敗をユーザーに通知できるようにする。
      console.error('Failed to fetch due count:', err);
      setError(toError(err));
    }
  }, []);

  // M-32 / M-36: 後方互換のため isLoading は「いずれかが読み込み中」を表す集約フラグとして派生させる
  const isLoading = isCardsLoading || isDueCardsLoading;

  const value = useMemo(
    () => ({
      cards,
      dueCards,
      isLoading,
      isCardsLoading,
      isDueCardsLoading,
      error,
      fetchCards,
      fetchDueCards,
      addCard,
      updateCard,
      deleteCard,
      dueCount,
      fetchDueCount,
      clearError,
    }),
    [cards, dueCards, isLoading, isCardsLoading, isDueCardsLoading, error, fetchCards, fetchDueCards, addCard, updateCard, deleteCard, dueCount, fetchDueCount, clearError]
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

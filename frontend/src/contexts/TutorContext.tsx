import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  type ReactNode,
} from "react";
import type { TutorSession, TutorMessage, LearningMode } from "@/types";
import * as tutorApi from "@/services/tutor-api";
import { ApiError, getUserFacingMessage } from "@/services/api";
import { TIMEOUT_MS, MESSAGE_LIMIT } from "@/constants/tutor";

interface TutorContextType {
  session: TutorSession | null;
  messages: TutorMessage[];
  isLoading: boolean;
  error: string | null;
  isLimitReached: boolean;
  isTimedOut: boolean;
  isInsufficientReviewData: boolean;
  isEmptyDeck: boolean;
  retryLastMessage: () => Promise<void>;
  startSession: (deckId: string, mode: LearningMode) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  endSession: () => Promise<void>;
  resumeSession: (deckId: string) => Promise<boolean>;
  clearError: () => void;
}

const TutorContext = createContext<TutorContextType | undefined>(undefined);

interface TutorProviderProps {
  children: ReactNode;
}

export const TutorProvider = ({ children }: TutorProviderProps) => {
  const [session, setSession] = useState<TutorSession | null>(null);
  const [messages, setMessages] = useState<TutorMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLimitReached, setIsLimitReached] = useState(false);
  const [isTimedOut, setIsTimedOut] = useState(false);
  const [isInsufficientReviewData, setIsInsufficientReviewData] =
    useState(false);
  const [isEmptyDeck, setIsEmptyDeck] = useState(false);
  const lastFailedContentRef = useRef<string | null>(null);
  const timeoutTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearError = useCallback(() => {
    setError(null);
    setIsInsufficientReviewData(false);
    setIsEmptyDeck(false);
  }, []);

  /** タイムアウトタイマーを(再)設定 */
  const resetTimeoutTimer = useCallback(() => {
    if (timeoutTimerRef.current) {
      clearTimeout(timeoutTimerRef.current);
    }
    timeoutTimerRef.current = setTimeout(() => {
      setIsTimedOut(true);
    }, TIMEOUT_MS);
  }, []);

  const clearTimeoutTimer = useCallback(() => {
    if (timeoutTimerRef.current) {
      clearTimeout(timeoutTimerRef.current);
      timeoutTimerRef.current = null;
    }
  }, []);

  // アンマウント時にタイマーをクリーンアップ
  useEffect(() => {
    return () => {
      clearTimeoutTimer();
    };
  }, [clearTimeoutTimer]);

  const startSession = useCallback(
    async (deckId: string, mode: LearningMode) => {
      setIsLoading(true);
      setError(null);
      setIsLimitReached(false);
      setIsTimedOut(false);
      setIsInsufficientReviewData(false);
      setIsEmptyDeck(false);
      try {
        const newSession = await tutorApi.startSession({
          deck_id: deckId,
          mode,
        });
        setSession(newSession);
        setMessages(newSession.messages);
        resetTimeoutTimer();
      } catch (err) {
        // E-3: 422 業務エラーは status で判定。バックエンド (tutor_handler.py) の
        // InsufficientReviewDataError / EmptyDeckError はいずれも 422 で code を持たないため、
        // 422 でゲートしたうえで 2 種のうちどちらかをメッセージ文字列で識別する。
        if (err instanceof ApiError && err.status === 422) {
          const message = err.message;
          // Detect 422 insufficient review data for weak_point mode
          if (
            message.includes("レビュー履歴が不足") ||
            message.includes("insufficient review")
          ) {
            setIsInsufficientReviewData(true);
          }
          // Detect 422 empty deck
          if (
            message.includes("カードがありません") ||
            message.includes("no cards")
          ) {
            setIsEmptyDeck(true);
          }
        }
        // E-1: 業務エラー(4xx)はメッセージを表示、想定外(5xx/ネットワーク)は固定文言
        setError(getUserFacingMessage(err, "セッションの開始に失敗しました"));
      } finally {
        setIsLoading(false);
      }
    },
    [resetTimeoutTimer],
  );

  const sendMessage = useCallback(
    async (content: string) => {
      if (!session) return;
      setIsLoading(true);
      setError(null);
      lastFailedContentRef.current = null;

      // Optimistically add user message with tempId for safe removal on error
      const tempId = crypto.randomUUID();
      const userMsg: TutorMessage = {
        role: "user",
        content,
        related_cards: [],
        timestamp: new Date().toISOString(),
        tempId,
      };
      setMessages((prev) => [...prev, userMsg]);

      try {
        const response = await tutorApi.sendMessage(session.session_id, {
          content,
        });
        // Remove tempId from optimistic message and append assistant response
        setMessages((prev) => [
          ...prev.map((m) => (m.tempId === tempId ? { ...m, tempId: undefined } : m)),
          response.message,
        ]);
        setSession((prev) =>
          prev ? { ...prev, message_count: response.message_count } : null,
        );
        if (response.is_limit_reached) {
          setIsLimitReached(true);
        }
        resetTimeoutTimer();
      } catch (err) {
        // Remove optimistic user message by tempId (safe even if other messages were added)
        setMessages((prev) => prev.filter((m) => m.tempId !== tempId));
        lastFailedContentRef.current = content;
        // E-1: 業務エラー(4xx)はメッセージを表示、想定外(5xx/ネットワーク)は固定文言
        setError(getUserFacingMessage(err, "メッセージの送信に失敗しました"));
      } finally {
        setIsLoading(false);
      }
    },
    [session, resetTimeoutTimer],
  );

  const retryLastMessage = useCallback(async () => {
    const content = lastFailedContentRef.current;
    if (!content) return;
    await sendMessage(content);
  }, [sendMessage]);

  const endSession = useCallback(async () => {
    if (!session) return;
    setIsLoading(true);
    setError(null);
    try {
      await tutorApi.endSession(session.session_id);
    } catch {
      // 409 (already ended) / 404 (not found) are expected — ignore
    } finally {
      // Always clear local state regardless of API result
      setSession(null);
      setMessages([]);
      setIsLimitReached(false);
      setIsTimedOut(false);
      clearTimeoutTimer();
      setIsLoading(false);
    }
  }, [session, clearTimeoutTimer]);

  /** deckId に対するアクティブセッションがあれば復帰。true=復帰成功 */
  const resumeSession = useCallback(
    async (deckId: string): Promise<boolean> => {
      setIsLoading(true);
      setError(null);
      try {
        const { sessions } = await tutorApi.listSessions("active", deckId);
        if (sessions.length > 0) {
          const active = await tutorApi.getSession(sessions[0].session_id);

          // Check timeout
          const lastUpdate = new Date(active.updated_at).getTime();
          if (Date.now() - lastUpdate > TIMEOUT_MS) {
            setIsTimedOut(true);
            setSession(null);
            setMessages([]);
            return false;
          }

          setSession(active);
          setMessages(active.messages);
          setIsLimitReached(active.message_count >= MESSAGE_LIMIT);
          resetTimeoutTimer();
          return true;
        }
        return false;
      } catch {
        return false;
      } finally {
        setIsLoading(false);
      }
    },
    [resetTimeoutTimer],
  );

  const value = useMemo(
    () => ({
      session,
      messages,
      isLoading,
      error,
      isLimitReached,
      isTimedOut,
      isInsufficientReviewData,
      isEmptyDeck,
      retryLastMessage,
      startSession,
      sendMessage,
      endSession,
      resumeSession,
      clearError,
    }),
    [
      session,
      messages,
      isLoading,
      error,
      isLimitReached,
      isTimedOut,
      isInsufficientReviewData,
      isEmptyDeck,
      retryLastMessage,
      startSession,
      sendMessage,
      endSession,
      resumeSession,
      clearError,
    ],
  );

  return (
    <TutorContext.Provider value={value}>{children}</TutorContext.Provider>
  );
};

export const useTutorContext = (): TutorContextType => {
  const context = useContext(TutorContext);
  if (context === undefined) {
    throw new Error("useTutorContext must be used within a TutorProvider");
  }
  return context;
};

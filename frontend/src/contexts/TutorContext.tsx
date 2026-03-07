import {
  createContext,
  useContext,
  useState,
  useCallback,
  useMemo,
  useRef,
  type ReactNode,
} from "react";
import type { TutorSession, TutorMessage, LearningMode } from "@/types";
import * as tutorApi from "@/services/tutor-api";

interface TutorContextType {
  session: TutorSession | null;
  messages: TutorMessage[];
  isLoading: boolean;
  error: string | null;
  isLimitReached: boolean;
  isTimedOut: boolean;
  isInsufficientReviewData: boolean;
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

/** 30分のタイムアウト閾値（ミリ秒） */
const TIMEOUT_MS = 30 * 60 * 1000;

export const TutorProvider = ({ children }: TutorProviderProps) => {
  const [session, setSession] = useState<TutorSession | null>(null);
  const [messages, setMessages] = useState<TutorMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLimitReached, setIsLimitReached] = useState(false);
  const [isTimedOut, setIsTimedOut] = useState(false);
  const [isInsufficientReviewData, setIsInsufficientReviewData] =
    useState(false);
  const timeoutTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearError = useCallback(() => {
    setError(null);
    setIsInsufficientReviewData(false);
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

  const startSession = useCallback(
    async (deckId: string, mode: LearningMode) => {
      setIsLoading(true);
      setError(null);
      setIsLimitReached(false);
      setIsTimedOut(false);
      setIsInsufficientReviewData(false);
      try {
        const newSession = await tutorApi.startSession({
          deck_id: deckId,
          mode,
        });
        setSession(newSession);
        setMessages(newSession.messages);
        resetTimeoutTimer();
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "セッションの開始に失敗しました";
        // Detect 422 insufficient review data for weak_point mode
        if (
          message.includes("レビュー履歴が不足") ||
          message.includes("insufficient review")
        ) {
          setIsInsufficientReviewData(true);
        }
        setError(message);
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

      // Optimistically add user message
      const userMsg: TutorMessage = {
        role: "user",
        content,
        related_cards: [],
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);

      try {
        const response = await tutorApi.sendMessage(session.session_id, {
          content,
        });
        setMessages((prev) => [...prev, response.message]);
        setSession((prev) =>
          prev ? { ...prev, message_count: response.message_count } : null,
        );
        if (response.is_limit_reached) {
          setIsLimitReached(true);
        }
        resetTimeoutTimer();
      } catch (err) {
        // Remove optimistic user message on error
        setMessages((prev) => prev.slice(0, -1));
        const message =
          err instanceof Error ? err.message : "メッセージの送信に失敗しました";
        setError(message);
      } finally {
        setIsLoading(false);
      }
    },
    [session, resetTimeoutTimer],
  );

  const endSession = useCallback(async () => {
    if (!session) return;
    setIsLoading(true);
    setError(null);
    try {
      await tutorApi.endSession(session.session_id);
      setSession(null);
      setMessages([]);
      setIsLimitReached(false);
      setIsTimedOut(false);
      clearTimeoutTimer();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "セッションの終了に失敗しました";
      setError(message);
    } finally {
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
          setIsLimitReached(active.message_count >= 20);
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

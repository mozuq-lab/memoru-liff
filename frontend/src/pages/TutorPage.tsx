import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTutorContext } from "@/contexts/TutorContext";
import { ModeSelector } from "@/components/tutor/ModeSelector";
import { ChatMessage } from "@/components/tutor/ChatMessage";
import { ChatInput } from "@/components/tutor/ChatInput";
import { SessionList } from "@/components/tutor/SessionList";
import { Loading } from "@/components/common/Loading";
import { Error } from "@/components/common/Error";
import type { LearningMode } from "@/types";

type PageView = "mode-select" | "chat" | "history";

export const TutorPage = () => {
  const { deckId } = useParams<{ deckId: string }>();
  const navigate = useNavigate();
  const {
    session,
    messages,
    isLoading,
    error,
    isLimitReached,
    isTimedOut,
    isInsufficientReviewData,
    isEmptyDeck,
    startSession,
    sendMessage,
    endSession,
    resumeSession,
    retryLastMessage,
    clearError,
  } = useTutorContext();

  const [view, setView] = useState<PageView>("mode-select");
  const [showEndConfirm, setShowEndConfirm] = useState(false);
  const [resumeChecked, setResumeChecked] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // T020: セッション継続ロジック — マウント時にアクティブセッションを確認
  useEffect(() => {
    if (!deckId || resumeChecked) return;
    setResumeChecked(true);
    resumeSession(deckId).then((resumed) => {
      if (resumed) {
        setView("chat");
      }
    });
  }, [deckId, resumeChecked, resumeSession]);

  // Auto-scroll when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // When session starts (not via mode switch), switch to chat view
  const [pendingModeSwitch, setPendingModeSwitch] = useState(false);
  useEffect(() => {
    if (session && view === "mode-select" && !pendingModeSwitch) {
      setView("chat");
    }
  }, [session, view, pendingModeSwitch]);

  if (!deckId) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Error message="デッキIDが指定されていません" />
      </div>
    );
  }

  const handleModeSelect = async (mode: LearningMode) => {
    setPendingModeSwitch(false);
    await startSession(deckId, mode);
  };

  const handleSendMessage = async (content: string) => {
    await sendMessage(content);
  };

  // T025a: モード切り替え — セッションをクリアしてモード選択に戻る
  const handleModeSwitch = async () => {
    if (session) {
      await endSession();
    }
    setPendingModeSwitch(true);
    setView("mode-select");
  };

  const handleEndSession = async () => {
    setShowEndConfirm(false);
    await endSession();
    setView("mode-select");
  };

  const handleViewHistory = () => {
    setView("history");
  };

  const handleBackFromHistory = () => {
    setView(session ? "chat" : "mode-select");
  };

  // T022: セッション履歴ビュー
  if (view === "history") {
    return (
      <div className="flex flex-col h-screen">
        <header className="bg-white shadow-sm p-4 flex items-center gap-3">
          <button
            onClick={handleBackFromHistory}
            className="p-2 text-gray-500 hover:text-gray-700 min-w-[44px] min-h-[44px] flex items-center justify-center"
            aria-label="戻る"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
          </button>
          <h1 className="text-lg font-semibold text-gray-800">
            セッション履歴
          </h1>
        </header>
        <div className="flex-1 overflow-y-auto p-4">
          <SessionList deckId={deckId} />
        </div>
      </div>
    );
  }

  // Mode selection view
  if (view === "mode-select") {
    return (
      <div className="flex flex-col h-screen">
        <header className="bg-white shadow-sm p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate(-1)}
              className="p-2 text-gray-500 hover:text-gray-700 min-w-[44px] min-h-[44px] flex items-center justify-center"
              aria-label="戻る"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </button>
            <h1 className="text-lg font-semibold text-gray-800">
              AI チューター
            </h1>
          </div>
          <button
            onClick={handleViewHistory}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            履歴
          </button>
        </header>
        <div className="flex-1 overflow-y-auto p-4">
          {isLoading && <Loading message="セッションを準備中..." />}
          {error && (
            <div className="mb-4">
              <Error message={error} onRetry={clearError} />
            </div>
          )}
          {/* T034: 空デッキメッセージ */}
          {isEmptyDeck && (
            <div className="mb-4 p-4 bg-gray-50 border border-gray-200 rounded-lg">
              <p className="text-gray-800 text-sm">
                このデッキにはカードがありません。カードを追加してからセッションを開始してください。
              </p>
            </div>
          )}
          {/* T031: レビュー履歴不足メッセージ（422エラー時） */}
          {isInsufficientReviewData && (
            <div className="mb-4 p-4 bg-orange-50 border border-orange-200 rounded-lg">
              <p className="text-orange-800 text-sm mb-2">
                このデッキにはまだレビュー履歴がないため、Weak Point Focus
                モードを利用できません。
              </p>
              <button
                type="button"
                onClick={() => {
                  clearError();
                  handleModeSelect("free_talk");
                }}
                className="text-sm text-orange-700 hover:text-orange-900 font-medium underline"
              >
                Free Talk モードで始める
              </button>
            </div>
          )}
          {/* T024: タイムアウト検出メッセージ */}
          {isTimedOut && (
            <div className="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
              <p className="text-yellow-800 text-sm">
                前回のセッションはタイムアウトしました。新しいセッションを開始してください。
              </p>
            </div>
          )}
          {!isLoading && (
            <ModeSelector onSelect={handleModeSelect} disabled={isLoading} />
          )}
        </div>
      </div>
    );
  }

  // Chat view
  return (
    <div className="flex flex-col h-screen">
      {/* T025: セッション終了ボタン付きヘッダー */}
      <header className="bg-white shadow-sm p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={handleModeSwitch}
            className="p-2 text-gray-500 hover:text-gray-700 min-w-[44px] min-h-[44px] flex items-center justify-center"
            aria-label="モード選択に戻る"
          >
            <svg
              className="w-5 h-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M15 19l-7-7 7-7"
              />
            </svg>
          </button>
          <div>
            <h1 className="text-lg font-semibold text-gray-800">
              AI チューター
            </h1>
            {session && (
              <p className="text-xs text-gray-500">
                {session.mode === "free_talk"
                  ? "Free Talk"
                  : session.mode === "quiz"
                    ? "Quiz"
                    : "Weak Point Focus"}
              </p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleViewHistory}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            履歴
          </button>
          <button
            onClick={() => setShowEndConfirm(true)}
            className="text-sm text-red-600 hover:text-red-800 px-3 py-1 border border-red-200 rounded-lg"
          >
            終了
          </button>
        </div>
      </header>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto p-4 bg-gray-50">
        {messages.map((msg, idx) => (
          <ChatMessage key={idx} message={msg} />
        ))}

        {/* Loading indicator for AI response */}
        {isLoading && (
          <div className="flex justify-start mb-3">
            <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-2">
              <div className="flex gap-1">
                <span
                  className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: "0ms" }}
                />
                <span
                  className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: "150ms" }}
                />
                <span
                  className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: "300ms" }}
                />
              </div>
            </div>
          </div>
        )}

        {/* T023: メッセージ上限到達 UI */}
        {isLimitReached && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg text-center">
            <p className="text-blue-800 text-sm mb-2">
              メッセージ上限（20ラウンドトリップ）に達しました。
            </p>
            <button
              onClick={handleModeSwitch}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium"
            >
              新しいセッションを開始する
            </button>
          </div>
        )}

        {/* T024: タイムアウト検出 UI */}
        {isTimedOut && (
          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg text-center">
            <p className="text-yellow-800 text-sm mb-2">
              セッションがタイムアウトしました（30分の非アクティブ）。
            </p>
            <button
              onClick={handleModeSwitch}
              className="text-sm text-yellow-700 hover:text-yellow-900 font-medium"
            >
              新しいセッションを開始する
            </button>
          </div>
        )}

        {/* Error in chat */}
        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg mb-3">
            <p className="text-red-700 text-sm">{error}</p>
            <div className="flex gap-3 mt-2">
              <button
                type="button"
                onClick={retryLastMessage}
                className="text-xs text-red-600 hover:text-red-800 font-medium"
              >
                再試行
              </button>
              <button
                type="button"
                onClick={clearError}
                className="text-xs text-red-500 hover:text-red-700"
              >
                閉じる
              </button>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area — disabled when limit reached or timed out */}
      <ChatInput
        onSend={handleSendMessage}
        disabled={isLoading || isLimitReached || isTimedOut}
      />

      {/* T025: セッション終了確認ダイアログ */}
      {showEndConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg p-6 max-w-sm w-full">
            <h3 className="text-lg font-semibold text-gray-800 mb-2">
              セッションを終了しますか？
            </h3>
            <p className="text-sm text-gray-600 mb-4">
              終了後は会話を続けることはできません。履歴から閲覧のみ可能です。
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowEndConfirm(false)}
                className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
              >
                キャンセル
              </button>
              <button
                onClick={handleEndSession}
                className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700"
              >
                終了する
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

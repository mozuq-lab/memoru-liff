import { useEffect, useState } from "react";
import { ChatMessage } from "./ChatMessage";
import * as tutorApi from "@/services/tutor-api";
import { formatDateTime } from "@/utils/date";
import type { TutorSession } from "@/types";

interface SessionListProps {
  deckId: string;
}

function modeLabel(mode: string): string {
  switch (mode) {
    case "free_talk":
      return "Free Talk";
    case "quiz":
      return "Quiz";
    case "weak_point":
      return "Weak Point Focus";
    default:
      return mode;
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case "ended":
      return "終了";
    case "timed_out":
      return "タイムアウト";
    case "active":
      return "アクティブ";
    default:
      return status;
  }
}

export const SessionList = ({ deckId }: SessionListProps) => {
  const [sessions, setSessions] = useState<TutorSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [expandedSession, setExpandedSession] = useState<TutorSession | null>(
    null,
  );
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    setLoading(true);
    tutorApi
      .listSessions(undefined, deckId)
      .then(({ sessions }) => {
        setSessions(sessions);
      })
      .catch(() => {
        setFetchError("セッション履歴の取得に失敗しました");
      })
      .finally(() => setLoading(false));
  }, [deckId]);

  const handleExpand = async (sessionId: string) => {
    if (expandedId === sessionId) {
      setExpandedId(null);
      setExpandedSession(null);
      return;
    }
    setExpandedId(sessionId);
    setLoadingDetail(true);
    try {
      const detail = await tutorApi.getSession(sessionId);
      setExpandedSession(detail);
    } catch {
      setExpandedSession(null);
    } finally {
      setLoadingDetail(false);
    }
  };

  if (loading) {
    return (
      <p className="text-center text-gray-500 text-sm py-8">読み込み中...</p>
    );
  }

  if (fetchError) {
    return (
      <p className="text-center text-red-500 text-sm py-8">
        {fetchError}
      </p>
    );
  }

  if (sessions.length === 0) {
    return (
      <p className="text-center text-gray-500 text-sm py-8">
        セッション履歴がありません
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {sessions.map((s) => (
        <div key={s.session_id} className="bg-white rounded-lg shadow">
          <button
            onClick={() => handleExpand(s.session_id)}
            aria-expanded={expandedId === s.session_id}
            aria-label={`${modeLabel(s.mode)} セッション詳細`}
            className="w-full text-left p-4 hover:bg-gray-50 transition-colors"
          >
            <div className="flex justify-between items-center">
              <div>
                <span className="text-sm font-medium text-gray-800">
                  {modeLabel(s.mode)}
                </span>
                <span className="ml-2 text-xs text-gray-500">
                  {statusLabel(s.status)}
                </span>
              </div>
              <span className="text-xs text-gray-400">
                {formatDateTime(s.created_at)}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-1">
              {s.message_count} メッセージ
            </p>
          </button>

          {/* Expanded view: conversation history */}
          {expandedId === s.session_id && (
            <div className="border-t p-4 bg-gray-50 max-h-[400px] overflow-y-auto">
              {loadingDetail ? (
                <p className="text-xs text-gray-500 text-center">
                  読み込み中...
                </p>
              ) : expandedSession ? (
                expandedSession.messages.map((msg, i) => (
                  <ChatMessage key={i} message={msg} />
                ))
              ) : (
                <p className="text-xs text-gray-500 text-center">
                  履歴の読み込みに失敗しました
                </p>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

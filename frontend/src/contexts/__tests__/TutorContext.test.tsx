import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TutorProvider, useTutorContext } from "../TutorContext";
import type {
  TutorSession,
  TutorMessage,
  SendMessageResponse,
} from "@/types";

// Mock tutor-api
const mockStartSession = vi.fn();
const mockSendMessage = vi.fn();
const mockEndSession = vi.fn();
const mockListSessions = vi.fn();
const mockGetSession = vi.fn();

vi.mock("@/services/tutor-api", () => ({
  startSession: (...args: unknown[]) => mockStartSession(...args),
  sendMessage: (...args: unknown[]) => mockSendMessage(...args),
  endSession: (...args: unknown[]) => mockEndSession(...args),
  listSessions: (...args: unknown[]) => mockListSessions(...args),
  getSession: (...args: unknown[]) => mockGetSession(...args),
}));

// Helper: build a mock session
const makeSession = (overrides?: Partial<TutorSession>): TutorSession => ({
  session_id: "tutor_test-session",
  deck_id: "deck_123",
  mode: "free_talk",
  status: "active",
  messages: [
    {
      role: "assistant",
      content: "こんにちは！",
      related_cards: [],
      timestamp: "2026-03-07T10:00:00Z",
    },
  ],
  message_count: 0,
  created_at: "2026-03-07T10:00:00Z",
  updated_at: "2026-03-07T10:00:00Z",
  ended_at: null,
  ...overrides,
});

const makeSendResponse = (
  overrides?: Partial<SendMessageResponse>,
): SendMessageResponse => ({
  message: {
    role: "assistant",
    content: "回答です",
    related_cards: [],
    timestamp: "2026-03-07T10:01:00Z",
  },
  session_id: "tutor_test-session",
  message_count: 1,
  is_limit_reached: false,
  ...overrides,
});

// Consumer component to expose context values
function TestConsumer() {
  const ctx = useTutorContext();
  return (
    <div>
      <span data-testid="session-id">{ctx.session?.session_id ?? "none"}</span>
      <span data-testid="is-loading">{String(ctx.isLoading)}</span>
      <span data-testid="error">{ctx.error ?? "none"}</span>
      <span data-testid="messages">{JSON.stringify(ctx.messages)}</span>
      <span data-testid="is-limit-reached">
        {String(ctx.isLimitReached)}
      </span>
      <button
        data-testid="start"
        onClick={() => ctx.startSession("deck_123", "free_talk")}
      />
      <button
        data-testid="send"
        onClick={() => ctx.sendMessage("テスト")}
      />
      <button data-testid="end" onClick={() => ctx.endSession()} />
    </div>
  );
}

function renderWithProvider() {
  return render(
    <TutorProvider>
      <TestConsumer />
    </TutorProvider>,
  );
}

describe("TutorContext", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("初期状態", () => {
    it("session は null、messages は空配列", () => {
      renderWithProvider();
      expect(screen.getByTestId("session-id").textContent).toBe("none");
      expect(screen.getByTestId("messages").textContent).toBe("[]");
      expect(screen.getByTestId("is-loading").textContent).toBe("false");
      expect(screen.getByTestId("error").textContent).toBe("none");
    });
  });

  describe("startSession", () => {
    it("セッションが開始されて状態が更新される", async () => {
      const session = makeSession();
      mockStartSession.mockResolvedValue(session);

      renderWithProvider();
      await act(async () => {
        screen.getByTestId("start").click();
      });

      await waitFor(() => {
        expect(screen.getByTestId("session-id").textContent).toBe(
          "tutor_test-session",
        );
      });
      expect(mockStartSession).toHaveBeenCalledWith({
        deck_id: "deck_123",
        mode: "free_talk",
      });
    });

    it("API エラー時にエラー状態が設定される", async () => {
      mockStartSession.mockRejectedValue(new Error("Network error"));

      renderWithProvider();
      await act(async () => {
        screen.getByTestId("start").click();
      });

      await waitFor(() => {
        expect(screen.getByTestId("error").textContent).not.toBe("none");
      });
    });
  });

  describe("sendMessage", () => {
    it("メッセージ送信後に応答が追加される", async () => {
      const session = makeSession();
      mockStartSession.mockResolvedValue(session);
      mockSendMessage.mockResolvedValue(makeSendResponse());

      renderWithProvider();
      // Start session first
      await act(async () => {
        screen.getByTestId("start").click();
      });
      await waitFor(() => {
        expect(screen.getByTestId("session-id").textContent).not.toBe("none");
      });

      // Send message
      await act(async () => {
        screen.getByTestId("send").click();
      });

      await waitFor(() => {
        const msgs = JSON.parse(
          screen.getByTestId("messages").textContent ?? "[]",
        );
        // Should contain initial assistant message + user message + assistant response
        expect(msgs.length).toBeGreaterThanOrEqual(3);
      });
    });

    it("is_limit_reached が true の場合にフラグが更新される", async () => {
      const session = makeSession();
      mockStartSession.mockResolvedValue(session);
      mockSendMessage.mockResolvedValue(
        makeSendResponse({ is_limit_reached: true }),
      );

      renderWithProvider();
      await act(async () => {
        screen.getByTestId("start").click();
      });
      await waitFor(() => {
        expect(screen.getByTestId("session-id").textContent).not.toBe("none");
      });

      await act(async () => {
        screen.getByTestId("send").click();
      });

      await waitFor(() => {
        expect(screen.getByTestId("is-limit-reached").textContent).toBe(
          "true",
        );
      });
    });

    it("セッションがない場合はメッセージ送信しない", async () => {
      renderWithProvider();
      await act(async () => {
        screen.getByTestId("send").click();
      });
      expect(mockSendMessage).not.toHaveBeenCalled();
    });
  });

  describe("endSession", () => {
    it("セッション終了後に状態がリセットされる", async () => {
      const session = makeSession();
      mockStartSession.mockResolvedValue(session);
      mockEndSession.mockResolvedValue({
        ...session,
        status: "ended",
        ended_at: "2026-03-07T10:30:00Z",
      });

      renderWithProvider();
      await act(async () => {
        screen.getByTestId("start").click();
      });
      await waitFor(() => {
        expect(screen.getByTestId("session-id").textContent).not.toBe("none");
      });

      await act(async () => {
        screen.getByTestId("end").click();
      });

      await waitFor(() => {
        expect(screen.getByTestId("session-id").textContent).toBe("none");
      });
    });
  });

  describe("useTutorContext outside provider", () => {
    it("Provider 外で使うとエラーが投げられる", () => {
      const spy = vi.spyOn(console, "error").mockImplementation(() => {});
      expect(() => render(<TestConsumer />)).toThrow();
      spy.mockRestore();
    });
  });
});

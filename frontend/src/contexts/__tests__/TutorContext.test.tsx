import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act, waitFor } from "@testing-library/react";
import { TutorProvider, useTutorContext } from "../TutorContext";
import { ApiError } from "@/services/api";
import type { TutorSession, SendMessageResponse } from "@/types";

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
      <span data-testid="is-limit-reached">{String(ctx.isLimitReached)}</span>
      <span data-testid="is-empty-deck">{String(ctx.isEmptyDeck)}</span>
      <span data-testid="is-insufficient">
        {String(ctx.isInsufficientReviewData)}
      </span>
      <button
        data-testid="start"
        onClick={() => ctx.startSession("deck_123", "free_talk")}
      />
      <button
        data-testid="start-weak"
        onClick={() => ctx.startSession("deck_123", "weak_point")}
      />
      <button data-testid="send" onClick={() => ctx.sendMessage("テスト")} />
      <button data-testid="end" onClick={() => ctx.endSession()} />
      <button
        data-testid="resume-other-deck"
        onClick={() => ctx.resumeSession("deck_456")}
      />
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

    it("E-1: 想定外エラー(非 ApiError)は生メッセージを露出せず固定文言になる", async () => {
      mockStartSession.mockRejectedValue(new Error("ECONNREFUSED 内部詳細"));

      renderWithProvider();
      await act(async () => {
        screen.getByTestId("start").click();
      });

      await waitFor(() => {
        // 生の "ECONNREFUSED 内部詳細" は露出せず、安全な固定文言に差し替わる
        expect(screen.getByTestId("error").textContent).toBe(
          "セッションの開始に失敗しました",
        );
      });
      expect(screen.getByTestId("error").textContent).not.toContain(
        "ECONNREFUSED",
      );
    });

    it("E-1: 5xx ApiError も生メッセージを露出せず固定文言になる", async () => {
      mockStartSession.mockRejectedValue(
        new ApiError("内部スタックトレース等の詳細", 503, "tutor_unavailable"),
      );

      renderWithProvider();
      await act(async () => {
        screen.getByTestId("start").click();
      });

      await waitFor(() => {
        expect(screen.getByTestId("error").textContent).toBe(
          "セッションの開始に失敗しました",
        );
      });
    });

    it("E-3: 422 + 空デッキメッセージで isEmptyDeck が立つ", async () => {
      mockStartSession.mockRejectedValue(
        new ApiError(
          "このデッキにはカードがありません。カードを追加してからセッションを開始してください。",
          422,
        ),
      );

      renderWithProvider();
      await act(async () => {
        screen.getByTestId("start").click();
      });

      await waitFor(() => {
        expect(screen.getByTestId("is-empty-deck").textContent).toBe("true");
      });
      expect(screen.getByTestId("is-insufficient").textContent).toBe("false");
    });

    it("E-3: 422 + レビュー履歴不足メッセージで isInsufficientReviewData が立つ", async () => {
      mockStartSession.mockRejectedValue(
        new ApiError(
          "レビュー履歴が不足しています。Free Talk モードをお試しください。",
          422,
        ),
      );

      renderWithProvider();
      await act(async () => {
        screen.getByTestId("start-weak").click();
      });

      await waitFor(() => {
        expect(screen.getByTestId("is-insufficient").textContent).toBe("true");
      });
      expect(screen.getByTestId("is-empty-deck").textContent).toBe("false");
    });

    it("E-3: 同じメッセージでも 500 では業務フラグが立たない(status ゲート)", async () => {
      // status が 422 でなければ、たとえメッセージに「カードがありません」を含んでも
      // 業務エラーフラグは立たず、固定文言になる
      mockStartSession.mockRejectedValue(
        new ApiError("このデッキにはカードがありません。", 500),
      );

      renderWithProvider();
      await act(async () => {
        screen.getByTestId("start").click();
      });

      await waitFor(() => {
        expect(screen.getByTestId("error").textContent).toBe(
          "セッションの開始に失敗しました",
        );
      });
      expect(screen.getByTestId("is-empty-deck").textContent).toBe("false");
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
        expect(screen.getByTestId("is-limit-reached").textContent).toBe("true");
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

  describe("resumeSession (High-3: デッキ不一致時の既存セッションクリア)", () => {
    it("別デッキにアクティブセッションが見つからない場合、残っていた session/messages をクリアする", async () => {
      // 【背景】: デッキ A (deck_123) のセッションが Context に残ったまま
      //   別デッキ (deck_456) を開いた際、resumeSession が該当デッキの
      //   アクティブセッションを見つけられなかった場合は古い state を
      //   クリアしないと、A の会話が表示され続け sendMessage が A の
      //   session_id へ送信されてしまう（High-3 の回帰テスト）。
      const session = makeSession(); // deck_id: "deck_123"
      mockStartSession.mockResolvedValue(session);
      mockListSessions.mockResolvedValue({ sessions: [], total: 0 });

      renderWithProvider();
      await act(async () => {
        screen.getByTestId("start").click();
      });
      await waitFor(() => {
        expect(screen.getByTestId("session-id").textContent).toBe(
          "tutor_test-session",
        );
      });

      // deck_456 に対する resumeSession は既存セッションを見つけられない
      await act(async () => {
        screen.getByTestId("resume-other-deck").click();
      });

      await waitFor(() => {
        expect(screen.getByTestId("session-id").textContent).toBe("none");
      });
      expect(
        JSON.parse(screen.getByTestId("messages").textContent ?? "[]"),
      ).toEqual([]);
      expect(mockListSessions).toHaveBeenCalledWith("active", "deck_456");
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

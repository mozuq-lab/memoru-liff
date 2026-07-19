import { describe, it, expect, vi, beforeEach, beforeAll } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { TutorPage } from "../TutorPage";
import type { LearningMode } from "@/types";

// jsdom は scrollIntoView 未実装のため、chat ビューのオートスクロール effect 用にスタブ化する
beforeAll(() => {
  Element.prototype.scrollIntoView = vi.fn();
});

// useTutorContext を制御可能なモックに差し替え
const mockStartSession = vi.fn();
const mockClearError = vi.fn();
const mockResumeSession = vi.fn().mockResolvedValue(false);

let mockTutorState: {
  session: unknown;
  messages: unknown[];
  isLoading: boolean;
  error: string | null;
  isLimitReached: boolean;
  isTimedOut: boolean;
  isInsufficientReviewData: boolean;
  isEmptyDeck: boolean;
};

vi.mock("@/contexts/TutorContext", () => ({
  useTutorContext: () => ({
    ...mockTutorState,
    startSession: mockStartSession,
    sendMessage: vi.fn(),
    endSession: vi.fn(),
    resumeSession: mockResumeSession,
    retryLastMessage: vi.fn(),
    clearError: mockClearError,
  }),
}));

const renderTutorPage = () =>
  render(
    <MemoryRouter initialEntries={["/tutor/deck-1"]}>
      <Routes>
        <Route path="/tutor/:deckId" element={<TutorPage />} />
      </Routes>
    </MemoryRouter>,
  );

describe("TutorPage (F-2: 再試行)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockResumeSession.mockResolvedValue(false);
    mockTutorState = {
      session: null,
      messages: [],
      isLoading: false,
      error: null,
      isLimitReached: false,
      isTimedOut: false,
      isInsufficientReviewData: false,
      isEmptyDeck: false,
    };
  });

  it("セッション開始失敗後の「再試行」で直前のモードで startSession を再実行する", async () => {
    const user = userEvent.setup();
    // 開始は失敗する想定（エラーは context 側でセットされるためモック state で表現）
    mockStartSession.mockResolvedValue(undefined);

    const { rerender } = renderTutorPage();

    // resumeSession の解決を待つ
    await waitFor(() => {
      expect(mockResumeSession).toHaveBeenCalled();
    });

    // モードを選択 → startSession(deckId, mode) が呼ばれる
    await user.click(screen.getByText("Quiz"));

    await waitFor(() => {
      expect(mockStartSession).toHaveBeenCalledWith("deck-1", "quiz" as LearningMode);
    });

    // エラー状態に遷移したと仮定して再レンダリング
    mockTutorState = { ...mockTutorState, error: "セッションの開始に失敗しました" };
    rerender(
      <MemoryRouter initialEntries={["/tutor/deck-1"]}>
        <Routes>
          <Route path="/tutor/:deckId" element={<TutorPage />} />
        </Routes>
      </MemoryRouter>,
    );

    // 「再試行」ボタンが表示される
    const retryButton = await screen.findByRole("button", { name: "再試行" });

    mockStartSession.mockClear();
    await user.click(retryButton);

    // F-2: clearError ではなく、直前のモードで startSession が再実行される
    await waitFor(() => {
      expect(mockStartSession).toHaveBeenCalledWith("deck-1", "quiz" as LearningMode);
    });
    expect(mockClearError).not.toHaveBeenCalled();
  });

  it("モード未選択でエラーが出た場合は「再試行」で clearError を呼ぶ", async () => {
    const user = userEvent.setup();

    // 初期描画時点でエラーあり・モード未選択（例: resume 経路の失敗想定）
    mockTutorState = { ...mockTutorState, error: "エラーが発生しました" };

    renderTutorPage();

    const retryButton = await screen.findByRole("button", { name: "再試行" });
    await user.click(retryButton);

    await waitFor(() => {
      expect(mockClearError).toHaveBeenCalled();
    });
    expect(mockStartSession).not.toHaveBeenCalled();
  });
});

describe("TutorPage (High-3: デッキ切替時に別デッキの会話を表示しない)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockTutorState = {
      session: null,
      messages: [],
      isLoading: false,
      error: null,
      isLimitReached: false,
      isTimedOut: false,
      isInsufficientReviewData: false,
      isEmptyDeck: false,
    };
  });

  it("Context に残る session.deck_id がルートの deckId と一致しない場合、chat ではなく mode-select を表示する", async () => {
    // 【背景】: TutorProvider は最上位にあるため、デッキ1のセッションが
    //   残った状態でデッキ2の /tutor/deck-2 を開くと、一致確認なしでは
    //   デッキ1の会話が表示され、送信メッセージがデッキ1の session_id へ
    //   送られてしまう問題（High-3）の回帰テスト。
    mockResumeSession.mockResolvedValue(false); // deck-2 にアクティブセッションはない
    mockTutorState = {
      ...mockTutorState,
      session: {
        session_id: "tutor_deck1_session",
        deck_id: "deck-1",
        mode: "free_talk",
        status: "active",
        messages: [],
        message_count: 1,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        ended_at: null,
      },
      messages: [
        {
          role: "assistant",
          content: "デッキ1の会話内容",
          related_cards: [],
          timestamp: "2026-01-01T00:00:00Z",
        },
      ],
    };

    render(
      <MemoryRouter initialEntries={["/tutor/deck-2"]}>
        <Routes>
          <Route path="/tutor/:deckId" element={<TutorPage />} />
        </Routes>
      </MemoryRouter>,
    );

    // mode-select 画面が表示される（ModeSelector の見出し）
    expect(await screen.findByText("学習モードを選択")).toBeInTheDocument();
    // デッキ1の会話やチャット専用の「終了」ボタンは表示されない
    expect(screen.queryByText("デッキ1の会話内容")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "終了" }),
    ).not.toBeInTheDocument();
  });

  it("session.deck_id がルートの deckId と一致する場合は chat を表示する", async () => {
    mockResumeSession.mockResolvedValue(false);
    mockTutorState = {
      ...mockTutorState,
      session: {
        session_id: "tutor_deck1_session",
        deck_id: "deck-1",
        mode: "free_talk",
        status: "active",
        messages: [],
        message_count: 1,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        ended_at: null,
      },
      messages: [
        {
          role: "assistant",
          content: "デッキ1の会話内容",
          related_cards: [],
          timestamp: "2026-01-01T00:00:00Z",
        },
      ],
    };

    render(
      <MemoryRouter initialEntries={["/tutor/deck-1"]}>
        <Routes>
          <Route path="/tutor/:deckId" element={<TutorPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("button", { name: "終了" }),
    ).toBeInTheDocument();
    expect(screen.getByText("デッキ1の会話内容")).toBeInTheDocument();
  });
});

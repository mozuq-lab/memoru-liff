import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { TutorPage } from "../TutorPage";
import type { LearningMode } from "@/types";

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

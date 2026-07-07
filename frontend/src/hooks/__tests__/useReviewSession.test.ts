/**
 * 【テスト概要】: useReviewSession フックのテスト
 * 【テスト対象】: deckId 変更時の競合ガード（requestId）と前回リクエストの中断
 * 【背景】: /review?deck_id=A → ?deck_id=B の遷移で新旧レスポンスの順序保証がなく、
 *           古いデッキのカードが表示され得る問題（MEDIUM）の回帰テスト
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { useReviewSession } from "../useReviewSession";
import type { DueCard, DueCardsResponse } from "@/types";

// cardsApi / reviewsApi をモック
vi.mock("@/services/api", () => ({
  cardsApi: {
    getDueCards: vi.fn(),
  },
  reviewsApi: {
    submitReview: vi.fn(),
    undoReview: vi.fn(),
  },
}));

import { cardsApi, reviewsApi } from "@/services/api";

const mockGetDueCards = cardsApi.getDueCards as ReturnType<typeof vi.fn>;
const mockSubmitReview = reviewsApi.submitReview as ReturnType<typeof vi.fn>;

const makeCard = (id: string, front: string): DueCard => ({
  card_id: id,
  front,
  back: `${front} の答え`,
  deck_id: null,
  due_date: "2026-07-07",
  overdue_days: 0,
});

const makeResponse = (cards: DueCard[]): DueCardsResponse => ({
  due_cards: cards,
  total_due_count: cards.length,
  next_due_date: null,
});

type Deferred = {
  resolve: (value: DueCardsResponse) => void;
  reject: (reason?: unknown) => void;
};

describe("useReviewSession", () => {
  const cancel = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("復習カードを取得して cards にセットする", async () => {
    mockGetDueCards.mockResolvedValue(
      makeResponse([makeCard("card-1", "デッキAのカード")]),
    );

    const { result } = renderHook(() => useReviewSession("deck-a", cancel));

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.cards.map((c) => c.card_id)).toEqual(["card-1"]);
    expect(mockGetDueCards).toHaveBeenCalledWith(
      undefined,
      "deck-a",
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("deckId 変更時、古いデッキのレスポンスが後着しても新しいデッキのカードを上書きしない", async () => {
    // 【テスト内容】: deck-a のレスポンスを遅延させたまま deck-b に切り替え、
    //                deck-b 解決 → deck-a 解決の順で後着させる
    const deferreds: Deferred[] = [];
    mockGetDueCards.mockImplementation(
      () =>
        new Promise<DueCardsResponse>((resolve, reject) => {
          deferreds.push({ resolve, reject });
        }),
    );

    const { result, rerender } = renderHook(
      ({ deckId }: { deckId: string }) => useReviewSession(deckId, cancel),
      { initialProps: { deckId: "deck-a" } },
    );

    // deck-a のリクエストがフライト中のまま deck-b へ切り替え
    rerender({ deckId: "deck-b" });
    await waitFor(() => {
      expect(deferreds).toHaveLength(2);
    });

    // deck-b（後発・最新）のレスポンスが先に到着
    await act(async () => {
      deferreds[1].resolve(makeResponse([makeCard("card-b", "デッキB")]));
    });
    expect(result.current.cards.map((c) => c.card_id)).toEqual(["card-b"]);
    expect(result.current.isLoading).toBe(false);

    // deck-a（先発・古い）のレスポンスが後着 → 破棄されること
    await act(async () => {
      deferreds[0].resolve(makeResponse([makeCard("card-a", "デッキA")]));
    });
    expect(result.current.cards.map((c) => c.card_id)).toEqual(["card-b"]);
    expect(result.current.error).toBeNull();
  });

  it("deckId 変更時に前回リクエストの signal が abort される", async () => {
    const signals: AbortSignal[] = [];
    mockGetDueCards.mockImplementation(
      (
        _limit: number | undefined,
        _deckId: string | undefined,
        options?: { signal?: AbortSignal },
      ) => {
        if (options?.signal) signals.push(options.signal);
        return new Promise<DueCardsResponse>(() => {});
      },
    );

    const { rerender } = renderHook(
      ({ deckId }: { deckId: string }) => useReviewSession(deckId, cancel),
      { initialProps: { deckId: "deck-a" } },
    );

    rerender({ deckId: "deck-b" });

    await waitFor(() => {
      expect(signals).toHaveLength(2);
    });
    // 前回（deck-a）のリクエストは中断され、最新（deck-b）は中断されていない
    expect(signals[0].aborted).toBe(true);
    expect(signals[1].aborted).toBe(false);
  });

  it("古いリクエストの中断（abort reject）でエラー state を汚染しない", async () => {
    // 【テスト内容】: 前回リクエストが AbortError で reject しても、
    //                requestId ガードにより error は設定されない
    const deferreds: Deferred[] = [];
    mockGetDueCards.mockImplementation(
      () =>
        new Promise<DueCardsResponse>((resolve, reject) => {
          deferreds.push({ resolve, reject });
        }),
    );

    const { result, rerender } = renderHook(
      ({ deckId }: { deckId: string }) => useReviewSession(deckId, cancel),
      { initialProps: { deckId: "deck-a" } },
    );

    rerender({ deckId: "deck-b" });
    await waitFor(() => {
      expect(deferreds).toHaveLength(2);
    });

    // 旧リクエストが中断エラーで reject
    await act(async () => {
      deferreds[0].reject(new DOMException("Aborted", "AbortError"));
    });
    expect(result.current.error).toBeNull();

    // 最新リクエストは正常に反映される
    await act(async () => {
      deferreds[1].resolve(makeResponse([makeCard("card-b", "デッキB")]));
    });
    expect(result.current.cards.map((c) => c.card_id)).toEqual(["card-b"]);
    expect(result.current.error).toBeNull();
  });

  it("最新リクエストの失敗ではエラーが表示される", async () => {
    mockGetDueCards.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useReviewSession("deck-a", cancel));

    await waitFor(() => {
      expect(result.current.error).toBe("復習カードの取得に失敗しました");
    });
    expect(result.current.isLoading).toBe(false);
  });

  it("完了済みデッキから別デッキへ切り替えるとセッション進行状態が初期化される", async () => {
    // 【テスト内容】: デッキ A を完了（isComplete === true）した後に deck_id だけが
    //                変わる遷移をすると、cards は B に差し替わるがセッション進行状態が
    //                残り、完了画面から戻れなくなる問題（PR #77 レビュー指摘）の回帰テスト
    mockGetDueCards.mockResolvedValueOnce(
      makeResponse([makeCard("card-a", "デッキA")]),
    );
    mockSubmitReview.mockResolvedValue({
      updated: { due_date: "2026-07-08" },
    });

    const { result, rerender } = renderHook(
      ({ deckId }: { deckId: string }) => useReviewSession(deckId, cancel),
      { initialProps: { deckId: "deck-a" } },
    );
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // デッキ A（1枚）を grade 5 で採点してセッション完了
    await act(async () => {
      await result.current.handleGrade(5);
    });
    expect(result.current.isComplete).toBe(true);
    expect(result.current.reviewedCount).toBe(1);
    expect(result.current.reviewResults).toHaveLength(1);

    // デッキ B へ切り替え
    mockGetDueCards.mockResolvedValueOnce(
      makeResponse([makeCard("card-b", "デッキB")]),
    );
    rerender({ deckId: "deck-b" });

    await waitFor(() => {
      expect(result.current.cards.map((c) => c.card_id)).toEqual(["card-b"]);
    });
    // セッション進行状態が初期化され、B の復習を最初から開始できる
    expect(result.current.isComplete).toBe(false);
    expect(result.current.currentIndex).toBe(0);
    expect(result.current.reviewedCount).toBe(0);
    expect(result.current.reviewResults).toEqual([]);
    expect(result.current.reconfirmQueue).toEqual([]);
    expect(result.current.isReconfirmMode).toBe(false);
    expect(result.current.regradeCardIndex).toBeNull();
  });

  it("再確認キューが残った状態でのデッキ切り替えでもキューが初期化される", async () => {
    // grade 0-2 で reconfirmQueue に入った状態からデッキを切り替えるケース
    mockGetDueCards.mockResolvedValueOnce(
      makeResponse([makeCard("card-a", "デッキA")]),
    );
    mockSubmitReview.mockResolvedValue({
      updated: { due_date: "2026-07-08" },
    });

    const { result, rerender } = renderHook(
      ({ deckId }: { deckId: string }) => useReviewSession(deckId, cancel),
      { initialProps: { deckId: "deck-a" } },
    );
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // grade 1（< 3）で採点 → 再確認モードへ
    await act(async () => {
      await result.current.handleGrade(1);
    });
    expect(result.current.isReconfirmMode).toBe(true);
    expect(result.current.reconfirmQueue).toHaveLength(1);

    mockGetDueCards.mockResolvedValueOnce(
      makeResponse([makeCard("card-b", "デッキB")]),
    );
    rerender({ deckId: "deck-b" });

    await waitFor(() => {
      expect(result.current.cards.map((c) => c.card_id)).toEqual(["card-b"]);
    });
    expect(result.current.isReconfirmMode).toBe(false);
    expect(result.current.reconfirmQueue).toEqual([]);
  });

  it("アンマウント時にフライト中のリクエストが中断される", async () => {
    const signals: AbortSignal[] = [];
    mockGetDueCards.mockImplementation(
      (
        _limit: number | undefined,
        _deckId: string | undefined,
        options?: { signal?: AbortSignal },
      ) => {
        if (options?.signal) signals.push(options.signal);
        return new Promise<DueCardsResponse>(() => {});
      },
    );

    const { unmount } = renderHook(() => useReviewSession("deck-a", cancel));

    await waitFor(() => {
      expect(signals).toHaveLength(1);
    });
    expect(signals[0].aborted).toBe(false);

    unmount();

    expect(signals[0].aborted).toBe(true);
  });
});

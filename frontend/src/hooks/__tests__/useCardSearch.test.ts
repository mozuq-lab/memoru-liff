/**
 * 【テスト概要】: useCardSearch フックのテスト
 * 【テスト対象】: useCardSearch フック
 * 【テスト対応】: クエリフィルター, reviewStatusフィルター, ソート
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCardSearch } from "../useCardSearch";
import type { Card } from "@/types";

// L-1 fix: テスト日付を固定して実行日に依存しないようにする
const FIXED_DATE = new Date("2026-02-28T12:00:00Z");

// テスト用フィクスチャ（2026-02-28 基準）
const TODAY = "2026-02-28";
const PAST = "2026-02-01";
const FUTURE = "2026-03-30";

const mockCards: Card[] = [
  {
    card_id: "1",
    user_id: "u1",
    front: "Apple リンゴ",
    back: "赤い果物",
    tags: [],
    ease_factor: 2.5,
    interval: 1,
    repetitions: 0, // new
    next_review_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: null,
  },
  {
    card_id: "2",
    user_id: "u1",
    front: "ｂａｎａｎａ バナナ",
    back: "黄色い果物",
    tags: [],
    ease_factor: 1.8,
    interval: 3,
    repetitions: 2, // learning or due
    next_review_at: PAST, // due (期日超過)
    created_at: "2026-01-05T00:00:00Z",
    updated_at: null,
  },
  {
    card_id: "3",
    user_id: "u1",
    front: "Cherry さくらんぼ",
    back: "赤い小さな果物",
    tags: [],
    ease_factor: 3.0,
    interval: 10,
    repetitions: 5, // learning
    next_review_at: FUTURE, // learning (未来)
    created_at: "2026-01-10T00:00:00Z",
    updated_at: null,
  },
];

// テスト用の今日日付をモック
vi.mock("@/utils/date", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/utils/date")>();
  return {
    ...actual,
  };
});

describe("useCardSearch", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(FIXED_DATE);
  });

  afterEach(() => {
    vi.useRealTimers();
  });
  describe("初期状態", () => {
    it("初期値が正しく設定される", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      expect(result.current.query).toBe("");
      expect(result.current.reviewStatus).toBe("all");
      expect(result.current.sortBy).toBe("created_at");
      expect(result.current.sortOrder).toBe("desc");
    });

    it("初期状態では全カードが返される", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      expect(result.current.filteredCards).toHaveLength(3);
    });
  });

  describe("クエリフィルター", () => {
    it("空クエリのとき全件返す", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => result.current.setQuery(""));
      expect(result.current.filteredCards).toHaveLength(3);
    });

    it("front への部分一致でフィルタリングされる", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => result.current.setQuery("Apple"));
      expect(result.current.filteredCards).toHaveLength(1);
      expect(result.current.filteredCards[0].card_id).toBe("1");
    });

    it("back への部分一致でフィルタリングされる", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => result.current.setQuery("果物"));
      expect(result.current.filteredCards).toHaveLength(3);
    });

    it("大文字・小文字を区別しない", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => result.current.setQuery("apple"));
      expect(result.current.filteredCards).toHaveLength(1);
      expect(result.current.filteredCards[0].card_id).toBe("1");
    });

    it("全角・半角を区別しない（全角クエリで半角テキストをマッチ）", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      // "banana" の全角は "ｂａｎａｎａ". mockCards[1].front に含まれる
      act(() => result.current.setQuery("banana"));
      expect(result.current.filteredCards).toHaveLength(1);
      expect(result.current.filteredCards[0].card_id).toBe("2");
    });

    it("マッチしないクエリのとき空配列を返す", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => result.current.setQuery("存在しないキーワードXYZ"));
      expect(result.current.filteredCards).toHaveLength(0);
    });
  });

  describe("reviewStatus フィルター", () => {
    it("reviewStatus='all' のとき全件返す", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => result.current.setReviewStatus("all"));
      expect(result.current.filteredCards).toHaveLength(3);
    });

    it("reviewStatus='new' のとき repetitions===0 のカードのみ返す", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => result.current.setReviewStatus("new"));
      expect(result.current.filteredCards).toHaveLength(1);
      expect(result.current.filteredCards[0].card_id).toBe("1");
    });

    it("reviewStatus='due' のとき next_review_at <= 今日 && repetitions>0 のカードのみ返す", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => result.current.setReviewStatus("due"));
      expect(result.current.filteredCards).toHaveLength(1);
      expect(result.current.filteredCards[0].card_id).toBe("2");
    });

    it("reviewStatus='learning' のとき next_review_at > 今日 && repetitions>0 のカードのみ返す", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => result.current.setReviewStatus("learning"));
      expect(result.current.filteredCards).toHaveLength(1);
      expect(result.current.filteredCards[0].card_id).toBe("3");
    });

    it("クエリと reviewStatus の AND フィルタが機能する", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => {
        result.current.setQuery("果物");
        result.current.setReviewStatus("new");
      });
      // "果物" を含む: 全3枚, new は card_id=1 のみ
      expect(result.current.filteredCards).toHaveLength(1);
      expect(result.current.filteredCards[0].card_id).toBe("1");
    });
  });

  describe("ソート", () => {
    it("sortBy='created_at', sortOrder='desc' で作成日降順になる", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => {
        result.current.setSortBy("created_at");
        result.current.setSortOrder("desc");
      });
      const ids = result.current.filteredCards.map((c) => c.card_id);
      expect(ids).toEqual(["3", "2", "1"]);
    });

    it("sortBy='created_at', sortOrder='asc' で作成日昇順になる", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => {
        result.current.setSortBy("created_at");
        result.current.setSortOrder("asc");
      });
      const ids = result.current.filteredCards.map((c) => c.card_id);
      expect(ids).toEqual(["1", "2", "3"]);
    });

    it("sortBy='ease_factor', sortOrder='asc' で習熟度昇順になる", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => {
        result.current.setSortBy("ease_factor");
        result.current.setSortOrder("asc");
      });
      const factors = result.current.filteredCards.map((c) => c.ease_factor);
      expect(factors).toEqual([1.8, 2.5, 3.0]);
    });

    it("sortBy='next_review_at', sortOrder='asc' で next_review_at null は末尾", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => {
        result.current.setSortBy("next_review_at");
        result.current.setSortOrder("asc");
      });
      const ids = result.current.filteredCards.map((c) => c.card_id);
      // PAST < FUTURE < null(末尾)
      expect(ids).toEqual(["2", "3", "1"]);
    });

    // H-2 テスト: 降順でも null は末尾に来ること
    it("sortBy='next_review_at', sortOrder='desc' で next_review_at null は末尾", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => {
        result.current.setSortBy("next_review_at");
        result.current.setSortOrder("desc");
      });
      const ids = result.current.filteredCards.map((c) => c.card_id);
      // FUTURE > PAST > null(末尾)
      expect(ids).toEqual(["3", "2", "1"]);
    });
  });

  describe("H-1: 時刻付き ISO 文字列の due 判定", () => {
    it("next_review_at が今日の時刻付き ISO 文字列でも due に分類される", () => {
      const cardsWithIsoTime: Card[] = [
        {
          card_id: "iso-1",
          user_id: "u1",
          front: "ISO test",
          back: "test",
          tags: [],
          ease_factor: 2.5,
          interval: 1,
          repetitions: 3,
          next_review_at: "2026-02-28T00:00:00", // 今日の時刻付き
          created_at: "2026-01-01T00:00:00Z",
          updated_at: null,
        },
        {
          card_id: "iso-2",
          user_id: "u1",
          front: "ISO test 2",
          back: "test 2",
          tags: [],
          ease_factor: 2.5,
          interval: 1,
          repetitions: 3,
          next_review_at: "2026-02-28T23:59:59", // 今日の時刻付き（深夜）
          created_at: "2026-01-02T00:00:00Z",
          updated_at: null,
        },
      ];

      const { result } = renderHook(() =>
        useCardSearch({ cards: cardsWithIsoTime }),
      );
      act(() => result.current.setReviewStatus("due"));
      // 両方とも due に分類されるべき
      expect(result.current.filteredCards).toHaveLength(2);
    });
  });

  describe("reset", () => {
    it("reset() で初期状態に戻る", () => {
      const { result } = renderHook(() => useCardSearch({ cards: mockCards }));
      act(() => {
        result.current.setQuery("apple");
        result.current.setReviewStatus("new");
        result.current.setSortBy("ease_factor");
        result.current.setSortOrder("asc");
      });
      act(() => result.current.reset());
      expect(result.current.query).toBe("");
      expect(result.current.reviewStatus).toBe("all");
      expect(result.current.sortBy).toBe("created_at");
      expect(result.current.sortOrder).toBe("desc");
    });
  });
});

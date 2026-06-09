import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { RelatedCardChip } from "../RelatedCardChip";
import { __clearRelatedCardCache } from "../relatedCardCache";
import { cardsApi } from "@/services/api";
import type { Card } from "@/types";

// cardsApi.getCard をモック
vi.mock("@/services/api", () => ({
  cardsApi: {
    getCard: vi.fn(),
  },
}));

const buildCard = (id: string, front: string): Card => ({
  card_id: id,
  user_id: "user1",
  front,
  back: "回答",
  tags: [],
  interval: 1,
  ease_factor: 2.5,
  repetitions: 0,
  created_at: "2024-01-01T00:00:00Z",
  updated_at: "2024-01-01T00:00:00Z",
});

const renderChip = (cardId: string) =>
  render(
    <MemoryRouter>
      <RelatedCardChip cardId={cardId} />
    </MemoryRouter>,
  );

describe("RelatedCardChip (F-5: キャッシュ)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    __clearRelatedCardCache();
  });

  it("カードの表面テキストを取得して表示する", async () => {
    vi.mocked(cardsApi.getCard).mockResolvedValue(buildCard("c1", "表面テキスト"));

    renderChip("c1");

    await waitFor(() => {
      expect(screen.getByText("表面テキスト")).toBeInTheDocument();
    });
  });

  it("同一 cardId のチップを複数描画しても getCard は1回しか呼ばれない（重複リクエスト防止）", async () => {
    vi.mocked(cardsApi.getCard).mockResolvedValue(buildCard("c1", "共有テキスト"));

    render(
      <MemoryRouter>
        <RelatedCardChip cardId="c1" />
        <RelatedCardChip cardId="c1" />
        <RelatedCardChip cardId="c1" />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getAllByText("共有テキスト")).toHaveLength(3);
    });
    // in-flight Promise 共有により API 呼び出しは1回のみ
    expect(cardsApi.getCard).toHaveBeenCalledTimes(1);
  });

  it("再マウント時にキャッシュを再利用し再フェッチしない", async () => {
    vi.mocked(cardsApi.getCard).mockResolvedValue(buildCard("c2", "キャッシュ対象"));

    const { unmount } = renderChip("c2");
    await waitFor(() => {
      expect(screen.getByText("キャッシュ対象")).toBeInTheDocument();
    });
    expect(cardsApi.getCard).toHaveBeenCalledTimes(1);

    unmount();

    // 再マウント — キャッシュヒットで追加フェッチは発生しない
    renderChip("c2");
    await waitFor(() => {
      expect(screen.getByText("キャッシュ対象")).toBeInTheDocument();
    });
    expect(cardsApi.getCard).toHaveBeenCalledTimes(1);
  });

  it("取得失敗時は cardId をフォールバック表示し、失敗結果もキャッシュする", async () => {
    vi.mocked(cardsApi.getCard).mockRejectedValue(new Error("not found"));

    renderChip("deleted-card");
    await waitFor(() => {
      expect(screen.getByText("deleted-card")).toBeInTheDocument();
    });
    expect(cardsApi.getCard).toHaveBeenCalledTimes(1);

    // 再描画しても失敗結果はキャッシュされ再フェッチしない
    renderChip("deleted-card");
    await waitFor(() => {
      expect(screen.getAllByText("deleted-card").length).toBeGreaterThan(0);
    });
    expect(cardsApi.getCard).toHaveBeenCalledTimes(1);
  });
});

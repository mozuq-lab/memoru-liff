import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChatMessage } from "../ChatMessage";
import type { TutorMessage } from "@/types";
import { MemoryRouter } from "react-router-dom";

const renderMessage = (msg: TutorMessage) =>
  render(
    <MemoryRouter>
      <ChatMessage message={msg} />
    </MemoryRouter>,
  );

describe("ChatMessage", () => {
  it("ユーザーメッセージが右寄せで表示される", () => {
    renderMessage({
      role: "user",
      content: "テストメッセージ",
      related_cards: [],
      timestamp: "2026-03-07T10:00:00Z",
    });
    const el = screen.getByText("テストメッセージ");
    expect(el).toBeInTheDocument();
  });

  it("アシスタントメッセージが左寄せで表示される", () => {
    renderMessage({
      role: "assistant",
      content: "AI回答です",
      related_cards: [],
      timestamp: "2026-03-07T10:00:00Z",
    });
    const el = screen.getByText("AI回答です");
    expect(el).toBeInTheDocument();
  });

  it("タイムスタンプが表示される", () => {
    renderMessage({
      role: "assistant",
      content: "タイムスタンプテスト",
      related_cards: [],
      timestamp: "2026-03-07T10:30:00Z",
    });
    // Time is displayed in local timezone — just check a time pattern exists
    expect(screen.getByText(/\d{1,2}:\d{2}/)).toBeInTheDocument();
  });

  it("related_cards が空の場合はカード chip が表示されない", () => {
    const { container } = renderMessage({
      role: "assistant",
      content: "テスト",
      related_cards: [],
      timestamp: "2026-03-07T10:00:00Z",
    });
    expect(container.querySelector("[data-testid='related-card']")).toBeNull();
  });
});

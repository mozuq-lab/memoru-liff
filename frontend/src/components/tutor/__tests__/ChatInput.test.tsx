import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatInput } from "../ChatInput";

describe("ChatInput", () => {
  const onSend = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("テキスト入力フィールドと送信ボタンが表示される", () => {
    render(<ChatInput onSend={onSend} />);
    expect(screen.getByPlaceholderText(/メッセージ/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /送信/ })).toBeInTheDocument();
  });

  it("テキスト入力後に送信ボタンをクリックすると onSend が呼ばれる", async () => {
    const user = userEvent.setup();
    render(<ChatInput onSend={onSend} />);
    const input = screen.getByPlaceholderText(/メッセージ/);
    await user.type(input, "テスト入力");
    await user.click(screen.getByRole("button", { name: /送信/ }));
    expect(onSend).toHaveBeenCalledWith("テスト入力");
  });

  it("送信後に入力フィールドがクリアされる", async () => {
    const user = userEvent.setup();
    render(<ChatInput onSend={onSend} />);
    const input = screen.getByPlaceholderText(/メッセージ/) as HTMLInputElement;
    await user.type(input, "テスト");
    await user.click(screen.getByRole("button", { name: /送信/ }));
    expect(input.value).toBe("");
  });

  it("空メッセージでは送信ボタンが無効", async () => {
    render(<ChatInput onSend={onSend} />);
    const btn = screen.getByRole("button", { name: /送信/ });
    expect(btn).toBeDisabled();
  });

  it("disabled prop が true の場合は入力と送信が無効", () => {
    render(<ChatInput onSend={onSend} disabled />);
    const input = screen.getByPlaceholderText(/メッセージ/);
    const btn = screen.getByRole("button", { name: /送信/ });
    expect(input).toBeDisabled();
    expect(btn).toBeDisabled();
  });

  it("2000文字を超える入力は制限される", async () => {
    const user = userEvent.setup();
    render(<ChatInput onSend={onSend} />);
    const input = screen.getByPlaceholderText(/メッセージ/) as HTMLInputElement;
    expect(input).toHaveAttribute("maxLength", "2000");
  });
});

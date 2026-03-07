import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ModeSelector } from "../ModeSelector";
import type { LearningMode } from "@/types";

describe("ModeSelector", () => {
  const onSelect = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("3つのモード選択肢が表示される", () => {
    render(<ModeSelector onSelect={onSelect} />);
    expect(screen.getByText("Free Talk")).toBeInTheDocument();
    expect(screen.getByText("Quiz")).toBeInTheDocument();
    expect(screen.getByText("Weak Point Focus")).toBeInTheDocument();
  });

  it("Free Talk を選択すると onSelect('free_talk') が呼ばれる", async () => {
    const user = userEvent.setup();
    render(<ModeSelector onSelect={onSelect} />);
    await user.click(screen.getByText("Free Talk"));
    expect(onSelect).toHaveBeenCalledWith("free_talk");
  });

  it("Quiz を選択すると onSelect('quiz') が呼ばれる", async () => {
    const user = userEvent.setup();
    render(<ModeSelector onSelect={onSelect} />);
    await user.click(screen.getByText("Quiz"));
    expect(onSelect).toHaveBeenCalledWith("quiz");
  });

  it("Weak Point Focus を選択すると onSelect('weak_point') が呼ばれる", async () => {
    const user = userEvent.setup();
    render(<ModeSelector onSelect={onSelect} />);
    await user.click(screen.getByText("Weak Point Focus"));
    expect(onSelect).toHaveBeenCalledWith("weak_point");
  });

  it("各モードに説明テキストが表示される", () => {
    render(<ModeSelector onSelect={onSelect} />);
    expect(
      screen.getByText(/デッキの内容について自由に質問/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/AIがカード内容からクイズを出題/),
    ).toBeInTheDocument();
    expect(screen.getByText(/苦手なカードを重点的に学習/)).toBeInTheDocument();
  });

  it("disabled 時はクリックが無効になる", async () => {
    const user = userEvent.setup();
    render(<ModeSelector onSelect={onSelect} disabled />);
    await user.click(screen.getByText("Free Talk"));
    expect(onSelect).not.toHaveBeenCalled();
  });
});

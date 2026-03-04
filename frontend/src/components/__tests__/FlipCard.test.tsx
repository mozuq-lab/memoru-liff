import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FlipCard } from "../FlipCard";
import type { FlipCardSpeechProps } from "../FlipCard";

const defaultProps = {
  front: "質問テキスト",
  back: "解答テキスト",
  isFlipped: false,
  onFlip: vi.fn(),
};

const renderFlipCard = (props = {}) => {
  return render(<FlipCard {...defaultProps} {...props} />);
};

describe("FlipCard", () => {
  describe("表面表示", () => {
    it("isFlipped=false の場合、表面テキストが表示される", () => {
      renderFlipCard({ isFlipped: false });
      expect(screen.getByText("質問テキスト")).toBeInTheDocument();
    });

    it("isFlipped=false の場合、裏面テキストも DOM に存在する（非表示）", () => {
      renderFlipCard({ isFlipped: false });
      expect(screen.getByText("解答テキスト")).toBeInTheDocument();
    });
  });

  describe("裏面表示", () => {
    it("isFlipped=true の場合、裏面テキストが表示される", () => {
      renderFlipCard({ isFlipped: true });
      expect(screen.getByText("解答テキスト")).toBeInTheDocument();
    });
  });

  describe("フリップ操作", () => {
    it("カードをクリックすると onFlip が呼ばれる", async () => {
      const onFlip = vi.fn();
      renderFlipCard({ onFlip });

      const user = userEvent.setup();
      await user.click(screen.getByRole("button"));

      expect(onFlip).toHaveBeenCalledTimes(1);
    });

    it("Enter キーで onFlip が呼ばれる", async () => {
      const onFlip = vi.fn();
      renderFlipCard({ onFlip });

      const user = userEvent.setup();
      screen.getByRole("button").focus();
      await user.keyboard("{Enter}");

      expect(onFlip).toHaveBeenCalled();
    });

    it("Space キーで onFlip が呼ばれる", async () => {
      const onFlip = vi.fn();
      renderFlipCard({ onFlip });

      const user = userEvent.setup();
      screen.getByRole("button").focus();
      await user.keyboard(" ");

      expect(onFlip).toHaveBeenCalled();
    });

    it("他のキーでは onFlip が呼ばれない", async () => {
      const onFlip = vi.fn();
      renderFlipCard({ onFlip });

      const user = userEvent.setup();
      screen.getByRole("button").focus();
      await user.keyboard("a");

      // click from focus + keyboard interaction, but not from 'a' key handler
      // onFlip should not be called from onKeyDown for 'a'
      expect(onFlip).not.toHaveBeenCalled();
    });
  });

  describe("CSS クラス", () => {
    it("isFlipped=false の場合、flipped クラスが適用されない", () => {
      const { container } = renderFlipCard({ isFlipped: false });
      const inner = container.querySelector(".flip-card-inner");
      expect(inner).not.toHaveClass("flipped");
    });

    it("isFlipped=true の場合、flipped クラスが適用される", () => {
      const { container } = renderFlipCard({ isFlipped: true });
      const inner = container.querySelector(".flip-card-inner");
      expect(inner).toHaveClass("flipped");
    });
  });

  describe("アクセシビリティ", () => {
    it('role="button" が設定されている', () => {
      renderFlipCard();
      expect(screen.getByRole("button")).toBeInTheDocument();
    });

    it("aria-label が設定されている", () => {
      renderFlipCard({ isFlipped: false });
      const button = screen.getByRole("button");
      expect(button).toHaveAttribute("aria-label");
    });
  });

  // ─── speechProps（読み上げ機能）────────────────────────────────

  describe("speechProps", () => {
    const makeSpeechProps = (
      overrides: Partial<FlipCardSpeechProps> = {},
    ): FlipCardSpeechProps => ({
      speechState: { isSpeaking: false, isSupported: true },
      onSpeakFront: vi.fn(),
      onSpeakBack: vi.fn(),
      ...overrides,
    });

    it("speechProps なしの場合、読み上げボタンが表示されない（後方互換）", () => {
      renderFlipCard();
      // aria-label に「読み上げ」を含むボタンが存在しない
      expect(
        screen.queryByRole("button", { name: /読み上げ/ }),
      ).not.toBeInTheDocument();
    });

    it("isSupported=false の場合、読み上げボタンが表示されない", () => {
      renderFlipCard({
        speechProps: makeSpeechProps({
          speechState: { isSpeaking: false, isSupported: false },
        }),
      });
      expect(
        screen.queryByRole("button", { name: /読み上げ/ }),
      ).not.toBeInTheDocument();
    });

    it("isFlipped=false のとき、表面の読み上げボタンが表示される", () => {
      renderFlipCard({ isFlipped: false, speechProps: makeSpeechProps() });
      expect(
        screen.getByRole("button", { name: "表面を読み上げ" }),
      ).toBeInTheDocument();
    });

    it("isFlipped=false のとき、裏面の読み上げボタンは表示されない", () => {
      renderFlipCard({ isFlipped: false, speechProps: makeSpeechProps() });
      expect(
        screen.queryByRole("button", { name: /裏面.*読み上げ/ }),
      ).not.toBeInTheDocument();
    });

    it("isFlipped=true のとき、裏面の読み上げボタンが表示される", () => {
      renderFlipCard({ isFlipped: true, speechProps: makeSpeechProps() });
      expect(
        screen.getByRole("button", { name: "裏面を読み上げ" }),
      ).toBeInTheDocument();
    });

    it("isFlipped=true のとき、表面の読み上げボタンは表示されない", () => {
      renderFlipCard({ isFlipped: true, speechProps: makeSpeechProps() });
      expect(
        screen.queryByRole("button", { name: /表面.*読み上げ/ }),
      ).not.toBeInTheDocument();
    });

    it("isSpeaking=true のとき、表面ボタンの aria-label が停止状態を示す", () => {
      renderFlipCard({
        isFlipped: false,
        speechProps: makeSpeechProps({
          speechState: { isSpeaking: true, isSupported: true },
        }),
      });
      expect(
        screen.getByRole("button", { name: "表面の読み上げを停止" }),
      ).toBeInTheDocument();
    });

    it("表面の読み上げボタンをクリックすると onSpeakFront が呼ばれる", async () => {
      const onSpeakFront = vi.fn();
      renderFlipCard({
        isFlipped: false,
        speechProps: makeSpeechProps({ onSpeakFront }),
      });
      const user = userEvent.setup();
      await user.click(screen.getByRole("button", { name: "表面を読み上げ" }));
      expect(onSpeakFront).toHaveBeenCalledTimes(1);
    });

    it("裏面の読み上げボタンをクリックすると onSpeakBack が呼ばれる", async () => {
      const onSpeakBack = vi.fn();
      renderFlipCard({
        isFlipped: true,
        speechProps: makeSpeechProps({ onSpeakBack }),
      });
      const user = userEvent.setup();
      await user.click(screen.getByRole("button", { name: "裏面を読み上げ" }));
      expect(onSpeakBack).toHaveBeenCalledTimes(1);
    });

    it("読み上げボタンをクリックしてもカードがフリップしない（クリック伝播防止）", async () => {
      const onFlip = vi.fn();
      const onSpeakFront = vi.fn();
      renderFlipCard({
        isFlipped: false,
        onFlip,
        speechProps: makeSpeechProps({ onSpeakFront }),
      });
      const user = userEvent.setup();
      await user.click(screen.getByRole("button", { name: "表面を読み上げ" }));
      expect(onFlip).not.toHaveBeenCalled();
      expect(onSpeakFront).toHaveBeenCalledTimes(1);
    });

    it("front が空のとき、表面の読み上げボタンが disabled になる", () => {
      renderFlipCard({
        front: "",
        isFlipped: false,
        speechProps: makeSpeechProps(),
      });
      // aria-label は「表面を読み上げ」だが disabled 状態
      const btn = screen.getByRole("button", { name: "表面を読み上げ" });
      expect(btn).toBeDisabled();
    });
  });
});

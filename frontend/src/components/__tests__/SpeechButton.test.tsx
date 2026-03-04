/**
 * 【テスト概要】: SpeechButton コンポーネントのテスト
 * 【テスト対象】: SpeechButton コンポーネント
 * 【テスト対応】: disabled・isSpeaking トグル・aria-label・onClick コールバック
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SpeechButton } from "../SpeechButton";

const defaultProps = {
  text: "読み上げテキスト",
  isSpeaking: false,
  onClick: vi.fn(),
};

const renderSpeechButton = (props: Partial<typeof defaultProps> = {}) => {
  return render(<SpeechButton {...defaultProps} {...props} />);
};

describe("SpeechButton", () => {
  // ─── 基本レンダリング ──────────────────────────────────────────

  describe("基本レンダリング", () => {
    it("ボタンが表示される", () => {
      renderSpeechButton();
      expect(screen.getByRole("button")).toBeInTheDocument();
    });

    it('type="button" が設定されている', () => {
      renderSpeechButton();
      expect(screen.getByRole("button")).toHaveAttribute("type", "button");
    });
  });

  // ─── isSpeaking の表示切り替え ────────────────────────────────

  describe("isSpeaking による表示切り替え", () => {
    it("isSpeaking=false のとき、再生ラベルが表示される", () => {
      renderSpeechButton({ isSpeaking: false });
      const btn = screen.getByRole("button");
      // 再生状態（play）を表す表示がある
      expect(btn.textContent).toBeTruthy();
    });

    it("isSpeaking=true のとき、停止ラベルが表示される", () => {
      renderSpeechButton({ isSpeaking: true });
      const btn = screen.getByRole("button");
      // 停止状態（stop）を表す表示がある
      expect(btn.textContent).toBeTruthy();
    });

    it("isSpeaking が変わると aria-label が変わる（再生 → 停止）", () => {
      const { rerender } = render(
        <SpeechButton {...defaultProps} isSpeaking={false} />,
      );
      const btnBefore = screen.getByRole("button");
      const labelBefore = btnBefore.getAttribute("aria-label") ?? "";

      rerender(<SpeechButton {...defaultProps} isSpeaking={true} />);
      const btnAfter = screen.getByRole("button");
      const labelAfter = btnAfter.getAttribute("aria-label") ?? "";

      expect(labelBefore).not.toBe(labelAfter);
    });
  });

  // ─── aria-label ────────────────────────────────────────────────

  describe("aria-label", () => {
    it("aria-label が設定されている", () => {
      renderSpeechButton();
      expect(screen.getByRole("button")).toHaveAttribute("aria-label");
    });

    it('label なし・isSpeaking=false のとき、aria-label に "読み上げ" が含まれる', () => {
      renderSpeechButton({ isSpeaking: false });
      const label = screen.getByRole("button").getAttribute("aria-label") ?? "";
      expect(label).toMatch(/読み上げ/);
    });

    it('label なし・isSpeaking=true のとき、aria-label に "停止" が含まれる', () => {
      renderSpeechButton({ isSpeaking: true });
      const label = screen.getByRole("button").getAttribute("aria-label") ?? "";
      expect(label).toMatch(/停止/);
    });

    it('label="表面" のとき、aria-label に "表面" が含まれる', () => {
      renderSpeechButton({ label: "表面" });
      const label = screen.getByRole("button").getAttribute("aria-label") ?? "";
      expect(label).toContain("表面");
    });

    it('label="表面" + isSpeaking=false → aria-label は "表面を読み上げ"', () => {
      renderSpeechButton({ label: "表面", isSpeaking: false });
      expect(screen.getByRole("button")).toHaveAttribute(
        "aria-label",
        "表面を読み上げ",
      );
    });

    it('label="表面" + isSpeaking=true → aria-label は "表面の読み上げを停止"', () => {
      renderSpeechButton({ label: "表面", isSpeaking: true });
      expect(screen.getByRole("button")).toHaveAttribute(
        "aria-label",
        "表面の読み上げを停止",
      );
    });

    it('label="裏面" + isSpeaking=false → aria-label は "裏面を読み上げ"', () => {
      renderSpeechButton({ label: "裏面", isSpeaking: false });
      expect(screen.getByRole("button")).toHaveAttribute(
        "aria-label",
        "裏面を読み上げ",
      );
    });
  });

  // ─── onClick ──────────────────────────────────────────────────

  describe("onClick", () => {
    it("ボタンをクリックすると onClick が呼ばれる", async () => {
      const onClick = vi.fn();
      renderSpeechButton({ onClick });
      const user = userEvent.setup();
      await user.click(screen.getByRole("button"));
      expect(onClick).toHaveBeenCalledTimes(1);
    });

    it("isSpeaking=true のときクリックすると onClick が呼ばれる（停止）", async () => {
      const onClick = vi.fn();
      renderSpeechButton({ isSpeaking: true, onClick });
      const user = userEvent.setup();
      await user.click(screen.getByRole("button"));
      expect(onClick).toHaveBeenCalledTimes(1);
    });
  });

  // ─── disabled ──────────────────────────────────────────────────

  describe("disabled", () => {
    it("disabled=true のとき、ボタンが非活性状態になる", () => {
      renderSpeechButton({ disabled: true });
      expect(screen.getByRole("button")).toBeDisabled();
    });

    it("disabled=true のとき、クリックしても onClick が呼ばれない", async () => {
      const onClick = vi.fn();
      renderSpeechButton({ disabled: true, onClick });
      const user = userEvent.setup();
      await user.click(screen.getByRole("button"));
      expect(onClick).not.toHaveBeenCalled();
    });

    it("disabled が省略された場合、デフォルトで非活性でない", () => {
      renderSpeechButton();
      expect(screen.getByRole("button")).not.toBeDisabled();
    });

    it("disabled=false の場合、ボタンがクリックできる", async () => {
      const onClick = vi.fn();
      renderSpeechButton({ disabled: false, onClick });
      const user = userEvent.setup();
      await user.click(screen.getByRole("button"));
      expect(onClick).toHaveBeenCalledTimes(1);
    });
  });
});

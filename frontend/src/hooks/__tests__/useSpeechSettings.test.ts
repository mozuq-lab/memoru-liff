/**
 * 【テスト概要】: useSpeechSettings フックのテスト
 * 【テスト対象】: useSpeechSettings フック（localStorage 読み書き）
 * 【テスト対応】: userId undefined 時のデフォルト値・parse エラー時のフォールバック・partial update
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSpeechSettings } from "../useSpeechSettings";
import type { SpeechSettings } from "@/types/speech";

const DEFAULT_SETTINGS: SpeechSettings = { autoPlay: false, rate: 1 };

describe("useSpeechSettings", () => {
  const TEST_USER_ID = "test-user-123";
  const STORAGE_KEY = `speech-settings:${TEST_USER_ID}`;

  beforeEach(() => {
    // setup.ts で localStorage は vi.fn() モックに置き換え済み。
    // 実際のデータ保存はされないため、各テスト前に呼び出し履歴をリセットする。
    vi.mocked(localStorage.getItem).mockReset();
    vi.mocked(localStorage.setItem).mockReset();
    vi.mocked(localStorage.removeItem).mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ─── デフォルト設定 ───────────────────────────────────────────

  describe("デフォルト設定", () => {
    it("userId が undefined の場合、デフォルト設定を返す", () => {
      const { result } = renderHook(() => useSpeechSettings(undefined));
      expect(result.current.settings).toEqual(DEFAULT_SETTINGS);
    });

    it("userId が undefined の場合、localStorage に書き込まない", () => {
      const setItem = vi.spyOn(Storage.prototype, "setItem");
      const { result } = renderHook(() => useSpeechSettings(undefined));
      act(() => {
        result.current.updateSettings({ autoPlay: true });
      });
      expect(setItem).not.toHaveBeenCalled();
    });

    it("localStorage に保存済みの設定がない場合、デフォルト設定を返す", () => {
      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));
      expect(result.current.settings).toEqual(DEFAULT_SETTINGS);
    });
  });

  // ─── localStorage からの読み込み ──────────────────────────────

  describe("設定の読み込み", () => {
    it("localStorage に有効な設定が保存されている場合、その値を返す", () => {
      const saved: SpeechSettings = { autoPlay: true, rate: 0.5 };
      vi.mocked(localStorage.getItem).mockReturnValueOnce(JSON.stringify(saved));

      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));
      expect(result.current.settings).toEqual(saved);
    });

    it("localStorage の値が JSON parse エラーの場合、デフォルト設定にフォールバック", () => {
      vi.mocked(localStorage.getItem).mockReturnValueOnce("invalid json {{{");
      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));
      expect(result.current.settings).toEqual(DEFAULT_SETTINGS);
    });

    it("localStorage の rate が不正値の場合、rate をデフォルト (1) にフォールバック", () => {
      vi.mocked(localStorage.getItem).mockReturnValueOnce(
        JSON.stringify({ autoPlay: true, rate: 99 }),
      );
      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));
      expect(result.current.settings.rate).toBe(1);
      expect(result.current.settings.autoPlay).toBe(true);
    });

    it("localStorage の autoPlay が boolean でない場合、デフォルト (false) にフォールバック", () => {
      vi.mocked(localStorage.getItem).mockReturnValueOnce(
        JSON.stringify({ autoPlay: "yes", rate: 1.5 }),
      );
      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));
      expect(result.current.settings.autoPlay).toBe(false);
    });
  });

  // ─── 設定の更新 ───────────────────────────────────────────────

  describe("updateSettings", () => {
    it("updateSettings で設定を更新すると state が変わる", () => {
      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));
      act(() => {
        result.current.updateSettings({ autoPlay: true });
      });
      expect(result.current.settings.autoPlay).toBe(true);
      expect(result.current.settings.rate).toBe(1); // 既存値を維持
    });

    it("partial update: 指定しなかったフィールドは既存値を維持する", () => {
      const initial: SpeechSettings = { autoPlay: true, rate: 1.5 };
      vi.mocked(localStorage.getItem).mockReturnValueOnce(JSON.stringify(initial));

      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));
      act(() => {
        result.current.updateSettings({ rate: 0.5 });
      });
      expect(result.current.settings.autoPlay).toBe(true); // 変わらない
      expect(result.current.settings.rate).toBe(0.5); // 更新された
    });

    it("updateSettings 後に localStorage に保存される", () => {
      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));
      act(() => {
        result.current.updateSettings({ autoPlay: true, rate: 1.5 });
      });
      // localStorage は vi.fn() モックのため実際には保存されない。
      // setItem が正しい引数で呼ばれたことを確認する。
      expect(localStorage.setItem).toHaveBeenCalledWith(
        STORAGE_KEY,
        JSON.stringify({ autoPlay: true, rate: 1.5 }),
      );
    });

    it("userId が undefined の場合、updateSettings を呼んでも localStorage に保存しない", () => {
      const { result } = renderHook(() => useSpeechSettings(undefined));
      act(() => {
        result.current.updateSettings({ autoPlay: true });
      });
      // localStorage は vi.fn() モックなので setItem が呼ばれていないことを確認
      expect(localStorage.setItem).not.toHaveBeenCalled();
    });

    it("updateSettings で rate を 0.5 に設定できる", () => {
      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));
      act(() => {
        result.current.updateSettings({ rate: 0.5 });
      });
      expect(result.current.settings.rate).toBe(0.5);
    });

    it("updateSettings で rate を 1.5 に設定できる", () => {
      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));
      act(() => {
        result.current.updateSettings({ rate: 1.5 });
      });
      expect(result.current.settings.rate).toBe(1.5);
    });
  });

  // ─── ユーザーID によるキー分離 ────────────────────────────────

  describe("ユーザーID によるキー分離", () => {
    it("異なる userId は別々の localStorage キーに保存される", () => {
      const { result: r1 } = renderHook(() => useSpeechSettings("user-A"));
      const { result: r2 } = renderHook(() => useSpeechSettings("user-B"));

      act(() => {
        r1.current.updateSettings({ autoPlay: true });
      });

      expect(r1.current.settings.autoPlay).toBe(true);
      expect(r2.current.settings.autoPlay).toBe(false); // 別ユーザーは影響を受けない
    });
  });
});

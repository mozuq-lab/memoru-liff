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

  // ─── autoPlay シナリオ (US2) ──────────────────────────────────

  describe("autoPlay (US2)", () => {
    it("autoPlay true に設定した後、rate を更新しても autoPlay は true を保持する", () => {
      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));

      act(() => {
        result.current.updateSettings({ autoPlay: true });
      });
      expect(result.current.settings.autoPlay).toBe(true);

      // 「次のカード」相当の操作（rate 変更）をしても autoPlay は維持される
      act(() => {
        result.current.updateSettings({ rate: 1.5 });
      });
      expect(result.current.settings.autoPlay).toBe(true);
      expect(result.current.settings.rate).toBe(1.5);
    });

    it("autoPlay を true → false に戻せる（手動停止が設定変更しない設計の逆：設定変更は可能）", () => {
      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));

      act(() => {
        result.current.updateSettings({ autoPlay: true });
      });
      expect(result.current.settings.autoPlay).toBe(true);

      act(() => {
        result.current.updateSettings({ autoPlay: false });
      });
      expect(result.current.settings.autoPlay).toBe(false);
    });

    it("localStorage に autoPlay: true が保存されている場合、初期値として読み込む", () => {
      vi.mocked(localStorage.getItem).mockReturnValueOnce(
        JSON.stringify({ autoPlay: true, rate: 1 }),
      );
      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));
      expect(result.current.settings.autoPlay).toBe(true);
    });

    it("autoPlay true 設定時に localStorage へ保存される", () => {
      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));
      act(() => {
        result.current.updateSettings({ autoPlay: true });
      });
      expect(localStorage.setItem).toHaveBeenCalledWith(
        STORAGE_KEY,
        JSON.stringify({ autoPlay: true, rate: 1 }),
      );
    });
  });

  // ─── userId 遅延確定 (REQ-002) ───────────────────────────────

  describe("userId 遅延確定 (REQ-002)", () => {
    it("userId が undefined → 有効値に変化したとき、保存済み設定が読み込まれる", () => {
      // 【テスト目的】: useEffect([userId]) による遅延読み込みの動作確認
      // 【テスト内容】: userId を undefined → "test-user-123" に rerender し、localStorage の設定が反映されるか検証
      // 【期待される動作】: rerender 後に保存済みの { autoPlay: true, rate: 1.5 } が settings に反映される
      // 🔵 REQ-002 受け入れ基準に基づく

      // 【テストデータ準備】: localStorage に保存済み設定をセットアップ
      const saved: SpeechSettings = { autoPlay: true, rate: 1.5 };
      vi.mocked(localStorage.getItem).mockReturnValue(JSON.stringify(saved));

      // 【初期条件設定】: userId=undefined で hook を初期化
      const { result, rerender } = renderHook(
        ({ userId }: { userId: string | undefined }) => useSpeechSettings(userId),
        { initialProps: { userId: undefined as string | undefined } },
      );

      // 【前提条件確認】: 初期状態はデフォルト設定
      // 【検証項目】: userId=undefined 時はデフォルト設定が適用される
      expect(result.current.settings).toEqual({ autoPlay: false, rate: 1 });

      // 【実際の処理実行】: userId を有効値に変更して rerender
      // 【処理内容】: useEffect([userId]) が発火し、loadSettings を実行する
      rerender({ userId: "test-user-123" });

      // 【結果検証】: localStorage から保存済み設定が読み込まれた
      // 【期待値確認】: autoPlay: true, rate: 1.5 が反映されていること
      // 【検証項目】: useEffect による遅延読み込みが正しく動作する 🔵
      expect(result.current.settings).toEqual(saved);
    });
  });

  // ─── localStorage.setItem 例外処理 (REQ-102) ─────────────────

  describe("localStorage.setItem 例外処理 (REQ-102)", () => {
    it("localStorage.setItem が throw しても state が更新される", () => {
      // 【テスト目的】: try/catch による localStorage 例外時の state 更新保証
      // 【テスト内容】: setItem が QuotaExceededError を throw する状態で updateSettings を呼び、state が更新されるか検証
      // 【期待される動作】: 例外発生時でも settings.autoPlay が true に更新される
      // 🟡 REQ-102 受け入れ基準 + loadSettings パターンからの推測

      // 【テストデータ準備】: setItem を例外を throw するモックに設定
      vi.mocked(localStorage.setItem).mockImplementation(() => {
        throw new Error("QuotaExceededError");
      });

      // 【初期条件設定】: userId 有効状態で hook を初期化
      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));

      // 【実際の処理実行】: updateSettings で autoPlay を true に変更
      // 【処理内容】: setItem は throw するが、try/catch で抑制されるはず
      act(() => {
        result.current.updateSettings({ autoPlay: true });
      });

      // 【結果検証】: state は正常に更新されている
      // 【検証項目】: localStorage 例外時でも state 更新が保証される 🟡
      expect(result.current.settings.autoPlay).toBe(true);
    });

    it("localStorage.setItem が throw してもエラーがスローされない", () => {
      // 【テスト目的】: try/catch による localStorage 例外時のエラー非伝播確認
      // 【テスト内容】: setItem が例外を throw しても updateSettings 呼び出し元にエラーが伝播しないことを検証
      // 【期待される動作】: act 内の updateSettings 呼び出しが例外なく完了する
      // 🟡 REQ-102 受け入れ基準 + loadSettings パターンからの推測

      // 【テストデータ準備】: setItem を例外を throw するモックに設定
      vi.mocked(localStorage.setItem).mockImplementation(() => {
        throw new Error("QuotaExceededError");
      });

      // 【初期条件設定】: userId 有効状態で hook を初期化
      const { result } = renderHook(() => useSpeechSettings(TEST_USER_ID));

      // 【結果検証】: updateSettings がエラーをスローしないこと
      // 【検証項目】: 例外が呼び出し元に伝播しない 🟡
      expect(() => {
        act(() => {
          result.current.updateSettings({ rate: 1.5 });
        });
      }).not.toThrow();
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

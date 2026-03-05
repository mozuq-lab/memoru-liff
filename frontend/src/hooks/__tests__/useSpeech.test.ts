/**
 * 【テスト概要】: useSpeech フックのテスト
 * 【テスト対象】: useSpeech フック
 * 【テスト対応】: isSupported 判定・speak・cancel・isSpeaking・cleanup
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSpeech } from "../useSpeech";
import type { SpeechRate } from "@/types/speech";

// モック SpeechSynthesisUtterance インスタンス型
interface MockUtteranceInstance {
  text: string;
  rate: number;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}

describe("useSpeech", () => {
  const mockCancel = vi.fn();
  const mockSpeak = vi.fn();
  let MockUtteranceClass: ReturnType<typeof vi.fn>;
  let lastUtterance: MockUtteranceInstance;

  beforeEach(() => {
    mockCancel.mockReset();
    mockSpeak.mockReset();

    // NOTE: vi.fn() に渡す実装は通常関数（function キーワード）にする必要がある。
    //       アロー関数はコンストラクタとして呼び出せないため、
    //       useSpeech.ts 内の `new SpeechSynthesisUtterance(text)` が失敗する。
    MockUtteranceClass = vi.fn(function (
      this: MockUtteranceInstance,
      text: string,
    ) {
      this.text = text;
      this.rate = 1;
      this.onend = null;
      this.onerror = null;
      lastUtterance = this;
    });

    vi.stubGlobal("speechSynthesis", {
      speak: mockSpeak,
      cancel: mockCancel,
      speaking: false,
    });
    vi.stubGlobal("SpeechSynthesisUtterance", MockUtteranceClass);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  // ─── isSupported ─────────────────────────────────────────────

  describe("isSupported", () => {
    it("speechSynthesis が window に存在する場合、isSupported は true", () => {
      const { result } = renderHook(() => useSpeech());
      expect(result.current.isSupported).toBe(true);
    });

    it("speechSynthesis が window に存在しない場合、isSupported は false", () => {
      vi.unstubAllGlobals();
      const { result } = renderHook(() => useSpeech());
      expect(result.current.isSupported).toBe(false);
    });
  });

  // ─── speak ───────────────────────────────────────────────────

  describe("speak", () => {
    it("speak を呼んだ直後に isSpeaking が true になる", () => {
      const { result } = renderHook(() => useSpeech());
      act(() => {
        result.current.speak("テスト");
      });
      expect(result.current.isSpeaking).toBe(true);
    });

    it("空文字を渡した場合は音声合成を呼び出さない", () => {
      const { result } = renderHook(() => useSpeech());
      act(() => {
        result.current.speak("");
      });
      expect(mockSpeak).not.toHaveBeenCalled();
      expect(result.current.isSpeaking).toBe(false);
    });

    it("speak 呼び出し時に SpeechSynthesisUtterance が正しいテキストで作成される", () => {
      const { result } = renderHook(() => useSpeech());
      act(() => {
        result.current.speak("読み上げテスト");
      });
      expect(MockUtteranceClass).toHaveBeenCalledWith("読み上げテスト");
      expect(mockSpeak).toHaveBeenCalledTimes(1);
    });

    it("speak 呼び出し前に cancel を先行して呼び出す（再発話のため）", () => {
      const { result } = renderHook(() => useSpeech());
      act(() => {
        result.current.speak("テスト");
      });
      // cancel は speak の中で先行して呼ばれる
      expect(mockCancel).toHaveBeenCalled();
    });

    it("発話中に再度 speak を呼ぶと cancel してから再発話する", () => {
      const { result } = renderHook(() => useSpeech());
      act(() => {
        result.current.speak("1回目");
      });
      const cancelCountAfterFirst = mockCancel.mock.calls.length;

      act(() => {
        result.current.speak("2回目");
      });

      expect(mockCancel.mock.calls.length).toBeGreaterThan(
        cancelCountAfterFirst,
      );
      expect(MockUtteranceClass).toHaveBeenLastCalledWith("2回目");
    });

    it("isSupported が false の場合、speak を呼んでも何もしない", () => {
      vi.unstubAllGlobals();
      const { result } = renderHook(() => useSpeech());
      act(() => {
        result.current.speak("テスト");
      });
      expect(result.current.isSpeaking).toBe(false);
    });
  });

  // ─── cancel ──────────────────────────────────────────────────

  describe("cancel", () => {
    it("cancel を呼ぶと isSpeaking が false になる", () => {
      const { result } = renderHook(() => useSpeech());
      act(() => {
        result.current.speak("テスト");
      });
      expect(result.current.isSpeaking).toBe(true);

      act(() => {
        result.current.cancel();
      });
      expect(result.current.isSpeaking).toBe(false);
      expect(mockCancel).toHaveBeenCalled();
    });

    it("isSupported が false の場合、cancel を呼んでも window.speechSynthesis.cancel は呼ばれない", () => {
      vi.unstubAllGlobals();
      // unstub 後は speechSynthesis が存在しないため、呼び出してもクラッシュしない
      const { result } = renderHook(() => useSpeech());
      expect(() => {
        act(() => {
          result.current.cancel();
        });
      }).not.toThrow();
    });
  });

  // ─── onend / onerror ──────────────────────────────────────────

  describe("発話完了", () => {
    it("発話完了後（onend）に isSpeaking が false になる", () => {
      const { result } = renderHook(() => useSpeech());
      act(() => {
        result.current.speak("テスト");
      });
      expect(result.current.isSpeaking).toBe(true);

      act(() => {
        lastUtterance.onend?.();
      });
      expect(result.current.isSpeaking).toBe(false);
    });

    it("発話エラー（onerror）後に isSpeaking が false になる", () => {
      const { result } = renderHook(() => useSpeech());
      act(() => {
        result.current.speak("テスト");
      });
      expect(result.current.isSpeaking).toBe(true);

      act(() => {
        lastUtterance.onerror?.();
      });
      expect(result.current.isSpeaking).toBe(false);
    });
  });

  // ─── cleanup ──────────────────────────────────────────────────

  describe("cleanup", () => {
    it("アンマウント時に cancel が自動呼び出しされる", () => {
      const { unmount } = renderHook(() => useSpeech());
      const cancelCountBeforeUnmount = mockCancel.mock.calls.length;
      unmount();
      expect(mockCancel.mock.calls.length).toBeGreaterThan(
        cancelCountBeforeUnmount,
      );
    });
  });

  // ─── rate オプション (US3) ────────────────────────────────────

  describe("rate オプション (US3)", () => {
    it("rate を指定しない場合、utterance.rate は 1 になる", () => {
      const { result } = renderHook(() => useSpeech());
      act(() => {
        result.current.speak("テスト");
      });
      expect(lastUtterance.rate).toBe(1);
    });

    it("rate 0.5 を指定すると utterance.rate が 0.5 になる", () => {
      const { result } = renderHook(() => useSpeech({ rate: 0.5 }));
      act(() => {
        result.current.speak("テスト");
      });
      expect(lastUtterance.rate).toBe(0.5);
    });

    it("rate 1.5 を指定すると utterance.rate が 1.5 になる", () => {
      const { result } = renderHook(() => useSpeech({ rate: 1.5 }));
      act(() => {
        result.current.speak("テスト");
      });
      expect(lastUtterance.rate).toBe(1.5);
    });

    it("rate 1 を明示的に指定しても utterance.rate が 1 になる", () => {
      const { result } = renderHook(() => useSpeech({ rate: 1 }));
      act(() => {
        result.current.speak("テスト");
      });
      expect(lastUtterance.rate).toBe(1);
    });

    it("options.rate が変わると次回発話から新しい rate が反映される", () => {
      const { result, rerender } = renderHook(
        ({ rate }: { rate: SpeechRate }) => useSpeech({ rate }),
        { initialProps: { rate: 0.5 as SpeechRate } },
      );
      act(() => {
        result.current.speak("1回目");
      });
      expect(lastUtterance.rate).toBe(0.5);

      rerender({ rate: 1.5 });
      act(() => {
        result.current.speak("2回目");
      });
      expect(lastUtterance.rate).toBe(1.5);
    });
  });
});

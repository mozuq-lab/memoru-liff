/**
 * 【機能概要】: Web Speech API (SpeechSynthesis) の薄いラッパーフック
 * 【テスト対応】: useSpeech.test.ts
 */
import { useState, useEffect, useCallback, useRef } from "react";
import type { SpeechRate } from "@/types/speech";

interface UseSpeechOptions {
  /** 読み上げ速度。省略時は 1 */
  rate?: SpeechRate;
}

interface UseSpeechReturn {
  /** 現在発話中かどうか */
  isSpeaking: boolean;
  /** このデバイス/ブラウザで音声合成が利用可能か */
  isSupported: boolean;
  /** テキストを読み上げる。isSpeaking なら cancel してから再発話。空文字は何もしない */
  speak: (text: string) => void;
  /** 読み上げを停止する */
  cancel: () => void;
}

export const useSpeech = (options?: UseSpeechOptions): UseSpeechReturn => {
  const isSupported =
    typeof window !== "undefined" && "speechSynthesis" in window;

  const [isSpeaking, setIsSpeaking] = useState(false);

  // rate は options が変わっても speak 関数を再生成しないよう ref で管理
  const rateRef = useRef<number>(options?.rate ?? 1);
  useEffect(() => {
    rateRef.current = options?.rate ?? 1;
  }, [options?.rate]);

  const cancel = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, [isSupported]);

  const speak = useCallback(
    (text: string) => {
      if (!isSupported || !text) return;
      // 既存の発話を停止してから新規発話を開始
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = rateRef.current;
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = () => setIsSpeaking(false);
      window.speechSynthesis.speak(utterance);
      setIsSpeaking(true);
    },
    [isSupported],
  );

  // アンマウント時にクリーンアップ
  // NOTE: vi.unstubAllGlobals() 後に cleanup が走ることがあるため、実行時に存在確認する
  useEffect(() => {
    return () => {
      if (typeof window !== "undefined" && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  return { isSpeaking, isSupported, speak, cancel };
};

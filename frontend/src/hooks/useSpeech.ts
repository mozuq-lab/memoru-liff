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

  // F-7: このフックが発話中かどうかをアンマウント時の cleanup から参照するための ref。
  // SpeechSynthesis はグローバル単一キューのため、isSpeaking state を直接 cleanup で
  // 読むと古い値を掴む。発話開始/終了で同期更新する ref を別に持つ。
  const speakingRef = useRef(false);

  // rate は options が変わっても speak 関数を再生成しないよう ref で管理
  const rateRef = useRef<number>(options?.rate ?? 1);
  useEffect(() => {
    rateRef.current = options?.rate ?? 1;
  }, [options?.rate]);

  const cancel = useCallback(() => {
    if (!isSupported) return;
    window.speechSynthesis.cancel();
    speakingRef.current = false;
    setIsSpeaking(false);
  }, [isSupported]);

  const speak = useCallback(
    (text: string) => {
      if (!isSupported || !text) return;
      // 既存の発話を停止してから新規発話を開始
      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = rateRef.current;
      utterance.onend = () => {
        speakingRef.current = false;
        setIsSpeaking(false);
      };
      utterance.onerror = () => {
        speakingRef.current = false;
        setIsSpeaking(false);
      };
      window.speechSynthesis.speak(utterance);
      speakingRef.current = true;
      setIsSpeaking(true);
    },
    [isSupported],
  );

  // アンマウント時のクリーンアップ。
  // F-7: このフックが発話中の場合のみ cancel する。無条件 cancel だと他コンポーネント
  // 起点の発話まで止めてしまう。ただし SpeechSynthesis はグローバル単一キューのため、
  // 完全な分離は不可能（複数フックが同時に発話すると後発が前発を上書きする）。
  // NOTE: vi.unstubAllGlobals() 後に cleanup が走ることがあるため、実行時に存在確認する
  useEffect(() => {
    return () => {
      if (
        speakingRef.current &&
        typeof window !== "undefined" &&
        window.speechSynthesis
      ) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  return { isSpeaking, isSupported, speak, cancel };
};

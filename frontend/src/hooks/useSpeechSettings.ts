/**
 * 【機能概要】: localStorage に保存された SpeechSettings を読み書きするフック
 * 【テスト対応】: useSpeechSettings.test.ts
 */
import { useState } from "react";
import type { SpeechRate, SpeechSettings } from "@/types/speech";

const DEFAULT_SETTINGS: SpeechSettings = { autoPlay: false, rate: 1 };

const VALID_RATES: SpeechRate[] = [0.5, 1, 1.5];

const isValidRate = (value: unknown): value is SpeechRate =>
  VALID_RATES.includes(value as SpeechRate);

function loadSettings(userId: string): SpeechSettings {
  try {
    const raw = localStorage.getItem(`speech-settings:${userId}`);
    if (!raw) return { ...DEFAULT_SETTINGS };
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    const rate = isValidRate(parsed.rate) ? parsed.rate : DEFAULT_SETTINGS.rate;
    const autoPlay =
      typeof parsed.autoPlay === "boolean"
        ? parsed.autoPlay
        : DEFAULT_SETTINGS.autoPlay;
    return { autoPlay, rate };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

interface UseSpeechSettingsReturn {
  /** 現在の読み上げ設定 */
  settings: SpeechSettings;
  /** 設定を更新して localStorage に保存する（partial パッチ） */
  updateSettings: (patch: Partial<SpeechSettings>) => void;
}

export const useSpeechSettings = (
  userId: string | undefined,
): UseSpeechSettingsReturn => {
  const [settings, setSettings] = useState<SpeechSettings>(() => {
    if (!userId) return { ...DEFAULT_SETTINGS };
    return loadSettings(userId);
  });

  const updateSettings = (patch: Partial<SpeechSettings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      if (userId) {
        localStorage.setItem(`speech-settings:${userId}`, JSON.stringify(next));
      }
      return next;
    });
  };

  return { settings, updateSettings };
};

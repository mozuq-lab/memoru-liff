/**
 * 読み上げ速度（遅め / 標準 / 速め の3段階）
 */
export type SpeechRate = 0.5 | 1 | 1.5;

/**
 * ユーザーごとの読み上げ設定。
 * localStorage キー: `speech-settings:<userId>`
 */
export interface SpeechSettings {
  /** カード表示時に自動読み上げするか。デフォルト: false */
  autoPlay: boolean;
  /** 読み上げ速度。デフォルト: 1 */
  rate: SpeechRate;
}

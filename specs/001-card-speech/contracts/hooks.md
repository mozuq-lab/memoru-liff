# Hook Contracts: Card Text-to-Speech

**Feature**: 001-card-speech
**Date**: 2026-03-04

---

## useSpeech

`SpeechSynthesis` API の薄いラッパー。発話・停止・状態管理を担う。

```ts
interface UseSpeechOptions {
  /** 読み上げ速度。省略時は 1 */
  rate?: SpeechRate;
}

interface UseSpeechReturn {
  /** 現在発話中かどうか */
  isSpeaking: boolean;
  /** このデバイス/ブラウザで音声合成が利用可能か */
  isSupported: boolean;
  /**
   * テキストを読み上げる。
   * - isSpeaking なら cancel してから speak（再読み上げ）
   * - text が空なら何もしない
   */
  speak: (text: string) => void;
  /** 読み上げを停止する */
  cancel: () => void;
}

declare function useSpeech(options?: UseSpeechOptions): UseSpeechReturn;
```

**Contract rules**:

- `isSupported` は `'speechSynthesis' in window` で判定し、初期化時に1度だけ評価する
- `speak(text)` を呼んだ直後に `isSpeaking` が `true` になる
- `cancel()` 呼び出し後または発話完了後に `isSpeaking` が `false` になる
- コンポーネントアンマウント時に `cancel()` を自動呼び出しする（cleanup）

---

## useSpeechSettings

localStorage に保存された `SpeechSettings` を読み書きする。

```ts
interface UseSpeechSettingsReturn {
  /** 現在の読み上げ設定 */
  settings: SpeechSettings;
  /** 設定を更新して localStorage に保存する */
  updateSettings: (patch: Partial<SpeechSettings>) => void;
}

declare function useSpeechSettings(
  userId: string | undefined,
): UseSpeechSettingsReturn;
```

**Contract rules**:

- `userId` が `undefined` の場合、localStorage 読み書きを行わずデフォルト設定を返す
- localStorage の値が parse エラーまたは不正な場合、デフォルト `{ autoPlay: false, rate: 1 }` を使用し、エラーは throw しない
- `updateSettings` は partial パッチをマージして保存する（指定しないフィールドは既存値を維持）
- 複数コンポーネントから同じ hook を使った場合、各インスタンスが独立した React state を持つ（同期は不要。このアプリでは1箇所のみで使用）

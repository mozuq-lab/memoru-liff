# UI Component Contracts: Card Text-to-Speech

**Feature**: 001-card-speech
**Date**: 2026-03-04

---

## SpeechButton

表面・裏面それぞれのカードに表示する読み上げ/停止トグルボタン。

```ts
interface SpeechButtonProps {
  /** 読み上げ対象テキスト */
  text: string;
  /** 現在発話中かどうか（ボタン表示の切り替えに使用） */
  isSpeaking: boolean;
  /** クリック時のコールバック（発話開始 or 停止） */
  onClick: () => void;
  /** テキストが空のとき disabled にする。省略時 false */
  disabled?: boolean;
  /** アクセシビリティ用ラベル接頭辞（例: "表面", "裏面"） */
  label?: string;
}
```

**Contract rules**:

- `disabled === true` のとき、ボタンは視覚的に非活性で `onClick` は呼ばれない
- `isSpeaking === true` のとき、停止アイコン（■）またはそれに相当するラベルを表示
- `isSpeaking === false` のとき、再生アイコン（▶）またはそれに相当するラベルを表示
- `aria-label` に読み上げ対象面と状態（再生/停止）を含める

---

## FlipCard（更新）

既存 `FlipCard` に音声ボタン統合のための `speechProps` を追加する。後方互換を維持するため完全 optional。

```ts
interface FlipCardSpeechProps {
  /** useSpeech hook から取得した現在の発話状態 */
  speechState: {
    isSpeaking: boolean;
    isSupported: boolean;
  };
  /** 表面テキストの読み上げ開始/停止を行うコールバック */
  onSpeakFront: () => void;
  /** 裏面テキストの読み上げ開始/停止を行うコールバック */
  onSpeakBack: () => void;
}

// 既存 FlipCardProps への追加（optional）
interface FlipCardProps {
  front: string;
  back: string;
  isFlipped: boolean;
  onFlip: () => void;
  speechProps?: FlipCardSpeechProps; // ← 追加
}
```

**Contract rules**:

- `speechProps` が未指定の場合、既存の動作と完全に同じ（後方互換）
- `isSupported === false` の場合、SpeechButton は描画しない（非表示）
- 表面表示中は `onSpeakFront` のボタン、裏面表示中は `onSpeakBack` のボタンのみ表示する

---

## SpeechSettingsSection

`SettingsPage` 内に追加する読み上げ設定セクション。

```ts
interface SpeechSettingsSectionProps {
  /** 現在の読み上げ設定 */
  settings: SpeechSettings;
  /** 設定変更時のコールバック */
  onChange: (settings: SpeechSettings) => void;
  /** このデバイスで音声合成が使えるか（false の場合は non-supported メッセージを表示） */
  isSupported: boolean;
}
```

**Contract rules**:

- `isSupported === false` の場合、「このデバイスでは読み上げ機能は利用できません」と表示し、設定 UI は非表示
- 速度ラジオボタンは「遅め (0.5)」「標準 (1.0)」「速め (1.5)」の3択
- 自動読み上げはトグルスイッチ（既存の notification_time 設定と同じ UI パターン）

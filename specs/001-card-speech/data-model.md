# Data Model: Card Text-to-Speech

**Feature**: 001-card-speech
**Date**: 2026-03-04

---

## Entities

### SpeechSettings

ユーザーごとの読み上げ設定。フロントエンドの localStorage にのみ存在し、バックエンドへの永続化は行わない。

| Field      | Type         | Default | Description                      |
| ---------- | ------------ | ------- | -------------------------------- |
| `autoPlay` | `boolean`    | `false` | カード表示時に自動読み上げするか |
| `rate`     | `SpeechRate` | `1`     | 読み上げ速度                     |

**SpeechRate** は以下の3値のユニオン型:

| 値    | UI ラベル | 意味                      |
| ----- | --------- | ------------------------- |
| `0.5` | 遅め      | 通常速度の半分            |
| `1`   | 標準      | Web Speech API デフォルト |
| `1.5` | 速め      | 通常速度の1.5倍           |

**Storage**:

- キー: `speech-settings:<userId>` （`userId` は OIDC subject claim）
- 形式: `JSON.stringify(SpeechSettings)`
- 取得失敗時はデフォルト値 `{ autoPlay: false, rate: 1 }` を使用

---

### SpeechState

`useSpeech` フックが返す現在の発話状態。UI の表示制御に使用。

| Field         | Type      | Description                                 |
| ------------- | --------- | ------------------------------------------- |
| `isSpeaking`  | `boolean` | 現在発話中かどうか                          |
| `isSupported` | `boolean` | このデバイス/ブラウザで音声合成が利用可能か |

---

## State Transitions

```
[Idle]
  │  speak(text) が呼ばれる
  ▼
[Speaking]
  │  発話完了 / cancel() が呼ばれる / 次カードへ進む
  ▼
[Idle]
```

**手動停止（トグル）**: `isSpeaking === true` のときにボタンをタップ → `cancel()` → `[Idle]`
**カード遷移**: `moveToNext` 呼び出し時に `cancel()` → `[Idle]`
**自動フリップなし**: `[Speaking]` → `[Idle]` 後もカードは裏返らない

---

## Validation Rules

- `rate` は `[0.5, 1, 1.5]` のいずれかのみ許容。localStorage から読み込んだ値が不正な場合はデフォルト `1` にフォールバック
- `autoPlay` が `true` かつ `isSupported` が `false` の場合、自動読み上げは実行しない（エラーを出さない）
- テキストが空文字列の場合、`speak()` を呼び出さない

---

## No Backend Changes

この機能はフロントエンドのみの変更であり、バックエンド API・DynamoDB スキーマへの変更は一切不要。

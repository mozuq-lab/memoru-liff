# Research: Card Text-to-Speech

**Feature**: 001-card-speech
**Date**: 2026-03-04
**Status**: Complete — All NEEDS CLARIFICATION resolved

---

## Decision 1: Web Speech API — SpeechSynthesis のブラウザサポート

**Decision**: `window.speechSynthesis` を直接使用する。ポリフィルや外部ライブラリは不要。

**Rationale**:

- Chrome 33+, Safari 7+, Edge 14+, Firefox 49+ で利用可能（対象ブラウザ全カバー）
- LINE in-app browser（iOS: WebKit、Android: Chrome ベース）もサポート
- `'speechSynthesis' in window` による機能検出で非対応環境を安全にスキップできる

**Alternatives considered**:

- Amazon Polly: 追加コスト・バックエンド API 変更が必要。Web Speech API で十分
- Web Speech API ポリフィル: 対象ブラウザが全サポートのため不要

**Key API patterns**:

```ts
// 機能検出
const isSupported = "speechSynthesis" in window;

// 発話
const utter = new SpeechSynthesisUtterance(text);
utter.rate = 1.0; // 0.1 〜 10（仕様では 0.5/1/1.5 の3段階）
window.speechSynthesis.speak(utter);

// 停止
window.speechSynthesis.cancel();

// 再生中チェック
window.speechSynthesis.speaking; // boolean
```

**Note**: `speak()` はタブが非表示になると Chrome/Android で自動停止される（visibilitychange イベント不要）。iOS Safari はユーザーインタラクション後のみ発話可能（ボタンタップ後に呼び出す分には問題なし）。

---

## Decision 2: 設定の永続化 — ユーザーIDキーによる localStorage

**Decision**: `speech-settings:<userId>` をキーとして localStorage に JSON 保存する。

**Rationale**:

- CLAUDE.md の Assumptions: 「認証済みユーザーID に紐付けてローカルストレージに保存する」（Q1 回答）
- `useAuth` hook から取得できる `user.sub`（OIDC subject claim）をキーとして使用
- サーバーサイド同期は対象外（Assumptions）

**Storage format**:

```ts
interface SpeechSettings {
  autoPlay: boolean; // 自動読み上げ on/off
  rate: 0.5 | 1 | 1.5; // 読み上げ速度（遅め/標準/速め）
}
// key: `speech-settings:${userId}`
// default: { autoPlay: false, rate: 1 }
```

**Alternatives considered**:

- React Context のみ（メモリ）: ページリロードで消える。NG
- ユーザー API に persisting: FR-006 と Assumptions で明示的に対象外

---

## Decision 3: Hook 設計 — `useSpeech` と `useSpeechSettings` の分離

**Decision**: 責務を2つの hook に分離する。

- `useSpeech(text, options)` — SpeechSynthesis の直接制御（発話・停止・状態）
- `useSpeechSettings(userId)` — localStorage から設定を読み書きする専用 hook

**Rationale**:

- `useSpeech` は pure DOM API の薄いラッパー → Vitest でモックが容易
- `useSpeechSettings` は localStorage のみに依存 → 副作用が局所化され単体テストしやすい
- 既存の `useCardSearch` / `useAuth` と同様の「単一責任フック」パターンに準拠

**Alternatives considered**:

- 1つの `useSpeech` に全機能を集約: 設定変更のテストが複雑になる。NG
- グローバル Context: この機能では不要な複雑さを追加する。NG

---

## Decision 4: Vitest でのモック戦略

**Decision**: `window.speechSynthesis` を `vi.stubGlobal` でモックする。

**Rationale**:

- jsdom（Vitest のデフォルト環境）は `speechSynthesis` を実装していない
- `vi.stubGlobal('speechSynthesis', mockSynth)` でグローバルオブジェクトを差し替えられる
- `SpeechSynthesisUtterance` も同様に `vi.fn()` でモック可能

**Test pattern**:

```ts
const mockSpeechSynthesis = {
  speak: vi.fn(),
  cancel: vi.fn(),
  speaking: false,
};
vi.stubGlobal("speechSynthesis", mockSpeechSynthesis);
vi.stubGlobal(
  "SpeechSynthesisUtterance",
  vi.fn().mockImplementation((text) => ({ text, rate: 1 })),
);
```

---

## Decision 5: FlipCard への音声ボタン統合方法

**Decision**: `FlipCard` コンポーネントに `speechProps` オプショナル prop を追加する。

**Rationale**:

- `FlipCard` は既に表面と裏面のテキストを持っており、どちらを読み上げるかを判断できる
- 音声ボタンを `FlipCard` の各面内に配置することで UX が自然になる
- `speechProps` を optional にすることで既存のテストを破壊せず後方互換を維持

**Alternatives considered**:

- ReviewPage から SpeechButton を FlipCard の外に配置: テキストの見た目と読み上げボタンが離れてしまい UX が悪い
- FlipCard を完全リファクタリング: 既存テストの影響範囲が大きい。NG

---

## All NEEDS CLARIFICATION Resolved

| 項目                     | ステータス                               |
| ------------------------ | ---------------------------------------- |
| 設定のユーザー識別方法   | ✅ userId キー付き localStorage          |
| 手動停止後の次カード挙動 | ✅ 現在カードのみ停止、次カードは継続    |
| 自動フリップの有無       | ✅ 自動フリップなし                      |
| ブラウザサポート範囲     | ✅ Win Speech API で全対象ブラウザカバー |
| Vitest モック方法        | ✅ vi.stubGlobal で対応                  |

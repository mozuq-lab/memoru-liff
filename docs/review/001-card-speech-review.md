# 001-card-speech ブランチ コードレビュー

> **レビュー日**: 2026-03-05
> **レビュアー**: Claude Code (Opus 4.6) + Codex
> **ブランチ**: `001-card-speech` (base: `b1108cd`)
> **対象コミット**: `ce9f494..b173ded` (10 commits)

## 概要

LINE ベースの暗記カードアプリに Web Speech API を利用した読み上げ機能を追加するブランチ。手動読み上げ（US1）、自動読み上げ（US2）、速度設定（US3）の3つのユーザーストーリーを実装。

### 変更規模

- **新規ファイル**: 15（hooks, components, tests, specs）
- **変更ファイル**: 36（うち speech 関連 12、infra/docs 整理 24）
- **差分**: +2,744 / -5,287 行（※ infra/docs 削除が大部分）

---

## 指摘事項

### Critical

#### C-1: 停止トグルが機能しない

**場所**: `ReviewPage.tsx:535,603,665` / `useSpeech.ts:42-55` / `SpeechButton.tsx:25`

**問題**: `SpeechButton` は `isSpeaking` 時に停止アイコン（■）を表示するが、`onClick` に渡されるのは常に `speak(text)` であり、`cancel()` が呼ばれない。`useSpeech.speak()` 内部で `cancel()` → 再 `speak()` するため、停止ボタンを押しても再度読み上げが開始される。

**再現手順**:
1. カードの読み上げボタン（▶）をタップ → 読み上げ開始
2. ボタンが停止（■）に変化
3. 停止ボタン（■）をタップ → **期待: 停止** / **実際: 再度読み上げ開始**

**修正提案（Claude Code）**:

```tsx
// ReviewPage.tsx — onSpeakFront/onSpeakBack を isSpeaking で分岐
speechProps={{
  speechState: { isSpeaking, isSupported },
  onSpeakFront: () => (isSpeaking ? cancel() : speak(currentCard.front)),
  onSpeakBack: () => (isSpeaking ? cancel() : speak(currentCard.back)),
}}
```

**修正提案（Codex）**: `FlipCardSpeechProps` に `onCancel` を追加し、`SpeechButton` 内部で `isSpeaking` に応じて `onClick` / `onCancel` を切り替え。

**合意**: いずれの方法でも修正可能。前者はシンプルだが、表面を再生中に裏面ボタンを押した場合は「停止」ではなく「切り替え」が自然なため、後者のほうが拡張性が高い。ただし、現在の UI では表裏同時表示はないため、前者で十分。

---

### High

#### H-1: userId 遅延確定時に保存済み設定が読み込まれない

**場所**: `useSpeechSettings.ts:41-44` / `ReviewPage.tsx:59-61` / `SettingsPage.tsx:55-56`

**問題**: `useSpeechSettings` は `useState` の初期化関数内でのみ `loadSettings(userId)` を呼ぶ。`useAuth` は非同期で `user` を取得するため、初回レンダリング時は `userId = undefined` → `DEFAULT_SETTINGS` が返る。その後 `userId` が確定しても再読み込みが行われない。

**影響**: ユーザーが保存した autoPlay=true や rate=1.5 が無視され、常にデフォルト（autoPlay=false, rate=1）で動作する。

**修正提案**:

```tsx
// useSpeechSettings.ts — useEffect で userId 変化を監視
useEffect(() => {
  if (userId) {
    setSettings(loadSettings(userId));
  }
}, [userId]);
```

#### H-2: 無関係な infrastructure/docs 差分の混在

**場所**: `infrastructure/cdk/` 全体、`docs/` 配下の cognito-line-login 関連ファイル

**問題**: `001-card-speech` ブランチは `main` の `b1108cd` から分岐しており、その後 `main` に追加された cognito-line-login 関連コミット（`03a9d51..44066e4`）を含んでいない。結果として、diff 上は cognito-line-login 関連の削除として見える。

**修正提案**: `main` に rebase し、speech 機能のみの差分に整理する。

---

### Medium

#### M-1: 自動読み上げスイッチのアクセシブル名不足

**場所**: `SettingsPage.tsx:292-309`

**問題**: `role="switch"` の `<button>` に `aria-label` / `aria-labelledby` がない。外側の `<label>` は `htmlFor` がなくボタンと紐づかない。スクリーンリーダーでは無名のスイッチとして読まれる可能性がある。

**修正提案**:

```tsx
<button
  type="button"
  role="switch"
  aria-checked={speechSettings.autoPlay}
  aria-label="自動読み上げ"
  ...
>
```

#### M-2: localStorage.setItem の例外未処理

**場所**: `useSpeechSettings.ts:49-51`

**問題**: Safari Private Browsing モードや容量超過時に `localStorage.setItem` が例外を投げる。`loadSettings` は `try/catch` で保護されているが、保存側は未保護。

**修正提案**:

```tsx
const updateSettings = (patch: Partial<SpeechSettings>) => {
  setSettings((prev) => {
    const next = { ...prev, ...patch };
    if (userId) {
      try {
        localStorage.setItem(`speech-settings:${userId}`, JSON.stringify(next));
      } catch {
        // Safari Private Mode 等 — state のみ更新
      }
    }
    return next;
  });
};
```

#### M-3: FlipCard 内のインタラクティブ要素のネスト

**場所**: `FlipCard.tsx:32,60,80`

**問題**: `role="button"` + `tabIndex={0}` の `<div>` 内に `<button>`（SpeechButton）がネストされている。`stopPropagation` で対処しているが、支援技術によってはフォーカス順序やボタン認識が不安定になるケースがある。

**修正提案**: 現時点では `stopPropagation` で実用上は動作するが、将来的にはカード全体を `role="group"` にし、フリップ用とスピーチ用のボタンを並列にするリファクタリングを検討。

#### M-4: 統合テスト不足

**場所**: `ReviewPage.test.tsx`, `SettingsPage.test.tsx`

**問題**: 単体テストは充実しているが、以下の統合テストが欠けている:
- 停止トグル動作（C-1 のバグを検出できない）
- `userId: undefined → defined` 時の設定再読み込み（H-1 のバグを検出できない）
- autoPlay 時のカード遷移 → 自動読み上げ発火シーケンス

---

### Low

#### L-1: utterance.lang 未設定

**場所**: `useSpeech.ts:47`

**問題**: `SpeechSynthesisUtterance` の `lang` が設定されていない。日本語カードアプリだが、ブラウザのデフォルト言語が英語の場合、英語音声エンジンで日本語テキストが読み上げられる可能性がある。

**修正提案**: `utterance.lang = 'ja-JP'` をデフォルト設定するか、`useSpeech` のオプションとして `lang` を受け取れるようにする。

#### L-2: SpeechButton の text prop が未使用

**場所**: `SpeechButton.tsx:19`

**問題**: `text` prop を `_text` として受け取っているが、コンポーネント内で使用されていない。`disabled` の制御にも使われておらず、呼び出し側が別途 `disabled={!front}` を指定している。

**修正提案**: `text` prop を削除するか、`disabled` のデフォルト計算（`disabled={!text.trim()}`）に利用する。

---

### Info

#### I-1: ReviewPage の状態数過多

**場所**: `ReviewPage.tsx:43-56`

**観察**: `useState` が 16 個あり、状態遷移ロジックが複雑。カード読み上げ機能の追加でさらに3つの hook が加わった。

**提案**: このPRのスコープ外だが、次フェーズで状態遷移表を作成し `useReducer` への移行を検討すると保守性が向上する。

---

## 良い点

- **hook/component 分離**: `useSpeech` / `useSpeechSettings` / `SpeechButton` の責務分離が明確
- **テストカバレッジ**: `useSpeech`, `useSpeechSettings`, `SpeechButton` はカバレッジ 100%（T017 で確認済み）
- **後方互換**: `FlipCard` の `speechProps` はオプショナルで、既存利用箇所への影響なし
- **アンマウント時クリーンアップ**: `useSpeech` で `speechSynthesis.cancel()` を呼んでおり、リソースリーク対策済み
- **rate の ref 管理**: `useSpeech` で `rateRef` を使い、`speak` 関数の不要な再生成を防止
- **仕様ドキュメント**: `specs/001-card-speech/` に研究・仕様・設計・タスクが体系的に整理されている

---

## 修正優先度まとめ

| 優先度 | ID | 概要 | 工数目安 |
|--------|----|------|----------|
| **Must** | C-1 | 停止トグル修正 | S |
| **Must** | H-1 | userId 遅延時の設定再読み込み | S |
| **Should** | H-2 | main への rebase（無関係差分除去） | M |
| **Should** | M-1 | switch の aria-label 追加 | XS |
| **Should** | M-2 | localStorage.setItem の try/catch | XS |
| **Could** | M-3 | FlipCard ネスト要素の改善 | M |
| **Could** | M-4 | 統合テスト追加 | M |
| **Could** | L-1 | utterance.lang 設定 | XS |
| **Could** | L-2 | 未使用 text prop 整理 | XS |

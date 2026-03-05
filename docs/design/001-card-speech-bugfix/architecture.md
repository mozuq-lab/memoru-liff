# 001-card-speech バグ修正 アーキテクチャ設計

**作成日**: 2026-03-05
**関連要件定義**: [requirements.md](../../spec/001-card-speech-bugfix/requirements.md)
**ヒアリング記録**: [design-interview.md](design-interview.md)

**【信頼性レベル凡例】**:

- 🔵 **青信号**: 要件定義書・既存実装・契約文書を参考にした確実な設計
- 🟡 **黄信号**: 要件定義書・既存実装から妥当な推測による設計
- 🔴 **赤信号**: 要件定義書・既存実装にない推測による設計

---

## システム概要 🔵

**信頼性**: 🔵 *requirements.md 概要より*

`001-card-speech` ブランチで実装されたカード読み上げ機能のバグ修正・改善。対象はフロントエンド（React hooks, components, pages）のみ。バックエンド・DB・インフラの変更なし。

## 修正対象ファイルと方針

### REQ-001: 停止トグル修正 🔵

**信頼性**: 🔵 *spec.md US1 Acceptance Scenario 3 + contracts/components.md onSpeakFront/onSpeakBack 定義より*

**対象ファイル**: `frontend/src/pages/ReviewPage.tsx`

**現状の問題**:

```
ReviewPage → FlipCard.speechProps.onSpeakFront = () => speak(text)
                                                       ↑ 常に speak() を呼ぶ
```

SpeechButton が `isSpeaking` 時に停止アイコン（■）を表示するが、`onClick` コールバックの `onSpeakFront` / `onSpeakBack` は常に `speak(text)` を呼ぶ。`useSpeech.speak()` は内部で `cancel()` → 再 `speak()` するため、停止にならない。

**修正方針**: ReviewPage で `onSpeakFront` / `onSpeakBack` を生成する際に `isSpeaking` 状態を参照し、発話中なら `cancel()` を呼ぶ。

```
修正後:
ReviewPage → FlipCard.speechProps.onSpeakFront = () => isSpeaking ? cancel() : speak(text)
```

**修正箇所**: ReviewPage 内の `speechProps` オブジェクト生成部分（3箇所: 通常モード、再採点モード、再確認モード）

**設計判断**: 🔵

- `useSpeech` hook 自体は変更しない（`speak()` の「cancel → re-speak」動作は「異なるテキストへの切り替え」ユースケースで正当）
- `FlipCardSpeechProps` インターフェースも変更不要（`onClick` の意味を「トグル」として呼び出し側で制御するのが契約に合致）
- 修正は ReviewPage のコールバック定義のみ

### REQ-002: userId 遅延確定時の設定再読み込み 🔵

**信頼性**: 🔵 *contracts/hooks.md useSpeechSettings Contract + レビュー H-1 より*

**対象ファイル**: `frontend/src/hooks/useSpeechSettings.ts`

**現状の問題**:

```
useSpeechSettings(userId)
  useState(() => userId ? loadSettings(userId) : DEFAULT)  ← 初回のみ
  // userId が後から確定しても再読み込みしない
```

**修正方針**: `useEffect` で `userId` の変化を監視し、有効値になったら `loadSettings` を再実行。

```tsx
// 追加する useEffect
useEffect(() => {
  if (userId) {
    setSettings(loadSettings(userId));
  }
}, [userId]);
```

**設計判断**: 🔵

- `userId` が `undefined` → `string` に変化したときのみ発火（初回有効時）
- `userId` が最初から有効な場合は `useState` 初期化で読み込み済みのため、`useEffect` は同じ値で上書きする（冪等）
- `userId` が `string` → 別の `string` に変化するケース（ユーザー切り替え）にも対応できる

### REQ-101: aria-label 追加 🔵

**信頼性**: 🔵 *WAI-ARIA switch パターン + レビュー M-1 より*

**対象ファイル**: `frontend/src/pages/SettingsPage.tsx`

**修正方針**: `role="switch"` の `<button>` に `aria-label="自動読み上げ"` を追加。

```tsx
<button
  type="button"
  role="switch"
  aria-checked={speechSettings.autoPlay}
  aria-label="自動読み上げ"  // ← 追加
  ...
>
```

### REQ-102: localStorage.setItem の例外処理 🟡

**信頼性**: 🟡 *loadSettings 側の try/catch パターンからの妥当な推測*

**対象ファイル**: `frontend/src/hooks/useSpeechSettings.ts`

**修正方針**: `updateSettings` 内の `localStorage.setItem` を `try/catch` で囲む。

```tsx
const updateSettings = (patch: Partial<SpeechSettings>) => {
  setSettings((prev) => {
    const next = { ...prev, ...patch };
    if (userId) {
      try {
        localStorage.setItem(`speech-settings:${userId}`, JSON.stringify(next));
      } catch {
        // Safari Private Mode / 容量超過 — state のみ更新
      }
    }
    return next;
  });
};
```

### REQ-103: 統合テスト追加 🔵

**信頼性**: 🔵 *REQ-001/REQ-002 の受け入れ基準より*

**対象ファイル**:

- (a) `frontend/src/hooks/__tests__/useSpeech.test.ts` — 停止トグル統合テスト追加
- (b) `frontend/src/hooks/__tests__/useSpeechSettings.test.ts` — userId 遅延確定テスト追加

**テスト設計**:

**(a) 停止トグルテスト**:

```
describe('停止トグル動作')
  it('isSpeaking 中に speak() ではなく cancel() が呼ばれるべき')
    → これは ReviewPage レベルの統合テストまたは手動テストで検証
    → useSpeech hook 自体のテストでは、cancel() 呼び出し後に isSpeaking=false を検証（既存）
```

NOTE: 停止トグルの不具合は ReviewPage のコールバック定義の問題であり、hook 単体テストでは検出できない。ReviewPage の統合テストまたは FlipCard の `speechProps.onSpeakFront` コールバック呼び出しテストで検証する。

**(b) userId 遅延確定テスト**:

```
describe('userId 遅延確定')
  it('userId が undefined → 有効値に変化したとき loadSettings が実行される')
  it('userId が最初から有効な場合は初期化時に正しく読み込まれる（既存動作維持）')
```

## 変更ファイル一覧

| ファイル | 修正内容 | REQ |
| --- | --- | --- |
| `frontend/src/pages/ReviewPage.tsx` | onSpeakFront/onSpeakBack で isSpeaking 判定追加 | REQ-001 |
| `frontend/src/hooks/useSpeechSettings.ts` | useEffect で userId 変化時の再読み込み + setItem try/catch | REQ-002, REQ-102 |
| `frontend/src/pages/SettingsPage.tsx` | switch ボタンに aria-label 追加 | REQ-101 |
| `frontend/src/hooks/__tests__/useSpeechSettings.test.ts` | userId 遅延確定テスト追加 | REQ-103(b) |
| `frontend/src/pages/__tests__/ReviewPage.test.tsx` or 新規テスト | 停止トグル統合テスト | REQ-103(a) |

## 技術的制約 🔵

**信頼性**: 🔵 *CLAUDE.md・contracts/ より*

- 既存テストを破壊しないこと（REQ-401）
- FlipCard の speechProps は引き続きオプショナル（REQ-402）
- `useSpeech` hook のインターフェースは変更しない（契約維持）
- `FlipCardSpeechProps` インターフェースは変更しない（契約維持）

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/001-card-speech-bugfix/requirements.md)
- **元仕様**: [specs/001-card-speech/spec.md](../../../specs/001-card-speech/spec.md)
- **Hook契約**: [specs/001-card-speech/contracts/hooks.md](../../../specs/001-card-speech/contracts/hooks.md)
- **Component契約**: [specs/001-card-speech/contracts/components.md](../../../specs/001-card-speech/contracts/components.md)

## 信頼性レベルサマリー

- 🔵 青信号: 9件 (90%)
- 🟡 黄信号: 1件 (10%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質

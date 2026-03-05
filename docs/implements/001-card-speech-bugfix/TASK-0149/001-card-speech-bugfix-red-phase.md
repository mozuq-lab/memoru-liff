# Red フェーズ記録: TASK-0149 ReviewPage 停止トグル修正

**作成日**: 2026-03-05
**タスクID**: TASK-0149
**フェーズ**: Red（失敗テスト作成完了）

---

## 作成したテストケースの一覧

| ID | テスト名 | 結果 | 信頼性 |
|----|----------|------|--------|
| TC-001 | 通常モード: 表面読み上げ中にボタンをクリックすると cancel() が呼ばれ、speak() は呼ばれない | FAIL（期待通り） | 🔵 |
| TC-002 | 通常モード: 裏面読み上げ中にボタンをクリックすると cancel() が呼ばれ、speak() は呼ばれない | FAIL（期待通り） | 🔵 |
| TC-003 | 通常モード: 停止中にボタンをクリックすると speak(text) が呼ばれ、cancel() は呼ばれない | PASS（既存動作確認） | 🔵 |

**既存テスト**: 62件 → 全てパス（回帰なし）

---

## テストが追加されたファイル

`frontend/src/pages/__tests__/ReviewPage.test.tsx`

---

## 追加したモック

ファイル先頭部分に以下を追加（`vi.mock` によるホイスト）:

```typescript
// 制御可能なモック変数
const mockSpeak = vi.fn();
const mockCancel = vi.fn();
let mockIsSpeaking = false;
let mockIsSupported = false;

vi.mock('@/hooks/useSpeech', () => ({
  useSpeech: () => ({
    isSpeaking: mockIsSpeaking,
    isSupported: mockIsSupported,
    speak: mockSpeak,
    cancel: mockCancel,
  }),
}));

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    user: { profile: { sub: 'test-user' } },
    isAuthenticated: true,
    isLoading: false,
    logout: vi.fn(),
  }),
}));

vi.mock('@/hooks/useSpeechSettings', () => ({
  useSpeechSettings: () => ({
    settings: { autoPlay: false, rate: 1 },
    updateSettings: vi.fn(),
  }),
}));
```

**重要**: `mockIsSupported = false` がデフォルトのため、既存テストでは SpeechButton が非表示になり影響なし。

---

## 期待される失敗内容

### TC-001 の失敗メッセージ
```
AssertionError: expected "vi.fn()" to be called 1 times, but got 0 times
  at ReviewPage.test.tsx:1805:26
```

**原因**: 現在の ReviewPage の `onSpeakFront` は `() => speak(currentCard.front)` と定義されており、`isSpeaking` 判定がない。クリック時に `cancel()` ではなく `speak()` が呼ばれる。

### TC-002 の失敗メッセージ
```
AssertionError: expected "vi.fn()" to be called 1 times, but got 0 times
  at ReviewPage.test.tsx:1858:26
```

**原因**: TC-001 と同様。`onSpeakBack` も `isSpeaking` 判定なしで常に `speak()` を呼ぶ。

---

## 実行コマンド

```bash
cd frontend && npx vitest run src/pages/__tests__/ReviewPage.test.tsx
```

---

## Green フェーズで実装すべき内容

ReviewPage.tsx の 3 箇所の speechProps を修正する：

### 1. 通常モード (L665-666)
```typescript
// 修正前
onSpeakFront: () => speak(currentCard.front),
onSpeakBack: () => speak(currentCard.back),

// 修正後
onSpeakFront: () => (isSpeaking ? cancel() : speak(currentCard.front)),
onSpeakBack: () => (isSpeaking ? cancel() : speak(currentCard.back)),
```

### 2. 再採点モード (L536-537)
```typescript
// 修正後
onSpeakFront: () => (isSpeaking ? cancel() : speak(regradeCard.front)),
onSpeakBack: () => (isSpeaking ? cancel() : speak(regradeCard.back)),
```

### 3. 再確認モード (L603-604)
```typescript
// 修正後
onSpeakFront: () => (isSpeaking ? cancel() : speak(reconfirmCard.front)),
onSpeakBack: () => (isSpeaking ? cancel() : speak(reconfirmCard.back)),
```

---

## 品質評価

- **テスト実行**: 成功（TC-001, TC-002 が期待通り失敗、TC-003 が期待通りパス）
- **期待値**: 明確で具体的
- **アサーション**: 適切（`toHaveBeenCalledTimes`, `not.toHaveBeenCalled`, `toHaveBeenCalledWith`）
- **実装方針**: 明確（3箇所の `isSpeaking ? cancel() : speak(text)` 追加）
- **信頼性レベル**: 🔵 青信号 3件（100%）

**判定**: ✅ 高品質

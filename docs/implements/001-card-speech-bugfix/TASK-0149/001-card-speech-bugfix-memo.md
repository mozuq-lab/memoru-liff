# TDD開発メモ: 001-card-speech-bugfix (TASK-0149)

## 概要

- 機能名: ReviewPage 停止トグル修正
- 開発開始: 2026-03-05
- 現在のフェーズ: Red

## 関連ファイル

- 元タスクファイル: `docs/tasks/001-card-speech-bugfix/TASK-0149.md`
- 要件定義: `docs/spec/001-card-speech-bugfix/requirements.md`
- テストケース定義: `docs/implements/001-card-speech-bugfix/TASK-0149/001-card-speech-bugfix-testcases.md`
- 実装ファイル（修正対象）: `frontend/src/pages/ReviewPage.tsx`
- テストファイル: `frontend/src/pages/__tests__/ReviewPage.test.tsx`
- Red フェーズ記録: `docs/implements/001-card-speech-bugfix/TASK-0149/001-card-speech-bugfix-red-phase.md`

## Red フェーズ（失敗するテスト作成）

### 作成日時

2026-03-05

### テストケース

| ID | テスト名 | 結果 | 信頼性 |
|----|----------|------|--------|
| TC-001 | 通常モード: 表面読み上げ中 → cancel() | FAIL（期待通り） | 🔵 |
| TC-002 | 通常モード: 裏面読み上げ中 → cancel() | FAIL（期待通り） | 🔵 |
| TC-003 | 通常モード: 停止中 → speak(text) | PASS（既存動作確認） | 🔵 |

**既存テスト**: 62件 → 全てパス（回帰なし）

### テストコード（追加箇所）

ファイル: `frontend/src/pages/__tests__/ReviewPage.test.tsx`

**モック追加（ファイル先頭部分）**:
```typescript
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

**新しい describe ブロック（ファイル末尾に追加）**:
```typescript
describe('TASK-0149: 停止トグル修正 - 通常モード', () => {
  beforeEach(() => {
    mockIsSupported = true;
    mockIsSpeaking = false;
    mockSpeak.mockClear();
    mockCancel.mockClear();
  });

  afterEach(() => {
    mockIsSupported = false;
    mockIsSpeaking = false;
  });

  // TC-001: isSpeaking=true で表面ボタン → cancel()
  // TC-002: isSpeaking=true で裏面ボタン → cancel()
  // TC-003: isSpeaking=false で表面ボタン → speak('質問1')
});
```

### 期待される失敗

**TC-001, TC-002 が失敗する理由**:
- 現在の `onSpeakFront: () => speak(currentCard.front)` は `isSpeaking` 判定なし
- `isSpeaking=true` でクリックしても `cancel()` が呼ばれず、`speak()` が呼ばれる
- `expect(mockCancel).toHaveBeenCalledTimes(1)` が `expected 1 but got 0` で失敗

**TC-003 がパスする理由**:
- 停止中（`isSpeaking=false`）のクリックで `speak(text)` が呼ばれることは現在も正常
- 既存の `onSpeakFront: () => speak(currentCard.front)` がそのまま機能する

### 次のフェーズへの要求事項

Green フェーズで `frontend/src/pages/ReviewPage.tsx` の 3 箇所を修正:

1. 通常モード (L665-666):
   ```typescript
   onSpeakFront: () => (isSpeaking ? cancel() : speak(currentCard.front)),
   onSpeakBack: () => (isSpeaking ? cancel() : speak(currentCard.back)),
   ```

2. 再採点モード (L536-537):
   ```typescript
   onSpeakFront: () => (isSpeaking ? cancel() : speak(regradeCard.front)),
   onSpeakBack: () => (isSpeaking ? cancel() : speak(regradeCard.back)),
   ```

3. 再確認モード (L603-604):
   ```typescript
   onSpeakFront: () => (isSpeaking ? cancel() : speak(reconfirmCard.front)),
   onSpeakBack: () => (isSpeaking ? cancel() : speak(reconfirmCard.back)),
   ```

## Green フェーズ（最小実装）

（未実施 - 次のフェーズで実装予定）

## Refactor フェーズ（品質改善）

（未実施 - Green フェーズ完了後に実施予定）

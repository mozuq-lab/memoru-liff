# TASK-0149 開発ノート：ReviewPage 停止トグル修正

**タスクID**: TASK-0149
**タスク名**: ReviewPage 停止トグル修正
**タスクタイプ**: TDD
**推定工数**: 2時間
**作成日**: 2026-03-05

---

## 1. 技術スタック

### フロントエンド
- **フレームワーク**: React 19 + TypeScript 5.x
- **テスティング**: Vitest + React Testing Library + userEvent
- **スタイリング**: Tailwind CSS 4
- **コンポーネント**: FlipCard, SpeechButton, ReviewPage

### 音声関連
- **Web Speech API**: `window.speechSynthesis` による読み上げ
- **useSpeech hook**: Web Speech API のラッパーフック（isSpeaking, speak(), cancel()）
- **FlipCardSpeechProps**: 読み上げ機能の統合インターフェース（speechState, onSpeakFront, onSpeakBack）

### 参照元
- `frontend/src/hooks/useSpeech.ts` — Web Speech API ラッパー
- `frontend/src/pages/ReviewPage.tsx` — 復習ページ（修正対象）
- `frontend/src/components/FlipCard.tsx` — フリップカードコンポーネント
- `frontend/src/components/SpeechButton.tsx` — 読み上げボタン
- `frontend/src/types/speech.ts` — 音声関連の型定義

---

## 2. 開発ルール

### プロジェクト共通ルール
- **コミット粒度**: タスクごとに1コミット（複数タスクをまとめない）
- **テスト目標**: 80% 以上のカバレッジを維持
- **契約維持**: useSpeech, FlipCardSpeechProps のインターフェースは変更しない

### タスク完了時の更新
1. `docs/tasks/001-card-speech-bugfix/TASK-0149.md` の完了条件を更新（`[ ]` → `[x]`）
2. 概要ファイル存在時は同様に更新
3. コミットメッセージは Tsumiki の `/tsumiki:tdd-*` ガイドに従う

### 参照元
- `CLAUDE.md` — Claude Code 開発ガイドライン
- `AGENTS.md` — 全AI エージェント共通ルール
- `docs/spec/001-card-speech-bugfix/requirements.md` — 要件定義
- `docs/design/001-card-speech-bugfix/architecture.md` — 設計文書

---

## 3. 関連実装

### useSpeech hook（契約維持）
**ファイル**: `frontend/src/hooks/useSpeech.ts`

```typescript
// useSpeech の仕様
interface UseSpeechReturn {
  isSpeaking: boolean;    // 現在発話中かどうか
  isSupported: boolean;   // Web Speech API が利用可能か
  speak: (text: string) => void;  // 読み上げ開始（発話中なら cancel→re-speak）
  cancel: () => void;     // 読み上げ停止
}

// 重要: speak() は内部で cancel() してから再発話するため、
// 異なるテキストへの切り替えは機能するが、
// 同じテキストの読み上げ中に speak() を呼ぶと再開される（停止しない）
```

**テストカバレッジ**: 100% （Vitest 確認済み）

### FlipCard コンポーネント（契約維持）
**ファイル**: `frontend/src/components/FlipCard.tsx`

```typescript
export interface FlipCardSpeechProps {
  speechState: {
    isSpeaking: boolean;
    isSupported: boolean;
  };
  onSpeakFront: () => void;  // 表面ボタンクリック時のコールバック
  onSpeakBack: () => void;   // 裏面ボタンクリック時のコールバック
}

// 注: speechProps? はオプショナル（後方互換）
// speechProps なしの場合、読み上げボタンは表示されない
```

**テストパターン**:
- `frontend/src/components/__tests__/FlipCard.test.tsx` — 230行
- SpeechButton のクリックコールバック検証が実装済み
- onSpeakFront/onSpeakBack の呼び出しテストがある

### ReviewPage ページコンポーネント（修正対象）
**ファイル**: `frontend/src/pages/ReviewPage.tsx`

**修正箇所**: 3箇所の speechProps 定義

1. **通常モード（L664-667）**: currentCard を使用
   ```typescript
   // 修正前
   speechProps={{
     speechState: { isSpeaking, isSupported },
     onSpeakFront: () => speak(currentCard.front),
     onSpeakBack: () => speak(currentCard.back),
   }}

   // 修正後
   speechProps={{
     speechState: { isSpeaking, isSupported },
     onSpeakFront: () => (isSpeaking ? cancel() : speak(currentCard.front)),
     onSpeakBack: () => (isSpeaking ? cancel() : speak(currentCard.back)),
   }}
   ```

2. **再採点モード（L534-537）**: regradeCard を使用
   ```typescript
   // 同様に isSpeaking 判定を追加
   onSpeakFront: () => (isSpeaking ? cancel() : speak(regradeCard.front)),
   onSpeakBack: () => (isSpeaking ? cancel() : speak(regradeCard.back)),
   ```

3. **再確認モード（L601-604）**: reconfirmCard を使用
   ```typescript
   // 同様に isSpeaking 判定を追加
   onSpeakFront: () => (isSpeaking ? cancel() : speak(reconfirmCard.front)),
   onSpeakBack: () => (isSpeaking ? cancel() : speak(reconfirmCard.back)),
   ```

**参照元**: `docs/design/001-card-speech-bugfix/architecture.md` REQ-001

---

## 4. 設計文書

### REQ-001: 停止トグル修正
**信頼性レベル**: 🔵 青信号（spec.md US1 + architecture.md より確実）

**現状の問題**:
- ReviewPage の onSpeakFront/onSpeakBack が常に speak() を呼ぶ
- useSpeech.speak() は内部で cancel()→re-speak するため、停止にならない
- SpeechButton は isSpeaking を表示するが、コールバックが正しく機能していない

**修正方針**:
- ReviewPage 側でコールバック生成時に isSpeaking 状態を参照
- 発話中なら cancel() を呼び、停止中なら speak() を呼ぶ
- useSpeech, FlipCardSpeechProps の契約は変更しない

**設計判断**:
- 修正は ReviewPage のコールバック定義のみ（呼び出し側の責任）
- 3箇所すべて修正し、モード間で漏れがないようにする

**参照元**: `docs/design/001-card-speech-bugfix/architecture.md`

### データフロー
```
ReviewPage.isSpeaking
  ↓
onSpeakFront/onSpeakBack コールバック生成時に判定
  ↓
isSpeaking ? cancel() : speak(text)
  ↓
useSpeech.cancel() / useSpeech.speak()
  ↓
useSpeech hook で isSpeaking 状態更新
  ↓
SpeechButton に反映（ボタンアイコン・aria-label 変化）
```

**参照元**: `docs/design/001-card-speech-bugfix/dataflow.md`

---

## 5. テスト戦略

### テスト対象
**信頼性レベル**: 🔵 青信号（REQ-103(a) より）

停止トグル動作の統合テストが必要：
1. 表面読み上げ中にボタンタップ → cancel() が呼ばれる（speak() ではない）
2. 裏面読み上げ中にボタンタップ → cancel() が呼ばれる
3. 停止後に再タップ → speak() が呼ばれる

### テストファイル戦略

**Option A: FlipCard.test.tsx に追加**（推奨）
- 既に FlipCard のテストパターンが確立
- speechProps.onSpeakFront/onSpeakBack のコールバック検証が可能
- モック化した useSpeech を使用してカバレッジ検証可能

**Option B: ReviewPage.test.tsx に追加**
- ReviewPage の統合テスト（より複雑）
- API モックが必要（DueCard の取得など）

### 既存テストパターン

**FlipCard.test.tsx** (230行):
```typescript
// 既存パターン
it("表面の読み上げボタンをクリックすると onSpeakFront が呼ばれる", async () => {
  const onSpeakFront = vi.fn();
  renderFlipCard({
    isFlipped: false,
    speechProps: makeSpeechProps({ onSpeakFront }),
  });
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "表面を読み上げ" }));
  expect(onSpeakFront).toHaveBeenCalledTimes(1);
});

// 停止トグルテスト（追加予定）
// isSpeaking=true のとき、cancel() を呼ぶべき
// isSpeaking=false のとき、speak() を呼ぶべき
```

**ReviewPage.test.tsx** (200+ 行):
- ローディング表示、カード表示、フリップ操作、採点送信など
- API モックが確立済み
- 統合テストパターンが整備済み

**ReviewPage.integration.test.tsx**:
- 統合テストの別ファイル（必要に応じて活用）

### テストカバレッジ目標
- **現状**: useSpeech, useSpeechSettings, SpeechButton で 100% 達成済み
- **目標**: ReviewPage の修正後も 80% 以上を維持
- **確認**: `npm run test -- --coverage` で検証

**参照元**:
- `frontend/src/components/__tests__/FlipCard.test.tsx`
- `frontend/src/pages/__tests__/ReviewPage.test.tsx`
- `frontend/src/hooks/__tests__/useSpeech.test.ts`

---

## 6. 完了条件チェックリスト

**タスクファイル**: `docs/tasks/001-card-speech-bugfix/TASK-0149.md`

- [ ] 通常モードの speechProps で isSpeaking 判定が追加されている
- [ ] 再採点モードの speechProps で isSpeaking 判定が追加されている
- [ ] 再確認モードの speechProps で isSpeaking 判定が追加されている
- [ ] 停止トグル動作の統合テストが追加され、パスしている
- [ ] 既存テストがすべてパスしている

### 実装手順

1. `/tsumiki:tdd-red` — 停止トグル統合テストを追加（失敗）
   - FlipCard.test.tsx または ReviewPage.test.tsx にテストを追加
   - isSpeaking=true のとき cancel() が呼ばれることを検証

2. `/tsumiki:tdd-green` — ReviewPage の speechProps 修正（3箇所）
   - 通常モード（L664-667）
   - 再採点モード（L534-537）
   - 再確認モード（L601-604）

3. `/tsumiki:tdd-refactor` — リファクタリング（必要に応じて）
   - コードの重複がないか確認
   - テスト有効性の確認

4. `/tsumiki:tdd-verify-complete` — 全テストパス確認
   - `npm run test` で全テスト実行
   - `npm run test -- --coverage` でカバレッジ確認（80%以上）

---

## 7. 注意事項

### 契約維持（重要）
- ✅ `useSpeech` hook 自体は変更しない
- ✅ `FlipCardSpeechProps` インターフェースは変更しない
- ✅ SpeechButton コンポーネントは変更しない
- 🔴 修正は ReviewPage のコールバック定義のみ

### 3箇所修正の漏れ防止
```
1. 通常モード（L664-667）: currentCard
2. 再採点モード（L534-537）: regradeCard
3. 再確認モード（L601-604）: reconfirmCard
```

全モードで同じパターンを適用：
```typescript
onSpeakFront: () => (isSpeaking ? cancel() : speak(cardVariable.front)),
onSpeakBack: () => (isSpeaking ? cancel() : speak(cardVariable.back)),
```

### テスト実行コマンド
```bash
cd frontend

# 全テスト実行
npm run test

# FlipCard/ReviewPage のテストのみ
npm run test FlipCard.test
npm run test ReviewPage.test

# カバレッジ確認
npm run test -- --coverage
```

---

## 8. 関連文書

### 要件定義
- `docs/spec/001-card-speech-bugfix/requirements.md` — REQ-001, REQ-103(a)
- `docs/spec/001-card-speech-bugfix/interview-record.md` — ヒアリング記録

### 設計文書
- `docs/design/001-card-speech-bugfix/architecture.md` — REQ-001 の設計方針
- `docs/design/001-card-speech-bugfix/dataflow.md` — データフロー図

### 元仕様・契約
- `specs/001-card-speech/spec.md` — US1 Acceptance Scenario 3
- `specs/001-card-speech/contracts/hooks.md` — useSpeech 契約
- `specs/001-card-speech/contracts/components.md` — FlipCard 契約

### タスクファイル
- `docs/tasks/001-card-speech-bugfix/TASK-0149.md` — このタスク

### 関連タスク（同一フェーズ）
- TASK-0150: useSpeechSettings の userId 遅延確定対応
- TASK-0151: SettingsPage の aria-label 追加
- TASK-0152: useSpeechSettings の localStorage.setItem 例外処理

---

## 信頼性レベルサマリー

| 項目 | レベル | 参照元 |
|------|--------|---------|
| REQ-001 設計方針 | 🔵 青 | spec.md US1 + architecture.md |
| 3箇所修正パターン | 🔵 青 | architecture.md REQ-001 設計方針 |
| 停止トグルテスト要件 | 🔵 青 | REQ-103(a) + spec.md |
| テスト戦略 | 🔵 青 | FlipCard.test.tsx 既存パターン |
| 契約維持ルール | 🔵 青 | contracts/hooks.md, contracts/components.md |

**品質評価**: ✅ 高品質（青信号 100%）

---

**ノート完成日**: 2026-03-05
**次のステップ**: `/tsumiki:tdd-red` を実行してテストを追加

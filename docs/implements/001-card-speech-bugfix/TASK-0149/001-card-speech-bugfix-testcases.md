# テストケース: ReviewPage 停止トグル修正

**機能名**: 001-card-speech-bugfix
**タスクID**: TASK-0149
**要件名**: ReviewPage 停止トグル修正
**出力ファイル名**: `docs/implements/001-card-speech-bugfix/TASK-0149/001-card-speech-bugfix-testcases.md`

---

## 1. 正常系テストケース（基本的な動作）

### TC-001: 通常モード - 表面読み上げ中にボタンクリックで cancel() が呼ばれる

- **テスト名**: 通常モード: 表面読み上げ中にボタンをクリックすると cancel() が呼ばれ、speak() は呼ばれない
  - **何をテストするか**: isSpeaking=true の状態で表面の読み上げボタンをクリックしたとき、ReviewPage が生成する onSpeakFront コールバックが cancel() を呼ぶこと
  - **期待される動作**: speak() ではなく cancel() が呼ばれ、読み上げが停止する
- **入力値**: isSpeaking=true, isSupported=true, カード表面テキスト「質問1」
  - **入力データの意味**: 発話中の状態を再現し、停止トグル動作を検証する
- **期待される結果**: cancel() が1回呼ばれ、speak() は呼ばれない
  - **期待結果の理由**: REQ-001 により、発話中にボタンをクリックすると停止すべき
- **テストの目的**: 停止トグルの主要なバグ修正が正しく動作することを確認
  - **確認ポイント**: onSpeakFront コールバック内で isSpeaking 判定が正しく機能していること
- 🔵 **青信号**: TASK-0149.md の完了条件 + architecture.md REQ-001 設計方針に基づく

### TC-002: 通常モード - 裏面読み上げ中にボタンクリックで cancel() が呼ばれる

- **テスト名**: 通常モード: 裏面読み上げ中にボタンをクリックすると cancel() が呼ばれ、speak() は呼ばれない
  - **何をテストするか**: isSpeaking=true の状態で裏面の読み上げボタンをクリックしたとき、ReviewPage が生成する onSpeakBack コールバックが cancel() を呼ぶこと
  - **期待される動作**: speak() ではなく cancel() が呼ばれ、読み上げが停止する
- **入力値**: isSpeaking=true, isSupported=true, isFlipped=true, カード裏面テキスト「解答1」
  - **入力データの意味**: 発話中の裏面表示状態を再現する
- **期待される結果**: cancel() が1回呼ばれ、speak() は呼ばれない
  - **期待結果の理由**: REQ-001 により、裏面でも停止トグル動作は同一であるべき
- **テストの目的**: 裏面でも停止トグルが正しく動作することを確認
  - **確認ポイント**: onSpeakBack コールバック内で isSpeaking 判定が正しく機能していること
- 🔵 **青信号**: TASK-0149.md 完了条件 + architecture.md REQ-001 より

### TC-003: 通常モード - 停止中にボタンクリックで speak() が呼ばれる

- **テスト名**: 通常モード: 停止中にボタンをクリックすると speak(text) が呼ばれ、cancel() は呼ばれない
  - **何をテストするか**: isSpeaking=false の状態で表面の読み上げボタンをクリックしたとき、speak(text) が呼ばれること
  - **期待される動作**: cancel() ではなく speak(currentCard.front) が呼ばれる
- **入力値**: isSpeaking=false, isSupported=true, カード表面テキスト「質問1」
  - **入力データの意味**: 停止中の状態から読み上げを再開するシナリオ
- **期待される結果**: speak() が「質問1」を引数に呼ばれ、cancel() は呼ばれない
  - **期待結果の理由**: 停止中のボタンクリックは新規読み上げ開始であるべき
- **テストの目的**: 停止→再生のトグル動作が正しく機能することを確認
  - **確認ポイント**: isSpeaking=false のときに speak() が正しいテキストで呼ばれること
- 🔵 **青信号**: TASK-0149.md 基本テスト要件「停止後に再タップ → speak() が呼ばれる」より

### TC-004: 再採点モード - 読み上げ中にボタンクリックで cancel() が呼ばれる

- **テスト名**: 再採点モード: 読み上げ中にボタンをクリックすると cancel() が呼ばれる
  - **何をテストするか**: 再採点モード（regradeCardIndex !== null）の speechProps で isSpeaking 判定が追加されていること
  - **期待される動作**: 再採点モードでも isSpeaking=true のとき cancel() が呼ばれる
- **入力値**: isSpeaking=true, isSupported=true, 再採点モードのカード表面テキスト
  - **入力データの意味**: Undo 後の再採点状態で発話中にボタンをクリックするシナリオ
- **期待される結果**: cancel() が1回呼ばれ、speak() は呼ばれない
  - **期待結果の理由**: TASK-0149 完了条件「再採点モードの speechProps で isSpeaking 判定が追加されている」
- **テストの目的**: 3箇所の修正のうち再採点モードが正しく修正されていることを確認
  - **確認ポイント**: regradeCard を使用する speechProps でも停止トグルが機能すること
- 🟡 **黄信号**: TASK-0149 完了条件に明記されているが、再採点モードのテスト実装は ReviewPage レベルの複雑なセットアップが必要で、テスト方法は推測を含む

### TC-005: 再確認モード - 読み上げ中にボタンクリックで cancel() が呼ばれる

- **テスト名**: 再確認モード: 読み上げ中にボタンをクリックすると cancel() が呼ばれる
  - **何をテストするか**: 再確認モード（isReconfirmMode && reconfirmQueue.length > 0）の speechProps で isSpeaking 判定が追加されていること
  - **期待される動作**: 再確認モードでも isSpeaking=true のとき cancel() が呼ばれる
- **入力値**: isSpeaking=true, isSupported=true, 再確認モードのカード表面テキスト
  - **入力データの意味**: 再確認キュー表示中に発話中にボタンをクリックするシナリオ
- **期待される結果**: cancel() が1回呼ばれ、speak() は呼ばれない
  - **期待結果の理由**: TASK-0149 完了条件「再確認モードの speechProps で isSpeaking 判定が追加されている」
- **テストの目的**: 3箇所の修正のうち再確認モードが正しく修正されていることを確認
  - **確認ポイント**: reconfirmCard を使用する speechProps でも停止トグルが機能すること
- 🟡 **黄信号**: TASK-0149 完了条件に明記されているが、再確認モードのテスト実装は ReviewPage レベルの複雑なセットアップが必要で、テスト方法は推測を含む

---

## 2. 異常系テストケース（エラーハンドリング）

### TC-006: isSupported=false のとき読み上げボタンが表示されない（既存動作維持）

- **テスト名**: Web Speech API が非対応のとき読み上げボタンが表示されない
  - **エラーケースの概要**: ブラウザが Web Speech API をサポートしていない場合
  - **エラー処理の重要性**: SpeechButton は isSupported=true のときのみ表示されるため、この条件下ではトグル問題自体が発生しない
- **入力値**: isSupported=false, isSpeaking=false
  - **不正な理由**: API 非対応は不正ではないが、ボタン非表示の確認は回帰テストとして重要
  - **実際の発生シナリオ**: 一部のブラウザ（SSR環境やテキストブラウザ）で発生
- **期待される結果**: 読み上げボタンが DOM に存在しない
  - **エラーメッセージの内容**: なし（ボタン非表示のみ）
  - **システムの安全性**: 安全（機能自体が非表示）
- **テストの目的**: 既存の後方互換テストが修正後も維持されることを確認
  - **品質保証の観点**: 回帰テストとして既存動作を保証
- 🔵 **青信号**: FlipCard.test.tsx の既存テスト「isSupported=false の場合、読み上げボタンが表示されない」と同一パターン

---

## 3. 境界値テストケース（最小値、最大値、null等）

### TC-007: isSpeaking が false → true → false とトグルする完全サイクル

- **テスト名**: 停止→再生→停止の完全トグルサイクルが正しく動作する
  - **境界値の意味**: isSpeaking の boolean 状態遷移の境界。false→true（再生開始）と true→false（停止）の両方を1シナリオで検証
  - **境界値での動作保証**: 連続操作でも状態が正しく遷移すること
- **入力値**: 初回クリック（isSpeaking=false）→ isSpeaking を true にモック更新 → 2回目クリック（isSpeaking=true）
  - **境界値選択の根拠**: トグルの状態遷移は2値のため、両方の遷移を1テストで検証
  - **実際の使用場面**: ユーザーが「再生→停止」を繰り返す一般的な操作
- **期待される結果**: 1回目で speak() が呼ばれ、2回目で cancel() が呼ばれる
  - **境界での正確性**: isSpeaking の値に応じて正しい関数が呼ばれること
  - **一貫した動作**: 何度トグルしても isSpeaking に基づく判定が一貫していること
- **テストの目的**: トグル動作の一貫性を確認
  - **堅牢性の確認**: 連続操作で状態が破綻しないこと
- 🟡 **黄信号**: TASK-0149 の要件から妥当な推測。useSpeech モックの再レンダリング制御が必要なため実装方法に推測を含む

---

## 4. 開発言語・フレームワーク

- **プログラミング言語**: TypeScript 5.x
  - **言語選択の理由**: プロジェクトのフロントエンドは React + TypeScript で統一されている
  - **テストに適した機能**: 型安全なモック定義、vi.fn() の型推論
- **テストフレームワーク**: Vitest + React Testing Library + @testing-library/user-event
  - **フレームワーク選択の理由**: プロジェクト既存のテスト環境。FlipCard.test.tsx, ReviewPage.test.tsx で確立済み
  - **テスト実行環境**: `cd frontend && npm run test`
- 🔵 **青信号**: note.md 技術スタック + 既存テストファイルより確実

---

## 5. テストケース実装時の日本語コメント指針

### テスト対象ファイル

`frontend/src/pages/__tests__/ReviewPage.test.tsx` に追加

### モック戦略

useSpeech hook をモックし、`isSpeaking`, `speak`, `cancel` を制御可能にする。
useAuth, useSpeechSettings もモックが必要（ReviewPage が使用するため）。

```typescript
// 【テスト前準備】: useSpeech hook のモック
const mockSpeak = vi.fn();
const mockCancel = vi.fn();
let mockIsSpeaking = false;

vi.mock('@/hooks/useSpeech', () => ({
  useSpeech: () => ({
    isSpeaking: mockIsSpeaking,
    isSupported: true,
    speak: mockSpeak,
    cancel: mockCancel,
  }),
}));

// 【テスト前準備】: useAuth hook のモック
vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({
    user: { profile: { sub: 'test-user' } },
  }),
}));

// 【テスト前準備】: useSpeechSettings hook のモック
vi.mock('@/hooks/useSpeechSettings', () => ({
  useSpeechSettings: () => ({
    settings: { autoPlay: false, rate: 1 },
    updateSettings: vi.fn(),
  }),
}));
```

### テストケース開始時のコメント

```typescript
// 【テスト目的】: ReviewPage の停止トグル修正が正しく動作することを確認
// 【テスト内容】: isSpeaking=true のとき cancel() が呼ばれ、isSpeaking=false のとき speak() が呼ばれることを検証
// 【期待される動作】: ボタンクリック時に isSpeaking 状態に応じた正しい関数が呼ばれる
// 🔵 青信号: TASK-0149 完了条件 + architecture.md REQ-001 より
```

### Given（準備フェーズ）のコメント

```typescript
// 【テストデータ準備】: useSpeech のモック状態を設定（isSpeaking=true で発話中を再現）
// 【初期条件設定】: API モックで DueCard を返却し、カード表示状態にする
// 【前提条件確認】: isSupported=true で SpeechButton が表示されること
```

### When（実行フェーズ）のコメント

```typescript
// 【実際の処理実行】: 表面の読み上げボタンをクリック（aria-label で特定）
// 【処理内容】: SpeechButton の onClick → FlipCard の onSpeakFront → ReviewPage のコールバック実行
// 【実行タイミング】: カード表示後、isSpeaking=true の状態でクリック
```

### Then（検証フェーズ）のコメント

```typescript
// 【結果検証】: cancel() が呼ばれたことを確認
// 【期待値確認】: speak() が呼ばれていないことを確認（停止トグルの核心）
// 【品質保証】: REQ-001 の受け入れ基準を満たすことを保証

// 【検証項目】: cancel() が1回呼ばれたこと
// 🔵 青信号
expect(mockCancel).toHaveBeenCalledTimes(1);

// 【検証項目】: speak() が呼ばれていないこと（autoPlay による呼び出しを除く）
// 🔵 青信号
expect(mockSpeak).not.toHaveBeenCalled();
```

### セットアップ・クリーンアップのコメント

```typescript
beforeEach(() => {
  // 【テスト前準備】: モック関数をリセットし、デフォルト状態に戻す
  // 【環境初期化】: mockIsSpeaking を false に、API モックを正常レスポンスに設定
  vi.clearAllMocks();
  mockIsSpeaking = false;
});
```

---

## 6. 要件定義との対応関係

- **参照した機能概要**: `docs/design/001-card-speech-bugfix/architecture.md` REQ-001 — 停止トグル修正
- **参照した入力・出力仕様**: `docs/tasks/001-card-speech-bugfix/TASK-0149.md` — 修正前後のコード例（speechProps の onSpeakFront/onSpeakBack）
- **参照した制約条件**: `docs/implements/001-card-speech-bugfix/TASK-0149/note.md` — 契約維持（useSpeech, FlipCardSpeechProps 変更不可）
- **参照した使用例**: `docs/design/001-card-speech-bugfix/architecture.md` REQ-103(a) — 停止トグル統合テスト仕様

---

## テストケースサマリー

| ID | テスト名 | 分類 | 信頼性 |
|----|----------|------|--------|
| TC-001 | 通常モード: 表面読み上げ中 → cancel() | 正常系 | 🔵 |
| TC-002 | 通常モード: 裏面読み上げ中 → cancel() | 正常系 | 🔵 |
| TC-003 | 通常モード: 停止中 → speak(text) | 正常系 | 🔵 |
| TC-004 | 再採点モード: 読み上げ中 → cancel() | 正常系 | 🟡 |
| TC-005 | 再確認モード: 読み上げ中 → cancel() | 正常系 | 🟡 |
| TC-006 | isSupported=false → ボタン非表示 | 異常系 | 🔵 |
| TC-007 | 停止→再生→停止の完全トグルサイクル | 境界値 | 🟡 |

---

## 信頼性レベルサマリー

- **総項目数**: 7項目
- 🔵 **青信号**: 4項目 (57%)
- 🟡 **黄信号**: 3項目 (43%)
- 🔴 **赤信号**: 0項目 (0%)

**品質評価**: ✅ 高品質

**補足**: 黄信号のテストケース（TC-004, TC-005, TC-007）は要件として明確だが、ReviewPage の複雑な状態遷移（Undo→再採点、再確認キュー）のテストセットアップに推測を含む。Red フェーズで実装可否を検証する。

---

## 実装優先度

1. **必須（Red フェーズで実装）**: TC-001, TC-002, TC-003 — 停止トグルの核心テスト
2. **推奨（可能であれば実装）**: TC-004, TC-005 — 再採点・再確認モードの網羅
3. **補助（回帰テスト確認）**: TC-006 — 既存テストで担保済みの可能性あり
4. **追加（余裕があれば）**: TC-007 — 完全トグルサイクルの統合テスト

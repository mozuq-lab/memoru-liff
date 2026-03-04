# テストケース定義: useSpeechSettings hook バグ修正

**機能名**: useSpeechSettings hook バグ修正（userId 遅延対応 + localStorage 例外処理）
**タスクID**: TASK-0148
**要件名**: 001-card-speech-bugfix
**出力ファイル**: `docs/implements/001-card-speech-bugfix/TASK-0148/usespeechsettings-bugfix-testcases.md`

---

## 1. 正常系テストケース（基本的な動作）

### TC-001: userId が undefined から有効値に変化したとき、保存済み設定が読み込まれる

- **テスト名**: userId 遅延確定時の設定再読み込み
  - **何をテストするか**: `useEffect([userId])` により、userId が undefined から有効な文字列に変化した際に `loadSettings` が実行され、localStorage に保存された設定が state に反映されること
  - **期待される動作**: renderHook で userId=undefined で初期化 → rerender で userId="test-user-123" に変更 → localStorage から保存済み設定が読み込まれる
- **入力値**:
  - 初回: `userId = undefined`
  - rerender: `userId = "test-user-123"`
  - localStorage に `speech-settings:test-user-123` = `{ autoPlay: true, rate: 1.5 }` を事前セット
  - **入力データの意味**: LIFF SDK / OIDC 認証が非同期で完了するため、初回レンダリング時に userId が undefined で、認証完了後に有効値に変化するパターンを再現
- **期待される結果**:
  - rerender 後の `settings` が `{ autoPlay: true, rate: 1.5 }` になる
  - **期待結果の理由**: useEffect([userId]) が userId の変化を検知し、loadSettings を再実行して localStorage から設定を読み込むため
- **テストの目的**: REQ-002 の受け入れ基準を検証
  - **確認ポイント**: rerender 前はデフォルト設定、rerender 後は保存済み設定に切り替わること
- 🔵 **青信号**: REQ-002 受け入れ基準 + architecture.md の設計方針に基づく

### TC-002: userId が最初から有効な場合、初期化時に正しく読み込まれる（既存動作維持）

- **テスト名**: userId 初期有効時の設定読み込み（冪等性確認）
  - **何をテストするか**: userId が最初から有効な場合、useState 初期化で loadSettings が実行され、追加される useEffect も同じ値で上書きする（冪等）ため、既存動作が維持されること
  - **期待される動作**: renderHook で userId="test-user-123" で初期化 → 保存済み設定が即座に反映される
- **入力値**:
  - `userId = "test-user-123"`
  - localStorage に `speech-settings:test-user-123` = `{ autoPlay: true, rate: 0.5 }` を事前セット
  - **入力データの意味**: 認証が同期的に完了している（または既にキャッシュされている）パターン。既存テストケースと同等だが、useEffect 追加後も動作が変わらないことの確認
- **期待される結果**:
  - `settings` が `{ autoPlay: true, rate: 0.5 }` になる
  - **期待結果の理由**: useState 初期化関数で loadSettings が呼ばれ、useEffect は同じ値で上書きするため結果は同じ
- **テストの目的**: useEffect 追加による既存動作への影響がないことを確認（REQ-401 既存テスト維持）
  - **確認ポイント**: 初回レンダリングから正しい設定が反映されていること
- 🔵 **青信号**: 既存テストパターン + architecture.md 冪等性の記述に基づく

### TC-003: userId が undefined のまま変化しない場合、デフォルト設定のまま

- **テスト名**: userId 未確定時のデフォルト設定維持
  - **何をテストするか**: userId が undefined のまま変化しない場合、useEffect が追加されてもデフォルト設定が維持されること
  - **期待される動作**: renderHook で userId=undefined で初期化 → 設定がデフォルト値のまま
- **入力値**:
  - `userId = undefined`（変化なし）
  - **入力データの意味**: 認証が完了していない状態が継続するケース（ゲストユーザー、認証エラー等）
- **期待される結果**:
  - `settings` が `{ autoPlay: false, rate: 1 }`（DEFAULT_SETTINGS）のまま
  - **期待結果の理由**: userId が undefined のため useState 初期化でデフォルト値が設定され、useEffect も userId が falsy のため loadSettings を呼ばない
- **テストの目的**: useEffect 追加による副作用がないことを確認
  - **確認ポイント**: localStorage.getItem が呼ばれていないこと（不要な読み込みが発生しないこと）
- 🔵 **青信号**: REQ-002 設計 + 既存テストパターンに基づく

---

## 2. 異常系テストケース（エラーハンドリング）

### TC-004: localStorage.setItem が throw しても state が更新される

- **テスト名**: localStorage.setItem 例外時の state 更新保証
  - **エラーケースの概要**: `localStorage.setItem` が `QuotaExceededError` 等の例外を throw する状況で、React state の更新は正常に行われること
  - **エラー処理の重要性**: Safari Private Mode や容量超過時にアプリの設定変更機能が完全に失われないようにする
- **入力値**:
  - `userId = "test-user-123"`
  - `localStorage.setItem` を `vi.mocked(localStorage.setItem).mockImplementation(() => { throw new Error("QuotaExceededError"); })` でモック
  - `updateSettings({ autoPlay: true })` を呼び出し
  - **不正な理由**: localStorage の書き込み容量制限を超えた場合、またはプライベートブラウジングモードで書き込みが禁止されている場合
  - **実際の発生シナリオ**: Safari Private Mode でアプリを使用した場合、または大量のデータが localStorage に保存されている場合
- **期待される結果**:
  - `settings.autoPlay` が `true` に更新されている
  - **エラーメッセージの内容**: エラーメッセージは不要（catch で黙殺）
  - **システムの安全性**: state は更新されるため、セッション中は変更後の設定が有効。localStorage への永続化のみ失敗する
- **テストの目的**: REQ-102 の受け入れ基準を検証
  - **品質保証の観点**: localStorage が使用不可な環境でもアプリが正常に動作し続けること
- 🟡 **黄信号**: REQ-102 受け入れ基準 + loadSettings 側の既存 try/catch パターンからの妥当な推測

### TC-005: localStorage.setItem が throw してもエラーがスローされない

- **テスト名**: localStorage.setItem 例外時のエラー非伝播
  - **エラーケースの概要**: `localStorage.setItem` が例外を throw しても、`updateSettings` 呼び出し元にエラーが伝播しないこと（アプリがクラッシュしないこと）
  - **エラー処理の重要性**: 未処理例外が React のエラーバウンダリまで伝播してUIが壊れることを防止する
- **入力値**:
  - `userId = "test-user-123"`
  - `localStorage.setItem` を `vi.mocked(localStorage.setItem).mockImplementation(() => { throw new Error("QuotaExceededError"); })` でモック
  - `updateSettings({ rate: 1.5 })` を `act` 内で呼び出し
  - **不正な理由**: TC-004 と同じ（localStorage 書き込み不可環境）
  - **実際の発生シナリオ**: TC-004 と同じ
- **期待される結果**:
  - `expect(() => { act(() => { result.current.updateSettings({ rate: 1.5 }) }) }).not.toThrow()`
  - **エラーメッセージの内容**: エラーは catch されるため、コンソールにも出力されない
  - **システムの安全性**: try/catch により例外が抑制され、React のレンダリングサイクルに影響しない
- **テストの目的**: REQ-102 の受け入れ基準（エラー非伝播）を検証
  - **品質保証の観点**: 例外がアプリケーション全体のクラッシュにつながらないこと
- 🟡 **黄信号**: REQ-102 受け入れ基準 + loadSettings 側の既存 try/catch パターンからの妥当な推測

---

## 3. 境界値テストケース（最小値、最大値、null等）

本タスク（TASK-0148）の修正範囲は userId の遅延確定と localStorage.setItem の例外処理に限定されるため、SpeechRate の境界値（0.5, 1, 1.5）やデータ形式の境界値は既存テストで十分にカバーされている。新規の境界値テストケースは不要と判断。

既存カバレッジ:
- rate 不正値（99）→ デフォルトフォールバック: 既存テスト「localStorage の rate が不正値の場合」
- autoPlay 非 boolean → デフォルトフォールバック: 既存テスト「localStorage の autoPlay が boolean でない場合」
- JSON parse エラー → デフォルトフォールバック: 既存テスト「localStorage の値が JSON parse エラーの場合」

---

## 4. 開発言語・フレームワーク

- **プログラミング言語**: TypeScript 5.x
  - **言語選択の理由**: プロジェクト全体で TypeScript を採用しており、型安全性が求められるため
  - **テストに適した機能**: 型チェックによるテストデータの正確性保証、IDE の補完支援
- **テストフレームワーク**: Vitest + React Testing Library (`renderHook`, `act`)
  - **フレームワーク選択の理由**: プロジェクト標準のテストフレームワーク。既存テストもすべて Vitest で記述されている
  - **テスト実行環境**: `npm run test`（Vitest、jsdom 環境）。localStorage は `frontend/src/test/setup.ts` で `vi.fn()` モックに置き換え済み
- 🔵 **青信号**: CLAUDE.md + note.md + 既存テストファイルに基づく

---

## 5. テストケース実装時の日本語コメント指針

### describe ブロック構成

```typescript
// 既存の describe("useSpeechSettings") 内に以下の2ブロックを追加

describe("userId 遅延確定 (REQ-002)", () => {
  // TC-001, TC-002, TC-003
});

describe("localStorage.setItem 例外処理 (REQ-102)", () => {
  // TC-004, TC-005
});
```

### TC-001 実装時コメント例

```typescript
it("userId が undefined → 有効値に変化したとき、保存済み設定が読み込まれる", () => {
  // 【テスト目的】: useEffect([userId]) による遅延読み込みの動作確認
  // 【テスト内容】: userId を undefined → "test-user-123" に rerender し、localStorage の設定が反映されるか検証
  // 【期待される動作】: rerender 後に保存済みの { autoPlay: true, rate: 1.5 } が settings に反映される
  // 🔵 REQ-002 受け入れ基準に基づく

  // 【テストデータ準備】: localStorage に保存済み設定をセットアップ
  const saved: SpeechSettings = { autoPlay: true, rate: 1.5 };
  vi.mocked(localStorage.getItem).mockReturnValue(JSON.stringify(saved));

  // 【初期条件設定】: userId=undefined で hook を初期化
  const { result, rerender } = renderHook(
    ({ userId }) => useSpeechSettings(userId),
    { initialProps: { userId: undefined as string | undefined } }
  );

  // 【前提条件確認】: 初期状態はデフォルト設定
  // 【検証項目】: userId=undefined 時はデフォルト設定が適用される
  expect(result.current.settings).toEqual({ autoPlay: false, rate: 1 });

  // 【実際の処理実行】: userId を有効値に変更して rerender
  // 【処理内容】: useEffect([userId]) が発火し、loadSettings を実行する
  rerender({ userId: "test-user-123" });

  // 【結果検証】: localStorage から保存済み設定が読み込まれた
  // 【期待値確認】: autoPlay: true, rate: 1.5 が反映されていること
  // 【検証項目】: useEffect による遅延読み込みが正しく動作する 🔵
  expect(result.current.settings).toEqual(saved);
});
```

### TC-004 実装時コメント例

```typescript
it("localStorage.setItem が throw しても state が更新される", () => {
  // 【テスト目的】: try/catch による localStorage 例外時の state 更新保証
  // 【テスト内容】: setItem が QuotaExceededError を throw する状態で updateSettings を呼び、state が更新されるか検証
  // 【期待される動作】: 例外発生時でも settings.autoPlay が true に更新される
  // 🟡 REQ-102 受け入れ基準 + loadSettings パターンからの推測

  // 【テストデータ準備】: setItem を例外を throw するモックに設定
  vi.mocked(localStorage.setItem).mockImplementation(() => {
    throw new Error("QuotaExceededError");
  });

  // 【初期条件設定】: userId 有効状態で hook を初期化
  const { result } = renderHook(() => useSpeechSettings("test-user-123"));

  // 【実際の処理実行】: updateSettings で autoPlay を true に変更
  // 【処理内容】: setItem は throw するが、try/catch で抑制されるはず
  act(() => {
    result.current.updateSettings({ autoPlay: true });
  });

  // 【結果検証】: state は正常に更新されている
  // 【検証項目】: localStorage 例外時でも state 更新が保証される 🟡
  expect(result.current.settings.autoPlay).toBe(true);
});
```

### セットアップ・クリーンアップ

```typescript
beforeEach(() => {
  // 【テスト前準備】: localStorage モックの呼び出し履歴をリセット
  // 【環境初期化】: 前のテストの localStorage 操作が影響しないようにする
  vi.mocked(localStorage.getItem).mockReset();
  vi.mocked(localStorage.setItem).mockReset();
  vi.mocked(localStorage.removeItem).mockReset();
});

afterEach(() => {
  // 【テスト後処理】: すべてのモックを元の状態に復元
  // 【状態復元】: vi.spyOn 等で追加したモックを確実にクリーンアップ
  vi.restoreAllMocks();
});
```

---

## 6. 要件定義との対応関係

- **参照した機能概要**: usespeechsettings-bugfix-requirements.md セクション 1（機能の概要）
- **参照した入力・出力仕様**: usespeechsettings-bugfix-requirements.md セクション 2（入力・出力の仕様 + データフロー）
- **参照した制約条件**: usespeechsettings-bugfix-requirements.md セクション 3（既存テスト維持、インターフェース不変、冪等性、localStorage 例外の黙殺）
- **参照した使用例**: usespeechsettings-bugfix-requirements.md セクション 4（userId 遅延確定テスト一覧 + localStorage 例外テスト一覧）
- **参照した設計文書**: architecture.md REQ-002（useEffect 設計方針）、REQ-102（try/catch 設計方針）、REQ-103(b)（テスト設計）
- **参照したタスク定義**: TASK-0148.md 完了条件 + 基本的なテスト要件

### テストケースと要件の対応表

| テストケース | 要件 | 信頼性 |
|---|---|---|
| TC-001: userId 遅延確定時の設定再読み込み | REQ-002, REQ-103(b) | 🔵 |
| TC-002: userId 初期有効時の設定読み込み（冪等性確認） | REQ-002, REQ-401 | 🔵 |
| TC-003: userId 未確定時のデフォルト設定維持 | REQ-002 | 🔵 |
| TC-004: localStorage.setItem 例外時の state 更新保証 | REQ-102, REQ-103(b) | 🟡 |
| TC-005: localStorage.setItem 例外時のエラー非伝播 | REQ-102, REQ-103(b) | 🟡 |

---

## 信頼性レベルサマリー

- **総テストケース数**: 5件
- 🔵 **青信号**: 3件 (60%) — EARS要件定義書・設計文書・既存テストパターンに基づく確実なテストケース
- 🟡 **黄信号**: 2件 (40%) — loadSettings 側の既存 try/catch パターンからの妥当な推測（localStorage 例外処理）
- 🔴 **赤信号**: 0件 (0%)

**品質評価**: ✅ 高品質

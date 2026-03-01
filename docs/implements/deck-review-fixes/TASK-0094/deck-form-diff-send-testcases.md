# TASK-0094: DeckFormModal 差分送信 - テストケース定義書

**タスクID**: TASK-0094
**機能名**: DeckFormModal edit モード差分送信
**要件名**: deck-review-fixes
**作成日**: 2026-03-01
**要件定義書**: `docs/implements/deck-review-fixes/TASK-0094/deck-form-diff-send-requirements.md`

---

## 4. 開発言語・フレームワーク

- **プログラミング言語**: TypeScript (React 18)
  - **言語選択の理由**: 既存フロントエンドが React + TypeScript で構成されており、型安全なテストが可能
  - **テストに適した機能**: 型推論による `UpdateDeckRequest` payload の検証が IDE レベルで可能
- **テストフレームワーク**: Vitest + React Testing Library
  - **フレームワーク選択の理由**: 既存プロジェクトで統一的に使用されている（`vitest.config.ts` で設定済み）
  - **テスト実行環境**: jsdom 環境、`@testing-library/react` でコンポーネントレンダリング
- **テストファイル**: `frontend/src/components/__tests__/DeckFormModal.test.tsx`（新規作成）
- 🔵 *既存テストファイル（DecksPage.test.tsx, DeckSelector.test.tsx）と同一パターン*

---

## テスト構成概要

### テスト対象

| 対象 | ファイル | テスト内容 |
|-----|---------|----------|
| DeckFormModal コンポーネント | `frontend/src/components/DeckFormModal.tsx` | edit モード差分送信ロジック |
| UpdateDeckRequest 型 | `frontend/src/types/deck.ts` | null 許容の型定義（型チェックのみ） |

### モック戦略

- `onSubmit` を `vi.fn()` でモック化し、呼び出し引数（payload）を検証
- `onClose` を `vi.fn()` でモック化
- `DeckFormModal` を直接レンダリング（DecksContext 不使用のため Context モック不要）

### テストヘルパー

```typescript
const makeDeck = (overrides: Partial<Deck>): Deck => ({
  deck_id: 'deck-1',
  user_id: 'user-1',
  name: '英語',
  description: '基本単語',
  color: '#3B82F6',
  card_count: 10,
  due_count: 3,
  created_at: '2024-01-01T00:00:00Z',
  ...overrides,
});
```

---

## 1. 正常系テストケース（基本的な動作）

### TC-01: name のみ変更時に name のみ送信される 🔵

- **テスト名**: name のみ変更時に name のみ送信される
  - **何をテストするか**: edit モードで name だけを変更した場合、payload に name のみが含まれること
  - **期待される動作**: `onSubmit` が `{ name: "英単語" }` で呼ばれる
- **入力値**:
  - 初期デッキ: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
  - 操作: name 入力欄を「英単語」に変更 → 保存ボタン押下
  - **入力データの意味**: name のみ変更し、他フィールドは初期値のまま
- **期待される結果**: `onSubmit` の引数が `{ name: "英単語" }` のみ
  - **期待結果の理由**: REQ-202 により変更フィールドのみ送信。description, color は未変更なので含まない
- **テストの目的**: 差分送信の基本動作確認（TC-202-01 対応）
  - **確認ポイント**: payload に `description` キーと `color` キーが存在しないこと
- 🔵 *REQ-202・TC-202-01・architecture.md セクション8 より*

---

### TC-02: description のみ変更時に description のみ送信される 🔵

- **テスト名**: description のみ変更時に description のみ送信される
  - **何をテストするか**: edit モードで description だけを変更した場合の payload
  - **期待される動作**: `onSubmit` が `{ description: "応用単語" }` で呼ばれる
- **入力値**:
  - 初期デッキ: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
  - 操作: description を「応用単語」に変更 → 保存
  - **入力データの意味**: description のみの値更新
- **期待される結果**: `onSubmit` の引数が `{ description: "応用単語" }`
  - **期待結果の理由**: name, color は未変更のため含まない
- **テストの目的**: 個別フィールド差分検出の正確性確認
  - **確認ポイント**: `name` キーと `color` キーが存在しないこと
- 🔵 *REQ-202・architecture.md セクション8 より*

---

### TC-03: color のみ変更時に color のみ送信される 🔵

- **テスト名**: color のみ変更時に color のみ送信される
  - **何をテストするか**: edit モードで color だけを変更した場合の payload
  - **期待される動作**: `onSubmit` が `{ color: "#EF4444" }` で呼ばれる
- **入力値**:
  - 初期デッキ: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
  - 操作: color パレットで `#EF4444` を選択 → 保存
  - **入力データの意味**: color のみの値更新
- **期待される結果**: `onSubmit` の引数が `{ color: "#EF4444" }`
  - **期待結果の理由**: name, description は未変更のため含まない
- **テストの目的**: color フィールドの差分検出確認
  - **確認ポイント**: `name` キーと `description` キーが存在しないこと
- 🔵 *REQ-202・architecture.md セクション8 より*

---

### TC-04: 複数フィールド変更時に変更フィールドのみ送信される 🔵

- **テスト名**: 複数フィールド変更時に変更フィールドのみ送信される
  - **何をテストするか**: name と description を同時に変更した場合、両方がpayloadに含まれ color は含まれないこと
  - **期待される動作**: `onSubmit` が `{ name: "英単語", description: "応用単語" }` で呼ばれる
- **入力値**:
  - 初期デッキ: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
  - 操作: name を「英単語」、description を「応用単語」に変更 → 保存
  - **入力データの意味**: 2つのフィールドを同時変更するケース
- **期待される結果**: `onSubmit` の引数が `{ name: "英単語", description: "応用単語" }`
  - **期待結果の理由**: 変更されたフィールドのみ。color は未変更なので含まない
- **テストの目的**: 複数変更の正確な差分抽出
  - **確認ポイント**: `color` キーが存在しないこと
- 🔵 *REQ-202・要件定義パターン4 より*

---

### TC-05: description をクリアすると null が送信される 🔵

- **テスト名**: description をクリアすると null が送信される
  - **何をテストするか**: edit モードで description を空にした場合、`description: null` が送信されること
  - **期待される動作**: `onSubmit` が `{ description: null }` で呼ばれる
- **入力値**:
  - 初期デッキ: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
  - 操作: description 入力欄を全て削除（空文字に） → 保存
  - **入力データの意味**: description を明示的にクリアする操作
- **期待される結果**: `onSubmit` の引数に `description: null` が含まれる
  - **期待結果の理由**: REQ-105 により空文字は null に変換し、バックエンドで REMOVE させる
- **テストの目的**: description 空文字 → null 変換の確認
  - **確認ポイント**: `null` であること（`undefined` や空文字 `''` ではないこと）
- 🔵 *REQ-105・REQ-202・要件定義パターン2 より*

---

### TC-06: color を選択解除すると null が送信される 🔵

- **テスト名**: color を選択解除すると null が送信される
  - **何をテストするか**: edit モードで color の「なし」ボタンを押した場合、`color: null` が送信されること
  - **期待される動作**: `onSubmit` が `{ color: null }` で呼ばれる
- **入力値**:
  - 初期デッキ: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
  - 操作: color パレットの「カラーなし」ボタンを押下 → 保存
  - **入力データの意味**: color を明示的にクリアする操作
- **期待される結果**: `onSubmit` の引数に `color: null` が含まれる
  - **期待結果の理由**: REQ-106 により選択解除は null に変換し、バックエンドで REMOVE させる
- **テストの目的**: color 選択解除 → null 変換の確認（TC-202-02 対応）
  - **確認ポイント**: `null` であること（`undefined` ではないこと。`undefined` だと JSON 化でキーが消失する）
- 🔵 *REQ-106・REQ-202・TC-202-02 より*

---

### TC-07: create モードの送信仕様が変わらない（回帰テスト） 🔵

- **テスト名**: create モードでは全フィールドが送信される（回帰テスト）
  - **何をテストするか**: create モードでは従来どおり入力フィールドが全て送信されること
  - **期待される動作**: `onSubmit` が `{ name: "新デッキ", description: "説明文", color: "#3B82F6" }` で呼ばれる
- **入力値**:
  - mode: `'create'`
  - 操作: name=「新デッキ」、description=「説明文」、color=`#3B82F6` を入力 → 保存
  - **入力データの意味**: create モードの標準的な入力
- **期待される結果**: `onSubmit` の引数に全フィールドが含まれる
  - **期待結果の理由**: create モードでは差分検出を行わず、入力値をそのまま送信する
- **テストの目的**: edit モード修正が create モードに影響しないことの回帰確認
  - **確認ポイント**: `CreateDeckRequest` 型の payload が送信されること
- 🔵 *制約条件「create モード非破壊」より*

---

## 2. 異常系テストケース（エラーハンドリング）

### TC-E01: 変更なし時に空 payload が送信される 🔵

- **テスト名**: 変更なし時に空 payload が送信される
  - **エラーケースの概要**: ユーザーが何も変更せず保存した場合の振る舞い
  - **エラー処理の重要性**: 不必要な API 呼び出しを最小化し、サーバー負荷を軽減する
- **入力値**:
  - 初期デッキ: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
  - 操作: 何も変更せず保存ボタン押下
  - **不正な理由**: 不正ではないが、変更なし送信のエッジケース
  - **実際の発生シナリオ**: ユーザーがモーダルを開いて内容を確認後、そのまま保存するケース
- **期待される結果**: `onSubmit` が `{}` で呼ばれる
  - **エラーメッセージの内容**: エラーは発生しない
  - **システムの安全性**: 空 payload でも API 呼び出しは正常に処理される
- **テストの目的**: 変更なし時のペイロードが空オブジェクトであることの確認
  - **品質保証の観点**: TASK-0094 完了条件「変更なしの場合」テストに対応
- 🔵 *TASK-0094 完了条件・要件定義 Edge1 より*

---

## 3. 境界値テストケース（最小値、最大値、null等）

### TC-B01: description が元々 null のデッキで空のまま保存すると変更なし 🟡

- **テスト名**: description が null のデッキで空のまま保存すると description は payload に含まれない
  - **境界値の意味**: `null` と空文字 `''` の正規化後の比較が一致し、差分なしと判定される境界
  - **境界値での動作保証**: 初期値 null → 空文字正規化、フォーム値 '' → 空文字。比較一致で差分なし
- **入力値**:
  - 初期デッキ: `{ name: "英語", description: null, color: "#3B82F6" }`
  - 操作: description を空のまま保存
  - **境界値選択の根拠**: `null ?? '' = ''` と入力 `''` の比較。正規化が正しくないと誤差分が発生する
  - **実際の使用場面**: description を設定したことのないデッキの編集時
- **期待される結果**: `onSubmit` の引数に `description` キーが含まれない
  - **境界での正確性**: `null → ''` 正規化と `'' === ''` 比較の正確性
  - **一貫した動作**: 「変更していないフィールドは送信しない」ルールの一貫性
- **テストの目的**: null/undefined の初期値正規化が正しく動作することの確認
  - **堅牢性の確認**: 初期値が null のケースでも差分検出が安定動作する
- 🟡 *要件定義 Edge2 から妥当な推測*

---

### TC-B02: color が元々 null のデッキで「なし」のまま保存すると変更なし 🟡

- **テスト名**: color が null のデッキで「なし」のまま保存すると color は payload に含まれない
  - **境界値の意味**: `null` と `undefined` の正規化後の比較が一致し、差分なしと判定される境界
  - **境界値での動作保証**: 初期値 `null → null`、フォーム値 `undefined → null`。比較一致で差分なし
- **入力値**:
  - 初期デッキ: `{ name: "英語", description: "基本単語", color: null }`
  - 操作: color を「なし」のまま保存
  - **境界値選択の根拠**: `null ?? null = null` と `undefined → null` 正規化の比較
  - **実際の使用場面**: color を設定したことのないデッキの編集時
- **期待される結果**: `onSubmit` の引数に `color` キーが含まれない
  - **境界での正確性**: `null === null` 比較の正確性
  - **一貫した動作**: color 未設定デッキの編集で不要な更新が発生しないこと
- **テストの目的**: color の null/undefined 正規化が正しく動作することの確認
  - **堅牢性の確認**: 初期値が null のケースでも差分検出が安定動作する
- 🟡 *要件定義 Edge3 から妥当な推測*

---

### TC-B03: description に空白のみを入力すると null が送信される 🟡

- **テスト名**: description に空白のみを入力すると null が送信される
  - **境界値の意味**: `trim()` 後に空文字になる入力が null 変換されることの確認
  - **境界値での動作保証**: 空白のみの入力が意味のある値として送信されないこと
- **入力値**:
  - 初期デッキ: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
  - 操作: description に「   」（空白のみ）を入力して保存
  - **境界値選択の根拠**: `"   ".trim() = ""` → null 変換のパス
  - **実際の使用場面**: ユーザーが description を消そうとしてスペースが残るケース
- **期待される結果**: `onSubmit` の引数に `description: null` が含まれる
  - **境界での正確性**: trim 後に空文字 → null 変換が正しく実行される
  - **一貫した動作**: 空白のみの入力は「クリア」と同等に扱われる
- **テストの目的**: trim 正規化と null 変換の組み合わせ確認
  - **堅牢性の確認**: 空白入力でも正しく null に変換される
- 🟡 *要件定義 Edge4 から妥当な推測*

---

### TC-B04: color を変更してから元に戻すと変更なし 🟡

- **テスト名**: color を変更してから元に戻すと変更なしとして空 payload が送信される
  - **境界値の意味**: 一度変更した値を元に戻した場合に差分検出が正しく「変更なし」と判定すること
  - **境界値での動作保証**: 中間状態ではなく最終的な値で差分比較が行われること
- **入力値**:
  - 初期デッキ: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
  - 操作: color を `#EF4444` に変更 → `#3B82F6` に戻す → 保存
  - **境界値選択の根拠**: 変更 → 元に戻す操作で、最終値と初期値が一致するケース
  - **実際の使用場面**: ユーザーが color を試し選びして結局元の色に戻すケース
- **期待される結果**: `onSubmit` の引数が `{}`（空オブジェクト）
  - **境界での正確性**: 最終値 `#3B82F6` === 初期値 `#3B82F6` → 差分なし
  - **一貫した動作**: 中間の変更履歴に影響されず最終値で比較される
- **テストの目的**: 変更後の復帰が正しく差分なしと判定されることの確認
  - **堅牢性の確認**: 操作の順序に関係なく最終値ベースの差分比較が正しく機能する
- 🟡 *要件定義 Edge5 から妥当な推測*

---

### TC-B05: description と color を同時に null に設定 🔵

- **テスト名**: description と color を同時にクリアすると両方 null が送信される
  - **境界値の意味**: 複数フィールドの同時クリアが正しく処理されること（EDGE-102 対応）
  - **境界値での動作保証**: 各フィールドの null 変換が独立して正しく動作する
- **入力値**:
  - 初期デッキ: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
  - 操作: description を空に、color の「なし」を選択 → 保存
  - **境界値選択の根拠**: EDGE-102（description と color の同時 null 設定）
  - **実際の使用場面**: デッキの説明とカラーを同時にリセットする操作
- **期待される結果**: `onSubmit` の引数が `{ description: null, color: null }`
  - **境界での正確性**: 両フィールドが独立して null に変換される
  - **一貫した動作**: name は未変更のため含まれない
- **テストの目的**: 複数フィールド同時クリアの正確な payload 生成確認
  - **堅牢性の確認**: フィールド間の相互干渉がないこと
- 🔵 *EDGE-102・REQ-105・REQ-106 より*

---

## テストケースサマリー

### カテゴリ別件数

| カテゴリ | テスト名 | 信頼性 |
|---------|---------|--------|
| **正常系** | TC-01: name のみ変更 | 🔵 |
| **正常系** | TC-02: description のみ変更 | 🔵 |
| **正常系** | TC-03: color のみ変更 | 🔵 |
| **正常系** | TC-04: 複数フィールド変更 | 🔵 |
| **正常系** | TC-05: description クリア → null | 🔵 |
| **正常系** | TC-06: color 選択解除 → null | 🔵 |
| **正常系** | TC-07: create モード回帰 | 🔵 |
| **異常系** | TC-E01: 変更なし → 空 payload | 🔵 |
| **境界値** | TC-B01: description null デッキ → 変更なし | 🟡 |
| **境界値** | TC-B02: color null デッキ → 変更なし | 🟡 |
| **境界値** | TC-B03: 空白のみ → null | 🟡 |
| **境界値** | TC-B04: 変更後元に戻す → 変更なし | 🟡 |
| **境界値** | TC-B05: description + color 同時 null | 🔵 |

### 信頼性レベル分布

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 9件 | 69% |
| 🟡 黄信号 | 4件 | 31% |
| 🔴 赤信号 | 0件 | 0% |

### TASK-0094 完了条件との対応

| 完了条件 | 対応テストケース |
|---------|---------------|
| edit モードでフォーム初期値を保持 | TC-01〜TC-06（全て初期値との比較を使用） |
| 保存時に各フィールドの変更を検出 | TC-01〜TC-04 |
| 変更されたフィールドのみを API に送信 | TC-01〜TC-04, TC-E01 |
| description 空文字 → null（クリア）変換 | TC-05, TC-B03 |
| color 選択解除 → null（クリア）変換 | TC-06 |
| UpdateDeckRequest の型変更 | 型チェック（コンパイル時検証） |
| テスト: 変更フィールドのみ送信、null 変換、変更なし | TC-01〜TC-06, TC-E01, TC-B01〜TC-B05 |

---

## 5. テストケース実装時の日本語コメント指針

### テストファイル全体構成

```typescript
/**
 * 【テスト概要】: DeckFormModal コンポーネントの差分送信テスト
 * 【テスト対象】: DeckFormModal edit モード - 変更フィールドのみ送信
 * 【関連要件】: REQ-202, REQ-105, REQ-106
 * 【関連タスク】: TASK-0094
 */
```

### セットアップ

```typescript
beforeEach(() => {
  // 【テスト前準備】: 各テスト実行前にモック関数をリセット
  // 【環境初期化】: onSubmit / onClose のモック呼び出し履歴をクリア
  vi.clearAllMocks();
});
```

### 各テストケース

```typescript
it('name のみ変更時に name のみ送信される', async () => {
  // 【テスト目的】: edit モードで name だけを変更した場合、payload に name のみが含まれることを確認
  // 【テスト内容】: description と color を初期値のまま、name のみ変更して保存
  // 【期待される動作】: onSubmit が { name: "英単語" } で呼ばれる
  // 🔵 REQ-202・TC-202-01

  // 【テストデータ準備】: 全フィールドが設定されたデッキを用意
  const deck = makeDeck({ name: '英語', description: '基本単語', color: '#3B82F6' });
  const onSubmit = vi.fn().mockResolvedValue(undefined);
  const onClose = vi.fn();

  // 【初期条件設定】: edit モードでモーダルをレンダリング
  render(
    <DeckFormModal mode="edit" deck={deck} isOpen={true} onClose={onClose} onSubmit={onSubmit} />
  );

  // 【実際の処理実行】: name 入力欄を変更して保存
  const nameInput = screen.getByTestId('deck-name-input');
  fireEvent.change(nameInput, { target: { value: '英単語' } });
  fireEvent.click(screen.getByTestId('deck-form-submit'));

  // 【結果検証】: onSubmit の引数が name のみを含むこと
  await waitFor(() => {
    expect(onSubmit).toHaveBeenCalledWith({ name: '英単語' }); // 🔵
  });
});
```

---

## 6. 要件定義との対応関係

- **参照した機能概要**: 要件定義セクション1（DeckFormModal edit モード差分送信の目的と位置づけ）
- **参照した入力・出力仕様**: 要件定義セクション2（UpdateDeckRequest payload、送信値の3パターン、正規化ルール）
- **参照した制約条件**: 要件定義セクション3（create モード非破壊、初期値スナップショット、正規化ルール）
- **参照した使用例**: 要件定義セクション4（パターン1〜4、Edge1〜Edge5）
- **参照した受け入れ基準**: TC-202-01（変更フィールドのみ送信）、TC-202-02（color 選択解除 → null）
- **参照した EARS 要件**: REQ-202, REQ-105, REQ-106, EDGE-102

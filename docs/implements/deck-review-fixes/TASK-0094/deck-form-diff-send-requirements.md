# TASK-0094: DeckFormModal 差分送信 - 要件定義書

**タスクID**: TASK-0094
**機能名**: DeckFormModal edit モード差分送信
**要件名**: deck-review-fixes
**作成日**: 2026-03-01

---

## 1. 機能の概要（EARS要件定義書・設計文書ベース）

- 🔵 **何をする機能か**: `DeckFormModal` の edit モードにおいて、ユーザーが変更したフィールドのみを `updateDeck` API に送信する差分送信機能。現状は変更有無にかかわらず全フィールドを送信しており、description クリアや color 選択解除の際に正しい null 値が送信されない問題を修正する。
- 🔵 **どのような問題を解決するか**: 現在の実装では edit モードで description を空にした場合に空文字 `''` が送信され、バックエンドの REMOVE（REQ-105）が発動しない。color を「なし」に戻した場合も `undefined` が代入されるため、JSON シリアライズ時にキーが消失し、バックエンドに「クリア」の意図が伝わらない。
- 🔵 **想定されるユーザー**: Memoru LIFF アプリケーションを使用するカード学習者。デッキの名前・説明・カラーを編集する操作を行う。
- 🔵 **システム内での位置づけ**: フロントエンド `DeckFormModal` コンポーネント（React）からバックエンド `PUT /decks/:id`（Lambda）への送信レイヤーに位置する。バックエンド側は TASK-0089（Sentinel パターン + description/color REMOVE）で対応済みのため、フロントエンドの送信値を正しく整形する修正。
- **参照したEARS要件**: REQ-202, REQ-105, REQ-106
- **参照した設計文書**: architecture.md セクション8、dataflow.md フロー7

---

## 2. 入力・出力の仕様（EARS機能要件・TypeScript型定義ベース）

### 入力

- 🔵 **モーダル起動時の初期値（`initialValues`）**: モーダルを開いた瞬間の `deck` オブジェクトから取得し、state として保持する
  - `name: string` - デッキ名（`deck.name`）
  - `description: string` - 説明（`deck.description ?? ''`、null/undefined は空文字に正規化）
  - `color: string | null` - カラー（`deck.color ?? null`、undefined は null に正規化）
- 🔵 **ユーザー入力フォーム値**: フォームの各フィールドに対するユーザーの入力値
  - `name: string` - trim 後の値
  - `description: string` - trim 後の値
  - `color: string | undefined` - 選択されたカラー、または `undefined`（「なし」選択時）

### 出力

- 🔵 **`UpdateDeckRequest` payload**: 変更されたフィールドのみを含むオブジェクト
  - `name?: string` - 変更時のみ含む
  - `description?: string | null` - 変更時のみ含む。空文字は `null` に変換（REMOVE 指示）
  - `color?: string | null` - 変更時のみ含む。選択解除（undefined）は `null` に変換（REMOVE 指示）

### 型定義の変更

- 🔵 **変更前**（`frontend/src/types/deck.ts`）:
  ```typescript
  export interface UpdateDeckRequest {
    name?: string;
    description?: string;
    color?: string;
  }
  ```
- 🔵 **変更後**:
  ```typescript
  export interface UpdateDeckRequest {
    name?: string;
    description?: string | null;
    color?: string | null;
  }
  ```

### 送信値の3パターン

- 🔵 `undefined`（キー未送信）: フィールド変更なし → payload に含めない
- 🔵 `null`: 明示的クリア → バックエンドで REMOVE
- 🔵 `string`: 値更新 → バックエンドで SET

- **参照したEARS要件**: REQ-202, REQ-105, REQ-106
- **参照した設計文書**: architecture.md セクション8（DeckFormModal 差分送信）、dataflow.md フロー4（デッキフィールドクリア）、dataflow.md フロー7（DeckFormModal 差分送信フローチャート）

---

## 3. 制約条件（EARS非機能要件・アーキテクチャ設計ベース）

### 互換性要件

- 🔵 **create モード非破壊**: `CreateDeckRequest` の型・送信ロジックは変更しない。create モードは従来どおり全フィールドを送信する。
- 🔵 **バックエンド互換**: バックエンド `PUT /decks/:id` は body キーの存在で `null` と未送信を判別する実装が TASK-0089 で完了済み。フロントエンドが `description: null` / `color: null` を正しく JSON で送信すれば要件を満たす。

### アーキテクチャ制約

- 🔵 **初期値スナップショット**: モーダルを開いた瞬間の値を `initialValues` state に保持する。`deck` prop が再レンダリングで変わっても、比較基準は起動時スナップショットを使う。
- 🟡 **変更なし時の振る舞い**: 変更がない場合は空 payload `{}` を `onSubmit` に渡す。API 呼び出しスキップは呼び出し元（DecksPage）の責務とする。

### 正規化ルール

- 🔵 **name**: `trim()` 後の値で比較・送信
- 🔵 **description**: `trim()` 後の値で比較。変更があり空文字の場合は `null` として送信
- 🔵 **color**: フォーム値 `undefined` を `null` に正規化して比較・送信。初期値も `deck.color ?? null` で正規化

- **参照したEARS要件**: REQ-202, REQ-105, REQ-106
- **参照した設計文書**: architecture.md セクション8

---

## 4. 想定される使用例（EARSEdgeケース・データフローベース）

### 基本的な使用パターン

#### パターン1: name のみ変更 🔵

- **初期値**: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
- **操作**: name を「英単語」に変更して保存
- **期待 payload**: `{ name: "英単語" }`

#### パターン2: description をクリア 🔵

- **初期値**: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
- **操作**: description を空にして保存
- **期待 payload**: `{ description: null }`

#### パターン3: color を選択解除 🔵

- **初期値**: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
- **操作**: color の「なし」ボタンを押して保存
- **期待 payload**: `{ color: null }`

#### パターン4: 複数フィールド変更 🔵

- **初期値**: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
- **操作**: name を「英単語」、description を空にして保存
- **期待 payload**: `{ name: "英単語", description: null }`

### エッジケース

#### Edge1: 変更なし 🔵

- **初期値**: `{ name: "英語", description: "基本単語", color: "#3B82F6" }`
- **操作**: 何も変更せず保存
- **期待 payload**: `{}`（空オブジェクト）

#### Edge2: description が元々 null のデッキで空のまま保存 🟡

- **初期値**: `{ name: "英語", description: null, color: null }`
- **操作**: description を空のまま保存
- **期待**: 変更なし（`description` は payload に含めない）
  - 初期値の null は空文字に正規化（`null ?? '' = ''`）、フォーム値も空文字 → 差分なし

#### Edge3: color が元々 null のデッキで「なし」のまま保存 🟡

- **初期値**: `{ name: "英語", description: null, color: null }`
- **操作**: color を「なし」のまま保存
- **期待**: 変更なし（`color` は payload に含めない）
  - 初期値の null → null、フォーム値 undefined → null に正規化 → 差分なし

#### Edge4: description に空白のみを入力 🟡

- **初期値**: `{ name: "英語", description: "基本単語", color: null }`
- **操作**: description に「   」（空白のみ）を入力して保存
- **期待 payload**: `{ description: null }`（trim 後に空文字 → null）

#### Edge5: color を変更してから元に戻す 🟡

- **初期値**: `{ name: "英語", description: null, color: "#3B82F6" }`
- **操作**: color を「#EF4444」に変更 → 再度「#3B82F6」に戻す → 保存
- **期待 payload**: `{}`（変更なし）

- **参照したEARS要件**: REQ-202, EDGE-102
- **参照した設計文書**: dataflow.md フロー7

---

## 5. EARS要件・設計文書との対応関係

- **参照したユーザストーリー**: デッキ管理（edit モードでの差分送信）
- **参照した機能要件**: REQ-202, REQ-105, REQ-106
- **参照した非機能要件**: なし（フロントエンド UI 修正のためパフォーマンス・セキュリティ要件は対象外）
- **参照したEdgeケース**: EDGE-102（description と color の同時 null 設定）
- **参照した受け入れ基準**:
  - TC-202-01: 変更されたフィールドのみ API に送信される
  - TC-202-02: color を選択後に「なし」に戻した場合の処理
- **参照した設計文書**:
  - **アーキテクチャ**: architecture.md セクション8（DeckFormModal 差分送信）
  - **データフロー**: dataflow.md フロー4（デッキフィールドクリア）、フロー7（DeckFormModal 差分送信フローチャート）
  - **型定義**: `frontend/src/types/deck.ts`（UpdateDeckRequest）
  - **データベース**: なし（フロントエンド修正のみ）
  - **API仕様**: `PUT /decks/:id`（バックエンド側は TASK-0089 で対応済み）

---

## 6. 実装対象ファイル

### 修正対象

| ファイル | 修正内容 |
|---------|---------|
| `frontend/src/types/deck.ts` | `UpdateDeckRequest` の `description`/`color` に `| null` を追加 |
| `frontend/src/components/DeckFormModal.tsx` | 初期値保持、差分比較ロジック、null 変換 |

### テストファイル

| ファイル | 内容 |
|---------|-----|
| `frontend/src/components/__tests__/DeckFormModal.test.tsx` | 新規作成 - 差分送信テスト |

### 参考ファイル

| ファイル | 用途 |
|---------|-----|
| `frontend/src/pages/__tests__/DecksPage.test.tsx` | テストパターンの参考 |
| `frontend/src/pages/DecksPage.tsx` | onSubmit 呼び出し元の確認 |
| `frontend/src/contexts/DecksContext.tsx` | updateDeck の実装確認 |
| `backend/src/api/handlers/decks_handler.py` | バックエンド受け口の確認 |
| `backend/src/services/deck_service.py` | Sentinel パターンの確認 |

---

## 信頼性レベルサマリー

| セクション | 🔵 青信号 | 🟡 黄信号 | 🔴 赤信号 |
|-----------|----------|----------|----------|
| 1. 機能の概要 | 4 | 0 | 0 |
| 2. 入力・出力の仕様 | 8 | 0 | 0 |
| 3. 制約条件 | 5 | 1 | 0 |
| 4. 想定される使用例 | 5 | 4 | 0 |
| 5. 対応関係 | - | - | - |
| **合計** | **22** | **5** | **0** |

**品質評価**: ✅ 高品質
- 要件の曖昧さ: なし（REQ-202, REQ-105, REQ-106 で明確に定義）
- 入出力定義: 完全（型定義・送信値パターン・正規化ルールを網羅）
- 制約条件: 明確（create モード非破壊、初期値スナップショット、正規化ルール）
- 実装可能性: 確実（バックエンド対応済み、フロントエンド修正のみ）
- 信頼性レベル: 🔵 が 81.5%、🟡 は妥当な推測のみ（エッジケースの振る舞い詳細）

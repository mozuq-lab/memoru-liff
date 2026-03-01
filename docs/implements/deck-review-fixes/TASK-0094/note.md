# TASK-0094: DeckFormModal 差分送信 - 開発ノート

## タスク概要

`DeckFormModal` の `edit` モードで、変更されたフィールドのみを `updateDeck` API に送信する。
あわせて、以下の null 変換ルールを満たす。

- description を空文字にした場合: `description: null` を送信（クリア）
- color を「なし」にした場合: `color: null` を送信（クリア）

### 関連要件
- REQ-202: `DeckFormModal` の edit モードでは、変更されたフィールドのみを API に送信しなければならない
- REQ-105: `description=null` で DynamoDB から属性を REMOVE
- REQ-106: `color=null` で DynamoDB から属性を REMOVE

---

## 技術スタック

### フロントエンド
- React 18 + TypeScript
- Context API (`DecksContext`)
- React Testing Library + Vitest
- Vite

### 参照元
- `frontend/src/components/DeckFormModal.tsx`
- `frontend/src/types/deck.ts`
- `docs/design/deck-review-fixes/architecture.md`（セクション8）
- `docs/spec/deck-review-fixes/requirements.md`（REQ-202, REQ-105, REQ-106）

---

## 開発ルール

### TDD ワークフロー
1. `/tsumiki:tdd-red` で失敗テストを追加
2. `/tsumiki:tdd-green` で最小実装
3. `/tsumiki:tdd-refactor` で整理

### 送信値の扱いルール
- `undefined`: キー未送信（変更なし）
- `null`: 明示的クリア（バックエンドで REMOVE）
- `string`: 値更新

### 比較時の正規化ルール
- `name`: `trim()` 後の値で比較・送信
- `description`: `trim()` 後の値で比較し、空文字は `null` として送信
- `color`: `string | undefined` を `string | null` に正規化して比較・送信

---

## 関連実装

### 1. DeckFormModal 現状実装の課題

ファイル: `frontend/src/components/DeckFormModal.tsx`

現状の `edit` モード送信ロジック:

```tsx
const data: UpdateDeckRequest = {};
if (trimmedName !== deck?.name) data.name = trimmedName;
if (description.trim() !== (deck?.description ?? '')) data.description = description.trim();
if (color !== (deck?.color ?? undefined)) data.color = color;
await onSubmit(data);
```

課題:
- `description` クリア時に `''` を送信してしまい、`null` 送信にならない
- `color` を「なし」にした時に `undefined` 代入になるため、JSON 化でキーが落ちて「クリア」にならない
- 初期値保持が `deck` 直接参照で、モーダル起動時スナップショットとして固定されない

### 2. 型定義の課題

ファイル: `frontend/src/types/deck.ts`

現状:

```ts
export interface UpdateDeckRequest {
  name?: string;
  description?: string;
  color?: string;
}
```

必要な修正:

```ts
export interface UpdateDeckRequest {
  name?: string;
  description?: string | null;
  color?: string | null;
}
```

### 3. バックエンド側の受け口（実装済み）

- `backend/src/api/handlers/decks_handler.py` は body キー存在で `null` と未送信を判別
- `backend/src/services/deck_service.py` は Sentinel パターンで `None` を REMOVE に変換

そのため、フロントエンドから `description: null` / `color: null` を正しく送れば要件を満たせる。

### 4. 目標ロジック（設計準拠）

```tsx
const payload: Partial<UpdateDeckRequest> = {};

if (normalizedName !== initialValues.name) {
  payload.name = normalizedName;
}
if (normalizedDescription !== initialValues.description) {
  payload.description = normalizedDescription === '' ? null : normalizedDescription;
}
if (normalizedColor !== initialValues.color) {
  payload.color = normalizedColor;
}

await onSubmit(payload);
```

---

## 設計文書

### architecture.md（セクション8）
- edit モードで差分のみ送信
- description 空文字は `null` に変換
- color 選択解除は `null` に変換

### interfaces.ts
- `UpdateDeckRequest.description` / `color` は `string | null | undefined`
- `DeckFormInitialValues` を保持して差分比較

### acceptance-criteria.md
- TC-202-01: 変更フィールドのみ送信
- TC-202-02: color を「なし」に戻した場合 `color: null` を送信

---

## 注意事項

### 初期値保持
- モーダルを開いた瞬間の値を `initialValues` として state に保持する
- `deck` が再描画で変わっても、比較基準は起動時スナップショットを使う

### 変更なし送信
- 変更なし時は空 payload `{}` 送信、または API 呼び出しスキップのどちらか
- TASK-0094 の完了条件では「変更なしの場合」をテストで保証する

### 型安全性
- `UpdateDeckRequest` の null 許容を先に適用してから差分実装する
- `CreateDeckRequest` 側は従来どおり `string` / `undefined` のまま維持する

---

## テスト項目（TASK-0094 完了条件）

### ユニットテスト（推奨）

対象候補:
- `frontend/src/components/__tests__/DeckFormModal.test.tsx`（新規）
- または `frontend/src/pages/__tests__/DecksPage.test.tsx` にモーダル送信検証を追加

主要ケース:
1. name のみ変更時、`{ name: ... }` のみ送信
2. description を空にして保存時、`{ description: null }` を送信
3. color を「なし」にして保存時、`{ color: null }` を送信
4. 複数変更時、変更されたキーのみ送信
5. 変更なし時、空 payload（または送信なし）

### 回帰確認
1. create モードの送信仕様が変わらないこと
2. 既存 DecksPage 操作（作成/編集/削除）に退行がないこと

---

## 実装チェックリスト

### Phase 1: 型修正
- [ ] `frontend/src/types/deck.ts` の `UpdateDeckRequest` を null 許容に変更

### Phase 2: 差分送信ロジック
- [ ] `DeckFormModal` に edit モード初期値保持を追加
- [ ] 保存時に正規化後の差分比較を実装
- [ ] description 空文字を `null` に変換
- [ ] color 選択解除を `null` に変換

### Phase 3: テスト
- [ ] 差分送信テストを追加
- [ ] null 変換テストを追加
- [ ] 変更なしケースを追加
- [ ] `npm run test` で関連テストが通ることを確認

---

## ファイルパス（相対パス）

### 対象ファイル
- `frontend/src/components/DeckFormModal.tsx`
- `frontend/src/types/deck.ts`

### テストファイル
- `frontend/src/components/__tests__/DeckFormModal.test.tsx`（新規想定）
- `frontend/src/pages/__tests__/DecksPage.test.tsx`（既存拡張案）

### 参考ファイル
- `frontend/src/pages/DecksPage.tsx`
- `frontend/src/contexts/DecksContext.tsx`
- `backend/src/api/handlers/decks_handler.py`
- `backend/src/services/deck_service.py`
- `docs/design/deck-review-fixes/architecture.md`
- `docs/spec/deck-review-fixes/requirements.md`
- `docs/spec/deck-review-fixes/acceptance-criteria.md`
- `docs/tasks/deck-review-fixes/TASK-0094.md`

---

## 信頼性レベルサマリー

- **REQ-202**: 🔵 青信号（レビュー M-4 と architecture.md で明示）
- **REQ-105 / REQ-106**: 🔵 青信号（backend 側 Sentinel 実装で担保済み）
- **TC-202-02（color 解除）**: 🟡 黄信号（受け入れ基準のエッジケース）

**品質評価**: ✅ 実装可能（フロントエンド差分送信の整合のみ）

---

## 実装の流れ（TDD方式）

1. `/tsumiki:tdd-requirements TASK-0094` - 詳細要件定義
2. `/tsumiki:tdd-testcases` - テストケース作成
3. `/tsumiki:tdd-red` - テスト実装（失敗）
4. `/tsumiki:tdd-green` - 最小実装
5. `/tsumiki:tdd-refactor` - リファクタリング
6. `/tsumiki:tdd-verify-complete` - 品質確認

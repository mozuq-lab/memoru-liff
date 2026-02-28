# Frontend State Contracts: カード検索

**Feature**: [spec.md](../spec.md)
**Date**: 2026-02-28
**Scope**: フロントエンド内部コントラクト（API変更なし）

> **Note**: このフィーチャーはバックエンドAPIを変更しないため、公開APIコントラクトは存在しない。
> このファイルは新規コンポーネント・フックの props/戻り値コントラクトを定義する。

---

## useCardSearch フック

### Signature

```typescript
// frontend/src/hooks/useCardSearch.ts

interface UseCardSearchOptions {
  /** フィルタリング対象のカード配列 */
  cards: Card[];
}

interface UseCardSearchReturn {
  // 状態
  query: string;
  reviewStatus: ReviewStatusFilter;
  sortBy: SortByOption;
  sortOrder: SortOrder;

  // 状態更新
  setQuery: (query: string) => void;
  setReviewStatus: (status: ReviewStatusFilter) => void;
  setSortBy: (sortBy: SortByOption) => void;
  setSortOrder: (order: SortOrder) => void;

  // 計算値
  /** フィルタリング・ソート済みカード配列 */
  filteredCards: Card[];

  // アクション
  /** すべてのフィルターをリセット（初期状態に戻す） */
  reset: () => void;
}

export const useCardSearch = (options: UseCardSearchOptions): UseCardSearchReturn;
```

### 初期値

| プロパティ     | 初期値         | 意味             |
| -------------- | -------------- | ---------------- |
| `query`        | `''`           | 検索なし         |
| `reviewStatus` | `'all'`        | すべて表示       |
| `sortBy`       | `'created_at'` | 作成日順         |
| `sortOrder`    | `'desc'`       | 新しい順（降順） |

### 振る舞いの保証

- `filteredCards` は `useMemo` で計算され、`[cards, query, reviewStatus, sortBy, sortOrder]` のいずれかが変化した時のみ再計算される
- `query` が空文字のとき、テキストフィルタリングをスキップする
- `reviewStatus` が `'all'` のとき、状態フィルタリングをスキップする
- ソートの安定性: 同値のカードは元の順序を維持する

---

## SearchBar コンポーネント

### Props Contract

```typescript
// frontend/src/components/SearchBar.tsx

interface SearchBarProps {
  /** 現在の検索文字列 */
  value: string;
  /** 検索文字列変更ハンドラ */
  onChange: (value: string) => void;
  /** プレースホルダーテキスト（デフォルト: "カードを検索..."） */
  placeholder?: string;
  /** 最大文字数（デフォルト: 100） */
  maxLength?: number;
}
```

### Testable Behaviors

| テスト ID | 振る舞い                                                        |
| --------- | --------------------------------------------------------------- |
| SB-001    | 入力フィールドが表示される                                      |
| SB-002    | テキスト入力により `onChange` が呼ばれる                        |
| SB-003    | `value` が空でないとき、クリアボタン（✕）が表示される           |
| SB-004    | クリアボタン押下で `onChange('')` が呼ばれる                    |
| SB-005    | `value` が空のときクリアボタンは表示されない                    |
| SB-006    | `maxLength` による入力制限が機能する                            |
| SB-007    | `data-testid="search-bar-input"` が付与されている               |
| SB-008    | `data-testid="search-bar-clear"` がクリアボタンに付与されている |

---

## FilterChips コンポーネント

### Props Contract

```typescript
// frontend/src/components/FilterChips.tsx

interface FilterChipsProps {
  /** 選択中の復習状態フィルター */
  value: ReviewStatusFilter;
  /** 変更ハンドラ */
  onChange: (status: ReviewStatusFilter) => void;
}
```

### Chip 定義

| `value`      | 表示ラベル  | `data-testid`          |
| ------------ | ----------- | ---------------------- |
| `'all'`      | すべて      | `filter-chip-all`      |
| `'due'`      | 期日（due） | `filter-chip-due`      |
| `'learning'` | 学習中      | `filter-chip-learning` |
| `'new'`      | 新規        | `filter-chip-new`      |

### Testable Behaviors

| テスト ID | 振る舞い                                                             |
| --------- | -------------------------------------------------------------------- |
| FC-001    | 4つのチップが表示される（all, due, learning, new）                   |
| FC-002    | 選択中のチップが視覚的に区別される（`aria-pressed="true"`)           |
| FC-003    | チップ押下で `onChange` が対応する `ReviewStatusFilter` 値で呼ばれる |
| FC-004    | `value='due'` のとき「期日（due）」チップが selected 状態になる      |

---

## SortSelect コンポーネント

### Props Contract

```typescript
// frontend/src/components/SortSelect.tsx

interface SortSelectProps {
  /** 現在のソートキー */
  sortBy: SortByOption;
  /** 現在のソート方向 */
  sortOrder: SortOrder;
  /** ソートキー変更ハンドラ */
  onSortByChange: (sortBy: SortByOption) => void;
  /** ソート方向変更ハンドラ */
  onSortOrderChange: (order: SortOrder) => void;
}
```

### ソートオプション定義

| `sortBy`           | 表示ラベル |
| ------------------ | ---------- |
| `'created_at'`     | 作成日     |
| `'next_review_at'` | 次回復習日 |
| `'ease_factor'`    | 習熟度     |

### Testable Behaviors

| テスト ID | 振る舞い                                           |
| --------- | -------------------------------------------------- |
| SS-001    | ソートキー選択ドロップダウンが表示される           |
| SS-002    | ソート方向トグルボタンが表示される                 |
| SS-003    | `data-testid="sort-by-select"` が付与されている    |
| SS-004    | `data-testid="sort-order-toggle"` が付与されている |
| SS-005    | ソートキー変更で `onSortByChange` が呼ばれる       |
| SS-006    | 方向トグルで `onSortOrderChange` が呼ばれる        |

---

## HighlightText コンポーネント

### Props Contract

```typescript
// frontend/src/components/HighlightText.tsx

interface HighlightTextProps {
  /** 表示する元テキスト */
  text: string;
  /** ハイライトするキーワード（空文字 = ハイライトなし） */
  query: string;
  /** テキストの最大文字数（truncate 用）。省略可 */
  maxLength?: number;
  /** テキスト全体に適用する CSS クラス */
  className?: string;
}
```

### Testable Behaviors

| テスト ID | 振る舞い                                                          |
| --------- | ----------------------------------------------------------------- |
| HT-001    | `query` が空のとき、テキストがそのまま表示される                  |
| HT-002    | `query` がマッチした箇所は `<mark>` タグで囲まれる                |
| HT-003    | マッチは大文字・小文字を区別しない                                |
| HT-004    | マッチは全角・半角を区別しない                                    |
| HT-005    | XSS を引き起こす特殊文字（`<script>` 等）が安全にエスケープされる |
| HT-006    | 複数箇所マッチの場合、すべての箇所がハイライトされる              |

---

## 変更される既存コントラクト

### CardList.tsx（変更）

```typescript
// 変更前
interface CardListProps {
  cards: Card[];
}

// 変更後
interface CardListProps {
  cards: Card[];
  /** 検索キーワード（HighlightText に渡す）。省略可 */
  highlightQuery?: string;
}
```

**後方互換性**: `highlightQuery` はオプショナルなため、既存の使用箇所に変更不要。

---

## バックエンド API（変更なし）

| エンドポイント   | 変更 |
| ---------------- | ---- |
| `GET /cards`     | なし |
| `GET /cards/due` | なし |
| その他すべて     | なし |

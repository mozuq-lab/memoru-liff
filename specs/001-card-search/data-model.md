# Data Model: カード検索

**Feature**: [spec.md](./spec.md)
**Date**: 2026-02-28

---

## 既存エンティティ（変更あり）

### Card（`frontend/src/types/card.ts`）

変更内容なし。フィルタリングに使用するフィールドの説明を追記。

| フィールド       | 型               | 用途                                  |
| ---------------- | ---------------- | ------------------------------------- |
| `card_id`        | `string`         | 一意識別子                            |
| `front`          | `string`         | 表面テキスト — **検索対象**           |
| `back`           | `string`         | 裏面テキスト — **検索対象**           |
| `repetitions`    | `number`         | 復習回数。`0` なら `new` 状態         |
| `next_review_at` | `string \| null` | 次回復習日。`<= 今日` なら `due` 状態 |
| `ease_factor`    | `number`         | SM-2 習熟度スコア。ソート対象         |
| `created_at`     | `string`         | 作成日時。ソート対象                  |

---

## 新規型定義（`frontend/src/types/card.ts` に追加）

### ReviewStatusFilter

```typescript
/**
 * カードの復習状態フィルター
 * - 'all': すべてのカード
 * - 'new': repetitions === 0
 * - 'due': repetitions > 0 かつ next_review_at <= 今日
 * - 'learning': repetitions > 0 かつ next_review_at > 今日
 */
export type ReviewStatusFilter = "all" | "new" | "due" | "learning";
```

### SortByOption

```typescript
/**
 * カードのソートキー
 * - 'created_at': 作成日順
 * - 'next_review_at': 次回復習日順（null は末尾）
 * - 'ease_factor': 習熟度順（低い = 苦手なカード）
 */
export type SortByOption = "created_at" | "next_review_at" | "ease_factor";
```

### SortOrder

```typescript
/**
 * ソート方向
 */
export type SortOrder = "asc" | "desc";
```

### CardFilterState

```typescript
/**
 * カード検索・フィルター・ソートの状態
 * useCardSearch フックが管理する状態の型
 */
export interface CardFilterState {
  /** キーワード検索文字列（空文字 = フィルターなし） */
  query: string;
  /** 復習状態フィルター */
  reviewStatus: ReviewStatusFilter;
  /** ソートキー */
  sortBy: SortByOption;
  /** ソート方向 */
  sortOrder: SortOrder;
}
```

---

## 状態遷移

### ReviewStatusFilter の導出ロジック

```
Card.repetitions === 0
  → ReviewStatus: 'new'

Card.repetitions > 0 AND Card.next_review_at !== null AND next_review_at <= 今日
  → ReviewStatus: 'due'

Card.repetitions > 0 AND (Card.next_review_at === null OR next_review_at > 今日)
  → ReviewStatus: 'learning'
```

### CardFilterState の適用順序

```
入力: cards[] (全カード配列)
  Step 1: query フィルター（front + back テキスト検索）
  Step 2: reviewStatus フィルター（状態分類）
  Step 3: sortBy + sortOrder によるソート
出力: filteredCards[] (表示用カード配列)
```

---

## バリデーションルール

| ルール                | 内容                                                                            |
| --------------------- | ------------------------------------------------------------------------------- |
| `query` の長さ制限    | UI 上で `maxLength={100}` を設ける（要件エッジケース）                          |
| `query` の特殊文字    | React の JSX レンダリングで自動エスケープ。正規表現用に手動エスケープ処理が必要 |
| 空 `query`            | `''` のとき全カードを表示（フィルタリングをスキップ）                           |
| `null` next_review_at | `'due'` フィルター選択時には除外し、`'learning'` にも含めない                   |

---

## コンポーネント別データフロー

```
CardsContext
  ↓ cards[]
CardsPage
  ↓ cards[] → useCardSearch
useCardSearch
  ↓ filteredCards[] + filter state
CardsPage
  ↓ filteredCards[]
CardList ← highlightQuery: string
  ↓ cards[], query
CardListItem
  ↓ card, query
HighlightText ← text: string, query: string
```

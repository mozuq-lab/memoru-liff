# Research: カード検索

**Feature**: [spec.md](./spec.md)
**Date**: 2026-02-28
**Status**: Complete — 全 NEEDS CLARIFICATION 解決済み

---

## 1. 全角・半角正規化の実装方法

**Decision**: `String.prototype.normalize('NFKC').toLowerCase()` を使用する

**Rationale**:

- `normalize('NFKC')` は全角英数字・カタカナを半角に正規化する（例: `Ａ` → `A`、`ａ` → `a`）
- `toLowerCase()` と組み合わせることで case-insensitive 検索を実現
- 標準 Web API のみで完結し、外部ライブラリ不要
- ひらがな・漢字はそのまま維持（意図した動作）

**Alternatives considered**:

- `wanakana` ライブラリ: ひらがな↔ローマ字変換も可能だが、今回の要件にはオーバースペック
- カスタム正規化マップ: メンテナンスコストが高い

**Implementation**:

```typescript
const normalize = (text: string): string =>
  text.normalize("NFKC").toLowerCase();

const matches =
  normalize(card.front).includes(normalize(query)) ||
  normalize(card.back).includes(normalize(query));
```

---

## 2. テキストハイライトの実装方法

**Decision**: カスタム `HighlightText` コンポーネントで文字列を分割して `<mark>` タグで囲む

**Rationale**:

- `dangerouslySetInnerHTML` や `innerHTML` を使わず XSS リスクゼロ
- 正規表現で文字列を分割し、マッチ部分のみ `<mark>` タグで囲む
- Tailwind CSS で `<mark>` をスタイリング（`bg-yellow-200 text-gray-900`）
- mark.js や react-highlight-words など外部ライブラリ不要

**Alternatives considered**:

- `react-highlight-words` / `react-highlight`: 機能は揃っているが、わずか数行で自前実装できるため依存追加は不要
- `dangerouslySetInnerHTML`: XSS リスクがあり Constitution 原則 II (Security First) 違反

**Implementation**:

```typescript
const HighlightText = ({ text, query }: { text: string; query: string }) => {
  if (!query) return <span>{text}</span>;
  // RegExp.escape は未サポートのため手動エスケープ
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const parts = text.split(new RegExp(`(${escaped})`, 'gi'));
  return (
    <span>
      {parts.map((part, i) =>
        part.toLowerCase() === query.toLowerCase()
          ? <mark key={i} className="bg-yellow-200 text-gray-900">{part}</mark>
          : <span key={i}>{part}</span>
      )}
    </span>
  );
};
```

---

## 3. フィルター状態管理の設計方針

**Decision**: カスタムフック `useCardSearch` に全フィルター状態を集約する

**Rationale**:

- `CardsPage.tsx` への直接実装よりテスト容易性が高い
- `useMemo` で `displayCards` を計算し、不要な再計算を防ぐ
- `useState` のみで依存ライブラリなし（Redux / Zustand 不要）
- フィルター状態は URL パラメータオプション対応可能な形で設計（今回はメモリのみ）

**Alternatives considered**:

- `CardsContext` に検索状態を追加: グローバル状態に UI 状態が混入するためアンチパターン
- URL パラメータによる状態管理: ブックマーク可能になるがスコープ外（Assumptions）
- Zustand / Jotai: シンプルな検索状態に対してオーバーエンジニアリング

**Hook Interface**:

```typescript
interface UseCardSearchOptions {
  cards: Card[];
}

interface UseCardSearchReturn {
  query: string;
  setQuery: (q: string) => void;
  reviewStatus: ReviewStatusFilter;
  setReviewStatus: (s: ReviewStatusFilter) => void;
  sortBy: SortByOption;
  setSortBy: (s: SortByOption) => void;
  sortOrder: SortOrder;
  setSortOrder: (o: SortOrder) => void;
  filteredCards: Card[];
  reset: () => void;
}
```

---

## 4. カード復習状態の分類ロジック

**Decision**: `Card.repetitions` と `Card.next_review_at` から復習状態を導出する

**Rationale**:

- バックエンドに追加の状態フィールドなし（API 変更不要）
- 既存の `getDueStatus()` ユーティリティを参考に新ロジックを実装

**Status Derivation**:

```typescript
type ReviewStatusFilter = "all" | "due" | "learning" | "new";

const getReviewStatus = (card: Card): "due" | "learning" | "new" => {
  if (card.repetitions === 0) return "new";
  if (card.next_review_at && new Date(card.next_review_at) <= new Date())
    return "due";
  return "learning";
};
```

| 状態       | 条件                                            | 表示名      |
| ---------- | ----------------------------------------------- | ----------- |
| `new`      | `repetitions === 0`                             | 新規        |
| `due`      | `repetitions > 0` かつ `next_review_at <= 今日` | 期日（due） |
| `learning` | `repetitions > 0` かつ `next_review_at > 今日`  | 学習中      |

---

## 5. ソート実装の方針

**Decision**: `Array.prototype.sort()` + 各フィールドのコンパレーター関数で実装

**Rationale**:

- 追加ライブラリ不要
- 500 枚程度のカードなら sort も即時（<1ms）

**Sort Comparators**:

```typescript
type SortByOption = "created_at" | "next_review_at" | "ease_factor";
type SortOrder = "asc" | "desc";

const sortCards = (
  cards: Card[],
  sortBy: SortByOption,
  order: SortOrder,
): Card[] => {
  const sorted = [...cards].sort((a, b) => {
    switch (sortBy) {
      case "created_at":
        return (
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
        );
      case "next_review_at": {
        const aVal = a.next_review_at
          ? new Date(a.next_review_at).getTime()
          : Infinity;
        const bVal = b.next_review_at
          ? new Date(b.next_review_at).getTime()
          : Infinity;
        return aVal - bVal;
      }
      case "ease_factor":
        return a.ease_factor - b.ease_factor;
    }
  });
  return order === "desc" ? sorted.reverse() : sorted;
};
```

---

## 6. パフォーマンス検証

**Decision**: デバウンスは不要。`useMemo` による再計算最適化のみで十分。

**Rationale**:

- ベンチマーク: 500 枚 × `String.prototype.includes` = 約 0.1ms（Chrome V8）
- `normalize('NFKC')` + `toLowerCase()` を含めても <1ms
- React の `useMemo` で `[cards, query, reviewStatus, sortBy, sortOrder]` が変化した時のみ再計算
- デバウンスを追加すると入力の視覚フィードバックが遅れて UX 悪化

**Benchmark Reference**: `Array.filter` on 500 strings with `includes` < 1ms in modern browsers

---

## 7. 既存コードへの影響分析

**CardList.tsx の変更**:

- `highlightQuery?: string` props を追加
- `CardListItem` に `HighlightText` を適用
- 既存テストは後方互換（`highlightQuery` はオプション）

**CardsPage.tsx の変更**:

- `useCardSearch` フックを導入
- 検索・フィルター UI（`SearchBar`, `FilterChips`, `SortSelect`）を追加
- 既存の `displayCards` ロジックを `filteredCards` に置き換え

**変更なし**:

- `CardsContext.tsx`（状態管理はそのまま）
- `services/api.ts`（API 変更なし）
- バックエンドコード全体

---

## まとめ: 全 NEEDS CLARIFICATION 解決

| 課題             | 解決策                                              |
| ---------------- | --------------------------------------------------- |
| 全角・半角正規化 | `normalize('NFKC').toLowerCase()`                   |
| ハイライト実装   | カスタム `HighlightText`（`<mark>` タグ、XSS なし） |
| 状態管理方式     | `useCardSearch` カスタムフック                      |
| 復習状態の分類   | `repetitions` + `next_review_at` から導出           |
| ソートの実装     | `Array.sort` + コンパレーター                       |
| パフォーマンス   | `useMemo` のみで十分（デバウンス不要）              |

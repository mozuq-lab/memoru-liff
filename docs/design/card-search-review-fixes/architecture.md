# card-search-review-fixes アーキテクチャ設計

**作成日**: 2026-03-01
**関連要件定義**: [requirements.md](../../spec/card-search-review-fixes/requirements.md)
**ヒアリング記録**: [design-interview.md](design-interview.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: コードレビュー結果・既存実装を参考にした確実な設計
- 🟡 **黄信号**: 既存実装パターンから妥当な推測による設計

---

## 概要 🔵

フロントエンドのみの修正。新しいコンポーネントやサービスの追加はなく、既存コードの修正・テスト追加・リファクタリングが中心。

## 修正対象ファイルと設計方針

### 1. CardsPage.tsx — FilterChips 条件付き表示 🔵

**信頼性**: 🔵 *REQ-001・既存実装の `activeTab` 変数より*

**現状**: FilterChips が常に表示される。復習対象タブでは `dueCardToCard` が `repetitions: 0` を固定返却するため、フィルターが正しく機能しない。

**設計**:
- `activeTab === "due"` のとき FilterChips を非表示にする
- JSX の条件レンダリング `{activeTab !== "due" && <FilterChips ... />}` で実現

```tsx
{/* 検索・フィルター・ソート */}
<div className="mt-3 flex flex-col gap-2">
  <SearchBar value={query} onChange={setQuery} />
  {activeTab !== "due" && (
    <FilterChips value={reviewStatus} onChange={setReviewStatus} />
  )}
  <SortSelect ... />
</div>
```

**影響範囲**: CardsPage.tsx のみ。他のコンポーネントへの影響なし。

### 2. useCardSearch.ts — reset 関数のメモ化 🔵

**信頼性**: 🔵 *REQ-002・React のメモ化パターンより*

**現状**: `reset` 関数がレンダリングごとに新しい参照を生成。

**設計**:
- `reset` を `useCallback` でラップ
- 依存配列は空 `[]`（setState 関数は安定参照のため）

```ts
const reset = useCallback(() => {
  setQuery("");
  setReviewStatus("all");
  setSortBy("created_at");
  setSortOrder("desc");
}, []);
```

### 3. normalize 関数の共通化 🟡

**信頼性**: 🟡 *REQ-102・DRY 原則から妥当な推測*

**現状**: `useCardSearch.ts` と `HighlightText.tsx` に同一の `normalize` 関数が重複定義。

**設計**:
- `frontend/src/utils/text.ts` を新規作成
- `normalize` 関数をエクスポート
- 両ファイルからインポートに変更

```ts
// frontend/src/utils/text.ts
export const normalize = (str: string): string =>
  str.normalize("NFKC").toLowerCase();
```

### 4. SortSelect.tsx — 型ガードの導入 🟡

**信頼性**: 🟡 *REQ-101・TypeScript ベストプラクティスから妥当な推測*

**現状**: `e.target.value as SortByOption` で強制キャスト。

**設計**:
- `SORT_BY_OPTIONS` 定数の値から型ガード関数を生成
- `onChange` ハンドラで型ガードによるバリデーション

```ts
const isSortByOption = (value: string): value is SortByOption =>
  (["created_at", "next_review_at", "ease_factor"] as string[]).includes(value);
```

### 5. FilterChips.tsx — role 属性の改善 🟡

**信頼性**: 🟡 *REQ-103・WAI-ARIA ベストプラクティスから妥当な推測*

**設計**: `role="group"` → `role="radiogroup"` に変更（排他的選択のセマンティクス）

### 6. useCardSearch.test.ts — デッドコード削除 🔵

**信頼性**: 🔵 *REQ-005・コード分析結果より*

**設計**: `vi.mock('@/utils/date')` ブロックを削除。ただし `normalize` 共通化（REQ-102）後のインポートパスに注意。

## テスト設計

### CardsPage.test.tsx 統合テスト 🔵

**信頼性**: 🔵 *REQ-003・既存テストパターンより*

**モック構成**: 既存の `vi.mock('@/contexts/CardsContext')` パターンを踏襲し、`cards` と `dueCards` のモックデータを用意。

**テストケース**:

| ID | テスト内容 | 関連要件 |
|----|-----------|---------|
| CP-S01 | 検索バーが表示される | REQ-003 |
| CP-S02 | 検索バー入力でカードがフィルタリングされる | REQ-003 |
| CP-S03 | 検索0件時に「該当するカードがありません」が表示される | REQ-003 |
| CP-S04 | FilterChips でカードがフィルタリングされる | REQ-003 |
| CP-S05 | タブ切替時にフィルター状態がリセットされる | REQ-003 |
| CP-S06 | 復習対象タブでは FilterChips が非表示 | REQ-001 |

### CardList.test.tsx 統合テスト 🔵

**信頼性**: 🔵 *REQ-004・既存テストパターンより*

| ID | テスト内容 | 関連要件 |
|----|-----------|---------|
| CL-H01 | highlightQuery でマッチ部分に mark タグが表示される | REQ-004 |
| CL-H02 | highlightQuery が空文字で mark タグが表示されない | REQ-004 |

## 信頼性レベルサマリー

- 🔵 青信号: 8件 (67%)
- 🟡 黄信号: 4件 (33%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質

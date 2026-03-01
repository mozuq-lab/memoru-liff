# card-search-review-fixes データフロー図

**作成日**: 2026-03-01
**関連アーキテクチャ**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/card-search-review-fixes/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: コードレビュー結果・既存実装を参考にした確実なフロー
- 🟡 **黄信号**: 既存実装パターンから妥当な推測によるフロー

---

## フロー1: FilterChips 条件付き表示 🔵

**信頼性**: 🔵 *REQ-001・既存 CardsPage.tsx の activeTab ロジックより*

```mermaid
flowchart TD
    A[ユーザーがタブを選択] --> B{activeTab}
    B -->|"due"| C[SearchBar + SortSelect のみ表示]
    B -->|"all"| D[SearchBar + FilterChips + SortSelect 表示]
    C --> E[resetSearch 呼び出し]
    D --> E
    E --> F[filteredCards 再計算]
    F --> G[CardList 表示更新]
```

**変更前**: FilterChips は両タブで常に表示
**変更後**: `activeTab === "due"` のとき FilterChips を非表示

## フロー2: useCardSearch フィルタリングパイプライン（変更なし） 🔵

**信頼性**: 🔵 *既存実装より（本修正ではロジック変更なし）*

```mermaid
flowchart LR
    A[cards 配列] --> B[クエリフィルター]
    B --> C[reviewStatus フィルター]
    C --> D[ソート]
    D --> E[filteredCards]
```

**注意**: フロー2 自体に変更はないが、フロー1 により「復習対象タブでは reviewStatus フィルターが `all` 固定」となる。

## フロー3: normalize 関数の共通化 🟡

**信頼性**: 🟡 *REQ-102・DRY 原則より*

```mermaid
flowchart TD
    subgraph 変更前
        A1[useCardSearch.ts] --> N1["normalize() 定義"]
        A2[HighlightText.tsx] --> N2["normalize() 定義（重複）"]
    end

    subgraph 変更後
        B0[utils/text.ts] --> N3["normalize() 定義"]
        B1[useCardSearch.ts] --> N3
        B2[HighlightText.tsx] --> N3
    end
```

## 信頼性レベルサマリー

- 🔵 青信号: 2件 (67%)
- 🟡 黄信号: 1件 (33%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質

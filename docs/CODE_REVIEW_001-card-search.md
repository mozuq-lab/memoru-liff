# コードレビュー: `001-card-search` ブランチ

**レビュー日**: 2026-02-28
**レビュアー**: GitHub Copilot (Claude Opus 4.6) + Codex
**対象ブランチ**: `001-card-search` (8 commits, +6,587 / -7 lines)
**スコープ**: フロントエンドのみ（バックエンド変更なし）

---

## 概要

カード一覧画面にキーワード検索・復習状態フィルター・ソート機能を追加するフロントエンド専用の変更。新規 9 ファイル・変更 4 ファイル。TDD で実装され、全 48 テスト（新規分）・391 テスト（全体）が合格。TypeScript 型エラーなし、リグレッションなし。

## テスト実行結果

| 項目 | 結果 |
|------|------|
| 新規テスト | 48/48 合格 |
| 全体テスト | 391/391 合格 (32 files) |
| TypeScript 型チェック | エラーなし |
| リグレッション | なし |

---

## 指摘事項

### \[H-1\] Critical: `due` 判定が時刻付き ISO 文字列で誤判定する

- **ファイル**: `frontend/src/hooks/useCardSearch.ts` L42, L57
- **レビュアー**: Codex + Copilot (関連)
- **仕様根拠**: spec.md US2 AS-1「今日以前に次回復習日が設定されているカード」、data-model.md「`next_review_at <= 今日` → due」

**問題**: `getReviewStatus()` で `card.next_review_at <= today` を文字列比較しているが、`today` は `new Date().toISOString().slice(0, 10)` で `"2026-02-28"`（10文字）、一方 API は `datetime.isoformat()` で `"2026-02-28T00:00:00"` 形式を返す。

文字列比較では **今日の日付を持つ時刻付き文字列は today より大きい** と判定される：

```
"2026-02-28T00:00:00" <= "2026-02-28"  → false  (本来 due であるべき)
"2026-02-28T23:59:59" <= "2026-02-28"  → false  (本来 due であるべき)
"2026-02-27T15:00:00" <= "2026-02-28"  → true   (正しい)
```

**影響**: 「今日が期日」のカードが `due` ではなく `learning` に分類される。`FilterChips` で `due` を選んでも今日期限のカードが表示されない。

**修正案**:

```typescript
// 比較前に日付部分のみ抽出して統一する
const getReviewStatus = (card: Card, today: string): ReviewStatusFilter => {
  if (card.repetitions === 0) return 'new';
  if (card.next_review_at && card.next_review_at.slice(0, 10) <= today) return 'due';
  return 'learning';
};
```

---

### \[H-2\] High: `next_review_at` 降順ソートで `null` が先頭に来る（仕様は末尾）

- **ファイル**: `frontend/src/hooks/useCardSearch.ts` L87-L93
- **レビュアー**: Codex + Copilot (関連)
- **仕様根拠**: tasks.md「`next_review_at` null 処理: null は sort 末尾扱い」、research.md §5

**問題**: `null` を `'\uFFFF'`（最大文字）に置換して昇順で末尾にしている。しかし降順時は `return -comparison` で符号反転するため、`null` が**先頭**に移動する。

**実行確認済み**:

```
desc order: [ 'B=null', 'C=2026-03-30', 'A=2026-02-01' ]
// 期待: [ 'C=2026-03-30', 'A=2026-02-01', 'B=null' ]
```

**テスト不足**: 降順 + `null` のテストケースが存在しない（昇順のみ）。

**修正案**:

```typescript
} else if (sortBy === 'next_review_at') {
  // null は常に末尾
  if (a.next_review_at === null && b.next_review_at === null) return 0;
  if (a.next_review_at === null) return 1;  // a を後ろへ（sortOrder 不問）
  if (b.next_review_at === null) return -1; // b を後ろへ（sortOrder 不問）
  comparison = a.next_review_at.localeCompare(b.next_review_at);
}

// null 処理がソート方向に影響されないよう、null 分岐は符号反転の前に return する
```

---

### \[H-3\] High: `HighlightText` の NFKC 正規化で文字長が変わるとハイライト範囲がずれる

- **ファイル**: `frontend/src/components/HighlightText.tsx` L44-L50
- **レビュアー**: Codex + Copilot

**問題**: 正規化後のテキスト上のインデックスを**元テキスト**の `slice()` にそのまま使用している。NFKC 正規化で文字数が変わるケース（例: `㌔` → `キロ` で 1文字 → 2文字、`ﬁ` → `fi` で 1文字 → 2文字）では、`text.slice(index, index + query.length)` で正しい範囲を切り出せない。

```tsx
// 現在のコード（L44-L50）
parts.push(
  <mark key={index}>
    {text.slice(index, index + query.length)}  // ← index は正規化後の位置
  </mark>
);
lastIndex = index + normalizedQuery.length;
```

**影響度**: 学習カードのテキストで CJK 互換文字（㌔, ㌢, ㍉ 等）やラテン合字（ﬁ, ﬂ 等）が使われることは稀なため、**実害の発生確率は低い**。ただしエッジケースとしてバグは確実に存在する。

**修正案**: 元テキストと正規化テキストのインデックスマッピングを構築する。

```typescript
// 元テキスト⇔正規化テキストの文字位置マッピングを構築
const buildIndexMap = (original: string): number[] => {
  const map: number[] = [];
  for (let i = 0; i < original.length; i++) {
    const charNormalized = original[i].normalize('NFKC');
    for (let j = 0; j < charNormalized.length; j++) {
      map.push(i);  // 正規化後の各文字 → 元テキストの文字位置
    }
  }
  return map;
};
```

---

### \[M-1\] Medium: 検索 0 件時の空状態メッセージが検索を考慮していない

- **ファイル**: `frontend/src/pages/CardsPage.tsx` L176-L179
- **レビュアー**: Copilot
- **仕様根拠**: spec.md FR-007「検索結果が0件の場合、空状態メッセージを表示」、US1 AS-3「該当するカードがありません」

**問題**: 空状態メッセージが `activeTab` のみで分岐しており、検索キーワードの有無を考慮していない。検索で 0 件になった場合も「カードがありません」と表示され、ユーザーが「検索結果がないのか」「本当にカードがないのか」を区別できない。

**修正案**:

```tsx
<p className="text-gray-600 mb-4">
  {query
    ? '該当するカードがありません'
    : activeTab === 'due'
      ? '復習対象のカードはありません'
      : 'カードがありません'}
</p>
```

---

### \[M-2\] Medium: タブ（due/all）と `FilterChips`（due）の二重フィルタリング

- **ファイル**: `frontend/src/pages/CardsPage.tsx` L37
- **レビュアー**: Copilot

**問題**: タブ「復習対象」で表示されるカードは API レベルで due のみのリスト（`dueCards`）。一方 `FilterChips` にも `due` フィルターがある。ユーザーが「復習対象」タブ + `FilterChips` の `due` で二重フィルタリングしても実害はないが、「復習対象」タブ + `FilterChips` の `new` を選ぶと結果が常に 0 件になるなど、UX が混乱する。

**対策案**: タブ切り替え時に `useCardSearch` の `reviewStatus` を `'all'` にリセットする、または「復習対象」タブでは `FilterChips` を非表示にする。

---

### \[L-1\] Low: テストの日付依存（`vi.useFakeTimers()` 未使用）

- **ファイル**: `frontend/src/hooks/__tests__/useCardSearch.test.ts` L14-16
- **レビュアー**: Copilot + Codex (関連)

**問題**: `TODAY = '2026-02-28'` をハードコードし、`Date` をモックしていない。`useCardSearch` 内の `new Date()` はテスト実行日の実際の日付を返す。テスト実行日が変わると `due` / `learning` の分類結果が変動する可能性がある。

**対策**: `vi.useFakeTimers()` + `vi.setSystemTime()` で日付を固定する。

---

### \[L-2\] Low: `SortSelect` の `as SortByOption` 型キャスト

- **ファイル**: `frontend/src/components/SortSelect.tsx` L49
- **レビュアー**: Copilot

**問題**: `e.target.value as SortByOption` で型安全を迂回している。`<option>` の値は `SORT_BY_OPTIONS` 定数から生成されるため実害はないが、将来オプション変更時のリスクがある。バリデーション付き変換関数を検討可。

---

### \[L-3\] Low: `FilterChips` の WAI-ARIA ロール

- **ファイル**: `frontend/src/components/FilterChips.tsx` L33
- **レビュアー**: Copilot

**問題**: 単一選択のチップグループに `role="group"` を使用。セマンティクス的には `role="radiogroup"` + `role="radio"` がより正確。ただし `aria-pressed` を使った `button` パターンも WCAG 準拠で問題ない。

---

### \[L-4\] Low: `useMemo` 内の `today` が依存配列に含まれない

- **ファイル**: `frontend/src/hooks/useCardSearch.ts` L57
- **レビュアー**: Copilot

**問題**: `const today = new Date().toISOString().slice(0, 10)` が `useMemo` 内で計算されるが依存配列に含まれない。日付をまたぐ長時間セッションで `due` 判定が古い日付を使い続ける可能性がある。ただし、他の依存 state が更新される度に再計算されるため実害は極めて低い。意図を明確にするコメント追加を推奨。

---

## 良い点

1. **設計文書の充実** — spec → research → data-model → contracts → plan → tasks の流れが整然として、設計と実装のトレーサビリティが高い
2. **TDD の徹底** — テスト ID（HT-001〜HT-006 等）がコントラクト文書と 1:1 対応し、受け入れ条件の検証が明確
3. **XSS 安全** — `HighlightText` で `dangerouslySetInnerHTML` を使わず React JSX レンダリング + `<mark>` タグで実装。HT-005 テストでも検証済み
4. **アクセシビリティ** — `aria-pressed`、`aria-label`、`role="searchbox"`、`role="group"` が適切に付与
5. **後方互換性** — `CardList` の `highlightQuery` はオプショナルで既存利用箇所に影響なし。バックエンド変更なし
6. **NFKC 正規化** — 全角・半角・大小文字を統一処理しており、日本語環境の要件に対応
7. **パフォーマンス** — `useMemo` の適切な使用でフィルタリングの再計算を最小化

---

## 総合評価

| 観点 | 評価 | コメント |
|------|------|----------|
| 設計・アーキテクチャ | ◎ | 文書・コード構造とも優秀 |
| コード品質 | ○ | 3 件のバグを除きクリーン |
| テストカバレッジ | ○ | 48 テスト合格。ただしエッジケース不足あり |
| セキュリティ | ◎ | XSS 対策確認済み |
| アクセシビリティ | ○ | WAI-ARIA 概ね適切 |
| パフォーマンス | ◎ | useMemo 適切使用 |
| 後方互換性 | ◎ | 破壊的変更なし |

---

## マージ判定

**条件付き承認**: H-1, H-2 を修正し、対応するテストケースを追加すればマージ可能。

| 指摘 | 必須/推奨 | 対応タイミング |
|------|-----------|----------------|
| H-1 (due 判定の時刻付き ISO) | **修正必須** | マージ前 |
| H-2 (null 降順ソート) | **修正必須** | マージ前 |
| H-3 (HighlightText NFKC) | 推奨 | マージ前 or フォローアップ |
| M-1 (空状態メッセージ) | 推奨 | フォローアップ可 |
| M-2 (タブ/フィルター二重) | 推奨 | フォローアップ可 |
| L-1〜L-4 | 任意 | フォローアップ可 |

### 追加すべきテストケース

1. **H-1 用**: 時刻付き ISO 文字列（`"2026-02-28T00:00:00"`）のカードが `due` に分類されること
2. **H-2 用**: `sortBy='next_review_at'`, `sortOrder='desc'` で `null` が末尾に来ること
3. **H-3 用**: NFKC で文字長が変わる文字（㌔ 等）のハイライトが正しいこと

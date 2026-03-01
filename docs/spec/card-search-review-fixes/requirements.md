# card-search-review-fixes 要件定義書（軽量版）

**作成日**: 2026-03-01
**ブランチ**: `001-card-search`
**対象PR**: #2 feat: カード検索機能（キーワード検索・フィルター・ソート）

## 概要

PR #2 のコードレビューで発見された問題点（Critical 2件、Major 3件、Minor 3件）を修正する。
主な修正は「復習対象タブでの FilterChips 動作不整合」「`reset` 関数のメモ化」「統合テストの追加」「コードクリーンアップ」。

## 関連文書

- **ヒアリング記録**: [💬 interview-record.md](interview-record.md)
- **元仕様書**: `specs/001-card-search/spec.md`（`001-card-search` ブランチ上）
- **元レビュー結果**: `docs/CODE_REVIEW_001-card-search.md`（`001-card-search` ブランチ上）

## 主要機能要件

**【信頼性レベル凡例】**:
- 🔵 **青信号**: コードレビュー結果・既存実装を参考にした確実な要件
- 🟡 **黄信号**: 既存実装パターンから妥当な推測による要件
- 🔴 **赤信号**: 推測による要件

### 必須修正（Must Have）

- **REQ-001**: 復習対象（due）タブ選択時、FilterChips コンポーネントを非表示にしなければならない 🔵 *C-1: `dueCardToCard` が `repetitions: 0` 固定のため、FilterChips のフィルタが正しく機能しない*
  - **理由**: `CardsContext.tsx` の `dueCardToCard` が `repetitions: 0` を固定で返すため、すべての due カードが `new` と判定され、`due` フィルターで全件非表示になる
  - **対象ファイル**: `frontend/src/pages/CardsPage.tsx`

- **REQ-002**: `useCardSearch` フックの `reset` 関数を `useCallback` でメモ化しなければならない 🔵 *C-2: レンダリングごとに新しい関数参照が生成され、依存配列に入れた際の無限ループリスク*
  - **対象ファイル**: `frontend/src/hooks/useCardSearch.ts`

- **REQ-003**: `CardsPage.test.tsx` に検索機能の統合テストを追加しなければならない 🔵 *M-1: 本PRの主要変更（SearchBar・FilterChips・SortSelect）の統合テストがゼロ*
  - テストケース:
    - 検索バーが表示される
    - 検索バーに入力するとカードがフィルタリングされる
    - 検索0件時に「該当するカードがありません」が表示される
    - フィルターチップを押すとカードがフィルタリングされる
    - タブ切替時にフィルターがリセットされる
    - 復習対象タブでは FilterChips が非表示
  - **対象ファイル**: `frontend/src/pages/__tests__/CardsPage.test.tsx`

- **REQ-004**: `CardList.test.tsx` に `highlightQuery` prop のテストを追加しなければならない 🔵 *M-2: CardList に追加された highlightQuery の統合テストが存在しない*
  - テストケース:
    - `highlightQuery` を渡すと `<mark>` タグが表示される
    - `highlightQuery` が空文字だと `<mark>` タグが表示されない
  - **対象ファイル**: `frontend/src/components/__tests__/CardList.test.tsx`（`001-card-search` ブランチ上）

- **REQ-005**: `useCardSearch.test.ts` のデッドな `vi.mock('@/utils/date')` ブロックを削除しなければならない 🔵 *M-3: 実際のモジュールをそのまま返すだけのモックで、useCardSearch.ts 自体がこのモジュールを使用していない*
  - **対象ファイル**: `frontend/src/hooks/__tests__/useCardSearch.test.ts`

### 推奨修正（Should Have）

- **REQ-101**: `SortSelect` の `e.target.value as SortByOption` 型キャストを型ガードに置き換えるべきである 🟡 *Mi-1: 型安全の迂回。将来のオプション変更時にコンパイルエラーが出ないリスク*
  - **対象ファイル**: `frontend/src/components/SortSelect.tsx`

- **REQ-102**: `normalize` 関数を `useCardSearch.ts` と `HighlightText.tsx` から共通ユーティリティに抽出すべきである 🟡 *Mi-2: 同一実装の重複定義。正規化ロジック変更時の保守性に影響*
  - **抽出先**: `frontend/src/utils/text.ts`（新規作成）
  - **対象ファイル**: `frontend/src/hooks/useCardSearch.ts`, `frontend/src/components/HighlightText.tsx`

- **REQ-103**: `FilterChips` の `role="group"` を `role="radiogroup"` に変更すべきである 🟡 *Mi-3: 排他的選択のセマンティクス。WCAG違反ではないがスクリーンリーダーの利用者体験を改善*
  - **対象ファイル**: `frontend/src/components/FilterChips.tsx`

### 基本的な制約

- **REQ-401**: 修正は `001-card-search` ブランチ上で行い、既存の391テストを破壊してはならない 🔵 *既存テストの全パスを維持*
- **REQ-402**: TypeScript の型チェック（`npm run type-check`）がエラーなしで通らなければならない 🔵

## 簡易ユーザーストーリー

### ストーリー1: 復習対象タブでの FilterChips 非表示

**私は** カード学習者 **として**
**復習対象タブで混乱なくカードを閲覧したい**
**そうすることで** フィルター操作で意図しない結果（全件非表示等）を避けられる

**関連要件**: REQ-001, REQ-003

### ストーリー2: 統合テストによる品質担保

**私は** 開発者 **として**
**検索・フィルター・ソート機能のページレベル統合テストを持ちたい**
**そうすることで** リグレッションを早期に検知できる

**関連要件**: REQ-003, REQ-004

## 基本的な受け入れ基準

### REQ-001: 復習対象タブでの FilterChips 非表示

**Given**: カード一覧画面が表示されている
**When**: 「復習対象」タブを選択する
**Then**: FilterChips コンポーネントが非表示になる

**Given**: カード一覧画面の「復習対象」タブが選択されている
**When**: 「すべて」タブに切り替える
**Then**: FilterChips コンポーネントが表示される

### REQ-002: reset 関数のメモ化

**Given**: `useCardSearch` フックが使用されている
**When**: コンポーネントが再レンダリングされる
**Then**: `reset` 関数の参照が維持される（`useCallback` による安定参照）

### REQ-003: CardsPage 統合テスト

**テストケース**:
- [ ] 検索バーが画面に表示される
- [ ] 検索バー入力でカードがフィルタリングされる
- [ ] 検索0件時に「該当するカードがありません」が表示される
- [ ] FilterChips でカードがフィルタリングされる
- [ ] タブ切替時にフィルター状態がリセットされる
- [ ] 復習対象タブでは FilterChips が非表示

### REQ-004: CardList highlightQuery テスト

**テストケース**:
- [ ] `highlightQuery` prop でマッチ部分に `<mark>` タグが表示される
- [ ] `highlightQuery` が空文字で `<mark>` タグが表示されない

## 最小限の非機能要件

- **パフォーマンス**: 既存の SC-001（300ms以内のフィルタリング応答）を維持 🔵 *spec.md SC-001 より*
- **アクセシビリティ**: `role="radiogroup"` への変更で ARIA セマンティクスを改善 🟡

## 信頼性レベルサマリー

- 🔵 **青信号**: 7件（REQ-001〜005, REQ-401〜402）— コードレビュー・既存実装から確実
- 🟡 **黄信号**: 3件（REQ-101〜103）— 既存パターンから妥当な推測
- 🔴 **赤信号**: 0件

**品質評価**: ✅ 高品質

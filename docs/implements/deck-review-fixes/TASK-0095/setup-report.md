# TASK-0095 設定作業実行

## 作業概要

- **タスクID**: TASK-0095
- **作業内容**: DeckSelector.tsx と DeckSummary.tsx から不要な `d.deck_id !== 'unassigned'` フィルタリング削除
- **実行日時**: 2026-03-01
- **実行者**: Claude Code

## 設計文書参照

- **参照文書**: docs/tasks/deck-review-fixes/TASK-0095.md
- **関連要件**: REQ-403

## 実行した作業

### 1. DeckSelector.tsx の修正

`regularDecks` 変数（`decks.filter((d) => d.deck_id !== 'unassigned')` によるフィルタリング）を削除し、`decks` を直接使用するよう変更。

**変更箇所**:
- `const regularDecks = decks.filter((d) => d.deck_id !== 'unassigned');` 行を削除
- コメント `// 「未分類」疑似デッキを除外` を削除
- `regularDecks.map(...)` → `decks.map(...)` に変更
- `regularDecks.find(...)` → `decks.find(...)` に変更

### 2. DeckSummary.tsx の修正

同様に `regularDecks` 変数を削除し、`decks` を直接使用するよう変更。

**変更箇所**:
- `const regularDecks = decks.filter((d) => d.deck_id !== 'unassigned');` 行を削除
- コメント `// 「未分類」疑似デッキを除外` を削除
- `regularDecks.length === 0` → `decks.length === 0` に変更
- `regularDecks.slice(0, MAX_DISPLAY_DECKS)` → `decks.slice(0, MAX_DISPLAY_DECKS)` に変更
- `regularDecks.length > MAX_DISPLAY_DECKS` → `decks.length > MAX_DISPLAY_DECKS` に変更

## 作業結果

- [x] `DeckSelector.tsx` から `'unassigned'` フィルタ削除
- [x] `DeckSummary.tsx` から `'unassigned'` フィルタ削除

## 次のステップ

- `/tsumiki:direct-verify` を実行してテストを確認

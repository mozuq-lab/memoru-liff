# TDD開発メモ: cards-page-deck-filter

## 確認すべきドキュメント

- `docs/tasks/deck-review-fixes/TASK-0091.md`
- `docs/implements/deck-review-fixes/TASK-0091/cards-page-deck-filter-requirements.md`
- `docs/implements/deck-review-fixes/TASK-0091/cards-page-deck-filter-testcases.md`

## 🎯 最終結果 (2026-03-01)

- **実装率**: 100% (45/45 テストケース)
- **品質判定**: 合格 ✅
- **要件網羅率**: 100%（8/8 完了条件すべて達成）
- **TODO更新**: ✅ 完了マーク追加済み

## 💡 重要な技術学習

### 実装パターン

- **setSearchParams の既存パラメータ保持**: `setSearchParams({tab: 'due'})` は既存の `deck_id` を失う。`Record<string, string>` に既存パラメータを引き継いでから呼ぶパターンが必要
  ```typescript
  const newParams: Record<string, string> = {};
  if (deckId) newParams['deck_id'] = deckId;
  if (tab === 'due') newParams['tab'] = 'due';
  setSearchParams(newParams);
  ```
- **searchParams の falsy 変換**: `searchParams.get('deck_id') || undefined` で空文字列を undefined に変換し、フィルタなしと同等に扱う
- **useCallback 依存配列に deckId を追加**: `handleRetry` など deckId を使う関数は依存配列への追加が必要

### テスト設計

- **MemoryRouter の initialEntries**: `{ pathname: '/cards', search: '?deck_id=deck-abc-123' }` 形式でクエリパラメータ付き URL をテスト
- **DecksContext のモック**: `useDecksContext` を vi.mock でモックし、デッキ名検索のテストを実現
- **Refactor フェーズで 3 件追加**: TC-091-B03（タブ切り替え保持）、TC-091-N01/N02（NFR-201 ナビゲーション）

### 品質保証

- **既存テスト 31 件が全通過**: TASK-0091 実装後も CardsContext・CardsPage の既存テストが全通過。後方互換性を完全維持
- **全体テスト失敗（GeneratePage・HomePage）は別問題**: DecksProvider が未追加という TASK-0091 とは無関係の既存問題

## テスト結果サマリー

| カテゴリ | テスト数 | 状態 |
|---------|---------|------|
| CardsContext（既存） | 14 | ✅ |
| CardsPage（既存） | 17 | ✅ |
| TASK-0091 新規（Red/Green） | 14 | ✅ |
| TASK-0091 新規（Refactor） | 3 | ✅ |
| **合計（対象ファイル）** | **45** | ✅ |

## 変更ファイル

| ファイル | 変更内容 |
|---------|---------|
| `frontend/src/services/api.ts` | `getCards(deckId?: string)` 追加、URLSearchParams でクエリ構築 |
| `frontend/src/contexts/CardsContext.tsx` | `fetchCards(deckId?)` / `fetchDueCards(deckId?)` シグネチャ変更 |
| `frontend/src/pages/CardsPage.tsx` | useSearchParams 読み取り、deckId 伝搬、デッキ名ヘッダー、NFR-201 リンク、setActiveTab/handleRetry 修正 |
| `frontend/src/pages/__tests__/CardsPage.test.tsx` | TASK-0091 テスト 17 件追加（Red 10 件 + Refactor 3 件 + 後追い追加） |
| `frontend/src/__tests__/CardsContext.test.tsx` | TASK-0091 テスト 4 件追加（TC-091-001〜004） |

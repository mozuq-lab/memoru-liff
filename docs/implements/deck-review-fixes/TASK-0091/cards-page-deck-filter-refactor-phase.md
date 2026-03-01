# TASK-0091: cards-page-deck-filter Refactor フェーズ記録

**作成日時**: 2026-03-01
**フェーズ**: Refactor（品質改善）

---

## リファクタリング概要

Green フェーズで特定した 3 つの課題をすべて解決し、テストも追加した。

| 改善 | 内容 | 信頼性 |
|------|------|--------|
| 改善1 | `setActiveTab` でタブ切り替え時に `deck_id` パラメータを保持 | 🟡 |
| 改善2 | `handleRetry` に `deckId` を渡してエラー後の再取得もフィルタを維持 | 🔵 |
| 改善3 | NFR-201: deck_id 指定時の「全カードを表示」リンク追加 | 🟡 |

---

## セキュリティレビュー結果

- **XSS**: JSX のテキスト出力は React が自動エスケープ - 問題なし 🔵
- **URL パラメータ検証**: `searchParams.get('deck_id') || undefined` で falsy 変換済み - 問題なし 🔵
- **バックエンドバリデーション**: `deck_id` は文字列として API に渡すのみ、バックエンドで検証する設計 - フロント側は問題なし 🔵

**重大な脆弱性**: なし

---

## パフォーマンスレビュー結果

- **deckName 計算**: `decks.find(d => d.deck_id === deckId)` は O(n) だが、デッキ数は通常少数で許容範囲 🟡
- **useCallback 依存配列**: `handleRetry` の依存配列に `deckId` を追加したことで、`deckId` 変更時に適切に再生成される 🔵
- **setActiveTab**: `Record<string, string>` オブジェクト生成は毎レンダリングだが、問題なし 🔵

**重大なパフォーマンス課題**: なし

---

## 改善1: `setActiveTab` での `deck_id` 保持

### 変更前（Green フェーズ）

```typescript
const setActiveTab = (tab: TabType) => {
  if (tab === 'due') {
    setSearchParams({ tab: 'due' });
  } else {
    setSearchParams({});
  }
};
```

**問題**: `setSearchParams({tab: 'due'})` や `setSearchParams({})` で呼び出すと、既存の `deck_id` パラメータが失われる。

### 変更後（Refactor フェーズ）

```typescript
/**
 * 【機能概要】: アクティブタブを切り替える
 * 【改善内容】: setSearchParams でタブ変更時に既存の deck_id パラメータを保持するよう修正
 * 【設計方針】: deck_id が指定されている場合は新しいパラメータオブジェクトにも deck_id を含める
 * 【保守性】: URL パラメータの意図的な分離（tab: タブ状態, deck_id: フィルタ条件）
 * 🟡 黄信号: Green フェーズ課題1（setSearchParams が deck_id を失う問題）の修正
 */
const setActiveTab = (tab: TabType) => {
  // 【既存パラメータ保持】: deck_id が指定されている場合は新しい searchParams にも引き継ぐ
  // 【タブ切り替え】: tab=due 以外はタブパラメータを削除（'all' がデフォルト）
  const newParams: Record<string, string> = {};
  if (deckId) newParams['deck_id'] = deckId;
  if (tab === 'due') newParams['tab'] = 'due';
  setSearchParams(newParams);
};
```

**信頼性**: 🟡 黄信号（Green フェーズ課題1の修正）

### 追加テスト: TC-091-B03

```typescript
it('TC-091-B03: タブ切り替え後も URL の deck_id パラメータが保持される', async () => {
  render(
    <MemoryRouter initialEntries={[{ pathname: '/cards', search: '?deck_id=deck-abc-123' }]}>
      <CardsPage />
    </MemoryRouter>
  );

  const dueTab = screen.getByTestId('tab-due');
  fireEvent.click(dueTab);

  expect(mockFetchDueCards).toHaveBeenCalledWith('deck-abc-123');
});
```

---

## 改善2: `handleRetry` に `deckId` を渡す修正

### 変更前（Green フェーズ）

```typescript
// 【再取得ハンドラ】
const handleRetry = useCallback(() => {
  if (activeTab === 'due') {
    fetchDueCards();
  } else {
    fetchCards();
  }
}, [activeTab, fetchCards, fetchDueCards]);
```

**問題**: エラー後の再取得で `deckId` が渡されず、全カードが取得される。

### 変更後（Refactor フェーズ）

```typescript
/**
 * 【機能概要】: エラー発生後の再取得ハンドラ
 * 【改善内容】: deckId を引数として渡すよう修正（Green フェーズ課題2）
 * 【設計方針】: エラー後の再取得でも deck_id フィルタを維持する
 * 🔵 青信号: Green フェーズ課題2（handleRetry が deckId なし）の修正
 */
const handleRetry = useCallback(() => {
  // 【再取得】: deckId を引数として渡し、フィルタ条件を維持したまま再取得する
  if (activeTab === 'due') {
    fetchDueCards(deckId);
  } else {
    fetchCards(deckId);
  }
}, [activeTab, deckId, fetchCards, fetchDueCards]);
```

**信頼性**: 🔵 青信号（Green フェーズ課題2の明確な修正）

---

## 改善3: NFR-201「全カードを表示」ナビゲーション追加

### 変更箇所

```typescript
{/* 【NFR-201】: deck_id 指定時に全カード一覧への「戻る」ナビゲーションを提供 */}
{/* 🟡 黄信号: NFR-201 ユーザビリティ要件より */}
{deckId && (
  <Link
    to="/cards"
    className="text-sm text-blue-600 hover:text-blue-700"
    data-testid="back-to-all-cards"
  >
    全カードを表示
  </Link>
)}
```

**信頼性**: 🟡 黄信号（NFR-201 ユーザビリティ要件）

### 追加テスト: TC-091-N01, TC-091-N02

```typescript
describe('NFR-201: 全カードへの戻るナビゲーション', () => {
  it('TC-091-N01: deck_id 指定時に「全カードを表示」リンクが表示される', () => {
    render(
      <MemoryRouter initialEntries={[{ pathname: '/cards', search: '?deck_id=deck-abc-123' }]}>
        <CardsPage />
      </MemoryRouter>
    );

    const backLink = screen.getByTestId('back-to-all-cards');
    expect(backLink).toBeInTheDocument();
    expect(backLink).toHaveAttribute('href', '/cards');
  });

  it('TC-091-N02: deck_id 未指定時に「全カードを表示」リンクが表示されない', () => {
    render(
      <MemoryRouter initialEntries={[{ pathname: '/cards', search: '' }]}>
        <CardsPage />
      </MemoryRouter>
    );

    expect(screen.queryByTestId('back-to-all-cards')).not.toBeInTheDocument();
  });
});
```

---

## テスト実行結果

```
実行コマンド:
cd frontend && npx vitest run --reporter=verbose src/pages/__tests__/CardsPage.test.tsx src/__tests__/CardsContext.test.tsx

Test Files: 2 passed (2)
Tests: 45 passed (45)
Duration: 1.72s
```

### テスト内訳

| カテゴリ | テスト数 | 状態 |
|---------|---------|------|
| CardsContext（既存） | 14 | ✅ |
| CardsPage（既存） | 17 | ✅ |
| TASK-0091 新規（Green） | 14 | ✅ |
| TASK-0091 新規（Refactor） | 3 | ✅ |
| **合計** | **45** | ✅ |

---

## 変更ファイルまとめ

| ファイル | 変更内容 | 行数 |
|---------|---------|------|
| `frontend/src/pages/CardsPage.tsx` | setActiveTab 修正、handleRetry 修正、NFR-201 リンク追加 | 239行 |
| `frontend/src/pages/__tests__/CardsPage.test.tsx` | TC-091-B03, TC-091-N01, TC-091-N02 追加 | 510行 |

---

## 品質判定

```
✅ 高品質:
- テスト結果: 全 45 件通過（Green から +3 件追加）
- セキュリティ: 重大な脆弱性なし
- パフォーマンス: 重大な性能課題なし
- リファクタ品質: Green フェーズの 3 課題すべて解決
- コード品質: 日本語コメント充実、責務明確
- ファイルサイズ: CardsPage 239 行（500 行制限以内）
- モック使用: 実装コードにモック・スタブなし
```

---

## 信頼性レベルサマリー

| 改善内容 | 信頼性 | 根拠 |
|---------|--------|------|
| setActiveTab 修正 | 🟡 | Green フェーズ課題1から妥当な推測 |
| handleRetry 修正 | 🔵 | Green フェーズ課題2の明確な修正 |
| NFR-201 リンク追加 | 🟡 | NFR-201 ユーザビリティ要件より |
| テスト TC-091-B03 | 🟡 | テストケース定義 TC-091-B03 より |
| テスト TC-091-N01/N02 | 🟡 | NFR-201 から妥当な推測 |

# TASK-0091: cards-page-deck-filter Red フェーズ記録

**作成日時**: 2026-03-01
**フェーズ**: Red（失敗するテスト作成）
**担当**: TDD Red フェーズ

---

## 作成したテストケース一覧

### CardsPage テスト（frontend/src/pages/__tests__/CardsPage.test.tsx 追記）

| テスト ID | テスト名 | 信頼性 | 結果 |
|----------|---------|--------|------|
| TC-091-005 | URL に deck_id パラメータがある場合に fetchCards(deckId) が呼ばれる | 🔵 | 失敗（期待通り） |
| TC-091-006 | URL に deck_id がない場合に fetchCards() が引数なしで呼ばれる | 🔵 | 失敗（期待通り） |
| TC-091-007 | deck_id 指定時にヘッダーにデッキ名が表示される | 🟡 | 失敗（期待通り） |
| TC-091-008 | deck_id 未指定時にヘッダーが「カード一覧」を表示する | 🔵 | 通過（既存動作確認） |
| TC-091-009 | deck_id 指定時にタブが due の場合、fetchDueCards(deckId) が呼ばれる | 🟡 | 失敗（期待通り） |
| TC-091-B02 | deck_id と tab=due の両方が指定された場合に正しくフィルタされる | 🟡 | 失敗（期待通り） |
| TC-091-E01 | 存在しない deck_id で空のカード一覧が表示される | 🟡 | 通過（既存動作確認） |
| TC-091-E02 | DecksContext にデッキ情報がない場合のヘッダー表示フォールバック | 🟡 | 通過（既存動作確認） |
| TC-091-E03 | deck_id 指定時に API エラーが発生した場合にエラー表示される | 🔵 | 通過（既存動作確認） |
| TC-091-B01 | deck_id が空文字列の場合は全カードが表示される（fetchCards(undefined) が呼ばれる） | 🟡 | 失敗（期待通り） |

### CardsContext テスト（frontend/src/__tests__/CardsContext.test.tsx 追記）

| テスト ID | テスト名 | 信頼性 | 結果 |
|----------|---------|--------|------|
| TC-091-001 | deck_id 指定時に fetchCards が deckId パラメータ付きで API を呼び出す | 🔵 | 失敗（期待通り） |
| TC-091-002 | deck_id 未指定で fetchCards を呼ぶと全カードを取得する | 🔵 | 失敗（期待通り） |
| TC-091-003 | deck_id 指定時に fetchDueCards が deckId パラメータ付きで API を呼び出す | 🔵 | 失敗（期待通り） |
| TC-091-004 | deck_id 未指定で fetchDueCards を呼ぶと全復習対象カードを取得する | 🔵 | 失敗（期待通り） |

---

## テスト実行結果

### 実行コマンド

```bash
cd frontend && npx vitest run --reporter=verbose src/pages/__tests__/CardsPage.test.tsx src/__tests__/CardsContext.test.tsx
```

### 結果サマリー

| ファイル | 失敗 | 通過 |
|---------|------|------|
| CardsPage.test.tsx（TASK-0091 ブロック） | 6 | 4 |
| CardsContext.test.tsx（TASK-0091 ブロック） | 4 | 0 |
| 既存テスト（回帰確認） | 0 | 全通過 |

### 失敗したテストと期待される失敗内容

**TC-091-001（CardsContext）**:
```
AssertionError: expected "vi.fn()" to be called with arguments: [ 'deck-abc-123' ]
Received: 1st vi.fn() call: []
```
→ `cardsApi.getCards` が引数なしで呼ばれている（fetchCards にパラメータ未実装）

**TC-091-002（CardsContext）**:
```
AssertionError: expected "vi.fn()" to be called with arguments: [ undefined ]
Received: 1st vi.fn() call: []
```
→ `cardsApi.getCards` が引数なしで呼ばれている

**TC-091-003（CardsContext）**:
```
AssertionError: expected "vi.fn()" to be called with arguments: [ undefined, 'deck-abc-123' ]
Received: 1st vi.fn() call: []
```
→ `cardsApi.getDueCards` が引数なしで呼ばれている

**TC-091-004（CardsContext）**:
```
AssertionError: expected "vi.fn()" to be called with arguments: [ undefined, undefined ]
Received: 1st vi.fn() call: []
```
→ `cardsApi.getDueCards` が引数なしで呼ばれている

**TC-091-005（CardsPage）**:
```
AssertionError: expected "vi.fn()" to be called with arguments: [ 'deck-abc-123' ]
Received: 1st vi.fn() call: []
```
→ fetchCards が引数なしで呼ばれている（CardsPage が deck_id を fetchCards に渡していない）

**TC-091-006（CardsPage）**:
```
AssertionError: expected "vi.fn()" to be called with arguments: [ undefined ]
Received: 1st vi.fn() call: []
```
→ fetchCards が完全に引数なし（undefined ではなく引数0個）で呼ばれている

**TC-091-007（CardsPage）**:
```
Error: Expected element to have text content: 英語基礎
Received: カード一覧
```
→ CardsPage がデッキ名をヘッダーに表示する実装がない

**TC-091-009（CardsPage）**:
```
AssertionError: expected "vi.fn()" to be called with arguments: [ 'deck-abc-123' ]
Received: 1st vi.fn() call: []
```
→ fetchDueCards が引数なしで呼ばれている（deck_id が渡されていない）

**TC-091-B01（CardsPage）**:
```
AssertionError: expected "vi.fn()" to be called with arguments: [ undefined ]
Received: 1st vi.fn() call: []
```
→ 空文字列の deck_id が正しく undefined として処理されていない

---

## Green フェーズで実装すべき内容

### Phase 1: CardsContext 修正（TC-091-001〜004）

**ファイル**: `frontend/src/contexts/CardsContext.tsx`

1. `fetchCards` のシグネチャを `(deckId?: string) => Promise<void>` に変更
   ```typescript
   const fetchCards = useCallback(async (deckId?: string) => {
     // ...
     const data = await cardsApi.getCards(deckId);
     // ...
   }, []);
   ```

2. `fetchDueCards` のシグネチャを `(deckId?: string) => Promise<void>` に変更
   ```typescript
   const fetchDueCards = useCallback(async (deckId?: string) => {
     // ...
     const response = await cardsApi.getDueCards(undefined, deckId);
     // ...
   }, []);
   ```

3. `CardsContextType` インターフェースも更新:
   ```typescript
   interface CardsContextType {
     fetchCards: (deckId?: string) => Promise<void>;
     fetchDueCards: (deckId?: string) => Promise<void>;
     // ...
   }
   ```

### Phase 2: CardsPage 修正（TC-091-005〜009, B01, B02）

**ファイル**: `frontend/src/pages/CardsPage.tsx`

1. `useSearchParams` で `deck_id` を読み取る:
   ```typescript
   const deckId = searchParams.get('deck_id') || undefined;
   ```

2. `useEffect` で `deckId` を `fetchCards`/`fetchDueCards` に渡す:
   ```typescript
   useEffect(() => {
     if (activeTab === 'due') {
       fetchDueCards(deckId);
     } else {
       fetchCards(deckId);
     }
   }, [activeTab, deckId, fetchCards, fetchDueCards]);
   ```

3. `useDecksContext` を使ってデッキ名をヘッダーに表示:
   ```typescript
   const { decks } = useDecksContext();
   const deckName = deckId ? decks.find(d => d.deck_id === deckId)?.name : undefined;
   // ...
   <h1>{deckName || 'カード一覧'}</h1>
   ```

4. `deckId` を `useEffect` の依存配列に追加

### Phase 3: API レイヤー確認（TC-091-010, 011）

**ファイル**: `frontend/src/services/api.ts`

`cardsApi.getCards` に `deckId` パラメータを追加:
```typescript
async getCards(deckId?: string): Promise<Card[]> {
  const searchParams = new URLSearchParams();
  if (deckId) searchParams.set('deck_id', deckId);
  const qs = searchParams.toString();
  const response = await this.request<{ cards: Card[] }>(`/cards${qs ? `?${qs}` : ''}`);
  return response.cards;
}
```

`cardsApi` facade も更新:
```typescript
export const cardsApi = {
  getCards: (deckId?: string) => apiClient.getCards(deckId),
  // ...
};
```

---

## 信頼性レベルサマリー

| カテゴリ | 🔵 青信号 | 🟡 黄信号 | 🔴 赤信号 |
|---------|-----------|-----------|-----------|
| CardsContext テスト | 4 | 0 | 0 |
| CardsPage テスト | 4 | 6 | 0 |
| **合計** | **8** | **6** | **0** |

- 🔵 青信号: 8項目 (57%)
- 🟡 黄信号: 6項目 (43%)
- 🔴 赤信号: 0項目 (0%)

---

## 品質判定

```
✅ 高品質:
- テスト実行: 成功（10件が期待通り失敗、4件が既存動作確認として通過）
- 期待値: 明確で具体的（引数の確認、ヘッダーテキストの確認）
- アサーション: 適切（toHaveBeenCalledWith, toHaveTextContent）
- 実装方針: 明確（fetchCards/fetchDueCards シグネチャ変更、useSearchParams 追加）
- 信頼性レベル: 🔵（青信号）が多い（57%）
- 既存テストの回帰: 全通過（既存機能に影響なし）
```

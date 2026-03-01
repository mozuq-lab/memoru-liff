# TASK-0091: cards-page-deck-filter Green フェーズ記録

**作成日時**: 2026-03-01
**フェーズ**: Green（最小実装）
**担当**: TDD Green フェーズ

---

## 実装方針

Red フェーズで特定した 10 件の失敗テストをすべて通すため、3 つのファイルを最小限に修正した。
実装の複雑さを避け、既存の `getDueCards` の `URLSearchParams` パターンを踏襲した。

---

## 実装ファイルと変更内容

### 1. `frontend/src/services/api.ts`

**変更内容**: `ApiClient.getCards` に `deckId` パラメータ追加、`cardsApi` facade 更新

```typescript
// ApiClient クラス内
/**
 * 【機能概要】: カード一覧を取得する（オプションで deck_id フィルタ対応）
 * 【実装方針】: getDueCards と同様に URLSearchParams でクエリ文字列を構築する
 * 【テスト対応】: TC-091-001, TC-091-002
 * 🔵 青信号: architecture.md セクション6・既存 getDueCards 実装パターンに基づく
 * @param deckId - フィルタするデッキID（省略時は全カード取得）
 */
async getCards(deckId?: string): Promise<Card[]> {
  // 【クエリ文字列構築】: deckId が指定された場合のみ deck_id パラメータを追加
  const searchParams = new URLSearchParams();
  if (deckId) searchParams.set('deck_id', deckId);
  const qs = searchParams.toString();
  const response = await this.request<{ cards: Card[] }>(`/cards${qs ? `?${qs}` : ''}`);
  return response.cards;
}

// cardsApi facade
export const cardsApi = {
  // 【deckId 対応】: deckId パラメータを API クライアントに転送 🔵
  getCards: (deckId?: string) => apiClient.getCards(deckId),
  // ... 他は変更なし
};
```

**信頼性**: 🔵 青信号（getDueCards と同パターン）

---

### 2. `frontend/src/contexts/CardsContext.tsx`

**変更内容**: `CardsContextType` インターフェース・`fetchCards`・`fetchDueCards` の修正

```typescript
interface CardsContextType {
  cards: Card[];
  dueCards: Card[];
  isLoading: boolean;
  error: Error | null;
  // 【TASK-0091】: deckId パラメータ追加（省略時は従来通り全カード取得） 🔵
  fetchCards: (deckId?: string) => Promise<void>;
  fetchDueCards: (deckId?: string) => Promise<void>;
  addCard: (card: Card) => void;
  updateCard: (cardId: string, updates: Partial<Card>) => void;
  deleteCard: (cardId: string) => void;
  dueCount: number;
  fetchDueCount: () => Promise<void>;
}

/**
 * 【機能概要】: カード一覧を取得してStateを更新する
 * 【実装方針】: deckId が指定された場合はフィルタあり、省略時は全カード取得（後方互換）
 * 【テスト対応】: TC-091-001, TC-091-002
 * 🔵 青信号: architecture.md セクション6・REQ-001・REQ-102 に基づく
 * @param deckId - フィルタするデッキID（省略時は全カード取得）
 */
const fetchCards = useCallback(async (deckId?: string) => {
  setIsLoading(true);
  setError(null);
  try {
    // 【API呼び出し】: deckId を API レイヤーに伝搬（undefined の場合は全カード取得）
    const data = await cardsApi.getCards(deckId);
    setCards(data);
  } catch (err) {
    setError(err as Error);
  } finally {
    setIsLoading(false);
  }
}, []);

/**
 * 【機能概要】: 復習対象カードを取得してStateを更新する
 * 【実装方針】: deckId が指定された場合はフィルタあり、省略時は全復習対象カード取得（後方互換）
 * 【テスト対応】: TC-091-003, TC-091-004
 * 🔵 青信号: architecture.md セクション6・既存 getDueCards 実装（deckId パラメータ対応済み）に基づく
 * @param deckId - フィルタするデッキID（省略時は全復習対象カード取得）
 */
const fetchDueCards = useCallback(async (deckId?: string) => {
  setIsLoading(true);
  setError(null);
  try {
    // 【API呼び出し】: limit は undefined、deckId を第2引数として伝搬
    const response = await cardsApi.getDueCards(undefined, deckId);
    setDueCards(response.due_cards.map(dueCardToCard));
    setDueCount(response.total_due_count);
  } catch (err) {
    setError(err as Error);
  } finally {
    setIsLoading(false);
  }
}, []);
```

**信頼性**: 🔵 青信号（architecture.md セクション6・REQ-001・REQ-102 に基づく）

---

### 3. `frontend/src/pages/CardsPage.tsx`

**変更内容**: `useDecksContext` インポート追加、`deckId` 読み取り、ヘッダー表示、`useEffect` 修正

```typescript
// インポート追加
import { useDecksContext } from '@/contexts/DecksContext';

// コンポーネント内
const { decks } = useDecksContext();

// 【TASK-0091】: URL クエリパラメータから deck_id を取得
// 空文字列や null の場合は undefined に変換（falsy な値をフィルタなしとして扱う）
// 🔵 青信号: architecture.md セクション6 の実装概要に基づく
const deckId = searchParams.get('deck_id') || undefined;

// 【TASK-0091】: deckId に対応するデッキ名を DecksContext から検索
// 🟡 黄信号: REQ-101・note.md の DecksContext 設計パターンより
const deckName = deckId ? decks.find(d => d.deck_id === deckId)?.name : undefined;

// 【初期読み込み】: タブと deck_id に応じたデータを取得
// 【TASK-0091】: deckId を依存配列に追加、fetchCards/fetchDueCards に deckId を渡す
// 🔵 青信号: architecture.md セクション6 の useEffect 実装概要に基づく
useEffect(() => {
  if (activeTab === 'due') {
    fetchDueCards(deckId);
  } else {
    fetchCards(deckId);
  }
}, [activeTab, deckId, fetchCards, fetchDueCards]);

// JSX ヘッダー部
{/* 【TASK-0091】: deck_id 指定時はデッキ名を表示、未指定時は「カード一覧」を表示 */}
{/* 🟡 黄信号: REQ-101・note.md deckName フォールバック設計より */}
<h1 className="text-xl font-bold text-gray-800" data-testid="cards-title">{deckName || 'カード一覧'}</h1>
```

**信頼性**: 🔵/🟡 青・黄信号（architecture.md セクション6・REQ-101 に基づく）

---

## テスト実行結果

```
実行コマンド:
cd frontend && npx vitest run --reporter=verbose src/pages/__tests__/CardsPage.test.tsx src/__tests__/CardsContext.test.tsx

Test Files: 2 passed (2)
Tests: 42 passed (42)
Duration: 2.04s
```

### TASK-0091 テスト詳細

| テスト ID | テスト名 | 結果 |
|----------|---------|------|
| TC-091-001 | deck_id 指定時に fetchCards が deckId パラメータ付きで API を呼び出す | ✅ 通過 |
| TC-091-002 | deck_id 未指定で fetchCards を呼ぶと全カードを取得する | ✅ 通過 |
| TC-091-003 | deck_id 指定時に fetchDueCards が deckId パラメータ付きで API を呼び出す | ✅ 通過 |
| TC-091-004 | deck_id 未指定で fetchDueCards を呼ぶと全復習対象カードを取得する | ✅ 通過 |
| TC-091-005 | URL に deck_id パラメータがある場合に fetchCards(deckId) が呼ばれる | ✅ 通過 |
| TC-091-006 | URL に deck_id がない場合に fetchCards() が引数なしで呼ばれる | ✅ 通過 |
| TC-091-007 | deck_id 指定時にヘッダーにデッキ名が表示される | ✅ 通過 |
| TC-091-008 | deck_id 未指定時にヘッダーが「カード一覧」を表示する | ✅ 通過 |
| TC-091-009 | deck_id 指定時にタブが due の場合、fetchDueCards(deckId) が呼ばれる | ✅ 通過 |
| TC-091-B01 | deck_id が空文字列の場合は全カードが表示される（fetchCards(undefined) が呼ばれる） | ✅ 通過 |
| TC-091-B02 | deck_id と tab=due の両方が指定された場合に正しくフィルタされる | ✅ 通過 |
| TC-091-E01 | 存在しない deck_id で空のカード一覧が表示される | ✅ 通過 |
| TC-091-E02 | DecksContext にデッキ情報がない場合のヘッダー表示フォールバック | ✅ 通過 |
| TC-091-E03 | deck_id 指定時に API エラーが発生した場合にエラー表示される | ✅ 通過 |

### 既存テスト（回帰テスト）

既存の 28 件のテストもすべて通過。`fetchCards` / `fetchDueCards` のシグネチャ変更はオプション引数のため後方互換性を維持。

---

## 品質判定

```
✅ 高品質:
- テスト結果: 全 42 件通過（TASK-0091 新規 14 件 + 既存 28 件）
- 実装品質: シンプル（既存の getDueCards パターンを踏襲）
- リファクタ箇所: setActiveTab が deck_id を失う問題、handleRetry が deckId なし
- 機能的問題: なし
- コンパイルエラー: なし
- ファイルサイズ: CardsPage 213 行・CardsContext 143 行・api.ts 247 行（800 行以下）
- モック使用: 実装コードにモック・スタブなし
```

---

## 課題・改善点（Refactor フェーズ対象）

1. **`setActiveTab` 時の `deck_id` 消失**: `setSearchParams({tab: 'due'})` / `setSearchParams({})` では既存の `deck_id` が失われる。タブ切り替え時に `deck_id` を保持するには、既存のクエリパラメータをマージして `setSearchParams` する必要がある。
2. **`handleRetry` が `deckId` を引数に渡していない**: エラー後の再取得で全カードが取得される（deckId フィルタなし）。
3. **NFR-201 未対応**: deck_id 指定時の「全カードに戻る」ナビゲーションが未実装。

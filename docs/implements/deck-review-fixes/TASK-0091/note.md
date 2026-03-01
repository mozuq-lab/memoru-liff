# TASK-0091: CardsPage deck_id フィルタ対応 - 開発ノート

## タスク概要

CardsPage で URL クエリパラメータ `deck_id` を読み取り、指定されたデッキのカードのみを一覧表示する機能の実装。
CardsContext の `fetchCards` / `fetchDueCards` に `deckId` パラメータを追加し、deck_id 指定時はページヘッダーにデッキ名を表示。

### 関連要件
- REQ-001: CardsPage は URL クエリパラメータ `deck_id` を読み取り、指定されたデッキのカードのみを一覧表示
- REQ-101: deck_id クエリパラメータがある場合、ページヘッダーにデッキ名を表示
- REQ-102: deck_id クエリパラメータがない場合、全カードを表示（従来動作維持）

---

## 技術スタック

### フロントエンド
- React 18+ + TypeScript
- React Router v6（useSearchParams）
- Context API（CardsContext, DecksContext）
- Vite（開発サーバー）

### 参照元
- docs/CLAUDE.md - フロントエンド技術スタック

---

## 開発ルール

### コンポーネント設計原則
- 参照元: frontend/src/pages/CardsPage.tsx の実装スタイル
  - JSDoc コメント（【機能概要】【実装方針】【テスト対応】）を冒頭に記載
  - useEffect で副作用を管理
  - useState で UI 状態を管理
  - useCallback で関数メモ化

### Context 設計
- 参照元: frontend/src/contexts/CardsContext.tsx, frontend/src/contexts/DecksContext.tsx
  - ContextType インターフェースで Props と戻り値を定義
  - useCallback で fetchXxx 関数をメモ化
  - useMemo で value オブジェクトをメモ化
  - 呼び出し側は引数なし（undefined）で従来動作を維持

### API 呼び出し
- 参照元: frontend/src/services/api.ts
  - cardsApi.getCards(): Promise<Card[]> - 全カード取得
  - cardsApi.getDueCards(limit?: number, deckId?: string): Promise<DueCardsResponse>
    - deckId パラメータを活用
    - URLSearchParams で クエリ文字列構築

---

## 関連実装

### 現在の CardsContext 実装
ファイル: frontend/src/contexts/CardsContext.tsx

```typescript
// fetchCards: () => Promise<void>
// - 現在: cardsApi.getCards() 呼び出し（パラメータなし）
// - 修正: fetchCards(deckId?: string) に変更、deckId を API に渡す

// fetchDueCards: () => Promise<void>
// - 現在: cardsApi.getDueCards() 呼び出し（パラメータなし）
// - 修正: fetchDueCards(deckId?: string) に変更、deckId を API に渡す
```

### 現在の CardsPage 実装
ファイル: frontend/src/pages/CardsPage.tsx

```typescript
// useSearchParams: [searchParams, setSearchParams]
// - 現在: activeTab パラメータのみ取得（tab=due / tab=all）
// - 修正: deck_id パラメータも取得（new URL parameter）
//   const deckId = searchParams.get('deck_id') || undefined;

// useEffect: activeTab 変更で fetchCards/fetchDueCards 実行
// - 現在: fetchCards() / fetchDueCards()（パラメータなし）
// - 修正: fetchCards(deckId) / fetchDueCards(deckId) に変更
//   依存配列に deckId を追加
```

### API レイヤー
ファイル: frontend/src/services/api.ts

```typescript
// getDueCards(limit?: number, deckId?: string): Promise<DueCardsResponse>
// - すでに deckId パラメータをサポート
// - URLSearchParams で deck_id クエリパラメータとして API に送信

// getCards() は追加パラメータが必要（新規実装）
// - API 側でサポート確認が必要：GET /cards?deck_id=xxx
```

### DecksContext
ファイル: frontend/src/contexts/DecksContext.tsx

```typescript
// 利用可能:
// - decks: Deck[] - デッキ一覧
// - fetchDecks(): Promise<void> - デッキ一覧取得

// 用途: deck_id に対応するデッキ名を検索表示
// 実装パターン:
//   const { decks } = useDecksContext();
//   const deckName = decks.find(d => d.deck_id === deckId)?.name || 'Unknown';
```

---

## 設計文書

### アーキテクチャ設計（セクション6: CardsPage deck_id フィルタ）
参照元: docs/design/deck-review-fixes/architecture.md（行264-288）

**実装概要**:
```typescript
// CardsPage.tsx
const [searchParams] = useSearchParams();
const deckId = searchParams.get('deck_id') || undefined;

useEffect(() => {
  if (activeTab === 'due') {
    fetchDueCards(deckId);
  } else {
    fetchCards(deckId);
  }
}, [activeTab, deckId, fetchCards, fetchDueCards]);
```

**ヘッダー表示**: deck_id が指定されている場合、DecksContext からデッキ名を取得して表示

### 要件定義書
参照元: docs/spec/deck-review-fixes/requirements.md

- REQ-001（🔵青）: CardsPage は URL クエリパラメータ `deck_id` を読み取り、指定されたデッキのカードのみを一覧表示
- REQ-101（🟡黄）: CardsPage に `deck_id` クエリパラメータがある場合、ページヘッダーにデッキ名を表示
- REQ-102（🔵青）: CardsPage に `deck_id` クエリパラメータがない場合、全カードを表示（従来動作維持）
- EDGE-003（🟡黄）: 存在しない `deck_id` がクエリパラメータに指定された場合、空のカード一覧を表示

---

## 注意事項

### 技術的制約

1. **API 側 GET /cards パラメータ確認**
   - current: cardsApi.getCards() は `/cards` エンドポイント（パラメータなし）
   - required: `/cards?deck_id=xxx` をサポートしているか確認
   - 可能性: API 側で deck_id フィルタが実装されていない場合、フロントエンドでフィルタリングが必要

2. **useSearchParams の依存配列**
   - deckId の変更時にも useEffect を実行する必要がある
   - 依存配列に deckId を含める
   - 複数回実行を防ぐため useCallback でメモ化

3. **DecksContext 初期化タイミング**
   - deckId からデッキ名を検索する際、DecksContext.decks が初期化済みであることを確認
   - 通常は App.tsx で CardsProvider と DecksProvider の初期化時に fetchDecks() が呼ばれる（REQ-201）

### パフォーマンス考慮

- fetchCards(deckId) / fetchDueCards(deckId) の呼び出し増加
  - ActiveTab 変更 + deckId 変更 → 複数回フェッチ可能
  - useCallback でメモ化し、不要なフェッチを最小化

### エッジケース

- 存在しない deck_id の場合：API は空配列を返す（フロントは空状態表示）
- deck_id 削除後アクセス：空状態表示（EDGE-003）
- deck_id 指定なし → 全カード表示（REQ-102）

---

## テスト項目（TASK-0091 完了条件）

### ユニットテスト（React Testing Library）

1. **CardsContext パラメータ追加テスト**
   - fetchCards(deckId) に deckId パラメータが渡される
   - fetchCards(undefined) で従来動作（全カード）
   - fetchDueCards(deckId) に deckId パラメータが渡される
   - fetchDueCards(undefined) で従来動作

2. **CardsPage deck_id 読み取りテスト**
   - URL に deck_id=xxx がある場合、deckId 状態が設定される
   - deck_id がない場合、deckId が undefined
   - useEffect が deckId 変更時に実行される

3. **CardsPage ヘッダー表示テスト**
   - deck_id 指定時：デッキ名がヘッダーに表示される
   - deck_id 未指定時：「カード一覧」ヘッダーのみ表示
   - 存在しない deck_id：「Unknown」または不表示

4. **カード フィルタリングテスト**
   - deck_id 指定時：該当デッキのカードのみ表示
   - deck_id 未指定時：全カード表示
   - 空結果：空状態（「カードがありません」表示）

### 統合テスト
- ブラウザで ?deck_id=xxx を含むリンクをクリック
- デッキ名がヘッダーに表示される
- 該当デッキのカードのみ表示される
- タブ切り替え時も deck_id フィルタが維持される

---

## 実装チェックリスト

### Phase 1: CardsContext 修正
- [ ] fetchCards(deckId?: string) シグネチャ変更
- [ ] fetchDueCards(deckId?: string) シグネチャ変更
- [ ] cardsApi.getCards(deckId) が API に deckId を渡す実装確認
- [ ] 既存呼び出し箇所で deckId 未指定（undefined）で従来動作維持

### Phase 2: CardsPage 修正
- [ ] useSearchParams で deck_id クエリパラメータ読み取り
- [ ] deckId 状態管理
- [ ] useEffect で activeTab / deckId 変更時にフェッチ
- [ ] deckId 指定時：DecksContext でデッキ名検索・ヘッダー表示
- [ ] deckId 未指定時：従来通り「カード一覧」ヘッダー表示

### Phase 3: API レイヤー確認
- [ ] cardsApi.getCards(deckId) が deck_id クエリパラメータをサポート
- [ ] バックエンド GET /cards?deck_id=xxx が実装済みか確認

---

## ファイルパス（相対パス）

### 対象ファイル
- frontend/src/contexts/CardsContext.tsx - fetchCards/fetchDueCards パラメータ追加
- frontend/src/pages/CardsPage.tsx - deck_id フィルタ実装

### 参考ファイル
- frontend/src/services/api.ts - API レイヤー（cardsApi.getDueCards で deckId サポート確認）
- frontend/src/contexts/DecksContext.tsx - デッキ名検索用
- frontend/src/types/index.ts - 型定義
- frontend/src/types/deck.ts - Deck インターフェース
- docs/design/deck-review-fixes/architecture.md - 設計文書
- docs/spec/deck-review-fixes/requirements.md - 要件定義

---

## 信頼性レベルサマリー

- **REQ-001**: 🔵 青信号（レビュー H-1、要件定義書より確実）
- **REQ-101**: 🟡 黄信号（要件定義から推測）
- **REQ-102**: 🔵 青信号（レビュー H-1 より確実）
- **EDGE-003**: 🟡 黄信号（要件定義から推測）

**品質評価**: ✅ 実装可能（パラメータの詳細確認が必要）

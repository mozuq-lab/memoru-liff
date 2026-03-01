# TASK-0091: CardsPage deck_id フィルタ対応 - TDD用要件整理

**タスクID**: TASK-0091
**要件名**: deck-review-fixes
**機能名**: CardsPage deck_id フィルタ対応
**作成日**: 2026-03-01

---

## 1. 機能の概要

### 何をする機能か 🔵

**信頼性**: 🔵 *REQ-001・レビュー H-1・要件 4.3 より*

CardsPage（カード一覧ページ）に URL クエリパラメータ `deck_id` によるフィルタ機能を追加する。デッキ一覧画面から特定デッキをタップした際に、そのデッキに所属するカードのみを一覧表示できるようにする。

### どのような問題を解決するか 🔵

**信頼性**: 🔵 *レビュー H-1・ユーザーストーリー 1.1 より*

現在の CardsPage は全カードのみ表示可能であり、特定デッキに紐付くカードだけを閲覧する手段がない。デッキ管理機能の追加に伴い、デッキ別のカード一覧表示が必要となる。

### 想定されるユーザー 🔵

**信頼性**: 🔵 *ユーザーストーリーより*

暗記カードアプリのユーザー。デッキでカードを分類管理し、特定デッキのカードを確認・復習したい。

### システム内での位置づけ 🔵

**信頼性**: 🔵 *architecture.md セクション6 より*

フロントエンドの変更のみで完結する機能。CardsContext の fetchCards/fetchDueCards に deckId パラメータを追加し、CardsPage で URL クエリパラメータを読み取って Context に渡す。バックエンド API（`GET /cards?deck_id=xxx`、`GET /cards/due?deck_id=xxx`）は既にパラメータ対応済み。

- **参照したEARS要件**: REQ-001, REQ-101, REQ-102
- **参照した設計文書**: architecture.md セクション6「CardsPage deck_id フィルタ」

---

## 2. 入力・出力の仕様

### 入力パラメータ 🔵

**信頼性**: 🔵 *architecture.md セクション6・既存 CardsPage 実装より*

| パラメータ | 型 | ソース | 必須 | 制約 |
|-----------|-----|--------|------|------|
| `deck_id` | `string \| undefined` | URL クエリパラメータ (`useSearchParams`) | いいえ | UUID形式の文字列。未指定時は `undefined` |
| `tab` | `'due' \| 'all'` | URL クエリパラメータ (既存) | いいえ | 既存動作維持。デフォルト `'all'` |

### 出力仕様 🔵

**信頼性**: 🔵 *REQ-001, REQ-101, REQ-102, architecture.md セクション6 より*

| 出力 | 条件 | 内容 |
|------|------|------|
| ページヘッダー（deck_id あり） | `deck_id` が指定かつ該当デッキが DecksContext に存在 | デッキ名を表示 |
| ページヘッダー（deck_id なし） | `deck_id` 未指定 | 「カード一覧」（従来動作） |
| カード一覧（deck_id あり） | `deck_id` が指定 | 該当デッキのカードのみ表示 |
| カード一覧（deck_id なし） | `deck_id` 未指定 | 全カード表示（従来動作） |
| 空状態表示 | 該当カードが0件 | 「カードがありません」メッセージ表示 |

### CardsContext インターフェース変更 🔵

**信頼性**: 🔵 *architecture.md セクション6・既存 CardsContext 実装より*

```typescript
// 変更前
interface CardsContextType {
  fetchCards: () => Promise<void>;
  fetchDueCards: () => Promise<void>;
  // ...
}

// 変更後
interface CardsContextType {
  fetchCards: (deckId?: string) => Promise<void>;
  fetchDueCards: (deckId?: string) => Promise<void>;
  // ...
}
```

### API レイヤーの現状確認 🔵

**信頼性**: 🔵 *frontend/src/services/api.ts 実装確認より*

| API メソッド | 現状 | 修正必要 |
|-------------|------|---------|
| `cardsApi.getDueCards(limit?, deckId?)` | deckId パラメータ対応済み | 不要 |
| `cardsApi.getCards()` | パラメータなし | **要修正**: `getCards(deckId?)` に変更し `deck_id` クエリパラメータを追加 |

### データフロー 🔵

**信頼性**: 🔵 *dataflow.md フロー1 より*

```
DecksPage → navigate("/cards?deck_id=xxx")
  → CardsPage: useSearchParams() で deck_id 取得
    → CardsContext: fetchCards(deckId) / fetchDueCards(deckId)
      → API: GET /cards?deck_id=xxx / GET /cards/due?deck_id=xxx
        → バックエンド: FilterExpression(deck_id=xxx)
          → DynamoDB: 該当カード返却
```

- **参照したEARS要件**: REQ-001, REQ-101, REQ-102
- **参照した設計文書**: architecture.md セクション6、frontend/src/services/api.ts、frontend/src/contexts/CardsContext.tsx

---

## 3. 制約条件

### アーキテクチャ制約 🔵

**信頼性**: 🔵 *architecture.md・既存実装パターンより*

1. **Context パターン維持**: CardsContext の useCallback / useMemo パターンを維持する
2. **後方互換性**: fetchCards / fetchDueCards の既存呼び出し箇所は引数なし（undefined）で従来動作を維持する
3. **DecksContext 依存**: デッキ名表示のため DecksContext から decks 一覧を参照する。App.tsx で DecksProvider が初期化済みであること（REQ-201）

### useSearchParams の制約 🟡

**信頼性**: 🟡 *既存 CardsPage の実装パターンから妥当な推測*

1. **setSearchParams 互換**: 既存の `setActiveTab` が `setSearchParams()` を使用している。deck_id 指定時にタブ切り替えを行った場合、deck_id パラメータを保持する必要がある
2. **useEffect 依存配列**: deckId を依存配列に含め、deckId 変更時にもフェッチを実行する
3. **useCallback メモ化**: fetchCards/fetchDueCards の依存配列変更に注意。deckId は引数として渡すため useCallback の依存には含めない

### API レイヤー制約 🔵

**信頼性**: 🔵 *frontend/src/services/api.ts 実装確認より*

1. **getCards メソッド修正**: 現在 `getCards()` はパラメータなし。`getCards(deckId?: string)` に変更し、URLSearchParams で `deck_id` クエリパラメータを構築する必要がある
2. **getDueCards メソッド**: 既に `getDueCards(limit?, deckId?)` で deckId 対応済み。変更不要

### ユーザビリティ制約 🟡

**信頼性**: 🟡 *NFR-201 から妥当な推測*

1. **戻るナビゲーション**: deck_id 指定時に全カード一覧（deck_id なし）への戻りリンクを提供する

- **参照したEARS要件**: REQ-001, REQ-101, REQ-102, NFR-201
- **参照した設計文書**: architecture.md セクション6、既存 CardsPage.tsx・CardsContext.tsx 実装

---

## 4. 想定される使用例

### 基本パターン1: デッキ別カード一覧表示 🔵

**信頼性**: 🔵 *REQ-001・dataflow.md フロー1 より*

1. ユーザーが DecksPage で特定デッキをタップ
2. `/cards?deck_id=xxx` に遷移
3. CardsPage が `useSearchParams()` で `deck_id` を取得
4. CardsContext の `fetchCards(deckId)` を呼び出し
5. 該当デッキのカードのみが表示される
6. ページヘッダーにデッキ名が表示される

### 基本パターン2: 全カード表示（従来動作） 🔵

**信頼性**: 🔵 *REQ-102 より*

1. ユーザーが Navigation バーから「カード」をタップ
2. `/cards` に遷移（deck_id なし）
3. CardsContext の `fetchCards()` を引数なしで呼び出し
4. 全カードが表示される（従来動作維持）
5. ページヘッダーは「カード一覧」

### 基本パターン3: デッキ別復習対象タブ 🟡

**信頼性**: 🟡 *受け入れ基準 TC-001-03 から妥当な推測*

1. `/cards?deck_id=xxx` で表示中にタブを「復習対象」に切り替え
2. `deck_id` パラメータが維持される
3. `fetchDueCards(deckId)` が呼び出される
4. 該当デッキの復習対象カードのみ表示される

### エッジケース1: 存在しない deck_id 🟡

**信頼性**: 🟡 *EDGE-003 から妥当な推測*

1. `/cards?deck_id=nonexistent` に遷移
2. API が空のカード配列を返す
3. 空状態表示（「カードがありません」メッセージ）

### エッジケース2: deck_id 指定時のデッキ名が DecksContext に未ロード 🟡

**信頼性**: 🟡 *REQ-201・note.md 注意事項より妥当な推測*

1. `/cards?deck_id=xxx` にダイレクトアクセス
2. DecksContext の decks が初期化前の可能性
3. デッキ名が取得できない場合のフォールバック表示が必要（デッキ名非表示またはデフォルト表示）

- **参照したEARS要件**: REQ-001, REQ-102, EDGE-003
- **参照した設計文書**: dataflow.md フロー1、architecture.md セクション6

---

## 5. EARS要件・設計文書との対応関係

### 参照したユーザストーリー
- ユーザーストーリー 1.1: デッキ別カード一覧表示

### 参照した機能要件
- **REQ-001**: CardsPage は URL クエリパラメータ `deck_id` を読み取り、指定されたデッキのカードのみを一覧表示しなければならない 🔵
- **REQ-101**: CardsPage に `deck_id` クエリパラメータがある場合、ページヘッダーにデッキ名を表示しなければならない 🟡
- **REQ-102**: CardsPage に `deck_id` クエリパラメータがない場合、全カードを表示しなければならない（従来動作維持） 🔵

### 参照した非機能要件
- **NFR-201**: デッキ別カード一覧から全カード一覧への「戻る」ナビゲーションが提供されること 🟡

### 参照したEdgeケース
- **EDGE-003**: 存在しない `deck_id` がクエリパラメータに指定された場合、空のカード一覧を表示する 🟡

### 参照した受け入れ基準
- **TC-001-01**: deck_id クエリパラメータ付きで該当デッキのカードのみ表示 🔵
- **TC-001-02**: deck_id なしで全カード表示 🔵
- **TC-001-03**: deck_id 付きで復習対象タブ切り替え時もフィルタ維持 🟡
- **TC-001-E01**: 存在しない deck_id で空のカード一覧表示 🟡

### 参照した設計文書
- **アーキテクチャ**: architecture.md セクション6「CardsPage deck_id フィルタ」
- **データフロー**: dataflow.md フロー1「デッキ別カード一覧表示」
- **型定義**: `frontend/src/types/card.ts`（Card, DueCard, DueCardsResponse）、`frontend/src/types/deck.ts`（Deck）
- **API仕様**: `frontend/src/services/api.ts`（cardsApi.getCards, cardsApi.getDueCards）

---

## 6. 実装対象ファイルと変更内容

### 変更対象ファイル

| ファイル | 変更内容 | 信頼性 |
|---------|---------|--------|
| `frontend/src/contexts/CardsContext.tsx` | fetchCards(deckId?), fetchDueCards(deckId?) パラメータ追加 | 🔵 |
| `frontend/src/pages/CardsPage.tsx` | useSearchParams で deck_id 読み取り、ヘッダー表示、useEffect 修正 | 🔵 |
| `frontend/src/services/api.ts` | getCards(deckId?) パラメータ追加、URLSearchParams 構築 | 🔵 |

### 参考ファイル（読み取りのみ）

| ファイル | 用途 |
|---------|------|
| `frontend/src/contexts/DecksContext.tsx` | デッキ名検索用（decks 配列参照） |
| `frontend/src/types/deck.ts` | Deck インターフェース参照 |
| `frontend/src/types/card.ts` | Card, DueCardsResponse インターフェース参照 |

---

## 信頼性レベルサマリー

| カテゴリ | 🔵 青信号 | 🟡 黄信号 | 🔴 赤信号 |
|---------|-----------|-----------|-----------|
| 機能概要 | 4 | 0 | 0 |
| 入出力仕様 | 5 | 0 | 0 |
| 制約条件 | 2 | 2 | 0 |
| 使用例 | 2 | 3 | 0 |
| **合計** | **13** | **5** | **0** |

- 🔵 青信号: 13項目 (72%)
- 🟡 黄信号: 5項目 (28%)
- 🔴 赤信号: 0項目 (0%)

**品質評価**: ✅ 高品質

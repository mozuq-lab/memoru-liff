# deck-review-fixes 受け入れ基準

**作成日**: 2026-02-28
**関連要件定義**: [requirements.md](requirements.md)
**関連ユーザストーリー**: [user-stories.md](user-stories.md)
**ヒアリング記録**: [interview-record.md](interview-record.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: レビュー文書・設計文書・ユーザヒアリングを参考にした確実な基準
- 🟡 **黄信号**: レビュー文書・設計文書・ユーザヒアリングから妥当な推測による基準
- 🔴 **赤信号**: レビュー文書・設計文書・ユーザヒアリングにない推測による基準

---

## REQ-001: CardsPage deck_id フィルタ対応 🔵

**信頼性**: 🔵 *レビュー H-1・要件 4.3 より*

### Given（前提条件）
- デッキにカードが紐付いている
- バックエンド `GET /cards?deck_id=xxx` は正しく動作する

### When（実行条件）
- ユーザーが `/cards?deck_id=xxx` に遷移する

### Then（期待結果）
- 指定デッキのカードのみが表示される
- ページヘッダーにデッキ名が表示される

### テストケース

#### 正常系

- [ ] **TC-001-01**: deck_id クエリパラメータ付きで CardsPage に遷移し、該当デッキのカードのみ表示される 🔵
  - **入力**: `/cards?deck_id=deck-1`（deck-1 に3枚、他に5枚）
  - **期待結果**: 3枚のカードが表示される
  - **信頼性**: 🔵 *レビュー H-1 より*

- [ ] **TC-001-02**: deck_id なしで CardsPage に遷移し、全カードが表示される 🔵
  - **入力**: `/cards`
  - **期待結果**: 全8枚のカードが表示される（従来動作）
  - **信頼性**: 🔵 *REQ-102 より*

- [ ] **TC-001-03**: deck_id 付きで復習対象タブ切り替え時もフィルタが維持される 🟡
  - **入力**: `/cards?deck_id=deck-1`、復習対象タブ選択
  - **期待結果**: deck-1 の復習対象カードのみ表示される
  - **信頼性**: 🟡 *H-1 から妥当な推測*

#### 異常系

- [ ] **TC-001-E01**: 存在しない deck_id が指定された場合 🟡
  - **入力**: `/cards?deck_id=nonexistent`
  - **期待結果**: 空のカード一覧が表示される
  - **信頼性**: 🟡 *EDGE-003 から妥当な推測*

---

## REQ-002: カード deck_id null 解除 🔵

**信頼性**: 🔵 *レビュー H-2 より*

### Given（前提条件）
- カードがデッキに割り当てられている

### When（実行条件）
- ユーザーが CardDetailPage でデッキを「未分類」に変更して保存

### Then（期待結果）
- API に `deck_id: null` が送信される
- バックエンドが DynamoDB から `deck_id` 属性を REMOVE する
- カードが未分類状態になる

### テストケース

#### 正常系

- [ ] **TC-002-01**: フロントエンドが deck_id=null を API に送信する 🔵
  - **入力**: DeckSelector で「未分類」を選択、保存ボタン押下
  - **期待結果**: PUT /cards/:id のリクエストボディに `"deck_id": null` が含まれる
  - **信頼性**: 🔵 *レビュー H-2 より*

- [ ] **TC-002-02**: バックエンドが deck_id=null で REMOVE を実行する 🔵
  - **入力**: `PUT /cards/:id` body: `{"deck_id": null}`
  - **期待結果**: DynamoDB の UpdateExpression に `REMOVE deck_id` が含まれる
  - **信頼性**: 🔵 *レビュー H-2 修正案より*

- [ ] **TC-002-03**: deck_id 未送信の場合は deck_id を変更しない 🔵
  - **入力**: `PUT /cards/:id` body: `{"front": "new front"}`（deck_id なし）
  - **期待結果**: カードの deck_id は変更されない
  - **信頼性**: 🔵 *REQ-104 より*

#### 境界値

- [ ] **TC-002-B01**: UpdateCardRequest の型定義が string | null を許容する 🔵
  - **入力**: TypeScript 型チェック
  - **期待結果**: `deck_id?: string | null` として型定義されている
  - **信頼性**: 🔵 *H-2 修正案より*

---

## REQ-003: DeckLimitExceededError HTTP 409 🔵

**信頼性**: 🔵 *追加レビュー H-3 より*

### Given（前提条件）
- ユーザーが50個のデッキを持っている

### When（実行条件）
- 新しいデッキ作成リクエストを送信

### Then（期待結果）
- HTTP 409 Conflict が返される
- エラーメッセージにデッキ数上限を示す内容が含まれる

### テストケース

#### 正常系

- [ ] **TC-003-01**: デッキ数上限で HTTP 409 が返される 🔵
  - **入力**: 50デッキ存在時に POST /decks
  - **期待結果**: HTTP 409、`"error": "DECK_LIMIT_EXCEEDED"` 相当のレスポンス
  - **信頼性**: 🔵 *H-3 より*

- [ ] **TC-003-02**: 49デッキ以下では正常に作成できる 🔵
  - **入力**: 49デッキ存在時に POST /decks
  - **期待結果**: HTTP 201、デッキが作成される
  - **信頼性**: 🔵 *既存テストケースより*

---

## REQ-004: デッキ数制限のアトミック検証 🔵

**信頼性**: 🔵 *追加レビュー H-4・ヒアリング回答より*

### Given（前提条件）
- DynamoDB に ConditionExpression が設定されている

### When（実行条件）
- 並行してデッキ作成リクエストが送信される

### Then（期待結果）
- 制限を超えるデッキが作成されない
- ConditionalCheckFailedException は HTTP 409 として返される

### テストケース

#### 正常系

- [ ] **TC-004-01**: ConditionExpression によりアトミックにデッキ数を検証する 🔵
  - **入力**: create_deck 呼び出し時の DynamoDB PutItem
  - **期待結果**: ConditionExpression がデッキ数上限をチェック
  - **信頼性**: 🔵 *ヒアリング回答より*

- [ ] **TC-004-02**: ConditionalCheckFailedException が DeckLimitExceededError に変換される 🔵
  - **入力**: 50デッキ存在時に create_deck
  - **期待結果**: DeckLimitExceededError が raise される
  - **信頼性**: 🔵 *H-4 修正方針より*

#### 異常系

- [ ] **TC-004-E01**: ConditionExpression が他ユーザーのデッキを参照しない 🔵
  - **入力**: ユーザーA が50デッキ、ユーザーB が0デッキの状態でユーザーB がデッキ作成
  - **期待結果**: ユーザーB のデッキが正常に作成される
  - **信頼性**: 🔵 *NFR-101 より*

---

## REQ-005: total_due_count の正確性 🔵

**信頼性**: 🔵 *レビュー M-1 より*

### Given（前提条件）
- デッキに復習対象カードが複数存在する

### When（実行条件）
- `GET /cards/due?deck_id=xxx&limit=10` をリクエスト

### Then（期待結果）
- `total_due_count` は limit に関係なく、指定デッキの復習対象カード総数を返す

### テストケース

#### 正常系

- [ ] **TC-005-01**: deck_id 指定時の total_due_count が正確 🔵
  - **入力**: deck-1 に20枚の復習対象、limit=10
  - **期待結果**: `total_due_count: 20`、返却カード数: 10
  - **信頼性**: 🔵 *レビュー M-1 より*

- [ ] **TC-005-02**: deck_id なしの場合も total_due_count が正確 🔵
  - **入力**: 全体で30枚の復習対象、limit=10
  - **期待結果**: `total_due_count: 30`、返却カード数: 10
  - **信頼性**: 🔵 *既存要件の回帰確認*

#### 境界値

- [ ] **TC-005-B01**: 指定デッキの復習対象が0件の場合 🟡
  - **入力**: deck-1 に復習対象0枚、limit=10
  - **期待結果**: `total_due_count: 0`、返却カード数: 0
  - **信頼性**: 🟡 *妥当な推測*

---

## REQ-103/104: カード deck_id の null vs 未送信の区別 🔵

**信頼性**: 🔵 *レビュー H-2 より*

### テストケース

- [ ] **TC-103-01**: deck_id=null 送信時に REMOVE が実行される 🔵
  - **入力**: `{"deck_id": null}`
  - **期待結果**: DynamoDB UpdateExpression に `REMOVE deck_id`
  - **信頼性**: 🔵 *REQ-103 より*

- [ ] **TC-104-01**: deck_id キーなし送信時に deck_id が変更されない 🔵
  - **入力**: `{"front": "updated"}`（deck_id キーなし）
  - **期待結果**: deck_id が元の値のまま
  - **信頼性**: 🔵 *REQ-104 より*

---

## REQ-105/106: デッキフィールドの明示的クリア 🔵

**信頼性**: 🔵 *レビュー M-3 より*

### テストケース

- [ ] **TC-105-01**: description=null 送信時に REMOVE が実行される 🔵
  - **入力**: `PUT /decks/:id` body: `{"description": null}`
  - **期待結果**: DynamoDB から description 属性が REMOVE される
  - **信頼性**: 🔵 *REQ-105 より*

- [ ] **TC-106-01**: color=null 送信時に REMOVE が実行される 🔵
  - **入力**: `PUT /decks/:id` body: `{"color": null}`
  - **期待結果**: DynamoDB から color 属性が REMOVE される
  - **信頼性**: 🔵 *REQ-106 より*

---

## REQ-201: Provider ネスト順序 🟡

**信頼性**: 🟡 *レビュー M-2 から妥当な推測*

### テストケース

- [ ] **TC-201-01**: App.tsx の Provider 順序が設計準拠 🟡
  - **入力**: App.tsx のコード確認
  - **期待結果**: `AuthProvider > CardsProvider > DecksProvider` の順序
  - **信頼性**: 🟡 *research.md から推測*

---

## REQ-202: DeckFormModal 差分送信 🔵

**信頼性**: 🔵 *レビュー M-4 より*

### テストケース

- [ ] **TC-202-01**: 変更されたフィールドのみ API に送信される 🔵
  - **入力**: name のみ変更して保存
  - **期待結果**: `updateDeck` に name のみが含まれる
  - **信頼性**: 🔵 *M-4 より*

- [ ] **TC-202-02**: color を選択後に「なし」に戻した場合の処理 🟡
  - **入力**: color を選択 → color を「なし」に戻す → 保存
  - **期待結果**: `color: null` が送信される（明示的クリア）
  - **信頼性**: 🟡 *M-4 エッジケースから妥当な推測*

---

## REQ-203: CardDetailPage デッキ変更後のコンテキスト更新 🔵

**信頼性**: 🔵 *レビュー L-4 より*

### テストケース

- [ ] **TC-203-01**: デッキ変更保存後に fetchDecks が呼ばれる 🔵
  - **入力**: CardDetailPage でデッキ変更 → 保存
  - **期待結果**: `DecksContext.fetchDecks()` が呼び出される
  - **信頼性**: 🔵 *L-4 より*

---

## REQ-401: handler.py ドメイン別分割 🔵

**信頼性**: 🔵 *レビュー L-2・ヒアリング回答より*

### テストケース

- [ ] **TC-401-01**: handler.py がドメイン別ファイルに分割されている 🔵
  - **入力**: ファイル構造確認
  - **期待結果**: `backend/src/api/` 配下に cards, decks, review 等のファイルが存在
  - **信頼性**: 🔵 *ヒアリング回答より*

- [ ] **TC-401-02**: 分割後も全 API エンドポイントが正常動作する 🔵
  - **入力**: 全バックエンドテスト実行
  - **期待結果**: 既存テストが全て通過
  - **信頼性**: 🔵 *回帰テスト*

---

## REQ-402: JSDoc コメントスタイル統一 🟡

**信頼性**: 🟡 *レビュー L-3 から妥当な推測*

### テストケース

- [ ] **TC-402-01**: 全デッキ関連コンポーネントに JSDoc コメントが存在する 🟡
  - **入力**: DeckFormModal, DecksPage のコード確認
  - **期待結果**: 【機能概要】【実装方針】の JSDoc コメントが存在
  - **信頼性**: 🟡 *L-3 から推測*

---

## REQ-403: unassigned フィルタリング削除 🔵

**信頼性**: 🔵 *レビュー L-1 より*

### テストケース

- [ ] **TC-403-01**: DeckSelector から unassigned フィルタが削除されている 🔵
  - **入力**: DeckSelector.tsx のコード確認
  - **期待結果**: `d.deck_id !== 'unassigned'` フィルタが存在しない
  - **信頼性**: 🔵 *L-1 より*

- [ ] **TC-403-02**: DeckSummary から unassigned フィルタが削除されている 🔵
  - **入力**: DeckSummary.tsx のコード確認
  - **期待結果**: `d.deck_id !== 'unassigned'` フィルタが存在しない
  - **信頼性**: 🔵 *L-1 より*

---

## REQ-404: M-5 リスク許容・TODO記録 🔵

**信頼性**: 🔵 *ヒアリング回答より*

### テストケース

- [ ] **TC-404-01**: get_deck_card_counts / get_deck_due_counts に TODO コメントが記載されている 🔵
  - **入力**: deck_service.py のコード確認
  - **期待結果**: パフォーマンス改善の TODO コメントが存在
  - **信頼性**: 🔵 *ヒアリング回答より*

---

## テストケースサマリー

### カテゴリ別件数

| カテゴリ | 正常系 | 異常系 | 境界値 | 合計 |
|---------|--------|--------|--------|------|
| High要件 (H-1〜H-4) | 10 | 2 | 1 | 13 |
| Medium要件 (M-1〜M-5) | 6 | 0 | 1 | 7 |
| Low要件 (L-1〜L-4) | 6 | 0 | 0 | 6 |
| **合計** | **22** | **2** | **2** | **26** |

### 信頼性レベル分布

- 🔵 青信号: 22件 (85%)
- 🟡 黄信号: 4件 (15%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質

### 優先度別テストケース

- **Must Have**: 13件（H-1〜H-4）
- **Should Have**: 7件（M-1〜M-4）
- **Could Have**: 6件（L-1〜L-4, M-5）

---

## テスト実施計画

### Phase 1: Critical/High 修正テスト
- REQ-001〜REQ-004（H-1〜H-4）
- 優先度: Must Have
- 13テストケース

### Phase 2: Medium 修正テスト
- REQ-005, REQ-105〜106, REQ-201〜202
- 優先度: Should Have
- 7テストケース

### Phase 3: Low 修正・リファクタリングテスト
- REQ-203, REQ-401〜404
- 優先度: Could Have
- 6テストケース

# deck-review-fixes 要件定義書

## 概要

`feature/deck-management-spec` ブランチのPR #1に対するコードレビューで検出された指摘事項の修正要件。Critical 1件（修正済み）、High 4件、Medium 5件、Low 4件の計14件を対象とする。

## 関連文書

- **ヒアリング記録**: [💬 interview-record.md](interview-record.md)
- **ユーザストーリー**: [📖 user-stories.md](user-stories.md)
- **受け入れ基準**: [✅ acceptance-criteria.md](acceptance-criteria.md)
- **コンテキストノート**: [📝 note.md](note.md)
- **レビュー文書**: [📋 review-deck-management-spec.md](../../review-deck-management-spec.md)

## 機能要件（EARS記法）

**【信頼性レベル凡例】**:
- 🔵 **青信号**: レビュー文書・設計文書・ユーザヒアリングを参考にした確実な要件
- 🟡 **黄信号**: レビュー文書・設計文書・ユーザヒアリングから妥当な推測による要件
- 🔴 **赤信号**: レビュー文書・設計文書・ユーザヒアリングにない推測による要件

### 通常要件

- REQ-001: `CardsPage` は URL クエリパラメータ `deck_id` を読み取り、指定されたデッキのカードのみを一覧表示しなければならない 🔵 *レビュー H-1・要件 4.3 より*
- REQ-002: ユーザーがカードのデッキを「未分類」に変更した場合、システムは `deck_id` を `null` として API に送信し、バックエンドは DynamoDB から `deck_id` 属性を REMOVE しなければならない 🔵 *レビュー H-2 より*
- REQ-003: `DeckLimitExceededError` が発生した場合、API は HTTP 409 Conflict を返さなければならない 🔵 *追加レビュー H-3 より*
- REQ-004: デッキ作成時、DynamoDB の `ConditionExpression` を使用して、ユーザーあたりのデッキ数制限（50）をアトミックに検証しなければならない 🔵 *追加レビュー H-4・ヒアリング回答より*
- REQ-005: `GET /cards/due?deck_id=xxx` の `total_due_count` は、`limit` パラメータに影響されず、指定デッキの復習対象カード総数を正確に返さなければならない 🔵 *レビュー M-1 より*

### 条件付き要件

- REQ-101: `CardsPage` に `deck_id` クエリパラメータがある場合、ページヘッダーにデッキ名を表示しなければならない 🟡 *レビュー H-1 から妥当な推測*
- REQ-102: `CardsPage` に `deck_id` クエリパラメータがない場合、全カードを表示しなければならない（従来動作維持） 🔵 *レビュー H-1 より*
- REQ-103: `UpdateCardRequest` の `deck_id` フィールドが `null` の場合、バックエンドはカードの `deck_id` 属性を DynamoDB から REMOVE しなければならない 🔵 *レビュー H-2 より*
- REQ-104: `UpdateCardRequest` の `deck_id` フィールドが未送信の場合、バックエンドは `deck_id` を変更してはならない 🔵 *レビュー H-2 より*
- REQ-105: `UpdateDeckRequest` の `description` が `null` の場合、バックエンドはデッキの `description` を DynamoDB から REMOVE しなければならない 🔵 *レビュー M-3 より*
- REQ-106: `UpdateDeckRequest` の `color` が `null` の場合、バックエンドはデッキの `color` を DynamoDB から REMOVE しなければならない 🔵 *レビュー M-3 より*

### 状態要件

- REQ-201: `App.tsx` の Provider ネスト順序は `AuthProvider > CardsProvider > DecksProvider` の順であるべきである 🟡 *レビュー M-2・research.md から妥当な推測*
- REQ-202: `DeckFormModal` の edit モードでは、変更されたフィールドのみを API に送信しなければならない 🔵 *レビュー M-4 より*
- REQ-203: `CardDetailPage` でデッキ変更を保存した後、`DecksContext.fetchDecks()` を呼び出してデッキの `card_count` / `due_count` を更新しなければならない 🔵 *レビュー L-4 より*

### 制約要件

- REQ-401: `handler.py` をドメイン別にファイル分割しなければならない（cards, decks, review 等） 🔵 *レビュー L-2・ヒアリング回答より*
- REQ-402: フロントエンドコンポーネント全体で JSDoc コメントスタイルを統一しなければならない 🟡 *レビュー L-3 から妥当な推測*
- REQ-403: `DeckSelector` / `DeckSummary` から不要な `'unassigned'` フィルタリングを削除しなければならない 🔵 *レビュー L-1 より*
- REQ-404: M-5（全カードスキャン）は MVP 段階ではリスク許容とし、TODO コメントで将来改善を記録する 🔵 *ヒアリング回答より*

## 非機能要件

### パフォーマンス

- NFR-001: `GET /cards/due?deck_id=xxx` のレスポンスタイムは、deck_id フィルタなしの場合と同等でなければならない 🟡 *REQ-005 から妥当な推測*
- NFR-002: handler.py のファイル分割後も Lambda のコールドスタート時間に影響がないこと 🟡 *REQ-401 から妥当な推測*

### セキュリティ

- NFR-101: デッキ数制限の ConditionExpression は、他ユーザーのデッキを参照してはならない 🔵 *H-4 修正・既存セキュリティ設計より*

### ユーザビリティ

- NFR-201: デッキ別カード一覧から全カード一覧への「戻る」ナビゲーションが提供されること 🟡 *H-1 修正に伴う妥当な推測*

## Edge ケース

### エラー処理

- EDGE-001: デッキ数上限（50）に達した状態でデッキ作成を試みた場合、HTTP 409 とわかりやすいエラーメッセージを返す 🔵 *H-3・H-4 より*
- EDGE-002: 同時に2つのリクエストでデッキを作成した場合、ConditionExpression により1つだけが成功する 🔵 *H-4・ヒアリング回答より*
- EDGE-003: 存在しない `deck_id` がクエリパラメータに指定された場合、空のカード一覧を表示する 🟡 *H-1 から妥当な推測*

### 境界値

- EDGE-101: `deck_id` を null に設定したカード更新リクエストで、DynamoDB の `deck_id` 属性が正しく REMOVE される 🔵 *H-2 より*
- EDGE-102: `description` と `color` を同時に null に設定したデッキ更新リクエストで、両属性が正しく REMOVE される 🔵 *M-3 より*

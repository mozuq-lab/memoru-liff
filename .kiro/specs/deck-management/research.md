# Research & Design Decisions

## Summary
- **Feature**: `deck-management`
- **Discovery Scope**: Extension（既存システムの拡張）
- **Key Findings**:
  - Card モデルに `deck_id` フィールドが既に存在し、`list_cards` のフィルタリング・`create_card` / `update_card` の受け付けも実装済み。新規テーブルと API エンドポイントの追加が主な作業。
  - 既存の handler.py は単一ファイルに全エンドポイントを定義するパターン。デッキ CRUD エンドポイントも同ファイルに追加する。
  - デッキ削除時のカード `deck_id` 一括更新は DynamoDB の制約（トランザクション最大 100 アイテム）を考慮し、バッチ更新方式を採用する必要がある。

## Research Log

### 既存 deck_id フィールドの利用状況
- **Context**: cards テーブルに `deck_id` が既に定義されているが、どの程度活用されているか確認
- **Sources Consulted**: `backend/src/models/card.py`, `backend/src/services/card_service.py`, `frontend/src/types/card.ts`
- **Findings**:
  - バックエンド `Card` Pydantic モデル: `deck_id: Optional[str] = None`
  - `create_card()`: `deck_id` パラメータを受け付け、DynamoDB アイテムに保存
  - `update_card()`: `deck_id` を UpdateExpression で更新可能
  - `list_cards()`: `deck_id` による `FilterExpression` フィルタリング対応済み
  - `to_dynamodb_item()`: `deck_id` が truthy な場合のみアイテムに含める
  - フロントエンド `Card` 型: `deck_id?: string | null`
  - `CreateCardRequest`: `deck_id?: string`
  - `UpdateCardRequest`: `deck_id?: string`
- **Implications**: バックエンドのカード CRUD は deck_id に対応済み。デッキの存在バリデーション（指定された deck_id が実在するか）は未実装のため、DeckService 側で追加が必要。

### DynamoDB テーブル設計パターン
- **Context**: 既存テーブル（Users, Cards, Reviews）の設計パターンを踏襲して Decks テーブルを設計
- **Sources Consulted**: `backend/template.yaml`, `backend/docker-compose.yaml`
- **Findings**:
  - 全テーブル: PAY_PER_REQUEST、PointInTimeRecovery 有効、SSE (KMS)、prod 環境で DeletionProtection
  - Users: PK=`user_id` (HASH)、GSI=`line_user_id-index`
  - Cards: PK=`user_id` (HASH) + SK=`card_id` (RANGE)、GSI=`user_id-due-index`
  - Reviews: PK=`card_id` (HASH) + SK=`reviewed_at` (RANGE)、GSI=`user_id-reviewed_at-index`
  - テーブル名規則: `memoru-{resource}-{Environment}`
- **Implications**: Decks テーブルは `user_id` (HASH) + `deck_id` (RANGE) で設計。GSI は不要（ユーザー単位のクエリのみ）。既存パターンに完全準拠。

### デッキ削除時のカード一括更新
- **Context**: デッキ削除時に属するカードの `deck_id` を null にリセットする方法
- **Sources Consulted**: DynamoDB TransactWriteItems 制限、既存 delete_card 実装
- **Findings**:
  - DynamoDB TransactWriteItems は最大 100 アイテム/トランザクション
  - カードは 1 ユーザー最大 2000 枚（`MAX_CARDS_PER_USER = 2000`）
  - 1 デッキに属するカード数は可変（数十〜数百枚の可能性）
  - 既存の delete_card は TransactWriteItems で Cards 削除 + Users card_count デクリメントをアトミックに実行
- **Implications**: デッキ削除時のカード更新は、`list_cards(deck_id=xxx)` で対象カードを取得し、`BatchWriter` で `deck_id` を `null` に一括更新するベストエフォート方式が適切。トランザクション保証は不要（カードの `deck_id` が残っても致命的ではない）。

### handler.py のエンドポイント追加パターン
- **Context**: 既存の handler.py にデッキ CRUD エンドポイントを追加する方法
- **Sources Consulted**: `backend/src/api/handler.py`
- **Findings**:
  - 単一 handler.py に全エンドポイント定義（User, Card, Review, AI Generation）
  - `APIGatewayHttpResolver` のデコレータ（`@app.get`, `@app.post`, `@app.put`, `@app.delete`）でルーティング
  - サービスはモジュールスコープでインスタンス化（`card_service = CardService()`）
  - エラーハンドリング: ドメイン例外 → HTTP レスポンスマッピング
  - template.yaml の Events セクションに HTTP API イベントを追加する必要あり
- **Implications**: `deck_service = DeckService()` をモジュールスコープで初期化し、`# Deck Endpoints` セクションとしてエンドポイントを追加。既存パターンに完全準拠。

### フロントエンド Context パターン
- **Context**: DecksContext の設計パターンを既存の CardsContext から学ぶ
- **Sources Consulted**: `frontend/src/contexts/CardsContext.tsx`, `frontend/src/App.tsx`
- **Findings**:
  - `createContext` + `useContext` パターン
  - Provider で `useState` / `useCallback` / `useMemo` を使用
  - `useCardsContext` フックで型安全なコンテキスト取得
  - App.tsx: `AuthProvider` → `CardsProvider` のネスト順
  - Barrel export: `contexts/index.ts` から re-export
- **Implications**: `DecksProvider` を `CardsProvider` と同階層に配置。`useDecksContext` フックを提供。`contexts/index.ts` に追加。

### フロントエンド API サービスパターン
- **Context**: decksApi の設計パターン
- **Sources Consulted**: `frontend/src/services/api.ts`
- **Findings**:
  - `ApiClient` クラスに全 API メソッドを集約
  - ドメイン別に `cardsApi`, `reviewsApi`, `usersApi` のファサードオブジェクトを export
  - 認証トークン自動付与・401 リフレッシュ処理は `request()` メソッドで共通化
- **Implications**: `ApiClient` にデッキ CRUD メソッドを追加し、`decksApi` ファサードを export。

### ReviewPage のデッキフィルタリング対応
- **Context**: 復習画面でデッキ指定のセッションをサポートする方法
- **Sources Consulted**: `frontend/src/pages/ReviewPage.tsx`
- **Findings**:
  - `fetchCards` で `cardsApi.getDueCards()` を呼び出し
  - URL パラメータの読み取りは未実装
  - `useSearchParams` を使えば `?deck_id=xxx` クエリパラメータを取得可能
- **Implications**: ReviewPage に `useSearchParams` を追加し、`deck_id` パラメータがあれば `getDueCards` に渡す。バックエンドの `GET /cards/due` に `deck_id` フィルタリングを追加。

## Architecture Pattern Evaluation

| Option | Description | Strengths | Risks / Limitations | Notes |
|--------|-------------|-----------|---------------------|-------|
| 既存レイヤードアーキテクチャ踏襲 | handler → DeckService → Deck model の3層 | 既存パターンと一貫性、学習コスト低 | handler.py の肥大化 | 採用: プロジェクト規約に完全準拠 |
| 別 Lambda 分離 | デッキ CRUD を別 Lambda Function に分離 | 責務分離、デプロイ独立性 | 設定の重複、コールドスタート増加 | 不採用: 現段階では過剰な分離 |

## Design Decisions

### Decision: Decks テーブルのキー設計
- **Context**: デッキの一意識別とクエリパターンの最適化
- **Alternatives Considered**:
  1. PK=`deck_id` のみ — シンプルだがユーザー別クエリに GSI が必要
  2. PK=`user_id` + SK=`deck_id` — ユーザー別クエリがネイティブ
- **Selected Approach**: PK=`user_id` + SK=`deck_id`
- **Rationale**: Cards テーブルと同じパターン。`Query(user_id=xxx)` で特定ユーザーの全デッキを効率的に取得可能。GSI 不要でコスト削減。
- **Trade-offs**: deck_id のみでのクロスユーザー検索は不可（要件にない）
- **Follow-up**: なし

### Decision: デッキ削除時のカード更新方式
- **Context**: デッキ削除時に属するカードの deck_id を null にリセットする必要がある
- **Alternatives Considered**:
  1. TransactWriteItems — アトミック保証だが 100 アイテム制限
  2. BatchWriter（ベストエフォート）— 制限なし、整合性は結果整合
  3. 遅延処理（SQS/Lambda）— 非同期で処理
- **Selected Approach**: BatchWriter によるベストエフォート一括更新
- **Rationale**: デッキ削除は低頻度操作。カードに古い deck_id が残っても致命的ではない（デッキ不存在の deck_id を持つカードは未分類として扱う）。SQS 導入は現段階では過剰。
- **Trade-offs**: 大量カード（100枚超）がデッキに属する場合、部分失敗の可能性あり
- **Follow-up**: 失敗時のログ記録を実装

### Decision: GET /decks レスポンスにカード数・due 数を含める方式
- **Context**: デッキ一覧でカード数と due カード数を表示する必要がある
- **Alternatives Considered**:
  1. Decks テーブルに `card_count` を持ち、カード CRUD 時にインクリメント/デクリメント — リアルタイムだがトランザクション複雑
  2. GET /decks 呼び出し時に Cards テーブルを都度クエリ — シンプルだがレイテンシ増
  3. フロントエンドで個別に集計 — API 呼び出し数増加
- **Selected Approach**: GET /decks 呼び出し時に Cards テーブルからデッキ別カード数を集計
- **Rationale**: デッキ数は最大 50、カード数は最大 2000。DynamoDB Query (Select=COUNT) で効率的に集計可能。リアルタイム性を保証でき、トランザクション複雑化を回避。
- **Trade-offs**: デッキ数が多い場合（50デッキ）に DynamoDB Query が50回発生。並列実行で緩和。
- **Follow-up**: パフォーマンスが問題になった場合は Decks テーブルに card_count カラムを追加する方式に移行

## Risks & Mitigations
- **handler.py 肥大化** — デッキ CRUD で約 150 行追加。現在約 800 行のため約 950 行に。将来的にはドメイン別ファイル分割を検討。
- **デッキ削除のカード更新失敗** — ベストエフォート方式のため部分失敗の可能性。ログ記録でモニタリング。
- **GET /decks のレイテンシ** — デッキ数分の DynamoDB Query が必要。asyncio.gather による並列化、またはキャッシュ導入で緩和。

## References
- [DynamoDB TransactWriteItems 制約](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html) — 最大 100 アイテム/トランザクション
- [AWS Lambda Powertools APIGatewayHttpResolver](https://docs.powertools.aws.dev/lambda/python/latest/core/event_handler/api_gateway/) — エンドポイント定義パターン
- [Pydantic v2 モデル定義](https://docs.pydantic.dev/latest/) — Field バリデーション

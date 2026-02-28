# Implementation Plan

## Phase 1: バックエンド基盤

- [x] 1. インフラストラクチャ: DecksTable 定義と環境変数追加
- [x] 1.1 SAM テンプレート（template.yaml）に DecksTable リソースを追加 (P)
  - `DecksTable` DynamoDB テーブル定義: PK=`user_id` (S), SK=`deck_id` (S)
  - PAY_PER_REQUEST, PointInTimeRecovery, SSE (KMS), DeletionProtection (prod のみ)
  - テーブル名: `memoru-decks-${Environment}`
  - Globals 環境変数に `DECKS_TABLE: !Ref DecksTable` を追加
  - `ApiFunction` に `DynamoDBCrudPolicy` を追加（DecksTable 用）
  - `ApiFunction` Events に Deck CRUD エンドポイント（ListDecks, CreateDeck, UpdateDeck, DeleteDeck）を追加
  - `LineWebhookFunction`, `DuePushJobFunction` のポリシーに DecksTable の Read 権限を追加（将来対応用、任意）
  - _Requirements: 2.1, 2.4_
- [x] 1.2 docker-compose.yaml にローカル DecksTable 作成コマンドを追加 (P)
  - `dynamodb-init` サービスの command に `aws dynamodb create-table` を追加
  - `--table-name memoru-decks-dev`, PK=`user_id` (S), SK=`deck_id` (S), `--billing-mode PAY_PER_REQUEST`
  - _Requirements: 2.5_

- [x] 2. バックエンドモデル: Deck Pydantic モデル定義
- [x] 2.1 `backend/src/models/deck.py` を作成 (P)
  - `Deck` クラス: `deck_id` (UUID v4 自動生成), `user_id`, `name`, `description` (Optional), `color` (Optional), `created_at`, `updated_at` (Optional)
  - `to_dynamodb_item()` / `from_dynamodb_item()` メソッド（既存 Card モデルのパターンに準拠）
  - `to_response(card_count, due_count)` メソッド
  - `CreateDeckRequest`: `name` (1〜100 文字, 必須), `description` (Optional, 500 文字以下), `color` (Optional, HEX カラー)
  - `UpdateDeckRequest`: `name` (Optional, 1〜100 文字), `description` (Optional), `color` (Optional)
  - `DeckResponse`: 全フィールド + `card_count`, `due_count`
  - `DeckListResponse`: `decks: list[DeckResponse]`, `total: int`
  - _Requirements: 1.6, 2.2, 2.3, 2.6_

- [ ] 3. バックエンドサービス: DeckService 実装
- [ ] 3.1 `backend/src/services/deck_service.py` を作成
  - `DeckServiceError`, `DeckNotFoundError`, `DeckLimitExceededError` 例外クラス定義
  - `DeckService.__init__()`: `DECKS_TABLE` / `CARDS_TABLE` 環境変数からテーブル名取得、boto3 リソース初期化
  - `create_deck()`: デッキ数上限チェック（Query Select=COUNT で現在数取得、50 超で DeckLimitExceededError）、Deck インスタンス生成、`put_item` で保存
  - `get_deck()`: `get_item` でデッキ取得、存在しない場合 DeckNotFoundError
  - `list_decks()`: `Query(user_id=xxx)` で全デッキ取得
  - `update_deck()`: `get_deck` で存在確認後、UpdateExpression で更新
  - `delete_deck()`: `get_deck` で存在確認 → `delete_item` → Cards テーブルから `deck_id` 一致カード取得 → `batch_writer` で `deck_id` を null に更新（ベストエフォート）
  - `get_deck_card_counts()`: Cards テーブル Query + FilterExpression でデッキ別カード数を集計
  - `get_deck_due_counts()`: Cards テーブル Query (user_id-due-index) + FilterExpression でデッキ別 due 数を集計
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7, 3.5_

- [ ] 4. バックエンドハンドラー: デッキ CRUD エンドポイント追加
- [ ] 4.1 handler.py にデッキ CRUD エンドポイントを追加
  - `from services.deck_service import DeckService, DeckNotFoundError, DeckLimitExceededError` をインポート
  - `from models.deck import CreateDeckRequest, UpdateDeckRequest, DeckListResponse` をインポート
  - `deck_service = DeckService()` をモジュールスコープで初期化
  - `POST /decks` → `create_deck()`: Pydantic バリデーション → DeckService.create_deck → DeckResponse (201)
  - `GET /decks` → `list_decks()`: DeckService.list_decks → get_deck_card_counts / get_deck_due_counts → DeckListResponse
  - `PUT /decks/<deck_id>` → `update_deck()`: Pydantic バリデーション → DeckService.update_deck → DeckResponse
  - `DELETE /decks/<deck_id>` → `delete_deck()`: DeckService.delete_deck → 204 No Content
  - DeckNotFoundError → NotFoundError (404)、DeckLimitExceededError → Response(400)、ValidationError → Response(400)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8_
- [ ] 4.2 handler.py の `get_due_cards()` に `deck_id` フィルタリングを追加 (P)
  - クエリパラメータから `deck_id` を取得
  - `review_service.get_due_cards()` に `deck_id` パラメータを渡す
  - `ReviewService.get_due_cards()` で `deck_id` フィルタリングを実装（CardService.get_due_cards の結果をフィルタ、または CardService に deck_id パラメータ追加）
  - _Requirements: 3.4_

## Phase 2: フロントエンド基盤

- [ ] 5. フロントエンド型定義・API サービス・Context
- [ ] 5.1 `frontend/src/types/deck.ts` を作成し、`types/index.ts` に re-export を追加 (P)
  - `Deck` interface: `deck_id`, `user_id`, `name`, `description?`, `color?`, `card_count`, `due_count`, `created_at`, `updated_at?`
  - `CreateDeckRequest` interface: `name`, `description?`, `color?`
  - `UpdateDeckRequest` interface: `name?`, `description?`, `color?`
  - `DeckListResponse` interface: `decks: Deck[]`, `total: number`
  - `types/index.ts` に `export type * from './deck';` を追加
  - _Requirements: 8.4_
- [ ] 5.2 `frontend/src/services/api.ts` にデッキ API メソッドを追加 (P)
  - `ApiClient` クラスに `getDecks()`, `createDeck()`, `updateDeck()`, `deleteDeck()` メソッドを追加
  - `decksApi` ファサードオブジェクトを export
  - `getDueCards()` に `deckId` オプションパラメータを追加（`?deck_id=xxx` クエリパラメータ付与）
  - _Requirements: 8.3_
- [ ] 5.3 `frontend/src/contexts/DecksContext.tsx` を作成し、`contexts/index.ts` に追加
  - `DecksContextType`: `decks`, `isLoading`, `error`, `fetchDecks`, `createDeck`, `updateDeck`, `deleteDeck`
  - `DecksProvider`: `useState` / `useCallback` / `useMemo` パターン（CardsContext に準拠）
  - `useDecksContext` フック
  - CUD 操作後に `fetchDecks()` を自動再取得
  - `contexts/index.ts` に `DecksProvider`, `useDecksContext` を追加
  - _Requirements: 8.1, 8.2, 8.5_
- [ ] 5.4 `App.tsx` に `DecksProvider` と `/decks` ルートを追加
  - `DecksProvider` を `CardsProvider` と並列でラップ（`AuthProvider` → `DecksProvider` + `CardsProvider`）
  - `<Route path="/decks" element={<ProtectedRoute><DecksPage /></ProtectedRoute>} />` を追加
  - `import { DecksPage } from '@/pages'` を追加
  - `pages/index.ts` に `DecksPage` を追加
  - _Requirements: 4.7, 8.2_

## Phase 3: フロントエンド UI

- [ ] 6. デッキ管理画面
- [ ] 6.1 `frontend/src/components/DeckFormModal.tsx` を作成 (P)
  - Props: `mode: 'create' | 'edit'`, `deck?: Deck`, `isOpen: boolean`, `onClose: () => void`, `onSubmit: (data: CreateDeckRequest | UpdateDeckRequest) => Promise<void>`
  - フィールド: デッキ名（必須、1〜100 文字）、説明（任意）、カラー（プリセットカラーパレットから選択）
  - モーダルオーバーレイ、閉じるボタン、キャンセル/保存ボタン
  - バリデーション: クライアントサイドでデッキ名の空チェック
  - _Requirements: 4.2, 4.4_
- [ ] 6.2 `frontend/src/pages/DecksPage.tsx` を作成
  - デッキ一覧表示: カード数・due 数バッジ、カラーインジケーター
  - 「デッキを作成」ボタン → DeckFormModal (create モード)
  - デッキカードタップ → `/cards?deck_id=xxx` に遷移
  - 編集ボタン → DeckFormModal (edit モード)
  - 削除ボタン → 確認ダイアログ → deleteDeck
  - 「復習する」ボタン → `/review?deck_id=xxx` に遷移（due_count > 0 の場合のみアクティブ）
  - 「未分類」セクション: `deck_id` なしのカード数を表示
  - Navigation コンポーネントを含む
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.1_

- [ ] 7. 共有コンポーネント
- [ ] 7.1 `frontend/src/components/DeckSelector.tsx` を作成 (P)
  - Props: `value?: string | null`, `onChange: (deckId: string | null) => void`, `className?: string`
  - DecksContext から `decks` を消費
  - `<select>` で「未分類」+ デッキ一覧を表示（カラーインジケーター付き）
  - _Requirements: 5.3, 5.4_
- [ ] 7.2 `frontend/src/components/DeckSummary.tsx` を作成 (P)
  - DecksContext から `decks` を消費
  - 最大 5 件のデッキを due 数付きで表示
  - デッキ 0 件時は「デッキを作成して学習を整理しましょう」メッセージ
  - 5 件超の場合「すべて表示」リンク → `/decks` に遷移
  - デッキタップ → `/cards?deck_id=xxx` に遷移
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [ ] 8. 既存ページ拡張
- [ ] 8.1 Navigation.tsx にデッキタブを追加 (P)
  - `navItems` 配列に `{ path: '/decks', label: 'デッキ', icon: <FolderIcon /> }` を追加
  - 「カード」タブの前に配置（ホーム → 作成 → デッキ → カード → 設定）
  - _Requirements: 4.8_
- [ ] 8.2 ReviewPage.tsx にデッキ指定復習対応を追加 (P)
  - `useSearchParams` で `deck_id` クエリパラメータを取得（既に `useSearchParams` なし → `useSearchParams` を追加）
  - `fetchCards` 内で `deck_id` がある場合は `cardsApi.getDueCards(limit, deckId)` に渡す
  - due カード 0 件時のメッセージをデッキ指定時用に変更（「このデッキに復習対象のカードはありません」）
  - _Requirements: 6.2, 6.3, 6.4_
- [ ] 8.3 HomePage.tsx にデッキサマリーセクションを追加 (P)
  - `DeckSummary` コンポーネントを復習カード数セクションの下に配置
  - DecksContext の `fetchDecks` を `useEffect` で呼び出し
  - _Requirements: 7.1, 7.2, 7.3, 7.4_
- [ ] 8.4 GeneratePage・CardDetailPage に DeckSelector を統合
  - GeneratePage: AI 生成カード保存時にデッキ選択を追加
  - CardDetailPage: 編集モードでデッキ変更を追加
  - _Requirements: 5.1, 5.2_

- [ ]* 9. テスト
- [ ]* 9.1 バックエンドユニットテスト (P)
  - `tests/unit/test_deck_model.py`: Pydantic バリデーション（名前長制限、カラー形式、UUID 自動生成）
  - `tests/unit/test_deck_service.py`: DeckService CRUD、上限チェック、デッキ削除時カード更新（moto DynamoDB モック）
  - `tests/unit/test_handler_decks.py`: デッキ CRUD エンドポイント、エラーレスポンス
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 2.2, 2.3, 3.4, 3.5_
- [ ]* 9.2 フロントエンドユニットテスト (P)
  - `components/__tests__/DeckSelector.test.tsx`: デッキ選択・未分類オプション
  - `components/__tests__/DeckSummary.test.tsx`: サマリー表示・0 件メッセージ
  - `contexts/__tests__/DecksContext.test.tsx`: fetch・CUD 操作・エラーハンドリング
  - `pages/__tests__/DecksPage.test.tsx`: デッキ表示・作成・編集・削除 UI
  - _Requirements: 4.1, 4.2, 4.4, 4.5, 5.3, 7.1, 7.4, 8.1, 8.5_

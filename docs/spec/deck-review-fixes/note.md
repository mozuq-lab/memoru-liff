# deck-review-fixes 開発コンテキストノート

## 作成日時
2026-02-28

## プロジェクト概要

### プロジェクト名
Memoru LIFF

### プロジェクトの目的
LINE ベースの暗記カードアプリケーション。AI がテキストからフラッシュカードを自動生成し、SM-2 アルゴリズムによる間隔反復学習（SRS）で効率的な暗記を支援する。

**参照元**: [CLAUDE.md](../../CLAUDE.md)

## 技術スタック

### 使用技術・フレームワーク
- **言語**: Python 3.12（バックエンド）, TypeScript（フロントエンド）
- **フレームワーク**: AWS SAM + Lambda Powertools（バックエンド）, React + Vite（フロントエンド）
- **ランタイム**: AWS Lambda（Python 3.12）, Node.js（Vite dev）
- **パッケージマネージャー**: pip（バックエンド）, npm（フロントエンド）
- **データベース**: DynamoDB（マルチテーブル設計）
- **認証**: Keycloak（OIDC + PKCE）

### アーキテクチャパターン
- **アーキテクチャスタイル**: サーバーレス（Lambda + API Gateway + DynamoDB）
- **設計パターン**: レイヤード（handler → service → model）、React Context + Hooks
- **ディレクトリ構造**: `backend/src/api/handler.py`（単一ハンドラ）, `backend/src/services/`（ドメインサービス）, `frontend/src/pages/`（ページコンポーネント）

**参照元**:
- [CLAUDE.md](../../CLAUDE.md)
- [docs/design/memoru-liff/architecture.md](../../design/memoru-liff/architecture.md)

## 開発ルール

### プロジェクト固有のルール
- Tsumiki プラグインの Kairo ワークフローを使用
- TDD タスクと DIRECT タスクの2種類
- タスクごとにコミット（複数タスクをまとめない）
- コミットメッセージにタスク ID を含める

### コーディング規約
- **命名規則**: Python は snake_case、TypeScript は camelCase/PascalCase
- **型チェック**: Pydantic v2（バックエンド）、TypeScript strict（フロントエンド）
- **コメント**: 日本語コメント対応
- **フォーマット**: ESLint, Tailwind CSS

### テスト要件
- **テストフレームワーク**: pytest（バックエンド）, Vitest（フロントエンド）
- **カバレッジ要件**: 80% 以上
- **テストパターン**: moto（DynamoDB モック）, React Testing Library

**参照元**:
- [AGENTS.md](../../AGENTS.md)
- [CLAUDE.md](../../CLAUDE.md)

## 既存の要件定義

### 本要件の背景

`feature/deck-management-spec` ブランチでデッキ管理機能（CRUD + カード紐付け）を実装済み。Claude / Codex による統合レビューで **Critical 1件、High 2件、Medium 5件、Low 4件** の指摘が発見された。本要件はそれらの修正を対象とする。

**参照元**: [docs/review-deck-management-spec.md](../../review-deck-management-spec.md)

### レビュー指摘一覧

#### Critical（必須修正、マージブロック）

| ID | 概要 | 対象ファイル | 状態 |
|----|------|-------------|------|
| C-1 | `DecksProvider` の未エクスポート（ビルド不能） | `frontend/src/contexts/index.ts` | **修正済み**（最新コミット 4463002 で対応済み） |

#### High（必須修正、マージブロック）

| ID | 概要 | 対象ファイル | 状態 |
|----|------|-------------|------|
| H-1 | `CardsPage` で `deck_id` クエリパラメータ未対応（デッキ別カード一覧が機能しない） | `frontend/src/pages/CardsPage.tsx`, `frontend/src/contexts/CardsContext.tsx` | 未修正 |
| H-2 | カードを「未分類」に戻せない（`deck_id` の null 解除不可能） | `frontend/src/pages/CardDetailPage.tsx`, `frontend/src/types/card.ts`, `backend/src/services/card_service.py` | 未修正 |

#### Medium（推奨修正）

| ID | 概要 | 対象ファイル | 状態 |
|----|------|-------------|------|
| M-1 | `GET /cards/due?deck_id=xxx` の `total_due_count` がフィルタ後のリスト長で過少 | `backend/src/services/review_service.py` | 未修正 |
| M-2 | `App.tsx` の Provider ネスト順序が設計と不整合 | `frontend/src/App.tsx` | 未修正 |
| M-3 | `UpdateDeckRequest` の description/color フィールドクリア操作が曖昧 | `backend/src/models/deck.py`, `backend/src/services/deck_service.py` | 未修正 |
| M-4 | `DeckFormModal` の edit モードで不要な更新が発生する可能性 | `frontend/src/components/DeckFormModal.tsx` | 未修正 |
| M-5 | `get_deck_card_counts` / `get_deck_due_counts` が全カードをスキャン | `backend/src/services/deck_service.py` | 未修正（MVP 許容範囲） |

#### Low（任意修正）

| ID | 概要 | 対象ファイル | 状態 |
|----|------|-------------|------|
| L-1 | `DeckSelector` / `DeckSummary` の `'unassigned'` フィルタリングが不要 | `frontend/src/components/DeckSelector.tsx`, `DeckSummary.tsx` | 未修正 |
| L-2 | `handler.py` の肥大化（約 950 行） | `backend/src/api/handler.py` | 未修正（後続タスク） |
| L-3 | コメントスタイルの不統一 | フロントエンドコンポーネント全般 | 未修正 |
| L-4 | `CardDetailPage` のデッキ変更後にコンテキストが陳腐化 | `frontend/src/pages/CardDetailPage.tsx` | 未修正 |

### 修正優先度

レビュー結論に基づき:
- **C-1**: 修正済み
- **H-1, H-2**: **必須修正**（マージブロック）
- **M-1**: **推奨修正**（total_due_count の正確性）
- **M-2〜M-5, L-1〜L-4**: 後続タスクとして対応可

## 既存の設計文書

### データベーススキーマ（デッキ関連）

#### DecksTable
- **PK**: `user_id` (String)
- **SK**: `deck_id` (String)
- **属性**: `name`, `description`, `color`, `created_at`, `updated_at`
- **制限**: ユーザーあたり最大 50 デッキ

#### CardsTable（デッキ拡張）
- **追加属性**: `deck_id` (Optional) - カードが所属するデッキ ID
- **GSI**: `user_id-due-index` - 復習対象カード取得に使用

**参照元**:
- [docs/design/memoru-liff/database-schema.md](../../design/memoru-liff/database-schema.md)
- [backend/template.yaml](../../../backend/template.yaml)

### API エンドポイント（デッキ関連）

| メソッド | パス | 説明 |
|---------|------|------|
| POST | `/decks` | デッキ作成 |
| GET | `/decks` | デッキ一覧取得（card_count / due_count 付き） |
| PUT | `/decks/<deck_id>` | デッキ更新 |
| DELETE | `/decks/<deck_id>` | デッキ削除（カードは未分類に移動） |
| GET | `/cards?deck_id=xxx` | デッキ別カード一覧（バックエンド対応済み） |
| GET | `/cards/due?deck_id=xxx` | デッキ別復習対象カード取得 |

**参照元**: [docs/design/memoru-liff/api-endpoints.md](../../design/memoru-liff/api-endpoints.md)

## 関連実装

### バックエンド

#### デッキサービス
- `backend/src/models/deck.py` - Deck Pydantic モデル（CreateDeckRequest, UpdateDeckRequest, Deck, DeckResponse）
- `backend/src/services/deck_service.py` - DeckService（CRUD + card_count/due_count 集計）
- `backend/src/api/handler.py` - `/decks` エンドポイント（約 150 行追加）

#### カードサービス（デッキ関連）
- `backend/src/services/card_service.py` - `create_card(deck_id=)`, `update_card(deck_id=)`, `list_cards(deck_id=)`
- `backend/src/services/review_service.py` - `get_due_cards(deck_id=)` にフィルタ対応

#### テスト
- `backend/tests/unit/test_deck_model.py` - モデルバリデーション 27 テスト
- `backend/tests/unit/test_deck_service.py` - サービス 25 テスト（moto モック）

### フロントエンド

#### ページ
- `frontend/src/pages/DecksPage.tsx` - デッキ一覧・CRUD 画面
- `frontend/src/pages/CardsPage.tsx` - カード一覧（**deck_id フィルタ未対応 = H-1**）
- `frontend/src/pages/CardDetailPage.tsx` - カード詳細（**null 解除不可 = H-2**）

#### コンポーネント
- `frontend/src/components/DeckFormModal.tsx` - デッキ作成・編集モーダル
- `frontend/src/components/DeckSelector.tsx` - デッキ選択ドロップダウン
- `frontend/src/components/DeckSummary.tsx` - ホーム画面デッキサマリー

#### コンテキスト
- `frontend/src/contexts/DecksContext.tsx` - デッキ状態管理（fetchDecks, createDeck, updateDeck, deleteDeck）
- `frontend/src/contexts/CardsContext.tsx` - カード状態管理

#### 型定義
- `frontend/src/types/deck.ts` - Deck, CreateDeckRequest, UpdateDeckRequest, DeckListResponse
- `frontend/src/types/card.ts` - Card（deck_id?: string | null）, UpdateCardRequest（**deck_id?: string — null 非許容 = H-2**）

#### テスト
- `frontend/src/pages/__tests__/DecksPage.test.tsx` - ページテスト 14 テスト
- `frontend/src/components/__tests__/DeckSelector.test.tsx` - コンポーネントテスト
- `frontend/src/components/__tests__/DeckSummary.test.tsx` - コンポーネントテスト
- `frontend/src/__tests__/DecksContext.test.tsx` - コンテキストテスト 11 テスト

**参照元**:
- [backend/src/services/deck_service.py](../../../backend/src/services/deck_service.py)
- [frontend/src/pages/DecksPage.tsx](../../../frontend/src/pages/DecksPage.tsx)
- [frontend/src/contexts/DecksContext.tsx](../../../frontend/src/contexts/DecksContext.tsx)

### 参考パターン

#### 既存のコードレビュー修正ワークフロー
- `docs/spec/code-review-remediation/` - コードレビュー修正 第1弾
- `docs/spec/code-review-fixes-v2/` - コードレビュー修正 第2弾
- いずれも Critical → High → Medium の優先度順に修正

#### update_card の deck_id 処理パターン（H-2 の修正に関連）
```python
# card_service.py 現在の実装
if deck_id is not None:
    update_parts.append("deck_id = :deck_id")
    expression_values[":deck_id"] = deck_id
    card.deck_id = deck_id
# → deck_id=None（未指定）と deck_id を明示的に null にしたい場合の区別がつかない
# → 修正案: sentinel 値または REMOVE 式で対応
```

#### CardsPage の fetchCards パターン（H-1 の修正に関連）
```typescript
// CardsPage.tsx 現在の実装
const { cards, dueCards, isLoading, error, fetchCards, fetchDueCards } = useCardsContext();
// → fetchCards() は deck_id パラメータを受け付けていない
// → バックエンド GET /cards?deck_id=xxx は対応済み
// → CardsContext.fetchCards を deck_id 対応にする or CardsPage 内で直接 API 呼び出し
```

### 共通モジュール・ユーティリティ
- `frontend/src/services/api.ts` - ApiClient（`cardsApi.getDueCards(limit, deckId)` は deck_id 対応済み）
- `frontend/src/contexts/CardsContext.tsx` - fetchCards, fetchDueCards（deck_id パラメータ未対応）

## 技術的制約

### パフォーマンス制約
- DynamoDB 1MB 読み取り制限内（カード最大 2000 枚、デッキ最大 50）
- `get_deck_card_counts` / `get_deck_due_counts` は全カードスキャン（MVP 許容）

### セキュリティ制約
- JWT 認証必須（全 API エンドポイント）
- user_id はトークンの sub クレームから取得（他ユーザーのリソースにアクセス不可）

### 互換性制約
- LINE LIFF SDK 対応（モバイルファースト UI）
- タッチターゲット最小 44px

### データ制約
- デッキ名: 1-100 文字
- デッキ説明: 0-500 文字
- カラーコード: `#[0-9A-Fa-f]{6}` 形式
- ユーザーあたり最大 50 デッキ
- ユーザーあたり最大 2000 カード

## 注意事項

### 開発時の注意点
- C-1 は最新コミット（4463002）で修正済み。H-1, H-2, M-1 が残りの主要修正対象
- H-2 は フロントエンド型定義 → フロントエンド送信ロジック → バックエンドサービスの 3 層にまたがる修正が必要
- H-1 はフロントエンドのみの修正（バックエンドは対応済み）
- M-1 はバックエンドのみの修正（フロントエンドの表示ロジックは `total_due_count` を使用済み）

### デプロイ・運用時の注意点
- AWS リソースのデプロイはユーザーが手動で実行
- DecksTable は既に `template.yaml` に定義済み

### セキュリティ上の注意点
- `deck_id` フィルタリングはバックエンド側で user_id と組み合わせて実行（他ユーザーのデッキにアクセス不可）

### パフォーマンス上の注意点
- M-1 の修正で `limit` なしクエリを実行する場合、カード数が多いユーザーでのパフォーマンスを考慮
- M-5 は MVP 段階では許容（カード最大 2000 枚、DynamoDB の ProjectionExpression 使用）

## Git情報

### 現在のブランチ
`feature/deck-management-spec`（origin と同期済み）

### 最近のコミット
```
4463002 fix(deck): DecksProvider の re-export 追加 + レビュードキュメント追加
37788f6 test(deck): Task 9 - バックエンド・フロントエンドユニットテスト
b2a1f32 feat(deck): Task 7,8 - 共有コンポーネント + 既存ページ拡張
03f0ec0 feat(deck): Task 5,6 - フロントエンド基盤 + デッキ管理画面
94bf030 feat(deck): Task 3,4 - DeckService 実装 + handler.py デッキ CRUD エンドポイント追加
473fe4d feat(deck): Task 1,2 - DecksTable インフラ定義 + Deck Pydantic モデル実装
083e342 feat(spec): deck-management 全フェーズ承認完了 - 実装準備完了
be6a0e0 feat(spec): deck-management タスク分解完了 - tasks.md 生成、設計承認
2979bd8 feat(spec): deck-management 設計フェーズ完了 - research.md / design.md 生成、要件承認
ca16dc7 feat(spec): deck-management の spec 初期化と要件定義を追加
```

### 開発状況
- `feature/deck-management-spec` ブランチでデッキ管理機能の実装完了
- Claude / Codex 統合レビュー完了、C-1 修正済み
- **H-1, H-2, M-1 の修正が残り**（本要件の対象）

## 収集したファイル一覧

### プロジェクト基本情報
- [CLAUDE.md](../../CLAUDE.md)
- [AGENTS.md](../../AGENTS.md)

### レビュードキュメント
- [docs/review-deck-management-spec.md](../../review-deck-management-spec.md)

### 設計文書
- [docs/design/memoru-liff/api-endpoints.md](../../design/memoru-liff/api-endpoints.md)
- [docs/design/memoru-liff/database-schema.md](../../design/memoru-liff/database-schema.md)
- [docs/system-overview.md](../../system-overview.md)

### バックエンド実装
- [backend/src/models/deck.py](../../../backend/src/models/deck.py)
- [backend/src/models/card.py](../../../backend/src/models/card.py)
- [backend/src/services/deck_service.py](../../../backend/src/services/deck_service.py)
- [backend/src/services/card_service.py](../../../backend/src/services/card_service.py)
- [backend/src/services/review_service.py](../../../backend/src/services/review_service.py)
- [backend/src/api/handler.py](../../../backend/src/api/handler.py)
- [backend/template.yaml](../../../backend/template.yaml)

### フロントエンド実装
- [frontend/src/App.tsx](../../../frontend/src/App.tsx)
- [frontend/src/types/card.ts](../../../frontend/src/types/card.ts)
- [frontend/src/types/deck.ts](../../../frontend/src/types/deck.ts)
- [frontend/src/services/api.ts](../../../frontend/src/services/api.ts)
- [frontend/src/contexts/DecksContext.tsx](../../../frontend/src/contexts/DecksContext.tsx)
- [frontend/src/contexts/CardsContext.tsx](../../../frontend/src/contexts/CardsContext.tsx)
- [frontend/src/pages/DecksPage.tsx](../../../frontend/src/pages/DecksPage.tsx)
- [frontend/src/pages/CardsPage.tsx](../../../frontend/src/pages/CardsPage.tsx)
- [frontend/src/pages/CardDetailPage.tsx](../../../frontend/src/pages/CardDetailPage.tsx)
- [frontend/src/components/DeckFormModal.tsx](../../../frontend/src/components/DeckFormModal.tsx)
- [frontend/src/components/DeckSelector.tsx](../../../frontend/src/components/DeckSelector.tsx)
- [frontend/src/components/DeckSummary.tsx](../../../frontend/src/components/DeckSummary.tsx)

### テスト
- [backend/tests/unit/test_deck_model.py](../../../backend/tests/unit/test_deck_model.py)
- [backend/tests/unit/test_deck_service.py](../../../backend/tests/unit/test_deck_service.py)
- [frontend/src/pages/__tests__/DecksPage.test.tsx](../../../frontend/src/pages/__tests__/DecksPage.test.tsx)
- [frontend/src/components/__tests__/DeckSelector.test.tsx](../../../frontend/src/components/__tests__/DeckSelector.test.tsx)
- [frontend/src/components/__tests__/DeckSummary.test.tsx](../../../frontend/src/components/__tests__/DeckSummary.test.tsx)
- [frontend/src/__tests__/DecksContext.test.tsx](../../../frontend/src/__tests__/DecksContext.test.tsx)

---

**注意**: すべてのファイルパスはプロジェクトルートからの相対パスで記載しています。

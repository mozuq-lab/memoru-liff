# Requirements Document

## Introduction

カテゴリ（デッキ）管理機能を実装し、カードをデッキ単位でグループ化することで、整理・復習を効率化する。現在、cards テーブルには `deck_id` フィールドが存在するが未使用であり、デッキの CRUD 操作やデッキ単位のフィルタリング・復習機能は未実装である。本機能により、ユーザーは学習対象をカテゴリ別に管理し、特定のデッキに絞った復習セッションを開始できるようになる。

### 現状分析
- **バックエンド**: `Card` モデルに `deck_id: Optional[str]` が定義済み。`list_cards` は `deck_id` による `FilterExpression` フィルタリングに対応済み。`create_card` / `update_card` も `deck_id` パラメータを受け付ける。ただし、decks テーブルや Deck 関連の API エンドポイントは存在しない。
- **フロントエンド**: `Card` 型に `deck_id?: string | null` が定義済み。`CreateCardRequest` に `deck_id?: string` が存在。Deck 関連の UI コンポーネント、Context、サービスは未実装。
- **ナビゲーション**: Home (`/`), 作成 (`/generate`), カード (`/cards`), 設定 (`/settings`) の 4 項目。復習 (`/review`) とカード詳細 (`/cards/:id`) のルートも存在。

## Requirements

### Requirement 1: デッキ CRUD（バックエンド）
**Objective:** As a ユーザー, I want デッキを作成・閲覧・更新・削除できる, so that カードを目的別にグループ化して管理できる

#### Acceptance Criteria
1. When ユーザーが `POST /decks` にデッキ名（必須）・説明（任意）・カラー（任意）を送信した場合, the システム shall デッキを DynamoDB に保存し、生成された `deck_id` を含むデッキ情報を返却する
2. When ユーザーが `GET /decks` を呼び出した場合, the システム shall 当該ユーザーの全デッキ一覧を、各デッキに属するカード数・due カード数と共に返却する
3. When ユーザーが `PUT /decks/{deckId}` でデッキ名・説明・カラーを送信した場合, the システム shall 対象デッキの情報を更新し、更新後のデッキ情報を返却する
4. When ユーザーが `DELETE /decks/{deckId}` を呼び出した場合, the システム shall 対象デッキを削除し、そのデッキに属していた全カードの `deck_id` を `null` に更新する（カード自体は削除しない）
5. When 存在しない `deckId` に対して更新・削除が要求された場合, the システム shall 404 Not Found エラーを返却する
6. The デッキ名 shall 1 文字以上 100 文字以下のバリデーションを適用する
7. The デッキ数 shall 1 ユーザーあたり最大 50 個の制限を設ける
8. When デッキ名が空文字または 100 文字超の場合, the システム shall 400 Bad Request エラーを返却する

### Requirement 2: デッキデータモデル（バックエンド）
**Objective:** As a 開発者, I want デッキのデータモデルと DynamoDB テーブルを定義する, so that デッキ情報を永続化・クエリできる

#### Acceptance Criteria
1. The decks テーブル shall `user_id`（パーティションキー）と `deck_id`（ソートキー）で構成される
2. The Deck モデル shall `deck_id`, `user_id`, `name`, `description`（任意）, `color`（任意）, `created_at`, `updated_at` フィールドを持つ
3. The `deck_id` shall UUID v4 で自動生成される
4. The SAM テンプレート（`template.yaml`）に decks テーブルの CloudFormation 定義 shall 追加される
5. The ローカル開発用の `docker-compose.yaml` に decks テーブルの作成コマンド shall 追加される
6. The Deck Pydantic モデル shall `backend/src/models/deck.py` に定義される

### Requirement 3: カードとデッキの紐付け（バックエンド）
**Objective:** As a ユーザー, I want カードをデッキに割り当て・移動できる, so that 既存カードの分類を後から変更できる

#### Acceptance Criteria
1. When カード作成時（`POST /cards`）に `deck_id` が指定された場合, the システム shall カードを指定デッキに紐付けて保存する（既存実装を活用）
2. When カード更新時（`PUT /cards/{cardId}`）に `deck_id` が指定された場合, the システム shall カードのデッキ割り当てを変更する（既存実装を活用）
3. When `GET /cards?deck_id=xxx` でデッキ ID が指定された場合, the システム shall 当該デッキに属するカードのみを返却する（既存実装を活用）
4. When `GET /cards/due` に `deck_id` クエリパラメータが指定された場合, the システム shall 当該デッキの due カードのみを返却する
5. When デッキが削除された場合, the システム shall 当該デッキに属する全カードの `deck_id` を `null` に更新する

### Requirement 4: デッキ管理 UI（フロントエンド）
**Objective:** As a ユーザー, I want デッキを画面上で作成・編集・削除できる, so that 直感的にカードを分類管理できる

#### Acceptance Criteria
1. When ユーザーがデッキ一覧画面にアクセスした場合, the システム shall 全デッキをカード数・due カード数と共にリスト表示する
2. When ユーザーがデッキ作成ボタンを押した場合, the システム shall デッキ名・説明・カラーを入力できるフォームを表示する
3. When ユーザーがデッキをタップした場合, the システム shall 当該デッキに属するカード一覧画面に遷移する
4. When ユーザーがデッキの編集ボタンを押した場合, the システム shall デッキ名・説明・カラーを変更できるフォームを表示する
5. When ユーザーがデッキの削除ボタンを押した場合, the システム shall 確認ダイアログを表示し、確定後にデッキを削除する
6. The デッキ一覧画面 shall 「未分類」セクションを表示し、`deck_id` が `null` のカード数を表示する
7. The デッキ一覧画面 shall `/decks` ルートでアクセス可能とする
8. The フッターナビゲーション shall デッキ一覧へのリンクを含む（「デッキ」タブを追加）

### Requirement 5: カード作成・編集時のデッキ選択（フロントエンド）
**Objective:** As a ユーザー, I want カード作成・編集時にデッキを選択できる, so that カードを適切なカテゴリに分類できる

#### Acceptance Criteria
1. When カード作成フォーム（GeneratePage でのAI生成カード保存、または手動作成）を表示した場合, the システム shall デッキ選択ドロップダウンを表示する
2. When カード詳細画面の編集モードでデッキを変更した場合, the システム shall `PUT /cards/{cardId}` で `deck_id` を更新する
3. The デッキ選択ドロップダウン shall API から取得したデッキ一覧を表示し、「未分類」オプションを含む
4. When デッキが未選択の場合, the システム shall カードを `deck_id: null`（未分類）として保存する

### Requirement 6: デッキ単位の復習セッション（フロントエンド）
**Objective:** As a ユーザー, I want 特定のデッキの due カードだけを復習できる, so that 特定の学習トピックに集中して復習できる

#### Acceptance Criteria
1. When ユーザーがデッキ一覧画面でデッキの「復習する」ボタンを押した場合, the システム shall 当該デッキの due カードのみで復習セッションを開始する
2. When デッキ指定の復習セッションを開始する場合, the システム shall `GET /cards/due?deck_id=xxx` から due カードを取得する
3. When 指定デッキに due カードがない場合, the システム shall 「このデッキに復習対象のカードはありません」というメッセージを表示する
4. The 復習画面（ReviewPage） shall `deck_id` クエリパラメータに対応し、デッキ指定の復習セッションをサポートする

### Requirement 7: ホーム画面のデッキ概要表示（フロントエンド）
**Objective:** As a ユーザー, I want ホーム画面でデッキごとの復習状況を一目で把握できる, so that 効率的に学習計画を立てられる

#### Acceptance Criteria
1. When ユーザーがホーム画面にアクセスした場合, the システム shall デッキ一覧を due カード数と共にサマリー表示する
2. When ホーム画面でデッキをタップした場合, the システム shall 当該デッキのカード一覧画面に遷移する
3. The ホーム画面 shall 最大 5 件のデッキをサマリー表示し、それ以上の場合は「すべて表示」リンクでデッキ一覧画面に遷移する
4. When デッキが 0 件の場合, the システム shall 「デッキを作成して学習を整理しましょう」という案内メッセージを表示する

### Requirement 8: デッキ状態管理（フロントエンド）
**Objective:** As a 開発者, I want デッキの状態を React Context で管理する, so that 複数の画面間でデッキデータを共有・同期できる

#### Acceptance Criteria
1. The `DecksContext` shall デッキ一覧の取得・追加・更新・削除を管理する
2. The `DecksProvider` shall `CardsProvider` と同階層で `App.tsx` に配置される
3. The API 通信サービス（`api.ts`）に `decksApi` オブジェクト shall 追加される（`getDecks`, `createDeck`, `updateDeck`, `deleteDeck`）
4. The Deck 型定義 shall `frontend/src/types/deck.ts` に定義され、`types/index.ts` から re-export される
5. When デッキの作成・更新・削除が完了した場合, the コンテキスト shall 自動的にデッキ一覧を再取得する

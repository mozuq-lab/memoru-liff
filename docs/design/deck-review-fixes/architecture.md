# deck-review-fixes アーキテクチャ設計

**作成日**: 2026-03-01
**関連要件定義**: [requirements.md](../../spec/deck-review-fixes/requirements.md)
**ヒアリング記録**: [design-interview.md](design-interview.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実な設計
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測による設計
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測による設計

---

## システム概要 🔵

**信頼性**: 🔵 *要件定義書・レビュー文書より*

本設計は `feature/deck-management-spec` ブランチの PR #1 に対するコードレビュー指摘 14 件（C-1 修正済み、H-1〜H-4、M-1〜M-5、L-1〜L-4）の修正アーキテクチャを定義する。既存の Memoru LIFF アプリケーション（サーバーレス構成: Lambda + API Gateway + DynamoDB、React + TypeScript フロントエンド）上での修正であり、新規コンポーネントの追加は最小限に留める。

## 修正対象アーキテクチャ概観 🔵

**信頼性**: 🔵 *既存設計文書・レビュー文書より*

```
修正レイヤー概要:

┌─────────────────────────────────────────────────────────┐
│ フロントエンド (React + TypeScript)                       │
│                                                          │
│  [H-1] CardsPage deck_id フィルタ対応                     │
│  [H-2] UpdateCardRequest 型 + CardDetailPage null送信     │
│  [M-2] App.tsx Provider ネスト順序修正                     │
│  [M-4] DeckFormModal 差分送信                             │
│  [L-1] DeckSelector/DeckSummary unassigned 削除           │
│  [L-3] JSDoc コメントスタイル統一                          │
│  [L-4] CardDetailPage デッキ変更後 fetchDecks             │
│                                                          │
├─────────────────────────────────────────────────────────┤
│ バックエンド (Python 3.12 + Lambda)                       │
│                                                          │
│  [H-2] card_service.py deck_id null→REMOVE                │
│  [H-3] handler.py DeckLimitExceededError → HTTP 409       │
│  [H-4] deck_service.py ConditionExpression アトミック検証  │
│  [M-1] review_service.py total_due_count 正確化           │
│  [M-3] deck_service.py description/color null→REMOVE      │
│  [M-5] deck_service.py TODO コメント追加                   │
│  [L-2] handler.py ドメイン別ルーター分割                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## アーキテクチャ変更方針

### 1. handler.py ルーター分割（REQ-401 / L-2） 🔵

**信頼性**: 🔵 *レビュー L-2・ヒアリング回答（ルーター分割方式）より*

**現状**: `backend/src/api/handler.py` が約 1024 行・25 関数を含む単一ファイル

**方針**: handler.py をルーターとして維持し、ドメインハンドラを個別ファイルに分割する

**分割後ディレクトリ構造**:
```
backend/src/api/
├── handler.py              # ルーター（APIGatewayHttpResolver + include_router）
├── handlers/
│   ├── __init__.py
│   ├── user_handler.py     # /users/* エンドポイント（4ルート）
│   ├── cards_handler.py    # /cards/* エンドポイント（5ルート）
│   ├── decks_handler.py    # /decks/* エンドポイント（4ルート）
│   ├── review_handler.py   # /reviews/* + /cards/due エンドポイント（3ルート）
│   └── ai_handler.py       # /cards/generate エンドポイント（1ルート）
└── shared.py               # 共通関数（get_user_id_from_context, _map_ai_error_to_http）
```

**実装詳細**:

```python
# handler.py（ルーター）
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from api.handlers.user_handler import router as user_router
from api.handlers.cards_handler import router as cards_router
from api.handlers.decks_handler import router as decks_router
from api.handlers.review_handler import router as review_router
from api.handlers.ai_handler import router as ai_router

app = APIGatewayHttpResolver()
app.include_router(user_router)
app.include_router(cards_router)
app.include_router(decks_router)
app.include_router(review_router)
app.include_router(ai_router)
```

```python
# handlers/decks_handler.py（例）
from aws_lambda_powertools.event_handler.api_gateway import Router
router = Router()

@router.post("/decks")
def create_deck_handler():
    ...
```

**制約事項**:
- サービスのインスタンス化は各ハンドラファイル内で行う（Lambda のコールドスタート最適化）
- `get_user_id_from_context()` 等の共通関数は `shared.py` に切り出す
- Lambda エントリポイント（`lambda_handler`）は `handler.py` に残す

---

### 2. DynamoDB REMOVE パターン（REQ-002, REQ-103〜106 / H-2, M-3） 🔵

**信頼性**: 🔵 *レビュー H-2・M-3・要件定義書より*

**現状の問題**:
- `card_service.py`: `if deck_id is not None:` で null と未送信を区別できない
- `deck_service.py`: `if description is not None:` / `if color is not None:` で同様の問題

**方針**: Sentinel 値パターンを使用して null（明示的クリア）と未送信（変更なし）を区別

**バックエンド修正**:

```python
# 共通 Sentinel 値定義（models/ または services/ の共通モジュール）
_UNSET = object()  # 未送信を表す sentinel

# card_service.py update_card
def update_card(self, user_id, card_id, ..., deck_id=_UNSET):
    if deck_id is None:
        # 明示的 null → REMOVE
        remove_parts.append("deck_id")
        card.deck_id = None
    elif deck_id is not _UNSET:
        # 新しい値 → SET
        update_parts.append("deck_id = :deck_id")
        expression_values[":deck_id"] = deck_id
        card.deck_id = deck_id
    # deck_id is _UNSET → 変更なし

# deck_service.py update_deck（description, color も同様）
def update_deck(self, user_id, deck_id, name=_UNSET, description=_UNSET, color=_UNSET):
    if description is None:
        remove_parts.append("description")
    elif description is not _UNSET:
        update_parts.append("description = :description")
        ...
```

**DynamoDB UpdateExpression の構築**:
```python
# SET 部分と REMOVE 部分を組み合わせ
expression = ""
if update_parts:
    expression += "SET " + ", ".join(update_parts)
if remove_parts:
    expression += " REMOVE " + ", ".join(remove_parts)
```

**フロントエンド修正**:
```typescript
// types/card.ts - null 許容に変更
export interface UpdateCardRequest {
  front?: string;
  back?: string;
  deck_id?: string | null;  // H-2: null 明示を許容
  tags?: string[];
  interval?: number;
}
```

---

### 3. デッキ数制限のアトミック検証（REQ-004 / H-4） 🔵

**信頼性**: 🔵 *追加レビュー H-4・ヒアリング回答（Query+Condition 方式）より*

**現状の問題**: `create_deck` が非アトミックなチェック（Query → PutItem が別操作でレースコンディション発生可能）

**方針**: Query(Select=COUNT) + PutItem with ConditionExpression

**実装詳細**:

```python
def create_deck(self, user_id, name, description=None, color=None):
    # Step 1: 現在のデッキ数を取得（デッキ作成前の楽観的チェック）
    current_count = self._get_deck_count(user_id)
    if current_count >= self.MAX_DECKS_PER_USER:
        raise DeckLimitExceededError(...)

    # Step 2: PutItem with ConditionExpression
    deck = Deck(user_id=user_id, name=name, ...)
    try:
        self.table.put_item(
            Item=deck.to_dynamodb_item(),
            ConditionExpression="attribute_not_exists(user_id) AND attribute_not_exists(deck_id)"
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise DeckLimitExceededError(...)
        raise

    # Step 3: 作成直後にカウント検証（レース検出）
    post_count = self._get_deck_count(user_id)
    if post_count > self.MAX_DECKS_PER_USER:
        # レースで超過 → ロールバック
        self.table.delete_item(
            Key={"user_id": user_id, "deck_id": deck.deck_id}
        )
        raise DeckLimitExceededError(...)

    return deck
```

**補足**: DynamoDB は単一テーブル内でのアイテム数制限を ConditionExpression で直接表現できないため、`attribute_not_exists` で重複防止 + 作成後カウント検証のパターンを採用する。完全なアトミック性はトランザクションでも実現困難なため、レース窓を最小化する実装とする。

---

### 4. HTTP ステータスコード修正（REQ-003 / H-3） 🔵

**信頼性**: 🔵 *追加レビュー H-3 より*

**現状**: `DeckLimitExceededError` → HTTP 400 Bad Request
**修正**: `DeckLimitExceededError` → HTTP 409 Conflict

```python
# handler.py（または handlers/decks_handler.py）
except DeckLimitExceededError:
    return Response(
        status_code=409,  # 400 → 409 に修正
        content_type=content_types.APPLICATION_JSON,
        body=json.dumps({"error": "Deck limit exceeded. Maximum 50 decks per user."}),
    )
```

---

### 5. total_due_count 修正（REQ-005 / M-1） 🔵

**信頼性**: 🔵 *レビュー M-1・既存バグ修正7408e48より*

**現状**: `total_due_count` が `limit` パラメータで切り詰められた件数を返す
**修正**: limit 適用前の件数を `total_due_count` として返す

```python
# review_service.py get_due_cards
def get_due_cards(self, user_id, limit=20, deck_id=None):
    # 全復習対象カードを取得（deck_id フィルタ適用）
    all_due_cards = self._query_due_cards(user_id, deck_id)
    total_due_count = len(all_due_cards)  # limit 前の総数

    # limit 適用
    due_cards = all_due_cards[:limit]

    return due_cards, total_due_count
```

**注**: このバグは直近コミット 7408e48 で一部修正済みの可能性があるため、実装時に最新状態を確認する。

---

### 6. CardsPage deck_id フィルタ（REQ-001, REQ-101, REQ-102 / H-1） 🔵

**信頼性**: 🔵 *レビュー H-1・要件 4.3 より*

**修正対象**:
- `CardsContext.tsx`: `fetchCards(deckId?)` / `fetchDueCards(deckId?)` にパラメータ追加
- `CardsPage.tsx`: URL から `deck_id` クエリパラメータを読み取り、フィルタに使用

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

---

### 7. Provider ネスト順序修正（REQ-201 / M-2） 🟡

**信頼性**: 🟡 *レビュー M-2・research.md から妥当な推測*

**現状**: `CardsProvider > DecksProvider`
**修正**: `AuthProvider > CardsProvider > DecksProvider`（設計文書準拠）

```tsx
// App.tsx
<AuthProvider>
  <CardsProvider>
    <DecksProvider>
      <Layout>...</Layout>
    </DecksProvider>
  </CardsProvider>
</AuthProvider>
```

**注**: CardsProvider が DecksProvider より外側にあるのは、DecksProvider が CardsContext を参照しない設計に基づく。将来的に DecksProvider が card_count 取得のため CardsContext を参照する場合は順序変更が必要。

---

### 8. DeckFormModal 差分送信（REQ-202 / M-4） 🔵

**信頼性**: 🔵 *レビュー M-4 より*

**修正**: edit モードで変更されたフィールドのみを API に送信

```typescript
// DeckFormModal.tsx（edit モード）
const handleSubmit = () => {
  const payload: Partial<UpdateDeckRequest> = {};
  if (name !== initialValues.name) payload.name = name;
  if (description !== initialValues.description) {
    payload.description = description || null;  // 空文字 → null（クリア）
  }
  if (color !== initialValues.color) {
    payload.color = color || null;  // 選択解除 → null（クリア）
  }
  updateDeck(deckId, payload);
};
```

---

### 9. CardDetailPage デッキ変更後のコンテキスト更新（REQ-203 / L-4） 🔵

**信頼性**: 🔵 *レビュー L-4 より*

**修正**: デッキ変更保存後に `DecksContext.fetchDecks()` を呼び出す

```typescript
// CardDetailPage.tsx
const { fetchDecks } = useDecksContext();

const handleSave = async () => {
  await updateCard(cardId, { deck_id: selectedDeckId });
  fetchDecks();  // デッキの card_count / due_count を更新
};
```

---

### 10. コードクリーンアップ（REQ-402, REQ-403, REQ-404 / L-1, L-3, M-5） 🔵

**信頼性**: 🔵 *レビュー L-1, L-3, M-5・ヒアリング回答より*

- **L-1**: `DeckSelector.tsx` / `DeckSummary.tsx` から `d.deck_id !== 'unassigned'` フィルタを削除
- **L-3**: デッキ関連コンポーネントに JSDoc コメントスタイルを統一
- **M-5**: `get_deck_card_counts` / `get_deck_due_counts` に TODO コメント追加

```python
# deck_service.py
def get_deck_card_counts(self, user_id):
    # TODO: パフォーマンス改善 - 全カードスキャンを GSI カウントまたは
    # DynamoDB Streams + カウンターテーブルに置き換える（MVP後対応）
    ...
```

---

## ディレクトリ構造（変更後） 🔵

**信頼性**: 🔵 *既存プロジェクト構造・ヒアリング回答より*

```
backend/src/api/
├── handler.py                  # [L-2] ルーターのみに縮小
├── shared.py                   # [L-2] 新規: 共通関数
└── handlers/                   # [L-2] 新規: ドメインハンドラ
    ├── __init__.py
    ├── user_handler.py
    ├── cards_handler.py
    ├── decks_handler.py        # [H-3] HTTP 409 修正
    ├── review_handler.py
    └── ai_handler.py

backend/src/services/
├── card_service.py             # [H-2] deck_id null→REMOVE
├── deck_service.py             # [H-4] ConditionExpression, [M-3] REMOVE, [M-5] TODO
├── review_service.py           # [M-1] total_due_count 修正
└── ...

frontend/src/
├── App.tsx                     # [M-2] Provider 順序修正
├── types/
│   └── card.ts                 # [H-2] deck_id?: string | null
├── contexts/
│   └── CardsContext.tsx         # [H-1] fetchCards(deckId?) 対応
├── pages/
│   ├── CardsPage.tsx            # [H-1] deck_id クエリパラメータ対応
│   └── CardDetailPage.tsx       # [H-2] null 送信, [L-4] fetchDecks
├── components/
│   ├── DeckFormModal.tsx        # [M-4] 差分送信
│   ├── DeckSelector.tsx         # [L-1] unassigned 削除, [L-3] JSDoc
│   └── DeckSummary.tsx          # [L-1] unassigned 削除, [L-3] JSDoc
└── ...
```

---

## 非機能要件の実現方法

### パフォーマンス 🟡

**信頼性**: 🟡 *NFR-001, NFR-002 から妥当な推測*

- **NFR-001（レスポンスタイム）**: deck_id フィルタは既存の DynamoDB FilterExpression を使用するため、スキャン範囲は変わらない（user_id パーティションキーでクエリ済み）
- **NFR-002（コールドスタート）**: handler.py 分割は Python の import 時間に軽微な影響。Lambda Powertools の Router はレイジーロードのため影響は最小限
- **M-5（全カードスキャン）**: MVP 段階ではリスク許容。カード最大 2000 枚、DynamoDB の ProjectionExpression 使用で読み取り容量単位を最小化

### セキュリティ 🔵

**信頼性**: 🔵 *NFR-101・既存セキュリティ設計より*

- **NFR-101**: ConditionExpression で使用する Query は `user_id = :user_id` 条件付き。他ユーザーのデッキ数を参照しない
- **JWT 認証**: 全エンドポイントで `get_user_id_from_context()` を使用する既存パターンを維持
- **deck_id フィルタ**: バックエンド側で `user_id` と `deck_id` を組み合わせた Query/FilterExpression で他ユーザーのデータにアクセス不可

### ユーザビリティ 🟡

**信頼性**: 🟡 *NFR-201 から妥当な推測*

- **戻るナビゲーション**: deck_id 付きカード一覧から全カード一覧への Link を提供
- **デッキ名表示**: deck_id 指定時にページヘッダーにデッキ名を表示（REQ-101）

---

## 技術的制約

### DynamoDB 制約 🔵

**信頼性**: 🔵 *既存 DynamoDB 設計・AWS ドキュメントより*

- DynamoDB の ConditionExpression はアイテム単位の条件評価のみ。テーブル全体のカウントに基づく条件は直接記述不可
- UpdateExpression で SET と REMOVE を組み合わせる場合、`SET ... REMOVE ...` の形式で記述
- `attribute_not_exists` は新規アイテム作成時の重複防止に使用可能

### Lambda Powertools Router 制約 🔵

**信頼性**: 🔵 *Lambda Powertools ドキュメント・既存実装より*

- `APIGatewayHttpResolver.include_router()` で Router インスタンスを登録
- Router 内のハンドラは `app.current_event` にアクセス可能（Powertools が自動注入）
- サービスインスタンスは各ハンドラファイル内でモジュールレベル変数として初期化

### フロントエンド互換性制約 🔵

**信頼性**: 🔵 *既存フロントエンド設計・LIFF SDK 制約より*

- LIFF SDK の `useSearchParams` は React Router v6 互換
- Context の fetchCards/fetchDueCards に deck_id パラメータを追加する際、既存の呼び出し箇所は引数なし（undefined）で従来動作を維持

---

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **設計ヒアリング記録**: [design-interview.md](design-interview.md)
- **要件定義**: [requirements.md](../../spec/deck-review-fixes/requirements.md)
- **ユーザストーリー**: [user-stories.md](../../spec/deck-review-fixes/user-stories.md)
- **受け入れ基準**: [acceptance-criteria.md](../../spec/deck-review-fixes/acceptance-criteria.md)
- **既存アーキテクチャ**: [architecture.md（memoru-liff）](../memoru-liff/architecture.md)
- **レビュー文書**: [review-deck-management-spec.md](../../review-deck-management-spec.md)

## 信頼性レベルサマリー

- 🔵 青信号: 18件 (90%)
- 🟡 黄信号: 2件 (10%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質

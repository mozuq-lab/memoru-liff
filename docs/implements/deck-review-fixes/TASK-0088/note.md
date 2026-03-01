# TASK-0088: total_due_count 修正 - 開発ノート

## 1. 技術スタック

### 使用技術・フレームワーク
- **バックエンド**: Python 3.12, AWS Lambda, AWS SAM
- **フレームワーク**: Lambda Powertools (Logger, Tracer)
- **データベース**: DynamoDB
- **API**: APIGatewayHttpResolver (Lambda Powertools)
- **テストフレームワーク**: pytest

### アーキテクチャパターン
- **サービス層パターン**: `ReviewService` がビジネスロジックを管理
- **ハンドラ層パターン**: `review_handler.py` が HTTP リクエスト処理
- **モデル層パターン**: Pydantic モデルで型安全性を確保

参照元:
- `backend/src/services/review_service.py`
- `backend/src/api/handlers/review_handler.py`
- `backend/src/models/review.py`

---

## 2. 開発ルール

### プロジェクト開発ワークフロー
1. **Tsumiki ワークフロー使用**: Kairo ワークフロー に従い TDD で実装
2. **TDD 流程**:
   - `/tsumiki:tdd-red`: テスト実装（失敗）
   - `/tsumiki:tdd-green`: 最小実装
   - `/tsumiki:tdd-refactor`: リファクタリング
3. **タスク管理**:
   - タスクファイル (`docs/tasks/deck-review-fixes/TASK-0088.md`) の完了条件を `[x]` に更新
   - 概要ファイル (`docs/tasks/deck-review-fixes/overview.md`) の状態を更新
4. **コミットルール**:
   - タスクごとにコミット（複数タスク併合しない）
   - コミットメッセージ形式: `TASK-0088: タスク名\n\n- 実装内容\n\nCo-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>`

### Python コーディング規約
- Type hints 必須（`Optional[str]`, `List[...]` 等）
- docstring は Google スタイル（引数説明、戻り値、例外）
- ログレベル: `logger.info()` / `logger.error()` 使い分け
- DynamoDB 操作は `boto3` ラッパーで実装

### テストルール
- **ユニットテスト**: `backend/tests/unit/test_review_service.py`
- **モック**: `moto` + `pytest-mock` で DynamoDB / Cognito をモック
- **テストケース**: arrange-act-assert パターン
- **テストカバレッジ**: 80% 以上を目標

参照元:
- `CLAUDE.md` - 開発ワークフロー、コミットルール
- `docs/spec/deck-review-fixes/requirements.md` - REQ-005

---

## 3. 関連実装

### get_due_cards メソッドの現状

**ファイル**: `backend/src/services/review_service.py` (行 377-446)

**現在の問題**:
```python
def get_due_cards(
    self,
    user_id: str,
    limit: int = 20,
    include_future: bool = False,
    deck_id: Optional[str] = None,
) -> DueCardsResponse:
    # ...
    due_cards = self.card_service.get_due_cards(...)

    # deck_id フィルタ後に limit を適用
    if deck_id is not None:
        due_cards = [c for c in due_cards if c.deck_id == deck_id]

    # ...
    if deck_id is not None:
        total_due_count = len(due_card_infos)  # ❌ limit 後の件数（バグ）
    else:
        total_due_count = self.card_service.get_due_card_count(...)
```

**期待動作**:
- `total_due_count` は `limit` 適用前の全復習対象カード数を返す
- deck_id フィルタ適用後でも、limit 前のカウント

### 修正パターン

参考になる類似実装:
- `CardService.get_due_cards()` (行 ~300) - due_cards 取得ロジック
- `DeckService._get_deck_count()` - カウント専用メソッド

### DynamoDB 操作パターン

**Query + FilterExpression**:
```python
response = self.cards_table.query(
    KeyConditionExpression=Key("user_id").eq(user_id),
    FilterExpression=Attr("deck_id").eq(deck_id),  # Optional filter
    Limit=limit,
)
```

参照元:
- `backend/src/services/review_service.py` - `_get_next_due_date()` メソッド

---

## 4. 設計文書

### 要件定義

**REQ-005** (🔵 青信号):
> `GET /cards/due?deck_id=xxx` の `total_due_count` は、`limit` パラメータに影響されず、指定デッキの復習対象カード総数を正確に返さなければならない

**テスト条件**:
- 20件の復習対象カード、limit=10 → `total_due_count=20`, `due_cards=10件`
- deck_id フィルタ付きで正確な件数を返すこと

参照元: `docs/spec/deck-review-fixes/requirements.md`

### アーキテクチャ設計

**修正箇所** (セクション5):
```
修正レイヤー:
├── backend/src/services/review_service.py
│   └── [M-1] total_due_count 修正: limit 前の総数を返す
└── backend/src/api/handlers/review_handler.py
    └── [M-1] レスポンスに total_due_count を含める
```

**実装詳細** (architecture.md セクション5より):
```python
def get_due_cards(self, user_id, limit=20, deck_id=None):
    # 全復習対象カードを取得（deck_id フィルタ適用）
    all_due_cards = self._query_due_cards(user_id, deck_id)
    total_due_count = len(all_due_cards)  # limit 前の総数

    # limit 適用
    due_cards = all_due_cards[:limit]

    return due_cards, total_due_count
```

**パフォーマンス**:
- NFR-001: レスポンスタイムは deck_id フィルタなしの場合と同等
- 全カードスキャン後 deck_id フィルタ（FilterExpression 相当）

**セキュリティ**:
- deck_id フィルタは user_id 単位で適用（他ユーザーデータアクセス不可）

参照元:
- `docs/design/deck-review-fixes/architecture.md` (セクション5)

### データモデル

**DueCardsResponse** (models/review.py):
```python
class DueCardsResponse(BaseModel):
    due_cards: List[DueCardInfo]
    total_due_count: int          # ← 修正対象フィールド
    next_due_date: Optional[str] = None
```

参照元: `backend/src/models/review.py` (行 79-84)

### API エンドポイント

**GET /cards/due** (review_handler.py):
```python
@router.get("/cards/due")
def get_due_cards():
    params = router.current_event.query_string_parameters or {}
    limit = min(int(params.get("limit", 20)), 100)
    deck_id = params.get("deck_id")

    response = review_service.get_due_cards(
        user_id=user_id,
        limit=limit,
        deck_id=deck_id,
    )
    return response.model_dump(mode="json")
```

パラメータ:
- `limit` (int, default=20): 返却カード数の上限
- `deck_id` (str, optional): デッキ ID フィルタ
- `include_future` (bool, default=false): 未来のカードを含める

参照元: `backend/src/api/handlers/review_handler.py` (行 27-49)

---

## 5. 注意事項

### 技術的制約

**DynamoDB クエリ順序**:
- `get_due_cards()` は `card_service.get_due_cards()` で due カード一覧を取得
- 返却カードは `limit` 個に制限
- その後、クライアント側で `deck_id` フィルタを適用
- ⚠️ `limit` はフィルタ前に適用されるため、デッキフィルタ後のカード数が limit より少ない可能性

**修正時の注意**:
1. `all_due_cards` でフィルタなしの全カードを先に取得
2. `total_due_count = len(all_due_cards)` で総数をカウント
3. その後 `all_due_cards[:limit]` で制限

### テストケース設計

**正常系**:
- 全カード (deck_id なし): limit=10, 全20件 → total_due_count=20, due_cards=10
- デッキフィルタ: limit=10, デッキA内5件 → total_due_count=5, due_cards=5
- デッキフィルタ + limit超過: limit=10, デッキB内15件 → total_due_count=15, due_cards=10

**境界値**:
- limit=0: due_cards=[], total_due_count=全数
- deck_id=存在しないID: total_due_count=0, due_cards=[]
- deck_id=null: 全カード（従来動作）

**参考**: 既存テスト `backend/tests/unit/test_review_service.py`

### セキュリティ考慮

- ✅ JWT 認証: `get_user_id_from_context()` で user_id 検証
- ✅ deck_id フィルタ: Query で user_id = :user_id 条件付き
- ⚠️ 他ユーザーのデッキ ID を指定された場合: FilterExpression で自動除外

### パフォーマンス考慮

- **スキャン範囲**: user_id で Query (スキャンなし)
- **FilterExpression**: deck_id はアプリケーション層で処理（費用最小化）
- **全カードスキャン**: MVP 段階ではリスク許容（最大2000件）
- 将来改善: GSI カウント または DynamoDB Streams + カウンターテーブル

参照元: `docs/design/deck-review-fixes/architecture.md` (セクション5・パフォーマンス)

---

## 6. 開発コマンド

```bash
# テスト実行
cd backend && make test

# 特定テスト実行
cd backend && pytest tests/unit/test_review_service.py::TestGetDueCards -v

# ローカルAPI起動
cd backend && make local-api

# ローカル全サービス起動
cd backend && make local-all
```

---

## 7. ファイル一覧

### 修正対象ファイル
- `backend/src/services/review_service.py` - `get_due_cards()` メソッド修正
- `backend/src/api/handlers/review_handler.py` - レスポンス構造確認
- `backend/tests/unit/test_review_service.py` - テストケース追加

### 参照ファイル
- `backend/src/models/review.py` - `DueCardsResponse` モデル
- `backend/src/services/card_service.py` - `get_due_cards()` 実装参考
- `docs/tasks/deck-review-fixes/TASK-0088.md` - タスク定義
- `docs/tasks/deck-review-fixes/overview.md` - フェーズ状態管理

---

**作成日**: 2026-03-01
**タスク**: TASK-0088: total_due_count 修正
**フェーズ**: Phase 2 - バックエンド Medium/Low + フロントエンド High
**状態**: 開発準備完了

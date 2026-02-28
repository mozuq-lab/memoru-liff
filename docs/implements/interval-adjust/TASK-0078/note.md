# TASK-0078 開発コンテキストノート

**タスク**: バックエンド interval更新サポート
**要件名**: interval-adjust
**作成日**: 2026-02-28

---

## 1. 技術スタック

### 使用技術・フレームワーク
- **Python 3.12** - ランタイム
- **Pydantic v2** - リクエスト/レスポンスのバリデーション・シリアライゼーション
- **AWS Lambda Powertools** - ロガー、トレーサー、APIGatewayHttpResolver
- **boto3** - DynamoDB操作（Table resource API + 低レベル client API）
- **moto** - テスト用 AWS モック
- **pytest** - テストフレームワーク

### アーキテクチャパターン
- **レイヤードアーキテクチャ**: handler → service → DynamoDB
- **Pydantic モデル**: リクエスト/レスポンスのバリデーション
- **ドメインモデル**: `Card` クラスが DynamoDB シリアライズ/デシリアライズを担当

### 参照元
- `CLAUDE.md`
- `docs/design/interval-adjust/architecture.md`

---

## 2. 開発ルール

### コーディング規約
- コミットメッセージ形式: `TASK-XXXX: タスク名` + 箇条書き + Co-Authored-By
- タスクごとにコミット（複数タスクをまとめない）
- テストカバレッジ 80% 以上を目標

### テスト要件
- TDD で開発（Red → Green → Refactor）
- moto + pytest でユニットテスト
- DynamoDB テストでは `mock_aws` デコレータを使用
- `transact_write_items` は moto にバグがあるためカスタムモックを使用

### 型チェック
- Pydantic v2 の `Field` で `ge`, `le`, `min_length`, `max_length` を使用
- `Optional` フィールドはデフォルト `None`

### 参照元
- `CLAUDE.md`

---

## 3. 関連実装

### 3.1 UpdateCardRequest（変更対象）

**ファイル**: `backend/src/models/card.py`

現在のモデル:
```python
class UpdateCardRequest(BaseModel):
    front: Optional[str] = Field(None, min_length=1, max_length=1000)
    back: Optional[str] = Field(None, min_length=1, max_length=2000)
    deck_id: Optional[str] = None
    tags: Optional[List[str]] = None
```

追加するフィールド:
```python
interval: Optional[int] = Field(None, ge=1, le=365)
```

### 3.2 CardService.update_card（変更対象）

**ファイル**: `backend/src/services/card_service.py`

現在のシグネチャ:
```python
def update_card(self, user_id, card_id, front=None, back=None, deck_id=None, tags=None) -> Card:
```

既存の更新パターン:
- `update_parts` リストに UpdateExpression のパーツを追加
- `expression_values` に値をセット
- `expression_names` に予約語エスケープ（例: `#front`, `#back`）
- 更新がない場合は早期リターン
- `updated_at` は自動付与

注意: `interval` は DynamoDB の予約語なので `#interval` としてエスケープが必要（`update_review_data` メソッドで既に使用されているパターン）

### 3.3 handler.update_card（変更対象）

**ファイル**: `backend/src/api/handler.py`（L521-559）

現在の呼び出し:
```python
card = card_service.update_card(
    user_id=user_id,
    card_id=card_id,
    front=request.front,
    back=request.back,
    deck_id=request.deck_id,
    tags=request.tags,
)
```

### 3.4 update_review_data（参考パターン）

**ファイル**: `backend/src/services/card_service.py`（L505-544）

interval と next_review_at の更新パターンの参考:
```python
UpdateExpression="SET next_review_at = :next_review, #interval = :interval, ..."
ExpressionAttributeNames={"#interval": "interval"},
ExpressionAttributeValues={
    ":next_review": next_review_at.isoformat(),
    ":interval": interval,
    ...
}
```

### 3.5 テストパターン（参考）

**ファイル**: `backend/tests/unit/test_card_service.py`

テスト構造:
- `@mock_aws` + `dynamodb_table` fixture で DynamoDB テーブルを作成
- `card_service` fixture で CardService インスタンスを作成
- テーブル: `memoru-cards-test`, `memoru-users-test`, `memoru-reviews-test`
- `transact_write_items` はカスタムモック（ただし `update_card` では不使用。通常の `update_item` を使用）

### 参照元
- `backend/src/models/card.py`
- `backend/src/services/card_service.py`
- `backend/src/api/handler.py`
- `backend/tests/unit/test_card_service.py`

---

## 4. 設計文書

### データモデル

cards テーブルの関連フィールド:
| フィールド | 型 | 説明 |
|-----------|-----|------|
| `user_id` | String (PK) | 所有ユーザーID |
| `card_id` | String (SK) | カードID (UUID) |
| `interval` | Number | 復習間隔（日数）。デフォルト 0 |
| `next_review_at` | String | 次回復習日時（ISO 8601, UTC）。GSI ソートキー |
| `ease_factor` | String | SM-2 ease factor（**string型**で保存） |
| `repetitions` | Number | 連続正解回数 |
| `updated_at` | String | 更新日時（ISO 8601） |

GSI: `user_id-due-index` (PK: user_id, SK: next_review_at)

### API仕様

`PUT /cards/:card_id` - カード更新
- 既存フィールド: front, back, deck_id, tags
- 追加: interval (Optional[int], 1-365)
- レスポンス: CardResponse（更新後のカードデータ）

### ディレクトリ構造

```
backend/
├── src/
│   ├── api/
│   │   └── handler.py          # API ハンドラ
│   ├── models/
│   │   └── card.py             # Card モデル（UpdateCardRequest 含む）
│   └── services/
│       └── card_service.py     # CardService（update_card 含む）
└── tests/
    └── unit/
        └── test_card_service.py # CardService テスト
```

### 参照元
- `docs/design/interval-adjust/architecture.md`
- `docs/design/interval-adjust/dataflow.md`
- `docs/design/memoru-liff/database-schema.md`
- `docs/design/memoru-liff/api-endpoints.md`

---

## 5. 注意事項

### 技術的制約

1. **DynamoDB の ease_factor は string 型**: `str(ease_factor)` で保存し、`float(item.get("ease_factor", 2.5))` で読み出す。interval 更新時にこの形式を壊さないこと
2. **next_review_at は ISO 8601 形式 (UTC)**: `datetime.now(timezone.utc).isoformat()` で保存。`user_id-due-index` GSI のソートキーとして使用されるため、形式を厳守
3. **`interval` は DynamoDB の予約語**: ExpressionAttributeNames で `#interval` → `interval` のエスケープが必要（`update_review_data` で既に使用されているパターン）
4. **interval と front/back の同時指定可能**: 1つの UpdateExpression でまとめて更新する

### 不変条件（REQ-004, REQ-403）

- interval 更新時に `ease_factor` を変更しない
- interval 更新時に `repetitions` を変更しない
- interval 更新は `review_history` に記録しない（復習操作ではないため）

### テスト上の注意

- `update_card` は通常の `table.update_item()` を使用するため、`transact_write_items` のカスタムモックは不要
- `datetime.now(timezone.utc)` のモックが必要（`next_review_at` の検証のため）

### 参照元
- `docs/tasks/interval-adjust/TASK-0078.md`（注意事項セクション）
- `docs/design/interval-adjust/architecture.md`（技術的制約セクション）
- `docs/spec/interval-adjust/requirements.md`（REQ-004, REQ-403）

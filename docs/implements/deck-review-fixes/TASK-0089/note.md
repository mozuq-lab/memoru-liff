# TASK-0089: deck_service.py description/color REMOVE - 開発ノート

## 技術スタック

- **言語**: Python 3.12
- **フレームワーク**: AWS Lambda Powertools (APIGatewayHttpResolver, Router)
- **DB**: DynamoDB (boto3 resource API)
- **バリデーション**: Pydantic v2
- **テスト**: pytest, moto (DynamoDB mock)

## 開発ルール

- TDD ワークフロー: Red -> Green -> Refactor
- コミットメッセージ: `TASK-XXXX: タスク名`
- テストカバレッジ: 80% 以上

## 関連実装

### 参照実装: card_service.py の Sentinel パターン (TASK-0085)

- `backend/src/services/card_service.py` の `_UNSET = object()` + `update_card(deck_id=_UNSET)`
- `backend/src/api/handlers/cards_handler.py` の `if "deck_id" in body:` パターン
- `deck_id is None` -> REMOVE, `deck_id is not _UNSET` -> SET, `deck_id is _UNSET` -> no change

### 変更対象

- `backend/src/services/deck_service.py` - `update_deck` メソッドに Sentinel パターン適用
- `backend/src/api/handlers/decks_handler.py` - JSON null/未送信の判別ロジック追加

### 現状の問題点 (deck_service.py:194-262)

```python
def update_deck(self, user_id, deck_id, name=None, description=None, color=None):
    # description=None と未送信を区別できない
    if description is not None:
        update_parts.append("description = :description")
    # color=None と未送信を区別できない
    if color is not None:
        update_parts.append("color = :color")
```

### 修正後の設計 (architecture.md セクション2)

```python
_UNSET = object()

def update_deck(self, user_id, deck_id, name=_UNSET, description=_UNSET, color=_UNSET):
    if description is None:
        remove_parts.append("description")
    elif description is not _UNSET:
        update_parts.append("description = :description")
    # _UNSET -> no change
```

## 設計文書

- **要件定義**: `docs/spec/deck-review-fixes/requirements.md` (REQ-105, REQ-106, EDGE-102)
- **アーキテクチャ**: `docs/design/deck-review-fixes/architecture.md` (セクション2: DynamoDB REMOVE パターン)

## 注意事項

- `name` フィールドは REMOVE 不可（必須フィールド）。name=_UNSET -> no change, name=値 -> SET
- UpdateExpression の SET + REMOVE 組み合わせ構築が必要
- `decks_handler.py` では JSON body の key 存在チェック (`"description" in body`) で null/未送信を判別
- Pydantic の `UpdateDeckRequest` モデル自体は変更不要（handler で raw body から判別）

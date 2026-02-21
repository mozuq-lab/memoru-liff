# Refactor Phase: card_count Transaction Fixes

**Task ID**: TASK-0043
**Feature**: card_count transaction fixes
**Phase**: Refactor (品質改善)
**Created**: 2026-02-21

---

## リファクタリング概要

Green フェーズで実装されたコードの品質改善を実施した。
全 211 テストが引き続き通過していることを確認済み。

---

## テスト実行結果

### リファクタ前

```
211 passed in 9.52s
```

### リファクタ後

```
211 passed in 8.56s
```

リグレッションなし、テスト実行時間もわずかに改善。

---

## セキュリティレビュー結果

| 項目 | 評価 | 詳細 |
|------|------|------|
| 入力値検証 | ✅ 問題なし | `card_id`, `user_id` は JWT クレームから取得され handler.py で処理される 🔵 |
| CancellationReasons 解析 | ✅ 問題なし | `.get()` によるデフォルト値処理で KeyError を防いでいる 🔵 |
| エラーメッセージ | ✅ 問題なし | 内部エラーの詳細は `logger.error` のみに出力され、レスポンスには含まれない 🔵 |
| カード上限 | ✅ 問題なし | `MAX_CARDS_PER_USER = 2000` を定数管理し、トランザクションで一元チェック 🔵 |

**重大な脆弱性**: 発見されなかった

---

## パフォーマンスレビュー結果

| 項目 | 評価 | 詳細 |
|------|------|------|
| `create_card` トランザクション | ✅ 適切 | 2オペレーション（Users Update + Cards Put）、DynamoDB 上限 25 の範囲内 🔵 |
| `delete_card` 事前読み取り | ⚠️ 設計上許容 | `get_card()` + `transact_write_items()` の 2回呼び出しは、存在確認とレースコンディション対策のため意図的 🟡 |
| `delete_card` トランザクション | ✅ 適切 | 3オペレーション（Cards Delete + Reviews Delete + Users Update）、DynamoDB 上限内 🔵 |
| トランザクションサイズ | ✅ 問題なし | 小さなアイテムのみで 4MB 上限に達しない 🔵 |

**重大な性能課題**: 発見されなかった

---

## 実施したリファクタリング

### 1. `card_service.py`: `__init__` 引数の行長修正 🔵

**変更理由**: PEP8 の行長制限（79文字）への適合。可読性向上。

**Before**:
```python
def __init__(self, table_name: Optional[str] = None, dynamodb_resource=None, users_table_name: Optional[str] = None, reviews_table_name: Optional[str] = None):
```

**After**:
```python
def __init__(
    self,
    table_name: Optional[str] = None,
    dynamodb_resource=None,
    users_table_name: Optional[str] = None,
    reviews_table_name: Optional[str] = None,
):
```

**信頼性**: 🔵 - PEP8 スタイルガイドに完全準拠

---

### 2. `card_service.py`: `delete_card` の docstring 強化 🔵

**変更理由**: Green フェーズで実装したトランザクション仕様（3オペレーション、各インデックスのエラー意味）が docstring に反映されていなかった。

**Before**:
```python
def delete_card(self, user_id: str, card_id: str) -> None:
    """Delete a card atomically with card_count decrement.

    Args:
        user_id: The user's ID.
        card_id: The card's ID.

    Raises:
        CardNotFoundError: If card does not exist.
        CardServiceError: If card_count is already at 0 or other error.
    ...
    """
```

**After**:
```python
def delete_card(self, user_id: str, card_id: str) -> None:
    """Delete a card atomically with card_count decrement.

    DynamoDB TransactWriteItems を使用して以下の3操作をアトミックに実行する:
      - Index 0: Cards テーブルからカードを削除 (attribute_exists 条件チェック付き)
      - Index 1: Reviews テーブルから関連レビューを削除 (条件なし: レビュー未作成でも成功)
      - Index 2: Users テーブルの card_count を 1 デクリメント (card_count > 0 の下限チェック付き)
    ...
    Raises:
        CardNotFoundError: カードが存在しない場合。または、トランザクション実行中に別リクエストが
                           先にカードを削除した場合（レースコンディション、EARS-012）。
        CardServiceError: card_count が既に 0 の場合（データ整合性ドリフト、EARS-013）。
                          その他の DynamoDB エラーが発生した場合。
    ...
    """
```

**信頼性**: 🔵 - EARS-010, EARS-012, EARS-013 仕様に完全準拠

---

### 3. `test_card_service.py`: fixture の初期化を正式化 🔵

**変更理由**: Green フェーズでは `reviews_table_name` を属性として手動設定していたが、
`__init__` パラメータとして正式にサポートされたため、コードを整合化。
Red フェーズ向けの古いコメントを削除。

**Before**:
```python
service = CardService(
    table_name="memoru-cards-test",
    users_table_name="memoru-users-test",
    dynamodb_resource=dynamodb_table
)
# EARS-011: reviews_table_name を手動で設定する (現実装では __init__ で受け付けないが、属性として設定)
# Green フェーズでは __init__ パラメータとして正式にサポートされる
service.reviews_table_name = "memoru-reviews-test"
```

**After**:
```python
service = CardService(
    table_name="memoru-cards-test",
    users_table_name="memoru-users-test",
    reviews_table_name="memoru-reviews-test",
    dynamodb_resource=dynamodb_table,
)
```

**信頼性**: 🔵 - EARS-011 仕様に準拠した正式な初期化

---

### 4. `test_card_service.py`: fixture docstring を更新 🔵

**変更理由**: Red フェーズの「現在の実装はこのパラメータをサポートしていない」という記述が残存していた。Green フェーズ完了後の現状に合わせて更新。

**信頼性**: 🔵 - 実装完了状態を正確に反映

---

### 5. `test_card_service.py`: `mock_transact_write_items` の条件チェック改善 🔵

**変更理由**: `create_card` の `:limit` チェックと `delete_card` の `:zero` チェックが同じ条件ブランチで処理されており、`:limit` キーの有無で分岐する `KeyError` に依存する暗黙の処理になっていた。明示的な `:limit` キーチェックで意図を明確化。

**Before**:
```python
if 'ConditionExpression' in update:
    try:
        response = table.get_item(Key=key_dict)
        current_item = response.get('Item', {})

        # Evaluate condition (simplified for card_count < :limit)
        if 'card_count' in current_item:
            limit = int(update['ExpressionAttributeValues'][':limit']['N'])
            if not (current_item['card_count'] < limit):
                raise ClientError(...)
    except KeyError:
        pass  # Item doesn't exist yet
```

**After**:
```python
if 'ConditionExpression' in update:
    response = table.get_item(Key=key_dict)
    current_item = response.get('Item', {})
    expr_values = update.get('ExpressionAttributeValues', {})
    card_count = int(current_item.get('card_count', 0))

    # 【条件チェック】: create_card の card_count < :limit 条件
    # (if_not_exists(card_count, :zero) < :limit を模擬)
    if ':limit' in expr_values:
        limit = int(expr_values[':limit']['N'])
        if not (card_count < limit):
            raise ClientError(...)
```

**信頼性**: 🔵 - 条件分岐の意図が明確になり、保守性が向上

---

## リファクタリング対象外とした項目

### `test_timezone_aware.py` の `mock_transact_write_items` 重複コード

**判断**: `test_timezone_aware.py` のモックは Delete 操作をサポートしない簡易版であり、
このテストファイルの目的（タイムゾーン確認）に特化した設計。
`test_card_service.py` のモックと完全に同一化する必要はなく、意図的な差異として許容。

conftest.py への共通モック抽出は、テストの独立性（他ファイルへの依存関係の増加）と
改善のトレードオフを考慮して今回は実施しない。

### `InternalError` の `__init__.py` エクスポート

**判断**: 現在は `test_card_service.py` で `from src.services.card_service import InternalError`
として直接インポートされており機能している。
パブリック API として公開する必要性は現時点では低いため、今回は変更しない。

---

## 品質判定

```
✅ 高品質:
- テスト結果: 211 passed (リグレッションなし)
- セキュリティ: 重大な脆弱性なし
- パフォーマンス: 重大な性能課題なし
- リファクタ品質: 目標達成（コード整合性、docstring 強化、モック改善）
- コード品質: 適切なレベルに向上
- ファイルサイズ: card_service.py 約 530 行 (500 行を若干超えるが、各メソッドが独立しており分割不要)
- 日本語コメント: 既存コメントが充実しており追加改善を実施
```

---

## 最終コード状態

### `backend/src/services/card_service.py` (主要変更箇所)

```python
class CardService:
    def __init__(
        self,
        table_name: Optional[str] = None,
        dynamodb_resource=None,
        users_table_name: Optional[str] = None,
        reviews_table_name: Optional[str] = None,
    ):
        ...

    def delete_card(self, user_id: str, card_id: str) -> None:
        """Delete a card atomically with card_count decrement.

        DynamoDB TransactWriteItems を使用して以下の3操作をアトミックに実行する:
          - Index 0: Cards テーブルからカードを削除 (attribute_exists 条件チェック付き)
          - Index 1: Reviews テーブルから関連レビューを削除 (条件なし)
          - Index 2: Users テーブルの card_count を 1 デクリメント (下限チェック付き)

        Raises:
            CardNotFoundError: カードが存在しない場合、またはレースコンディション (EARS-012)。
            CardServiceError: card_count が 0 の場合 (EARS-013)、その他エラー。
        ...
        """
```

---

**Document Version**: 1.0
**Last Updated**: 2026-02-21
**Author**: Claude Code

# Red Phase: card_count Transaction Fixes

**Task ID**: TASK-0043
**Feature**: card_count transaction fixes
**Phase**: Red (失敗するテスト作成)
**Created**: 2026-02-21

---

## 作成したテストケース一覧

| ID | クラス | メソッド | 失敗理由 | 信頼性 |
|----|--------|---------|---------|--------|
| TC-01 | TestCardCountIfNotExists | test_create_card_with_missing_card_count | `card_count + :inc` で属性未存在エラー | 🔵 |
| TC-02 | TestTransactionErrorClassification | test_conditional_check_failed_raises_limit_error | **既存実装でPASS** | 🔵 |
| TC-03 | TestTransactionErrorClassification | test_non_conditional_raises_internal_error | `InternalError` クラスが存在しない (ImportError) | 🔵 |
| TC-04a | TestTransactionErrorClassification | test_missing_cancellation_reasons_raises_internal | `InternalError` クラスが存在しない (ImportError) | 🟡 |
| TC-04b | TestTransactionErrorClassification | test_empty_cancellation_reasons_raises_internal | `InternalError` クラスが存在しない (ImportError) | 🟡 |
| TC-05 | TestDeleteCardTransaction | test_delete_card_decrements_card_count | `delete_card` がトランザクションを使わない | 🔵 |
| TC-06a | TestDeleteCardTransaction | test_delete_card_race_condition_not_found | `delete_card` がトランザクションを使わない | 🔵 |
| TC-06b | TestDeleteCardTransaction | test_delete_card_prevents_negative_count | `delete_card` がトランザクションを使わない | 🟡 |
| TC-07 | TestGetOrCreateUser | test_get_or_create_user_existing | **既存実装でPASS** | 🔵 |
| TC-08 | TestGetOrCreateUser | test_get_or_create_user_new | **既存実装でPASS** | 🔵 |
| TC-09 | TestCardCountEndToEnd | test_create_delete_card_count_consistency | `delete_card` が card_count をデクリメントしない | 🔵 |

---

## テスト実行結果

```
collected 30 items / 21 deselected / 9 selected

TestCardCountIfNotExists::test_create_card_with_missing_card_count FAILED
TestTransactionErrorClassification::test_conditional_check_failed_raises_limit_error PASSED  ← 期待通り
TestTransactionErrorClassification::test_non_conditional_raises_internal_error FAILED
TestTransactionErrorClassification::test_missing_cancellation_reasons_raises_internal FAILED
TestTransactionErrorClassification::test_empty_cancellation_reasons_raises_internal FAILED
TestDeleteCardTransaction::test_delete_card_decrements_card_count FAILED
TestDeleteCardTransaction::test_delete_card_race_condition_not_found FAILED
TestDeleteCardTransaction::test_delete_card_prevents_negative_count FAILED
TestCardCountEndToEnd::test_create_delete_card_count_consistency FAILED

8 failed, 1 passed (TC-02 is expected pass per testcases.md)
```

---

## 失敗の詳細

### TC-01: card_count属性なしでのカード作成
```
CardServiceError: Failed to create card: An error occurred (ValidationException)
when calling the UpdateItem operation: The provided expression refers to an attribute
that does not exist in the item
```
**原因**: `card_service.py` L112 の `'SET card_count = card_count + :inc'` が card_count 属性なしで失敗する。
**Fix**: `'SET card_count = if_not_exists(card_count, :zero) + :inc'` に変更が必要。

### TC-03, TC-04a, TC-04b: InternalError クラスの欠如
```
ImportError: cannot import name 'InternalError' from 'src.services.card_service'
```
**原因**: `InternalError` クラスが `card_service.py` に存在しない。
**Fix**: `CardServiceError` を継承する `InternalError` クラスを追加する。

### TC-05: card_count がデクリメントされない
```
AssertionError: assert Decimal('6') == 5
```
**原因**: `delete_card` が `table.delete_item()` を使って単純削除するだけで、card_count を更新しない。
**Fix**: `transact_write_items` を使ってアトミックに削除とデクリメントを実行する。

### TC-06a: レースコンディションで CardNotFoundError が発生しない
```
Failed: DID NOT RAISE <class 'src.services.card_service.CardNotFoundError'>
```
**原因**: `delete_card` がトランザクションを使わないため、CancellationReasons を解析できない。
**Fix**: `transact_write_items` を使って CancellationReasons を解析する。

### TC-06b: CardServiceError が発生しない
```
Failed: DID NOT RAISE <class 'src.services.card_service.CardServiceError'>
```
**原因**: `delete_card` がトランザクションを使わないため、card_count 下限チェックができない。
**Fix**: `transact_write_items` で `ConditionExpression: 'card_count > :zero'` を設定する。

### TC-09: エンドツーエンドで card_count が一貫しない
```
AssertionError: assert Decimal('3') == 2
```
**原因**: TC-05 と同じ。`delete_card` が card_count をデクリメントしない。

---

## 実装ファイル

- **テストファイル (card)**: `backend/tests/unit/test_card_service.py`
- **テストファイル (user)**: `backend/tests/unit/test_user_service.py`

---

## Green フェーズで実装すべき内容

### 1. `InternalError` クラスの追加 (card_service.py L26-29 の後)
```python
class InternalError(CardServiceError):
    """Raised when an internal transaction error occurs."""
    pass
```

### 2. `reviews_table_name` パラメータの追加 (card_service.py L37)
```python
def __init__(self, table_name=None, dynamodb_resource=None, users_table_name=None, reviews_table_name=None):
    ...
    self.reviews_table_name = reviews_table_name or os.environ.get("REVIEWS_TABLE", "memoru-reviews-dev")
```

### 3. `create_card` の UpdateExpression 修正 (card_service.py L112-117)
```python
'UpdateExpression': 'SET card_count = if_not_exists(card_count, :zero) + :inc',
'ConditionExpression': 'if_not_exists(card_count, :zero) < :limit',
'ExpressionAttributeValues': {
    ':inc': {'N': '1'},
    ':limit': {'N': str(self.MAX_CARDS_PER_USER)},
    ':zero': {'N': '0'}
}
```

### 4. `create_card` のエラー処理修正 (card_service.py L129-133)
```python
except ClientError as e:
    if e.response["Error"]["Code"] == "TransactionCanceledException":
        reasons = e.response.get("CancellationReasons", [])
        if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
            raise CardLimitExceededError(f"Card limit of {self.MAX_CARDS_PER_USER} exceeded")
        logger.error(f"Transaction cancelled with reasons: {reasons}")
        raise InternalError("Card creation failed due to transaction conflict")
    raise CardServiceError(f"Failed to create card: {e}")
```

### 5. `delete_card` メソッドの書き換え (card_service.py L234-250)
```python
def delete_card(self, user_id: str, card_id: str) -> None:
    self.get_card(user_id, card_id)
    try:
        client = self.dynamodb.meta.client
        client.transact_write_items(
            TransactItems=[
                {'Delete': {'TableName': self.table_name, 'Key': {...}, 'ConditionExpression': 'attribute_exists(card_id)'}},
                {'Delete': {'TableName': self.reviews_table_name, 'Key': {...}}},
                {'Update': {'TableName': self.users_table_name, 'Key': {...},
                            'UpdateExpression': 'SET card_count = card_count - :dec',
                            'ConditionExpression': 'card_count > :zero', ...}},
            ]
        )
    except ClientError as e:
        # CancellationReasons[0] → CardNotFoundError
        # CancellationReasons[2] → CardServiceError (card_count already 0)
```

---

## 品質評価

| 項目 | 評価 |
|------|------|
| テスト実行 | ✅ 実行可能 (8 FAILED, 1 PASSED as expected) |
| 期待値 | ✅ 明確で具体的 |
| アサーション | ✅ 適切 |
| 実装方針 | ✅ 明確 |
| 信頼性分布 | 🔵 x 7, 🟡 x 2, 🔴 x 0 |

**総合評価**: ✅ 高品質 - 全テストが適切に失敗し、実装すべき内容が明確

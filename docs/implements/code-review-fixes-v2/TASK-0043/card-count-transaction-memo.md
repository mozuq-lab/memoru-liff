# TDD開発メモ: card-count-transaction

## 概要

- 機能名: card_count Transaction Fixes
- 開発開始: 2026-02-21
- 現在のフェーズ: 完了 (Red → Green → Refactor 完了)

## 関連ファイル

- 元タスクファイル: `docs/tasks/memoru-liff/TASK-0043.md`
- 要件定義: `docs/implements/code-review-fixes-v2/TASK-0043/requirements.md`
- テストケース定義: `docs/implements/code-review-fixes-v2/TASK-0043/testcases.md`
- 実装ファイル (card): `backend/src/services/card_service.py`
- 実装ファイル (handler): `backend/src/api/handler.py`
- テストファイル (card): `backend/tests/unit/test_card_service.py`
- テストファイル (user): `backend/tests/unit/test_user_service.py`

## Redフェーズ（失敗するテスト作成）

### 作成日時

2026-02-21

### テストケース

11個のテストケースを実装 (9個がcard_service、2個がuser_service)：

| ID | テスト | 状態 |
|----|--------|------|
| TC-01 | card_count属性なしでのカード作成 | FAIL (期待通り) |
| TC-02 | ConditionalCheckFailed → CardLimitExceededError | PASS (既存実装で動作) |
| TC-03 | 非ConditionalCheckFailed → InternalError | FAIL (InternalError未定義) |
| TC-04a | CancellationReasons欠如 → InternalError | FAIL (InternalError未定義) |
| TC-04b | CancellationReasons空リスト → InternalError | FAIL (InternalError未定義) |
| TC-05 | delete_card がcard_countをデクリメント | FAIL (トランザクション未実装) |
| TC-06a | delete_card レースコンディション → CardNotFoundError | FAIL (トランザクション未実装) |
| TC-06b | card_count = 0 での削除 → CardServiceError | FAIL (トランザクション未実装) |
| TC-07 | get_or_create_user 既存ユーザー返却 | PASS (既存実装で動作) |
| TC-08 | get_or_create_user 新規ユーザー作成 | PASS (既存実装で動作) |
| TC-09 | エンドツーエンド card_count 一貫性 | FAIL (delete_card未修正) |

### テスト実行コマンド

```bash
# card_service の新規テスト
cd backend && python -m pytest tests/unit/test_card_service.py -v \
  -k "TestCardCountIfNotExists or TestTransactionErrorClassification or TestDeleteCardTransaction or TestCardCountEndToEnd" \
  --tb=short

# user_service の新規テスト
cd backend && python -m pytest tests/unit/test_user_service.py -v \
  -k "get_or_create" --tb=short
```

### 期待される失敗

1. **TC-01** (`CardServiceError: Failed to create card: ValidationException`):
   - 原因: `card_count + :inc` が card_count 属性なしで失敗する
   - Fix: `if_not_exists(card_count, :zero) + :inc` に変更

2. **TC-03, TC-04a, TC-04b** (`ImportError: cannot import name 'InternalError'`):
   - 原因: `InternalError` クラスが card_service.py に存在しない
   - Fix: `InternalError(CardServiceError)` クラスを追加

3. **TC-05** (`AssertionError: assert Decimal('6') == 5`):
   - 原因: `delete_card` が card_count をデクリメントしない
   - Fix: `transact_write_items` でアトミックに削除とデクリメントを実行

4. **TC-06a** (`Failed: DID NOT RAISE CardNotFoundError`):
   - 原因: `delete_card` がトランザクションを使わないため CancellationReasons を解析できない
   - Fix: `transact_write_items` + CancellationReasons 解析

5. **TC-06b** (`Failed: DID NOT RAISE CardServiceError`):
   - 原因: `delete_card` が card_count 下限チェックをしない
   - Fix: `ConditionExpression: 'card_count > :zero'` をトランザクションに追加

6. **TC-09** (`AssertionError: assert Decimal('3') == 2`):
   - 原因: TC-05 と同じく `delete_card` が card_count をデクリメントしない

### 次のフェーズへの要求事項

#### card_service.py への変更

1. **InternalError クラスの追加** (L26-29の後):
   ```python
   class InternalError(CardServiceError):
       """Raised when an internal transaction error occurs."""
       pass
   ```

2. **`reviews_table_name` パラメータの追加** (L37):
   ```python
   def __init__(self, table_name=None, dynamodb_resource=None,
                users_table_name=None, reviews_table_name=None):
       ...
       self.reviews_table_name = reviews_table_name or os.environ.get("REVIEWS_TABLE", "memoru-reviews-dev")
   ```

3. **create_card の UpdateExpression/ConditionExpression 修正** (L112-117):
   ```python
   'UpdateExpression': 'SET card_count = if_not_exists(card_count, :zero) + :inc',
   'ConditionExpression': 'if_not_exists(card_count, :zero) < :limit',
   'ExpressionAttributeValues': {
       ':inc': {'N': '1'},
       ':limit': {'N': str(self.MAX_CARDS_PER_USER)},
       ':zero': {'N': '0'}
   }
   ```

4. **create_card のエラー処理修正** (L129-133):
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

5. **delete_card メソッドの書き換え** (L234-250):
   - `table.delete_item()` → `client.transact_write_items()` に変更
   - Cards 削除 (Index 0) + Reviews 削除 (Index 1) + card_count デクリメント (Index 2)
   - CancellationReasons 解析: [0]ConditionalCheckFailed → CardNotFoundError, [2]ConditionalCheckFailed → CardServiceError

#### card_service フィクスチャの更新 (test_card_service.py)

- `reviews_table_name` パラメータを正式に使用するよう変更
- `mock_transact_write_items` の Delete 操作サポートは既に追加済み
- card_count デクリメントロジックを mock に追加する必要がある

## Greenフェーズ（最小実装）

### 実装日時

2026-02-21

### 実装方針

1. `InternalError` 例外クラスを `CardServiceError` 継承で追加
2. `Logger` インポートと `logger = Logger()` を追加（エラーロギング用）
3. `__init__` に `reviews_table_name` パラメータを追加
4. `create_card` の UpdateExpression を `if_not_exists(card_count, :zero) + :inc` に修正
5. `create_card` の ConditionExpression を `if_not_exists(card_count, :zero) < :limit` に修正
6. `create_card` のエラーハンドリングを CancellationReasons 解析版に修正
7. `delete_card` を `transact_write_items` を使ったトランザクション版に書き換え
8. `handler.py` の `create_card` エンドポイントに `get_or_create_user` 呼び出しを追加
9. `test_timezone_aware.py` の `card_service` fixture にカスタムモックを追加（moto の if_not_exists バグ対応）

### 実装した変更

| ファイル | 変更内容 |
|---------|---------|
| `backend/src/services/card_service.py` | InternalError クラス追加、Logger追加、reviews_table_name追加、if_not_exists修正、CancellationReasons解析、delete_card トランザクション化 |
| `backend/src/api/handler.py` | create_card エンドポイントに get_or_create_user 呼び出しを追加 |
| `backend/tests/unit/test_timezone_aware.py` | card_service fixture にカスタムモックを追加 |

### テスト結果

```
# 新規テスト (9件)
cd backend && python -m pytest tests/unit/test_card_service.py -v \
  -k "TestCardCountIfNotExists or TestTransactionErrorClassification or TestDeleteCardTransaction or TestCardCountEndToEnd" \
  --tb=short
# 結果: 9 passed

# user_service テスト (2件)
cd backend && python -m pytest tests/unit/test_user_service.py -v \
  -k "get_or_create" --tb=short
# 結果: 2 passed

# 全ユニットテスト
cd backend && python -m pytest tests/unit/ -v --tb=short
# 結果: 157 passed (リグレッションなし)
```

### 課題・改善点（Refactorフェーズ対象）

1. **mock_transact_write_items の重複コード**: `test_card_service.py` と `test_timezone_aware.py` に同様のモックロジックが存在。共通 fixture に抽出できる。
2. **delete_card の card_count デクリメント**: mock の card_count デクリメントロジックが完全ではない（test_card_service.py の mock では手動でデクリメントしている）。
3. **ドキュメント**: delete_card メソッドの docstring に新しいトランザクション仕様を詳細に記述する。
4. **型ヒント**: `InternalError` のインポートエクスポート管理を整理する。

## Refactorフェーズ（品質改善）

### 実装日時

2026-02-21

### 改善内容

| 項目 | 改善内容 | 信頼性 |
|------|---------|--------|
| `card_service.py` `__init__` | 引数の行長を PEP8 準拠に修正 | 🔵 |
| `card_service.py` `delete_card` docstring | トランザクション3オペレーションの詳細、Raises 詳細を追加 | 🔵 |
| `test_card_service.py` fixture 初期化 | `reviews_table_name` を `__init__` パラメータとして正式化 | 🔵 |
| `test_card_service.py` fixture docstring | Red フェーズ向けの古い記述を削除・更新 | 🔵 |
| `test_card_service.py` mock 条件チェック | `:limit` キーの明示的チェックで `KeyError` 依存を解消 | 🔵 |

### テスト結果

```
211 passed in 8.56s (リグレッションなし)
```

### セキュリティレビュー

重大な脆弱性なし。エラーメッセージの情報漏洩リスクなし。

### パフォーマンスレビュー

重大な性能課題なし。`delete_card` の 2回 DynamoDB 呼び出しは設計上意図的。

### 品質評価

| 項目 | 評価 |
|------|------|
| テスト結果 | ✅ 211 passed |
| セキュリティ | ✅ 問題なし |
| パフォーマンス | ✅ 問題なし |
| コード品質 | ✅ PEP8 準拠、docstring 充実 |
| ドキュメント | ✅ refactor-phase.md 作成済み |

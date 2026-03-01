# TASK-0088: total_due_count 修正 - Green フェーズ記録

**作成日**: 2026-03-01
**タスクID**: TASK-0088
**フェーズ**: Green（最小実装）

---

## 実装方針

### バグ修正の方針

Red フェーズで特定した2つのバグを最小限の変更で修正する。

**バグ1の修正**: `card_service.get_due_cards()` に `limit` を渡さない
- `limit` パラメータを `Optional[int] = None` に変更
- `limit is None` の場合は DynamoDB Query に `Limit` を設定しない
- 全復習対象カードを取得することで、deck_id フィルタ前の切り詰めを防ぐ

**バグ2の修正**: `total_due_count` を limit 適用前に計算する
- `all_due_cards` を取得後、deck_id フィルタを適用
- `total_due_count = len(all_due_cards)` で limit 前の総数をカウント
- `limited_cards = all_due_cards[:limit]` でスライスしてから DueCardInfo に変換

---

## 実装コード

### 修正1: `backend/src/services/card_service.py`

**変更内容**: `get_due_cards()` の `limit` パラメータを `Optional[int] = None` に変更

```python
def get_due_cards(
    self,
    user_id: str,
    limit: Optional[int] = None,  # 変更: int=20 → Optional[int]=None
    before: Optional[datetime] = None,
) -> List[Card]:
    """Get cards due for review.

    Args:
        user_id: The user's ID.
        limit: Maximum number of cards to return. If None, returns all due cards.
               【バグ1修正】: limit=None を受け付けることで、DynamoDB クエリ前の
               切り詰めを防止する（TASK-0088）。🔵
        before: Get cards due before this time (defaults to now).

    Returns:
        List of cards due for review.
    """
    if before is None:
        before = datetime.now(timezone.utc)

    try:
        # 【クエリ引数構築】: limit=None の場合は DynamoDB に Limit を渡さない
        # これにより全復習対象カードを取得でき、deck_id フィルタ前の切り詰めを防ぐ 🔵
        query_kwargs = {
            "IndexName": "user_id-due-index",
            "KeyConditionExpression": "user_id = :user_id AND next_review_at <= :before",
            "ExpressionAttributeValues": {
                ":user_id": user_id,
                ":before": before.isoformat(),
            },
            "ScanIndexForward": True,  # Oldest due first
        }
        # 【Limit 条件付き設定】: limit が指定された場合のみ DynamoDB Limit を設定する 🔵
        if limit is not None:
            query_kwargs["Limit"] = limit

        response = self.table.query(**query_kwargs)
        return [Card.from_dynamodb_item(item) for item in response.get("Items", [])]
    except ClientError as e:
        raise CardServiceError(f"Failed to get due cards: {e}")
```

### 修正2: `backend/src/services/review_service.py`

**変更内容**: `get_due_cards()` メソッドのロジックを修正

```python
def get_due_cards(
    self,
    user_id: str,
    limit: int = 20,
    include_future: bool = False,
    deck_id: Optional[str] = None,
) -> DueCardsResponse:
    # ...
    now = datetime.now(timezone.utc)

    # 【バグ1修正】: limit を渡さず全復習対象カードを取得する
    # 旧実装では card_service.get_due_cards(limit=limit) を呼んでおり、
    # DynamoDB Query レベルで limit 件数に切り詰められていた。
    all_due_cards = self.card_service.get_due_cards(
        user_id=user_id,
        limit=None,  # 【バグ1修正】: DynamoDB Query レベルの切り詰めを防ぐ 🔵
        before=now if not include_future else None,
    )

    # Filter by deck_id if specified
    if deck_id is not None:
        all_due_cards = [c for c in all_due_cards if c.deck_id == deck_id]

    # 【バグ2修正】: total_due_count を limit 適用前に計算する
    # 旧実装では deck_id フィルタ後 limit 適用後のリスト長（due_card_infos の件数）を
    # total_due_count として返していた。
    total_due_count = len(all_due_cards)  # limit 前の全件数 🔵

    # 【limit 適用】: 返却カードのみ limit で制限する（total_due_count には影響しない）🔵
    limited_cards = all_due_cards[:limit]

    # Convert to response format
    due_card_infos: List[DueCardInfo] = []
    for card in limited_cards:
        overdue_days = 0
        if card.next_review_at:
            delta = now - card.next_review_at
            overdue_days = max(0, delta.days)

        due_card_infos.append(
            DueCardInfo(
                card_id=card.card_id,
                front=card.front,
                back=card.back,
                deck_id=card.deck_id,
                due_date=card.next_review_at.date().isoformat() if card.next_review_at else None,
                overdue_days=overdue_days,
            )
        )

    # ...
    return DueCardsResponse(
        due_cards=due_card_infos,
        total_due_count=total_due_count,
        next_due_date=next_due_date,
    )
```

---

## テスト実行結果

### TASK-0088 専用テスト（TestGetDueCardsTotalDueCountFix）

```
tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc001_total_due_count_without_deck_id_limit_less_than_total PASSED
tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc002_total_due_count_with_deck_id_limit_greater_than_deck_cards PASSED
tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc003_total_due_count_with_deck_id_limit_less_than_deck_cards PASSED
tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc004_total_due_count_without_deck_id_limit_gte_total PASSED
tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc005_card_service_called_without_limit_for_total_count PASSED
tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc006_nonexistent_deck_id_returns_empty_response PASSED
tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc007_zero_due_cards_returns_next_due_date PASSED
tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc008_small_limit_returns_correct_total_count PASSED
tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc009_limit_one_returns_single_card_with_correct_total PASSED
tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc010_deck_id_filter_excludes_all_cards_returns_zero PASSED
tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc011_deck_id_with_limit_card_service_level_truncation_bug PASSED
tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc012_limit_max_100_with_larger_total_returns_correct_count PASSED

12 passed in 1.14s
```

### 全テスト（既存テストの影響確認）

```
49 passed in 3.40s
```

**結果**: 全 49 テスト PASSED（TC-003, TC-011 の FAILED → PASSED 達成）

---

## 品質評価

| 評価項目 | 結果 | 備考 |
|---------|------|------|
| テスト成功状況 | ✅ | 49/49 全通過 |
| 実装品質 | ✅ | シンプルな修正のみ |
| リファクタ箇所 | ✅ | 明確に特定可能 |
| 機能的問題 | ✅ | なし |
| ファイルサイズ | ✅ | review_service.py: 608行, card_service.py: 598行 |
| モック使用 | ✅ | 実装コードにモック・スタブなし |

---

## 課題・改善点（Refactor フェーズ）

1. **パフォーマンス**: 全件取得 (`limit=None`) によりメモリ使用量が増える
   - 現状は MVP なので許容（最大 2000 件）
   - 将来改善: GSI + カウンターテーブル or DynamoDB FilterExpression 最適化

2. **`get_due_card_count()` の不使用化**: deck_id なしの場合でも全件取得で対応しているため、
   `card_service.get_due_card_count()` が呼ばれなくなった
   - 既存テスト `test_get_due_cards_empty` が `next_due_date` を確認しているため影響なし
   - Refactor フェーズで `get_due_card_count()` の扱いを整理する

3. **`limit` の型変更の影響確認**: `card_service.get_due_cards()` の `limit` を `Optional[int]` に変更した
   - 既存の呼び出し元 (`review_service.py` 以外) を確認する
   - `limit=None` のデフォルト変更が意図しない動作変化を起こしていないか確認

# TASK-0088: total_due_count 修正 - Red フェーズ記録

**作成日**: 2026-03-01
**タスクID**: TASK-0088
**フェーズ**: Red（失敗するテスト作成）

---

## 作成したテストケース一覧

| ID | テスト名 | 信頼性 | 結果 |
|----|---------|--------|------|
| TC-001 | deck_id なし・limit=10 で20件の復習対象カードがある場合、total_due_count=20 を返す | 🔵 | PASSED（既存動作確認） |
| TC-002 | deck_id フィルタ付き・limit(10) > デッキ内カード数(5) の場合の total_due_count | 🔵 | PASSED |
| TC-003 | deck_id フィルタ付き・limit(10) < デッキ内カード数(15) の場合の total_due_count | 🔵 | **FAILED（バグ2の検証）** |
| TC-004 | limit(20) >= 全件数(15) の場合に total_due_count と due_cards の件数が一致 | 🔵 | PASSED |
| TC-005 | card_service.get_due_cards に limit が渡されず全件取得されることの確認 | 🔵 | PASSED |
| TC-006 | 存在しないデッキIDを指定した場合に空レスポンスが返る | 🟡 | PASSED |
| TC-007 | 復習対象カードがない場合に total_due_count=0 と next_due_date が返る | 🔵 | PASSED |
| TC-008 | limit=2（小さい値）の場合に total_due_count が全件数を返す | 🟡 | PASSED |
| TC-009 | limit=1（最小有効値）の場合に total_due_count が全件数を返す | 🟡 | PASSED |
| TC-010 | deck_id フィルタで該当カード0件の場合に total_due_count=0 を返す | 🟡 | PASSED |
| TC-011 | deck_id フィルタ時に card_service レベルの limit でカードが切り詰められないこと | 🔵 | **FAILED（バグ1の検証）** |
| TC-012 | limit=100（API 上限）の場合に total_due_count が正確な全件数を返す | 🟡 | PASSED |

---

## テストが失敗した詳細

### TC-003 失敗（バグ2 の直接検証）

```
AssertionError: assert 10 == 15
  where 10 = DueCardsResponse(..., total_due_count=10, ...).total_due_count
```

**原因**: `review_service.py` 行 429-430 のバグ:
```python
if deck_id is not None:
    total_due_count = len(due_card_infos)  # ❌ limit 適用後の件数（バグ）
```
`due_card_infos` は limit で切り詰められた `due_cards` から変換されるため、
`total_due_count` が `limit` の値(10)になってしまっている。正しくは15。

### TC-011 失敗（バグ1 の検証）

```
AssertionError: assert 1 == 4
  where 1 = DueCardsResponse(..., total_due_count=1, ...).total_due_count
```

**原因**: `review_service.py` 行 398-402 のバグ:
```python
due_cards = self.card_service.get_due_cards(
    user_id=user_id,
    limit=limit,  # ❌ DynamoDB Query に limit が渡される（バグ）
    before=now if not include_future else None,
)
```
`card_service.get_due_cards()` が `Limit=5` で DynamoDB をクエリするため、
GSI ソート順（古い due 日順）で先頭5件のみが取得される。
デッキAのカードが古い場合、5件中デッキBは1件のみになり、
`deck_id="deck-b-tc011"` フィルタ後 total_due_count=1（正解は4）。

---

## テストファイル

- **テストファイル**: `backend/tests/unit/test_review_service.py`
- **追加クラス**: `TestGetDueCardsTotalDueCountFix`
- **ヘルパー関数**: `_put_due_card()`

---

## テスト実行コマンド

```bash
# 全 TASK-0088 テスト実行
cd backend && python -m pytest tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix -v

# 特定のテストのみ実行
cd backend && python -m pytest tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc003_total_due_count_with_deck_id_limit_less_than_deck_cards -v

# 全テストファイル実行（既存テストが壊れていないことを確認）
cd backend && python -m pytest tests/unit/test_review_service.py -v
```

---

## 期待される失敗メッセージ（修正前）

### TC-003
```
FAILED tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc003_total_due_count_with_deck_id_limit_less_than_deck_cards
AssertionError: assert 10 == 15
```

### TC-011
```
FAILED tests/unit/test_review_service.py::TestGetDueCardsTotalDueCountFix::test_tc011_deck_id_with_limit_card_service_level_truncation_bug
AssertionError: assert 1 == 4
```

---

## Green フェーズで実装すべき内容

### `review_service.py` の `get_due_cards()` メソッド修正

```python
def get_due_cards(
    self,
    user_id: str,
    limit: int = 20,
    include_future: bool = False,
    deck_id: Optional[str] = None,
) -> DueCardsResponse:
    now = datetime.now(timezone.utc)

    # Step 1: limit なしで全復習対象カードを取得（バグ1の修正）
    all_due_cards = self.card_service.get_due_cards(
        user_id=user_id,
        limit=None,  # ← limit を渡さない（または十分大きい値を使用）
        before=now if not include_future else None,
    )

    # Step 2: deck_id フィルタ適用
    if deck_id is not None:
        all_due_cards = [c for c in all_due_cards if c.deck_id == deck_id]

    # Step 3: total_due_count を limit 前にカウント（バグ2の修正）
    total_due_count = len(all_due_cards)

    # Step 4: limit 適用（返却カードのみ制限）
    limited_cards = all_due_cards[:limit]

    # Step 5: DueCardInfo に変換
    due_card_infos = [...]  # limited_cards から変換

    # Step 6: レスポンス返却
    return DueCardsResponse(
        due_cards=due_card_infos,
        total_due_count=total_due_count,
        next_due_date=...,
    )
```

### `card_service.py` の `get_due_cards()` メソッド修正（必要な場合）

`limit=None` サポートまたは大きな値（例: 2000）を渡す対応が必要：

```python
def get_due_cards(
    self,
    user_id: str,
    limit: Optional[int] = None,  # ← Optional に変更
    before: Optional[datetime] = None,
) -> List[Card]:
    # ...
    query_kwargs = {
        "IndexName": "user_id-due-index",
        "KeyConditionExpression": "...",
        "ScanIndexForward": True,
    }
    if limit is not None:
        query_kwargs["Limit"] = limit

    response = self.table.query(**query_kwargs)
```

---

## 信頼性レベルサマリー

- **総テストケース数**: 12件
- 🔵 **青信号**: 7件 (58%) - 要件定義・既存実装から直接導出
- 🟡 **黄信号**: 5件 (42%) - 要件定義から妥当な推測
- 🔴 **赤信号**: 0件 (0%)

**品質評価**: ✅ 高品質

---

## テスト実行結果サマリー

```
49 tests total:
  - 47 passed (既存テスト 47件全て通過)
  - 2 failed (TC-003, TC-011: バグを正しく検出)

FAILED: test_tc003_total_due_count_with_deck_id_limit_less_than_deck_cards
FAILED: test_tc011_deck_id_with_limit_card_service_level_truncation_bug
```

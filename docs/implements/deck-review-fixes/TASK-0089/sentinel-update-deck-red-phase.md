# TASK-0089: Sentinel パターン update_deck - Red フェーズ記録

**タスクID**: TASK-0089
**機能名**: sentinel-update-deck
**フェーズ**: Red（失敗テスト作成）
**作成日**: 2026-03-01

---

## 作成したテストケース一覧

| No. | テストメソッド | TC | 分類 | 信頼性 | 結果 |
|-----|--------------|-----|------|--------|------|
| 1 | test_tc001_description_unset_no_change | TC-001 | 正常系 | 🔵 | PASS（既存実装と互換） |
| 2 | test_tc002_description_none_removes_attribute | TC-002 | 正常系 | 🔵 | **FAIL** ← 期待通り |
| 3 | test_tc003_description_value_sets_attribute | TC-003 | 正常系 | 🔵 | PASS（既存実装と互換） |
| 4 | test_tc004_color_unset_no_change | TC-004 | 正常系 | 🔵 | PASS（既存実装と互換） |
| 5 | test_tc005_color_none_removes_attribute | TC-005 | 正常系 | 🔵 | **FAIL** ← 期待通り |
| 6 | test_tc006_color_value_sets_attribute | TC-006 | 正常系 | 🔵 | PASS（既存実装と互換） |
| 7 | test_tc007_description_and_color_none_both_removed | TC-007 | 正常系 | 🔵 | **FAIL** ← 期待通り |
| 8 | test_tc008_mixed_set_and_remove | TC-008 | 正常系 | 🔵 | **FAIL** ← 期待通り |
| 9 | test_tc009_all_unset_returns_existing_deck | TC-009 | 正常系 | 🟡 | PASS（既存実装と互換） |
| 10 | test_tc010_name_unset_preserves_existing_name | TC-010 | 正常系 | 🔵 | PASS（既存実装と互換） |
| 11 | test_tc011_description_remove_then_set | TC-011 | 正常系 | 🔵 | **FAIL** ← 期待通り |
| 12 | test_tc012_color_remove_then_set | TC-012 | 正常系 | 🔵 | **FAIL** ← 期待通り |
| 13 | test_tc013_unset_is_not_none | TC-013 | 正常系 | 🔵 | **FAIL** ← 期待通り (ImportError) |
| 14 | test_tc014_not_found_with_sentinel_args | TC-014 | 異常系 | 🔵 | PASS（既存実装と互換） |
| 15 | test_tc015_description_none_on_deck_without_description | TC-015 | 異常系 | 🟡 | PASS（既存実装と互換） |
| 16 | test_tc016_remove_only_updates_updated_at | TC-016 | 境界値 | 🔵 | **FAIL** ← 期待通り |
| 17 | test_tc017_name_unset_description_set | TC-017 | 境界値 | 🔵 | PASS（既存実装と互換） |
| 18 | test_tc018_all_fields_set_backward_compat | TC-018 | 境界値 | 🔵 | PASS（既存実装と互換） |

**合計**: 18テスト作成、8件 FAIL（期待通り）、10件 PASS

---

## 期待される失敗内容

```
FAILED tests/unit/test_deck_service.py::TestUpdateDeckSentinelPattern::test_tc002_description_none_removes_attribute
  AssertionError: assert 'テスト用の説明' is None
  → deck.description が None にならない（既存実装は description=None を「変更なし」と扱う）

FAILED tests/unit/test_deck_service.py::TestUpdateDeckSentinelPattern::test_tc005_color_none_removes_attribute
  AssertionError: assert '#FF5733' is None
  → deck.color が None にならない（同上）

FAILED tests/unit/test_deck_service.py::TestUpdateDeckSentinelPattern::test_tc007_description_and_color_none_both_removed
  AssertionError: assert '削除される説明' is None
  → 両フィールドとも REMOVE されない

FAILED tests/unit/test_deck_service.py::TestUpdateDeckSentinelPattern::test_tc008_mixed_set_and_remove
  AssertionError: assert '削除される説明' is None
  → SET + REMOVE 混合パターンで REMOVE が動作しない

FAILED tests/unit/test_deck_service.py::TestUpdateDeckSentinelPattern::test_tc011_description_remove_then_set
  AssertionError: assert 'description' not in {..., 'description': '最初の説明', ...}
  → REMOVE が機能していないため、中間状態での確認が失敗

FAILED tests/unit/test_deck_service.py::TestUpdateDeckSentinelPattern::test_tc012_color_remove_then_set
  AssertionError: assert 'color' not in {..., 'color': '#FF0000', ...}
  → REMOVE が機能していないため、中間状態での確認が失敗

FAILED tests/unit/test_deck_service.py::TestUpdateDeckSentinelPattern::test_tc013_unset_is_not_none
  ImportError: cannot import name '_UNSET' from 'services.deck_service'
  → deck_service.py に _UNSET sentinel が定義されていない

FAILED tests/unit/test_deck_service.py::TestUpdateDeckSentinelPattern::test_tc016_remove_only_updates_updated_at
  AssertionError: assert None is not None
  → description=None が「変更なし」として扱われるため、update_item が呼ばれず updated_at も更新されない
```

---

## テストファイル

- **テストファイル**: `backend/tests/unit/test_deck_service.py`
- **テストクラス**: `TestUpdateDeckSentinelPattern`
- **テスト実行コマンド**: `cd backend && python -m pytest tests/unit/test_deck_service.py -v --tb=short`

---

## Green フェーズで実装すべき内容

### 1. `backend/src/services/deck_service.py` の変更

```python
# モジュールレベルに追加
_UNSET = object()

# update_deck メソッドのシグネチャ変更
def update_deck(
    self,
    user_id: str,
    deck_id: str,
    name=_UNSET,         # Optional[str] = None → _UNSET
    description=_UNSET,  # Optional[str] = None → _UNSET
    color=_UNSET,        # Optional[str] = None → _UNSET
) -> Deck:

# update_deck メソッド内の変更
# 変更前:
if description is not None:
    update_parts.append("description = :description")

# 変更後:
remove_parts = []
if description is None:     # 明示的 null → REMOVE
    remove_parts.append("description")
    deck.description = None
elif description is not _UNSET:  # 値 → SET
    update_parts.append("description = :description")
    expression_values[":description"] = description
    deck.description = description
# _UNSET → 変更なし（何もしない）

# color も同様のロジック

# UpdateExpression の構築変更
if update_parts:
    set_clause = "SET " + ", ".join(update_parts)
else:
    set_clause = ""

if remove_parts:
    remove_clause = "REMOVE " + ", ".join(remove_parts)
else:
    remove_clause = ""

if set_clause and remove_clause:
    update_expression = f"{set_clause} {remove_clause}"
elif set_clause:
    update_expression = set_clause
else:
    update_expression = remove_clause
```

### 2. `backend/src/api/handlers/decks_handler.py` の変更

```python
from services.deck_service import DeckService, DeckNotFoundError, DeckLimitExceededError, _UNSET

# update_deck ハンドラ内の変更
body = router.current_event.json_body

# JSON body の key 存在チェックで null/未送信を判別
update_kwargs = {}
if "name" in body:
    update_kwargs["name"] = body["name"]
if "description" in body:
    update_kwargs["description"] = body["description"]  # None または 文字列
if "color" in body:
    update_kwargs["color"] = body["color"]  # None または 文字列

deck = deck_service.update_deck(
    user_id=user_id,
    deck_id=deck_id,
    **update_kwargs
)
```

---

## 信頼性レベルサマリー

- **総テストケース数**: 18件
- 🔵 **青信号（高信頼）**: 16件 (89%)
- 🟡 **黄信号（妥当な推測）**: 2件 (11%)
- 🔴 **赤信号（推測）**: 0件 (0%)

**品質評価**: ✅ 高品質 - 元資料への高い準拠度

# TASK-0089: Sentinel パターン update_deck - Green フェーズ記録

**タスクID**: TASK-0089
**機能名**: sentinel-update-deck
**フェーズ**: Green（最小実装）
**実装日**: 2026-03-01

---

## 実装方針

Red フェーズで特定した 8 件の失敗を通すために以下の変更を実施した。

### 基本方針

`card_service.py` の `update_card` で `deck_id` フィールドに適用されている Sentinel パターンと同一の設計を `deck_service.py` の `update_deck` の `description` / `color` フィールドに適用する。

---

## 実装内容

### 1. `backend/src/services/deck_service.py`

#### 変更点 1: `_UNSET` sentinel 定数の追加

```python
# 【Sentinel 定数定義】: "未送信" と "明示的 null (None)" を区別するための sentinel 値
# 🔵 信頼性レベル: 青信号 - card_service.py と同一パターン (TASK-0085 参照)
_UNSET = object()
```

#### 変更点 2: `update_deck` シグネチャ変更

```python
def update_deck(
    self,
    user_id: str,
    deck_id: str,
    name=_UNSET,         # Optional[str] = None → _UNSET
    description=_UNSET,  # Optional[str] = None → _UNSET
    color=_UNSET,        # Optional[str] = None → _UNSET
) -> Deck:
```

#### 変更点 3: description / color の 3 状態処理ロジック

```python
# 【name 処理】: name は必須フィールドのため _UNSET（省略）→ 変更なし、値→ SET のみ
if name is not _UNSET:
    update_parts.append("#name = :name")
    expression_values[":name"] = name
    expression_names["#name"] = "name"
    deck.name = name

# 【description 処理】: Sentinel パターンで 3 状態を判定
if description is None:           # 明示的 null → REMOVE
    remove_parts.append("description")
    deck.description = None
elif description is not _UNSET:   # 値 → SET
    update_parts.append("description = :description")
    expression_values[":description"] = description
    deck.description = description
# description is _UNSET → 変更なし（何もしない）

# 【color 処理】: description と同一の Sentinel パターン
if color is None:                 # 明示的 null → REMOVE
    remove_parts.append("color")
    deck.color = None
elif color is not _UNSET:         # 値 → SET
    update_parts.append("color = :color")
    expression_values[":color"] = color
    deck.color = color
# color is _UNSET → 変更なし（何もしない）
```

#### 変更点 4: SET + REMOVE 組み合わせ UpdateExpression の構築

```python
update_expression = ""
if update_parts:
    update_expression += "SET " + ", ".join(update_parts)
if remove_parts:
    update_expression += " REMOVE " + ", ".join(remove_parts)
```

### 2. `backend/src/api/handlers/decks_handler.py`

#### 変更点: JSON body の key 存在チェックによる Sentinel 判別

```python
# Pydantic バリデーション（color フォーマット等）
body = router.current_event.json_body
UpdateDeckRequest(**body)  # バリデーションのみ（結果は使用しない）

# Sentinel パターン: key が存在する場合のみ渡す
update_kwargs = {}
if "name" in body:
    update_kwargs["name"] = body["name"]
if "description" in body:
    update_kwargs["description"] = body["description"]  # None または文字列
if "color" in body:
    update_kwargs["color"] = body["color"]  # None または文字列

deck = deck_service.update_deck(
    user_id=user_id,
    deck_id=deck_id,
    **update_kwargs,
)
```

---

## テスト実行結果

```
tests/unit/test_deck_service.py::TestUpdateDeckSentinelPattern - 18 tests

test_tc001_description_unset_no_change              PASSED
test_tc002_description_none_removes_attribute       PASSED  ← 修正対象（FAIL → PASS）
test_tc003_description_value_sets_attribute         PASSED
test_tc004_color_unset_no_change                    PASSED
test_tc005_color_none_removes_attribute             PASSED  ← 修正対象（FAIL → PASS）
test_tc006_color_value_sets_attribute               PASSED
test_tc007_description_and_color_none_both_removed  PASSED  ← 修正対象（FAIL → PASS）
test_tc008_mixed_set_and_remove                     PASSED  ← 修正対象（FAIL → PASS）
test_tc009_all_unset_returns_existing_deck          PASSED
test_tc010_name_unset_preserves_existing_name       PASSED
test_tc011_description_remove_then_set              PASSED  ← 修正対象（FAIL → PASS）
test_tc012_color_remove_then_set                    PASSED  ← 修正対象（FAIL → PASS）
test_tc013_unset_is_not_none                        PASSED  ← 修正対象（FAIL → PASS）
test_tc014_not_found_with_sentinel_args             PASSED
test_tc015_description_none_on_deck_without_description PASSED
test_tc016_remove_only_updates_updated_at           PASSED  ← 修正対象（FAIL → PASS）
test_tc017_name_unset_description_set               PASSED
test_tc018_all_fields_set_backward_compat           PASSED

18 passed
```

**全テスト（test_deck_service.py）**: 43 passed（既存テストへの影響なし）

---

## 品質判定

```
✅ 高品質:
- テスト結果: 18/18 PASS（Sentinel テスト）、43/43 PASS（全テスト）
- 実装品質: シンプルかつ動作する（card_service.py と同一パターン）
- リファクタ箇所: 明確（型アノテーション追加、Optional 型表記の整備）
- 機能的問題: なし
- コンパイルエラー: なし
- ファイルサイズ: deck_service.py=506行、decks_handler.py=182行（800行以下）
- モック使用: 実装コードにモック・スタブが含まれていない
```

---

## Refactor フェーズへの課題

1. **型アノテーション**: `name=_UNSET` などの引数に型アノテーションを追加（Union 型または `Any`）
2. **Docstring の更新**: `update_deck` の Args セクションを Sentinel パターンに合わせて整備
3. **handler の整理**: `UpdateDeckRequest` バリデーション結果を使わず body を直接参照している点の統合検討

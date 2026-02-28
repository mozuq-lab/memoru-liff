# TASK-0078: バックエンド interval更新サポート - Greenフェーズ記録

**機能名**: interval-adjust (バックエンド interval更新サポート)
**タスクID**: TASK-0078
**フェーズ**: Green（最小実装）
**実装日**: 2026-02-28

---

## 実装したコードの全文

### 1. `backend/src/models/card.py` - `UpdateCardRequest` に `interval` フィールドを追加

```python
class UpdateCardRequest(BaseModel):
    """Request model for updating a card."""

    front: Optional[str] = Field(None, min_length=1, max_length=1000)
    back: Optional[str] = Field(None, min_length=1, max_length=2000)
    deck_id: Optional[str] = None
    tags: Optional[List[str]] = None
    # 【フィールド追加】: interval フィールドを追加する
    # 【実装方針】: ge=1, le=365 の制約で復習間隔（日数）をバリデーションする
    # 【テスト対応】: TC-E01〜TC-E03（範囲外エラー）, TC-B01〜TC-B02（境界値）, TC-B04（None許容）
    # 🔵 信頼性レベル: 要件定義 REQ-101, REQ-102, architecture.md UpdateCardRequest拡張セクションより
    interval: Optional[int] = Field(None, ge=1, le=365)
```

### 2. `backend/src/services/card_service.py` - `update_card` メソッドに `interval` パラメータを追加

シグネチャ変更:

```python
def update_card(
    self,
    user_id: str,
    card_id: str,
    front: Optional[str] = None,
    back: Optional[str] = None,
    deck_id: Optional[str] = None,
    tags: Optional[List[str]] = None,
    interval: Optional[int] = None,  # 追加
) -> Card:
```

`tags` 処理の後に追加した interval 更新ロジック:

```python
# 【interval 更新処理】: interval が指定された場合に interval と next_review_at を更新する
# 【実装方針】: DynamoDB の予約語 interval を ExpressionAttributeNames でエスケープ
# 【next_review_at 再計算】: 現在日時 + interval 日 で再計算する（REQ-003）
# 【不変条件】: ease_factor, repetitions は更新しない（REQ-004）
# 【review_history 非記録】: update_card は復習操作ではないため、review_history に記録しない（REQ-403）
# 🔵 信頼性レベル: 要件定義 REQ-002〜004, REQ-402〜403, architecture.md 技術的制約セクションより
if interval is not None:
    # 【予約語エスケープ】: DynamoDB で "interval" は予約語のため #interval としてエスケープする
    update_parts.append("#interval = :interval")
    expression_values[":interval"] = interval
    expression_names["#interval"] = "interval"
    card.interval = interval

    # 【next_review_at 再計算】: 現在日時 + interval 日で next_review_at を計算する
    from datetime import timedelta
    next_review_at = datetime.now(timezone.utc) + timedelta(days=interval)
    update_parts.append("next_review_at = :next_review_at")
    expression_values[":next_review_at"] = next_review_at.isoformat()
    card.next_review_at = next_review_at
```

### 3. `backend/src/api/handler.py` - `card_service.update_card()` 呼び出しに `interval` を追加

```python
# 【interval パラメータ追加】: リクエストの interval をサービス層に渡す
# 【実装方針】: request.interval が None の場合は interval 関連フィールドを更新しない（後方互換性）
# 🔵 信頼性レベル: 要件定義 REQ-002, REQ-401, architecture.md handler拡張セクションより
card = card_service.update_card(
    user_id=user_id,
    card_id=card_id,
    front=request.front,
    back=request.back,
    deck_id=request.deck_id,
    tags=request.tags,
    interval=request.interval,  # 追加
)
```

### 4. テストコードの修正 - `backend/tests/unit/test_card_service_interval.py`

`update_review_data` のシグネチャに `quality` パラメータが存在しないため、テストのセットアップコードから `quality=` を除去した。

---

## 実装方針と判断理由

1. **UpdateCardRequest への `interval` フィールド追加**: Pydantic v2 の `Field(None, ge=1, le=365)` を使用。`ge=1` で最小値 1（翌日）、`le=365` で最大値 365（約1年）を制約。`Optional` にすることで後方互換性を維持。

2. **`update_card` の interval ロジック**: 既存の `update_parts` / `expression_values` / `expression_names` パターンに従って実装。DynamoDB の予約語エスケープ（`#interval`）は `update_review_data` で使用されているパターンをそのまま踏襲。

3. **`timedelta` のローカルインポート**: Refactorフェーズでファイル先頭へ移動予定。現時点では動作最優先のためローカルインポートとした。

4. **テストコードの `quality` パラメータ除去**: Redフェーズで作成されたテストの `update_review_data` 呼び出しで `quality=` が誤って指定されていた。実際のシグネチャに `quality` は存在しないため除去した。

---

## テスト実行結果

```
tests/unit/test_card_model_interval.py::TestUpdateCardRequestInterval::test_interval_1_is_valid PASSED
tests/unit/test_card_model_interval.py::TestUpdateCardRequestInterval::test_interval_365_is_valid PASSED
tests/unit/test_card_model_interval.py::TestUpdateCardRequestInterval::test_interval_7_is_valid PASSED
tests/unit/test_card_model_interval.py::TestUpdateCardRequestInterval::test_interval_none_is_valid PASSED
tests/unit/test_card_model_interval.py::TestUpdateCardRequestInterval::test_interval_only_none_explicit PASSED
tests/unit/test_card_model_interval.py::TestUpdateCardRequestInterval::test_interval_0_raises_validation_error PASSED
tests/unit/test_card_model_interval.py::TestUpdateCardRequestInterval::test_interval_minus_1_raises_validation_error PASSED
tests/unit/test_card_model_interval.py::TestUpdateCardRequestInterval::test_interval_366_raises_validation_error PASSED
tests/unit/test_card_model_interval.py::TestUpdateCardRequestInterval::test_interval_string_raises_validation_error PASSED
tests/unit/test_card_model_interval.py::TestUpdateCardRequestInterval::test_interval_float_with_fraction_raises_validation_error PASSED
tests/unit/test_card_model_interval.py::TestUpdateCardRequestInterval::test_interval_with_front_back_is_valid PASSED
tests/unit/test_card_service_interval.py::TestCardServiceUpdateInterval::test_update_card_interval_only PASSED
tests/unit/test_card_service_interval.py::TestCardServiceUpdateInterval::test_update_card_interval_ease_factor_unchanged PASSED
tests/unit/test_card_service_interval.py::TestCardServiceUpdateInterval::test_update_card_interval_repetitions_unchanged PASSED
tests/unit/test_card_service_interval.py::TestCardServiceUpdateInterval::test_update_card_interval_and_front_simultaneously PASSED
tests/unit/test_card_service_interval.py::TestCardServiceUpdateInterval::test_update_card_without_interval_does_not_change_interval PASSED
tests/unit/test_card_service_interval.py::TestCardServiceUpdateInterval::test_update_card_interval_not_recorded_in_review_history PASSED
tests/unit/test_card_service_interval.py::TestCardServiceUpdateInterval::test_update_card_interval_not_found_raises_error PASSED
tests/unit/test_card_service_interval.py::TestCardServiceUpdateInterval::test_update_card_interval_boundary_min PASSED
tests/unit/test_card_service_interval.py::TestCardServiceUpdateInterval::test_update_card_interval_boundary_max PASSED
tests/unit/test_card_service_interval.py::TestCardServiceUpdateInterval::test_update_card_interval_on_fresh_card PASSED
tests/unit/test_card_service_interval.py::TestCardServiceUpdateInterval::test_update_card_interval_next_review_at_format PASSED

============================== 22 passed in 1.03s ==============================
```

全22件通過。

---

## 課題・改善点（Refactorフェーズで対応）

1. **`timedelta` のローカルインポート**: `update_card` メソッド内でローカルインポートしているが、ファイル先頭の `from datetime import datetime, timezone` に `timedelta` を追加すべき
2. **日本語コメントの整理**: `update_card` メソッドのコメントを整理し、Docstring との重複を解消
3. **テストコードの `quality` パラメータ**: Redフェーズのテストコードに `quality=` が含まれていた。Refactorフェーズでテストコードのコメントに記録を残す

---

## 品質判定結果

```
✅ 高品質:
- テスト結果: 22/22 件全通過
- 実装品質: シンプルかつ動作する（既存パターンに従った最小変更）
- リファクタ箇所: timedelta ローカルインポートを先頭に移動
- 機能的問題: なし
- コンパイルエラー: なし
- ファイルサイズ: 800行以下
- モック使用: 実装コードにモック・スタブが含まれていない
```

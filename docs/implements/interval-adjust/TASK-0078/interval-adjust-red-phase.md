# TASK-0078: バックエンド interval更新サポート - Redフェーズ記録

**機能名**: interval-adjust (バックエンド interval更新サポート)
**タスクID**: TASK-0078
**フェーズ**: Red（失敗するテスト作成）
**作成日**: 2026-02-28

---

## 作成したテストケースの一覧

### ファイル1: `backend/tests/unit/test_card_model_interval.py`

**テストクラス**: `TestUpdateCardRequestInterval`

| テストID | テスト名 | 対応要件 | 信頼性 |
|---------|---------|---------|--------|
| TC-B01(モデル) | `test_interval_1_is_valid` | EDGE-101, TC-101-B01 | 🔵 |
| TC-B02(モデル) | `test_interval_365_is_valid` | EDGE-102, TC-102-B01 | 🔵 |
| TC-N01(モデル) | `test_interval_7_is_valid` | REQ-101, REQ-102 | 🔵 |
| TC-B04(モデル) | `test_interval_none_is_valid` | REQ-401, REQ-402 | 🔵 |
| TC-B04(明示) | `test_interval_only_none_explicit` | REQ-401, REQ-402 | 🔵 |
| TC-E01 | `test_interval_0_raises_validation_error` | REQ-101, TC-101-01 | 🔵 |
| TC-E02 | `test_interval_minus_1_raises_validation_error` | REQ-101, TC-101-02 | 🔵 |
| TC-E03 | `test_interval_366_raises_validation_error` | REQ-102, TC-102-01 | 🔵 |
| TC-E04 | `test_interval_string_raises_validation_error` | 型安全性 | 🟡 |
| TC-E05 | `test_interval_float_with_fraction_raises_validation_error` | 型安全性 | 🟡 |
| TC-N04(モデル) | `test_interval_with_front_back_is_valid` | architecture.md 技術的制約 | 🔵 |

### ファイル2: `backend/tests/unit/test_card_service_interval.py`

**テストクラス**: `TestCardServiceUpdateInterval`

| テストID | テスト名 | 対応要件 | 信頼性 |
|---------|---------|---------|--------|
| TC-N01 | `test_update_card_interval_only` | REQ-003, TC-003-01 | 🔵 |
| TC-N02 | `test_update_card_interval_ease_factor_unchanged` | REQ-004, TC-004-01 | 🔵 |
| TC-N03 | `test_update_card_interval_repetitions_unchanged` | REQ-004, TC-004-02 | 🔵 |
| TC-N04 | `test_update_card_interval_and_front_simultaneously` | architecture.md 技術的制約 | 🔵 |
| TC-N05 | `test_update_card_without_interval_does_not_change_interval` | REQ-401, REQ-402 | 🔵 |
| TC-N07 | `test_update_card_interval_not_recorded_in_review_history` | REQ-403 | 🟡 |
| TC-E06 | `test_update_card_interval_not_found_raises_error` | 既存パターン | 🔵 |
| TC-B01 | `test_update_card_interval_boundary_min` | EDGE-101, TC-003-02 | 🔵 |
| TC-B02 | `test_update_card_interval_boundary_max` | EDGE-102, TC-102-B01 | 🔵 |
| TC-B03 | `test_update_card_interval_on_fresh_card` | EDGE-103 | 🟡 |
| TC-N06 | `test_update_card_interval_next_review_at_format` | 技術的制約 | 🟡 |

**合計**: 22 テストケース

---

## テスト実行結果（Redフェーズ確認）

```
FAILED tests/unit/test_card_service_interval.py - 11 failed
FAILED tests/unit/test_card_model_interval.py - 11 failed
============================== 22 failed in 1.03s ==============================
```

### 失敗原因の分類

#### test_card_model_interval.py（11件全失敗）

**原因**: `UpdateCardRequest` に `interval` フィールドが存在しない

```
AttributeError: 'UpdateCardRequest' object has no attribute 'interval'
```

- `backend/src/models/card.py` の `UpdateCardRequest` クラスに `interval: Optional[int] = Field(None, ge=1, le=365)` が未追加

#### test_card_service_interval.py（11件全失敗）

**原因**: `CardService.update_card()` が `interval` パラメータを受け付けない

```
TypeError: CardService.update_card() got an unexpected keyword argument 'interval'
```

- `backend/src/services/card_service.py` の `update_card` メソッドのシグネチャに `interval: Optional[int] = None` が未追加
- interval 指定時の `next_review_at` 再計算ロジックが未実装

---

## テスト実行コマンド

```bash
# モデル層テスト（Pydantic バリデーション）
cd backend && python -m pytest tests/unit/test_card_model_interval.py -v

# サービス層テスト（update_card 拡張）
cd backend && python -m pytest tests/unit/test_card_service_interval.py -v

# 両テストファイルを同時実行
cd backend && python -m pytest tests/unit/test_card_model_interval.py tests/unit/test_card_service_interval.py -v

# 全テスト実行（既存テストとの整合性確認）
cd backend && make test
```

---

## Greenフェーズで実装すべき内容

### 1. UpdateCardRequest 拡張（backend/src/models/card.py）

```python
class UpdateCardRequest(BaseModel):
    front: Optional[str] = Field(None, min_length=1, max_length=1000)
    back: Optional[str] = Field(None, min_length=1, max_length=2000)
    deck_id: Optional[str] = None
    tags: Optional[List[str]] = None
    interval: Optional[int] = Field(None, ge=1, le=365)  # 追加
```

### 2. CardService.update_card 拡張（backend/src/services/card_service.py）

シグネチャに `interval: Optional[int] = None` を追加し、以下のロジックを実装:

```python
def update_card(self, user_id, card_id, front=None, back=None, deck_id=None, tags=None, interval=None):
    # ...既存ロジック...

    # interval 指定時の処理を追加
    if interval is not None:
        update_parts.append("#interval = :interval")
        expression_values[":interval"] = interval
        expression_names["#interval"] = "interval"  # DynamoDB 予約語エスケープ
        card.interval = interval

        # next_review_at を現在日時 + interval 日で再計算
        next_review_at = datetime.now(timezone.utc) + timedelta(days=interval)
        update_parts.append("next_review_at = :next_review_at")
        expression_values[":next_review_at"] = next_review_at.isoformat()
        card.next_review_at = next_review_at
```

### 3. handler.update_card 拡張（backend/src/api/handler.py）

`card_service.update_card()` 呼び出しに `interval=request.interval` を追加:

```python
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

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 17 | 77% |
| 🟡 黄信号 | 5 | 23% |
| 🔴 赤信号 | 0 | 0% |

**品質評価**: ✅ 高品質（青信号 77%、赤信号 0%）

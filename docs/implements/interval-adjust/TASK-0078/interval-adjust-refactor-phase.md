# TASK-0078: バックエンド interval更新サポート - Refactorフェーズ記録

**機能名**: interval-adjust (バックエンド interval更新サポート)
**タスクID**: TASK-0078
**フェーズ**: Refactor（品質改善）
**実施日**: 2026-02-28

---

## リファクタリング内容

### 改善1: `timedelta` のローカルインポートをファイル先頭へ移動 🔵

**対象ファイル**: `backend/src/services/card_service.py`

**改善前**:
```python
from datetime import datetime, timezone  # ファイル先頭

# update_card メソッド内
if interval is not None:
    from datetime import timedelta  # ← ローカルインポート（品質問題）
    next_review_at = datetime.now(timezone.utc) + timedelta(days=interval)
```

**改善後**:
```python
from datetime import datetime, timedelta, timezone  # ← ファイル先頭に追加

# update_card メソッド内
if interval is not None:
    next_review_at = datetime.now(timezone.utc) + timedelta(days=interval)  # ローカルインポート削除
```

**改善理由**:
- Greenフェーズで「動作優先」として残したローカルインポートを標準の位置へ移動
- Python のベストプラクティスに従い、すべてのインポートをファイル先頭にまとめる
- コードの可読性と一貫性を向上

**信頼性**: 🔵 青信号 - 既存コードの `from datetime import datetime, timezone` パターンに従った改善

---

### 改善2: `UpdateCardRequest.interval` フィールドのコメント整理と `description` 追加 🔵

**対象ファイル**: `backend/src/models/card.py`

**改善前**:
```python
    # 【フィールド追加】: interval フィールドを追加する
    # 【実装方針】: ge=1, le=365 の制約で復習間隔（日数）をバリデーションする
    # 【テスト対応】: TC-E01〜TC-E03（範囲外エラー）, TC-B01〜TC-B02（境界値）, TC-B04（None許容）
    # 🔵 信頼性レベル: 要件定義 REQ-101, REQ-102, architecture.md UpdateCardRequest拡張セクションより
    interval: Optional[int] = Field(None, ge=1, le=365)
```

**改善後**:
```python
    # 【interval フィールド】: 手動で復習間隔（日数）を設定するオプションフィールド
    # 【バリデーション】: ge=1（最小1日）, le=365（最大1年）の制約を適用
    # 【Optional の理由】: 未指定時は既存の interval/next_review_at を変更しない（後方互換性）
    # 🔵 信頼性レベル: 要件定義 REQ-101, REQ-102 より
    interval: Optional[int] = Field(None, ge=1, le=365, description="Review interval in days (1-365)")
```

**改善理由**:
- Greenフェーズで「実装工程の詳細」として記録されていたコメント（`テスト対応`, `フィールド追加`）を削除
- 本番コードとして読まれる際に意味のある情報（目的・制約の理由）に置き換え
- 他フィールドの `description` パターン（例: `front: Field(..., description="Front side text")`）と統一
- API ドキュメント生成（OpenAPI）でも説明が表示されるよう `description` を追加

**信頼性**: 🔵 青信号 - 既存フィールドの `description` パターンに従った改善

---

### 改善3: `update_card` メソッドの docstring 整理 🟡

**対象ファイル**: `backend/src/services/card_service.py`

**改善前**:
```python
        Raises:
            CardNotFoundError: If card does not exist.

        【実装方針】: interval パラメータを追加し、指定時に next_review_at を自動再計算する
        【テスト対応】: TC-N01〜TC-N07, TC-B01〜TC-B03, TC-E06 に対応
        🔵 信頼性レベル: 要件定義 REQ-002〜004, REQ-401〜403, architecture.md より
```

**改善後**:
```python
        Raises:
            CardNotFoundError: If card does not exist.

        【interval 指定時の動作】:
          - interval と next_review_at を同一 UpdateExpression でまとめて更新する
          - next_review_at = 現在日時 (UTC) + interval 日 で自動再計算する
          - ease_factor, repetitions は変更しない（REQ-004）
          - review_history には記録しない（復習操作ではないため。REQ-403）
        🔵 信頼性レベル: 要件定義 REQ-002〜004, REQ-401〜403, architecture.md より
```

**改善理由**:
- `【実装方針】` は実装の経緯を記録するコメントであり、docstring として不適切
- `【テスト対応】` はテストファイルに記録すべき情報であり、実装 docstring には不要
- `【interval 指定時の動作】` として、メソッドの動作仕様（不変条件・副作用）を明確に記述
- メソッドを初めて読む開発者が `interval` の仕様を理解しやすい構造に変更

**信頼性**: 🟡 黄信号 - docstring の書き方は慣例に基づく判断

---

## セキュリティレビュー結果

| 観点 | 評価 | 詳細 |
|------|------|------|
| 入力値検証 | ✅ | Pydantic v2 の `ge=1, le=365` で不正値を早期拒否 |
| 認証・認可 | ✅ | handler.py での JWT 認証（変更なし）+ `get_card()` によるオーナーチェック |
| 予約語エスケープ | ✅ | DynamoDB の `interval` 予約語を `#interval` でエスケープ |
| データ漏洩リスク | ✅ | interval 更新は他ユーザーのデータに影響しない（user_id でスコープ制限） |
| 重大な脆弱性 | ✅ なし | - |

---

## パフォーマンスレビュー結果

| 観点 | 評価 | 詳細 |
|------|------|------|
| 計算量 | ✅ O(1) | 単一 `table.update_item()` 操作（`update_review_data` と同等） |
| DB アクセス数 | ✅ 2回 | `get_card()` (存在確認) + `update_item()` (更新) |
| timedelta 計算 | ✅ | 単純な日付演算、パフォーマンス影響なし |
| メモリ使用 | ✅ | 追加のメモリ使用なし |
| 重大な性能課題 | ✅ なし | - |

---

## テスト実行結果（リファクタリング後）

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

============================== 22 passed in 0.95s ==============================
```

全22件通過。

---

## 改善されたコードの全文

### `backend/src/services/card_service.py` (変更部分)

```python
# ファイル先頭インポート（改善後）
from datetime import datetime, timedelta, timezone  # timedelta を追加

# update_card メソッド docstring（改善後）
        【interval 指定時の動作】:
          - interval と next_review_at を同一 UpdateExpression でまとめて更新する
          - next_review_at = 現在日時 (UTC) + interval 日 で自動再計算する
          - ease_factor, repetitions は変更しない（REQ-004）
          - review_history には記録しない（復習操作ではないため。REQ-403）

# interval 更新ロジック（ローカルインポート削除後）
        if interval is not None:
            # 【予約語エスケープ】: DynamoDB で "interval" は予約語のため #interval としてエスケープする
            update_parts.append("#interval = :interval")
            expression_values[":interval"] = interval
            expression_names["#interval"] = "interval"
            card.interval = interval

            # 【next_review_at 再計算】: 現在日時 + interval 日で next_review_at を計算する
            next_review_at = datetime.now(timezone.utc) + timedelta(days=interval)  # ← ローカルインポート削除
            update_parts.append("next_review_at = :next_review_at")
            expression_values[":next_review_at"] = next_review_at.isoformat()
            card.next_review_at = next_review_at
```

### `backend/src/models/card.py` (変更部分)

```python
class UpdateCardRequest(BaseModel):
    """Request model for updating a card."""

    front: Optional[str] = Field(None, min_length=1, max_length=1000)
    back: Optional[str] = Field(None, min_length=1, max_length=2000)
    deck_id: Optional[str] = None
    tags: Optional[List[str]] = None
    # 【interval フィールド】: 手動で復習間隔（日数）を設定するオプションフィールド
    # 【バリデーション】: ge=1（最小1日）, le=365（最大1年）の制約を適用
    # 【Optional の理由】: 未指定時は既存の interval/next_review_at を変更しない（後方互換性）
    # 🔵 信頼性レベル: 要件定義 REQ-101, REQ-102 より
    interval: Optional[int] = Field(None, ge=1, le=365, description="Review interval in days (1-365)")
```

---

## 品質判定結果

```
✅ 高品質:
- テスト結果: 22/22 件全通過（リファクタリング後）
- セキュリティ: 重大な脆弱性なし（入力検証・認証・エスケープ）
- パフォーマンス: 重大な性能課題なし（O(1) 単一 update_item 操作）
- リファクタ品質: 全3件の改善目標を達成
- コード品質: ローカルインポート解消・コメント整理・description 統一
- ドキュメント: refactor-phase.md 作成、memo.md 更新
```

---

## 信頼性レベルサマリー

| 改善項目 | 信頼性 | 根拠 |
|---------|--------|------|
| timedelta ローカルインポート移動 | 🔵 | 既存コードのインポートパターンに従う |
| description 追加 | 🔵 | 既存フィールドの description パターンに統一 |
| docstring 整理 | 🟡 | docstring の書き方は慣例に基づく判断 |

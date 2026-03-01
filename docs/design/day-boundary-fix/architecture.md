# day-boundary-fix アーキテクチャ設計

**作成日**: 2026-03-01
**関連要件定義**: [requirements.md](../../spec/day-boundary-fix/requirements.md)
**元設計文書**: [day-boundary architecture.md](../day-boundary/architecture.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: コードレビュー指摘・既存実装・要件定義書を参考にした確実な設計
- 🟡 **黄信号**: 既存実装・設計パターンから妥当な推測による設計

---

## システム概要 🔵

コードレビュー（Claude + Codex）で発見された `day-boundary` 機能のバグ修正と品質改善。既存のアーキテクチャ・データフローは変更せず、防御的プログラミングの追加とバリデーション強化のみを行う。

## 設計方針 🔵

**既存コードの内部修正のみ**: インターフェース（引数名・戻り値型）は変更せず、関数内部のバリデーション・型変換・エラーハンドリングを追加する。

- **変更箇所**: srs.py（型変換・フォールバック）、user.py（TZ検証）、テストファイル
- **変更しない箇所**: API ハンドラー、サービス層のインターフェース、フロントエンド

## 変更対象レイヤー

```
変更レイヤー:
┌─────────────────────────────────────────────────┐
│  Service: srs.py                                 │ ← Decimal→int変換、TZフォールバック、import移動
├─────────────────────────────────────────────────┤
│  Model: user.py                                  │ ← TZ実在検証、デフォルトsettings修正
├─────────────────────────────────────────────────┤
│  Tests: test_srs.py                              │ ← Decimal/不正TZテスト追加
│         test_review_service.py                   │ ← 弱いアサーション修正
│         test_user_models.py                      │ ← TZバリデーションテスト追加
├─────────────────────────────────────────────────┤
│  Docs: interview-record.md                       │ ← 選択肢範囲の不整合修正
└─────────────────────────────────────────────────┘

変更なし:
┌─────────────────────────────────────────────────┐
│  API Handler: review_handler.py                  │ ← インターフェース不変
│              cards_handler.py                    │ ← インターフェース不変
│              user_handler.py                     │ ← インターフェース不変
│  Service: review_service.py                      │ ← インターフェース不変
│          card_service.py                         │ ← インターフェース不変
│          user_service.py                         │ ← インターフェース不変
│  Frontend: SettingsPage.tsx                      │ ← 変更なし
│           types/user.ts                          │ ← 変更なし
└─────────────────────────────────────────────────┘
```

## コンポーネント設計

### 1. `calculate_next_review_boundary()` 防御実装 🔵

**ファイル**: `backend/src/services/srs.py`
**関連要件**: REQ-001, REQ-003, REQ-101

**変更内容**:

```python
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # REQ-101: モジュールレベルに移動

logger = Logger()  # フォールバックログ用

def calculate_next_review_boundary(
    interval: int,
    user_timezone: str = "Asia/Tokyo",
    day_start_hour: int = 4,
) -> datetime:
    # REQ-001: DynamoDB Decimal → int 変換
    interval = int(interval)
    day_start_hour = int(day_start_hour)
    if not 0 <= day_start_hour <= 23:
        raise ValueError(f"day_start_hour must be 0-23, got {day_start_hour}")

    # REQ-003: ZoneInfo フォールバック
    try:
        user_tz = ZoneInfo(user_timezone)
    except (ZoneInfoNotFoundError, KeyError):
        logger.warning(f"Invalid timezone '{user_timezone}', falling back to Asia/Tokyo")
        user_tz = ZoneInfo("Asia/Tokyo")

    # ... 以降の正規化ロジックは変更なし
```

**信頼性**: 🔵 *コードレビュー指摘 #1, #3, #7 の推奨修正*

### 2. `UserSettingsRequest.validate_timezone()` ZoneInfo 検証 🔵

**ファイル**: `backend/src/models/user.py`
**関連要件**: REQ-002

**変更内容**: 既存の正規表現バリデーションを `ZoneInfo` 実在検証に置き換える。

```python
@field_validator("timezone")
@classmethod
def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
    """Validate IANA timezone string using ZoneInfo."""
    if v is None:
        return v
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        ZoneInfo(v)
    except (ZoneInfoNotFoundError, KeyError):
        raise ValueError(f"Invalid timezone: {v}")
    return v
```

**設計判断**:
- 既存の正規表現チェック（`^[A-Za-z_]+/[A-Za-z_]+$`）を完全に置き換える
- `ZoneInfo` は Python 3.9+ 標準ライブラリで追加依存なし
- `ZoneInfoNotFoundError` と `KeyError` の両方を catch（Python バージョン差異への対応）

**信頼性**: 🔵 *コードレビュー指摘 #2 の推奨修正*

### 3. `User.from_dynamodb_item()` デフォルト settings 修正 🟡

**ファイル**: `backend/src/models/user.py`
**関連要件**: REQ-102

**変更内容**: デフォルト settings に `day_start_hour` を追加。

```python
@classmethod
def from_dynamodb_item(cls, item: dict) -> "User":
    return cls(
        ...
        settings=item.get("settings", {
            "notification_time": "09:00",
            "timezone": "Asia/Tokyo",
            "day_start_hour": 4,  # 追加
        }),
        ...
    )
```

**信頼性**: 🟡 *コードレビュー指摘 #8。一貫性のための改善*

### 4. テスト修正・追加 🔵

**ファイル**: `backend/tests/unit/test_srs.py`
**関連要件**: REQ-103

追加テストケース:
- `test_decimal_day_start_hour`: `Decimal(4)` を渡しても正常動作
- `test_decimal_boundary_values`: `Decimal(0)` / `Decimal(23)` の境界値
- `test_invalid_day_start_hour_range`: `Decimal(24)` / `Decimal(-1)` で `ValueError`
- `test_invalid_timezone_fallback`: 不正 TZ でフォールバック動作
- `test_fallback_produces_valid_result`: フォールバック時の結果が正しい

**ファイル**: `backend/tests/unit/test_review_service.py`
**関連要件**: REQ-004

修正:
- `test_next_review_at_normalized_to_day_boundary`: `assert A or B` → 単一期待値に固定

**ファイル**: `backend/tests/unit/test_user_models.py`
**関連要件**: REQ-103

追加テストケース:
- `test_invalid_timezone_non_existent`: 非実在 TZ `"Foo/Bar"` の拒否
- `test_valid_timezone_zoneinfo`: `"Asia/Tokyo"`, `"UTC"` の受け入れ

**信頼性**: 🔵 *コードレビュー指摘 #1, #2, #4 に対応するテスト*

### 5. ドキュメント修正 🔵

**ファイル**: `docs/spec/day-boundary/interview-record.md`
**関連要件**: REQ-005

Q4 の回答を修正:
- 修正前: 「0時〜6時（推奨）を選択。7つの選択肢。」
- 修正後: 「0時〜23時（24個）、ドロップダウン形式。夜勤など多様な生活リズムに対応するため全時間帯を選択可能とした。」

**信頼性**: 🔵 *実装仕様・requirements.md REQ-003 との整合*

## 技術的制約 🔵

- `zoneinfo` は Python 3.9+ 標準ライブラリ（追加依存なし）
- DynamoDB は Number 型を `Decimal` として返す（boto3 の仕様）
- moto テストでは `Decimal` ではなく `int` が返るため、`Decimal` テストは明示的に値を渡す必要がある
- `aws_lambda_powertools.Logger` は既にインポート済み（srs.py に追加が必要）

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/day-boundary-fix/requirements.md)
- **コードレビュー結果**: [CODE_REVIEW_day-boundary.md](../../reviews/CODE_REVIEW_day-boundary.md)
- **元設計文書**: [day-boundary architecture.md](../day-boundary/architecture.md)

## 信頼性レベルサマリー

- 🔵 青信号: 8件 (89%)
- 🟡 黄信号: 1件 (11%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: ✅ 高品質

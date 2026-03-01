# day-boundary アーキテクチャ設計

**作成日**: 2026-03-01
**関連要件定義**: [requirements.md](../../spec/day-boundary/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・既存実装・ユーザヒアリングを参考にした確実な設計
- 🟡 **黄信号**: 既存実装・設計パターンから妥当な推測による設計

---

## システム概要 🔵

復習カードの `next_review_at` を書き込み時にユーザーの日付境界時刻に正規化する。既存のクエリロジック (`next_review_at <= now`) は変更せず、正規化のみで復習カードの表示タイミングを制御する。

## 設計方針 🔵

**書き込み時正規化**: `next_review_at` の保存時にユーザーの `timezone` と `day_start_hour` を使って正規化する。クエリ側の変更は不要。

- **変更箇所**: SRS 正規化関数追加 + レビュー/カード保存フロー + ユーザー設定
- **変更しない箇所**: `calculate_sm2()` アルゴリズム本体、DynamoDB クエリロジック、GSI 構成

## 変更対象レイヤー

```
変更レイヤー:
┌─────────────────────────────────────────────────┐
│  Frontend: SettingsPage.tsx / types/user.ts      │ ← 設定 UI 追加
├─────────────────────────────────────────────────┤
│  API Handler: review_handler.py                  │ ← UserService 注入
│              cards_handler.py                    │ ← 正規化パラメータ追加
│              user_handler.py                     │ ← day_start_hour 受付
├─────────────────────────────────────────────────┤
│  Service: srs.py                                 │ ← 正規化関数追加
│          review_service.py                       │ ← 正規化呼び出し
│          card_service.py                         │ ← interval更新時正規化
│          user_service.py                         │ ← day_start_hour 保存
├─────────────────────────────────────────────────┤
│  Model: user.py                                  │ ← day_start_hour 追加
├─────────────────────────────────────────────────┤
│  DynamoDB: UsersTable (settings map)             │ ← フィールド追加のみ
│           CardsTable (next_review_at)             │ ← 値の内容が変化
└─────────────────────────────────────────────────┘

変更なし:
┌─────────────────────────────────────────────────┐
│  Service: deck_service.py                        │ ← クエリロジック不変
│  DynamoDB: user_id-due-index (GSI)               │ ← 構成不変
│  Service: srs.py calculate_sm2()                 │ ← アルゴリズム不変
└─────────────────────────────────────────────────┘
```

## コンポーネント設計

### 1. SRS 正規化関数 🔵

**ファイル**: `backend/src/services/srs.py`

新関数 `calculate_next_review_boundary()` を追加。`calculate_sm2()` は変更しない。

```python
def calculate_next_review_boundary(
    interval: int,
    user_timezone: str = "Asia/Tokyo",
    day_start_hour: int = 4,
) -> datetime:
    """Calculate next_review_at normalized to user's day boundary.

    Args:
        interval: Days until next review (from SM-2 calculation).
        user_timezone: User's IANA timezone string.
        day_start_hour: Hour when user's "day" starts (0-23).

    Returns:
        UTC datetime set to the day boundary time.
    """
    from zoneinfo import ZoneInfo

    user_tz = ZoneInfo(user_timezone)
    now_utc = datetime.now(timezone.utc)
    local_now = now_utc.astimezone(user_tz)

    # 有効日付: 境界時刻前なら前日扱い
    effective_date = local_now.date()
    if local_now.hour < day_start_hour:
        effective_date -= timedelta(days=1)

    # interval 日後の境界時刻
    target_date = effective_date + timedelta(days=interval)
    boundary = datetime(
        target_date.year, target_date.month, target_date.day,
        day_start_hour, 0, 0, tzinfo=user_tz,
    )
    return boundary.astimezone(timezone.utc)
```

**信頼性**: 🔵 *REQ-001 正規化ロジックより*

### 2. ユーザー設定拡張 🔵

**ファイル**: `backend/src/models/user.py`

| 変更箇所 | 内容 |
|---------|------|
| `UserSettingsRequest` | `day_start_hour: Optional[int]` 追加（0-23, バリデーション） |
| `UserResponse` | `day_start_hour: int = 4` 追加 |
| `User.settings` デフォルト | `"day_start_hour": 4` 追加 |
| `User.to_response()` | `day_start_hour` フィールド追加 |

**ファイル**: `backend/src/services/user_service.py`

`update_settings()` に `day_start_hour` パラメータ追加。既存の `notification_time` / `timezone` と同じパターンで DynamoDB 更新。

**信頼性**: 🔵 *既存 settings パターンの踏襲。REQ-002 より*

### 3. レビューフロー変更 🔵

**ファイル**: `backend/src/api/handlers/review_handler.py`

`submit_review()` ハンドラーで:
1. `UserService` をインポート・インスタンス化（`cards_handler.py` と同じパターン）
2. `user_service.get_or_create_user(user_id)` でユーザー設定を取得
3. `timezone` と `day_start_hour` を `review_service.submit_review()` に渡す

**ファイル**: `backend/src/services/review_service.py`

`submit_review()` に `user_timezone`, `day_start_hour` パラメータ追加:
1. `calculate_sm2()` でアルゴリズム計算（変更なし）
2. `calculate_next_review_boundary(result.interval, user_timezone, day_start_hour)` で正規化
3. 正規化済み `next_review_at` を使ってカード更新

**信頼性**: 🔵 *REQ-001、REQ-403 より*

### 4. カード interval 更新フロー変更 🟡

**ファイル**: `backend/src/services/card_service.py`

`update_card()` に `user_timezone`, `day_start_hour` オプショナルパラメータ追加。interval 更新時のみ正規化を適用。

**ファイル**: `backend/src/api/handlers/cards_handler.py`

`update_card()` ハンドラーで interval が指定されている場合:
1. `user_service.get_or_create_user(user_id)` でユーザー設定を取得（`user_service` は既にインポート済み）
2. `timezone` と `day_start_hour` を `card_service.update_card()` に渡す

**信頼性**: 🟡 *REQ-004 より。REQ-001 との一貫性*

### 5. フロントエンド設定 UI 🔵

**ファイル**: `frontend/src/types/user.ts`

```typescript
export interface User {
  // 既存フィールド...
  day_start_hour: number;  // 追加
}

export interface UpdateUserRequest {
  // 既存フィールド...
  day_start_hour?: number;  // 追加
}
```

**ファイル**: `frontend/src/pages/SettingsPage.tsx`

既存の「通知設定」セクションに「日付切り替え時刻」サブセクションを追加:
- 0時〜23時の24個のドロップダウン（select 要素）
- 状態管理: `selectedDayStartHour` (useState)
- `hasChanges` 判定に `day_start_hour` を含める
- 保存時に `day_start_hour` を `updateUser()` に含める

**信頼性**: 🔵 *REQ-003、既存 SettingsPage パターンより*

### 6. ユーザー設定 API ハンドラー 🔵

**ファイル**: `backend/src/api/handlers/user_handler.py`

`update_settings()` の呼び出しに `day_start_hour=request.day_start_hour` を追加。

**信頼性**: 🔵 *既存パターンの踏襲*

## 技術的制約 🔵

- DynamoDB の GSI `user_id-due-index` の構成変更は不要
- `next_review_at` の ISO 文字列形式は変更なし（正規化後も同じ形式）
- `zoneinfo.ZoneInfo` は Python 3.9+ 標準ライブラリ（追加依存なし）
- レビュー送信時に DynamoDB GetItem が1回追加（ユーザー設定取得）

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/day-boundary/requirements.md)

## 信頼性レベルサマリー

- 🔵 青信号: 10件 (91%)
- 🟡 黄信号: 1件 (9%)
- 🔴 赤信号: 0件 (0%)

**品質評価**: 高品質

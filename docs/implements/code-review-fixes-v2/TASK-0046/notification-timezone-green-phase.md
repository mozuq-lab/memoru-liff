# TDD Greenフェーズ記録: 通知時刻/タイムゾーン判定

**タスクID**: TASK-0046
**要件名**: code-review-fixes-v2
**機能名**: 通知時刻/タイムゾーン判定 (notification-timezone)
**Greenフェーズ実施日**: 2026-02-21
**TDDフェーズ**: Green（最小実装完了）

---

## 1. 実装内容

### 1.1 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---------|---------|------|
| `backend/src/services/notification_service.py` | 修正 | `should_notify` メソッド追加 + `process_notifications` へ統合 |
| `backend/tests/unit/test_notification_service.py` | 修正 | 既存テストの `current_time` を新仕様に合わせて更新 |

---

### 1.2 notification_service.py の実装コード

**追加インポート**:

```python
from datetime import datetime, timezone
# 【インポート追加】: タイムゾーン変換に Python 3.9+ 標準ライブラリの zoneinfo を使用 🔵
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
```

**should_notify メソッド** (L49-L95):

```python
def should_notify(self, user, current_utc: datetime) -> bool:
    """
    【機能概要】: ユーザーのローカル時刻が notification_time と一致するかを判定する
    【実装方針】: settings 辞書から timezone と notification_time を取得し、UTC→ローカル変換後に ±5分精度で比較する
    【テスト対応】: TC-001〜TC-008, TC-011〜TC-018 を通すための最小実装
    🔵 REQ-V2-041, REQ-V2-042, NFR-V2-301: タイムゾーン考慮 + 時刻一致判定 + ±5分精度
    """
    # 【タイムゾーン取得】: settings 辞書から timezone を取得。なければ Asia/Tokyo をデフォルトとして使用 🔵
    tz_name = user.settings.get("timezone", "Asia/Tokyo") if user.settings else "Asia/Tokyo"

    # 【タイムゾーン変換準備】: ZoneInfo でタイムゾーンオブジェクトを生成。無効な名前は Asia/Tokyo にフォールバック 🟡
    try:
        user_tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, Exception):
        logger.warning(f"Invalid timezone '{tz_name}', falling back to Asia/Tokyo")
        user_tz = ZoneInfo("Asia/Tokyo")

    # 【UTC→ローカル変換】: ユーザーのローカル時刻を計算する 🔵
    local_time = current_utc.astimezone(user_tz)

    # 【notification_time 取得】: settings 辞書から通知時刻を取得。なければ '09:00' をデフォルトとして使用 🟡
    notification_time = user.settings.get("notification_time", "09:00") if user.settings else "09:00"

    # 【時刻パース】: HH:MM 形式の文字列を時・分に変換する 🔵
    notif_hour, notif_min = map(int, notification_time.split(":"))
    local_hour, local_min = local_time.hour, local_time.minute

    # 【分単位変換】: 比較のために時・分を合計分数に変換する 🔵
    notif_total_min = notif_hour * 60 + notif_min
    local_total_min = local_hour * 60 + local_min

    # 【差分計算】: 絶対値差分を計算する 🔵
    diff = abs(local_total_min - notif_total_min)

    # 【日付境界補正】: 23:58 と 00:02 のように日付をまたぐ場合の差分を補正する 🟡
    # 差分が 12時間（720分）を超える場合、24時間から引くことで正しい差分を得る
    if diff > 720:
        diff = 1440 - diff

    # 【判定】: EventBridge の 5分実行間隔に合わせて ±5分以内なら通知対象とする 🔵
    return diff <= 5
```

**process_notifications 追加部分** (L134-L143):

```python
# 【タイムゾーン考慮の時刻一致チェック】: ユーザーのローカル時刻が notification_time と一致するか判定 🔵
# REQ-V2-041: タイムゾーンを考慮して通知時刻が一致するユーザーにのみ通知を送信する
if not self.should_notify(user, current_time):
    logger.debug(
        f"User {user.user_id} notification time does not match "
        f"(tz={user.settings.get('timezone', 'Asia/Tokyo') if user.settings else 'Asia/Tokyo'}, "
        f"notification_time={user.settings.get('notification_time', '09:00') if user.settings else '09:00'})"
    )
    result.skipped += 1
    continue
```

---

## 2. 実装方針と判断理由

### 2.1 settings 辞書からのアクセス

User モデルは `settings` 辞書に `timezone` と `notification_time` を格納しているため、
`user.settings.get("timezone", "Asia/Tokyo")` でアクセスする方式を採用。

- `settings` が `None` または空の場合の防御的処理も実装 (`if user.settings else "Asia/Tokyo"`)

### 2.2 zoneinfo の選択

Python 3.9+ 標準ライブラリの `zoneinfo` を使用（Lambda Python 3.12 で利用可能）。
外部ライブラリ（pytz 等）への依存を避けた。

### 2.3 無効タイムゾーンのフォールバック

`ZoneInfoNotFoundError` を含む Exception を try-except で捕捉し、
Asia/Tokyo にフォールバックすることで処理を継続させる。

### 2.4 既存テストの修正

既存の `test_notification_service.py` は `should_notify` がない前提で
UTC 09:00 を `current_time` として使用していた。

新仕様（JST デフォルト、notification_time='09:00'）では
UTC 09:00 = JST 18:00 となり `should_notify` が False を返す。

仕様として正しい TASK-0046 の要件に合わせて、
既存テストの `current_time` を UTC 00:00（= JST 09:00）に修正した。

---

## 3. テスト実行結果

### 3.1 TASK-0046 対象テスト（17件）

```
tests/unit/test_notification_timezone.py - 17 passed in 1.16s
```

全 17件 PASS。

### 3.2 全テストスイート（251件）

```
251 passed in 8.65s
```

既存テスト含め全 251件 PASS。

---

## 4. 品質評価

| 評価項目 | 結果 |
|---------|------|
| テスト結果 | ✅ 17件全て PASS |
| 全体テスト | ✅ 251件全て PASS |
| 実装品質 | ✅ シンプルで理解しやすい |
| ファイルサイズ | ✅ 191行（800行制限内）|
| モック使用 | ✅ 実装コードにモック・スタブなし |
| 信頼性分布 | 🔵 主に青信号（要件定義書に明記） |

**品質判定**: ✅ 高品質

---

## 5. 課題・改善点（Refactorフェーズ対応候補）

1. **settings アクセスの重複**: `user.settings.get(...)` が `should_notify` 内と `process_notifications` のログ部分で重複している → ヘルパープロパティまたは取得ロジックの分離を検討
2. **型ヒントの追加**: `user` パラメータの型が `User` ではなく `Any` 扱いになっている → `from src.models.user import User` を追加して適切な型ヒントを付ける
3. **エラーハンドリングの統一**: `except (ZoneInfoNotFoundError, Exception)` は `ZoneInfoNotFoundError` が `Exception` のサブクラスなので単純に `except Exception` に変更可能

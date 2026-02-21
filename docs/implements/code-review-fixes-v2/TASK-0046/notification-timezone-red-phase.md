# TDD Redフェーズ記録: 通知時刻/タイムゾーン判定

**タスクID**: TASK-0046
**要件名**: code-review-fixes-v2
**機能名**: 通知時刻/タイムゾーン判定 (notification-timezone)
**Redフェーズ実施日**: 2026-02-21
**TDDフェーズ**: Red（失敗テスト作成完了）

---

## 1. 作成したテストケース一覧

| テストID | クラス | テスト名 | 信頼性 | 分類 | 失敗原因 |
|---------|--------|----------|--------|------|---------|
| TC-001 | `TestShouldNotifyBasic` | `test_tc001_should_notify_matches_notification_time_japan` | 🔵 | 正常系 | `AttributeError: 'NotificationService' object has no attribute 'should_notify'` |
| TC-002 | `TestShouldNotifyBasic` | `test_tc002_should_notify_no_match_different_time` | 🔵 | 正常系 | 同上 |
| TC-003 | `TestShouldNotifyBasic` | `test_tc003_should_notify_within_five_minute_tolerance` | 🔵 | 正常系 | 同上 |
| TC-004 | `TestShouldNotifyBasic` | `test_tc004_should_notify_different_timezone_new_york` | 🔵 | 正常系 | 同上 |
| TC-011 | `TestShouldNotifyBasic` | `test_tc011_should_notify_outside_tolerance_six_minutes` | 🔵 | 境界値 | 同上 |
| TC-012 | `TestShouldNotifyBasic` | `test_tc012_should_notify_default_timezone_when_missing` | 🟡 | 境界値 | 同上 |
| TC-014 | `TestShouldNotifyBasic` | `test_tc014_should_notify_date_boundary_crossing` | 🟡 | 境界値 | 同上 |
| TC-005 | `TestProcessNotificationsWithShouldNotify` | `test_tc005_process_notifications_filters_by_should_notify` | 🔵 | 統合 | `should_notify` 未実装 + `process_notifications` に時刻判定なし |
| TC-005b | `TestProcessNotificationsWithShouldNotify` | `test_tc005b_process_notifications_notifies_matching_user_utc_offset` | 🔵 | 統合 | 同上 |
| TC-006 | `TestShouldNotifyEdgeCases` | `test_tc006_should_notify_exactly_five_minutes_before` | 🟡 | 境界値 | `AttributeError: 'NotificationService' object has no attribute 'should_notify'` |
| TC-007 | `TestShouldNotifyEdgeCases` | `test_tc007_should_notify_utc_timezone` | 🟡 | 正常系 | 同上 |
| TC-013 | `TestShouldNotifyEdgeCases` | `test_tc013_should_notify_default_notification_time_when_missing` | 🟡 | 境界値 | 同上 |
| TC-015 | `TestShouldNotifyEdgeCases` | `test_tc015_should_notify_date_boundary_outside_tolerance` | 🟡 | 境界値 | 同上 |
| TC-016 | `TestShouldNotifyEdgeCases` | `test_tc016_should_notify_midnight_notification_time` | 🟡 | 境界値 | 同上 |
| TC-017 | `TestShouldNotifyEdgeCases` | `test_tc017_should_notify_late_night_notification_time` | 🟡 | 境界値 | 同上 |
| TC-018 | `TestShouldNotifyEdgeCases` | `test_tc018_should_notify_empty_settings_uses_defaults` | 🟡 | 境界値 | 同上 |
| TC-008 | `TestShouldNotifyErrorCases` | `test_tc008_should_notify_invalid_timezone_falls_back_to_default` | 🟡 | 異常系 | 同上 |

**合計**: 17件 / 17件失敗（100% FAIL 確認済み）

---

## 2. テスト実行結果

```
============================= test session starts ==============================
platform darwin -- Python 3.13.5, pytest-8.3.5, pluggy-1.5.0
collected 17 items

tests/unit/test_notification_timezone.py::TestShouldNotifyBasic::test_tc001_should_notify_matches_notification_time_japan FAILED
tests/unit/test_notification_timezone.py::TestShouldNotifyBasic::test_tc002_should_notify_no_match_different_time FAILED
tests/unit/test_notification_timezone.py::TestShouldNotifyBasic::test_tc003_should_notify_within_five_minute_tolerance FAILED
tests/unit/test_notification_timezone.py::TestShouldNotifyBasic::test_tc004_should_notify_different_timezone_new_york FAILED
tests/unit/test_notification_timezone.py::TestShouldNotifyBasic::test_tc011_should_notify_outside_tolerance_six_minutes FAILED
tests/unit/test_notification_timezone.py::TestShouldNotifyBasic::test_tc012_should_notify_default_timezone_when_missing FAILED
tests/unit/test_notification_timezone.py::TestShouldNotifyBasic::test_tc014_should_notify_date_boundary_crossing FAILED
tests/unit/test_notification_timezone.py::TestProcessNotificationsWithShouldNotify::test_tc005_process_notifications_filters_by_should_notify FAILED
tests/unit/test_notification_timezone.py::TestProcessNotificationsWithShouldNotify::test_tc005b_process_notifications_notifies_matching_user_utc_offset FAILED
tests/unit/test_notification_timezone.py::TestShouldNotifyEdgeCases::test_tc006_should_notify_exactly_five_minutes_before FAILED
tests/unit/test_notification_timezone.py::TestShouldNotifyEdgeCases::test_tc007_should_notify_utc_timezone FAILED
tests/unit/test_notification_timezone.py::TestShouldNotifyEdgeCases::test_tc013_should_notify_default_notification_time_when_missing FAILED
tests/unit/test_notification_timezone.py::TestShouldNotifyEdgeCases::test_tc015_should_notify_date_boundary_outside_tolerance FAILED
tests/unit/test_notification_timezone.py::TestShouldNotifyEdgeCases::test_tc016_should_notify_midnight_notification_time FAILED
tests/unit/test_notification_timezone.py::TestShouldNotifyEdgeCases::test_tc017_should_notify_late_night_notification_time FAILED
tests/unit/test_notification_timezone.py::TestShouldNotifyEdgeCases::test_tc018_should_notify_empty_settings_uses_defaults FAILED
tests/unit/test_notification_timezone.py::TestShouldNotifyErrorCases::test_tc008_should_notify_invalid_timezone_falls_back_to_default FAILED
============================== 17 failed in 0.76s ==============================
```

---

## 3. 期待される失敗メッセージ

### should_notify 関連テスト (TC-001 〜 TC-018)

```
AttributeError: 'NotificationService' object has no attribute 'should_notify'
```

**原因**: `NotificationService` クラスに `should_notify` メソッドが実装されていない。

### process_notifications 統合テスト (TC-005, TC-005b)

```
AssertionError: assert 2 == 1
```

**原因**: `process_notifications` に `should_notify` による時刻フィルタリングが組み込まれていないため、全ユーザーに通知が送信される。

---

## 4. テストファイル

**パス**: `backend/tests/unit/test_notification_timezone.py`

---

## 5. Greenフェーズで実装すべき内容

### 5.1 必須実装: should_notify メソッド

**ファイル**: `backend/src/services/notification_service.py`

```python
from zoneinfo import ZoneInfo

def should_notify(self, user, current_utc: datetime) -> bool:
    """ユーザーのローカル時刻が notification_time と一致するか判定"""
    tz_name = user.settings.get('timezone', 'Asia/Tokyo')

    try:
        user_tz = ZoneInfo(tz_name)
    except Exception:
        # 無効なタイムゾーン名の場合は Asia/Tokyo にフォールバック
        user_tz = ZoneInfo('Asia/Tokyo')

    local_time = current_utc.astimezone(user_tz)
    notification_time = user.settings.get('notification_time', '09:00')

    notif_hour, notif_min = map(int, notification_time.split(':'))
    local_hour, local_min = local_time.hour, local_time.minute

    notif_total_min = notif_hour * 60 + notif_min
    local_total_min = local_hour * 60 + local_min
    diff = abs(local_total_min - notif_total_min)

    # 日付境界をまたぐケースの補正
    if diff > 720:
        diff = 1440 - diff

    return diff <= 5
```

### 5.2 必須実装: process_notifications への統合

**ファイル**: `backend/src/services/notification_service.py`

`process_notifications` の `last_notified_date` チェック後に以下を追加:

```python
# タイムゾーン考慮の時刻一致チェック
if not self.should_notify(user, current_time):
    result.skipped += 1
    continue
```

---

## 6. 品質評価

| 評価項目 | 結果 |
|---------|------|
| テスト実行 | ✅ 実行可能（17件全て FAIL 確認）|
| 期待値 | ✅ 明確で具体的 |
| アサーション | ✅ 適切 (`assert result is True/False`) |
| 実装方針 | ✅ 明確（should_notify 未実装が原因） |
| 信頼性レベル分布 | 🔵 6件 (35%), 🟡 11件 (65%), 🔴 0件 |

**品質判定**: ✅ 高品質

---

## 7. 信頼性レベル統計

| 分類 | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|------|-------|-------|-------|------|
| 正常系 | 4 | 1 | 0 | 5 |
| 統合 | 2 | 0 | 0 | 2 |
| 境界値 | 0 | 9 | 0 | 9 |
| 異常系 | 0 | 1 | 0 | 1 |
| **合計** | **6** | **11** | **0** | **17** |

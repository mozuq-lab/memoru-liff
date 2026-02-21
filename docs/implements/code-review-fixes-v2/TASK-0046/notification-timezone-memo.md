# TDD開発メモ: 通知時刻/タイムゾーン判定 (notification-timezone)

## 概要

- 機能名: 通知時刻/タイムゾーン判定 (notification-timezone)
- 開発開始: 2026-02-21
- 現在のフェーズ: Green（最小実装完了）

## 関連ファイル

- 元タスクファイル: `docs/tasks/code-review-fixes-v2/TASK-0046.md`
- 要件定義: `docs/implements/code-review-fixes-v2/TASK-0046/notification-timezone-requirements.md`
- テストケース定義: `docs/implements/code-review-fixes-v2/TASK-0046/notification-timezone-testcases.md`
- Redフェーズ記録: `docs/implements/code-review-fixes-v2/TASK-0046/notification-timezone-red-phase.md`
- 実装ファイル: `backend/src/services/notification_service.py`
- テストファイル: `backend/tests/unit/test_notification_timezone.py`

---

## Redフェーズ（失敗するテスト作成）

### 作成日時

2026-02-21

### テストケース概要

テストケース定義書の Phase 1（必須）と Phase 2（推奨）を中心に 17件のテストケースを実装した。

| 分類 | TC数 | 対象メソッド |
|------|------|-------------|
| Phase 1 正常系 | TC-001〜004 | `should_notify` |
| Phase 1 統合 | TC-005, TC-005b | `process_notifications` + `should_notify` |
| Phase 1 境界値 | TC-011, TC-012, TC-014 | `should_notify` |
| Phase 2 境界値 | TC-006, TC-007, TC-013, TC-015, TC-016, TC-017, TC-018 | `should_notify` |
| Phase 2 異常系 | TC-008 | `should_notify` |

### テストファイル

`backend/tests/unit/test_notification_timezone.py` (新規作成)

テストクラス構成:
- `TestShouldNotifyBasic`: 正常系 + Phase 1 必須境界値 (7件)
- `TestProcessNotificationsWithShouldNotify`: 統合テスト (2件)
- `TestShouldNotifyEdgeCases`: Phase 2 境界値 (7件)
- `TestShouldNotifyErrorCases`: 異常系 (1件)

### 期待される失敗

```
AttributeError: 'NotificationService' object has no attribute 'should_notify'
```

全 17件が `should_notify` メソッド未実装（`AttributeError`）により失敗する。

### テスト実行コマンド

```bash
cd /Volumes/external/dev/memoru-liff/backend && python -m pytest tests/unit/test_notification_timezone.py -v
```

### 実行結果（Red フェーズ確認）

```
17 failed in 0.76s
```

### 次のフェーズへの要求事項

Greenフェーズで実装すべき内容:

1. **`NotificationService.should_notify(user, current_utc)` メソッドの新規追加**
   - `user.settings.get('timezone', 'Asia/Tokyo')` でタイムゾーン取得
   - `ZoneInfo(tz_name)` でタイムゾーンオブジェクト生成（無効名は Asia/Tokyo にフォールバック）
   - `current_utc.astimezone(user_tz)` でローカル時刻に変換
   - `user.settings.get('notification_time', '09:00')` で通知時刻取得
   - 分単位で差分を計算し `diff <= 5` で判定
   - 日付境界ケース: `diff > 720` の場合 `1440 - diff` に補正

2. **`NotificationService.process_notifications()` への統合**
   - `last_notified_date` チェック後に `should_notify(user, current_time)` を呼び出す
   - `should_notify` が `False` の場合は `result.skipped += 1` してスキップ

---

## Greenフェーズ（最小実装）

### 実装日時

2026-02-21

### 実装方針

- `NotificationService.should_notify(user, current_utc)` を新規追加
- `user.settings` 辞書から `timezone`（デフォルト: Asia/Tokyo）と `notification_time`（デフォルト: 09:00）を取得
- Python 3.9+ 標準ライブラリ `zoneinfo` で UTC→ローカル時刻変換
- 無効タイムゾーン名は try-except で捕捉し Asia/Tokyo にフォールバック
- 分単位での差分計算 + 日付境界補正（diff > 720 → 1440 - diff）+ `diff <= 5` で判定
- `process_notifications` の `last_notified_date` チェック後に `should_notify` を呼び出すよう修正
- 既存テスト `test_notification_service.py` の `current_time` を新仕様（UTC 00:00 = JST 09:00）に合わせて修正

### テスト結果

```
tests/unit/test_notification_timezone.py - 17 passed in 1.16s
全テストスイート - 251 passed in 8.65s
```

### 課題・改善点（Refactorフェーズ対応候補）

1. `settings` アクセスの重複コードを削減
2. `user` パラメータへの型ヒント追加（`User` 型を明示）
3. `except (ZoneInfoNotFoundError, Exception)` を `except Exception` に簡略化

---

## Refactorフェーズ（品質改善）

### リファクタ日時

（未実施）

### 改善内容

（Refactorフェーズで記述）

### 最終コード

（Refactorフェーズで記述）

### 品質評価

（Refactorフェーズで記述）

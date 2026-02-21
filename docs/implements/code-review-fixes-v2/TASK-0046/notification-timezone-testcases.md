# テストケース定義書: 通知時刻/タイムゾーン判定

**タスクID**: TASK-0046
**要件名**: code-review-fixes-v2
**機能名**: 通知時刻/タイムゾーン判定 (notification-timezone)
**作成日**: 2026-02-21
**TDDフェーズ**: テストケース定義

---

## 1. 正常系テストケース（基本的な動作）

### TC-001: 通知時刻一致（Asia/Tokyo、ちょうど一致） 🔵

**信頼性**: 🔵 *REQ-V2-041, REQ-V2-042: 基本的な時刻判定。タスクファイルのテストケース1に明記*

- **テスト名**: 通知時刻がJSTローカル時刻とちょうど一致する場合にTrueを返す
  - **何をテストするか**: `should_notify` メソッドが、ユーザーのローカル時刻と `notification_time` がちょうど一致する場合に `True` を返すこと
  - **期待される動作**: UTC時刻をユーザーのタイムゾーン（Asia/Tokyo, UTC+9）でローカル時刻に変換し、`notification_time` と比較する
- **入力値**:
  - `user.settings = {"timezone": "Asia/Tokyo", "notification_time": "09:00"}`
  - `current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)` (JST 09:00)
  - **入力データの意味**: UTC 00:00 は JST 09:00 に相当し、notification_time と完全に一致する
- **期待される結果**: `True`
  - **期待結果の理由**: ローカル時刻 09:00 と notification_time 09:00 の差分は 0分で、±5分の許容範囲内
- **テストの目的**: 最も基本的な正常系。タイムゾーン変換が正しく行われ、一致判定が機能することを確認
  - **確認ポイント**: ZoneInfo による UTC→JST 変換、分単位の差分計算

### TC-002: 通知時刻不一致（Asia/Tokyo、大幅にずれている） 🔵

**信頼性**: 🔵 *REQ-V2-111: 時刻不一致時のスキップ。タスクファイルのテストケース2に明記*

- **テスト名**: 通知時刻がJSTローカル時刻と大幅にずれている場合にFalseを返す
  - **何をテストするか**: `should_notify` メソッドが、ローカル時刻と `notification_time` が大幅にずれている場合に `False` を返すこと
  - **期待される動作**: UTC 06:00 (JST 15:00) と notification_time 09:00 の差分は 360分で、±5分超過
- **入力値**:
  - `user.settings = {"timezone": "Asia/Tokyo", "notification_time": "09:00"}`
  - `current_utc = datetime(2024, 1, 1, 6, 0, 0, tzinfo=timezone.utc)` (JST 15:00)
  - **入力データの意味**: 6時間のずれ（360分）は明らかに許容範囲外
- **期待される結果**: `False`
  - **期待結果の理由**: ローカル時刻 15:00 と notification_time 09:00 の差分は 360分で、±5分超過
- **テストの目的**: 不一致時に通知が送信されないことを確認
  - **確認ポイント**: 差分計算が正しく行われ、False が返ること

### TC-003: ±5分以内の精度判定（3分後、許容範囲内） 🔵

**信頼性**: 🔵 *NFR-V2-301: EventBridge 5分間隔対応の精度判定。タスクファイルのテストケース3に明記*

- **テスト名**: ローカル時刻が通知時刻の3分後でもTrueを返す（±5分以内）
  - **何をテストするか**: `should_notify` メソッドの ±5分許容範囲の機能
  - **期待される動作**: UTC 00:03 (JST 09:03) と notification_time 09:00 の差分は 3分で、許容範囲内
- **入力値**:
  - `user.settings = {"timezone": "Asia/Tokyo", "notification_time": "09:00"}`
  - `current_utc = datetime(2024, 1, 1, 0, 3, 0, tzinfo=timezone.utc)` (JST 09:03)
  - **入力データの意味**: 3分のずれは EventBridge の実行間隔内で発生しうる
- **期待される結果**: `True`
  - **期待結果の理由**: 差分3分は ±5分の許容範囲内
- **テストの目的**: EventBridge の実行タイミングのばらつきに対応できることを確認
  - **確認ポイント**: 差分計算が絶対値で行われ、小さな差分を許容すること

### TC-004: 異なるタイムゾーンでの通知判定（America/New_York） 🔵

**信頼性**: 🔵 *REQ-V2-041: タイムゾーン変換。タスクファイルのテストケース7に明記*

- **テスト名**: America/New_Yorkタイムゾーンのユーザーに対して正しく判定する
  - **何をテストするか**: Asia/Tokyo 以外のタイムゾーンでの正しい時刻変換と判定
  - **期待される動作**: UTC 14:00 は EST 09:00 に相当し、notification_time 09:00 と一致
- **入力値**:
  - `user.settings = {"timezone": "America/New_York", "notification_time": "09:00"}`
  - `current_utc = datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc)` (EST 09:00)
  - **入力データの意味**: 冬季の America/New_York は UTC-5 なので、UTC 14:00 = EST 09:00
- **期待される結果**: `True`
  - **期待結果の理由**: EST 09:00 と notification_time 09:00 は一致
- **テストの目的**: 複数タイムゾーンに対応できることを確認
  - **確認ポイント**: ZoneInfo による UTC→EST 変換の正確性

### TC-005: process_notifications で should_notify による通知フィルタリング 🔵

**信頼性**: 🔵 *dataflow.md セクション4: process_notifications の should_notify 呼び出しフロー。タスクファイルのテストケース8に明記*

- **テスト名**: process_notificationsが通知時刻一致ユーザーのみに通知する
  - **何をテストするか**: `process_notifications` 内で `should_notify` が呼び出され、時刻一致ユーザーのみに通知が送信されること
  - **期待される動作**: 通知時刻一致ユーザーには通知が送信され、不一致ユーザーはスキップされる
- **入力値**:
  - ユーザー1: `settings = {"notification_time": "09:00", "timezone": "Asia/Tokyo"}` (一致)
  - ユーザー2: `settings = {"notification_time": "15:00", "timezone": "Asia/Tokyo"}` (不一致)
  - `current_time`: UTC 00:00 (JST 09:00)
  - 両ユーザーに復習カードあり
  - **入力データの意味**: JST 09:00 に実行した場合、09:00 設定のユーザーのみ通知対象
- **期待される結果**: `result.sent == 1`（ユーザー1のみ）、`result.skipped >= 1`（ユーザー2はスキップ）
  - **期待結果の理由**: should_notify がフィルタリングを行い、時刻一致ユーザーのみに通知される
- **テストの目的**: should_notify と process_notifications の統合動作を確認
  - **確認ポイント**: should_notify の結果に基づく通知送信/スキップの分岐

### TC-006: ±5分以内の精度判定（5分前、許容範囲ギリギリ） 🟡

**信頼性**: 🟡 *NFR-V2-301 の ±5分精度から推測。ちょうど5分前のケースはタスクファイルに明記なし*

- **テスト名**: ローカル時刻が通知時刻の5分前でもTrueを返す（許容範囲ギリギリ）
  - **何をテストするか**: 許容範囲の境界ぎりぎり（5分ちょうど）で True が返ること
  - **期待される動作**: UTC 23:55 前日 (JST 08:55) と notification_time 09:00 の差分は 5分で、diff <= 5 の判定により True
- **入力値**:
  - `user.settings = {"timezone": "Asia/Tokyo", "notification_time": "09:00"}`
  - `current_utc = datetime(2023, 12, 31, 23, 55, 0, tzinfo=timezone.utc)` (JST 08:55)
  - **入力データの意味**: ちょうど5分前は許容範囲の境界値
- **期待される結果**: `True`
  - **期待結果の理由**: 差分5分は `diff <= 5` により許容範囲内
- **テストの目的**: 許容範囲の境界で正しく動作することを確認
  - **確認ポイント**: `<=` 演算子の境界動作

### TC-007: UTCタイムゾーンでの通知判定 🟡

**信頼性**: 🟡 *UserSettingsRequest に "UTC" が有効なタイムゾーンとして登録されている。タスクファイルには明記なし*

- **テスト名**: UTCタイムゾーンのユーザーに対して正しく判定する
  - **何をテストするか**: タイムゾーンオフセットなし（UTC そのもの）での判定
  - **期待される動作**: UTC 09:00 と notification_time 09:00 が一致
- **入力値**:
  - `user.settings = {"timezone": "UTC", "notification_time": "09:00"}`
  - `current_utc = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)` (UTC 09:00)
  - **入力データの意味**: タイムゾーン変換なしの最も単純なケース
- **期待される結果**: `True`
  - **期待結果の理由**: UTC 09:00 と notification_time 09:00 は一致
- **テストの目的**: タイムゾーン変換のオフセットが 0 の場合の動作確認
  - **確認ポイント**: ZoneInfo("UTC") の動作

---

## 2. 異常系テストケース（エラーハンドリング）

### TC-008: 無効なタイムゾーン名のフォールバック 🟡

**信頼性**: 🟡 *設計文書に「無効なタイムゾーンの場合は Asia/Tokyo をデフォルトとして使用」と記載があるが、具体的なエラーハンドリング方式は推測*

- **テスト名**: 無効なタイムゾーン名が設定されている場合にデフォルト（Asia/Tokyo）にフォールバックする
  - **エラーケースの概要**: ユーザーの settings に不正なタイムゾーン名が格納されている場合
  - **エラー処理の重要性**: DynamoDB に直接書き込まれた不正データや、バリデーション前のデータに対して安全に動作する必要がある
- **入力値**:
  - `user.settings = {"timezone": "Invalid/Timezone", "notification_time": "09:00"}`
  - `current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)` (JST 09:00)
  - **不正な理由**: "Invalid/Timezone" は IANA タイムゾーンデータベースに存在しない
  - **実際の発生シナリオ**: DynamoDB に直接書き込まれたデータ、またはバリデーション不備時
- **期待される結果**: 例外を発生させず、Asia/Tokyo としてフォールバック処理される。UTC 00:00 = JST 09:00 なので `True` を返す
  - **エラーメッセージの内容**: 内部的に warning ログを出力（ユーザーには影響なし）
  - **システムの安全性**: 通知処理全体が中断されず、他のユーザーへの処理が続行される
- **テストの目的**: 防御的プログラミングの確認。不正データがシステム全体を停止させないことを保証
  - **品質保証の観点**: バッチ処理の堅牢性確保

### TC-009: notification_time が不正なフォーマットの場合 🔴

**信頼性**: 🔴 *タスクファイルや要件定義には notification_time の不正フォーマット処理についての明記なし。防御的プログラミングから推測*

- **テスト名**: notification_timeが不正なフォーマットの場合にエラーハンドリングされる
  - **エラーケースの概要**: `notification_time` が HH:MM 形式でない場合（例: "invalid", "25:00"）
  - **エラー処理の重要性**: DynamoDB の既存データに不正値が含まれる可能性への対処
- **入力値**:
  - `user.settings = {"timezone": "Asia/Tokyo", "notification_time": "invalid"}`
  - `current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)`
  - **不正な理由**: "invalid" は HH:MM 形式ではなく、`int()` 変換で `ValueError` が発生する
  - **実際の発生シナリオ**: DynamoDB に直接書き込まれた不正データ
- **期待される結果**: 例外が適切にハンドリングされる（`False` を返すか、デフォルト値 "09:00" にフォールバック）
  - **エラーメッセージの内容**: error/warning ログ出力
  - **システムの安全性**: 処理が中断せず、他ユーザーの通知処理が続行される
- **テストの目的**: 不正データに対する堅牢性の確認
  - **品質保証の観点**: バッチ処理の全ユーザーループが不正データで中断されないこと

### TC-010: process_notifications で should_notify が例外を投げた場合のエラーハンドリング 🟡

**信頼性**: 🟡 *notification_service.py の既存エラーハンドリングパターン（try-except per user）から推測*

- **テスト名**: should_notifyが例外を投げた場合にprocess_notificationsがエラーを記録して続行する
  - **エラーケースの概要**: should_notify 内部で予期しない例外が発生した場合
  - **エラー処理の重要性**: 1ユーザーのエラーが他ユーザーの通知処理に影響しないこと
- **入力値**:
  - 複数ユーザー（1人は should_notify で例外発生、他は正常）
  - `current_time`: 任意のUTC時刻
  - **不正な理由**: should_notify が予期しない例外（KeyError, ZoneInfoNotFoundError 等）を投げる
  - **実際の発生シナリオ**: settings 辞書の構造が想定外のケース
- **期待される結果**: エラーが `result.errors` に記録され、他のユーザーの処理が続行される
  - **エラーメッセージの内容**: エラーが errors リストに追加される
  - **システムの安全性**: 処理全体が中断されず、正常なユーザーには通知が送信される
- **テストの目的**: バッチ処理の堅牢性確認
  - **品質保証の観点**: 1ユーザーの問題が全体に波及しないことの保証

---

## 3. 境界値テストケース（最小値、最大値、null等）

### TC-011: ±5分超過（6分後、許容範囲外） 🔵

**信頼性**: 🔵 *タスクファイルのテストケース4に明記*

- **テスト名**: ローカル時刻が通知時刻の6分後の場合にFalseを返す（許容範囲外）
  - **境界値の意味**: ±5分の許容範囲の外側（5分+1分）。`diff <= 5` が False になる最初の値
  - **境界値での動作保証**: 5分以内は True、6分以上は False であることの境界確認
- **入力値**:
  - `user.settings = {"timezone": "Asia/Tokyo", "notification_time": "09:00"}`
  - `current_utc = datetime(2024, 1, 1, 0, 6, 0, tzinfo=timezone.utc)` (JST 09:06)
  - **境界値選択の根拠**: `diff <= 5` の判定で False になる最小の整数分値（6分）
  - **実際の使用場面**: EventBridge の実行タイミングが想定より遅延した場合
- **期待される結果**: `False`
  - **境界での正確性**: 差分6分は `diff <= 5` により False
  - **一貫した動作**: 5分以内は True、6分以上は False
- **テストの目的**: 許容範囲の境界外で正しくスキップされることを確認
  - **堅牢性の確認**: 許容範囲の外側で確実に False が返ること

### TC-012: タイムゾーン未設定のデフォルト（settings に timezone キーなし） 🟡

**信頼性**: 🟡 *REQ-V2-112: デフォルトタイムゾーン Asia/Tokyo。User モデルの settings デフォルト値から推測*

- **テスト名**: settingsにtimezoneキーがない場合にAsia/Tokyoをデフォルトとして使用する
  - **境界値の意味**: settings 辞書に timezone キーが存在しない場合のデフォルト動作
  - **境界値での動作保証**: デフォルト値が正しく適用されること
- **入力値**:
  - `user.settings = {"notification_time": "09:00"}` (timezone キーなし)
  - `current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)` (JST 09:00)
  - **境界値選択の根拠**: DynamoDB の既存レコードに timezone が存在しないケース
  - **実際の使用場面**: TASK-0046 実装前に作成されたユーザーレコード
- **期待される結果**: `True`（Asia/Tokyo として判定される）
  - **境界での正確性**: `settings.get('timezone', 'Asia/Tokyo')` が Asia/Tokyo を返す
  - **一貫した動作**: 明示的に Asia/Tokyo を設定した場合と同じ動作
- **テストの目的**: 後方互換性の確認。既存ユーザーデータでも正しく動作すること
  - **堅牢性の確認**: デフォルト値の適用が確実に行われること

### TC-013: notification_time 未設定のデフォルト（settings に notification_time キーなし） 🟡

**信頼性**: 🟡 *User モデルの settings デフォルト値 "09:00" から推測。タスクファイルには明記なし*

- **テスト名**: settingsにnotification_timeキーがない場合にデフォルト09:00として使用する
  - **境界値の意味**: settings 辞書に notification_time キーが存在しない場合のデフォルト動作
  - **境界値での動作保証**: デフォルト値 "09:00" が適用されること
- **入力値**:
  - `user.settings = {"timezone": "Asia/Tokyo"}` (notification_time キーなし)
  - `current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)` (JST 09:00)
  - **境界値選択の根拠**: notification_time が未設定の既存レコード
  - **実際の使用場面**: settings を一度も更新していないユーザー
- **期待される結果**: `True`（デフォルトの 09:00 として判定される）
  - **境界での正確性**: `settings.get('notification_time', '09:00')` が 09:00 を返す
  - **一貫した動作**: 明示的に 09:00 を設定した場合と同じ動作
- **テストの目的**: デフォルト値の適用確認
  - **堅牢性の確認**: 未設定フィールドでも安全に動作すること

### TC-014: 日付境界をまたぐケース（23:58 → 00:01） 🟡

**信頼性**: 🟡 *EDGE-V2-102: 日付境界処理。タスクファイルのテストケース6に明記*

- **テスト名**: 通知時刻23:58でローカル時刻が00:01の場合にTrueを返す（日付境界）
  - **境界値の意味**: 日付をまたぐケースでは単純な差分（1437分）ではなく、反対方向の差分（3分）で判定
  - **境界値での動作保証**: diff > 720 の場合に 1440 - diff の補正が正しく行われること
- **入力値**:
  - `user.settings = {"timezone": "America/New_York", "notification_time": "23:58"}`
  - `current_utc = datetime(2024, 1, 1, 5, 1, 0, tzinfo=timezone.utc)` (EST 00:01)
  - **境界値選択の根拠**: 23:58 と 00:01 は3分差だが、単純計算では 1437分差になる
  - **実際の使用場面**: 深夜近くの通知時刻を設定しているユーザー
- **期待される結果**: `True`（差分3分、許容範囲内）
  - **境界での正確性**: `diff = abs(1 - 1438) = 1437 → 1440 - 1437 = 3` で3分と判定
  - **一貫した動作**: 日付をまたがない場合と同じ精度で判定
- **テストの目的**: 日付境界の特殊処理が正しく機能することを確認
  - **堅牢性の確認**: 深夜帯の通知時刻でもシステムが正しく動作すること

### TC-015: 日付境界をまたぐケース（許容範囲外、23:50 → 00:01） 🟡

**信頼性**: 🟡 *EDGE-V2-102 の拡張。日付境界で False になるケースの確認*

- **テスト名**: 通知時刻23:50でローカル時刻が00:01の場合にFalseを返す（日付境界、範囲外）
  - **境界値の意味**: 日付境界をまたぐ場合でも、差分が6分以上なら False になることを確認
  - **境界値での動作保証**: 日付境界の補正後も ±5分判定が正しく適用されること
- **入力値**:
  - `user.settings = {"timezone": "America/New_York", "notification_time": "23:50"}`
  - `current_utc = datetime(2024, 1, 1, 5, 1, 0, tzinfo=timezone.utc)` (EST 00:01)
  - **境界値選択の根拠**: 23:50 と 00:01 は11分差（日付境界補正後）で許容範囲外
  - **実際の使用場面**: 日付境界付近だが許容範囲外のケース
- **期待される結果**: `False`（差分11分、許容範囲外）
  - **境界での正確性**: `diff = abs(1 - 1430) = 1429 → 1440 - 1429 = 11` で11分と判定
  - **一貫した動作**: 日付境界でも ±5分判定が一貫して適用される
- **テストの目的**: 日付境界の補正後にも許容範囲判定が正しく行われることを確認
  - **堅牢性の確認**: 日付境界で誤って True を返さないことの保証

### TC-016: notification_time が 00:00（真夜中） 🟡

**信頼性**: 🟡 *HH:MM フォーマットの最小値。要件定義には明記なしだが UserSettingsRequest のバリデーション 00:00-23:59 から推測*

- **テスト名**: 通知時刻00:00（真夜中）で正しく判定する
  - **境界値の意味**: notification_time の最小値。分単位の合計値が 0 になる境界
  - **境界値での動作保証**: 0 分での計算が正しく行われること
- **入力値**:
  - `user.settings = {"timezone": "Asia/Tokyo", "notification_time": "00:00"}`
  - `current_utc = datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone.utc)` (JST 00:00 翌日)
  - **境界値選択の根拠**: HH:MM の最小値 00:00
  - **実際の使用場面**: 深夜0時に通知を受け取りたいユーザー
- **期待される結果**: `True`
  - **境界での正確性**: `notif_total_min = 0`, `local_total_min = 0`, `diff = 0`
  - **一貫した動作**: 他の時刻と同じロジックで判定
- **テストの目的**: 最小境界値での計算の正確性を確認
  - **堅牢性の確認**: 0時0分での分単位計算が正しく行われること

### TC-017: notification_time が 23:59（最大値） 🟡

**信頼性**: 🟡 *HH:MM フォーマットの最大値。UserSettingsRequest のバリデーション 00:00-23:59 から推測*

- **テスト名**: 通知時刻23:59（最大値）で正しく判定する
  - **境界値の意味**: notification_time の最大値。分単位の合計値が 1439 になる境界
  - **境界値での動作保証**: 1439 分での計算が正しく行われること
- **入力値**:
  - `user.settings = {"timezone": "Asia/Tokyo", "notification_time": "23:59"}`
  - `current_utc = datetime(2024, 1, 1, 14, 59, 0, tzinfo=timezone.utc)` (JST 23:59)
  - **境界値選択の根拠**: HH:MM の最大値 23:59
  - **実際の使用場面**: 深夜直前に通知を受け取りたいユーザー
- **期待される結果**: `True`
  - **境界での正確性**: `notif_total_min = 1439`, `local_total_min = 1439`, `diff = 0`
  - **一貫した動作**: 他の時刻と同じロジックで判定
- **テストの目的**: 最大境界値での計算の正確性を確認
  - **堅牢性の確認**: 23:59 での分単位計算が正しく行われること

### TC-018: settings が空辞書の場合（全フィールド未設定） 🟡

**信頼性**: 🟡 *DynamoDB の既存レコードで settings が空の場合の防御的処理。要件定義には明記なし*

- **テスト名**: settingsが空辞書の場合にデフォルト値で判定する
  - **境界値の意味**: settings 辞書が空（`{}`）の場合、全てのフィールドがデフォルト値で動作
  - **境界値での動作保証**: timezone = "Asia/Tokyo"、notification_time = "09:00" で判定
- **入力値**:
  - `user.settings = {}`
  - `current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)` (JST 09:00)
  - **境界値選択の根拠**: settings が空の最小ケース
  - **実際の使用場面**: DynamoDB 上のレガシーレコード
- **期待される結果**: `True`（デフォルト: Asia/Tokyo, 09:00 として判定）
  - **境界での正確性**: 両方の `.get()` がデフォルト値を返す
  - **一貫した動作**: 完全にデフォルト値が設定された場合と同じ動作
- **テストの目的**: 完全なデフォルト値適用の確認
  - **堅牢性の確認**: 最も不完全なデータでも安全に動作すること

---

## 4. 開発言語・フレームワーク

### バックエンド テスト

- **プログラミング言語**: Python 3.12
  - **言語選択の理由**: Lambda ランタイムと一致。`zoneinfo` モジュールが標準ライブラリで利用可能
  - **テストに適した機能**: `unittest.mock` によるモック、`datetime` の timezone-aware 操作
- **テストフレームワーク**: pytest + pytest-mock
  - **フレームワーク選択の理由**: プロジェクト既存のテストフレームワーク（`backend/tests/` 配下の全テストで使用）
  - **テスト実行環境**: ローカル環境（`make test` / `pytest tests/unit/`）
- **テストファイルパス**: `backend/tests/unit/test_notification_timezone.py`
- 🔵 この内容の信頼性レベル: 🔵 *CLAUDE.md、note.md で確認済み*

---

## 5. テストケース実装時の日本語コメント指針

各テストケースの実装時には以下の日本語コメントパターンに従う。

### テストケース開始時のコメント

```python
# 【テスト目的】: ユーザーのローカル時刻とnotification_timeの一致判定を確認する
# 【テスト内容】: UTC時刻をAsia/Tokyoに変換し、09:00との差分が0分であることを確認
# 【期待される動作】: should_notify が True を返す
# 🔵 REQ-V2-041, REQ-V2-042: 基本的な時刻判定
```

### Given（準備フェーズ）のコメント

```python
# 【テストデータ準備】: Asia/Tokyoタイムゾーンで09:00通知設定のユーザーを作成
# 【初期条件設定】: UTC 00:00（JST 09:00相当）の時刻を設定
# 【前提条件確認】: ユーザーのsettingsにtimezoneとnotification_timeが設定されている
```

### When（実行フェーズ）のコメント

```python
# 【実際の処理実行】: should_notify メソッドを呼び出す
# 【処理内容】: UTCからユーザーのローカル時刻へ変換し、notification_timeとの差分を計算
# 【実行タイミング】: EventBridge cron実行時を想定
```

### Then（検証フェーズ）のコメント

```python
# 【結果検証】: should_notify の戻り値が True であることを確認
# 【期待値確認】: ローカル時刻 09:00 と notification_time 09:00 の差分は 0分（±5分以内）
# 【品質保証】: 通知時刻一致時に確実に通知が送信されることを保証
```

### 各 assert ステートメントのコメント

```python
# 【検証項目】: should_notify の戻り値
# 🔵 REQ-V2-042: notification_time とローカル時刻が一致する場合に True
assert result is True  # 【確認内容】: ローカル時刻がnotification_timeと一致するため True

# 【検証項目】: process_notifications の送信カウント
# 🔵 dataflow.md: 時刻一致ユーザーのみに通知送信
assert result.sent == 1  # 【確認内容】: 通知時刻一致ユーザーのみに送信されること
```

### セットアップ・クリーンアップのコメント

```python
@pytest.fixture
def notification_service(self):
    # 【テスト前準備】: NotificationServiceのモックサービスを作成
    # 【環境初期化】: UserService, CardService, LineServiceをMagicMockで置き換え
    ...

@pytest.fixture
def mock_services(self):
    # 【テスト前準備】: 依存サービスのモックを作成
    # 【状態復元】: 各テストで独立したモックインスタンスを使用
    ...
```

---

## 6. 要件定義との対応関係

### 参照した機能概要

- **REQ-V2-041**: 通知送信前にユーザーのタイムゾーンを考慮したローカル時刻を算出する → TC-001, TC-004, TC-007
- **REQ-V2-042**: ユーザー設定の notification_time とローカル時刻が一致する場合のみ通知を送信する → TC-001, TC-002, TC-005

### 参照した入力・出力仕様

- **should_notify メソッド**: 入力 (User, datetime) → 出力 (bool) → 全テストケース
- **process_notifications メソッド**: 入力 (datetime) → 出力 (NotificationResult) → TC-005, TC-010
- **notification-timezone-requirements.md セクション2**: 入出力仕様の詳細定義

### 参照した制約条件

- **NFR-V2-301**: 通知送信は notification_time ±5分の精度で実行される → TC-003, TC-006, TC-011
- **REQ-V2-112**: タイムゾーン未設定時は Asia/Tokyo をデフォルト → TC-012, TC-018

### 参照した使用例

- **パターン1-5 (requirements.md セクション4.1)**: TC-001〜TC-005 の元となるパターン
- **エッジケース1-3 (requirements.md セクション4.2)**: TC-012〜TC-014 の元となるパターン
- **エラーケース1 (requirements.md セクション4.3)**: TC-008 の元となるパターン

### 参照した設計文書

- **architecture.md セクション2.3**: should_notify アルゴリズムの設計コード → TC-001〜TC-018 のアルゴリズム根拠
- **dataflow.md セクション4**: process_notifications の通知送信フロー → TC-005, TC-010
- **api-endpoints.md**: PUT /users/me/settings の仕様 → 設定更新テスト（本タスクでは既に実装済み）

---

## 7. テストケースサマリー

### テストケース一覧

| ID | 分類 | テスト名 | 信頼性 | テスト対象 |
|----|------|----------|--------|-----------|
| TC-001 | 正常系 | 通知時刻一致（Asia/Tokyo） | 🔵 | `should_notify` |
| TC-002 | 正常系 | 通知時刻不一致（大幅ずれ） | 🔵 | `should_notify` |
| TC-003 | 正常系 | ±5分以内（3分後） | 🔵 | `should_notify` |
| TC-004 | 正常系 | 異なるタイムゾーン（America/New_York） | 🔵 | `should_notify` |
| TC-005 | 正常系 | process_notifications フィルタリング | 🔵 | `process_notifications` |
| TC-006 | 正常系 | ±5分以内（5分前、境界ギリギリ） | 🟡 | `should_notify` |
| TC-007 | 正常系 | UTCタイムゾーン | 🟡 | `should_notify` |
| TC-008 | 異常系 | 無効なタイムゾーン名のフォールバック | 🟡 | `should_notify` |
| TC-009 | 異常系 | notification_time 不正フォーマット | 🔴 | `should_notify` |
| TC-010 | 異常系 | should_notify 例外時の process_notifications 続行 | 🟡 | `process_notifications` |
| TC-011 | 境界値 | ±5分超過（6分後） | 🔵 | `should_notify` |
| TC-012 | 境界値 | timezone 未設定のデフォルト | 🟡 | `should_notify` |
| TC-013 | 境界値 | notification_time 未設定のデフォルト | 🟡 | `should_notify` |
| TC-014 | 境界値 | 日付境界（23:58→00:01、許容範囲内） | 🟡 | `should_notify` |
| TC-015 | 境界値 | 日付境界（23:50→00:01、許容範囲外） | 🟡 | `should_notify` |
| TC-016 | 境界値 | notification_time 00:00（最小値） | 🟡 | `should_notify` |
| TC-017 | 境界値 | notification_time 23:59（最大値） | 🟡 | `should_notify` |
| TC-018 | 境界値 | settings 空辞書 | 🟡 | `should_notify` |

### 信頼性レベル統計

| カテゴリ | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|---------|-------|-------|-------|------|
| 正常系 | 5 | 2 | 0 | 7 |
| 異常系 | 0 | 2 | 1 | 3 |
| 境界値 | 1 | 7 | 0 | 8 |
| **合計** | **6** | **11** | **1** | **18** |

### 全体評価

- **総テストケース数**: 18件
- 🔵 **青信号**: 6件 (33%)
- 🟡 **黄信号**: 11件 (61%)
- 🔴 **赤信号**: 1件 (6%)

---

## 8. 実装優先度

### Phase 1（必須、RED フェーズ最初に実装）

TC-001, TC-002, TC-003, TC-004, TC-005, TC-011, TC-012, TC-014

### Phase 2（推奨、GREEN フェーズ後に追加）

TC-006, TC-007, TC-008, TC-013, TC-015, TC-016, TC-017, TC-018

### Phase 3（任意、REFACTOR フェーズで検討）

TC-009, TC-010

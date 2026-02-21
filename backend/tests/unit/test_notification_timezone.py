"""
TDD Red Phase: 通知時刻/タイムゾーン判定 テスト
TASK-0046: notification_service.py の should_notify メソッドと process_notifications への統合

テスト対象:
  - NotificationService.should_notify() メソッド（未実装 → RED フェーズで全て失敗する）
  - NotificationService.process_notifications() への should_notify 統合

信頼性レベル凡例:
  🔵 青信号: 要件定義書・設計文書に明記されている
  🟡 黄信号: 要件定義書から妥当な推測
  🔴 赤信号: 推測（要件定義に明記なし）
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.models.user import User
from src.services.notification_service import NotificationService, NotificationResult
from src.services.line_service import LineApiError


# ---------------------------------------------------------------------------
# フィクスチャ
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_services():
    """
    【テスト前準備】: 依存サービスのモックを作成する
    【環境初期化】: 各テストで独立したモックインスタンスを使用するため fixture で生成
    """
    user_service = MagicMock()
    card_service = MagicMock()
    line_service = MagicMock()
    return user_service, card_service, line_service


@pytest.fixture
def notification_service(mock_services):
    """
    【テスト前準備】: NotificationService を mock_services で初期化する
    【環境初期化】: 実際の DynamoDB / LINE API 呼び出しを行わないようモック化
    """
    user_service, card_service, line_service = mock_services
    return NotificationService(
        user_service=user_service,
        card_service=card_service,
        line_service=line_service,
    )


def _make_user(
    user_id: str,
    timezone_str: str = "Asia/Tokyo",
    notification_time: str = "09:00",
    last_notified_date: str = None,
    line_user_id: str = "U1234567890abcdef1234567890abcdef",
) -> User:
    """
    【テストデータ準備】: テスト用 User オブジェクトを生成するヘルパー関数
    【初期条件設定】: settings 辞書に timezone と notification_time を格納した User を返す
    """
    return User(
        user_id=user_id,
        line_user_id=line_user_id,
        last_notified_date=last_notified_date,
        settings={
            "notification_time": notification_time,
            "timezone": timezone_str,
        },
        created_at=datetime.now(timezone.utc),
    )


# ===========================================================================
# Phase 1 必須テストケース (TC-001 〜 TC-005, TC-011, TC-012, TC-014)
# ===========================================================================


class TestShouldNotifyBasic:
    """正常系: should_notify の基本動作確認"""

    # ------------------------------------------------------------------
    # TC-001: 通知時刻一致（Asia/Tokyo、ちょうど一致）
    # ------------------------------------------------------------------

    def test_tc001_should_notify_matches_notification_time_japan(
        self, notification_service
    ):
        """
        【テスト目的】: ユーザーのローカル時刻と notification_time がちょうど一致するときに True を返すことを確認する
        【テスト内容】: UTC 00:00 → JST 09:00。notification_time='09:00' と差分 0分
        【期待される動作】: should_notify が True を返す
        🔵 REQ-V2-041, REQ-V2-042: 基本的なタイムゾーン変換 + 時刻一致判定
        """
        # 【テストデータ準備】: Asia/Tokyo (UTC+9) で 09:00 通知設定のユーザーを作成
        user = _make_user("test-001", timezone_str="Asia/Tokyo", notification_time="09:00")

        # 【初期条件設定】: UTC 00:00 = JST 09:00 となる時刻を設定
        current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す（未実装のため AttributeError が発生する）
        # 【処理内容】: UTC をユーザーのローカル時刻に変換し、notification_time との差分を計算
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: True が返ること
        # 【期待値確認】: JST 09:00 と notification_time 09:00 の差分は 0分 → ±5分以内
        assert result is True  # 【確認内容】: ローカル時刻が notification_time とちょうど一致するため True 🔵

    # ------------------------------------------------------------------
    # TC-002: 通知時刻不一致（大幅ずれ）
    # ------------------------------------------------------------------

    def test_tc002_should_notify_no_match_different_time(
        self, notification_service
    ):
        """
        【テスト目的】: ローカル時刻と notification_time が大幅にずれているときに False を返すことを確認する
        【テスト内容】: UTC 06:00 → JST 15:00。notification_time='09:00' と差分 360分
        【期待される動作】: should_notify が False を返す
        🔵 REQ-V2-111: 時刻不一致時のスキップ
        """
        # 【テストデータ準備】: Asia/Tokyo で 09:00 通知設定のユーザーを作成
        user = _make_user("test-002", timezone_str="Asia/Tokyo", notification_time="09:00")

        # 【初期条件設定】: UTC 06:00 = JST 15:00（通知時刻と 6時間ずれ）
        current_utc = datetime(2024, 1, 1, 6, 0, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: False が返ること
        # 【期待値確認】: JST 15:00 と notification_time 09:00 の差分は 360分 → ±5分超過
        assert result is False  # 【確認内容】: 差分 360分は許容範囲外のため False 🔵

    # ------------------------------------------------------------------
    # TC-003: ±5分以内の精度判定（3分後）
    # ------------------------------------------------------------------

    def test_tc003_should_notify_within_five_minute_tolerance(
        self, notification_service
    ):
        """
        【テスト目的】: 通知時刻の 3分後でも True を返すことを確認する（±5分許容範囲の確認）
        【テスト内容】: UTC 00:03 → JST 09:03。notification_time='09:00' と差分 3分
        【期待される動作】: should_notify が True を返す
        🔵 NFR-V2-301: EventBridge 5分間隔対応の精度判定
        """
        # 【テストデータ準備】: Asia/Tokyo で 09:00 通知設定のユーザー
        user = _make_user("test-003", timezone_str="Asia/Tokyo", notification_time="09:00")

        # 【初期条件設定】: UTC 00:03 = JST 09:03（通知時刻の 3分後）
        current_utc = datetime(2024, 1, 1, 0, 3, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: True が返ること
        # 【期待値確認】: 差分 3分は diff <= 5 の判定により許容範囲内
        assert result is True  # 【確認内容】: 3分差は ±5分以内のため True 🔵

    # ------------------------------------------------------------------
    # TC-004: 異なるタイムゾーン（America/New_York）
    # ------------------------------------------------------------------

    def test_tc004_should_notify_different_timezone_new_york(
        self, notification_service
    ):
        """
        【テスト目的】: Asia/Tokyo 以外のタイムゾーンで正しく時刻変換と判定が行われることを確認する
        【テスト内容】: UTC 14:00 → EST 09:00 (America/New_York, 冬季 UTC-5)。notification_time='09:00' と差分 0分
        【期待される動作】: should_notify が True を返す
        🔵 REQ-V2-041: タイムゾーン変換の正確性
        """
        # 【テストデータ準備】: America/New_York (UTC-5 冬季) で 09:00 通知設定のユーザー
        user = _make_user("test-004", timezone_str="America/New_York", notification_time="09:00")

        # 【初期条件設定】: UTC 14:00 = EST 09:00（冬季 UTC-5）
        current_utc = datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: True が返ること
        # 【期待値確認】: ZoneInfo で UTC→EST 変換し EST 09:00 と notification_time 09:00 が一致
        assert result is True  # 【確認内容】: EST 09:00 と notification_time 09:00 が一致するため True 🔵

    # ------------------------------------------------------------------
    # TC-011: ±5分超過（6分後、許容範囲外）
    # ------------------------------------------------------------------

    def test_tc011_should_notify_outside_tolerance_six_minutes(
        self, notification_service
    ):
        """
        【テスト目的】: 通知時刻の 6分後では False を返すことを確認する（±5分の境界外）
        【テスト内容】: UTC 00:06 → JST 09:06。notification_time='09:00' と差分 6分
        【期待される動作】: should_notify が False を返す
        🔵 NFR-V2-301: 差分 6分は diff <= 5 の判定で False になる最初の値
        """
        # 【テストデータ準備】: Asia/Tokyo で 09:00 通知設定のユーザー
        user = _make_user("test-011", timezone_str="Asia/Tokyo", notification_time="09:00")

        # 【初期条件設定】: UTC 00:06 = JST 09:06（通知時刻の 6分後）
        current_utc = datetime(2024, 1, 1, 0, 6, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: False が返ること
        # 【期待値確認】: 差分 6分は diff <= 5 の判定で False
        assert result is False  # 【確認内容】: 6分差は ±5分超過のため False 🔵

    # ------------------------------------------------------------------
    # TC-012: timezone 未設定のデフォルト（settings に timezone キーなし）
    # ------------------------------------------------------------------

    def test_tc012_should_notify_default_timezone_when_missing(
        self, notification_service
    ):
        """
        【テスト目的】: settings に timezone キーがない場合に Asia/Tokyo をデフォルトとして使用することを確認する
        【テスト内容】: settings = {"notification_time": "09:00"}（timezone キーなし）、UTC 00:00 → JST 09:00
        【期待される動作】: Asia/Tokyo としてフォールバックされ True を返す
        🟡 REQ-V2-112: デフォルトタイムゾーン Asia/Tokyo（後方互換性）
        """
        # 【テストデータ準備】: settings から timezone キーを除外したユーザーを作成
        # 【初期条件設定】: timezone キーが存在しない DynamoDB レガシーレコードを模擬
        user = User(
            user_id="test-012",
            line_user_id="U1234567890abcdef1234567890abcdef",
            settings={"notification_time": "09:00"},  # timezone キーなし
            created_at=datetime.now(timezone.utc),
        )

        # 【初期条件設定】: UTC 00:00 = JST 09:00 となる時刻を設定
        current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: True が返ること（Asia/Tokyo デフォルトで JST 09:00 = notification_time 09:00）
        # 【期待値確認】: settings.get('timezone', 'Asia/Tokyo') が Asia/Tokyo を返し、差分 0分
        assert result is True  # 【確認内容】: デフォルト Asia/Tokyo で判定し、JST 09:00 が notification_time 09:00 と一致するため True 🟡

    # ------------------------------------------------------------------
    # TC-014: 日付境界をまたぐケース（23:58 → 00:01）
    # ------------------------------------------------------------------

    def test_tc014_should_notify_date_boundary_crossing(
        self, notification_service
    ):
        """
        【テスト目的】: 通知時刻が 23:58 でローカル時刻が 00:01 の場合、日付境界処理が正しく行われることを確認する
        【テスト内容】: notification_time='23:58'、ローカル時刻 00:01。単純差分は 1437分だが、境界補正で 3分となる
        【期待される動作】: should_notify が True を返す（差分3分、±5分以内）
        🟡 EDGE-V2-102: 日付境界をまたぐケースの正確な判定
        """
        # 【テストデータ準備】: America/New_York で 23:58 通知設定のユーザー
        user = _make_user(
            "test-014",
            timezone_str="America/New_York",
            notification_time="23:58",
        )

        # 【初期条件設定】: UTC 05:01 = EST 00:01（冬季 UTC-5）
        # notification_time 23:58 とローカル時刻 00:01 の単純差分は 1437分
        # diff > 720 の場合、1440 - 1437 = 3分として処理される
        current_utc = datetime(2024, 1, 1, 5, 1, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: True が返ること（日付境界補正後 差分3分）
        # 【期待値確認】: diff = abs(1 - 1438) = 1437 > 720 → 1440 - 1437 = 3分 → ±5分以内
        assert result is True  # 【確認内容】: 日付境界補正で 3分差として判定されるため True 🟡


# ===========================================================================
# TC-005: process_notifications での should_notify フィルタリング統合テスト
# ===========================================================================


class TestProcessNotificationsWithShouldNotify:
    """統合: process_notifications が should_notify を使ってフィルタリングすること"""

    def test_tc005_process_notifications_filters_by_should_notify(
        self, notification_service, mock_services
    ):
        """
        【テスト目的】: process_notifications が通知時刻一致ユーザーのみに通知を送信することを確認する
        【テスト内容】:
          - ユーザー1: notification_time='09:00', timezone='Asia/Tokyo'（UTC 00:00 = JST 09:00 → 一致）
          - ユーザー2: notification_time='15:00', timezone='Asia/Tokyo'（UTC 00:00 = JST 09:00 → 不一致）
          - 両ユーザーに復習カードあり
        【期待される動作】: ユーザー1のみ通知が送信され、ユーザー2はスキップされる
        🔵 dataflow.md セクション4: process_notifications の should_notify 呼び出しフロー
        """
        user_service, card_service, line_service = mock_services

        # 【テストデータ準備】: 通知時刻一致ユーザー（user-1）と不一致ユーザー（user-2）
        user1 = _make_user("user-1", notification_time="09:00", timezone_str="Asia/Tokyo")
        user2 = _make_user("user-2", notification_time="15:00", timezone_str="Asia/Tokyo")

        # 【初期条件設定】: 両ユーザーを get_linked_users が返すよう設定
        user_service.get_linked_users.return_value = [user1, user2]

        # 【初期条件設定】: 両ユーザーに復習カードあり（due_count > 0）
        card_service.get_due_card_count.return_value = 3
        line_service.push_message.return_value = True

        # 【実際の処理実行】: UTC 00:00 (JST 09:00) に process_notifications を呼び出す
        # 【処理内容】: should_notify で時刻判定し、一致するユーザーのみ通知を送信する
        current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = notification_service.process_notifications(current_utc)

        # 【結果検証】: user1 のみ通知が送信され、user2 はスキップされること
        # 【期待値確認】: sent == 1（user1）、skipped >= 1（user2 は should_notify で False）
        assert result.sent == 1  # 【確認内容】: 通知時刻一致ユーザー（user1）のみ通知送信 🔵
        assert result.skipped >= 1  # 【確認内容】: 不一致ユーザー（user2）はスキップ 🔵
        assert result.processed == 2  # 【確認内容】: 両ユーザーを処理した 🔵

    def test_tc005b_process_notifications_notifies_matching_user_utc_offset(
        self, notification_service, mock_services
    ):
        """
        【テスト目的】: 複数タイムゾーンユーザーが混在する場合、各自のローカル時刻で判定することを確認する
        【テスト内容】:
          - user-japan: notification_time='09:00', timezone='Asia/Tokyo'（UTC 00:00 = JST 09:00 → 一致）
          - user-newyork: notification_time='09:00', timezone='America/New_York'（UTC 00:00 = EST 19:00 前日 → 不一致）
        【期待される動作】: user-japan のみ通知が送信される
        🔵 REQ-V2-041: タイムゾーン考慮した通知フィルタリング
        """
        user_service, card_service, line_service = mock_services

        # 【テストデータ準備】: 異なるタイムゾーンで同じ 09:00 設定のユーザー
        user_japan = _make_user(
            "user-japan", timezone_str="Asia/Tokyo", notification_time="09:00",
            line_user_id="Ujapan00000000000000000000000001"
        )
        user_newyork = _make_user(
            "user-newyork", timezone_str="America/New_York", notification_time="09:00",
            line_user_id="Unewyork0000000000000000000000002"
        )

        # 【初期条件設定】: 両ユーザーに復習カードあり
        user_service.get_linked_users.return_value = [user_japan, user_newyork]
        card_service.get_due_card_count.return_value = 5
        line_service.push_message.return_value = True

        # 【実際の処理実行】: UTC 00:00 (JST 09:00, EST 19:00前日) に process_notifications を呼び出す
        current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = notification_service.process_notifications(current_utc)

        # 【結果検証】: user-japan のみ通知が送信されること
        # 【期待値確認】: user-japan: JST 09:00 ≈ notification_time 09:00 → True
        #                 user-newyork: EST 19:00（前日）≈ notification_time 09:00 → False
        assert result.sent == 1  # 【確認内容】: Asia/Tokyo ユーザーのみ送信 🔵
        assert result.skipped >= 1  # 【確認内容】: America/New_York ユーザーはスキップ 🔵


# ===========================================================================
# Phase 2 追加テストケース（境界値・異常系）
# ===========================================================================


class TestShouldNotifyEdgeCases:
    """境界値テストケース"""

    # ------------------------------------------------------------------
    # TC-006: ±5分以内の精度判定（5分前、境界ギリギリ）
    # ------------------------------------------------------------------

    def test_tc006_should_notify_exactly_five_minutes_before(
        self, notification_service
    ):
        """
        【テスト目的】: 通知時刻の 5分前でも True を返すことを確認する（境界値ちょうど）
        【テスト内容】: UTC 23:55 前日 → JST 08:55。notification_time='09:00' と差分 5分ちょうど
        【期待される動作】: diff <= 5 の判定により True を返す
        🟡 NFR-V2-301: 許容範囲の境界値確認
        """
        # 【テストデータ準備】: Asia/Tokyo で 09:00 通知設定のユーザー
        user = _make_user("test-006", timezone_str="Asia/Tokyo", notification_time="09:00")

        # 【初期条件設定】: UTC 2023-12-31 23:55 = JST 2024-01-01 08:55（ちょうど 5分前）
        current_utc = datetime(2023, 12, 31, 23, 55, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: True が返ること（diff <= 5 の境界値）
        # 【期待値確認】: 差分 5分ちょうどは diff <= 5 の条件を満たす
        assert result is True  # 【確認内容】: 差分 5分は許容範囲の境界値であり True 🟡

    # ------------------------------------------------------------------
    # TC-007: UTCタイムゾーンでの通知判定
    # ------------------------------------------------------------------

    def test_tc007_should_notify_utc_timezone(self, notification_service):
        """
        【テスト目的】: タイムゾーンオフセットなし（UTC そのもの）での正しい判定を確認する
        【テスト内容】: timezone='UTC'、UTC 09:00 → ローカル 09:00。notification_time='09:00' と差分 0分
        【期待される動作】: should_notify が True を返す
        🟡 UserSettingsRequest に "UTC" が有効なタイムゾーンとして定義されている
        """
        # 【テストデータ準備】: UTC タイムゾーンで 09:00 通知設定のユーザー
        user = _make_user("test-007", timezone_str="UTC", notification_time="09:00")

        # 【初期条件設定】: UTC 09:00（タイムゾーン変換なし、そのまま 09:00）
        current_utc = datetime(2024, 1, 1, 9, 0, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: True が返ること
        # 【期待値確認】: ZoneInfo("UTC") での変換後も 09:00 と notification_time 09:00 が一致
        assert result is True  # 【確認内容】: UTC タイムゾーンでオフセットなし、差分 0分のため True 🟡

    # ------------------------------------------------------------------
    # TC-013: notification_time 未設定のデフォルト（settings に notification_time キーなし）
    # ------------------------------------------------------------------

    def test_tc013_should_notify_default_notification_time_when_missing(
        self, notification_service
    ):
        """
        【テスト目的】: settings に notification_time キーがない場合に '09:00' をデフォルトとして使用することを確認する
        【テスト内容】: settings = {"timezone": "Asia/Tokyo"}（notification_time キーなし）、UTC 00:00 → JST 09:00
        【期待される動作】: デフォルト '09:00' として判定され True を返す
        🟡 User モデルの settings デフォルト値 "09:00" から推測
        """
        # 【テストデータ準備】: notification_time キーを除外した settings を持つユーザー
        user = User(
            user_id="test-013",
            line_user_id="U1234567890abcdef1234567890abcdef",
            settings={"timezone": "Asia/Tokyo"},  # notification_time キーなし
            created_at=datetime.now(timezone.utc),
        )

        # 【初期条件設定】: UTC 00:00 = JST 09:00
        current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: True が返ること
        # 【期待値確認】: settings.get('notification_time', '09:00') が '09:00' を返す → 差分 0分
        assert result is True  # 【確認内容】: デフォルト notification_time '09:00' でJST 09:00 と一致するため True 🟡

    # ------------------------------------------------------------------
    # TC-015: 日付境界をまたぐケース（許容範囲外、23:50 → 00:01）
    # ------------------------------------------------------------------

    def test_tc015_should_notify_date_boundary_outside_tolerance(
        self, notification_service
    ):
        """
        【テスト目的】: 日付境界をまたぐ場合でも差分が 6分以上なら False を返すことを確認する
        【テスト内容】: notification_time='23:50'、ローカル時刻 00:01。補正後差分は 11分
        【期待される動作】: should_notify が False を返す（差分11分、±5分超過）
        🟡 EDGE-V2-102 の拡張：日付境界で許容範囲外の確認
        """
        # 【テストデータ準備】: America/New_York で 23:50 通知設定のユーザー
        user = _make_user(
            "test-015",
            timezone_str="America/New_York",
            notification_time="23:50",
        )

        # 【初期条件設定】: UTC 05:01 = EST 00:01（冬季 UTC-5）
        # notification_time 23:50 とローカル時刻 00:01 の単純差分は 1429分
        # diff > 720 → 1440 - 1429 = 11分（許容範囲外）
        current_utc = datetime(2024, 1, 1, 5, 1, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: False が返ること（日付境界補正後も 11分差）
        # 【期待値確認】: diff = 1440 - 1429 = 11 > 5 → False
        assert result is False  # 【確認内容】: 日付境界補正後 11分差は ±5分超過のため False 🟡

    # ------------------------------------------------------------------
    # TC-016: notification_time が 00:00（真夜中、最小値）
    # ------------------------------------------------------------------

    def test_tc016_should_notify_midnight_notification_time(
        self, notification_service
    ):
        """
        【テスト目的】: notification_time='00:00'（最小値）での正しい判定を確認する
        【テスト内容】: notification_time='00:00'、JST 00:00 に通知。UTC 15:00（前日）= JST 00:00
        【期待される動作】: should_notify が True を返す
        🟡 HH:MM の最小値。UserSettingsRequest のバリデーション 00:00 から推測
        """
        # 【テストデータ準備】: Asia/Tokyo で 00:00 通知設定のユーザー
        user = _make_user("test-016", timezone_str="Asia/Tokyo", notification_time="00:00")

        # 【初期条件設定】: UTC 15:00 = JST 00:00（翌日0時）
        current_utc = datetime(2024, 1, 1, 15, 0, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: True が返ること
        # 【期待値確認】: notif_total_min = 0, local_total_min = 0, diff = 0
        assert result is True  # 【確認内容】: 00:00 での差分 0分のため True 🟡

    # ------------------------------------------------------------------
    # TC-017: notification_time が 23:59（最大値）
    # ------------------------------------------------------------------

    def test_tc017_should_notify_late_night_notification_time(
        self, notification_service
    ):
        """
        【テスト目的】: notification_time='23:59'（最大値）での正しい判定を確認する
        【テスト内容】: notification_time='23:59'、JST 23:59 に通知。UTC 14:59 = JST 23:59
        【期待される動作】: should_notify が True を返す
        🟡 HH:MM の最大値。UserSettingsRequest のバリデーション 23:59 から推測
        """
        # 【テストデータ準備】: Asia/Tokyo で 23:59 通知設定のユーザー
        user = _make_user("test-017", timezone_str="Asia/Tokyo", notification_time="23:59")

        # 【初期条件設定】: UTC 14:59 = JST 23:59
        current_utc = datetime(2024, 1, 1, 14, 59, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: True が返ること
        # 【期待値確認】: notif_total_min = 1439, local_total_min = 1439, diff = 0
        assert result is True  # 【確認内容】: 23:59 での差分 0分のため True 🟡

    # ------------------------------------------------------------------
    # TC-018: settings が空辞書（全フィールド未設定）
    # ------------------------------------------------------------------

    def test_tc018_should_notify_empty_settings_uses_defaults(
        self, notification_service
    ):
        """
        【テスト目的】: settings が空辞書の場合にデフォルト値（Asia/Tokyo, 09:00）で判定することを確認する
        【テスト内容】: settings={}、UTC 00:00 → Asia/Tokyo デフォルトで JST 09:00
        【期待される動作】: should_notify が True を返す（全デフォルト値適用）
        🟡 DynamoDB の既存レコードで settings が空の場合の防御的処理
        """
        # 【テストデータ準備】: settings が空辞書のユーザー（DynamoDB のレガシーレコードを模擬）
        user = User(
            user_id="test-018",
            line_user_id="U1234567890abcdef1234567890abcdef",
            settings={},  # 全フィールド未設定
            created_at=datetime.now(timezone.utc),
        )

        # 【初期条件設定】: UTC 00:00（デフォルト Asia/Tokyo 適用で JST 09:00）
        current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: True が返ること（全デフォルト値 Asia/Tokyo + 09:00 で差分 0分）
        # 【期待値確認】: timezone デフォルト Asia/Tokyo、notification_time デフォルト '09:00'
        assert result is True  # 【確認内容】: 空 settings でデフォルト値適用、差分 0分のため True 🟡


# ===========================================================================
# 異常系テストケース
# ===========================================================================


class TestShouldNotifyErrorCases:
    """異常系: エラーハンドリング確認"""

    # ------------------------------------------------------------------
    # TC-008: 無効なタイムゾーン名のフォールバック
    # ------------------------------------------------------------------

    def test_tc008_should_notify_invalid_timezone_falls_back_to_default(
        self, notification_service
    ):
        """
        【テスト目的】: 無効なタイムゾーン名が設定されている場合に Asia/Tokyo にフォールバックして処理が継続することを確認する
        【テスト内容】: timezone='Invalid/Timezone'、UTC 00:00 → Asia/Tokyo フォールバックで JST 09:00
        【期待される動作】: 例外を発生させず、Asia/Tokyo として判定し True を返す
        🟡 設計文書「無効なタイムゾーンの場合は Asia/Tokyo をデフォルトとして使用」より
        """
        # 【テストデータ準備】: 不正なタイムゾーン名を持つユーザー（DynamoDB 直接書き込みを模擬）
        user = User(
            user_id="test-008",
            line_user_id="U1234567890abcdef1234567890abcdef",
            settings={
                "timezone": "Invalid/Timezone",
                "notification_time": "09:00",
            },
            created_at=datetime.now(timezone.utc),
        )

        # 【初期条件設定】: UTC 00:00（Asia/Tokyo フォールバックで JST 09:00）
        current_utc = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # 【実際の処理実行】: should_notify メソッドを呼び出す（例外が発生しないことを確認）
        # 【処理内容】: 無効なタイムゾーン名を try-except でキャッチし Asia/Tokyo にフォールバック
        result = notification_service.should_notify(user, current_utc)

        # 【結果検証】: 例外が発生せず、Asia/Tokyo フォールバックで True が返ること
        # 【期待値確認】: Asia/Tokyo でフォールバックし UTC 00:00 = JST 09:00 → notification_time 09:00 と一致
        assert result is True  # 【確認内容】: 無効 TZ は Asia/Tokyo にフォールバックし判定継続のため True 🟡

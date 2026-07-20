"""Notification service for sending review reminders."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
# 【インポート追加】: タイムゾーン変換に Python 3.9+ 標準ライブラリの zoneinfo を使用 🔵
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aws_lambda_powertools import Logger

from .user_service import UserService
from .card_service import CardService
from .line_service import LineService, LineApiError
from .flex_messages import create_reminder_message

logger = Logger()


@dataclass
class NotificationResult:
    """Result of notification processing."""

    processed: int = 0
    sent: int = 0
    skipped: int = 0
    errors: List[dict] = field(default_factory=list)


class NotificationService:
    """Service for sending review reminder notifications."""

    def __init__(
        self,
        user_service: Optional[UserService] = None,
        card_service: Optional[CardService] = None,
        line_service: Optional[LineService] = None,
    ):
        """Initialize NotificationService.

        Args:
            user_service: UserService instance.
            card_service: CardService instance.
            line_service: LineService instance.
        """
        self.user_service = user_service or UserService()
        self.card_service = card_service or CardService()
        self.line_service = line_service or LineService()

    def _resolve_timezone(self, user) -> ZoneInfo:
        """
        【機能概要】: ユーザーの settings からタイムゾーンを解決する
        【実装方針】: _local_time（ひいては should_notify / get_local_date_str /
        get_claim_date_str）で同一のタイムゾーン解決ロジックを共有するために切り出したヘルパー。
        無効なタイムゾーン名は Asia/Tokyo にフォールバックする。
        🔵 REQ-V2-041: タイムゾーン考慮（既存実装からの抽出、ロジック変更なし）
        Args:
            user: User オブジェクト（settings に timezone を持つ）
        Returns:
            ZoneInfo: 解決されたタイムゾーンオブジェクト
        """
        # 【タイムゾーン取得】: settings 辞書から timezone を取得。なければ Asia/Tokyo をデフォルトとして使用 🔵
        tz_name = user.settings.get("timezone", "Asia/Tokyo") if user.settings else "Asia/Tokyo"

        # 【タイムゾーン変換準備】: ZoneInfo でタイムゾーンオブジェクトを生成。無効な名前は Asia/Tokyo にフォールバック 🟡
        try:
            return ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, Exception):
            # 【エラーハンドリング】: 無効なタイムゾーン名の場合は Asia/Tokyo にフォールバックして処理を継続 🟡
            logger.warning(f"Invalid timezone '{tz_name}', falling back to Asia/Tokyo")
            return ZoneInfo("Asia/Tokyo")

    def _local_time(self, user, current_utc: datetime) -> datetime:
        """
        【機能概要】: ユーザーのタイムゾーンでの現在時刻（ローカル time）を返す共通ヘルパー
        【実装方針】: should_notify / get_local_date_str / get_claim_date_str で
        重複していた「タイムゾーン解決 → astimezone 変換」を集約する。
        Args:
            user: User オブジェクト（settings に timezone を持つ）
            current_utc: 現在の UTC 日時（timezone-aware）
        Returns:
            datetime: ユーザーのローカルタイムゾーンに変換された日時
        """
        user_tz = self._resolve_timezone(user)
        return current_utc.astimezone(user_tz)

    def _parse_notification_time(self, user) -> Tuple[int, int]:
        """
        【機能概要】: ユーザーの settings から notification_time (HH:MM) をパースする
        【実装方針】: should_notify と get_claim_date_str で同一のパースロジック
        （デフォルト '09:00'、無効値は 09:00 にフォールバック）を共有するために切り出したヘルパー。
        Args:
            user: User オブジェクト（settings に notification_time を持つ）
        Returns:
            Tuple[int, int]: (時, 分)
        """
        # 【notification_time 取得】: settings 辞書から通知時刻を取得。なければ '09:00' をデフォルトとして使用 🟡
        notification_time = user.settings.get("notification_time", "09:00") if user.settings else "09:00"

        # 【時刻パース】: HH:MM 形式の文字列を時・分に変換する 🔵
        try:
            notif_hour, notif_min = map(int, notification_time.split(":"))
        except (ValueError, AttributeError):
            logger.warning(
                f"Invalid notification_time format '{notification_time}' for user, "
                "falling back to 09:00"
            )
            notif_hour, notif_min = 9, 0
        return notif_hour, notif_min

    def get_local_date_str(self, user, current_utc: datetime) -> str:
        """
        【機能概要】: ユーザーのタイムゾーンにおけるローカル日付文字列 (YYYY-MM-DD) を取得する
        【用途】: 現在時刻がユーザーのタイムゾーンでどの暦日に属するかを返す単純なユーティリティ。
        冪等性キー（claim 日付）としては get_claim_date_str を使うこと（このメソッドは
        notification_time が日付境界付近にある場合の occurrence 補正を含まない）。
        Args:
            user: User オブジェクト（settings に timezone を持つ）
            current_utc: 現在の UTC 日時（timezone-aware）
        Returns:
            str: ユーザーのローカル日付 (YYYY-MM-DD 形式)
        """
        return self._local_time(user, current_utc).strftime("%Y-%m-%d")

    def get_claim_date_str(self, user, current_utc: datetime) -> str:
        """
        【機能概要】: 冪等性キー（last_notified_date の claim に使う日付）として、
        should_notify がマッチ判定に使う「notification_time の occurrence（実施回）」が
        属するローカル日付を返す。
        【Medium-1 再発修正】: get_local_date_str（= 現在時刻のローカル日付）を claim キーに
        使うと、notification_time がローカル日付境界付近（例: 00:00, 23:58 等）の場合に、
        「23:55 ローカル」と「翌 00:00 ローカル」のように隣接する 2 回の実行がどちらも
        ±5分マッチしつつ異なる暦日の claim キーとなり、二重送信が再発する
        （2024-01-04T14:55Z と 15:00Z が good example: Asia/Tokyo, notification_time=00:00 で
        両方 should_notify=True になるが、現在時刻のローカル日付は 2024-01-04 / 2024-01-05 と異なる）。
        本メソッドは should_notify と同じ 720分閾値の日付境界補正を用いて「マッチ相手の
        occurrence」が前日・当日・翌日のどれかを判定し、その occurrence の暦日を返すことで、
        隣接する 2 回の実行が同じ claim キーになるようにする。
        🔵 Medium-1: ローカル日付境界での二重送信の修正
        Args:
            user: User オブジェクト（settings に timezone と notification_time を持つ）
            current_utc: 現在の UTC 日時（timezone-aware）
        Returns:
            str: claim に使う日付 (YYYY-MM-DD 形式)
        """
        local_time = self._local_time(user, current_utc)
        notif_hour, notif_min = self._parse_notification_time(user)

        notif_total_min = notif_hour * 60 + notif_min
        local_total_min = local_time.hour * 60 + local_time.minute

        # 【occurrence 判定】: should_notify の diff 補正（abs → 720分超なら 1440-diff）と等価な
        # 符号付き delta を使い、マッチする occurrence が前日/当日/翌日のどれかを判定する。
        # delta > 720  → 現在時刻は当日の終わり近くで notification_time は当日の早い時刻
        #                （例: local=23:55, notif=00:00）→ マッチ相手は「翌日」の occurrence
        # delta < -720 → 現在時刻は当日の始まり近くで notification_time は当日の遅い時刻
        #                （例: local=00:02, notif=23:58）→ マッチ相手は「前日」の occurrence
        # それ以外     → マッチ相手は「当日」の occurrence
        delta = local_total_min - notif_total_min
        base_date = local_time.date()
        if delta > 720:
            claim_date = base_date + timedelta(days=1)
        elif delta < -720:
            claim_date = base_date - timedelta(days=1)
        else:
            claim_date = base_date

        return claim_date.strftime("%Y-%m-%d")

    def should_notify(self, user, current_utc: datetime) -> bool:
        """
        【機能概要】: ユーザーのローカル時刻が notification_time と一致するかを判定する
        【実装方針】: settings 辞書から timezone と notification_time を取得し、UTC→ローカル変換後に ±5分精度で比較する
        【テスト対応】: TC-001〜TC-008, TC-011〜TC-018 を通すための最小実装
        🔵 REQ-V2-041, REQ-V2-042, NFR-V2-301: タイムゾーン考慮 + 時刻一致判定 + ±5分精度
        Args:
            user: User オブジェクト（settings に timezone と notification_time を持つ）
            current_utc: 現在の UTC 日時（timezone-aware）
        Returns:
            bool: ローカル時刻が notification_time の ±5分以内なら True
        """
        # 【UTC→ローカル変換】: ユーザーのローカル時刻を計算する 🔵
        local_time = self._local_time(user, current_utc)

        # 【notification_time 取得・パース】: get_claim_date_str と共通のヘルパーを使用 🔵
        notif_hour, notif_min = self._parse_notification_time(user)
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

    def process_notifications(self, current_time: datetime) -> NotificationResult:
        """Process and send notifications to all eligible users.

        Args:
            current_time: Current time for determining due cards.

        Returns:
            NotificationResult with processing statistics.
        """
        result = NotificationResult()
        # 【ログ用の日付】: 実行ログ表示用の UTC 日付。冪等性キー（claim）にはユーザーごとの
        # ローカル日付を使うため、この値はログ出力にのみ使用する 🔵
        utc_date_str = current_time.strftime("%Y-%m-%d")

        logger.info(f"Starting notification processing for {utc_date_str}")

        # Get all LINE-linked users
        try:
            linked_users = self.user_service.get_linked_users()
            logger.info(f"Found {len(linked_users)} linked users")
        except Exception as e:
            logger.error(f"Failed to get linked users: {e}")
            result.errors.append({
                "type": "get_users_failed",
                "error": str(e),
            })
            return result

        # Process each user
        for user in linked_users:
            result.processed += 1

            try:
                # LINE 未連携ユーザーには push できない（クエリ前提だが防御的にガード）
                if not user.line_user_id:
                    logger.warning(f"User {user.user_id} has no line_user_id; skipping")
                    result.skipped += 1
                    continue

                # 【Medium-1 修正】: 冪等性キーは「マッチする notification_time の occurrence」が
                # 属するローカル日付（get_claim_date_str）を使用する。
                # UTC 日付や単純な現在時刻のローカル日付をそのまま使うと、UTC 日付境界や
                # ローカル日付境界（notification_time が 00:00 や 23:58 等の場合）をまたぐ
                # 隣接する 2 回の実行が別々の claim キーとなり、二重通知が発生してしまう。
                claim_date_str = self.get_claim_date_str(user, current_time)

                # Check if already notified today (in user's local timezone)
                if user.last_notified_date == claim_date_str:
                    logger.debug(f"User {user.user_id} already notified today")
                    result.skipped += 1
                    continue

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

                # Check if user has due cards
                due_count = self.card_service.get_due_card_count(
                    user.user_id, before=current_time
                )

                if due_count == 0:
                    logger.debug(f"User {user.user_id} has no due cards")
                    result.skipped += 1
                    continue

                # 【claim → push 順序化（N-8）】: push の「前」に last_notified_date を claim する。
                # update_last_notified_date は ConditionExpression 付きで、当日分が未設定の場合のみ
                # True を返す。並行実行（スケジューラ二重起動等）では先に claim した実行だけが
                # push に進み、二重通知を根本から防ぐ。
                # 【Medium-1 修正】: claim キーは occurrence ベースのローカル日付（claim_date_str）を使用する。
                claimed = self.user_service.update_last_notified_date(
                    user.user_id, claim_date_str
                )
                if not claimed:
                    # 別実行が先に claim 済み（= 当日分は既に処理されている）→ スキップ
                    logger.debug(f"User {user.user_id} already claimed by another run")
                    result.skipped += 1
                    continue

                # Send push message
                # 【push 失敗時に claim を戻さない設計判断】:
                # LINE push の失敗は大半がブロック等の恒久エラーであり、claim を戻すと
                # 後続実行が再度 push を試みてリトライストームを招く。トランジェントな失敗で
                # その日の通知が 1 回失われることは許容し、claim はそのまま保持する。
                message = create_reminder_message(due_count)
                self.line_service.push_message(user.line_user_id, [message])

                result.sent += 1
                logger.info(
                    f"Sent notification to user {user.user_id}: {due_count} cards due"
                )

            except LineApiError as e:
                # LINE API error (e.g., user blocked the bot)
                logger.warning(f"Failed to send to user {user.user_id}: {e}")
                result.errors.append({
                    "user_id": user.user_id,
                    "line_user_id": user.line_user_id[:8] + "..." if user.line_user_id else None,
                    "error_type": "line_api_error",
                    "error": str(e),
                })
            except Exception as e:
                # Other errors
                logger.error(f"Error processing user {user.user_id}: {e}")
                result.errors.append({
                    "user_id": user.user_id,
                    "error_type": type(e).__name__,
                    "error": str(e),
                })

        logger.info(
            f"Notification processing complete: "
            f"processed={result.processed}, sent={result.sent}, "
            f"skipped={result.skipped}, errors={len(result.errors)}"
        )

        return result

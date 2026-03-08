"""Notification service for sending review reminders."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
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
        # 【タイムゾーン取得】: settings 辞書から timezone を取得。なければ Asia/Tokyo をデフォルトとして使用 🔵
        tz_name = user.settings.get("timezone", "Asia/Tokyo") if user.settings else "Asia/Tokyo"

        # 【タイムゾーン変換準備】: ZoneInfo でタイムゾーンオブジェクトを生成。無効な名前は Asia/Tokyo にフォールバック 🟡
        try:
            user_tz = ZoneInfo(tz_name)
        except (ZoneInfoNotFoundError, Exception):
            # 【エラーハンドリング】: 無効なタイムゾーン名の場合は Asia/Tokyo にフォールバックして処理を継続 🟡
            logger.warning(f"Invalid timezone '{tz_name}', falling back to Asia/Tokyo")
            user_tz = ZoneInfo("Asia/Tokyo")

        # 【UTC→ローカル変換】: ユーザーのローカル時刻を計算する 🔵
        local_time = current_utc.astimezone(user_tz)

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
        today_str = current_time.strftime("%Y-%m-%d")

        logger.info(f"Starting notification processing for {today_str}")

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
                # Check if already notified today
                if user.last_notified_date == today_str:
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

                # Send push message
                message = create_reminder_message(due_count)
                self.line_service.push_message(user.line_user_id, [message])

                # Update last notified date
                self.user_service.update_last_notified_date(user.user_id, today_str)

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

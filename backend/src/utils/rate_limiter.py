"""AI エンドポイント用のユーザー単位レート制限（固定ウィンドウカウンタ）。

認証済みユーザーによる AI 系エンドポイントの高頻度呼び出しを抑止する
（Bedrock 課金の急増と ReservedConcurrentExecutions の圧迫の防止）。
DynamoDB の ADD（アトミックインクリメント）+ TTL による固定ウィンドウ方式。

設計方針:
- fail-open: レート制限テーブルへのアクセス失敗時は制限をスキップして通す。
  レート制限は防御層でありコア機能ではないため、可用性を優先する。
- RATE_LIMITS_TABLE 未設定（ローカル開発・テスト等）では何もしない。
- ウィンドウとキーは `{user_id}#{category}#{window_start}` の固定ウィンドウ。
  厳密なスライディングウィンドウではないが、コスト急増防止の目的には十分。
"""

import os
import time
from typing import Any, Optional

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from utils.dynamodb_client import get_dynamodb_resource

logger = Logger()

DEFAULT_LIMIT = 30
DEFAULT_WINDOW_SECONDS = 300

_table: Optional[Any] = None
_table_name: Optional[str] = None


class RateLimitExceededError(Exception):
    """ユーザーがウィンドウ内の許容リクエスト数を超過した。"""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            f"Rate limit exceeded; retry after {retry_after_seconds}s"
        )
        self.retry_after_seconds = retry_after_seconds


def _get_table(table_name: str) -> Any:
    """レート制限テーブルを取得する（Lambda コンテナ内でキャッシュ）。"""
    global _table, _table_name
    if _table is None or _table_name != table_name:
        _table = get_dynamodb_resource().Table(table_name)
        _table_name = table_name
    return _table


def enforce_rate_limit(user_id: str, category: str = "ai") -> None:
    """ユーザーのリクエストをカウントし、上限超過なら例外を送出する。

    Args:
        user_id: システムユーザー ID。
        category: レート制限のバケット名（既定は AI 系共通の "ai"）。

    Raises:
        RateLimitExceededError: ウィンドウ内の上限を超過した場合。

    環境変数:
        RATE_LIMITS_TABLE: カウンタ用 DynamoDB テーブル名。未設定なら制限なし。
        RATE_LIMIT_ENABLED: "false" で無効化（既定は有効）。
        AI_RATE_LIMIT_PER_WINDOW: ウィンドウあたりの許容リクエスト数（既定 30）。
        AI_RATE_LIMIT_WINDOW_SECONDS: ウィンドウ幅秒（既定 300）。
    """
    table_name = os.environ.get("RATE_LIMITS_TABLE", "")
    if not table_name:
        return
    if os.environ.get("RATE_LIMIT_ENABLED", "true").strip().lower() in ("false", "0"):
        return

    try:
        limit = int(os.environ.get("AI_RATE_LIMIT_PER_WINDOW", DEFAULT_LIMIT))
        window = int(
            os.environ.get("AI_RATE_LIMIT_WINDOW_SECONDS", DEFAULT_WINDOW_SECONDS)
        )
    except ValueError:
        limit, window = DEFAULT_LIMIT, DEFAULT_WINDOW_SECONDS
    if limit <= 0 or window <= 0:
        return

    now = int(time.time())
    window_start = now - (now % window)
    key = f"{user_id}#{category}#{window_start}"

    try:
        response = _get_table(table_name).update_item(
            Key={"pk": key},
            # ADD はアトミック。TTL はウィンドウ終了後の清掃用（2 ウィンドウ分残す）。
            UpdateExpression="ADD #c :one SET #ttl = if_not_exists(#ttl, :ttl)",
            ExpressionAttributeNames={"#c": "request_count", "#ttl": "ttl"},
            ExpressionAttributeValues={
                ":one": 1,
                ":ttl": window_start + window * 2,
            },
            ReturnValues="ALL_NEW",
        )
        current = int(response["Attributes"]["request_count"])
    except (ClientError, KeyError, TypeError, ValueError) as e:
        # fail-open: カウンタ更新に失敗してもリクエストは通す
        logger.warning(
            "Rate limit check failed; allowing request (fail-open)",
            extra={"user_id": user_id, "category": category, "error": str(e)},
        )
        return

    if current > limit:
        retry_after = max(window_start + window - now, 1)
        logger.warning(
            "Rate limit exceeded",
            extra={
                "user_id": user_id,
                "category": category,
                "count": current,
                "limit": limit,
                "retry_after_seconds": retry_after,
            },
        )
        raise RateLimitExceededError(retry_after)

"""サインアップ許可リスト判定ロジック (signup-allowlist)。

``auth.pre_signup.handler`` から呼び出され、``SignupAllowlistTable`` の照会
（approved/pending の判定）と pending 記録を担う。
設計: docs/design/signup-allowlist/architecture.md #2。

タイムアウト方針:
    Cognito は PreSignUp トリガーの応答を最大 5 秒しか待たない（変更不可・無応答なら
    計 3 回まで再試行）。DynamoDB が劣化していても Timeout (5s) 以内に例外送出が完了
    するよう、boto3 リソースは botocore ``Config`` で connect/read タイムアウトを
    それぞれ約 1 秒・リトライ最大 1 回に絞って生成する（設計レビュー A-5 / B-4）。
"""

from __future__ import annotations

import os
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import boto3
from aws_lambda_powertools import Logger
from botocore.config import Config
from botocore.exceptions import ClientError

logger = Logger()

STATUS_APPROVED = "approved"
STATUS_PENDING = "pending"

# pending レコードの保持期間。approved には ttl を付けない（設計 #1）。
_PENDING_TTL_DAYS = 30

# display_name は攻撃者制御値（LINE の name 属性）なので、承認判断の根拠にしない
# （設計レビュー B-6）。保存前に長さを制限する。
_DISPLAY_NAME_MAX_LENGTH = 100

# Cognito のトリガー応答制限 (5 秒) 内に確実に応答するための短いタイムアウト。
_BOTO_CONFIG = Config(
    connect_timeout=1,
    read_timeout=1,
    retries={"max_attempts": 1},
)

_resource: Optional[Any] = None


def _get_table(table_name: Optional[str] = None) -> Any:
    """許可リストテーブルの boto3 Table を取得する（Lambda コンテナ内で boto3 リソースをキャッシュ）。"""
    global _resource
    if _resource is None:
        # utils/dynamodb_client.get_dynamodb_resource() をあえて使わない: 共通ファクトリは
        # デフォルトの boto3 タイムアウト/リトライ設定のままリソースを生成するが、本関数は
        # Cognito PreSignUp トリガーの 5 秒応答制限に収める必要があるため、専用の短い
        # connect/read タイムアウト + リトライ回数を指定した Config（`_BOTO_CONFIG`）で
        # 個別に生成する。
        _resource = boto3.resource("dynamodb", config=_BOTO_CONFIG)
    name = table_name or os.environ.get("ALLOWLIST_TABLE", "")
    return _resource.Table(name)


def sanitize_display_name(display_name: Optional[str]) -> str:
    """display_name をサニタイズする（制御文字除去 + 最大文字数切り詰め）。

    Unicode カテゴリ Cc（制御文字）/ Cf（書式文字）を除去する。攻撃者制御値のため、
    承認判断の根拠にはしない（アウトオブバンドの本人確認 + created_at 突合で行う。
    設計レビュー B-6）。

    Args:
        display_name: サニタイズ対象の文字列（None/空文字は空文字を返す）。

    Returns:
        制御文字除去 + 最大 100 文字に切り詰めた文字列。
    """
    if not display_name:
        return ""
    cleaned = "".join(
        ch for ch in display_name if unicodedata.category(ch) not in ("Cc", "Cf")
    )
    return cleaned[:_DISPLAY_NAME_MAX_LENGTH]


def get_status(identifier: str) -> Optional[str]:
    """許可リストから identifier のステータスを取得する。

    Args:
        identifier: ``email#<address>`` または ``idp#<userName>`` 形式の識別子。

    Returns:
        レコードが存在すれば ``status`` 属性の値（``approved`` / ``pending``）、
        存在しなければ None。

    Raises:
        ClientError: DynamoDB 呼び出しに失敗した場合（フェイルクローズ。呼び出し側で
            そのまま送出する）。

    Note:
        許可判定はアクセス制御に使われるため ``ConsistentRead=True`` で強整合性読み取り
        を行う（既定の結果整合性のままだと ``allowlist-remove`` 直後に古い approved が
        返り、削除済み識別子の登録を許可しうる）。
    """
    table = _get_table()
    response = table.get_item(Key={"identifier": identifier}, ConsistentRead=True)
    item = response.get("Item")
    if not item:
        return None
    status = item.get("status")
    return str(status) if status is not None else None


def record_pending(identifier: str, display_name: Optional[str] = None) -> None:
    """identifier を pending として記録する（未登録 LINE ユーザーの承認待ち登録）。

    既存レコード（approved または既存 pending）がある場合は上書きしない
    （``ConditionExpression: attribute_not_exists(identifier)``）。条件不成立
    （``ConditionalCheckFailedException``）は Cognito のトリガー再試行に対しても
    冪等になるよう握りつぶす。それ以外の DynamoDB 例外はそのまま送出する
    （フェイルクローズ）。

    Args:
        identifier: ``idp#<userName>`` 形式の識別子。
        display_name: LINE の ``name`` 属性など、参考情報として保存する表示名
            （サニタイズして保存する）。

    Raises:
        ClientError: ConditionalCheckFailedException 以外の DynamoDB エラー。
    """
    table = _get_table()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    item = {
        "identifier": identifier,
        "status": STATUS_PENDING,
        "display_name": sanitize_display_name(display_name),
        "created_at": now_iso,
        "updated_at": now_iso,
        "ttl": int((now + timedelta(days=_PENDING_TTL_DAYS)).timestamp()),
    }

    try:
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(identifier)",
        )
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            logger.info(
                "Pending record already exists; not overwritten",
                extra={"decision": "pending_not_overwritten"},
            )
            return
        raise

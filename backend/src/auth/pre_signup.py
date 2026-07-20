"""Cognito PreSignUp トリガー (signup-allowlist)。

メールセルフサインアップ / LINE federation（初回サインイン） / AdminCreateUser の
3 経路すべてで発火し、サインアップの入口を DynamoDB 許可リスト
（``services.allowlist_service``）で一元的に遮断する。
設計: docs/design/signup-allowlist/architecture.md #2。

フェイルクローズ:
    例外はそのまま送出する（DynamoDB 障害・未知の triggerSource を含む）。
    Cognito は PreSignUp トリガーが例外を投げるとユーザー作成自体を中断するため、
    拒否された試行は UNCONFIRMED ユーザーとしても残らない。
    ``autoConfirmUser`` / ``autoVerifyEmail`` は操作しない（既定の確認・検証フローを
    維持する）。

内部エラーメッセージの非露出:
    DynamoDB の ClientError やタイムアウト等インフラ起因の例外がそのまま Cognito に
    渡ると、native 経路では Hosted UI に生のエラーメッセージ（呼び出した AWS API 名を
    含む等）が表示されうる。``handler`` は内部処理を ``_handle`` に委譲し、全体を
    try/except で包む。意図的な拒否（:class:`SignupNotAllowedError`）はそのまま
    送出し、それ以外の予期しない例外は ``logger.exception`` でサーバー側にのみ記録した
    上で、一般文言（``REJECT_MESSAGE``）のみを持つ :class:`SignupNotAllowedError` に
    変換して送出する（フェイルクローズは維持しつつ内部情報は含めない）。
"""

from __future__ import annotations

from typing import Any, Dict

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from services.allowlist_service import STATUS_APPROVED, get_status, record_pending

logger = Logger()

_TRIGGER_ADMIN_CREATE_USER = "PreSignUp_AdminCreateUser"
_TRIGGER_SIGN_UP = "PreSignUp_SignUp"
_TRIGGER_EXTERNAL_PROVIDER = "PreSignUp_ExternalProvider"

# 全経路共通の一般文言。存在有無（許可リストにあるか / アカウントが既にあるか）を
# 漏らさない（設計レビュー B-1）。native 経路では Hosted UI に
# "PreSignUp failed with error <このメッセージ>." の形式で表示されるが、この前置形式に
# 依存するロジックは組まない。federated 経路ではコールバック URL の
# error_description リダイレクトで返る（フロントには届かない。設計 #2 参照）。
REJECT_MESSAGE = (
    "現在、新規登録は招待制です。利用を希望する場合は管理者に連絡してください。"
)


class SignupNotAllowedError(Exception):
    """サインアップを拒否するための専用例外。

    Cognito にはこの例外のメッセージ（常に ``REJECT_MESSAGE``）のみが渡る。DynamoDB の
    ClientError 等インフラ起因の例外は ``handler`` 内でこの型に変換してから送出し、
    内部のエラーメッセージ（AWS API 名・エラーコード等）が Hosted UI 等に露出しない
    ようにする。
    """


def _normalize_email(email: str) -> str:
    """メールアドレスを identifier 用に正規化する（trim + 小文字化）。"""
    return email.strip().lower()


@logger.inject_lambda_context
def handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """Cognito PreSignUp トリガーのエントリポイント。

    Args:
        event: Cognito PreSignUp トリガーイベント。
        context: Lambda コンテキスト。

    Returns:
        許可された場合は受信した event をそのまま返す
        （autoConfirmUser / autoVerifyEmail は操作しない）。

    Raises:
        SignupNotAllowedError: サインアップを拒否する場合（フェイルクローズ）。
            DynamoDB 例外や未知の triggerSource など予期しない例外もすべてこの型に
            変換されて送出される（生の内部エラーメッセージは Cognito に渡さず、
            サーバー側のログにのみ記録する）。
    """
    try:
        return _handle(event, context)
    except SignupNotAllowedError:
        raise
    except Exception:
        logger.exception("Unexpected error in PreSignUp handler")
        raise SignupNotAllowedError(REJECT_MESSAGE) from None


def _handle(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
    """PreSignUp トリガーの本体ロジック（例外の非露出処理は ``handler`` 側で行う）。"""
    trigger_source = event.get("triggerSource", "")

    if trigger_source == _TRIGGER_ADMIN_CREATE_USER:
        # 管理者による作成は承認済みとみなす（常に許可）。
        _log_decision(trigger_source, "allowed")
        return event

    if trigger_source == _TRIGGER_SIGN_UP:
        email = event.get("request", {}).get("userAttributes", {}).get("email", "")
        identifier = "email#" + _normalize_email(email)
        if get_status(identifier) == STATUS_APPROVED:
            _log_decision(trigger_source, "allowed")
            return event
        # native（メール）経路は記録しない: メールアドレスは事前に分かるため pending
        # 不要で、記録すると probe によりテーブルが汚染される（設計レビュー B-1 関連）。
        _log_decision(trigger_source, "rejected")
        raise SignupNotAllowedError(REJECT_MESSAGE)

    if trigger_source == _TRIGGER_EXTERNAL_PROVIDER:
        user_name = event.get("userName", "")
        identifier = "idp#" + user_name.lower()
        if get_status(identifier) == STATUS_APPROVED:
            _log_decision(trigger_source, "allowed")
            return event
        display_name = (
            event.get("request", {}).get("userAttributes", {}).get("name", "")
        )
        record_pending(identifier, display_name=display_name)
        _log_decision(trigger_source, "pending_recorded")
        raise SignupNotAllowedError(REJECT_MESSAGE)

    # 未知の triggerSource はフェイルクローズ。
    _log_decision(trigger_source, "rejected")
    raise SignupNotAllowedError(REJECT_MESSAGE)


def _log_decision(trigger_source: str, decision: str) -> None:
    """構造化ログで triggerSource と判定結果を記録する。

    メールアドレス・LINE userName 等の生値はログに出さない
    （許可リスト変更操作は CloudTrail に残らないため、この判定ログが実質唯一の証跡。
    設計レビュー B-8）。
    """
    logger.info(
        "PreSignUp decision",
        extra={"trigger_source": trigger_source, "decision": decision},
    )

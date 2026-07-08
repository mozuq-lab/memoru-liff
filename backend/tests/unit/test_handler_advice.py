"""POST /advice エンドポイントのテスト（ai-async-jobs 版）。

advice_handler Lambda ハンドラーのテストケース。
構造的前提:
- advice_handler は独立 Lambda 関数（app/APIGatewayHttpResolver 経由ではない）
- 生の API Gateway HTTP API v2 イベントを直接受け取る
- レスポンスは Lambda プロキシ統合形式の dict（statusCode, headers, body）

ai-async-jobs: ジョブ作成は非冪等のため GET → POST に変更された。
ハンドラーは同期検証（認証・language）後に submit_ai_job でジョブを登録し
202 を返すだけになった。レビューサマリー集計・AI 呼び出し・レスポンス形状・
AI エラーマッピングの検証は
tests/unit/test_ai_job_executors.py（execute_advice）と
tests/unit/test_ai_job_errors.py（classify_ai_job_error）に移設した。
"""

import json
from unittest.mock import patch

import pytest

from api.handler import advice_handler

# submit_ai_job モックの戻り値（作成直後の queued ジョブレコード相当）
SUBMIT_RESULT = {"job_id": "aijob_t", "job_type": "advice", "status": "queued"}


# =============================================================================
# テスト共通ヘルパー
# =============================================================================


def _make_advice_event(
    user_id: str = "test-user-id",
    query_params: dict | None = None,
    authorizer: dict | None = None,
) -> dict:
    """advice_handler 用の API Gateway HTTP API v2 イベントを構築する。

    Args:
        user_id: JWT claims の sub クレーム。
        query_params: クエリストリングパラメータ（language 等）。
        authorizer: リクエストコンテキストの authorizer。None の場合は標準 JWT 形式。

    Returns:
        API Gateway HTTP API v2 形式のイベント辞書。
    """
    if authorizer is None:
        authorizer = {
            "jwt": {
                "claims": {"sub": user_id},
                "scopes": ["openid", "profile"],
            }
        }
    event = {
        "version": "2.0",
        "routeKey": "POST /advice",
        "rawPath": "/advice",
        "rawQueryString": "",
        "pathParameters": None,
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api-id",
            "authorizer": authorizer,
            "http": {"method": "POST"},
            "requestId": "test-request-id",
            "routeKey": "POST /advice",
            "stage": "$default",
        },
        "headers": {"content-type": "application/json"},
        "isBase64Encoded": False,
    }
    if query_params:
        event["queryStringParameters"] = query_params
    return event


# =============================================================================
# 共通フィクスチャ
# =============================================================================


@pytest.fixture
def mock_submit():
    """submit_ai_job のモック。作成直後の queued ジョブレコードを返す。

    パッチ対象: api.handler.submit_ai_job（インポートされた関数）。
    """
    with patch("api.handler.submit_ai_job") as mock:
        mock.return_value = dict(SUBMIT_RESULT)
        yield mock


# =============================================================================
# カテゴリ A: 認証テスト
# =============================================================================


class TestAdviceHandlerAuth:
    """認証関連テスト。認証失敗時はジョブを submit しない（同期 401）。"""

    def test_advice_returns_401_when_no_authorizer(self, lambda_context, mock_submit):
        """authorizer が空の場合に HTTP 401 を返すことを確認."""
        event = _make_advice_event(authorizer={})

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert body["error"] == "Unauthorized"
        mock_submit.assert_not_called()

    def test_advice_returns_401_when_no_sub_claim(self, lambda_context, mock_submit):
        """JWT claims に sub がない場合に HTTP 401 を返すことを確認."""
        authorizer = {"jwt": {"claims": {"iss": "https://keycloak.example.com"}}}
        event = _make_advice_event(authorizer=authorizer)

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert body["error"] == "Unauthorized"
        mock_submit.assert_not_called()

    def test_advice_extracts_user_id_from_jwt_claims(self, lambda_context, mock_submit):
        """JWT claims.sub から抽出した user_id が submit に渡ることを確認."""
        event = _make_advice_event(user_id="user-abc-123")

        advice_handler(event, lambda_context)

        assert mock_submit.call_args.kwargs["user_id"] == "user-abc-123"


# =============================================================================
# カテゴリ B: ジョブ submit テスト
# =============================================================================


class TestAdviceHandlerSubmit:
    """submit_ai_job の呼び出し引数（user_id / job_type / payload）を検証する。

    旧「データフローテスト」の後継。ReviewSummary の集計・AI への伝播は
    test_ai_job_executors.py::TestExecuteAdvice が担保する。
    """

    def test_advice_submits_job_with_correct_args(self, lambda_context, mock_submit):
        """submit_ai_job が user_id / job_type / payload 一式で 1 回呼ばれることを確認."""
        event = _make_advice_event()

        advice_handler(event, lambda_context)

        mock_submit.assert_called_once_with(
            user_id="test-user-id",
            job_type="advice",
            payload={"language": "ja"},
        )

    def test_advice_passes_language_param_to_payload(self, lambda_context, mock_submit):
        """language=en が payload に渡ることを確認."""
        event = _make_advice_event(query_params={"language": "en"})

        advice_handler(event, lambda_context)

        assert mock_submit.call_args.kwargs["payload"] == {"language": "en"}

    def test_advice_uses_default_language_ja(self, lambda_context, mock_submit):
        """queryStringParameters なしでデフォルト language=ja を確認."""
        event = _make_advice_event()  # query_params なし

        advice_handler(event, lambda_context)

        assert mock_submit.call_args.kwargs["payload"] == {"language": "ja"}

    def test_advice_returns_400_when_language_is_invalid(
        self, lambda_context, mock_submit
    ):
        """language が ja/en 以外の場合に HTTP 400 を返すことを確認（許可リスト検証）."""
        event = _make_advice_event(query_params={"language": "xx"})

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"] == "Unsupported language. Use 'ja' or 'en'."
        mock_submit.assert_not_called()


# =============================================================================
# カテゴリ C: 正常系レスポンステスト（202 Accepted）
# =============================================================================


class TestAdviceHandlerAccepted:
    """202 レスポンスの検証（旧・正常系 200 レスポンステストの後継）。

    completed 時の result 形状（LearningAdviceResponse 互換）は
    test_ai_job_executors.py と tests/integration/test_integration.py が担保する。
    """

    def test_advice_returns_202(self, lambda_context, mock_submit):
        """正常系で HTTP 202 Accepted が返ることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 202

    def test_advice_accepted_body_has_job_fields(self, lambda_context, mock_submit):
        """202 ボディが {job_id, job_type, status} のみを含むことを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        body = json.loads(response["body"])
        assert body == {
            "job_id": "aijob_t",
            "job_type": "advice",
            "status": "queued",
        }

    def test_advice_accepted_response_is_json(self, lambda_context, mock_submit):
        """Content-Type が application/json であることを確認."""
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 202
        assert response["headers"]["Content-Type"] == "application/json"


# =============================================================================
# カテゴリ D: 予期しないエラーテスト
# =============================================================================


class TestAdviceHandlerUnexpectedErrors:
    """submit 段階での予期しない例外の汎用ハンドリングを検証する。

    AI 例外のマッピング（504/429/503/500）と ReviewService 例外は
    executor + classify_ai_job_error に移設した。
    """

    def test_advice_returns_500_when_submit_fails_unexpectedly(
        self, lambda_context, mock_submit
    ):
        """submit_ai_job が予期しない例外を送出した場合に HTTP 500 を返すことを確認."""
        mock_submit.side_effect = RuntimeError("unexpected")
        event = _make_advice_event()

        response = advice_handler(event, lambda_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "Internal Server Error"


# =============================================================================
# カテゴリ E: ロギングテスト
# =============================================================================


class TestAdviceHandlerLogging:
    """submit 時のリクエストロギングを検証する。

    詳細な構造化フィールドの検証は tests/unit/test_structured_logging.py。
    """

    def test_advice_logs_request_info(self, lambda_context, mock_submit):
        """submit 受付時に logger.info で user_id を含む情報を記録することを確認."""
        event = _make_advice_event(user_id="log-test-user")

        with patch("api.handler.logger") as mock_logger:
            advice_handler(event, lambda_context)

        info_calls_str = str(mock_logger.info.call_args_list)
        assert "log-test-user" in info_calls_str

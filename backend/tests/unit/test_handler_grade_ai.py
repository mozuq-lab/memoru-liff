"""POST /reviews/{card_id}/grade-ai エンドポイントのテスト（ai-async-jobs 版）。

grade_ai_handler Lambda ハンドラーのテストケース。
構造的前提:
- grade_ai_handler は独立 Lambda 関数（app/APIGatewayHttpResolver 経由ではない）
- 生の API Gateway HTTP API v2 イベントを直接受け取る
- レスポンスは Lambda プロキシ統合形式の dict（statusCode, headers, body）

ai-async-jobs: ハンドラーは同期検証（認証・バリデーション・カード所有権）後に
submit_ai_job でジョブを登録し 202 を返すだけになった。AI 採点の実行・
レスポンス形状・AI エラーマッピングの検証は
tests/unit/test_ai_job_executors.py（execute_grade_ai）と
tests/unit/test_ai_job_errors.py（classify_ai_job_error）に移設した。
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from api.handler import grade_ai_handler
from services.card_service import CardNotFoundError

# submit_ai_job モックの戻り値（作成直後の queued ジョブレコード相当）
SUBMIT_RESULT = {"job_id": "aijob_t", "job_type": "grade_ai", "status": "queued"}


# =============================================================================
# テスト共通ヘルパー
# =============================================================================


def _make_grade_ai_event(
    card_id: str = "card-123",
    body: dict | None = None,
    user_id: str = "test-user-id",
    query_params: dict | None = None,
    authorizer: dict | None = None,
) -> dict:
    """grade_ai_handler 用の API Gateway HTTP API v2 イベントを構築する。

    Args:
        card_id: パスパラメータの cardId（camelCase）
        body: リクエストボディ（None の場合はデフォルト {"user_answer": "東京"}）
        user_id: JWT claims の sub クレーム
        query_params: クエリストリングパラメータ
        authorizer: リクエストコンテキストの authorizer。None の場合は標準 JWT 形式

    Returns:
        API Gateway HTTP API v2 形式のイベント辞書
    """
    if body is None:
        body = {"user_answer": "東京"}

    if authorizer is None:
        authorizer = {
            "jwt": {
                "claims": {"sub": user_id},
                "scopes": ["openid", "profile"],
            }
        }

    event = {
        "version": "2.0",
        "routeKey": "POST /reviews/{cardId}/grade-ai",
        "rawPath": f"/reviews/{card_id}/grade-ai",
        "rawQueryString": "",
        "body": json.dumps(body) if body is not None else None,
        "pathParameters": {"cardId": card_id},
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api-id",
            "authorizer": authorizer,
            "http": {"method": "POST"},
            "requestId": "test-request-id",
            "routeKey": "POST /reviews/{cardId}/grade-ai",
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
def mock_card_service():
    """CardService のモック。card.front / card.back をモック Card で返す。

    パッチ対象: api.handler.card_service（モジュールレベルグローバル変数）。
    submit 時の fail-fast 所有権チェックで使用される。
    """
    with patch("api.handler.card_service") as mock:
        mock_card = MagicMock()
        mock_card.front = "日本の首都は？"
        mock_card.back = "東京"
        mock.get_card.return_value = mock_card
        yield mock


@pytest.fixture
def mock_submit():
    """submit_ai_job のモック。作成直後の queued ジョブレコードを返す。

    パッチ対象: api.handler.submit_ai_job（インポートされた関数）。
    """
    with patch("api.handler.submit_ai_job") as mock:
        mock.return_value = dict(SUBMIT_RESULT)
        yield mock


# =============================================================================
# テストカテゴリ A: 認証テスト
# =============================================================================


class TestGradeAiHandlerAuth:
    """認証関連テスト。

    grade_ai_handler は独立 Lambda のため、JWT claims を
    event.requestContext.authorizer.jwt.claims.sub から直接抽出する。
    認証失敗時はジョブを submit しないこと（同期 401）を確認する。
    """

    def test_grade_ai_returns_401_when_no_authorizer(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """authorizer が空の場合に HTTP 401 を返し、submit されないことを確認。"""
        event = _make_grade_ai_event(authorizer={})

        response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert body["error"] == "Unauthorized"
        mock_submit.assert_not_called()

    def test_grade_ai_returns_401_when_no_sub_claim(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """JWT claims に sub がない場合に HTTP 401 を返すことを確認。"""
        authorizer = {"jwt": {"claims": {"iss": "https://keycloak.example.com"}}}
        event = _make_grade_ai_event(authorizer=authorizer)

        response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert body["error"] == "Unauthorized"
        mock_submit.assert_not_called()

    def test_grade_ai_extracts_user_id_from_jwt_claims(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """authorizer.jwt.claims.sub の user_id が所有権チェックと submit に渡ることを確認。"""
        event = _make_grade_ai_event(user_id="user-abc-123")

        grade_ai_handler(event, lambda_context)

        mock_card_service.get_card.assert_called_once_with("user-abc-123", "card-123")
        assert mock_submit.call_args.kwargs["user_id"] == "user-abc-123"


# =============================================================================
# テストカテゴリ B: パスパラメータテスト
# =============================================================================


class TestGradeAiHandlerPathParams:
    """パスパラメータ関連テスト。

    template.yaml で /reviews/{cardId}/grade-ai と定義されているため、
    pathParameters のキーは cardId（camelCase）。
    """

    def test_grade_ai_extracts_card_id_from_path_params(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """pathParameters.cardId から card_id を正しく取得することを確認。"""
        event = _make_grade_ai_event(card_id="card-xyz-789")

        grade_ai_handler(event, lambda_context)

        mock_card_service.get_card.assert_called_once_with(
            "test-user-id", "card-xyz-789"
        )
        assert mock_submit.call_args.kwargs["payload"]["card_id"] == "card-xyz-789"

    def test_grade_ai_returns_400_when_card_id_missing(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """pathParameters が null の場合に HTTP 400 を返し、submit されないことを確認。"""
        event = _make_grade_ai_event()
        event["pathParameters"] = None

        response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 400
        mock_submit.assert_not_called()


# =============================================================================
# テストカテゴリ C: リクエストバリデーションテスト
# =============================================================================


class TestGradeAiHandlerValidation:
    """リクエストバリデーション関連テスト。

    GradeAnswerRequest の Pydantic バリデーションと JSON パースエラーは
    submit 前の同期検証として維持される（400 を即時に返し、ジョブ化しない）。
    """

    def test_grade_ai_returns_400_when_body_is_null(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """event.body が null の場合に HTTP 400 を返すことを確認。"""
        event = _make_grade_ai_event()
        event["body"] = None

        response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 400
        mock_submit.assert_not_called()

    def test_grade_ai_returns_400_when_body_is_invalid_json(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """event.body が不正な JSON の場合に HTTP 400 を返すことを確認。"""
        event = _make_grade_ai_event()
        event["body"] = "not json"

        response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 400
        mock_submit.assert_not_called()

    def test_grade_ai_returns_400_when_user_answer_empty(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """user_answer が空文字列の場合に HTTP 400 を返すことを確認（min_length=1）。"""
        event = _make_grade_ai_event(body={"user_answer": ""})

        response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 400
        mock_submit.assert_not_called()

    def test_grade_ai_returns_400_when_user_answer_whitespace_only(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """user_answer が空白のみの場合に HTTP 400 を返すことを確認。"""
        event = _make_grade_ai_event(body={"user_answer": "   "})

        response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 400
        mock_submit.assert_not_called()

    def test_grade_ai_returns_400_when_user_answer_too_long(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """user_answer が 2000 文字超の場合に HTTP 400 を返すことを確認（max_length=2000）。"""
        event = _make_grade_ai_event(body={"user_answer": "a" * 2001})

        response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 400
        mock_submit.assert_not_called()

    def test_grade_ai_returns_400_when_user_answer_missing(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """user_answer フィールドが未指定の場合に HTTP 400 を返すことを確認。"""
        event = _make_grade_ai_event(body={})

        response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 400
        mock_submit.assert_not_called()

    def test_grade_ai_returns_400_when_language_is_invalid(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """language が ja/en 以外の場合に HTTP 400 を返すことを確認（許可リスト検証）。"""
        event = _make_grade_ai_event(query_params={"language": "xx"})

        response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert body["error"] == "Unsupported language. Use 'ja' or 'en'."
        mock_submit.assert_not_called()


# =============================================================================
# テストカテゴリ D: カード関連エラーテスト（fail-fast 所有権チェック）
# =============================================================================


class TestGradeAiHandlerCardErrors:
    """カード取得関連エラーテスト。

    submit 時の fail-fast 検証として CardService.get_card() の
    CardNotFoundError ハンドリング（404 + submit しない）を検証する。
    ワーカー実行時点の再検証は test_ai_job_executors.py が担保する。
    """

    def test_grade_ai_returns_404_when_card_not_found(
        self, lambda_context, mock_submit
    ):
        """CardNotFoundError の場合に HTTP 404 を返し、ジョブ化しないことを確認。"""
        with patch("api.handler.card_service") as mock_cs:
            mock_cs.get_card.side_effect = CardNotFoundError("Card not found")
            event = _make_grade_ai_event()

            response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert body["error"] == "Not Found"
        mock_submit.assert_not_called()

    def test_grade_ai_returns_404_for_other_users_card(
        self, lambda_context, mock_submit
    ):
        """他ユーザーのカードにアクセスした場合に HTTP 404 を返すことを確認。

        CardService は user_id をパーティションキーとして使用するため、
        情報漏洩防止のため 403 ではなく 404 を返す。
        """
        with patch("api.handler.card_service") as mock_cs:
            mock_cs.get_card.side_effect = CardNotFoundError("Card not found")
            event = _make_grade_ai_event(
                user_id="user-other", card_id="card-owned-by-someone-else"
            )

            response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 404
        mock_submit.assert_not_called()


# =============================================================================
# テストカテゴリ E: ジョブ submit テスト
# =============================================================================


class TestGradeAiHandlerSubmit:
    """submit_ai_job の呼び出し引数（user_id / job_type / payload）を検証する。

    旧「AI 採点呼び出しテスト」の後継。AI サービスへの引数伝播は
    test_ai_job_executors.py::TestExecuteGradeAi が担保する。
    """

    def test_grade_ai_submits_job_with_correct_args(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """submit_ai_job が user_id / job_type / payload 一式で 1 回呼ばれることを確認。"""
        event = _make_grade_ai_event(body={"user_answer": "東京"})

        grade_ai_handler(event, lambda_context)

        mock_submit.assert_called_once_with(
            user_id="test-user-id",
            job_type="grade_ai",
            payload={
                "card_id": "card-123",
                "user_answer": "東京",
                "language": "ja",
            },
        )

    def test_grade_ai_passes_language_param_to_payload(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """クエリパラメータ language=en が payload に渡ることを確認。"""
        event = _make_grade_ai_event(query_params={"language": "en"})

        grade_ai_handler(event, lambda_context)

        assert mock_submit.call_args.kwargs["payload"]["language"] == "en"

    def test_grade_ai_uses_default_language_ja(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """queryStringParameters なしの場合にデフォルト "ja" が使われることを確認。"""
        event = _make_grade_ai_event()  # query_params なし

        grade_ai_handler(event, lambda_context)

        assert mock_submit.call_args.kwargs["payload"]["language"] == "ja"


# =============================================================================
# テストカテゴリ F: 正常系レスポンステスト（202 Accepted）
# =============================================================================


class TestGradeAiHandlerAccepted:
    """202 レスポンスの検証（旧・正常系 200 レスポンステストの後継）。

    completed 時の result 形状（GradeAnswerResponse 互換）は
    test_ai_job_executors.py と tests/integration/test_integration.py が担保する。
    """

    def test_grade_ai_returns_202(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """正常系で HTTP 202 Accepted が返ることを確認。"""
        event = _make_grade_ai_event()

        response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 202

    def test_grade_ai_accepted_body_has_job_fields(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """202 ボディが {job_id, job_type, status} のみを含むことを確認。"""
        event = _make_grade_ai_event()

        response = grade_ai_handler(event, lambda_context)

        body = json.loads(response["body"])
        assert body == {
            "job_id": "aijob_t",
            "job_type": "grade_ai",
            "status": "queued",
        }

    def test_grade_ai_accepted_response_is_json(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """202 レスポンスの Content-Type が application/json であることを確認。"""
        event = _make_grade_ai_event()

        response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 202
        assert response["headers"]["Content-Type"] == "application/json"


# =============================================================================
# テストカテゴリ G: 予期しないエラーテスト
# =============================================================================


class TestGradeAiHandlerUnexpectedErrors:
    """submit 段階での予期しない例外の汎用ハンドリングを検証する。

    AI 例外のマッピング（504/429/503/500）は executor + classify_ai_job_error に
    移設した（test_ai_job_executors.py / test_ai_job_errors.py）。
    """

    def test_grade_ai_returns_500_when_submit_fails_unexpectedly(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """submit_ai_job が予期しない例外を送出した場合に HTTP 500 を返すことを確認。"""
        mock_submit.side_effect = RuntimeError("unexpected")
        event = _make_grade_ai_event()

        response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert body["error"] == "Internal Server Error"

    def test_grade_ai_returns_500_on_unexpected_card_service_error(
        self, lambda_context, mock_submit
    ):
        """カード取得の予期しない例外（RuntimeError 等）で HTTP 500 を返すことを確認。"""
        with patch("api.handler.card_service") as mock_cs:
            mock_cs.get_card.side_effect = RuntimeError("unexpected db error")
            event = _make_grade_ai_event()

            response = grade_ai_handler(event, lambda_context)

        assert response["statusCode"] == 500
        mock_submit.assert_not_called()


# =============================================================================
# テストカテゴリ H: ロギングテスト
# =============================================================================


class TestGradeAiHandlerLogging:
    """submit 時のリクエストロギングを検証する。

    詳細な構造化フィールドの検証は tests/unit/test_structured_logging.py。
    """

    def test_grade_ai_logs_request_info(
        self, lambda_context, mock_card_service, mock_submit
    ):
        """submit 受付時に logger.info で card_id を含む情報を記録することを確認。"""
        event = _make_grade_ai_event(body={"user_answer": "テスト回答"})

        with patch("api.handler.logger") as mock_logger:
            grade_ai_handler(event, lambda_context)

        info_calls_str = str(mock_logger.info.call_args_list)
        assert "card" in info_calls_str or "card-123" in info_calls_str

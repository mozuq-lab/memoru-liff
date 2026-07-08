"""POST /cards/refine ハンドラーテスト（ai-async-jobs 版）。

ai-async-jobs: ハンドラーは同期検証（認証・バリデーション）後に submit_ai_job で
ジョブを登録し 202 を返すだけになった。AI 改善の実行・レスポンス形状・
AI エラーマッピングの検証は tests/unit/test_ai_job_executors.py
（TestExecuteRefine）に移設した。
"""

import json
from unittest.mock import patch


# submit_ai_job モックの戻り値（作成直後の queued ジョブレコード相当）
SUBMIT_RESULT = {"job_id": "aijob_t", "job_type": "refine", "status": "queued"}


def _make_refine_event(
    body: dict | None = None,
    user_id: str = "test-user-id",
) -> dict:
    """POST /cards/refine 用の API Gateway HTTP API v2 イベントを構築."""
    if body is None:
        body = {"front": "クロージャとは？", "back": "変数を覚えてる関数"}
    return {
        "version": "2.0",
        "routeKey": "POST /cards/refine",
        "rawPath": "/cards/refine",
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api-id",
            "authorizer": {
                "jwt": {
                    "claims": {"sub": user_id},
                    "scopes": ["openid", "profile"],
                }
            },
            "http": {"method": "POST"},
            "requestId": "test-request-id",
            "routeKey": "POST /cards/refine",
            "stage": "$default",
        },
        "pathParameters": {},
        "isBase64Encoded": False,
    }


def _make_refine_event_no_auth(body: dict | None = None) -> dict:
    """認証なしの POST /cards/refine イベント."""
    if body is None:
        body = {"front": "テスト", "back": "テスト"}
    return {
        "version": "2.0",
        "routeKey": "POST /cards/refine",
        "rawPath": "/cards/refine",
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body),
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "api-id",
            "authorizer": {},
            "http": {"method": "POST"},
            "requestId": "test-request-id",
            "routeKey": "POST /cards/refine",
            "stage": "$default",
        },
        "pathParameters": {},
        "isBase64Encoded": False,
    }


class TestRefineCardSubmit:
    """正常系: ジョブ submit + 202 検証."""

    def test_refine_card_returns_202_with_job_body(self, lambda_context):
        """認証済みユーザーが front と back を送信すると 202 + ジョブ情報が返ること."""
        event = _make_refine_event()

        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            mock_submit.return_value = dict(SUBMIT_RESULT)

            from api.handler import handler
            response = handler(event, lambda_context)

        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body == {
            "job_id": "aijob_t",
            "job_type": "refine",
            "status": "queued",
        }

    def test_refine_card_submits_payload(self, lambda_context):
        """submit_ai_job が user_id / job_type / payload 一式で呼ばれること."""
        event = _make_refine_event(
            body={"front": "クロージャとは？", "back": "変数を覚えてる関数", "language": "en"}
        )

        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            mock_submit.return_value = dict(SUBMIT_RESULT)

            from api.handler import handler
            handler(event, lambda_context)

        mock_submit.assert_called_once_with(
            user_id="test-user-id",
            job_type="refine",
            payload={
                "front": "クロージャとは？",
                "back": "変数を覚えてる関数",
                "language": "en",
            },
        )

    def test_refine_card_front_only(self, lambda_context):
        """表面のみ送信でも 202 になり、back は既定の空文字で submit されること."""
        event = _make_refine_event(body={"front": "クロージャ"})

        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            mock_submit.return_value = dict(SUBMIT_RESULT)

            from api.handler import handler
            response = handler(event, lambda_context)

        assert response["statusCode"] == 202
        assert mock_submit.call_args.kwargs["payload"] == {
            "front": "クロージャ",
            "back": "",
            "language": "ja",
        }


class TestRefineCardValidation:
    """バリデーションエラーテスト（400 は同期のまま。ジョブ化しない）."""

    def test_both_empty_returns_400(self, lambda_context):
        """front と back の両方が空の場合 400 が返ること."""
        event = _make_refine_event(body={"front": "", "back": ""})

        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            from api.handler import handler
            response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body
        mock_submit.assert_not_called()

    def test_front_exceeds_max_length_returns_400(self, lambda_context):
        """front が 1000 文字を超える場合 400 が返ること."""
        event = _make_refine_event(body={"front": "あ" * 1001})

        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            from api.handler import handler
            response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        mock_submit.assert_not_called()


class TestRefineCardAuth:
    """認証エラーテスト."""

    def test_no_auth_returns_401(self, lambda_context):
        """未認証リクエストで 401 が返り、ジョブ化しないこと."""
        event = _make_refine_event_no_auth()

        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            from api.handler import handler
            response = handler(event, lambda_context)

        assert response["statusCode"] == 401
        mock_submit.assert_not_called()


class TestRefineCardInvalidBody:
    """不正ボディのテスト."""

    def _make_raw_body_event(self, raw_body: str, user_id: str = "test-user-id") -> dict:
        """任意の raw body を持つ API Gateway イベントを構築."""
        return {
            "version": "2.0",
            "routeKey": "POST /cards/refine",
            "rawPath": "/cards/refine",
            "rawQueryString": "",
            "headers": {"content-type": "application/json"},
            "body": raw_body,
            "requestContext": {
                "accountId": "123456789012",
                "apiId": "api-id",
                "authorizer": {
                    "jwt": {
                        "claims": {"sub": user_id},
                        "scopes": ["openid", "profile"],
                    }
                },
                "http": {"method": "POST"},
                "requestId": "test-request-id",
                "routeKey": "POST /cards/refine",
                "stage": "$default",
            },
            "pathParameters": {},
            "isBase64Encoded": False,
        }

    def test_null_body_returns_400(self, lambda_context):
        """body が null の場合 400 が返ること."""
        event = self._make_raw_body_event("null")

        from api.handler import handler
        response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    def test_array_body_returns_400(self, lambda_context):
        """body が配列の場合 400 が返ること."""
        event = self._make_raw_body_event("[1, 2, 3]")

        from api.handler import handler
        response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

    def test_string_body_returns_400(self, lambda_context):
        """body が文字列の場合 400 が返ること."""
        event = self._make_raw_body_event('"hello"')

        from api.handler import handler
        response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "error" in body

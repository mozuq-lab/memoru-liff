"""POST /cards/generate ハンドラー body=null テスト."""

import json


class TestGenerateCardsInvalidBody:
    """不正ボディのテスト."""

    def _make_raw_body_event(self, raw_body: str, user_id: str = "test-user-id") -> dict:
        """任意の raw body を持つ API Gateway イベントを構築."""
        return {
            "version": "2.0",
            "routeKey": "POST /cards/generate",
            "rawPath": "/cards/generate",
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
                "routeKey": "POST /cards/generate",
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

"""Unit tests for AI handler (ai-async-jobs: submit のみ担当).

generate-from-url の submit 時同期検証を中心に検証する:
- profile_id 指定は 501 Not Implemented で即拒否（AgentCore Browser 統合の無効化中）
- SSRF バリデーション（validate_url）失敗は 400 で fail-fast（ジョブ化しない）
- 正常系は submit_ai_job + 202

重複 URL 警告・カード生成・コンテンツ取得はワーカー側 executor に移設されたため、
tests/unit/test_ai_job_executors.py（TestExecuteGenerateFromUrl）が担保する。
"""

import json
from unittest.mock import patch

SUBMIT_RESULT = {
    "job_id": "aijob_t",
    "job_type": "generate_from_url",
    "status": "queued",
}


class TestGenerateFromUrlProfileIdDisabled:
    """POST /cards/generate-from-url の profile_id は 501 で即拒否される。"""

    def test_profile_id_returns_501(self, api_gateway_event, lambda_context):
        """profile_id を渡すと 501 Not Implemented が返り、ジョブ化されない
        (壊れた経路に入らないこと)。"""
        event = api_gateway_event(
            method="POST",
            path="/cards/generate-from-url",
            body={
                "url": "https://example.com/page",
                "profile_id": "bp-anything",
            },
            user_id="user-1",
        )

        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 501
        body = json.loads(response["body"])
        assert body["code"] == "browser_unavailable"
        assert "対応していません" in body["error"]

        # ジョブ化されていないこと
        mock_submit.assert_not_called()

    def test_no_profile_id_submits_job(self, api_gateway_event, lambda_context):
        """profile_id 無しのリクエストは submit されて 202 が返る。"""
        event = api_gateway_event(
            method="POST",
            path="/cards/generate-from-url",
            body={"url": "https://example.com/page"},
            user_id="user-1",
        )

        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            mock_submit.return_value = dict(SUBMIT_RESULT)
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 202
        body = json.loads(response["body"])
        assert body == {
            "job_id": "aijob_t",
            "job_type": "generate_from_url",
            "status": "queued",
        }


class TestGenerateFromUrlSsrfFailFast:
    """SSRF バリデーションは submit 時に fail-fast（400）する。"""

    def test_private_ip_url_returns_400(self, api_gateway_event, lambda_context):
        """プライベート IP への URL は 400 で即拒否され、ジョブ化しない。"""
        event = api_gateway_event(
            method="POST",
            path="/cards/generate-from-url",
            body={"url": "https://192.168.1.1/internal"},
            user_id="user-1",
        )

        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "無効なURLです" in body["error"]
        mock_submit.assert_not_called()

    def test_blocked_hostname_returns_400(self, api_gateway_event, lambda_context):
        """localhost 等のブロック対象ホストも 400 で即拒否される。"""
        event = api_gateway_event(
            method="POST",
            path="/cards/generate-from-url",
            body={"url": "https://localhost/page"},
            user_id="user-1",
        )

        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            from api.handler import handler

            response = handler(event, lambda_context)

        assert response["statusCode"] == 400
        mock_submit.assert_not_called()


class TestGenerateFromUrlSubmitPayload:
    """submit_ai_job へ渡る payload（正規化済み URL + 生成パラメータ）を検証。"""

    def test_submits_normalized_url_and_params(self, api_gateway_event, lambda_context):
        event = api_gateway_event(
            method="POST",
            path="/cards/generate-from-url",
            body={
                "url": "https://example.com/page",
                "card_type": "definition",
                "target_count": 5,
                "difficulty": "hard",
                "language": "en",
            },
            user_id="user-1",
        )

        with patch("api.handlers.ai_handler.submit_ai_job") as mock_submit:
            mock_submit.return_value = dict(SUBMIT_RESULT)
            from api.handler import handler

            handler(event, lambda_context)

        mock_submit.assert_called_once_with(
            user_id="user-1",
            job_type="generate_from_url",
            payload={
                "url": "https://example.com/page",
                "card_type": "definition",
                "target_count": 5,
                "difficulty": "hard",
                "language": "en",
            },
        )

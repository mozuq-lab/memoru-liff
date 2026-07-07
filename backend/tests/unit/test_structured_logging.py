"""TASK-0111: handler.py / shared.py の構造化ログテスト。

f-string ログが extra={} パラメータ形式に変換されていることを確認する。

ai-async-jobs: grade_ai / advice ハンドラーは submit のみを行うため、
ログメッセージは "Grade AI job submit" / "Advice job submit" に変更された。
AI 実行後の成功・エラーログの検証は不要になった（AI 実行はワーカー側の
run_job_inline / classify_ai_job_error が構造化ログを出す。
tests/unit/test_ai_job_service.py 参照）。
"""

import json
from unittest.mock import MagicMock, patch

import pytest


from api.handler import grade_ai_handler, advice_handler

SUBMIT_RESULT = {"job_id": "aijob_t", "job_type": "grade_ai", "status": "queued"}


def _make_event(
    card_id: str = "card-123",
    user_id: str = "test-user",
    body: dict | None = None,
) -> dict:
    if body is None:
        body = {"user_answer": "answer"}
    return {
        "pathParameters": {"cardId": card_id},
        "body": json.dumps(body),
        "queryStringParameters": {"language": "ja"},
        "requestContext": {
            "authorizer": {"jwt": {"claims": {"sub": user_id}}},
        },
        "headers": {},
    }


class TestGradeAiStructuredLogging:
    """grade_ai_handler の構造化ログを検証する。"""

    @patch("api.handler.submit_ai_job")
    @patch("api.handler.card_service")
    @patch("api.handler.logger")
    def test_submit_log_contains_structured_fields(
        self, mock_logger, mock_card_svc, mock_submit
    ):
        """submit ログ（"Grade AI job submit"）に card_id, user_id 等の構造化フィールドが含まれる。"""
        mock_card = MagicMock()
        mock_card.front = "Q"
        mock_card.back = "A"
        mock_card_svc.get_card.return_value = mock_card
        mock_submit.return_value = dict(SUBMIT_RESULT)

        event = _make_event(card_id="c1", user_id="u1")
        result = grade_ai_handler(event, None)
        assert result["statusCode"] == 202

        # 構造化ログ: extra にフィールドが含まれている
        info_calls = mock_logger.info.call_args_list
        assert len(info_calls) == 1

        args, kwargs = info_calls[0]
        assert args[0] == "Grade AI job submit"
        assert "extra" in kwargs
        assert kwargs["extra"]["card_id"] == "c1"
        assert kwargs["extra"]["user_id"] == "u1"
        assert "user_answer_length" in kwargs["extra"]

    @patch("api.handler.submit_ai_job")
    @patch("api.handler.card_service")
    @patch("api.handler.logger")
    def test_error_log_on_unexpected_submit_failure(
        self, mock_logger, mock_card_svc, mock_submit
    ):
        """submit の予期しない失敗時に error が構造化フィールド付きで記録される。"""
        mock_card = MagicMock()
        mock_card.front = "Q"
        mock_card.back = "A"
        mock_card_svc.get_card.return_value = mock_card
        mock_submit.side_effect = RuntimeError("submit failed")

        event = _make_event(card_id="c2", user_id="u2")
        result = grade_ai_handler(event, None)
        assert result["statusCode"] == 500

        error_calls = mock_logger.error.call_args_list
        assert len(error_calls) >= 1
        _, kwargs = error_calls[0]
        assert "extra" in kwargs
        assert "error" in kwargs["extra"]


class TestAdviceStructuredLogging:
    """advice_handler の構造化ログを検証する。"""

    @patch("api.handler.submit_ai_job")
    @patch("api.handler.logger")
    def test_submit_log_contains_user_id(self, mock_logger, mock_submit):
        """submit ログ（"Advice job submit"）に user_id が構造化フィールドとして含まれる。"""
        mock_submit.return_value = {
            "job_id": "aijob_t",
            "job_type": "advice",
            "status": "queued",
        }

        event = {
            "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "u3"}}}},
            "queryStringParameters": {"language": "ja"},
            "headers": {},
        }
        result = advice_handler(event, None)
        assert result["statusCode"] == 202

        info_calls = mock_logger.info.call_args_list
        assert len(info_calls) == 1

        args, kwargs = info_calls[0]
        assert args[0] == "Advice job submit"
        assert "extra" in kwargs
        assert kwargs["extra"]["user_id"] == "u3"


class TestSharedStructuredLogging:
    """shared.py の構造化ログを検証する。"""

    @patch("api.shared.logger")
    def test_jwt_decode_error_structured(self, mock_logger):
        from api.shared import _jwt_dev_fallback_decode
        import os

        with patch.dict(os.environ, {"ENVIRONMENT": "dev", "AWS_SAM_LOCAL": "true"}):
            result = _jwt_dev_fallback_decode("Bearer invalid.token")
            # Invalid token will cause decode error
            assert result is None
            error_calls = mock_logger.error.call_args_list
            assert len(error_calls) >= 1
            _, kwargs = error_calls[0]
            assert "extra" in kwargs
            assert "error" in kwargs["extra"]

    @patch("api.shared.logger")
    def test_authorizer_context_error_structured(self, mock_logger):
        """authorizer 解析エラー時に構造化ログが出力される。"""
        from api.shared import get_user_id_from_context
        from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

        mock_resolver = MagicMock()
        # jwt キーがあるが claims が KeyError を起こす設定
        mock_resolver.current_event.request_context.authorizer = {"jwt": {"no_claims": {}}}
        mock_resolver.current_event.get_header_value.return_value = None

        with pytest.raises(UnauthorizedError):
            get_user_id_from_context(mock_resolver)

        warn_calls = mock_logger.warning.call_args_list
        assert len(warn_calls) >= 1
        _, kwargs = warn_calls[0]
        assert "extra" in kwargs
        assert "error" in kwargs["extra"]

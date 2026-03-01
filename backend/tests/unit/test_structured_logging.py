"""TASK-0111: handler.py / shared.py の構造化ログテスト。

f-string ログが extra={} パラメータ形式に変換されていることを確認する。
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from api.handler import grade_ai_handler, advice_handler


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

    @patch("api.handler.create_ai_service")
    @patch("api.handler.card_service")
    @patch("api.handler.logger")
    def test_info_logs_contain_structured_fields(self, mock_logger, mock_card_svc, mock_ai_factory):
        """正常系ログに card_id, user_id, grade 等の構造化フィールドが含まれる。"""
        mock_card = MagicMock()
        mock_card.front = "Q"
        mock_card.back = "A"
        mock_card_svc.get_card.return_value = mock_card

        mock_ai = MagicMock()
        mock_ai.grade_answer.return_value = MagicMock(grade=4, reasoning="OK", model_used="test-model", processing_time_ms=100)
        mock_ai_factory.return_value = mock_ai

        event = _make_event(card_id="c1", user_id="u1")
        result = grade_ai_handler(event, None)
        assert result["statusCode"] == 200

        # 構造化ログ: extra にフィールドが含まれている
        info_calls = mock_logger.info.call_args_list
        assert len(info_calls) == 2

        # request log
        _, kwargs = info_calls[0]
        assert "extra" in kwargs
        assert kwargs["extra"]["card_id"] == "c1"
        assert kwargs["extra"]["user_id"] == "u1"

        # success log
        _, kwargs = info_calls[1]
        assert "extra" in kwargs
        assert kwargs["extra"]["card_id"] == "c1"
        assert kwargs["extra"]["grade"] == 4

    @patch("api.handler.create_ai_service")
    @patch("api.handler.card_service")
    @patch("api.handler.logger")
    def test_warning_log_on_ai_error(self, mock_logger, mock_card_svc, mock_ai_factory):
        """AI エラー時のログに card_id, error_type が構造化フィールドとして含まれる。"""
        from services.ai_service import AITimeoutError

        mock_card = MagicMock()
        mock_card.front = "Q"
        mock_card.back = "A"
        mock_card_svc.get_card.return_value = mock_card

        mock_ai = MagicMock()
        mock_ai.grade_answer.side_effect = AITimeoutError("timeout")
        mock_ai_factory.return_value = mock_ai

        event = _make_event(card_id="c2", user_id="u2")
        result = grade_ai_handler(event, None)
        assert result["statusCode"] == 504

        warn_calls = mock_logger.warning.call_args_list
        assert len(warn_calls) >= 1
        _, kwargs = warn_calls[0]
        assert "extra" in kwargs
        assert kwargs["extra"]["card_id"] == "c2"
        assert kwargs["extra"]["user_id"] == "u2"
        assert kwargs["extra"]["error_type"] == "AITimeoutError"


class TestAdviceStructuredLogging:
    """advice_handler の構造化ログを検証する。"""

    @patch("api.handler.review_service")
    @patch("api.handler.create_ai_service")
    @patch("api.handler.logger")
    def test_info_logs_contain_user_id(self, mock_logger, mock_ai_factory, mock_review_svc):
        """アドバイスログに user_id, model 等の構造化フィールドが含まれる。"""
        from services.ai_service import ReviewSummary

        mock_summary = ReviewSummary(
            total_reviews=10, average_grade=3.5, total_cards=5,
            cards_due_today=2, streak_days=3,
        )
        mock_review_svc.get_review_summary.return_value = mock_summary

        mock_ai = MagicMock()
        mock_ai.get_learning_advice.return_value = MagicMock(
            advice_text="Keep studying",
            weak_areas=["math"],
            recommendations=["review daily"],
            model_used="test-model",
            processing_time_ms=200,
        )
        mock_ai_factory.return_value = mock_ai

        event = {
            "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "u3"}}}},
            "queryStringParameters": {"language": "ja"},
            "headers": {},
        }
        result = advice_handler(event, None)
        assert result["statusCode"] == 200

        info_calls = mock_logger.info.call_args_list
        assert len(info_calls) == 2

        # request log
        _, kwargs = info_calls[0]
        assert "extra" in kwargs
        assert kwargs["extra"]["user_id"] == "u3"

        # success log
        _, kwargs = info_calls[1]
        assert "extra" in kwargs
        assert kwargs["extra"]["user_id"] == "u3"
        assert kwargs["extra"]["model"] == "test-model"


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

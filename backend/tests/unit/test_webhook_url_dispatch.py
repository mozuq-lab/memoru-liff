"""Unit tests for N-5 dispatch logic in the LINE webhook handler.

受付 (handle_url_card_generation) のディスパッチ分岐を検証する:
  - queue URL あり & inline でない → SQS へ enqueue し、同期実行しない。
  - queue URL なし or inline → その場で同期実行（インラインフォールバック）。
  - enqueue 失敗 → インラインフォールバック。
"""

import json
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

import webhook.line_handler as lh


@pytest.fixture
def sqs_queue():
    with mock_aws():
        sqs = boto3.client("sqs", region_name="ap-northeast-1")
        url = sqs.create_queue(QueueName="memoru-url-generate-test")["QueueUrl"]
        yield sqs, url


def _patch_dispatch(queue_url: str = "", worker_mode: str = ""):
    """ディスパッチ判定に使うモジュール定数 + SQS クライアントを差し替える。"""
    return patch.multiple(
        lh,
        URL_GENERATE_QUEUE_URL=queue_url,
        URL_WORKER_MODE=worker_mode,
    )


class TestShouldEnqueue:
    def test_enqueue_when_queue_set_and_not_inline(self):
        with _patch_dispatch(queue_url="https://q", worker_mode=""):
            assert lh._should_enqueue() is True

    def test_no_enqueue_when_no_queue(self):
        with _patch_dispatch(queue_url="", worker_mode=""):
            assert lh._should_enqueue() is False

    def test_no_enqueue_when_inline_mode(self):
        with _patch_dispatch(queue_url="https://q", worker_mode="inline"):
            assert lh._should_enqueue() is False


class TestDispatch:
    @patch("webhook.line_handler.generate_and_push_url_cards")
    @patch("webhook.line_handler.line_service")
    def test_enqueues_and_does_not_run_inline(
        self, mock_line_service, mock_generate, sqs_queue
    ):
        """queue URL あり → SQS に enqueue され、同期実行は呼ばれない。"""
        sqs, queue_url = sqs_queue
        with _patch_dispatch(queue_url=queue_url, worker_mode=""), patch(
            "webhook.line_handler._get_sqs_client", return_value=sqs
        ):
            lh.handle_url_card_generation(
                user_id="user-1",
                line_user_id="line-1",
                url="https://example.com/article",
                reply_token="rt",
                webhook_event_id="evt-1",
            )

        # 同期実行されていない。
        mock_generate.assert_not_called()

        # メッセージ内容を検証。
        msgs = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10).get(
            "Messages", []
        )
        assert len(msgs) == 1
        body = json.loads(msgs[0]["Body"])
        assert body == {
            "user_id": "user-1",
            "line_user_id": "line-1",
            "url": "https://example.com/article",
            "webhook_event_id": "evt-1",
        }

    @patch("webhook.line_handler.generate_and_push_url_cards")
    @patch("webhook.line_handler.line_service")
    def test_inline_when_no_queue(self, mock_line_service, mock_generate):
        """queue URL なし → その場で同期実行される。"""
        with _patch_dispatch(queue_url="", worker_mode=""):
            lh.handle_url_card_generation(
                user_id="user-1",
                line_user_id="line-1",
                url="https://example.com/article",
                reply_token="rt",
                webhook_event_id="evt-1",
            )
        mock_generate.assert_called_once_with(
            user_id="user-1",
            line_user_id="line-1",
            url="https://example.com/article",
        )

    @patch("webhook.line_handler.generate_and_push_url_cards")
    @patch("webhook.line_handler.line_service")
    def test_inline_when_inline_mode(self, mock_line_service, mock_generate):
        """URL_WORKER_MODE=inline → 同期実行される（ローカル相当）。"""
        with _patch_dispatch(queue_url="https://q", worker_mode="inline"):
            lh.handle_url_card_generation(
                user_id="user-1",
                line_user_id="line-1",
                url="https://example.com/article",
                reply_token="rt",
            )
        mock_generate.assert_called_once()

    @patch("webhook.line_handler.generate_and_push_url_cards")
    @patch("webhook.line_handler.line_service")
    def test_enqueue_failure_falls_back_to_inline(
        self, mock_line_service, mock_generate
    ):
        """enqueue 失敗 → インラインへフォールバックし、受付は落とさない。"""
        failing_sqs = MagicMock()
        failing_sqs.send_message.side_effect = RuntimeError("boom")
        with _patch_dispatch(queue_url="https://q", worker_mode=""), patch(
            "webhook.line_handler._get_sqs_client", return_value=failing_sqs
        ):
            lh.handle_url_card_generation(
                user_id="user-1",
                line_user_id="line-1",
                url="https://example.com/article",
                reply_token="rt",
            )
        mock_generate.assert_called_once()

    @patch("webhook.line_handler.generate_and_push_url_cards")
    @patch("webhook.line_handler.line_service")
    def test_invalid_url_neither_enqueues_nor_runs(
        self, mock_line_service, mock_generate, sqs_queue
    ):
        """バリデーション失敗 → enqueue も同期実行もしない。"""
        sqs, queue_url = sqs_queue
        with _patch_dispatch(queue_url=queue_url, worker_mode=""), patch(
            "webhook.line_handler._get_sqs_client", return_value=sqs
        ), patch(
            "webhook.line_handler.validate_url",
            side_effect=lh.UrlValidationError("bad"),
        ):
            lh.handle_url_card_generation(
                user_id="user-1",
                line_user_id="line-1",
                url="http://169.254.169.254/",
                reply_token="rt",
            )
        mock_generate.assert_not_called()
        msgs = sqs.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=10).get(
            "Messages", []
        )
        assert msgs == []

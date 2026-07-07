"""AI 非同期ジョブ基盤の統合テスト（ai-async-jobs 版）.

全 7 AI エンドポイントを新アーキテクチャの E2E で検証する:

    submit（202 + job_id）→ inline 実行（キュー URL 未設定）
    → GET /ai-jobs/{job_id}（ポーリング API）→ completed
    → result が旧同期レスポンスと同一形状

- AiJobsTable は moto でモック（テーブル名は conftest の
  AI_JOBS_TABLE=memoru-ai-jobs-test）
- キュー URL 未設定のため submit_ai_job は inline モードで即時実行する
  （フロントは 1 回目のポーリングで completed を受け取る想定と同一）
- AI 呼び出しは services.ai_job_executors 名前空間でモックする

テストカテゴリ:
- TestSubmitPollE2E: 全 7 エンドポイントの submit → poll → completed フロー
- TestFailedJobE2E: ワーカー実行時エラーが failed ジョブ（旧ステータス互換の
  error）として記録されるフロー
- TestJobAccessControl: ポーリング API の所有者チェック（IDOR 404）
"""

import json
from unittest.mock import MagicMock, patch

import boto3
import pytest
from moto import mock_aws

from services.ai_job_store import AiJobStore
from services.ai_service import (
    AITimeoutError,
    GeneratedCard,
    GenerationResult,
    GradingResult,
    LearningAdvice,
    RefineResult,
    ReviewSummary,
)
from services.card_service import CardNotFoundError
from models.tutor import SendMessageResponse, TutorMessage, TutorSessionResponse

TABLE_NAME = "memoru-ai-jobs-test"


# =============================================================================
# フィクスチャ
# =============================================================================


@pytest.fixture(autouse=True)
def _inline_mode(monkeypatch):
    """キュー URL 未設定 = inline モードを保証する（submit が即時実行する）。"""
    for name in ("AI_JOB_QUEUE_URL", "AI_JOB_HEAVY_QUEUE_URL", "AI_JOB_WORKER_MODE"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def ai_jobs_store():
    """moto の AiJobsTable を作成し、submit / ポーリングの両経路に配線する。"""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "job_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "job_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        store = AiJobStore(table_name=TABLE_NAME, dynamodb_resource=dynamodb)

        # submit_ai_job（store 引数なし呼び出し）とポーリングハンドラーの
        # モジュールレベル store の両方を moto 配線の store に差し替える。
        with patch("services.ai_job_service.AiJobStore", return_value=store), patch(
            "api.handlers.ai_jobs_handler.ai_job_store", store
        ):
            yield store


# =============================================================================
# 共通ヘルパー
# =============================================================================


def _make_grade_ai_event(
    card_id: str = "card-123",
    body: dict | None = None,
    user_id: str = "test-user-id",
) -> dict:
    """POST /reviews/{cardId}/grade-ai 用のイベント（独立 Lambda 形式）。"""
    if body is None:
        body = {"user_answer": "東京"}
    return {
        "version": "2.0",
        "routeKey": "POST /reviews/{cardId}/grade-ai",
        "rawPath": f"/reviews/{card_id}/grade-ai",
        "rawQueryString": "",
        "body": json.dumps(body),
        "pathParameters": {"cardId": card_id},
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
            "routeKey": "POST /reviews/{cardId}/grade-ai",
            "stage": "$default",
        },
        "headers": {"content-type": "application/json"},
        "isBase64Encoded": False,
    }


def _make_advice_event(user_id: str = "test-user-id") -> dict:
    """POST /advice 用のイベント（独立 Lambda 形式。GET → POST 化済み）。"""
    return {
        "version": "2.0",
        "routeKey": "POST /advice",
        "rawPath": "/advice",
        "rawQueryString": "",
        "pathParameters": None,
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
            "routeKey": "POST /advice",
            "stage": "$default",
        },
        "headers": {"content-type": "application/json"},
        "isBase64Encoded": False,
    }


def _setup_ai_mocks() -> MagicMock:
    """全 AI メソッドの戻り値を一括設定したモックサービスを返す。"""
    mock_service = MagicMock()
    mock_service.generate_cards.return_value = GenerationResult(
        cards=[GeneratedCard(front="Q1", back="A1", suggested_tags=["tag1"])],
        input_length=30,
        model_used="test-model",
        processing_time_ms=500,
    )
    mock_service.grade_answer.return_value = GradingResult(
        grade=4,
        reasoning="Correct answer",
        model_used="test-model",
        processing_time_ms=500,
    )
    mock_service.get_learning_advice.return_value = LearningAdvice(
        advice_text="学習頻度を上げましょう。",
        weak_areas=["数学"],
        recommendations=["毎日復習する"],
        model_used="test-model",
        processing_time_ms=800,
    )
    mock_service.refine_card.return_value = RefineResult(
        refined_front="クロージャとは何か？",
        refined_back="外部スコープの変数を参照し続ける関数。",
        model_used="test-model",
        processing_time_ms=1200,
    )
    return mock_service


def _accepted_job(response) -> dict:
    """202 レスポンスを検証してボディ（job 情報）を返す。"""
    assert response["statusCode"] == 202, (
        f"expected 202, got {response['statusCode']}: {response.get('body')}"
    )
    body = json.loads(response["body"])
    assert set(body.keys()) == {"job_id", "job_type", "status"}
    assert body["status"] == "queued"  # 202 は作成時点の queued レコードを返す
    assert body["job_id"].startswith("aijob_")
    return body


def _poll_job(api_gateway_event, lambda_context, job_id: str, user_id: str = "test-user-id"):
    """GET /ai-jobs/{job_id} をメインハンドラー（Router）経由で実行する。"""
    from api.handler import handler

    event = api_gateway_event(
        method="GET", path=f"/ai-jobs/{job_id}", user_id=user_id
    )
    return handler(event, lambda_context)


def _poll_completed(api_gateway_event, lambda_context, job_body: dict) -> dict:
    """ポーリングして completed ジョブのボディを返す（inline なので 1 回で完了）。"""
    response = _poll_job(api_gateway_event, lambda_context, job_body["job_id"])
    assert response["statusCode"] == 200
    polled = json.loads(response["body"])
    assert polled["job_id"] == job_body["job_id"]
    assert polled["job_type"] == job_body["job_type"]
    assert polled["status"] == "completed", f"job not completed: {polled}"
    assert "created_at" in polled and "updated_at" in polled
    # payload（リクエスト原文）や user_id は漏れない
    assert "payload" not in polled
    assert "user_id" not in polled
    return polled


# =============================================================================
# カテゴリ 1: submit → poll → completed の E2E（全 7 エンドポイント）
# =============================================================================


class TestSubmitPollE2E:
    """submit（202）→ inline 実行 → ポーリングで旧同期レスポンスと同一形状の
    result を取得できることを全エンドポイントで検証する。"""

    def test_generate_e2e(self, ai_jobs_store, api_gateway_event, lambda_context):
        """POST /cards/generate → 202 → completed + GenerateCardsResponse 形状。"""
        from api.handler import handler

        event = api_gateway_event(
            method="POST",
            path="/cards/generate",
            body={
                "input_text": "テスト用の学習テキストです。十分な長さが必要です。",
                "card_count": 3,
                "difficulty": "medium",
                "language": "ja",
            },
        )

        with patch("services.ai_job_executors.create_ai_service") as mock_factory:
            mock_factory.return_value = _setup_ai_mocks()
            response = handler(event, lambda_context)
            job_body = _accepted_job(response)
            assert job_body["job_type"] == "generate"

            polled = _poll_completed(api_gateway_event, lambda_context, job_body)

        # 旧同期レスポンス（GenerateCardsResponse）と同一形状
        assert polled["result"] == {
            "generated_cards": [
                {"front": "Q1", "back": "A1", "suggested_tags": ["tag1"]}
            ],
            "generation_info": {
                "input_length": 30,
                "model_used": "test-model",
                "processing_time_ms": 500,
            },
        }

    def test_generate_from_url_e2e(
        self, ai_jobs_store, api_gateway_event, lambda_context
    ):
        """POST /cards/generate-from-url → 202 → completed + GenerateFromUrlResponse 形状。"""
        from api.handler import handler

        event = api_gateway_event(
            method="POST",
            path="/cards/generate-from-url",
            body={"url": "https://example.com/page"},
        )

        page = MagicMock()
        page.url = "https://example.com/page"
        page.title = "Example Page"
        page.text_content = "x" * 200
        page.fetch_method = "http"
        page.fetched_at = "2026-07-07T00:00:00+00:00"

        with patch("services.ai_job_executors.CardService") as mock_card_cls, patch(
            "services.ai_job_executors.fetch_and_generate_cards"
        ) as mock_fetch, patch("services.ai_job_executors.UrlContentService"), patch(
            "services.ai_job_executors.BrowserService"
        ):
            mock_card_cls.return_value.find_cards_by_reference_url.return_value = []
            mock_fetch.return_value = (
                page,
                ["x" * 200],
                GenerationResult(
                    cards=[GeneratedCard(front="f", back="b", suggested_tags=[])],
                    input_length=200,
                    model_used="test-model",
                    processing_time_ms=10,
                ),
            )

            response = handler(event, lambda_context)
            job_body = _accepted_job(response)
            assert job_body["job_type"] == "generate_from_url"

            polled = _poll_completed(api_gateway_event, lambda_context, job_body)

        # 旧同期レスポンス（GenerateFromUrlResponse）と同一形状（warning なし）
        assert polled["result"] == {
            "generated_cards": [{"front": "f", "back": "b", "suggested_tags": []}],
            "generation_info": {
                "model_used": "test-model",
                "processing_time_ms": 10,
                "fetch_method": "http",
                "chunk_count": 1,
                "content_length": 200,
            },
            "page_info": {
                "url": "https://example.com/page",
                "title": "Example Page",
                "fetched_at": "2026-07-07T00:00:00+00:00",
            },
        }

    def test_refine_e2e(self, ai_jobs_store, api_gateway_event, lambda_context):
        """POST /cards/refine → 202 → completed + RefineCardResponse 形状。"""
        from api.handler import handler

        event = api_gateway_event(
            method="POST",
            path="/cards/refine",
            body={"front": "クロージャとは？", "back": "変数を覚えてる関数"},
        )

        with patch("services.ai_job_executors.create_ai_service") as mock_factory:
            mock_factory.return_value = _setup_ai_mocks()
            response = handler(event, lambda_context)
            job_body = _accepted_job(response)
            assert job_body["job_type"] == "refine"

            polled = _poll_completed(api_gateway_event, lambda_context, job_body)

        assert polled["result"] == {
            "refined_front": "クロージャとは何か？",
            "refined_back": "外部スコープの変数を参照し続ける関数。",
            "model_used": "test-model",
            "processing_time_ms": 1200,
        }

    def test_grade_ai_e2e(self, ai_jobs_store, api_gateway_event, lambda_context):
        """POST /reviews/{cardId}/grade-ai → 202 → completed + GradeAnswerResponse 形状。"""
        from api.handler import grade_ai_handler

        mock_card = MagicMock()
        mock_card.front = "日本の首都は？"
        mock_card.back = "東京"

        with patch("api.handler.card_service") as mock_handler_cs, patch(
            "services.ai_job_executors.CardService"
        ) as mock_worker_cs, patch(
            "services.ai_job_executors.create_ai_service"
        ) as mock_factory:
            # submit 時の fail-fast とワーカー時の再取得の両方を成功させる
            mock_handler_cs.get_card.return_value = mock_card
            mock_worker_cs.return_value.get_card.return_value = mock_card
            mock_factory.return_value = _setup_ai_mocks()

            response = grade_ai_handler(_make_grade_ai_event(), lambda_context)
            job_body = _accepted_job(response)
            assert job_body["job_type"] == "grade_ai"

            polled = _poll_completed(api_gateway_event, lambda_context, job_body)

        assert polled["result"] == {
            "grade": 4,
            "reasoning": "Correct answer",
            "card_front": "日本の首都は？",
            "card_back": "東京",
            "grading_info": {
                "model_used": "test-model",
                "processing_time_ms": 500,
            },
        }

    def test_advice_e2e(self, ai_jobs_store, api_gateway_event, lambda_context):
        """POST /advice → 202 → completed + LearningAdviceResponse 形状。

        study_stats.average_grade の float は store で Decimal 変換 →
        読み出しで float に戻る（設計レビュー C-1 の実挙動確認）。
        """
        from api.handler import advice_handler

        with patch("services.ai_job_executors.UserService") as mock_user_cls, patch(
            "services.ai_job_executors.ReviewService"
        ) as mock_review_cls, patch(
            "services.ai_job_executors.create_ai_service"
        ) as mock_factory:
            mock_user_cls.return_value.get_or_create_user.return_value.settings = {
                "timezone": "Asia/Tokyo"
            }
            mock_review_cls.return_value.get_review_summary.return_value = (
                ReviewSummary(
                    total_reviews=100,
                    average_grade=3.5,
                    total_cards=50,
                    cards_due_today=10,
                    streak_days=5,
                )
            )
            mock_factory.return_value = _setup_ai_mocks()

            response = advice_handler(_make_advice_event(), lambda_context)
            job_body = _accepted_job(response)
            assert job_body["job_type"] == "advice"

            polled = _poll_completed(api_gateway_event, lambda_context, job_body)

            # 集計は submit 時ではなくワーカー実行時に行われる
            mock_review_cls.return_value.get_review_summary.assert_called_once_with(
                "test-user-id", user_timezone="Asia/Tokyo"
            )

        assert polled["result"] == {
            "advice_text": "学習頻度を上げましょう。",
            "weak_areas": ["数学"],
            "recommendations": ["毎日復習する"],
            "study_stats": {
                "total_reviews": 100,
                "average_grade": 3.5,  # Decimal 変換往復後も float で返る
                "total_cards": 50,
                "cards_due_today": 10,
                "streak_days": 5,
            },
            "advice_info": {
                "model_used": "test-model",
                "processing_time_ms": 800,
            },
        }

    def test_tutor_start_e2e(
        self, ai_jobs_store, api_gateway_event, lambda_context, monkeypatch
    ):
        """POST /tutor/sessions → 202 → completed + TutorSessionResponse 形状。"""
        from api.handler import handler

        session = TutorSessionResponse(
            session_id="tutor_e2e-session",
            deck_id="deck_001",
            mode="free_talk",
            status="active",
            messages=[
                TutorMessage(
                    role="assistant",
                    content="こんにちは！",
                    related_cards=[],
                    timestamp="2026-07-07T10:00:00Z",
                )
            ],
            message_count=0,
            created_at="2026-07-07T10:00:00Z",
            updated_at="2026-07-07T10:00:00Z",
            ended_at=None,
        )
        mock_tutor = MagicMock()
        mock_tutor.start_session.return_value = session
        monkeypatch.setattr("services.ai_job_executors._tutor_service", mock_tutor)

        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions",
            body={"deck_id": "deck_001", "mode": "free_talk"},
        )

        with patch("api.handlers.tutor_handler.tutor_service") as mock_validate_svc:
            response = handler(event, lambda_context)
            job_body = _accepted_job(response)
            assert job_body["job_type"] == "tutor_start"

            polled = _poll_completed(api_gateway_event, lambda_context, job_body)

        # 事前検証（fail-fast）は submit 時に同期実行される
        mock_validate_svc.validate_start_session.assert_called_once_with(
            user_id="test-user-id", deck_id="deck_001", mode="free_talk"
        )
        # AI 実行はワーカー側（executor）で行われる
        mock_tutor.start_session.assert_called_once_with(
            user_id="test-user-id", deck_id="deck_001", mode="free_talk"
        )
        assert polled["result"] == session.model_dump(mode="json")

    def test_tutor_message_e2e(
        self, ai_jobs_store, api_gateway_event, lambda_context, monkeypatch
    ):
        """POST /tutor/sessions/{id}/messages → 202 → completed + SendMessageResponse 形状。"""
        from api.handler import handler

        send_response = SendMessageResponse(
            message=TutorMessage(
                role="assistant",
                content="AI の応答です。",
                related_cards=[],
                timestamp="2026-07-07T10:00:25Z",
            ),
            session_id="tutor_e2e-session",
            message_count=1,
            is_limit_reached=False,
        )
        mock_tutor = MagicMock()
        mock_tutor.send_message.return_value = send_response
        monkeypatch.setattr("services.ai_job_executors._tutor_service", mock_tutor)

        event = api_gateway_event(
            method="POST",
            path="/tutor/sessions/tutor_e2e-session/messages",
            body={"content": "appleについて教えて"},
            path_parameters={"sessionId": "tutor_e2e-session"},
        )

        with patch("api.handlers.tutor_handler.tutor_service") as mock_validate_svc:
            response = handler(event, lambda_context)
            job_body = _accepted_job(response)
            assert job_body["job_type"] == "tutor_message"

            polled = _poll_completed(api_gateway_event, lambda_context, job_body)

        mock_validate_svc.validate_send_message.assert_called_once_with(
            user_id="test-user-id", session_id="tutor_e2e-session"
        )
        mock_tutor.send_message.assert_called_once_with(
            user_id="test-user-id",
            session_id="tutor_e2e-session",
            content="appleについて教えて",
        )
        assert polled["result"] == send_response.model_dump(mode="json")


# =============================================================================
# カテゴリ 2: ワーカー実行時エラー → failed ジョブ E2E
# =============================================================================


class TestFailedJobE2E:
    """AI エラーが failed ジョブ（旧同期ステータス互換の error）として記録され、
    ポーリングで取得できることを検証する。"""

    def test_ai_timeout_records_failed_job_with_old_status(
        self, ai_jobs_store, api_gateway_event, lambda_context
    ):
        """AITimeoutError → failed + error {status: 504, code: ai_timeout, 旧文言}。"""
        from api.handler import handler

        event = api_gateway_event(
            method="POST",
            path="/cards/generate",
            body={"input_text": "テスト用の学習テキストです。十分な長さが必要です。"},
        )

        with patch("services.ai_job_executors.create_ai_service") as mock_factory:
            mock_service = MagicMock()
            mock_service.generate_cards.side_effect = AITimeoutError("timeout")
            mock_factory.return_value = mock_service

            response = handler(event, lambda_context)
            job_body = _accepted_job(response)  # submit 自体は 202 で成功する

            poll_response = _poll_job(
                api_gateway_event, lambda_context, job_body["job_id"]
            )

        assert poll_response["statusCode"] == 200
        polled = json.loads(poll_response["body"])
        assert polled["status"] == "failed"
        assert polled["error"] == {
            "status": 504,
            "code": "ai_timeout",
            "message": "AI service timeout",
        }
        assert "result" not in polled

    def test_card_deleted_after_submit_records_failed_404(
        self, ai_jobs_store, api_gateway_event, lambda_context
    ):
        """submit 後にカードが削除された場合、ワーカー時の再検証で failed(404) になる。"""
        from api.handler import grade_ai_handler

        mock_card = MagicMock()
        mock_card.front = "Q"
        mock_card.back = "A"

        with patch("api.handler.card_service") as mock_handler_cs, patch(
            "services.ai_job_executors.CardService"
        ) as mock_worker_cs, patch("services.ai_job_executors.create_ai_service"):
            # submit 時の fail-fast は通過し、ワーカー時に消えているシナリオ
            mock_handler_cs.get_card.return_value = mock_card
            mock_worker_cs.return_value.get_card.side_effect = CardNotFoundError(
                "Card not found"
            )

            response = grade_ai_handler(_make_grade_ai_event(), lambda_context)
            job_body = _accepted_job(response)

            poll_response = _poll_job(
                api_gateway_event, lambda_context, job_body["job_id"]
            )

        polled = json.loads(poll_response["body"])
        assert polled["status"] == "failed"
        assert polled["error"] == {
            "status": 404,
            "code": "not_found",
            "message": "Not Found",
        }


# =============================================================================
# カテゴリ 3: ポーリング API のアクセス制御
# =============================================================================


class TestJobAccessControl:
    """GET /ai-jobs/{jobId} の所有者チェック（IDOR: 列挙防止の同一 404）。"""

    def test_other_users_job_returns_404(
        self, ai_jobs_store, api_gateway_event, lambda_context
    ):
        """他ユーザーのジョブは存在しないジョブと同一の 404 を返す。"""
        from api.handler import handler

        event = api_gateway_event(
            method="POST",
            path="/cards/generate",
            body={"input_text": "テスト用の学習テキストです。十分な長さが必要です。"},
        )

        with patch("services.ai_job_executors.create_ai_service") as mock_factory:
            mock_factory.return_value = _setup_ai_mocks()
            response = handler(event, lambda_context)
            job_body = _accepted_job(response)

        # 別ユーザーとしてポーリング → 404（存在しない場合と同一ボディ）
        other_response = _poll_job(
            api_gateway_event, lambda_context, job_body["job_id"], user_id="other-user"
        )
        assert other_response["statusCode"] == 404
        assert json.loads(other_response["body"]) == {"error": "Job not found"}

        missing_response = _poll_job(
            api_gateway_event, lambda_context, "aijob_missing"
        )
        assert missing_response["statusCode"] == 404
        assert json.loads(missing_response["body"]) == json.loads(
            other_response["body"]
        )

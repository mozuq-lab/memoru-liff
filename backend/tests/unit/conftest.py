"""Unit テスト共通設定とフィクスチャ.

TASK-0065 リファクタリング: test_quality_gate.py の共通ヘルパーをここに集約。
品質ゲートテスト全体で再利用できるモックファクトリとイベントビルダーを提供する。

🔵 信頼性: 既存テストコードから抽出した確定済みヘルパー群。
"""

import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from services.ai_service import (
    GeneratedCard,
    GenerationResult,
    GradingResult,
    LearningAdvice,
    ReviewSummary,
)
from services.bedrock import BedrockService


# =============================================================================
# Agent / Bedrock レスポンスモックヘルパー
# =============================================================================


def make_mock_agent(response_text: str) -> MagicMock:
    """Agent モックを作成するヘルパー.

    【機能概要】: Strands Agent の __call__ 戻り値を str() したとき response_text を返すモックを作成する。
    【再利用性】: StrandsAIService を使う全テストクラスで共通利用できる。
    🔵 信頼性: 既存 test_quality_gate.py の _make_mock_agent() を名称統一してリネーム。
    """
    mock_response = MagicMock()
    mock_response.__str__ = MagicMock(return_value=response_text)
    mock_agent = MagicMock()
    mock_agent.return_value = mock_response
    return mock_agent


def make_bedrock_response(text: str) -> MagicMock:
    """Bedrock API のレスポンスモックを作成するヘルパー.

    【機能概要】: invoke_model が返す辞書形式のモックレスポンスを生成する。
    【再利用性】: BedrockService を使う全テストクラスで共通利用できる。
    🔵 信頼性: 既存 test_quality_gate.py の _make_bedrock_response() を名称統一してリネーム。
    """
    body_mock = MagicMock()
    body_mock.read.return_value = json.dumps({"content": [{"text": text}]}).encode()
    return {"body": body_mock}


def make_client_error(code: str) -> ClientError:
    """botocore ClientError を作成するヘルパー.

    【機能概要】: 指定したエラーコードの ClientError インスタンスを生成する。
    【再利用性】: Bedrock / Strands のエラーハンドリングテスト全体で共通利用できる。
    🔵 信頼性: 既存 test_quality_gate.py の _make_client_error() を名称統一してリネーム。
    """
    return ClientError({"Error": {"Code": code, "Message": f"{code} error"}}, "invoke_model")


# =============================================================================
# API Gateway イベントビルダー
# =============================================================================


def make_generate_event(user_id: str = "test-user-id") -> dict:
    """POST /cards/generate 用の API Gateway HTTP API v2 イベントを構築する.

    【機能概要】: カード生成エンドポイントへのリクエストイベントを生成する。
    【再利用性】: エンドポイント動作テストとエラーマッピングテストで共通利用できる。
    🔵 信頼性: 既存 test_quality_gate.py の _make_generate_event() を名称統一してリネーム。
    """
    return {
        "version": "2.0",
        "routeKey": "POST /cards/generate",
        "rawPath": "/cards/generate",
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"input_text": "テスト用のテキストです。" * 5}),
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


def make_grade_ai_event(
    card_id: str = "card-123",
    user_id: str = "test-user-id",
) -> dict:
    """POST /reviews/{cardId}/grade-ai 用のイベントを構築する.

    【機能概要】: AI採点エンドポイントへのリクエストイベントを生成する。
    【再利用性】: エンドポイント動作テストとエラーマッピングテストで共通利用できる。
    🔵 信頼性: 既存 test_quality_gate.py の _make_grade_ai_event() を名称統一してリネーム。
    """
    return {
        "version": "2.0",
        "routeKey": "POST /reviews/{cardId}/grade-ai",
        "rawPath": f"/reviews/{card_id}/grade-ai",
        "rawQueryString": "",
        "headers": {"content-type": "application/json"},
        "body": json.dumps({"user_answer": "東京"}),
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
        "isBase64Encoded": False,
    }


def make_advice_event(user_id: str = "test-user-id") -> dict:
    """GET /advice 用のイベントを構築する.

    【機能概要】: 学習アドバイスエンドポイントへのリクエストイベントを生成する。
    【再利用性】: エンドポイント動作テストとエラーマッピングテストで共通利用できる。
    🔵 信頼性: 既存 test_quality_gate.py の _make_advice_event() を名称統一してリネーム。
    """
    return {
        "version": "2.0",
        "routeKey": "GET /advice",
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
            "http": {"method": "GET"},
            "requestId": "test-request-id",
            "routeKey": "GET /advice",
            "stage": "$default",
        },
        "headers": {"content-type": "application/json"},
        "isBase64Encoded": False,
    }


# =============================================================================
# AI サービス結果モックファクトリ
# =============================================================================


def make_mock_review_summary() -> ReviewSummary:
    """テスト用の ReviewSummary を作成するヘルパー.

    【機能概要】: アドバイスエンドポイントのテストに必要なレビューサマリーを生成する。
    【再利用性】: アドバイス系テスト全体で共通利用できる。
    🔵 信頼性: 既存 test_quality_gate.py の _make_mock_review_summary() を名称統一してリネーム。
    """
    return ReviewSummary(
        total_reviews=100,
        average_grade=3.5,
        total_cards=50,
        cards_due_today=10,
        streak_days=7,
    )


def make_mock_ai_service() -> MagicMock:
    """全 3 AI メソッドが正常な戻り値を返すモックサービスを作成する.

    【機能概要】: エンドポイント動作テストとレスポンスフォーマットテストで使用する
                  モック AI サービスを生成する。
    【再利用性】: TestEndpointFunctionalFinal と TestResponseFormatFinal で共通利用できる。
    🔵 信頼性: 既存 test_quality_gate.py の _make_mock_ai_service() と
                _make_mock_ai_service_for_format() を統合。
    """
    mock_service = MagicMock()
    mock_service.generate_cards.return_value = GenerationResult(
        cards=[GeneratedCard(front="Question", back="Answer", suggested_tags=["AI生成", "test"])],
        input_length=100,
        model_used="test_model",
        processing_time_ms=500,
    )
    mock_service.grade_answer.return_value = GradingResult(
        grade=4,
        reasoning="The answer is mostly correct",
        model_used="test_model",
        processing_time_ms=300,
    )
    mock_service.get_learning_advice.return_value = LearningAdvice(
        advice_text="You are doing well, keep it up!",
        weak_areas=["vocabulary", "grammar"],
        recommendations=["Review daily", "Practice listening"],
        model_used="test_model",
        processing_time_ms=400,
    )
    return mock_service


def make_mock_card(front: str = "日本の首都は？", back: str = "東京") -> MagicMock:
    """テスト用のモックカードを作成する.

    【機能概要】: grade-ai エンドポイントのテストに必要なカードモックを生成する。
    【再利用性】: grade-ai 系テスト全体で共通利用できる。
    🔵 信頼性: 既存テストコードから抽出。
    """
    mock_card = MagicMock()
    mock_card.front = front
    mock_card.back = back
    return mock_card


# =============================================================================
# pytest フィクスチャ
# =============================================================================


@pytest.fixture
def mock_ai_service():
    """全 3 AI メソッドが正常な戻り値を返すモックサービスのフィクスチャ."""
    return make_mock_ai_service()


@pytest.fixture
def mock_review_summary():
    """テスト用の ReviewSummary フィクスチャ."""
    return make_mock_review_summary()


@pytest.fixture
def mock_card():
    """テスト用のモックカードフィクスチャ."""
    return make_mock_card()

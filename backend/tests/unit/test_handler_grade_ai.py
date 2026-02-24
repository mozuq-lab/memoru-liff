"""TASK-0060: POST /reviews/{card_id}/grade-ai エンドポイントのテスト。

grade_ai_handler Lambda ハンドラーの本実装に対するテストケース。
構造的前提:
- grade_ai_handler は独立 Lambda 関数（app/APIGatewayHttpResolver 経由ではない）
- 生の API Gateway HTTP API v2 イベントを直接受け取る
- レスポンスは Lambda プロキシ統合形式の dict（statusCode, headers, body）
"""

import json
from unittest.mock import MagicMock, call, patch

import pytest

from api.handler import grade_ai_handler
from services.ai_service import (
    AIInternalError,
    AIParseError,
    AIProviderError,
    AIRateLimitError,
    AIServiceError,
    AITimeoutError,
    GradingResult,
)
from services.card_service import CardNotFoundError


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
    # デフォルトボディ設定
    if body is None:
        body = {"user_answer": "東京"}

    # デフォルト authorizer 設定（JWT Authorizer 形式）
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

    パッチ対象: api.handler.card_service（モジュールレベルグローバル変数）
    """
    with patch("api.handler.card_service") as mock:
        mock_card = MagicMock()
        mock_card.front = "日本の首都は？"
        mock_card.back = "東京"
        mock.get_card.return_value = mock_card
        yield mock


@pytest.fixture
def mock_ai_service():
    """create_ai_service のモック。GradingResult を返す。

    パッチ対象: api.handler.create_ai_service（インポートされた関数）

    Yields:
        tuple: (mock_factory, mock_service)
    """
    with patch("api.handler.create_ai_service") as mock_factory:
        mock_service = MagicMock()
        mock_service.grade_answer.return_value = GradingResult(
            grade=4,
            reasoning="Correct answer with good understanding",
            model_used="test-model",
            processing_time_ms=500,
        )
        mock_factory.return_value = mock_service
        yield mock_factory, mock_service


# =============================================================================
# テストカテゴリ A: 認証テスト
# =============================================================================


class TestGradeAiHandlerAuth:
    """認証関連テスト（TC-060-AUTH-001 ~ 003）。

    grade_ai_handler は独立 Lambda のため、JWT claims を
    event.requestContext.authorizer.jwt.claims.sub から直接抽出する。
    """

    def test_grade_ai_returns_401_when_no_authorizer(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-AUTH-001: authorizer が空の場合に HTTP 401 を返すことを確認。

        【テスト目的】: authorizer が空辞書 {} の場合の認証失敗ハンドリングを検証
        【テスト内容】: requestContext.authorizer = {} として grade_ai_handler を呼び出す
        【期待される動作】: HTTP 401 Unauthorized が返る
        🔵 信頼性レベル: 青信号 - get_user_id_from_context() の既存パターン、api-endpoints.md 認証仕様
        """
        # 【テストデータ準備】: authorizer が空の場合
        event = _make_grade_ai_event(authorizer={})

        # 【実際の処理実行】: grade_ai_handler を直接呼び出す
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】: 401 Unauthorized が返ることを確認
        assert response["statusCode"] == 401  # 【確認内容】: HTTP ステータスコードが 401 であること
        body = json.loads(response["body"])
        assert body["error"] == "Unauthorized"  # 【確認内容】: エラーメッセージが "Unauthorized" であること

    def test_grade_ai_returns_401_when_no_sub_claim(self, lambda_context):
        """TC-060-AUTH-002: JWT claims に sub がない場合に HTTP 401 を返すことを確認。

        【テスト目的】: JWT claims に sub クレームが欠如している場合の認証失敗を検証
        【テスト内容】: authorizer.jwt.claims に sub キーなし（iss のみ）でリクエスト
        【期待される動作】: HTTP 401 Unauthorized が返る
        🔵 信頼性レベル: 青信号 - JWT claims 構造は API Gateway HTTP API v2 仕様で確定
        """
        # 【テストデータ準備】: sub クレームなしの JWT claims
        authorizer = {"jwt": {"claims": {"iss": "https://keycloak.example.com"}}}
        event = _make_grade_ai_event(authorizer=authorizer)

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 401  # 【確認内容】: sub クレームなしで 401 が返ること
        body = json.loads(response["body"])
        assert body["error"] == "Unauthorized"  # 【確認内容】: エラーメッセージが "Unauthorized" であること

    def test_grade_ai_extracts_user_id_from_jwt_claims(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-AUTH-003: authorizer.jwt.claims.sub から user_id を正しく抽出することを確認。

        【テスト目的】: JWT claims の sub フィールドから user_id を抽出し CardService に渡す処理を検証
        【テスト内容】: user_id="user-abc-123" で grade_ai_handler を呼び出す
        【期待される動作】: card_service.get_card が user_id="user-abc-123" で呼ばれる
        🔵 信頼性レベル: 青信号 - 既存 get_user_id_from_context() の HTTP API パス（handler.py L122-123）
        """
        # 【テストデータ準備】: カスタム user_id を持つイベント
        event = _make_grade_ai_event(user_id="user-abc-123")

        # 【実際の処理実行】
        grade_ai_handler(event, lambda_context)

        # 【結果検証】: CardService.get_card が正しい user_id で呼ばれたことを確認
        mock_card_service.get_card.assert_called_once_with(
            "user-abc-123", "card-123"
        )  # 【確認内容】: user_id="user-abc-123" が get_card に渡されること


# =============================================================================
# テストカテゴリ B: パスパラメータテスト
# =============================================================================


class TestGradeAiHandlerPathParams:
    """パスパラメータ関連テスト（TC-060-PATH-001 ~ 002）。

    template.yaml で /reviews/{cardId}/grade-ai と定義されているため、
    pathParameters のキーは cardId（camelCase）。
    """

    def test_grade_ai_extracts_card_id_from_path_params(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-PATH-001: pathParameters.cardId から card_id を正しく取得することを確認。

        【テスト目的】: camelCase の cardId キーから card_id を抽出して CardService に渡す処理を検証
        【テスト内容】: card_id="card-xyz-789" のイベントで grade_ai_handler を呼び出す
        【期待される動作】: card_service.get_card が card_id="card-xyz-789" で呼ばれる
        🔵 信頼性レベル: 青信号 - template.yaml /reviews/{cardId}/grade-ai のキー名は camelCase で確定
        """
        # 【テストデータ準備】: カスタム card_id を持つイベント
        event = _make_grade_ai_event(card_id="card-xyz-789")

        # 【実際の処理実行】
        grade_ai_handler(event, lambda_context)

        # 【結果検証】: CardService.get_card が正しい card_id で呼ばれたことを確認
        mock_card_service.get_card.assert_called_once_with(
            "test-user-id", "card-xyz-789"
        )  # 【確認内容】: card_id="card-xyz-789" が get_card に渡されること

    def test_grade_ai_returns_400_when_card_id_missing(self, lambda_context):
        """TC-060-PATH-002: pathParameters が null の場合に HTTP 400 を返すことを確認。

        【テスト目的】: pathParameters がない場合の防御的処理を検証
        【テスト内容】: event["pathParameters"] = None として grade_ai_handler を呼び出す
        【期待される動作】: HTTP 400 Bad Request が返る
        🔵 信頼性レベル: 青信号 - 防御的プログラミング、api-endpoints.md バリデーションエラー 400
        """
        # 【テストデータ準備】: pathParameters が None のイベント
        event = _make_grade_ai_event()
        event["pathParameters"] = None

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 400  # 【確認内容】: pathParameters なしで 400 が返ること


# =============================================================================
# テストカテゴリ C: リクエストバリデーションテスト
# =============================================================================


class TestGradeAiHandlerValidation:
    """リクエストバリデーション関連テスト（TC-060-VAL-001 ~ 006）。

    GradeAnswerRequest の Pydantic バリデーションと JSON パースエラーのハンドリングを検証。
    """

    def test_grade_ai_returns_400_when_body_is_null(self, lambda_context):
        """TC-060-VAL-001: event.body が null の場合に HTTP 400 を返すことを確認。

        【テスト目的】: body が None の場合の JSON パースエラーハンドリングを検証
        【テスト内容】: event["body"] = None として grade_ai_handler を呼び出す
        【期待される動作】: HTTP 400 Bad Request が返る
        🔵 信頼性レベル: 青信号 - 既存 handler.py の json.JSONDecodeError ハンドリングパターン
        """
        # 【テストデータ準備】: body が None のイベント
        event = _make_grade_ai_event()
        event["body"] = None

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 400  # 【確認内容】: body=None で 400 が返ること

    def test_grade_ai_returns_400_when_body_is_invalid_json(self, lambda_context):
        """TC-060-VAL-002: event.body が不正な JSON の場合に HTTP 400 を返すことを確認。

        【テスト目的】: JSON パース失敗時のエラーハンドリングを検証
        【テスト内容】: event["body"] = "not json" として grade_ai_handler を呼び出す
        【期待される動作】: HTTP 400 Bad Request が返る
        🔵 信頼性レベル: 青信号 - 既存 handler.py の json.JSONDecodeError パターン
        """
        # 【テストデータ準備】: 不正な JSON 文字列
        event = _make_grade_ai_event()
        event["body"] = "not json"

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 400  # 【確認内容】: 不正 JSON で 400 が返ること

    def test_grade_ai_returns_400_when_user_answer_empty(self, lambda_context):
        """TC-060-VAL-003: user_answer が空文字列の場合に HTTP 400 を返すことを確認。

        【テスト目的】: GradeAnswerRequest の min_length=1 バリデーション制約を検証
        【テスト内容】: {"user_answer": ""} として grade_ai_handler を呼び出す
        【期待される動作】: HTTP 400 Bad Request が返る（Pydantic ValidationError）
        🔵 信頼性レベル: 青信号 - GradeAnswerRequest の min_length=1 制約（grading.py L17）
        """
        # 【テストデータ準備】: 空文字列の user_answer
        event = _make_grade_ai_event(body={"user_answer": ""})

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 400  # 【確認内容】: 空文字列 user_answer で 400 が返ること

    def test_grade_ai_returns_400_when_user_answer_whitespace_only(self, lambda_context):
        """TC-060-VAL-004: user_answer が空白のみの場合に HTTP 400 を返すことを確認。

        【テスト目的】: GradeAnswerRequest の validate_user_answer バリデータを検証
        【テスト内容】: {"user_answer": "   "} として grade_ai_handler を呼び出す
        【期待される動作】: HTTP 400 Bad Request が返る（Pydantic ValidationError）
        🔵 信頼性レベル: 青信号 - GradeAnswerRequest の validate_user_answer バリデータ（grading.py L23-28）
        """
        # 【テストデータ準備】: 空白のみの user_answer
        event = _make_grade_ai_event(body={"user_answer": "   "})

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 400  # 【確認内容】: 空白のみ user_answer で 400 が返ること

    def test_grade_ai_returns_400_when_user_answer_too_long(self, lambda_context):
        """TC-060-VAL-005: user_answer が 2000 文字超の場合に HTTP 400 を返すことを確認。

        【テスト目的】: GradeAnswerRequest の max_length=2000 バリデーション制約を検証
        【テスト内容】: {"user_answer": "a" * 2001} として grade_ai_handler を呼び出す
        【期待される動作】: HTTP 400 Bad Request が返る（Pydantic ValidationError）
        🔵 信頼性レベル: 青信号 - GradeAnswerRequest の max_length=2000 制約（grading.py L18）
        """
        # 【テストデータ準備】: 2001 文字の user_answer
        event = _make_grade_ai_event(body={"user_answer": "a" * 2001})

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 400  # 【確認内容】: 2001 文字 user_answer で 400 が返ること

    def test_grade_ai_returns_400_when_user_answer_missing(self, lambda_context):
        """TC-060-VAL-006: user_answer フィールドが未指定の場合に HTTP 400 を返すことを確認。

        【テスト目的】: GradeAnswerRequest の必須フィールドバリデーションを検証
        【テスト内容】: {} （空オブジェクト）として grade_ai_handler を呼び出す
        【期待される動作】: HTTP 400 Bad Request が返る（Pydantic ValidationError）
        🔵 信頼性レベル: 青信号 - GradeAnswerRequest の user_answer は必須フィールド（... = Required）
        """
        # 【テストデータ準備】: user_answer なしの空ボディ
        event = _make_grade_ai_event(body={})

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 400  # 【確認内容】: user_answer 未指定で 400 が返ること


# =============================================================================
# テストカテゴリ D: カード関連エラーテスト
# =============================================================================


class TestGradeAiHandlerCardErrors:
    """カード取得関連エラーテスト（TC-060-CARD-001 ~ 003）。

    CardService.get_card() の CardNotFoundError ハンドリングを検証。
    CardService は user_id をパーティションキーとして使用するため、
    他ユーザーのカードにはアクセスできない。
    """

    def test_grade_ai_returns_404_when_card_not_found(
        self, lambda_context, mock_ai_service
    ):
        """TC-060-CARD-001: CardNotFoundError が raise された場合に HTTP 404 を返すことを確認。

        【テスト目的】: card_service.get_card() が CardNotFoundError を raise した場合のハンドリングを検証
        【テスト内容】: mock_card_service.get_card.side_effect = CardNotFoundError
        【期待される動作】: HTTP 404 Not Found が返る
        🔵 信頼性レベル: 青信号 - api-endpoints.md エラーコード 404、CardService.get_card() 仕様
        """
        # 【テストデータ準備】: CardNotFoundError を raise するモック
        with patch("api.handler.card_service") as mock_cs:
            mock_cs.get_card.side_effect = CardNotFoundError("Card not found")
            event = _make_grade_ai_event()

            # 【実際の処理実行】
            response = grade_ai_handler(event, lambda_context)

        # 【結果検証】: 404 Not Found が返ることを確認
        assert response["statusCode"] == 404  # 【確認内容】: CardNotFoundError で 404 が返ること
        body = json.loads(response["body"])
        assert body["error"] == "Not Found"  # 【確認内容】: エラーメッセージが "Not Found" であること

    def test_grade_ai_passes_card_front_back_to_ai_service(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-CARD-002: 取得したカードの .front と .back が AI サービスに渡されることを確認。

        【テスト目的】: Card Pydantic モデルの .front/.back 属性が grade_answer() に渡される処理を検証
        【テスト内容】: card.front="日本の首都は？", card.back="東京" で grade_ai_handler を呼び出す
        【期待される動作】: ai_service.grade_answer() に card_front, card_back が渡される
        🔵 信頼性レベル: 青信号 - Card モデル（Pydantic BaseModel）の .front/.back 属性アクセスで確定
        """
        # 【テストデータ準備】: フィクスチャのデフォルト card（front="日本の首都は？", back="東京"）
        _, mock_service = mock_ai_service
        event = _make_grade_ai_event(body={"user_answer": "東京"})

        # 【実際の処理実行】
        grade_ai_handler(event, lambda_context)

        # 【結果検証】: grade_answer に card_front, card_back が正しく渡されたことを確認
        mock_service.grade_answer.assert_called_once_with(
            card_front="日本の首都は？",
            card_back="東京",
            user_answer="東京",
            language="ja",
        )  # 【確認内容】: card の .front / .back 属性から正しく引数が渡されること

    def test_grade_ai_returns_404_for_other_users_card(
        self, lambda_context, mock_ai_service
    ):
        """TC-060-CARD-003: 他ユーザーのカードにアクセスした場合に HTTP 404 を返すことを確認。

        【テスト目的】: CardService の user_id ベースのアクセス制御を検証
        【テスト内容】: 他ユーザーの card_id でアクセス → CardNotFoundError
        【期待される動作】: HTTP 404 Not Found が返る（情報漏洩防止のため 403 ではなく 404）
        🔵 信頼性レベル: 青信号 - CardService.get_card() は user_id をパーティションキーとして使用
        """
        # 【テストデータ準備】: 他ユーザーの card_id でアクセス
        with patch("api.handler.card_service") as mock_cs:
            mock_cs.get_card.side_effect = CardNotFoundError("Card not found")
            event = _make_grade_ai_event(
                user_id="user-other", card_id="card-owned-by-someone-else"
            )

            # 【実際の処理実行】
            response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 404  # 【確認内容】: 他ユーザーのカードにアクセスで 404 が返ること


# =============================================================================
# テストカテゴリ E: AI 採点呼び出しテスト
# =============================================================================


class TestGradeAiHandlerAICall:
    """AI 採点呼び出し関連テスト（TC-060-AI-001 ~ 004）。

    create_ai_service() ファクトリーの使用と grade_answer() の引数検証。
    language パラメータは queryStringParameters から取得（デフォルト "ja"）。
    """

    def test_grade_ai_calls_create_ai_service_factory(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-AI-001: create_ai_service() ファクトリーが 1 回呼ばれることを確認。

        【テスト目的】: AI サービスファクトリーが適切に呼ばれることを検証
        【テスト内容】: 正常リクエストで grade_ai_handler を呼び出す
        【期待される動作】: create_ai_service() が exactly 1 回呼ばれる
        🔵 信頼性レベル: 青信号 - 既存 generate_cards エンドポイントのパターン（handler.py L317）
        """
        # 【テストデータ準備】: 正常イベント
        mock_factory, _ = mock_ai_service
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        grade_ai_handler(event, lambda_context)

        # 【結果検証】: create_ai_service() が 1 回呼ばれたことを確認
        mock_factory.assert_called_once()  # 【確認内容】: ファクトリーが exactly 1 回呼ばれること

    def test_grade_ai_passes_correct_args_to_grade_answer(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-AI-002: grade_answer() に正しい引数が渡されることを確認。

        【テスト目的】: grade_answer() 呼び出し時の引数（card_front, card_back, user_answer, language）を検証
        【テスト内容】: user_answer="東京", card.front="日本の首都は？", card.back="東京" でリクエスト
        【期待される動作】: grade_answer(card_front="日本の首都は？", card_back="東京", user_answer="東京", language="ja")
        🔵 信頼性レベル: 青信号 - AIService Protocol の grade_answer シグネチャ（ai_service.py L133-151）
        """
        # 【テストデータ準備】: デフォルトカード（front="日本の首都は？", back="東京"）と user_answer="東京"
        _, mock_service = mock_ai_service
        event = _make_grade_ai_event(body={"user_answer": "東京"})

        # 【実際の処理実行】
        grade_ai_handler(event, lambda_context)

        # 【結果検証】: grade_answer の引数を確認
        mock_service.grade_answer.assert_called_once_with(
            card_front="日本の首都は？",
            card_back="東京",
            user_answer="東京",
            language="ja",
        )  # 【確認内容】: 全引数が正しく渡されること

    def test_grade_ai_passes_language_param_to_grade_answer(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-AI-003: クエリパラメータ language=en が AI サービスに渡されることを確認。

        【テスト目的】: queryStringParameters から language を取得して grade_answer() に渡す処理を検証
        【テスト内容】: queryStringParameters = {"language": "en"} でリクエスト
        【期待される動作】: grade_answer(..., language="en") が呼ばれる
        🔵 信頼性レベル: 青信号 - api-endpoints.md の language パラメータ仕様
        """
        # 【テストデータ準備】: language=en のクエリパラメータ
        _, mock_service = mock_ai_service
        event = _make_grade_ai_event(query_params={"language": "en"})

        # 【実際の処理実行】
        grade_ai_handler(event, lambda_context)

        # 【結果検証】: language="en" が grade_answer に渡されたことを確認
        call_kwargs = mock_service.grade_answer.call_args.kwargs
        assert call_kwargs["language"] == "en"  # 【確認内容】: language="en" が渡されること

    def test_grade_ai_uses_default_language_ja(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-AI-004: queryStringParameters なしの場合にデフォルト "ja" が使われることを確認。

        【テスト目的】: language パラメータのデフォルト値 "ja" を検証
        【テスト内容】: queryStringParameters なしでリクエスト（_make_grade_ai_event のデフォルト）
        【期待される動作】: grade_answer(..., language="ja") が呼ばれる
        🔵 信頼性レベル: 青信号 - TASK-0060.md「language デフォルト "ja"」
        """
        # 【テストデータ準備】: query_params なしのイベント（デフォルト）
        _, mock_service = mock_ai_service
        event = _make_grade_ai_event()  # query_params なし

        # 【実際の処理実行】
        grade_ai_handler(event, lambda_context)

        # 【結果検証】: language="ja" が grade_answer に渡されたことを確認
        call_kwargs = mock_service.grade_answer.call_args.kwargs
        assert call_kwargs["language"] == "ja"  # 【確認内容】: デフォルト language="ja" が渡されること


# =============================================================================
# テストカテゴリ F: 正常系レスポンステスト
# =============================================================================


class TestGradeAiHandlerSuccess:
    """正常系レスポンステスト（TC-060-RES-001 ~ 007）。

    GradeAnswerResponse の全フィールドと HTTP 200 ステータスを検証。
    """

    def test_grade_ai_success_returns_200(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-RES-001: 正常系で HTTP 200 が返ることを確認。

        【テスト目的】: 成功時の HTTP ステータスコードを検証
        【テスト内容】: 正常リクエスト + カード存在 + AI 採点成功
        【期待される動作】: HTTP 200 OK が返る
        🔵 信頼性レベル: 青信号 - api-endpoints.md「レスポンス（成功 200）」
        """
        # 【テストデータ準備】: 正常イベント（フィクスチャでモック設定済み）
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 200  # 【確認内容】: 成功時に HTTP 200 が返ること

    def test_grade_ai_success_response_contains_grade(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-RES-002: レスポンスに grade フィールドが正しく含まれることを確認。

        【テスト目的】: GradeAnswerResponse の grade フィールドを検証
        【テスト内容】: AI が grade=4 を返す（フィクスチャのデフォルト）
        【期待される動作】: response body の grade == 4
        🔵 信頼性レベル: 青信号 - GradeAnswerResponse モデル定義（grading.py L45-49）
        """
        # 【テストデータ準備】: AI は grade=4 を返す（フィクスチャで設定済み）
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        body = json.loads(response["body"])
        assert body["grade"] == 4  # 【確認内容】: grade フィールドが 4 であること

    def test_grade_ai_success_response_contains_reasoning(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-RES-003: レスポンスに reasoning フィールドが正しく含まれることを確認。

        【テスト目的】: GradeAnswerResponse の reasoning フィールドを検証
        【テスト内容】: AI が reasoning="Correct answer with good understanding" を返す
        【期待される動作】: response body の reasoning が正しく設定されている
        🔵 信頼性レベル: 青信号 - GradeAnswerResponse モデル定義（grading.py L51-53）
        """
        # 【テストデータ準備】: フィクスチャで reasoning を設定済み
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        body = json.loads(response["body"])
        assert (
            body["reasoning"] == "Correct answer with good understanding"
        )  # 【確認内容】: reasoning フィールドが正しく設定されること

    def test_grade_ai_success_response_contains_card_front_back(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-RES-004: レスポンスに card_front と card_back が含まれることを確認。

        【テスト目的】: GradeAnswerResponse の card_front / card_back フィールドを検証
        【テスト内容】: card.front="日本の首都は？", card.back="東京"（フィクスチャのデフォルト）
        【期待される動作】: body の card_front == "日本の首都は？", card_back == "東京"
        🔵 信頼性レベル: 青信号 - GradeAnswerResponse の card_front / card_back フィールド（grading.py L55-62）
        """
        # 【テストデータ準備】: フィクスチャで card.front="日本の首都は？", card.back="東京" を設定済み
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        body = json.loads(response["body"])
        assert body["card_front"] == "日本の首都は？"  # 【確認内容】: card_front が正しく設定されること
        assert body["card_back"] == "東京"  # 【確認内容】: card_back が正しく設定されること

    def test_grade_ai_success_response_contains_grading_info(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-RES-005: レスポンスの grading_info に model_used と processing_time_ms が含まれることを確認。

        【テスト目的】: GradeAnswerResponse の grading_info フィールドを検証
        【テスト内容】: AI が model_used="test-model", processing_time_ms=500 を返す
        【期待される動作】: grading_info["model_used"] == "test-model", grading_info["processing_time_ms"] == 500
        🔵 信頼性レベル: 青信号 - api-endpoints.md の grading_info 仕様
        """
        # 【テストデータ準備】: フィクスチャで model_used="test-model", processing_time_ms=500 を設定済み
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        body = json.loads(response["body"])
        assert (
            body["grading_info"]["model_used"] == "test-model"
        )  # 【確認内容】: model_used が grading_info に含まれること
        assert (
            body["grading_info"]["processing_time_ms"] == 500
        )  # 【確認内容】: processing_time_ms が grading_info に含まれること

    def test_grade_ai_success_response_is_json(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-RES-006: 正常系（HTTP 200）で Content-Type ヘッダーが application/json であることを確認。

        【テスト目的】: 正常系レスポンスの Content-Type ヘッダーを検証
        【テスト内容】: 正常リクエストで grade_ai_handler を呼び出し HTTP 200 かつ Content-Type を確認
        【期待される動作】: HTTP 200 かつ Content-Type が "application/json" である
        🔵 信頼性レベル: 青信号 - _make_lambda_response のレスポンスパターン（handler.py）
        """
        # 【テストデータ準備】: 正常イベント
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 200  # 【確認内容】: 正常系で HTTP 200 が返ること
        assert (
            response["headers"]["Content-Type"] == "application/json"
        )  # 【確認内容】: Content-Type が application/json であること

    def test_grade_ai_success_full_e2e_flow(self, lambda_context):
        """TC-060-RES-007: 認証 -> カード取得 -> AI 採点 -> レスポンス返却の一連フローを確認。

        【テスト目的】: grade_ai_handler の全フローが正しく動作することを検証（E2E シナリオ）
        【テスト内容】: カスタム user_id, card_id, user_answer でフル E2E テスト
        【期待される動作】: 全フィールドが正しく返される
        🔵 信頼性レベル: 青信号 - dataflow.md 機能2: 回答採点フロー全体
        """
        # 【テストデータ準備】: E2E シナリオ専用のカスタムモック
        with patch("api.handler.card_service") as mock_cs, patch(
            "api.handler.create_ai_service"
        ) as mock_factory:
            mock_card = MagicMock()
            mock_card.front = "フランスの首都は？"
            mock_card.back = "パリ"
            mock_cs.get_card.return_value = mock_card

            mock_service = MagicMock()
            mock_service.grade_answer.return_value = GradingResult(
                grade=5,
                reasoning="Perfect match",
                model_used="claude-3-haiku",
                processing_time_ms=350,
            )
            mock_factory.return_value = mock_service

            event = _make_grade_ai_event(
                user_id="e2e-user",
                card_id="e2e-card",
                body={"user_answer": "パリ"},
            )

            # 【実際の処理実行】: フル E2E フロー
            response = grade_ai_handler(event, lambda_context)

        # 【結果検証】: 全フィールドを検証
        assert response["statusCode"] == 200  # 【確認内容】: HTTP 200 が返ること
        body = json.loads(response["body"])
        assert body["grade"] == 5  # 【確認内容】: grade が 5 であること
        assert body["reasoning"] == "Perfect match"  # 【確認内容】: reasoning が正しいこと
        assert body["card_front"] == "フランスの首都は？"  # 【確認内容】: card_front が正しいこと
        assert body["card_back"] == "パリ"  # 【確認内容】: card_back が正しいこと
        assert (
            body["grading_info"]["model_used"] == "claude-3-haiku"
        )  # 【確認内容】: grading_info.model_used が正しいこと
        assert (
            body["grading_info"]["processing_time_ms"] == 350
        )  # 【確認内容】: grading_info.processing_time_ms が正しいこと

        # コール引数を検証
        mock_cs.get_card.assert_called_once_with(
            "e2e-user", "e2e-card"
        )  # 【確認内容】: get_card に正しい引数が渡されること
        mock_service.grade_answer.assert_called_once_with(
            card_front="フランスの首都は？",
            card_back="パリ",
            user_answer="パリ",
            language="ja",
        )  # 【確認内容】: grade_answer に正しい引数が渡されること


# =============================================================================
# テストカテゴリ G: AI エラーハンドリングテスト
# =============================================================================


class TestGradeAiHandlerAIErrors:
    """AI エラーハンドリングテスト（TC-060-ERR-001 ~ 007）。

    _map_ai_error_to_http() を使用した AI 例外の HTTP マッピングを検証。
    独立 Lambda では Response オブジェクトを dict 形式に変換する必要がある。
    """

    def test_grade_ai_returns_504_on_ai_timeout(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-ERR-001: AITimeoutError が HTTP 504 にマッピングされることを確認。

        【テスト目的】: AITimeoutError → 504 Gateway Timeout のマッピングを検証
        【テスト内容】: grade_answer が AITimeoutError を raise する
        【期待される動作】: HTTP 504, {"error": "AI service timeout"}
        🔵 信頼性レベル: 青信号 - _map_ai_error_to_http() 実装（handler.py L74-80）
        """
        # 【テストデータ準備】: AITimeoutError を raise する設定
        _, mock_service = mock_ai_service
        mock_service.grade_answer.side_effect = AITimeoutError("timeout")
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 504  # 【確認内容】: AITimeoutError で 504 が返ること
        body = json.loads(response["body"])
        assert body["error"] == "AI service timeout"  # 【確認内容】: エラーメッセージが "AI service timeout" であること

    def test_grade_ai_returns_429_on_ai_rate_limit(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-ERR-002: AIRateLimitError が HTTP 429 にマッピングされることを確認。

        【テスト目的】: AIRateLimitError → 429 Too Many Requests のマッピングを検証
        【テスト内容】: grade_answer が AIRateLimitError を raise する
        【期待される動作】: HTTP 429, {"error": "AI service rate limit exceeded"}
        🔵 信頼性レベル: 青信号 - _map_ai_error_to_http() 実装（handler.py L81-86）
        """
        # 【テストデータ準備】: AIRateLimitError を raise する設定
        _, mock_service = mock_ai_service
        mock_service.grade_answer.side_effect = AIRateLimitError("rate limit")
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 429  # 【確認内容】: AIRateLimitError で 429 が返ること
        body = json.loads(response["body"])
        assert (
            body["error"] == "AI service rate limit exceeded"
        )  # 【確認内容】: エラーメッセージが "AI service rate limit exceeded" であること

    def test_grade_ai_returns_503_on_ai_provider_error(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-ERR-003: AIProviderError が HTTP 503 にマッピングされることを確認。

        【テスト目的】: AIProviderError → 503 Service Unavailable のマッピングを検証
        【テスト内容】: grade_answer が AIProviderError を raise する
        【期待される動作】: HTTP 503, {"error": "AI service unavailable"}
        🔵 信頼性レベル: 青信号 - _map_ai_error_to_http() 実装（handler.py L88-93）
        """
        # 【テストデータ準備】: AIProviderError を raise する設定
        _, mock_service = mock_ai_service
        mock_service.grade_answer.side_effect = AIProviderError("provider down")
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 503  # 【確認内容】: AIProviderError で 503 が返ること
        body = json.loads(response["body"])
        assert (
            body["error"] == "AI service unavailable"
        )  # 【確認内容】: エラーメッセージが "AI service unavailable" であること

    def test_grade_ai_returns_500_on_ai_parse_error(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-ERR-004: AIParseError が HTTP 500 にマッピングされることを確認。

        【テスト目的】: AIParseError → 500 Internal Server Error のマッピングを検証
        【テスト内容】: grade_answer が AIParseError を raise する
        【期待される動作】: HTTP 500, {"error": "AI service response parse error"}
        🔵 信頼性レベル: 青信号 - _map_ai_error_to_http() 実装（handler.py L95-100）
        """
        # 【テストデータ準備】: AIParseError を raise する設定
        _, mock_service = mock_ai_service
        mock_service.grade_answer.side_effect = AIParseError("invalid json")
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 500  # 【確認内容】: AIParseError で 500 が返ること
        body = json.loads(response["body"])
        assert (
            body["error"] == "AI service response parse error"
        )  # 【確認内容】: エラーメッセージが "AI service response parse error" であること

    def test_grade_ai_returns_500_on_ai_internal_error(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-ERR-005: AIInternalError が HTTP 500 にマッピングされることを確認。

        【テスト目的】: AIInternalError → 500 Internal Server Error のマッピングを検証
        【テスト内容】: grade_answer が AIInternalError を raise する
        【期待される動作】: HTTP 500, {"error": "AI service error"}
        🔵 信頼性レベル: 青信号 - _map_ai_error_to_http() 実装（handler.py L102-106）
        """
        # 【テストデータ準備】: AIInternalError を raise する設定
        _, mock_service = mock_ai_service
        mock_service.grade_answer.side_effect = AIInternalError("internal failure")
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 500  # 【確認内容】: AIInternalError で 500 が返ること
        body = json.loads(response["body"])
        assert (
            body["error"] == "AI service error"
        )  # 【確認内容】: エラーメッセージが "AI service error" であること

    def test_grade_ai_returns_503_on_factory_init_failure(
        self, lambda_context, mock_card_service
    ):
        """TC-060-ERR-006: create_ai_service() 自体が AIProviderError を raise した場合に HTTP 503 を返すことを確認。

        【テスト目的】: AI ファクトリー初期化失敗時のエラーハンドリングを検証
        【テスト内容】: create_ai_service() が AIProviderError を raise する
        【期待される動作】: HTTP 503, {"error": "AI service unavailable"}
        🔵 信頼性レベル: 青信号 - ai_service.py「raise AIProviderError」、TC-056-013 のテストパターン
        """
        # 【テストデータ準備】: ファクトリー自体が AIProviderError を raise する
        with patch("api.handler.create_ai_service") as mock_factory:
            mock_factory.side_effect = AIProviderError(
                "Failed to initialize AI service"
            )
            event = _make_grade_ai_event()

            # 【実際の処理実行】
            response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 503  # 【確認内容】: ファクトリー初期化失敗で 503 が返ること
        body = json.loads(response["body"])
        assert (
            body["error"] == "AI service unavailable"
        )  # 【確認内容】: エラーメッセージが "AI service unavailable" であること

    def test_grade_ai_returns_500_on_unexpected_exception(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-ERR-007: 予期しない例外（RuntimeError 等）が HTTP 500 にマッピングされることを確認。

        【テスト目的】: 予期しない例外の汎用エラーハンドリングを検証
        【テスト内容】: grade_answer が RuntimeError を raise する
        【期待される動作】: HTTP 500, {"error": "Internal Server Error"}
        🔵 信頼性レベル: 青信号 - TASK-0060.md の except Exception as e パターン
        """
        # 【テストデータ準備】: RuntimeError を raise する設定
        _, mock_service = mock_ai_service
        mock_service.grade_answer.side_effect = RuntimeError("unexpected")
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        response = grade_ai_handler(event, lambda_context)

        # 【結果検証】
        assert response["statusCode"] == 500  # 【確認内容】: 予期しない例外で 500 が返ること
        body = json.loads(response["body"])
        assert (
            body["error"] == "Internal Server Error"
        )  # 【確認内容】: エラーメッセージが "Internal Server Error" であること


# =============================================================================
# テストカテゴリ H: ロギングテスト
# =============================================================================


class TestGradeAiHandlerLogging:
    """ロギング関連テスト（TC-060-LOG-001 ~ 003）。

    grade_ai_handler が適切なタイミングで適切なフィールドをロギングすることを検証。
    """

    def test_grade_ai_logs_request_info(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-LOG-001: 採点リクエスト受信時に logger.info で card_id, user_id, user_answer_length を記録することを確認。

        【テスト目的】: リクエスト受信時のロギングを検証
        【テスト内容】: user_answer="テスト回答"（5文字）でリクエスト
        【期待される動作】: logger.info が card_id, user_id, user_answer_length を含む引数で呼ばれる
        🔵 信頼性レベル: 青信号 - TASK-0060.md ロギング仕様 L204-209
        """
        # 【テストデータ準備】: ロギング検証用のリクエスト
        event = _make_grade_ai_event(body={"user_answer": "テスト回答"})

        # 【実際の処理実行】: logger をモックして呼び出しを記録
        with patch("api.handler.logger") as mock_logger:
            grade_ai_handler(event, lambda_context)

        # 【結果検証】: logger.info が card_id, user_id, user_answer_length を含む引数で呼ばれたことを確認
        info_calls_str = str(mock_logger.info.call_args_list)
        assert (
            "card" in info_calls_str or "card-123" in info_calls_str
        )  # 【確認内容】: card_id がログに含まれること

    def test_grade_ai_logs_success_info(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-LOG-002: 採点成功時に logger.info で grade を含む情報を記録することを確認。

        【テスト目的】: 採点成功時のロギングを検証
        【テスト内容】: 正常リクエスト + AI 採点成功（grade=4）
        【期待される動作】: logger.info が grade を含む引数で呼ばれる
        🔵 信頼性レベル: 青信号 - 既存 generate_cards の成功ログパターン（handler.py L324-326）
        """
        # 【テストデータ準備】: 正常フロー（AI は grade=4 を返す）
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        with patch("api.handler.logger") as mock_logger:
            grade_ai_handler(event, lambda_context)

        # 【結果検証】: logger.info が grade を含む引数で呼ばれたことを確認
        info_calls_str = str(mock_logger.info.call_args_list)
        assert (
            "grade" in info_calls_str or "4" in info_calls_str
        )  # 【確認内容】: grade がログに含まれること

    def test_grade_ai_logs_ai_error(
        self, lambda_context, mock_card_service, mock_ai_service
    ):
        """TC-060-LOG-003: AI エラー発生時に logger.warning または logger.error で記録することを確認。

        【テスト目的】: AI エラー発生時のエラーロギングを検証
        【テスト内容】: grade_answer が AITimeoutError を raise する
        【期待される動作】: logger.warning または logger.error が呼ばれる
        🔵 信頼性レベル: 青信号 - 既存 generate_cards の AI エラーログパターン（handler.py L348）
        """
        # 【テストデータ準備】: AITimeoutError を raise する設定
        _, mock_service = mock_ai_service
        mock_service.grade_answer.side_effect = AITimeoutError("timeout")
        event = _make_grade_ai_event()

        # 【実際の処理実行】
        with patch("api.handler.logger") as mock_logger:
            grade_ai_handler(event, lambda_context)

        # 【結果検証】: logger.warning または logger.error が呼ばれたことを確認
        assert (
            mock_logger.warning.called or mock_logger.error.called
        )  # 【確認内容】: AI エラー時に warning または error がログに記録されること

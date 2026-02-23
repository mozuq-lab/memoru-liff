"""Protocol 準拠テスト: BedrockService AIService Protocol 準拠改修 (TASK-0055).

このファイルは TASK-0055 の TDD Red フェーズで作成された新規テストファイルです。
既存の test_bedrock.py を変更せず、Protocol 準拠に関する全テストをここに集約します。

テスト対象:
- BedrockService が AIService Protocol を実装していること
- grade_answer() メソッドの正常系・異常系
- get_learning_advice() メソッドの正常系・異常系
- 例外クラスの AIServiceError 階層への統合
- 境界値テスト

実行方法:
    cd backend && python -m pytest tests/unit/test_bedrock_protocol.py -v
"""

import json
import pytest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError

from services.bedrock import (
    BedrockService,
    BedrockServiceError,
    BedrockTimeoutError,
    BedrockRateLimitError,
    BedrockInternalError,
    BedrockParseError,
    GeneratedCard,
)
from services.ai_service import (
    AIService,
    AIServiceError,
    AITimeoutError,
    AIRateLimitError,
    AIInternalError,
    AIParseError,
    GradingResult,
    LearningAdvice,
)


class TestBedrockServiceProtocol:
    """Protocol 準拠テスト (TC-055-001, TC-055-002)."""

    def test_bedrock_service_implements_ai_service_protocol(self):
        # 【テスト目的】: BedrockService が AIService Protocol を満たすことを確認
        # 【テスト内容】: runtime_checkable Protocol の isinstance チェック
        # 【期待される動作】: 3メソッドを実装していれば True を返す
        # 🔵

        # Given
        # 【テストデータ準備】: モッククライアントでサービスインスタンス作成
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        # Then
        # 【結果検証】: Protocol 準拠チェック
        # 【検証項目】: isinstance で Protocol 適合を確認
        assert isinstance(service, AIService)  # 【確認内容】: AIService Protocol を満たすこと

    def test_bedrock_service_has_all_protocol_methods(self):
        # 【テスト目的】: Protocol で定義された全メソッドが存在することを確認
        # 【テスト内容】: hasattr + callable で各メソッドを検証
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        # Then
        assert hasattr(service, 'generate_cards') and callable(service.generate_cards)
        assert hasattr(service, 'grade_answer') and callable(service.grade_answer)
        assert hasattr(service, 'get_learning_advice') and callable(service.get_learning_advice)


class TestGradeAnswerSuccess:
    """grade_answer() 正常系テスト (TC-055-003 ~ TC-055-007)."""

    def test_grade_answer_correct_answer_japanese(self):
        # 【テスト目的】: 日本語の正解回答が高グレードで採点されることを確認
        # 【テスト内容】: card_front/card_back/user_answer を日本語で指定し、grade=5 のレスポンスを検証
        # 【期待される動作】: GradingResult(grade=5, reasoning="完全一致です。", ...) が返る
        # 🔵

        # Given
        # 【テストデータ準備】: 正解と一致するユーザー回答を用意
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        grading_response = {
            "grade": 5,
            "reasoning": "完全一致です。",
            "feedback": "素晴らしいです。"
        }
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps(grading_response)}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When
        # 【実際の処理実行】: grade_answer() を日本語パラメータで呼び出し
        result = service.grade_answer(
            card_front="日本の首都は？",
            card_back="東京",
            user_answer="東京",
            language="ja",
        )

        # Then
        # 【結果検証】: GradingResult の全フィールドを検証
        assert isinstance(result, GradingResult)
        assert result.grade == 5                      # 【検証項目】: グレードが5であること
        assert result.reasoning == "完全一致です。"      # 【検証項目】: 推論理由が設定されること
        assert isinstance(result.model_used, str)      # 【検証項目】: モデルIDが文字列であること
        assert result.processing_time_ms >= 0          # 【検証項目】: 処理時間が非負であること
        mock_client.invoke_model.assert_called_once()  # 【検証項目】: API が1回呼ばれること

    def test_grade_answer_wrong_answer_english(self):
        # 【テスト目的】: 誤った回答が低グレードで採点されることを確認
        # 【テスト内容】: 全く関係ない回答に対して grade=0 のレスポンスを検証
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        grading_response = {
            "grade": 0,
            "reasoning": "Completely incorrect. The answer is unrelated.",
            "feedback": "Review the concept of programming languages."
        }
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps(grading_response)}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When
        result = service.grade_answer(
            card_front="What is Python?",
            card_back="A programming language",
            user_answer="A type of snake",
            language="en",
        )

        # Then
        assert isinstance(result, GradingResult)
        assert result.grade == 0
        assert len(result.reasoning) > 0

    def test_grade_answer_partial_answer(self):
        # 【テスト目的】: 部分的に正しい回答が中間グレードで採点されることを確認
        # 🟡

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        grading_response = {
            "grade": 3,
            "reasoning": "概念は理解しているが詳細が不足しています。",
            "feedback": "もう少し具体的に回答してみましょう。"
        }
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps(grading_response)}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When
        result = service.grade_answer(
            card_front="光合成とは？",
            card_back="植物が光エネルギーを使って二酸化炭素と水から有機物を合成する反応",
            user_answer="植物が光で何かを作る反応",
            language="ja",
        )

        # Then
        assert isinstance(result, GradingResult)
        assert result.grade == 3
        assert 0 <= result.grade <= 5

    def test_grade_answer_english_language(self):
        # 【テスト目的】: 英語での採点が正常に動作することを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        grading_response = {
            "grade": 4,
            "reasoning": "Correct with minor hesitation.",
            "feedback": "Good job!"
        }
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps(grading_response)}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When
        result = service.grade_answer(
            card_front="What is the capital of France?",
            card_back="Paris",
            user_answer="Paris",
            language="en",
        )

        # Then
        assert isinstance(result, GradingResult)
        assert result.grade == 4
        assert result.reasoning == "Correct with minor hesitation."
        mock_client.invoke_model.assert_called_once()

    def test_grade_answer_uses_retry_logic(self):
        # 【テスト目的】: grade_answer() がリトライ機構を使用することを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        grading_response = {"grade": 4, "reasoning": "Good.", "feedback": "OK."}
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps(grading_response)}]
        }).encode()

        mock_client.invoke_model.side_effect = [
            ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
                "InvokeModel",
            ),
            {"body": mock_response_body},
        ]

        # When
        result = service.grade_answer(
            card_front="Q", card_back="A", user_answer="A",
        )

        # Then
        assert isinstance(result, GradingResult)
        assert mock_client.invoke_model.call_count == 2  # 【検証項目】: リトライで2回呼ばれること


class TestGetLearningAdviceSuccess:
    """get_learning_advice() 正常系テスト (TC-055-008 ~ TC-055-011)."""

    def test_get_learning_advice_with_dict_input(self):
        # 【テスト目的】: dict 形式の入力で学習アドバイスが正常に生成されることを確認
        # 【テスト内容】: 典型的な復習統計データを渡し、LearningAdvice の全フィールドを検証
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        advice_response = {
            "advice_text": "有機化学の復習を重点的に行いましょう。",
            "weak_areas": ["有機化学"],
            "recommendations": ["有機化学のカードを毎日5枚復習する", "間隔を短くして反復回数を増やす"]
        }
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps(advice_response)}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        review_summary = {
            "total_reviews": 100,
            "average_grade": 3.2,
            "total_cards": 50,
            "cards_due_today": 10,
            "streak_days": 5,
            "tag_performance": {"生物学": 3.8, "有機化学": 2.1},
        }

        # When
        result = service.get_learning_advice(
            review_summary=review_summary,
            language="ja",
        )

        # Then
        assert isinstance(result, LearningAdvice)
        assert result.advice_text == "有機化学の復習を重点的に行いましょう。"
        assert result.weak_areas == ["有機化学"]
        assert len(result.recommendations) == 2
        assert isinstance(result.model_used, str)
        assert result.processing_time_ms >= 0
        mock_client.invoke_model.assert_called_once()

    def test_get_learning_advice_english_language(self):
        # 【テスト目的】: 英語での学習アドバイス生成が正常に動作することを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        advice_response = {
            "advice_text": "Focus on improving your vocabulary section.",
            "weak_areas": ["vocabulary"],
            "recommendations": ["Review vocabulary cards daily"]
        }
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps(advice_response)}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When
        result = service.get_learning_advice(
            review_summary={"total_reviews": 50, "average_grade": 2.5, "total_cards": 30,
                            "cards_due_today": 5, "streak_days": 3, "tag_performance": {"vocabulary": 2.0}},
            language="en",
        )

        # Then
        assert isinstance(result, LearningAdvice)
        assert result.advice_text == "Focus on improving your vocabulary section."
        assert result.weak_areas == ["vocabulary"]

    def test_get_learning_advice_with_low_scores(self):
        # 【テスト目的】: 低スコアの復習データでアドバイスが正常に生成されることを確認
        # 🟡

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        advice_response = {
            "advice_text": "全体的にスコアが低いため、基礎から見直しましょう。",
            "weak_areas": ["数学", "物理", "化学"],
            "recommendations": ["基礎カードから始める", "毎日の学習時間を増やす"]
        }
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps(advice_response)}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When
        result = service.get_learning_advice(
            review_summary={
                "total_reviews": 30,
                "average_grade": 1.5,
                "total_cards": 20,
                "cards_due_today": 15,
                "streak_days": 1,
                "tag_performance": {"数学": 1.2, "物理": 1.5, "化学": 1.8},
            },
            language="ja",
        )

        # Then
        assert isinstance(result, LearningAdvice)
        assert len(result.weak_areas) > 0
        assert len(result.recommendations) > 0

    def test_get_learning_advice_uses_retry_logic(self):
        # 【テスト目的】: get_learning_advice() がリトライ機構を使用することを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        advice_response = {"advice_text": "...", "weak_areas": [], "recommendations": []}
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps(advice_response)}]
        }).encode()

        mock_client.invoke_model.side_effect = [
            ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
                "InvokeModel",
            ),
            {"body": mock_response_body},
        ]

        # When
        result = service.get_learning_advice(
            review_summary={"total_reviews": 10, "average_grade": 3.0, "total_cards": 5,
                            "cards_due_today": 2, "streak_days": 1, "tag_performance": {}},
        )

        # Then
        assert isinstance(result, LearningAdvice)
        assert mock_client.invoke_model.call_count == 2


class TestGenerateCardsCompatibility:
    """generate_cards() 既存互換性テスト (TC-055-012)."""

    def test_generate_cards_still_works_after_protocol_adaptation(self):
        # 【テスト目的】: Protocol 準拠改修後も generate_cards() が正常動作することを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": '{"cards": [{"front": "Q", "back": "A", "tags": []}]}'}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When
        result = service.generate_cards(
            input_text="Test input text for card generation",
            card_count=1,
        )

        # Then
        assert len(result.cards) == 1
        assert result.cards[0].front == "Q"
        assert result.cards[0].back == "A"
        assert result.processing_time_ms >= 0
        assert isinstance(result.model_used, str)


class TestGradeAnswerErrors:
    """grade_answer() エラーハンドリングテスト (TC-055-013 ~ TC-055-018)."""

    def test_grade_answer_timeout_error(self):
        # 【テスト目的】: タイムアウト時に BedrockTimeoutError が発生することを確認
        # 【テスト内容】: ReadTimeoutError を発生させ、例外の型と階層を検証
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)
        mock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ReadTimeoutError", "Message": "Timeout"}},
            "InvokeModel",
        )

        # When / Then
        with pytest.raises(BedrockTimeoutError):
            service.grade_answer(card_front="Q", card_back="A", user_answer="A")

        # 【検証項目】: リトライなし（タイムアウトはリトライしない）
        assert mock_client.invoke_model.call_count == 1

    def test_grade_answer_timeout_caught_as_ai_timeout_error(self):
        # 【テスト目的】: BedrockTimeoutError が AITimeoutError でもキャッチできることを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)
        mock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ReadTimeoutError", "Message": "Timeout"}},
            "InvokeModel",
        )

        # When / Then
        # 【結果検証】: AITimeoutError でキャッチ可能であること
        with pytest.raises(AITimeoutError):
            service.grade_answer(card_front="Q", card_back="A", user_answer="A")

    def test_grade_answer_rate_limit_error(self):
        # 【テスト目的】: レート制限時にリトライ後 BedrockRateLimitError が発生することを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)
        mock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
            "InvokeModel",
        )

        # When / Then
        with pytest.raises(BedrockRateLimitError):
            service.grade_answer(card_front="Q", card_back="A", user_answer="A")

        # 【検証項目】: 初回 + 2回リトライ = 3回呼ばれること
        assert mock_client.invoke_model.call_count == 3

    def test_grade_answer_parse_error(self):
        # 【テスト目的】: 不正な JSON レスポンスで BedrockParseError が発生することを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": "This is not valid JSON at all"}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When / Then
        with pytest.raises(BedrockParseError):
            service.grade_answer(card_front="Q", card_back="A", user_answer="A")

    def test_grade_answer_parse_error_caught_as_ai_parse_error(self):
        # 【テスト目的】: BedrockParseError が AIParseError でもキャッチできることを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": "Not JSON"}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When / Then
        with pytest.raises(AIParseError):
            service.grade_answer(card_front="Q", card_back="A", user_answer="A")

    def test_grade_answer_internal_error(self):
        # 【テスト目的】: Bedrock API 内部エラー時に BedrockInternalError が発生することを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)
        mock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "InternalServerException", "Message": "Internal"}},
            "InvokeModel",
        )

        # When / Then
        with pytest.raises(BedrockInternalError):
            service.grade_answer(card_front="Q", card_back="A", user_answer="A")

        # 【検証項目】: 内部エラーはリトライされる（3回呼ばれる）
        assert mock_client.invoke_model.call_count == 3


class TestGetLearningAdviceErrors:
    """get_learning_advice() エラーハンドリングテスト (TC-055-019 ~ TC-055-021)."""

    def test_get_learning_advice_timeout_error(self):
        # 【テスト目的】: get_learning_advice() のタイムアウトエラーを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)
        mock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ReadTimeoutError", "Message": "Timeout"}},
            "InvokeModel",
        )

        # When / Then
        with pytest.raises(BedrockTimeoutError):
            service.get_learning_advice(
                review_summary={"total_reviews": 10, "average_grade": 3.0, "total_cards": 5,
                                "cards_due_today": 2, "streak_days": 1, "tag_performance": {}},
            )

        assert mock_client.invoke_model.call_count == 1

    def test_get_learning_advice_parse_error(self):
        # 【テスト目的】: get_learning_advice() のパースエラーを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": "Invalid response text"}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When / Then
        with pytest.raises(BedrockParseError):
            service.get_learning_advice(
                review_summary={"total_reviews": 10, "average_grade": 3.0, "total_cards": 5,
                                "cards_due_today": 2, "streak_days": 1, "tag_performance": {}},
            )

    def test_get_learning_advice_rate_limit_error(self):
        # 【テスト目的】: get_learning_advice() のレート制限エラーを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)
        mock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
            "InvokeModel",
        )

        # When / Then
        with pytest.raises(BedrockRateLimitError):
            service.get_learning_advice(
                review_summary={"total_reviews": 10, "average_grade": 3.0, "total_cards": 5,
                                "cards_due_today": 2, "streak_days": 1, "tag_performance": {}},
            )

        assert mock_client.invoke_model.call_count == 3


class TestExceptionHierarchy:
    """例外階層テスト (TC-055-022 ~ TC-055-025)."""

    def test_exception_hierarchy_ai_service_error(self):
        # 【テスト目的】: 全 Bedrock 例外が AIServiceError 階層に統合されていることを確認
        # 🔵

        # BedrockServiceError → AIServiceError
        assert issubclass(BedrockServiceError, AIServiceError)

        # BedrockTimeoutError → AITimeoutError + BedrockServiceError
        assert issubclass(BedrockTimeoutError, AITimeoutError)
        assert issubclass(BedrockTimeoutError, BedrockServiceError)
        assert issubclass(BedrockTimeoutError, AIServiceError)

        # BedrockRateLimitError → AIRateLimitError + BedrockServiceError
        assert issubclass(BedrockRateLimitError, AIRateLimitError)
        assert issubclass(BedrockRateLimitError, BedrockServiceError)
        assert issubclass(BedrockRateLimitError, AIServiceError)

        # BedrockInternalError → AIInternalError + BedrockServiceError
        assert issubclass(BedrockInternalError, AIInternalError)
        assert issubclass(BedrockInternalError, BedrockServiceError)
        assert issubclass(BedrockInternalError, AIServiceError)

        # BedrockParseError → AIParseError + BedrockServiceError
        assert issubclass(BedrockParseError, AIParseError)
        assert issubclass(BedrockParseError, BedrockServiceError)
        assert issubclass(BedrockParseError, AIServiceError)

    def test_backward_compatibility_bedrock_service_error_catches_all(self):
        # 【テスト目的】: except BedrockServiceError が全 Bedrock 例外をキャッチできることを確認
        # 🔵

        # 【テストデータ準備】: 各例外インスタンスを作成
        exceptions = [
            BedrockTimeoutError("timeout"),
            BedrockRateLimitError("rate limit"),
            BedrockInternalError("internal"),
            BedrockParseError("parse"),
        ]

        for exc in exceptions:
            # 【結果検証】: except BedrockServiceError でキャッチ可能
            try:
                raise exc
            except BedrockServiceError:
                pass  # 期待通りキャッチされた
            except Exception:
                pytest.fail(f"{type(exc).__name__} was not caught by except BedrockServiceError")

    def test_ai_service_error_catches_bedrock_exceptions(self):
        # 【テスト目的】: except AIServiceError が全 Bedrock 例外をキャッチできることを確認
        # 🔵

        exceptions = [
            BedrockServiceError("base"),
            BedrockTimeoutError("timeout"),
            BedrockRateLimitError("rate limit"),
            BedrockInternalError("internal"),
            BedrockParseError("parse"),
        ]

        for exc in exceptions:
            try:
                raise exc
            except AIServiceError:
                pass
            except Exception:
                pytest.fail(f"{type(exc).__name__} was not caught by except AIServiceError")

    def test_specific_ai_errors_catch_bedrock_exceptions(self):
        # 【テスト目的】: 具体的な AI 例外が対応する Bedrock 例外をキャッチできることを確認
        # 🔵

        # AITimeoutError → BedrockTimeoutError
        with pytest.raises(AITimeoutError):
            raise BedrockTimeoutError("timeout")

        # AIRateLimitError → BedrockRateLimitError
        with pytest.raises(AIRateLimitError):
            raise BedrockRateLimitError("rate limit")

        # AIInternalError → BedrockInternalError
        with pytest.raises(AIInternalError):
            raise BedrockInternalError("internal")

        # AIParseError → BedrockParseError
        with pytest.raises(AIParseError):
            raise BedrockParseError("parse")


class TestBoundaryValues:
    """境界値テスト (TC-055-026 ~ TC-055-034)."""

    def test_grade_answer_minimum_grade_zero(self):
        # 【テスト目的】: grade=0（最小値）が正しく処理されることを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps({"grade": 0, "reasoning": "Complete blackout", "feedback": "..."})}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When
        result = service.grade_answer(card_front="Q", card_back="A", user_answer="")

        # Then
        assert result.grade == 0

    def test_grade_answer_maximum_grade_five(self):
        # 【テスト目的】: grade=5（最大値）が正しく処理されることを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps({"grade": 5, "reasoning": "Perfect", "feedback": "..."})}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When
        result = service.grade_answer(card_front="Q", card_back="A", user_answer="A")

        # Then
        assert result.grade == 5

    def test_grade_answer_out_of_range_grade(self):
        # 【テスト目的】: grade が範囲外(6)の場合のハンドリングを確認
        # 【注意】: 実装に応じて AIParseError を期待するか、クランプを期待するか調整が必要
        # 🟡

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps({"grade": 6, "reasoning": "...", "feedback": "..."})}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When / Then
        # 実装方針A: エラーを送出する場合
        # with pytest.raises((BedrockParseError, AIParseError)):
        #     service.grade_answer(card_front="Q", card_back="A", user_answer="A")

        # 実装方針B: クランプする場合
        # result = service.grade_answer(card_front="Q", card_back="A", user_answer="A")
        # assert 0 <= result.grade <= 5
        pass  # 実装方針に応じてアサーションを選択

    def test_get_learning_advice_empty_weak_areas_and_recommendations(self):
        # 【テスト目的】: 空の weak_areas/recommendations が正常に処理されることを確認
        # 🟡

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        advice_response = {
            "advice_text": "素晴らしい学習成績です！この調子で頑張りましょう。",
            "weak_areas": [],
            "recommendations": []
        }
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps(advice_response)}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When
        result = service.get_learning_advice(
            review_summary={
                "total_reviews": 200,
                "average_grade": 4.8,
                "total_cards": 100,
                "cards_due_today": 3,
                "streak_days": 30,
                "tag_performance": {"数学": 4.9, "英語": 4.7},
            },
            language="ja",
        )

        # Then
        assert isinstance(result, LearningAdvice)
        assert result.weak_areas == []
        assert result.recommendations == []
        assert len(result.advice_text) > 0

    def test_get_learning_advice_empty_tag_performance(self):
        # 【テスト目的】: 空の tag_performance でも正常に動作することを確認
        # 🟡

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        advice_response = {
            "advice_text": "タグ別データがないため、全般的なアドバイスです。",
            "weak_areas": [],
            "recommendations": ["まずカードにタグを付けて学習しましょう"]
        }
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps(advice_response)}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When
        result = service.get_learning_advice(
            review_summary={
                "total_reviews": 5,
                "average_grade": 3.0,
                "total_cards": 3,
                "cards_due_today": 1,
                "streak_days": 1,
                "tag_performance": {},
            },
        )

        # Then
        assert isinstance(result, LearningAdvice)
        assert len(result.advice_text) > 0

    def test_grade_answer_json_in_markdown_code_block(self):
        # 【テスト目的】: マークダウンコードブロック内の JSON が正しくパースされることを確認
        # 🟡

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        json_in_code_block = '```json\n{"grade": 4, "reasoning": "Good answer.", "feedback": "Nice!"}\n```'
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json_in_code_block}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When
        result = service.grade_answer(card_front="Q", card_back="A", user_answer="A")

        # Then
        assert isinstance(result, GradingResult)
        assert result.grade == 4

    def test_get_learning_advice_json_in_markdown_code_block(self):
        # 【テスト目的】: get_learning_advice() がマークダウンコードブロック内 JSON を処理できることを確認
        # 🟡

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        json_in_code_block = '```json\n{"advice_text": "Keep studying!", "weak_areas": ["math"], "recommendations": ["Practice daily"]}\n```'
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json_in_code_block}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When
        result = service.get_learning_advice(
            review_summary={"total_reviews": 10, "average_grade": 2.5, "total_cards": 5,
                            "cards_due_today": 2, "streak_days": 1, "tag_performance": {}},
        )

        # Then
        assert isinstance(result, LearningAdvice)
        assert result.advice_text == "Keep studying!"

    def test_processing_time_ms_is_non_negative_integer(self):
        # 【テスト目的】: grade_answer() と get_learning_advice() の processing_time_ms が非負整数であることを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(bedrock_client=mock_client)

        # grade_answer 用
        grading_response = {"grade": 3, "reasoning": "OK", "feedback": "..."}
        mock_response_body_grading = MagicMock()
        mock_response_body_grading.read.return_value = json.dumps({
            "content": [{"text": json.dumps(grading_response)}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body_grading}

        result_grading = service.grade_answer(card_front="Q", card_back="A", user_answer="A")
        assert isinstance(result_grading.processing_time_ms, int)
        assert result_grading.processing_time_ms >= 0

        # get_learning_advice 用
        mock_client.reset_mock()
        advice_response = {"advice_text": "...", "weak_areas": [], "recommendations": []}
        mock_response_body_advice = MagicMock()
        mock_response_body_advice.read.return_value = json.dumps({
            "content": [{"text": json.dumps(advice_response)}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body_advice}

        result_advice = service.get_learning_advice(
            review_summary={"total_reviews": 10, "average_grade": 3.0, "total_cards": 5,
                            "cards_due_today": 2, "streak_days": 1, "tag_performance": {}},
        )
        assert isinstance(result_advice.processing_time_ms, int)
        assert result_advice.processing_time_ms >= 0

    def test_model_used_matches_service_model_id(self):
        # 【テスト目的】: GradingResult/LearningAdvice の model_used がサービスのモデル ID と一致することを確認
        # 🔵

        # Given
        mock_client = MagicMock()
        service = BedrockService(model_id="custom-model-id", bedrock_client=mock_client)

        grading_response = {"grade": 4, "reasoning": "Good", "feedback": "..."}
        mock_response_body = MagicMock()
        mock_response_body.read.return_value = json.dumps({
            "content": [{"text": json.dumps(grading_response)}]
        }).encode()
        mock_client.invoke_model.return_value = {"body": mock_response_body}

        # When
        result = service.grade_answer(card_front="Q", card_back="A", user_answer="A")

        # Then
        assert result.model_used == "custom-model-id"

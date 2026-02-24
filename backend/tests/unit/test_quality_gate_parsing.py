"""TASK-0065: 品質ゲート - レスポンス解析とプロンプトセキュリティ.

カテゴリ 10: StrandsAIService レスポンス解析 (TC-QG-013)
カテゴリ 11: BedrockService レスポンス解析 (TC-QG-014)
カテゴリ 12: プロンプトセキュリティ (TC-QG-015)

🔵 信頼性: 既存 test_quality_gate.py から分割。ロジック変更なし。
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from services.ai_service import AIParseError
from services.bedrock import BedrockParseError, BedrockService
from services.strands_service import StrandsAIService
from tests.unit.conftest import make_bedrock_response, make_mock_agent


# =============================================================================
# カテゴリ 10: StrandsAIService レスポンス解析 (TestStrandsResponseParsingFinal)
# =============================================================================


class TestStrandsResponseParsingFinal:
    """StrandsAIService の 3 つのパーサーの動作を最終確認 (TC-QG-013-001 ~ TC-QG-013-010).

    【テスト方針】: Agent のレスポンステキストをモックし、各パーサーが
    正しく JSON を解析できるか、エラー時に AIParseError を raise するかを検証する。
    """

    @pytest.fixture
    def strands_service(self):
        """BedrockModel をモックした StrandsAIService のインスタンスを提供する."""
        with patch("services.strands_service.BedrockModel"), patch.dict("os.environ", {"ENVIRONMENT": "prod"}):
            service = StrandsAIService()
        return service

    def test_plain_json_generate_cards(self, strands_service):
        """TC-QG-013-001: プレーン JSON レスポンスが正しく解析される (generate_cards)."""
        response_text = json.dumps({
            "cards": [{"front": "Q", "back": "A", "tags": ["tag"]}]
        })
        mock_agent = make_mock_agent(response_text)

        with patch("services.strands_service.Agent", return_value=mock_agent):
            result = strands_service.generate_cards(input_text="test")

        assert len(result.cards) == 1
        assert result.cards[0].front == "Q"
        assert result.cards[0].back == "A"

    def test_markdown_json_generate_cards(self, strands_service):
        """TC-QG-013-002: Markdown ```json ... ``` コードブロックが正しく解析される (generate_cards)."""
        response_text = '```json\n{"cards": [{"front": "Q", "back": "A", "tags": []}]}\n```'
        mock_agent = make_mock_agent(response_text)

        with patch("services.strands_service.Agent", return_value=mock_agent):
            result = strands_service.generate_cards(input_text="test")

        assert len(result.cards) == 1

    def test_missing_cards_field_raises_parse_error(self, strands_service):
        """TC-QG-013-003: "cards" フィールド欠落時に AIParseError が raise される."""
        response_text = json.dumps({"data": []})
        mock_agent = make_mock_agent(response_text)

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AIParseError):
                strands_service.generate_cards(input_text="test")

    def test_invalid_json_raises_parse_error(self, strands_service):
        """TC-QG-013-004: 不正 JSON 文字列に対して AIParseError が raise される."""
        response_text = "This is not valid JSON at all"
        mock_agent = make_mock_agent(response_text)

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AIParseError):
                strands_service.generate_cards(input_text="test")

    def test_cards_with_missing_fields_are_skipped(self, strands_service):
        """TC-QG-013-005: front/back 欠落のカードがスキップされる (空でないカードのみ返却)."""
        response_text = json.dumps({
            "cards": [
                {"front": "", "back": "A1"},           # front が空 → スキップ
                {"back": "A2"},                         # front 欠落 → スキップ
                {"front": "Q3", "back": "A3"},          # 有効
            ]
        })
        mock_agent = make_mock_agent(response_text)

        with patch("services.strands_service.Agent", return_value=mock_agent):
            result = strands_service.generate_cards(input_text="test")

        assert len(result.cards) == 1
        assert result.cards[0].front == "Q3"

    def test_zero_valid_cards_raises_parse_error(self, strands_service):
        """TC-QG-013-006: 有効カード 0 枚時に AIParseError が raise される."""
        response_text = json.dumps({
            "cards": [
                {"front": "", "back": "A1"},
                {"back": "A2"},
            ]
        })
        mock_agent = make_mock_agent(response_text)

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AIParseError):
                strands_service.generate_cards(input_text="test")

    def test_ai_tag_auto_inserted(self, strands_service):
        """TC-QG-013-007: "AI生成" タグが未設定のカードに自動挿入される."""
        response_text = json.dumps({
            "cards": [{"front": "Q", "back": "A"}]  # tags なし
        })
        mock_agent = make_mock_agent(response_text)

        with patch("services.strands_service.Agent", return_value=mock_agent):
            result = strands_service.generate_cards(input_text="test")

        assert "AI生成" in result.cards[0].suggested_tags

    @pytest.mark.parametrize("response_json", [
        {"reasoning": "..."},             # grade 欠落
        {"grade": 5},                     # reasoning 欠落
    ])
    def test_grade_answer_missing_required_fields_raises_parse_error(
        self, strands_service, response_json
    ):
        """TC-QG-013-008: grade_answer パース: "grade" / "reasoning" 欠落時に AIParseError."""
        response_text = json.dumps(response_json)
        mock_agent = make_mock_agent(response_text)

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AIParseError):
                strands_service.grade_answer(card_front="Q", card_back="A", user_answer="A")

    def test_grade_answer_non_int_grade_raises_parse_error(self, strands_service):
        """TC-QG-013-009: grade_answer パース: grade が整数に変換できない場合に AIParseError."""
        response_text = json.dumps({"grade": "five", "reasoning": "..."})
        mock_agent = make_mock_agent(response_text)

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AIParseError):
                strands_service.grade_answer(card_front="Q", card_back="A", user_answer="A")

    @pytest.mark.parametrize("missing_field", ["advice_text", "weak_areas", "recommendations"])
    def test_get_learning_advice_missing_fields_raises_parse_error(self, strands_service, missing_field):
        """TC-QG-013-010: get_learning_advice パース: 必須フィールド欠落時に AIParseError."""
        complete_response = {
            "advice_text": "Study well",
            "weak_areas": ["vocab"],
            "recommendations": ["Review daily"],
        }
        complete_response.pop(missing_field)
        response_text = json.dumps(complete_response)
        mock_agent = make_mock_agent(response_text)

        with patch("services.strands_service.Agent", return_value=mock_agent):
            with pytest.raises(AIParseError):
                strands_service.get_learning_advice(review_summary={})


# =============================================================================
# カテゴリ 11: BedrockService レスポンス解析 (TestBedrockResponseParsingFinal)
# =============================================================================


class TestBedrockResponseParsingFinal:
    """BedrockService のパーサー (_parse_response, _parse_json_response) の動作を最終確認.

    TC-QG-014-001 ~ TC-QG-014-005

    【テスト方針】: invoke_model の戻り値をモックして、BedrockService の
    レスポンスパーサーが JSON と Markdown コードブロックを正しく処理することを確認する。
    """

    def _setup_service_with_response(self, response_text: str) -> BedrockService:
        """指定したレスポンステキストを返すモック Bedrock クライアントで BedrockService を設定する."""
        mock_client = MagicMock()
        mock_client.invoke_model.return_value = make_bedrock_response(response_text)
        return BedrockService(bedrock_client=mock_client)

    def test_plain_json_generate_cards(self):
        """TC-QG-014-001: プレーン JSON レスポンスが正しく解析される (generate_cards)."""
        response_text = json.dumps({
            "cards": [{"front": "Q", "back": "A", "tags": ["tag"]}]
        })
        service = self._setup_service_with_response(response_text)
        result = service.generate_cards(input_text="test input")

        assert len(result.cards) == 1
        assert result.cards[0].front == "Q"
        assert result.cards[0].back == "A"

    def test_markdown_json_generate_cards(self):
        """TC-QG-014-002: Markdown ```json ... ``` コードブロックが正しく解析される."""
        response_text = '```json\n{"cards": [{"front": "Q", "back": "A", "tags": []}]}\n```'
        service = self._setup_service_with_response(response_text)
        result = service.generate_cards(input_text="test input")

        assert len(result.cards) == 1

    def test_missing_cards_field_raises_bedrock_parse_error(self):
        """TC-QG-014-003: "cards" フィールド欠落時に BedrockParseError が raise される."""
        response_text = json.dumps({"data": []})
        service = self._setup_service_with_response(response_text)

        with pytest.raises(BedrockParseError):
            service.generate_cards(input_text="test input")

    @pytest.mark.parametrize("method_name,response_json,kwargs", [
        (
            "grade_answer",
            {"reasoning": "..."},  # grade 欠落
            {"card_front": "Q", "card_back": "A", "user_answer": "A"},
        ),
        (
            "get_learning_advice",
            {"advice_text": "...", "weak_areas": []},  # recommendations 欠落
            {"review_summary": {}},
        ),
    ])
    def test_missing_required_fields_raises_bedrock_parse_error(
        self, method_name, response_json, kwargs
    ):
        """TC-QG-014-004: 必須フィールド欠落時に BedrockParseError (grade, advice)."""
        response_text = json.dumps(response_json)
        service = self._setup_service_with_response(response_text)

        with pytest.raises(BedrockParseError):
            getattr(service, method_name)(**kwargs)

    def test_invalid_json_raises_bedrock_parse_error(self):
        """TC-QG-014-005: 不正 JSON 文字列に対して BedrockParseError が raise される."""
        response_text = "Not valid JSON"
        service = self._setup_service_with_response(response_text)

        with pytest.raises(BedrockParseError):
            service.generate_cards(input_text="test input")


# =============================================================================
# カテゴリ 12: プロンプトセキュリティ (TestPromptSecurityFinal)
# =============================================================================


class TestPromptSecurityFinal:
    """プロンプトテンプレートとシステムプロンプトの構造的分離を最終確認 (TC-QG-015-001 ~ TC-QG-015-005).

    【テスト方針】: プロンプト関数がユーザー入力を正しくテンプレートに埋め込むことと、
    システムプロンプト定数にユーザー入力変数が混入していないことを確認する。
    """

    def test_get_card_generation_prompt_embeds_input_text(self):
        """TC-QG-015-001: get_card_generation_prompt() が入力テキストをテンプレートに埋め込んで返す."""
        from services.prompts.generate import get_card_generation_prompt

        input_text = "テストテキスト"
        card_count = 3
        result = get_card_generation_prompt(
            input_text=input_text,
            card_count=card_count,
            difficulty="medium",
            language="ja",
        )

        assert input_text in result
        assert str(card_count) in result

    def test_get_grading_prompt_embeds_card_fields(self):
        """TC-QG-015-002: get_grading_prompt() が card_front, card_back, user_answer をテンプレートに埋め込んで返す."""
        from services.prompts.grading import get_grading_prompt

        card_front = "日本の首都は？"
        card_back = "東京"
        user_answer = "東京"
        result = get_grading_prompt(
            card_front=card_front,
            card_back=card_back,
            user_answer=user_answer,
        )

        assert card_front in result
        assert card_back in result

    def test_get_advice_prompt_embeds_review_summary(self):
        """TC-QG-015-003: get_advice_prompt() が review_summary データを埋め込んで返す."""
        from services.prompts.advice import get_advice_prompt

        review_summary = {
            "total_reviews": 100,
            "average_grade": 3.5,
            "total_cards": 50,
            "cards_due_today": 10,
            "streak_days": 7,
        }
        result = get_advice_prompt(review_summary=review_summary, language="ja")

        assert "100" in result
        assert "3.5" in result
        assert "50" in result

    def test_grading_system_prompt_contains_no_user_input_variables(self):
        """TC-QG-015-004: GRADING_SYSTEM_PROMPT 定数がユーザー入力変数を含まない."""
        from services.prompts.grading import GRADING_SYSTEM_PROMPT

        # 【セキュリティ検証】: システムプロンプトにユーザー入力変数が混入していないことを確認
        user_input_vars = [
            "{card_front}",
            "{card_back}",
            "{user_answer}",
            "{input_text}",
        ]
        for var in user_input_vars:
            assert var not in GRADING_SYSTEM_PROMPT, (
                f"GRADING_SYSTEM_PROMPT should not contain user input variable {var!r}"
            )

    def test_advice_system_prompt_contains_no_user_input_variables(self):
        """TC-QG-015-005: ADVICE_SYSTEM_PROMPT 定数がユーザー入力変数を含まない."""
        from services.prompts.advice import ADVICE_SYSTEM_PROMPT

        # 【セキュリティ検証】: システムプロンプトにユーザー入力変数が混入していないことを確認
        user_input_vars = [
            "{review_summary}",
            "{total_reviews}",
            "{average_grade}",
            "{input_text}",
        ]
        for var in user_input_vars:
            assert var not in ADVICE_SYSTEM_PROMPT, (
                f"ADVICE_SYSTEM_PROMPT should not contain user input variable {var!r}"
            )

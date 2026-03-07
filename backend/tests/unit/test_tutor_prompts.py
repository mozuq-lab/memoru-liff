"""Unit tests for tutor prompts — TDD Red Phase.

Tests mode-specific prompt generation, card context injection,
and language-matching instruction.
"""

import pytest


class TestGetSystemPrompt:
    """Tests for get_system_prompt function."""

    def test_free_talk_prompt_contains_mode_instruction(self):
        from services.prompts.tutor import get_system_prompt

        prompt = get_system_prompt(
            mode="free_talk",
            deck_name="英単語 基礎",
            cards_context="front: apple, back: りんご",
        )
        assert "free_talk" in prompt.lower() or "自由" in prompt or "free" in prompt.lower()

    def test_quiz_prompt_contains_quiz_instruction(self):
        from services.prompts.tutor import get_system_prompt

        prompt = get_system_prompt(
            mode="quiz",
            deck_name="英単語 基礎",
            cards_context="front: apple, back: りんご",
        )
        assert "quiz" in prompt.lower() or "クイズ" in prompt or "question" in prompt.lower()

    def test_weak_point_prompt_contains_weak_point_instruction(self):
        from services.prompts.tutor import get_system_prompt

        prompt = get_system_prompt(
            mode="weak_point",
            deck_name="英単語 基礎",
            cards_context="front: apple, back: りんご",
            weak_cards_context="apple: accuracy 30%, ease 1.3",
        )
        assert "weak" in prompt.lower() or "弱点" in prompt or "苦手" in prompt

    def test_prompt_includes_card_context(self):
        from services.prompts.tutor import get_system_prompt

        cards = "front: apple, back: りんご\nfront: dog, back: 犬"
        prompt = get_system_prompt(
            mode="free_talk",
            deck_name="テストデッキ",
            cards_context=cards,
        )
        assert "apple" in prompt
        assert "りんご" in prompt

    def test_prompt_includes_deck_name(self):
        from services.prompts.tutor import get_system_prompt

        prompt = get_system_prompt(
            mode="free_talk",
            deck_name="日本史",
            cards_context="front: 鎌倉幕府, back: 1185年",
        )
        assert "日本史" in prompt

    def test_prompt_includes_language_instruction(self):
        from services.prompts.tutor import get_system_prompt

        prompt = get_system_prompt(
            mode="free_talk",
            deck_name="テスト",
            cards_context="front: test, back: テスト",
        )
        # FR-017: Respond in the same language as card content
        assert "language" in prompt.lower() or "言語" in prompt or "同じ" in prompt

    def test_weak_point_without_context_still_works(self):
        from services.prompts.tutor import get_system_prompt

        prompt = get_system_prompt(
            mode="weak_point",
            deck_name="テスト",
            cards_context="front: test, back: テスト",
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestFormatCardsContext:
    """Tests for format_cards_context helper."""

    def test_format_cards_produces_string(self):
        from services.prompts.tutor import format_cards_context

        cards = [
            {"front": "apple", "back": "りんご"},
            {"front": "dog", "back": "犬"},
        ]
        result = format_cards_context(cards)
        assert "apple" in result
        assert "りんご" in result
        assert isinstance(result, str)

    def test_format_empty_cards_returns_empty_string(self):
        from services.prompts.tutor import format_cards_context

        result = format_cards_context([])
        assert result == ""

    def test_format_cards_includes_all_cards(self):
        from services.prompts.tutor import format_cards_context

        cards = [{"front": f"q{i}", "back": f"a{i}"} for i in range(5)]
        result = format_cards_context(cards)
        for i in range(5):
            assert f"q{i}" in result
            assert f"a{i}" in result

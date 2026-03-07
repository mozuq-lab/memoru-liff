"""Unit tests for URL card generation prompt variants (T027)."""

import pytest

from services.prompts.url_generate import (
    CARD_TYPE_INSTRUCTIONS,
    DIFFICULTY_GUIDELINES,
    get_url_card_generation_prompt,
)


class TestUrlGeneratePrompts:
    """Tests for URL-specific prompt generation."""

    def test_qa_type_japanese(self) -> None:
        """QA card type generates Q&A format instructions in Japanese."""
        prompt = get_url_card_generation_prompt(
            chunk_text="Sample content",
            card_count=5,
            card_type="qa",
            difficulty="medium",
            language="ja",
        )
        assert "Q&A" in prompt or "質問と回答" in prompt

    def test_definition_type_japanese(self) -> None:
        """Definition card type generates definition format instructions in Japanese."""
        prompt = get_url_card_generation_prompt(
            chunk_text="Sample content",
            card_count=5,
            card_type="definition",
            difficulty="medium",
            language="ja",
        )
        assert "用語" in prompt or "定義" in prompt

    def test_cloze_type_japanese(self) -> None:
        """Cloze card type generates cloze format instructions in Japanese."""
        prompt = get_url_card_generation_prompt(
            chunk_text="Sample content",
            card_count=5,
            card_type="cloze",
            difficulty="medium",
            language="ja",
        )
        assert "穴埋め" in prompt or "[___]" in prompt

    def test_qa_type_english(self) -> None:
        """QA card type generates Q&A format instructions in English."""
        prompt = get_url_card_generation_prompt(
            chunk_text="Sample content",
            card_count=5,
            card_type="qa",
            difficulty="medium",
            language="en",
        )
        assert "Q&A" in prompt or "question-and-answer" in prompt

    def test_definition_type_english(self) -> None:
        """Definition card type generates definition format in English."""
        prompt = get_url_card_generation_prompt(
            chunk_text="Sample content",
            card_count=5,
            card_type="definition",
            difficulty="medium",
            language="en",
        )
        assert "Definition" in prompt or "definition" in prompt

    def test_cloze_type_english(self) -> None:
        """Cloze card type generates cloze format in English."""
        prompt = get_url_card_generation_prompt(
            chunk_text="Sample content",
            card_count=5,
            card_type="cloze",
            difficulty="medium",
            language="en",
        )
        assert "Cloze" in prompt or "[___]" in prompt

    def test_easy_difficulty(self) -> None:
        """Easy difficulty includes appropriate guidance."""
        prompt = get_url_card_generation_prompt(
            chunk_text="Sample content",
            card_count=5,
            card_type="qa",
            difficulty="easy",
            language="ja",
        )
        assert "easy" in prompt or "基本" in prompt

    def test_hard_difficulty(self) -> None:
        """Hard difficulty includes appropriate guidance."""
        prompt = get_url_card_generation_prompt(
            chunk_text="Sample content",
            card_count=5,
            card_type="qa",
            difficulty="hard",
            language="ja",
        )
        assert "hard" in prompt or "応用" in prompt

    def test_card_count_in_prompt(self) -> None:
        """Card count is included in the prompt."""
        prompt = get_url_card_generation_prompt(
            chunk_text="Sample content",
            card_count=7,
            card_type="qa",
            difficulty="medium",
            language="ja",
        )
        assert "7" in prompt

    def test_page_title_context(self) -> None:
        """Page title is included as context."""
        prompt = get_url_card_generation_prompt(
            chunk_text="Sample content",
            card_count=5,
            card_type="qa",
            difficulty="medium",
            language="ja",
            page_title="Python Tutorial",
        )
        assert "Python Tutorial" in prompt

    def test_section_title_context(self) -> None:
        """Section title is included as context."""
        prompt = get_url_card_generation_prompt(
            chunk_text="Sample content",
            card_count=5,
            card_type="qa",
            difficulty="medium",
            language="ja",
            page_title="Tutorial",
            section_title="Data Structures",
        )
        assert "Data Structures" in prompt

    def test_all_card_types_have_instructions(self) -> None:
        """All card types have both ja and en instructions."""
        for card_type in ("qa", "definition", "cloze"):
            assert card_type in CARD_TYPE_INSTRUCTIONS
            assert "ja" in CARD_TYPE_INSTRUCTIONS[card_type]
            assert "en" in CARD_TYPE_INSTRUCTIONS[card_type]

    def test_all_difficulties_have_guidelines(self) -> None:
        """All difficulty levels have both ja and en guidelines."""
        for difficulty in ("easy", "medium", "hard"):
            assert difficulty in DIFFICULTY_GUIDELINES
            assert "ja" in DIFFICULTY_GUIDELINES[difficulty]
            assert "en" in DIFFICULTY_GUIDELINES[difficulty]

    def test_chunk_text_in_prompt(self) -> None:
        """The actual chunk text content appears in the prompt."""
        prompt = get_url_card_generation_prompt(
            chunk_text="Unique test content about quantum physics",
            card_count=5,
            card_type="qa",
            difficulty="medium",
            language="ja",
        )
        assert "quantum physics" in prompt

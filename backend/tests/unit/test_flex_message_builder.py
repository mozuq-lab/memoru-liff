"""Unit tests for card preview Flex Message builder (T034)."""

import pytest

from services.flex_messages import (
    create_url_generation_progress_message,
    create_card_preview_carousel,
    create_url_generation_error_message,
)


class TestUrlGenerationProgressMessage:
    """Tests for URL generation progress message."""

    def test_progress_message_type(self) -> None:
        """Progress message is a text message."""
        msg = create_url_generation_progress_message("https://example.com")
        assert msg["type"] == "text"

    def test_progress_message_contains_url(self) -> None:
        """Progress message mentions the URL."""
        msg = create_url_generation_progress_message("https://example.com/article")
        assert "example.com" in msg["text"]

    def test_progress_message_indicates_generating(self) -> None:
        """Progress message indicates card generation is in progress."""
        msg = create_url_generation_progress_message("https://example.com")
        assert "生成" in msg["text"] or "カード" in msg["text"]


class TestCardPreviewCarousel:
    """Tests for card preview carousel Flex Message."""

    def test_carousel_type(self) -> None:
        """Card carousel is a Flex Message."""
        cards = [
            {"front": "Question 1", "back": "Answer 1", "tags": ["tag1"]},
            {"front": "Question 2", "back": "Answer 2", "tags": ["tag2"]},
        ]
        msg = create_card_preview_carousel(
            cards=cards,
            page_title="Test Page",
            page_url="https://example.com",
            user_id="user-123",
        )
        assert msg["type"] == "flex"

    def test_carousel_contains_cards(self) -> None:
        """Carousel contains bubble for each card."""
        cards = [
            {"front": "Q1", "back": "A1", "tags": []},
            {"front": "Q2", "back": "A2", "tags": []},
            {"front": "Q3", "back": "A3", "tags": []},
        ]
        msg = create_card_preview_carousel(
            cards=cards,
            page_title="Page",
            page_url="https://example.com",
            user_id="user-1",
        )
        contents = msg["contents"]
        assert contents["type"] == "carousel"
        # Should have bubbles for cards + summary bubble
        assert len(contents["contents"]) >= 3

    def test_carousel_card_shows_front_and_back(self) -> None:
        """Each card bubble shows front (question) and back (answer)."""
        cards = [
            {"front": "What is Python?", "back": "A programming language", "tags": []},
        ]
        msg = create_card_preview_carousel(
            cards=cards,
            page_title="Page",
            page_url="https://example.com",
            user_id="user-1",
        )
        # Flatten the message to string to check content
        msg_str = str(msg)
        assert "What is Python?" in msg_str
        assert "A programming language" in msg_str

    def test_carousel_has_save_button(self) -> None:
        """Card carousel includes a save all button."""
        cards = [
            {"front": "Q1", "back": "A1", "tags": []},
        ]
        msg = create_card_preview_carousel(
            cards=cards,
            page_title="Page",
            page_url="https://example.com",
            user_id="user-1",
        )
        msg_str = str(msg)
        assert "保存" in msg_str

    def test_carousel_save_postback_data(self) -> None:
        """Save button has correct postback data."""
        cards = [
            {"front": "Q1", "back": "A1", "tags": []},
        ]
        msg = create_card_preview_carousel(
            cards=cards,
            page_title="Page",
            page_url="https://example.com",
            user_id="user-1",
        )
        msg_str = str(msg)
        assert "action=save_url_cards" in msg_str

    def test_empty_cards_returns_error_message(self) -> None:
        """Empty card list returns error-style message."""
        msg = create_card_preview_carousel(
            cards=[],
            page_title="Page",
            page_url="https://example.com",
            user_id="user-1",
        )
        msg_str = str(msg)
        assert "生成" in msg_str or "カード" in msg_str

    def test_max_cards_in_carousel(self) -> None:
        """Carousel limits cards to LINE's max (10 bubbles)."""
        cards = [
            {"front": f"Q{i}", "back": f"A{i}", "tags": []}
            for i in range(15)
        ]
        msg = create_card_preview_carousel(
            cards=cards,
            page_title="Page",
            page_url="https://example.com",
            user_id="user-1",
        )
        contents = msg["contents"]["contents"]
        # LINE carousel max is 10 bubbles
        assert len(contents) <= 10


class TestUrlGenerationErrorMessage:
    """Tests for URL generation error message."""

    def test_error_message_type(self) -> None:
        """Error message is a text message."""
        msg = create_url_generation_error_message("Failed to fetch")
        assert msg["type"] == "text"

    def test_error_message_contains_reason(self) -> None:
        """Error message includes the error reason."""
        msg = create_url_generation_error_message("Page requires JavaScript")
        assert "JavaScript" in msg["text"] or "エラー" in msg["text"]

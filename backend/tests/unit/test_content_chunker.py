"""Unit tests for content chunker (T006)."""

import pytest

from services.content_chunker import chunk_content, ContentChunk


class TestChunkContent:
    """Tests for chunk_content function."""

    def test_short_text_returns_single_chunk(self) -> None:
        """Text under the limit returns a single chunk."""
        text = "This is a short paragraph about Python."
        chunks = chunk_content(text, page_title="Python Basics")
        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].page_title == "Python Basics"
        assert chunks[0].chunk_index == 0
        assert chunks[0].total_chunks == 1

    def test_heading_based_split(self) -> None:
        """Text with headings splits at heading boundaries."""
        text = (
            "# Introduction\n\nThis is the intro.\n\n"
            "# Methods\n\nThis is the methods section.\n\n"
            "# Results\n\nThis is the results section."
        )
        chunks = chunk_content(text, page_title="Paper")
        assert len(chunks) >= 2
        # First chunk should contain introduction content
        assert "intro" in chunks[0].text.lower()

    def test_respects_max_chunk_size(self) -> None:
        """No chunk exceeds the max size."""
        # Create text larger than default chunk size
        long_section = "This is a sentence. " * 200  # ~4000 chars
        text = f"# Section 1\n\n{long_section}\n\n# Section 2\n\nShort section."
        chunks = chunk_content(text, page_title="Test", max_chunk_size=3000)
        for chunk in chunks:
            assert len(chunk.text) <= 3000 + 200  # Allow small overflow for paragraph boundary

    def test_preserves_section_titles(self) -> None:
        """Section titles are captured in chunk metadata."""
        text = "# Main Title\n\nContent here.\n\n## Sub Section\n\nMore content."
        chunks = chunk_content(text, page_title="Doc")
        # At least one chunk should have a section title
        section_titles = [c.section_title for c in chunks if c.section_title]
        assert len(section_titles) > 0

    def test_chunk_indices_are_sequential(self) -> None:
        """Chunk indices are 0-based and sequential."""
        text = "# A\n\nContent A.\n\n# B\n\nContent B.\n\n# C\n\nContent C."
        chunks = chunk_content(text, page_title="Test")
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
            assert chunk.total_chunks == len(chunks)

    def test_empty_text_returns_empty_list(self) -> None:
        """Empty text returns no chunks."""
        chunks = chunk_content("", page_title="Empty")
        assert chunks == []

    def test_whitespace_only_returns_empty(self) -> None:
        """Whitespace-only text returns no chunks."""
        chunks = chunk_content("   \n\n   ", page_title="Blank")
        assert chunks == []

    def test_page_title_on_all_chunks(self) -> None:
        """All chunks carry the page title."""
        text = "# A\n\nContent A.\n\n# B\n\nContent B."
        chunks = chunk_content(text, page_title="My Page")
        for chunk in chunks:
            assert chunk.page_title == "My Page"

    def test_content_chunk_dataclass(self) -> None:
        """ContentChunk has expected fields."""
        chunk = ContentChunk(
            text="hello",
            section_title="Section",
            page_title="Page",
            chunk_index=0,
            total_chunks=1,
        )
        assert chunk.text == "hello"
        assert chunk.section_title == "Section"
        assert chunk.page_title == "Page"

    def test_large_text_without_headings(self) -> None:
        """Large text without headings splits at paragraph boundaries."""
        paragraphs = [f"Paragraph {i}. " * 30 for i in range(20)]
        text = "\n\n".join(paragraphs)
        chunks = chunk_content(text, page_title="No Headings", max_chunk_size=3000)
        assert len(chunks) > 1
        # All content should be preserved
        combined = " ".join(c.text for c in chunks)
        assert "Paragraph 0" in combined
        assert "Paragraph 19" in combined

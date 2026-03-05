"""URL-based card generation prompt templates."""

from typing import Literal

from ._types import Language

CardType = Literal["qa", "definition", "cloze"]
DifficultyLevel = Literal["easy", "medium", "hard"]

URL_CARD_GENERATION_SYSTEM_PROMPT = """You are an expert flashcard creator specialized in spaced repetition learning.

Your task is to create effective flashcards from web page content that maximize learning retention.

Guidelines:
- Create clear, concise questions on the front
- Provide complete, accurate answers on the back
- Focus on key concepts, definitions, and important relationships
- Ensure each card tests a single concept
- Add relevant tags for categorization
- Include "AI生成" and "URL生成" in the tags

Respond ONLY with a JSON object in this exact format:
{
  "cards": [
    {"front": "question", "back": "answer", "tags": ["AI生成", "URL生成", "tag1"]}
  ]
}

Do not include any text outside the JSON object."""

CARD_TYPE_INSTRUCTIONS = {
    "qa": {
        "ja": "Q&A形式：重要な概念について質問と回答のペアを作成してください。",
        "en": "Q&A format: Create question-and-answer pairs about key concepts.",
    },
    "definition": {
        "ja": "用語定義形式：表面に用語、裏面にその定義を記述してください。",
        "en": "Definition format: Term on the front, definition on the back.",
    },
    "cloze": {
        "ja": "穴埋め形式：重要な語句を[___]で穴埋めにした文を表面に、正解を裏面に記述してください。",
        "en": "Cloze format: Use [___] for key terms on the front, answer on the back.",
    },
}

DIFFICULTY_GUIDELINES = {
    "easy": {
        "ja": "基本的な用語定義、単純な事実を問う簡単な問題",
        "en": "Basic terminology definitions and simple factual questions",
    },
    "medium": {
        "ja": "概念の説明、関係性の理解を問う中程度の問題",
        "en": "Concept explanations and relationship understanding questions",
    },
    "hard": {
        "ja": "応用問題、複合的な理解を問う難しい問題",
        "en": "Application problems and complex understanding questions",
    },
}


def get_url_card_generation_prompt(
    chunk_text: str,
    card_count: int,
    card_type: CardType,
    difficulty: DifficultyLevel,
    language: Language,
    page_title: str = "",
    section_title: str | None = None,
) -> str:
    """Generate a prompt for URL-based card generation.

    Args:
        chunk_text: The text chunk to generate cards from.
        card_count: Number of cards to generate from this chunk.
        card_type: Type of cards (qa, definition, cloze).
        difficulty: Difficulty level.
        language: Output language.
        page_title: Page title for context.
        section_title: Section title for context (if available).

    Returns:
        Formatted prompt string.
    """
    card_type_inst = CARD_TYPE_INSTRUCTIONS.get(card_type, CARD_TYPE_INSTRUCTIONS["qa"])
    card_type_desc = card_type_inst.get(language, card_type_inst["ja"])

    difficulty_guide = DIFFICULTY_GUIDELINES.get(difficulty, DIFFICULTY_GUIDELINES["medium"])
    difficulty_desc = difficulty_guide.get(language, difficulty_guide["ja"])

    context_parts = []
    if page_title:
        context_parts.append(f"ページタイトル: {page_title}" if language == "ja" else f"Page title: {page_title}")
    if section_title:
        context_parts.append(f"セクション: {section_title}" if language == "ja" else f"Section: {section_title}")
    context_str = "\n".join(context_parts)

    if language == "ja":
        prompt = f"""以下の Web ページのコンテンツから学習効果の高いフラッシュカードを{card_count}枚作成してください。

## コンテキスト
{context_str}

## コンテンツ
{chunk_text}

## 要件
- カードタイプ: {card_type_desc}
- 難易度: {difficulty} ({difficulty_desc})
- 言語: 日本語
- 重要な概念を優先的にカード化
- 各カードは独立して学習できるように
- タグに「AI生成」「URL生成」を含める

## 出力形式
以下のJSON形式で出力してください。他のテキストは含めないでください。
```json
{{
  "cards": [
    {{"front": "問題文", "back": "解答", "tags": ["AI生成", "URL生成", "タグ"]}}
  ]
}}
```"""
    else:
        prompt = f"""Create {card_count} effective flashcards from the following web page content.

## Context
{context_str}

## Content
{chunk_text}

## Requirements
- Card type: {card_type_desc}
- Difficulty: {difficulty} ({difficulty_desc})
- Language: English
- Prioritize important concepts
- Each card should be independently learnable
- Include "AI生成" and "URL生成" in tags

## Output Format
Output in the following JSON format only. Do not include any other text.
```json
{{
  "cards": [
    {{"front": "question", "back": "answer", "tags": ["AI生成", "URL生成", "tag"]}}
  ]
}}
```"""

    return prompt

"""Prompt templates for AI card generation."""

from typing import Literal


DifficultyLevel = Literal["easy", "medium", "hard"]
Language = Literal["ja", "en"]


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


def get_card_generation_prompt(
    input_text: str,
    card_count: int,
    difficulty: DifficultyLevel,
    language: Language,
) -> str:
    """Generate prompt for flashcard creation.

    Args:
        input_text: The source text to generate cards from.
        card_count: Number of cards to generate.
        difficulty: Difficulty level (easy/medium/hard).
        language: Output language (ja/en).

    Returns:
        Formatted prompt string.
    """
    difficulty_guide = DIFFICULTY_GUIDELINES.get(difficulty, DIFFICULTY_GUIDELINES["medium"])
    difficulty_desc = difficulty_guide.get(language, difficulty_guide["ja"])

    if language == "ja":
        prompt = f"""あなたはフラッシュカード作成の専門家です。
以下のテキストから学習効果の高いフラッシュカードを{card_count}枚作成してください。

## 入力テキスト
{input_text}

## 要件
- 難易度: {difficulty} ({difficulty_desc})
- 言語: 日本語
- 問題文（front）は簡潔で明確に、質問形式で記述
- 解答（back）は必要十分な情報を含める
- 重要な概念を優先的にカード化
- 各カードは独立して学習できるように

## 出力形式
以下のJSON形式で出力してください。他のテキストは含めないでください。
```json
{{
  "cards": [
    {{"front": "問題文", "back": "解答", "tags": ["タグ1", "タグ2"]}}
  ]
}}
```"""
    else:
        prompt = f"""You are an expert at creating flashcards.
Create {card_count} effective flashcards from the following text.

## Input Text
{input_text}

## Requirements
- Difficulty: {difficulty} ({difficulty_desc})
- Language: English
- The front (question) should be concise and clear, in question format
- The back (answer) should contain sufficient information
- Prioritize important concepts
- Each card should be independently learnable

## Output Format
Output in the following JSON format only. Do not include any other text.
```json
{{
  "cards": [
    {{"front": "question", "back": "answer", "tags": ["tag1", "tag2"]}}
  ]
}}
```"""

    return prompt

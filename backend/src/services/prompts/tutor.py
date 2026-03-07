"""Tutor prompt templates for AI Tutor feature.

Mode-specific system prompts with card context injection
and language-matching instruction (FR-017).
"""

from typing import Literal


LearningMode = Literal["free_talk", "quiz", "weak_point"]


def format_cards_context(cards: list[dict]) -> str:
    """Format card data into a context string for the system prompt.

    Args:
        cards: List of card dicts with 'front' and 'back' keys.

    Returns:
        Formatted string with card content, or empty string if no cards.
    """
    if not cards:
        return ""
    lines = []
    for i, card in enumerate(cards, 1):
        card_id = card.get("card_id", "")
        front = card.get("front", "")
        back = card.get("back", "")
        id_part = f" (id: {card_id})" if card_id else ""
        lines.append(f"{i}. Front: {front} | Back: {back}{id_part}")
    return "\n".join(lines)


_BASE_INSTRUCTIONS = """You are an AI tutor helping a user learn from their flashcard deck.
Deck name: "{deck_name}"

## Card Content
{cards_context}

## Language Instruction
Respond in the same language as the card content. If cards are in Japanese, respond in Japanese. If in English, respond in English. Match the language of the deck's cards.

## Related Cards
When your response is related to specific cards in the deck, include a tag at the end of your response in this format:
[RELATED_CARDS: card_id1, card_id2]
Only include card IDs that exist in the deck above. If no cards are directly related, omit this tag."""


_FREE_TALK_PROMPT = """## Mode: Free Talk
You are in free talk / open conversation mode. The user can ask any questions about the deck's topic.
- Answer questions about any card's content with clear, helpful explanations
- Provide context, examples, and connections between concepts
- Encourage curiosity and deeper understanding
- If the user asks about something not in the deck, relate it back to the deck content when possible
- Start with a friendly greeting that summarizes what the deck covers and invite the user to ask questions"""


_QUIZ_PROMPT = """## Mode: Quiz
You are in quiz mode. Generate questions based on the deck's card content and evaluate user answers.
- Start by presenting a question derived from one of the cards
- After the user answers, evaluate whether their answer is correct
- Provide feedback: if correct, confirm and add extra context; if incorrect, explain the correct answer
- Then present the next question
- Vary question types: direct recall, application, comparison between cards
- Keep track of which cards you've quizzed on and try to cover different cards"""


_WEAK_POINT_PROMPT = """## Mode: Weak Point Focus
You are in weak point focus mode. Prioritize helping the user with their weakest cards.
- Focus explanations on the cards the user struggles with most
- Provide alternative explanations, mnemonics, and memory aids
- Ask the user to explain concepts in their own words to check understanding
- Gradually build from weak areas to reinforce connections with stronger knowledge

## User's Weak Cards
{weak_cards_context}
If weak card data is provided above, prioritize those topics. Otherwise, focus on the most complex cards in the deck."""


_MODE_PROMPTS: dict[str, str] = {
    "free_talk": _FREE_TALK_PROMPT,
    "quiz": _QUIZ_PROMPT,
    "weak_point": _WEAK_POINT_PROMPT,
}


def get_system_prompt(
    mode: LearningMode,
    deck_name: str,
    cards_context: str,
    weak_cards_context: str | None = None,
) -> str:
    """Build a mode-specific system prompt with card context.

    Args:
        mode: Learning mode (free_talk, quiz, weak_point).
        deck_name: Name of the target deck.
        cards_context: Formatted card content string.
        weak_cards_context: Optional weak card data for weak_point mode.

    Returns:
        Complete system prompt string.
    """
    base = _BASE_INSTRUCTIONS.format(
        deck_name=deck_name,
        cards_context=cards_context or "(No cards in this deck)",
    )

    mode_prompt = _MODE_PROMPTS[mode]
    if mode == "weak_point" and weak_cards_context:
        mode_prompt = mode_prompt.format(weak_cards_context=weak_cards_context)
    elif mode == "weak_point":
        mode_prompt = mode_prompt.format(
            weak_cards_context="(No weak card data available)"
        )

    return f"{base}\n\n{mode_prompt}"

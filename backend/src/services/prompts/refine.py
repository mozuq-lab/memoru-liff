"""カード補足・改善プロンプトモジュール.

ユーザーが入力したフラッシュカードの表面（問題文）と裏面（解答）を
AIが改善するためのプロンプトを提供する。

# 【機能概要】: フラッシュカード補足・改善プロンプトテンプレートを管理する
# 🔵 設計文書 architecture.md プロンプト設計より
"""

from ._types import Language


# --- システムプロンプト (ja/en) ---

_REFINE_SYSTEM_PROMPT_JA = """あなたはフラッシュカード改善の専門家です。
ユーザーが入力した暗記カードの表面（問題文）と裏面（解答）を改善してください。

【表面（問題文）の改善方針】
- ユーザーの意図を維持しつつ、明確で簡潔な質問形式に整える
- 曖昧な表現をより具体的にする
- 学習者が問われている内容を即座に理解できるようにする

【裏面（解答）の改善方針】
- ユーザーの入力内容を基盤として維持する
- 不足している重要な情報を補足する
- 学習に最適な構造（箇条書き、定義+例示など）に整形する
- 正確性を保ちながら簡潔にまとめる

JSON 形式のみで回答してください:
{"refined_front": "...", "refined_back": "..."}"""

_REFINE_SYSTEM_PROMPT_EN = """You are a flashcard improvement expert.
Improve the front (question) and back (answer) of the user's flashcard.

[Front (Question) Improvement Guidelines]
- Maintain the user's intent while making the question clear and concise
- Replace vague expressions with more specific ones
- Ensure the learner can immediately understand what is being asked

[Back (Answer) Improvement Guidelines]
- Maintain the user's input content as the foundation
- Supplement missing important information
- Format for optimal learning (bullet points, definition + examples, etc.)
- Keep it concise while maintaining accuracy

Respond ONLY in JSON format:
{"refined_front": "...", "refined_back": "..."}"""

# 後方互換性: 既存コードが REFINE_SYSTEM_PROMPT を参照している場合に備える
REFINE_SYSTEM_PROMPT = _REFINE_SYSTEM_PROMPT_JA


def get_refine_system_prompt(language: Language = "ja") -> str:
    """言語に応じたリファイン用システムプロンプトを返す.

    Args:
        language: 出力言語（ja/en）。

    Returns:
        システムプロンプト文字列。
    """
    if language == "ja":
        return _REFINE_SYSTEM_PROMPT_JA
    return _REFINE_SYSTEM_PROMPT_EN


def get_refine_user_prompt(front: str, back: str, language: Language = "ja") -> str:
    """カード補足用ユーザープロンプトを生成する.

    入力パターン（表面・裏面両方/表面のみ/裏面のみ）に応じて
    適切なプロンプトを返す。

    Args:
        front: カードの表面テキスト（空文字の場合は未入力扱い）。
        back: カードの裏面テキスト（空文字の場合は未入力扱い）。
        language: 出力言語（ja/en）。

    Returns:
        フォーマット済みプロンプト文字列。
    """
    has_front = bool(front.strip())
    has_back = bool(back.strip())

    if language == "ja":
        if has_front and has_back:
            return _get_both_prompt_ja(front, back)
        elif has_front:
            return _get_front_only_prompt_ja(front)
        else:
            return _get_back_only_prompt_ja(back)
    else:
        if has_front and has_back:
            return _get_both_prompt_en(front, back)
        elif has_front:
            return _get_front_only_prompt_en(front)
        else:
            return _get_back_only_prompt_en(back)


# --- 日本語テンプレート ---


def _get_both_prompt_ja(front: str, back: str) -> str:
    """表面・裏面両方がある場合の日本語プロンプト."""
    return f"""以下のフラッシュカードを改善してください。

## 問題文（表面）
{front}

## 解答（裏面）
{back}

改善結果を JSON 形式で出力してください。"""


def _get_front_only_prompt_ja(front: str) -> str:
    """表面のみの場合の日本語プロンプト."""
    return f"""以下のフラッシュカードの問題文を改善してください。
裏面は入力されていないため、refined_back は空文字にしてください。

## 問題文（表面）
{front}

改善結果を JSON 形式で出力してください。"""


def _get_back_only_prompt_ja(back: str) -> str:
    """裏面のみの場合の日本語プロンプト."""
    return f"""以下のフラッシュカードの解答を改善してください。
表面は入力されていないため、refined_front は空文字にしてください。

## 解答（裏面）
{back}

改善結果を JSON 形式で出力してください。"""


# --- 英語テンプレート ---


def _get_both_prompt_en(front: str, back: str) -> str:
    """表面・裏面両方がある場合の英語プロンプト."""
    return f"""Improve the following flashcard.

## Question (Front)
{front}

## Answer (Back)
{back}

Output the improved result in JSON format."""


def _get_front_only_prompt_en(front: str) -> str:
    """表面のみの場合の英語プロンプト."""
    return f"""Improve the following flashcard question.
The back is not provided, so set refined_back to an empty string.

## Question (Front)
{front}

Output the improved result in JSON format."""


def _get_back_only_prompt_en(back: str) -> str:
    """裏面のみの場合の英語プロンプト."""
    return f"""Improve the following flashcard answer.
The front is not provided, so set refined_front to an empty string.

## Answer (Back)
{back}

Output the improved result in JSON format."""

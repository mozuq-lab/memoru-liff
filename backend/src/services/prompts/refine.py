"""カード補足・改善プロンプトモジュール.

ユーザーが入力したフラッシュカードの表面（問題文）と裏面（解答）を
AIが改善するためのプロンプトを提供する。

# 【機能概要】: フラッシュカード補足・改善プロンプトテンプレートを管理する
# 🔵 設計文書 architecture.md プロンプト設計より
"""

from ._types import Language


REFINE_SYSTEM_PROMPT = """あなたはフラッシュカード改善の専門家です。
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

    if has_front and has_back:
        return _get_both_prompt(front, back)
    elif has_front:
        return _get_front_only_prompt(front)
    else:
        return _get_back_only_prompt(back)


def _get_both_prompt(front: str, back: str) -> str:
    """表面・裏面両方がある場合のプロンプト."""
    return f"""以下のフラッシュカードを改善してください。

## 問題文（表面）
{front}

## 解答（裏面）
{back}

改善結果を JSON 形式で出力してください。"""


def _get_front_only_prompt(front: str) -> str:
    """表面のみの場合のプロンプト."""
    return f"""以下のフラッシュカードの問題文を改善してください。
裏面は入力されていないため、refined_back は空文字にしてください。

## 問題文（表面）
{front}

改善結果を JSON 形式で出力してください。"""


def _get_back_only_prompt(back: str) -> str:
    """裏面のみの場合のプロンプト."""
    return f"""以下のフラッシュカードの解答を改善してください。
表面は入力されていないため、refined_front は空文字にしてください。

## 解答（裏面）
{back}

改善結果を JSON 形式で出力してください。"""

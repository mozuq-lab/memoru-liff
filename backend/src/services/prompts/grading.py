"""回答採点プロンプトモジュール.

SM-2 アルゴリズムに基づくグレード定義（0-5）と
AI 採点プロンプトテンプレートを提供する。

# 【機能概要】: SRS 回答採点用の AI プロンプトを管理する
# 【実装方針】: SM-2 グレード定義（0-5）を埋め込んだ採点プロンプトを提供
# 【テスト対応】: TC-005, TC-006, TC-007, TC-008, TC-014, TC-016, TC-021, TC-023 を通すための実装
# 【改善内容】: Language 型と _LANGUAGE_INSTRUCTION を _types.py の共通定義から import し、重複定義を排除
# 🔵 REQ-SM-003、設計ヒアリング Q4、api-endpoints.md グレード定義表から確定
"""

from ._types import (  # 【共通型インポート】: 重複定義を排除し DRY 原則を適用
    DEFAULT_LANGUAGE_INSTRUCTION,
    LANGUAGE_INSTRUCTION,
    Language,
)


# 【定数定義】: SM-2 グレード定義文字列（グレード 0-5 の全定義）
# 🔵 api-endpoints.md グレード定義表、REQ-SM-003 から確定
SM2_GRADE_DEFINITIONS = """SM-2 Grading Scale:
- Grade 5: Perfect response - Complete and accurate answer with no hesitation
- Grade 4: Correct with some hesitation - Correct answer but minor gaps or uncertainty
- Grade 3: Correct with serious difficulty - Correct answer but required significant effort to recall
- Grade 2: Incorrect; correct answer seemed easy - Wrong answer, but correct answer was easy to recall after seeing it
- Grade 1: Incorrect; correct answer remembered - Wrong answer, but had some related knowledge
- Grade 0: Complete blackout - No answer or completely unrelated response"""


# 【定数定義】: 回答採点用システムプロンプト
# 🔵 タスクファイルの grading.py 設計仕様から確定
# 【テスト対応】: TC-006（SM-2 含有）, TC-023（JSON フィールド指示）
GRADING_SYSTEM_PROMPT = """You are an expert flashcard grader using the SM-2 spaced repetition algorithm.

Your task is to evaluate the student's answer against the correct answer and assign an SM-2 grade.

""" + SM2_GRADE_DEFINITIONS + """

Respond ONLY with a JSON object in this exact format:
{
  "grade": <integer 0-5>,
  "reasoning": "<brief explanation of the grade in the target language>",
  "feedback": "<constructive feedback for the student in the target language>"
}

Do not include any text outside the JSON object."""


def get_grading_prompt(
    card_front: str,
    card_back: str,
    user_answer: str,
    language: Language = "ja",
) -> str:
    """回答採点プロンプトを生成する.

    # 【機能概要】: カードの問題・正解・ユーザー回答を含む採点プロンプトを生成する
    # 【実装方針】: 3つの入力値と言語指示を埋め込んだプロンプトを返す
    # 【テスト対応】: TC-007（日本語）, TC-008（英語）, TC-014（フォールバック）, TC-016（デフォルト）
    # 🔵 タスクファイルの grading.py 仕様、要件定義書 2.2 節から確定

    Args:
        card_front: カード表面（問題文）。
        card_back: カード裏面（正解）。
        user_answer: ユーザーの回答。
        language: 出力言語（デフォルト: "ja"）。

    Returns:
        SM-2 採点基準を含むプロンプト文字列。
    """
    # 【言語指示取得】: サポート外の言語は日本語にフォールバック
    # 【改善内容】: _types.py の共通 LANGUAGE_INSTRUCTION と DEFAULT_LANGUAGE_INSTRUCTION を使用
    # 🟡 要件定義書 4.7 節の .get() フォールバック仕様から推測
    lang_instruction = LANGUAGE_INSTRUCTION.get(language, DEFAULT_LANGUAGE_INSTRUCTION)

    # 【プロンプト構築】: 問題・正解・回答を埋め込んだ採点プロンプトを生成
    # 🔵 タスクファイルの実装仕様から確定
    return f"""Please grade the following flashcard response:

Question (Card Front): {card_front}
Correct Answer (Card Back): {card_back}
Student's Answer: {user_answer}

{lang_instruction}

Evaluate the student's answer and provide your grade in JSON format."""

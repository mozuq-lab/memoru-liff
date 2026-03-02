"""カード生成プロンプトモジュール.

既存の services/prompts.py からの移行ファイル。
get_card_generation_prompt 関数と関連定数を提供する。

# 【機能概要】: フラッシュカード生成プロンプトテンプレートを管理する
# 【実装方針】: 既存 prompts.py の内容を変更なしにそのまま移行（後方互換性維持）
# 【テスト対応】: TC-001, TC-002, TC-003, TC-004 を通すための実装
# 【改善内容】: Language 型を _types.py の共通定義から import し、重複定義を排除
# 🔵 既存 backend/src/services/prompts.py をそのまま移行
"""

from typing import Literal

from ._types import Language  # 【共通型インポート】: 重複定義を排除し DRY 原則を適用


# 【型定義】: 難易度レベルの型エイリアス
# 🔵 既存 prompts.py と同一
DifficultyLevel = Literal["easy", "medium", "hard"]

# 【型定義】: 出力言語の型エイリアス（_types.py からの再エクスポート）
# 【改善内容】: Greenフェーズでは各ファイルに重複定義していたが、共通モジュールに集約
# 🔵 _types.py の Language 型定義を参照


# 【定数定義】: カード生成用システムプロンプト
# 🔵 REQ-004: generate_cards に system_prompt を設定
CARD_GENERATION_SYSTEM_PROMPT = """You are an expert flashcard creator specialized in spaced repetition learning.

Your task is to create effective flashcards from the given text that maximize learning retention.

Guidelines:
- Create clear, concise questions on the front
- Provide complete, accurate answers on the back
- Focus on key concepts and important relationships
- Ensure each card tests a single concept
- Add relevant tags for categorization

Respond ONLY with a JSON object in this exact format:
{
  "cards": [
    {"front": "question", "back": "answer", "tags": ["tag1", "tag2"]}
  ]
}

Do not include any text outside the JSON object."""


# 【定数定義】: 難易度ガイドラインの辞書
# 🔵 既存 prompts.py と同一
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
    """フラッシュカード生成プロンプトを生成する.

    # 【機能概要】: 入力テキストからフラッシュカードを生成するためのプロンプトを返す
    # 【実装方針】: 既存 prompts.py の実装をそのまま維持（互換性保証）
    # 【テスト対応】: TC-001（日本語）, TC-002（英語）, TC-003（難易度）
    # 🔵 既存 prompts.py::get_card_generation_prompt と同一

    Args:
        input_text: カード生成元テキスト（10-2000文字）。
        card_count: 生成カード数（1-10）。
        difficulty: 難易度（easy/medium/hard）。
        language: 出力言語（ja/en）。

    Returns:
        フォーマット済みプロンプト文字列。
    """
    # 【難易度ガイドライン取得】: 指定された難易度の説明を取得する
    # 🔵 既存実装と同一
    difficulty_guide = DIFFICULTY_GUIDELINES.get(difficulty, DIFFICULTY_GUIDELINES["medium"])
    difficulty_desc = difficulty_guide.get(language, difficulty_guide["ja"])

    # 【言語分岐】: 日本語と英語でテンプレートを切り替える
    # 🔵 既存実装と同一
    if language == "ja":
        prompt = f"""あなたはフラッシュカード作成の専門家です。
以下のユーザーが入力したテキストを素材として、フラッシュカードを{card_count}枚作成してください。

## ユーザー入力テキスト
{input_text}

## 要件
- 難易度: {difficulty} ({difficulty_desc})
- 言語: 日本語
- 問題文（front）は簡潔で明確に、質問形式で記述
- 解答（back）はユーザーが入力したテキストの該当部分を清書・整形して使用すること
- 解答に新規情報を創作・追加しないこと。原文の意味を維持しながら読みやすく整える
- 明らかな誤字脱字・冗長表現・不自然な文は改善する
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
        # 【英語テンプレート】: language="en" 時の英語プロンプト
        prompt = f"""You are an expert at creating flashcards.
Create {card_count} flashcards based on the following user-provided text.

## User Input Text
{input_text}

## Requirements
- Difficulty: {difficulty} ({difficulty_desc})
- Language: English
- The front (question) should be concise and clear, in question format
- The back (answer) should be a polished, structured version of relevant parts from the user's input text
- Do not add new information not present in the user's input. Preserve the original meaning while improving readability
- Fix obvious typos, redundant expressions, and unnatural phrasing
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

"""学習アドバイスプロンプトモジュール.

復習統計データ（ReviewSummary）に基づく学習アドバイス用
AI プロンプトテンプレートを提供する。

# 【機能概要】: パーソナライズされた学習アドバイス生成用の AI プロンプトを管理する
# 【実装方針】: dict と ReviewSummary dataclass の両方に対応したプロンプト生成
# 【テスト対応】: TC-009, TC-010, TC-011, TC-013, TC-015, TC-017, TC-018, TC-019, TC-022, TC-024
# 【改善内容】: Language 型と _LANGUAGE_INSTRUCTION を _types.py の共通定義から import し、重複定義を排除
# 【改善内容】: TYPE_CHECKING を用いた ReviewSummary の型ヒント改善（循環 import 回避）
# 🔵 REQ-SM-004、設計ヒアリング Q5、interfaces.py ReviewSummary から確定
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

from ._types import (  # 【共通型インポート】: 重複定義を排除し DRY 原則を適用
    DEFAULT_LANGUAGE_INSTRUCTION,
    LANGUAGE_INSTRUCTION,
    Language,
)

if TYPE_CHECKING:
    # 【型チェック専用 import】: 実行時には import せず、mypy/pyright 等の静的解析のみに使用
    # 【循環 import 回避】: advice.py → ai_service.py の実行時 import を避ける
    # 🟡 TYPE_CHECKING による循環 import 回避は Python の標準的な手法
    from services.ai_service import ReviewSummary


# 【定数定義】: 学習アドバイス用システムプロンプト
# 🔵 タスクファイルの advice.py 設計仕様から確定
# 【テスト対応】: TC-009（存在確認）, TC-024（JSON フィールド指示）
ADVICE_SYSTEM_PROMPT = """You are an expert learning advisor specializing in spaced repetition and effective study techniques.

Your task is to analyze a student's learning statistics and provide personalized advice to improve their study efficiency.

Focus on:
- Identifying weak areas where the student is struggling
- Suggesting concrete improvement strategies
- Encouraging consistent study habits

Respond ONLY with a JSON object in this exact format:
{
  "advice_text": "<main personalized advice based on the statistics>",
  "weak_areas": ["<area1>", "<area2>"],
  "recommendations": ["<strategy1>", "<strategy2>"]
}

Do not include any text outside the JSON object."""


def get_advice_prompt(
    review_summary: Union[dict, ReviewSummary],
    language: Language = "ja",
) -> str:
    """学習アドバイスプロンプトを生成する.

    # 【機能概要】: 復習統計データを埋め込んだ学習アドバイスプロンプトを生成する
    # 【実装方針】: dict と ReviewSummary dataclass の両方に対応（isinstance で振り分け）
    # 【テスト対応】: TC-010（dict）, TC-011（ReviewSummary）, TC-013（改善指示）,
    #               TC-015（フォールバック）, TC-017（デフォルト）, TC-018（空tag）, TC-019（ゼロ値）
    # 【改善内容】: 型ヒントを Union[dict, object] → Union[dict, ReviewSummary] に改善
    #             (TYPE_CHECKING による循環 import 回避を適用)
    # 🔵 タスクファイルの advice.py 仕様、設計ヒアリング Q5 から確定

    Args:
        review_summary: 復習統計データ（dict または ReviewSummary dataclass）。
        language: 出力言語（デフォルト: "ja"）。

    Returns:
        統計データ埋め込み済み学習アドバイスプロンプト文字列。
    """
    # 【入力値正規化】: dict と ReviewSummary dataclass の両方に対応
    # 🔵 要件定義書 4.5 節、interfaces.py ReviewSummary から確定
    if isinstance(review_summary, dict):
        # 【dict 形式】: dict から直接フィールドを取得
        stats = review_summary
        total_reviews = stats.get("total_reviews", 0)
        average_grade = stats.get("average_grade", 0.0)
        total_cards = stats.get("total_cards", 0)
        cards_due_today = stats.get("cards_due_today", 0)
        streak_days = stats.get("streak_days", 0)
        tag_performance = stats.get("tag_performance", {})
    else:
        # 【dataclass 形式】: ReviewSummary dataclass の属性を取得
        # 🔵 interfaces.py ReviewSummary の属性定義から確定
        total_reviews = getattr(review_summary, "total_reviews", 0)
        average_grade = getattr(review_summary, "average_grade", 0.0)
        total_cards = getattr(review_summary, "total_cards", 0)
        cards_due_today = getattr(review_summary, "cards_due_today", 0)
        streak_days = getattr(review_summary, "streak_days", 0)
        tag_performance = getattr(review_summary, "tag_performance", {})

    # 【言語指示取得】: サポート外の言語は日本語にフォールバック
    # 【改善内容】: _types.py の共通 LANGUAGE_INSTRUCTION と DEFAULT_LANGUAGE_INSTRUCTION を使用
    # 🟡 要件定義書 4.7 節の .get() フォールバック仕様から推測
    lang_instruction = LANGUAGE_INSTRUCTION.get(language, DEFAULT_LANGUAGE_INSTRUCTION)

    # 【タグ別パフォーマンス文字列化】: 辞書を読みやすい形式に変換
    # 🟡 設計文書に明記なし、空辞書でも正常動作するよう実装
    if tag_performance:
        tag_perf_str = "\n".join(
            f"  - {tag}: {score:.1f}" for tag, score in tag_performance.items()
        )
    else:
        tag_perf_str = "  (no tag data available)"

    # 【プロンプト構築】: 統計データを埋め込んだアドバイスプロンプトを生成
    # 🔵 タスクファイルの advice.py テンプレートから確定
    # 【テスト対応 TC-013】: "struggling", "weak", "improve" を含む改善指示
    return f"""Please analyze the following learning statistics and provide personalized advice:

## Learning Statistics
- Total Reviews: {total_reviews}
- Average Grade: {average_grade:.1f} (out of 5.0)
- Total Cards: {total_cards}
- Cards Due Today: {cards_due_today}
- Study Streak: {streak_days} days

## Tag Performance (average grade by category)
{tag_perf_str}

Based on these statistics, identify areas where the student is struggling and provide actionable recommendations to improve their weak areas and boost their overall learning efficiency.

{lang_instruction}

Provide your advice in JSON format."""

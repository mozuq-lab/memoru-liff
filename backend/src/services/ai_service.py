"""AIService Protocol、共通型定義、例外階層.

AI サービスの共通インターフェースと型定義を提供する。
USE_STRANDS フラグに応じて BedrockAIService または StrandsAIService を選択する。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Literal, Protocol, runtime_checkable

# Type aliases
DifficultyLevel = Literal["easy", "medium", "hard"]
Language = Literal["ja", "en"]


# Data classes (following interfaces.py exactly)
@dataclass
class GeneratedCard:
    """生成されたフラッシュカード."""

    front: str
    back: str
    suggested_tags: List[str] = field(default_factory=list)


@dataclass
class GenerationResult:
    """カード生成結果メタデータ."""

    cards: List[GeneratedCard]
    input_length: int
    model_used: str
    processing_time_ms: int


@dataclass
class GradingResult:
    """AI 回答採点結果."""

    grade: int  # 0-5
    reasoning: str
    model_used: str
    processing_time_ms: int


@dataclass
class ReviewSummary:
    """復習履歴の集計結果."""

    total_reviews: int
    average_grade: float
    total_cards: int
    cards_due_today: int
    streak_days: int
    tag_performance: Dict[str, float] = field(default_factory=dict)
    recent_review_dates: List[str] = field(default_factory=list)


@dataclass
class LearningAdvice:
    """AI 学習アドバイス結果."""

    advice_text: str
    weak_areas: List[str]
    recommendations: List[str]
    model_used: str
    processing_time_ms: int


# Exception hierarchy
class AIServiceError(Exception):
    """AI サービスの基底例外クラス."""

    pass


class AITimeoutError(AIServiceError):
    """AI タイムアウトエラー → HTTP 504."""

    pass


class AIRateLimitError(AIServiceError):
    """AI レート制限エラー → HTTP 429."""

    pass


class AIInternalError(AIServiceError):
    """AI 内部エラー → HTTP 500."""

    pass


class AIParseError(AIServiceError):
    """AI レスポンス解析エラー → HTTP 500."""

    pass


class AIProviderError(AIServiceError):
    """AI プロバイダーエラー → HTTP 503."""

    pass


# Protocol
@runtime_checkable
class AIService(Protocol):
    """AI サービスの共通インターフェース."""

    def generate_cards(
        self,
        input_text: str,
        card_count: int = 5,
        difficulty: DifficultyLevel = "medium",
        language: Language = "ja",
    ) -> GenerationResult:
        """テキストからフラッシュカードを生成する.

        Args:
            input_text: 生成元テキスト（10-2000文字）。
            card_count: 生成カード数（1-10）。
            difficulty: 難易度。
            language: 出力言語。

        Returns:
            生成されたカードとメタ情報。
        """
        ...

    def grade_answer(
        self,
        card_front: str,
        card_back: str,
        user_answer: str,
        language: Language = "ja",
    ) -> GradingResult:
        """ユーザーの回答を AI で採点する.

        Args:
            card_front: カードの問題文。
            card_back: カードの正解。
            user_answer: ユーザーの回答。
            language: 言語。

        Returns:
            SRS グレード（0-5）と採点理由。
        """
        ...

    def get_learning_advice(
        self,
        review_summary: dict,
        language: Language = "ja",
    ) -> LearningAdvice:
        """学習履歴に基づく AI アドバイスを取得する.

        Args:
            review_summary: 復習履歴の集計データ（事前クエリ結果）。
            language: 出力言語。

        Returns:
            アドバイス、弱点分野、推奨事項。
        """
        ...


# Factory function
def create_ai_service(use_strands: bool | None = None) -> AIService:
    """USE_STRANDS フラグに応じた AIService 実装を返す.

    Args:
        use_strands: 実装を明示指定する場合に渡す。None の場合は環境変数
            USE_STRANDS を参照する（"true" で StrandsAIService、それ以外は
            BedrockService）。

    Returns:
        フラグに応じた AIService 実装インスタンス。

    Raises:
        AIProviderError: サービスの初期化に失敗した場合。
    """
    if use_strands is None:
        use_strands = os.getenv("USE_STRANDS", "false").lower() == "true"

    try:
        if use_strands:
            from services.strands_service import StrandsAIService

            return StrandsAIService()
        else:
            from services.bedrock import BedrockService

            return BedrockService()
    except Exception as e:
        raise AIProviderError(f"Failed to initialize AI service: {e}") from e

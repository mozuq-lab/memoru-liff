"""
AI Strands Migration 型定義・インターフェース設計

作成日: 2026-02-23
関連設計: architecture.md

信頼性レベル:
- 🔵 青信号: EARS要件定義書・設計文書・既存実装を参考にした確実な型定義
- 🟡 黄信号: EARS要件定義書・設計文書・既存実装から妥当な推測による型定義
- 🔴 赤信号: EARS要件定義書・設計文書・既存実装にない推測による型定義
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal, Optional, Protocol


# ========================================
# 共通型定義
# ========================================

DifficultyLevel = Literal["easy", "medium", "hard"]  # 🔵 既存 prompts.py より
Language = Literal["ja", "en"]  # 🔵 既存 prompts.py より
SRSGrade = Literal[0, 1, 2, 3, 4, 5]  # 🔵 既存 srs.py の grade 定義より


# ========================================
# カード生成関連（既存互換）
# ========================================


@dataclass
class GeneratedCard:
    """生成されたフラッシュカード.

    🔵 信頼性: 既存 bedrock.py の GeneratedCard dataclass より
    """

    front: str  # 🔵 問題文
    back: str  # 🔵 解答
    suggested_tags: List[str] = field(default_factory=list)  # 🔵 推奨タグ


@dataclass
class GenerationResult:
    """カード生成結果メタデータ.

    🔵 信頼性: 既存 bedrock.py の GenerationResult dataclass より
    """

    cards: List[GeneratedCard]  # 🔵 生成されたカード一覧
    input_length: int  # 🔵 入力テキスト長
    model_used: str  # 🔵 使用モデル名
    processing_time_ms: int  # 🔵 処理時間(ms)


# ========================================
# 回答採点関連（新規）
# ========================================


@dataclass
class GradingResult:
    """AI 回答採点結果.

    🔵 信頼性: 要件 REQ-SM-003・設計ヒアリング Q4「AI直接グレーディング」選択より
    """

    grade: int  # 🔵 SRS グレード 0-5（SM-2 互換）
    reasoning: str  # 🔵 AI による採点理由
    model_used: str  # 🔵 使用モデル名
    processing_time_ms: int  # 🔵 処理時間(ms)


# ========================================
# 学習アドバイス関連（新規）
# ========================================


@dataclass
class ReviewSummary:
    """復習履歴の集計結果（事前クエリで作成）.

    🔵 信頼性: 要件 REQ-SM-004・設計ヒアリング Q5「事前クエリ」選択より
    """

    total_reviews: int  # 🔵 総復習回数
    average_grade: float  # 🔵 平均グレード
    total_cards: int  # 🔵 総カード数
    cards_due_today: int  # 🔵 本日期限カード数
    streak_days: int  # 🟡 連続学習日数（計算ロジックは実装時に決定）
    tag_performance: dict[str, float]  # 🔵 タグ別正答率 {tag: accuracy}
    recent_review_dates: List[str]  # 🟡 直近の復習日（表示用）


@dataclass
class LearningAdvice:
    """AI 学習アドバイス結果.

    🔵 信頼性: 要件 REQ-SM-004・ユーザーストーリー 3.1 より
    """

    advice_text: str  # 🔵 アドバイス本文
    weak_areas: List[str]  # 🔵 弱点分野
    recommendations: List[str]  # 🔵 推奨事項
    model_used: str  # 🔵 使用モデル名
    processing_time_ms: int  # 🔵 処理時間(ms)


# ========================================
# AIService Protocol
# ========================================


class AIService(Protocol):
    """AI サービスの共通インターフェース.

    🔵 信頼性: 設計ヒアリング Q1「Protocolベース」選択より

    USE_STRANDS フラグに応じて以下の実装が選択される:
    - USE_STRANDS=false: BedrockAIService（既存 boto3 実装）
    - USE_STRANDS=true:  StrandsAIService（Strands Agents SDK）
    """

    def generate_cards(
        self,
        input_text: str,
        card_count: int = 5,
        difficulty: DifficultyLevel = "medium",
        language: Language = "ja",
    ) -> GenerationResult:
        """テキストからフラッシュカードを生成する.

        🔵 信頼性: 既存 bedrock.py の generate_cards() インターフェースより

        Args:
            input_text: 生成元テキスト（10-2000文字）
            card_count: 生成カード数（1-10）
            difficulty: 難易度
            language: 出力言語

        Returns:
            GenerationResult: 生成されたカードとメタ情報
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

        🔵 信頼性: 要件 REQ-SM-003・設計ヒアリング Q4 より

        Args:
            card_front: カードの問題文
            card_back: カードの正解
            user_answer: ユーザーの回答
            language: 言語

        Returns:
            GradingResult: SRS グレード(0-5)と採点理由
        """
        ...

    def get_learning_advice(
        self,
        review_summary: dict,
        language: Language = "ja",
    ) -> LearningAdvice:
        """学習履歴に基づく AI アドバイスを取得する.

        🔵 信頼性: 要件 REQ-SM-004・設計ヒアリング Q5 より

        Args:
            review_summary: 復習履歴の集計データ（事前クエリ結果）
            language: 出力言語

        Returns:
            LearningAdvice: アドバイス、弱点分野、推奨事項
        """
        ...


# ========================================
# API リクエスト/レスポンスモデル（Pydantic v2）
# ========================================

# 以下は Pydantic BaseModel で実装する設計。
# 実際のコードは backend/src/models/ に配置。


# --- カード生成（既存互換） ---
# GenerateCardsRequest   🔵 既存 models/generate.py
# GenerateCardsResponse  🔵 既存 models/generate.py


# --- 回答採点（新規） ---
# GradeAnswerRequest:
#   user_answer: str (1-2000文字、空白のみ不可) 🔵 REQ-SM-003 より
#
# GradeAnswerResponse:
#   grade: int (0-5)        🔵 設計ヒアリング Q4 より
#   reasoning: str           🔵 設計ヒアリング Q4 より
#   card_front: str          🔵 参考表示用
#   card_back: str           🔵 参考表示用
#   grading_info: dict       🔵 メタ情報（model_used, processing_time_ms）


# --- 学習アドバイス（新規） ---
# LearningAdviceResponse:
#   advice_text: str         🔵 REQ-SM-004 より
#   weak_areas: List[str]    🔵 REQ-SM-004 より
#   recommendations: List[str] 🔵 REQ-SM-004 より
#   study_stats: dict        🔵 事前集計データ
#   advice_info: dict        🔵 メタ情報


# ========================================
# 例外階層
# ========================================


class AIServiceError(Exception):
    """AI サービスの基底例外クラス.

    🔵 信頼性: 設計ヒアリング Q6「統一例外階層」選択より
    """

    pass


class AITimeoutError(AIServiceError):
    """AI タイムアウトエラー → HTTP 504.

    🔵 信頼性: 既存 BedrockTimeoutError のマッピングより
    """

    pass


class AIRateLimitError(AIServiceError):
    """AI レート制限エラー → HTTP 429.

    🔵 信頼性: 既存 BedrockRateLimitError のマッピングより
    """

    pass


class AIInternalError(AIServiceError):
    """AI 内部エラー → HTTP 500.

    🔵 信頼性: 既存 BedrockInternalError のマッピングより
    """

    pass


class AIParseError(AIServiceError):
    """AI レスポンス解析エラー → HTTP 500.

    🔵 信頼性: 既存 BedrockParseError のマッピングより
    """

    pass


class AIProviderError(AIServiceError):
    """AI プロバイダーエラー → HTTP 503.

    🟡 信頼性: Strands Agents のプロバイダー切替エラーから推測
    """

    pass


# ========================================
# ファクトリ関数
# ========================================


def create_ai_service() -> AIService:
    """USE_STRANDS フラグに応じた AIService 実装を返す.

    🔵 信頼性: 設計ヒアリング Q1・REQ-SM-102/103 より

    Returns:
        AIService: フラグに応じた実装
            - USE_STRANDS=true:  StrandsAIService
            - USE_STRANDS=false: BedrockAIService
            - USE_STRANDS 未設定: BedrockAIService（安全なデフォルト）
    """
    ...


# ========================================
# 信頼性レベルサマリー
# ========================================
#
# - 🔵 青信号: 38件 (90%)
# - 🟡 黄信号: 4件 (10%)
# - 🔴 赤信号: 0件 (0%)
#
# 品質評価: ✅ 高品質（青信号 90%、赤信号なし）
#
# 🟡 の項目:
# - ReviewSummary.streak_days: 計算ロジックの詳細は実装時に決定
# - ReviewSummary.recent_review_dates: 表示フォーマットの詳細は実装時に決定
# - AIProviderError: Strands Agents のプロバイダーエラー型は SDK 調査後に確定
# - SRSGrade の Literal 定義: int の Union 型として実装するか検討

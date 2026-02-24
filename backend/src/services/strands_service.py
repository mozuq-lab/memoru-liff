"""StrandsAIService: AWS Strands Agents SDK を使用した AI サービス実装.

AIService Protocol に準拠し、Strands Agent 経由でフラッシュカードを生成する。
環境変数 ENVIRONMENT に応じて BedrockModel (prod/staging) または OllamaModel (dev)
を選択する。
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import List

from strands import Agent
from strands.models import BedrockModel

# OllamaModel: オプション依存（ollama パッケージが必要）。
# 未インストール環境でもモジュール import が成功するよう try/except でラップする。
try:
    from strands.models.ollama import OllamaModel
except ImportError:  # pragma: no cover
    OllamaModel = None  # type: ignore[assignment,misc]

from services.ai_service import (
    AIParseError,
    AIProviderError,
    AIRateLimitError,
    AIServiceError,
    AITimeoutError,
    DifficultyLevel,
    GeneratedCard,
    GenerationResult,
    GradingResult,
    Language,
    LearningAdvice,
)
from services.prompts import get_card_generation_prompt, get_grading_prompt
from services.prompts.grading import GRADING_SYSTEM_PROMPT

# Bedrock のデフォルトモデル ID
_DEFAULT_BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
_DEFAULT_OLLAMA_HOST = "http://localhost:11434"
_DEFAULT_OLLAMA_MODEL = "llama3.2"

# model_used フィールドに使用するプロバイダー識別子
_MODEL_USED_BEDROCK = "strands_bedrock"
_MODEL_USED_OLLAMA = "strands_ollama"


class StrandsAIService:
    """AWS Strands Agents SDK を使用した AI サービス実装.

    AIService Protocol に準拠し、カード生成と回答採点を提供する。
    get_learning_advice() は Phase 3 で実装予定のため、
    現在は NotImplementedError を raise するスタブになっている。

    Attributes:
        environment: 実行環境名 ('prod', 'staging', 'dev' 等)。
        model: Strands モデルプロバイダーインスタンス。
        model_used: model_used フィールドに使用するプロバイダー識別子。
    """

    def __init__(self, environment: str | None = None) -> None:
        """StrandsAIService を初期化する.

        Args:
            environment: 実行環境名。None の場合は環境変数 ENVIRONMENT を参照
                し、未設定の場合は "prod" をデフォルトとして使用する。
        """
        if environment is None:
            environment = os.getenv("ENVIRONMENT", "prod")
        self.environment = environment
        self.model, self.model_used = self._create_model()

    def _create_model(self) -> tuple[object, str]:
        """環境変数に基づいてモデルプロバイダーを選択・初期化する.

        Returns:
            (モデルプロバイダーインスタンス, model_used 識別子文字列) のタプル。
        """
        if self.environment == "dev":
            ollama_host = os.getenv("OLLAMA_HOST", _DEFAULT_OLLAMA_HOST)
            ollama_model = os.getenv("OLLAMA_MODEL", _DEFAULT_OLLAMA_MODEL)
            model = OllamaModel(
                host=ollama_host,
                model_id=ollama_model,
            )
            return model, _MODEL_USED_OLLAMA
        else:
            bedrock_model_id = os.getenv("BEDROCK_MODEL_ID", _DEFAULT_BEDROCK_MODEL_ID)
            model = BedrockModel(
                model_id=bedrock_model_id,
            )
            return model, _MODEL_USED_BEDROCK

    def generate_cards(
        self,
        input_text: str,
        card_count: int = 5,
        difficulty: DifficultyLevel = "medium",
        language: Language = "ja",
    ) -> GenerationResult:
        """テキストからフラッシュカードを Strands Agent 経由で生成する.

        Args:
            input_text: 生成元テキスト（10-2000文字）。
            card_count: 生成カード数（1-10）。
            difficulty: 難易度（'easy', 'medium', 'hard'）。
            language: 出力言語（'ja', 'en'）。

        Returns:
            GenerationResult: 生成されたカードとメタ情報。

        Raises:
            AITimeoutError: Agent 呼び出しがタイムアウトした場合。
            AIRateLimitError: レート制限に達した場合。
            AIProviderError: プロバイダー接続エラーが発生した場合。
            AIParseError: レスポンスの解析に失敗した場合。
            AIServiceError: その他の予期しないエラーが発生した場合。
        """
        start_time = time.time()

        try:
            # プロンプトを生成
            user_prompt = get_card_generation_prompt(
                input_text=input_text,
                card_count=card_count,
                difficulty=difficulty,
                language=language,
            )

            # Strands Agent を作成して呼び出す
            agent = Agent(model=self.model)
            response = agent(user_prompt)

            # レスポンスをテキストに変換して解析
            response_text = str(response)
            cards = self._parse_generation_result(response_text)

            processing_time_ms = int((time.time() - start_time) * 1000)

            return GenerationResult(
                cards=cards,
                input_length=len(input_text),
                model_used=self.model_used,
                processing_time_ms=processing_time_ms,
            )

        except AIServiceError:
            # 既にマッピング済みの例外はそのまま再 raise
            raise
        except TimeoutError as e:
            raise AITimeoutError(f"Agent timed out: {e}") from e
        except ConnectionError as e:
            raise AIProviderError(f"Provider connection error: {e}") from e
        except Exception as e:
            # botocore.exceptions.ClientError などの SDK 固有例外を処理
            error_str = str(e)

            # ClientError (botocore) のレート制限チェック
            if _is_rate_limit_error(e):
                raise AIRateLimitError(f"Rate limit exceeded: {e}") from e

            # タイムアウト関連エラーのチェック
            if "timeout" in error_str.lower() or "timed out" in error_str.lower():
                raise AITimeoutError(f"Agent timed out: {e}") from e

            # 接続エラー関連チェック（エラーメッセージと例外クラス名を確認）
            if "connection" in error_str.lower() or "connect" in type(e).__name__.lower():
                raise AIProviderError(f"Provider connection error: {e}") from e

            # その他の予期しない例外を AIServiceError にラップ
            raise AIServiceError(f"Unexpected error: {e}") from e

    def _parse_generation_result(self, response_text: str) -> List[GeneratedCard]:
        """Strands Agent のレスポンステキストをカードリストに変換する.

        以下の 2 種類のフォーマットに対応する:
        1. プレーン JSON: {"cards": [...]}
        2. Markdown コードブロック: ```json\\n{...}\\n```

        Args:
            response_text: Agent から返されたレスポンステキスト。

        Returns:
            GeneratedCard のリスト。

        Raises:
            AIParseError: JSON の解析に失敗した場合、または "cards" フィールドが
                欠落している場合、または有効なカードが 0 枚の場合。
        """
        try:
            # Markdown コードブロックを検出して JSON を抽出
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response_text)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response_text.strip()

            data = json.loads(json_str)

        except json.JSONDecodeError as e:
            raise AIParseError(f"Failed to parse JSON response: {e}") from e

        if "cards" not in data:
            raise AIParseError(
                "Response missing required 'cards' field. "
                f"Available keys: {list(data.keys())}"
            )

        cards: List[GeneratedCard] = []
        for card_data in data["cards"]:
            # 必須フィールドが欠落しているカードはスキップ
            if "front" not in card_data or "back" not in card_data:
                continue

            front = str(card_data["front"]).strip()
            back = str(card_data["back"]).strip()

            # 空文字のカードはスキップ
            if not front or not back:
                continue

            # tags フィールドを取得・検証
            tags = card_data.get("tags", [])
            if not isinstance(tags, list):
                tags = []
            tags = [str(t).strip() for t in tags if t]

            # "AI生成" タグが未設定の場合は先頭に挿入
            if "AI生成" not in tags and "AI Generated" not in tags:
                tags.insert(0, "AI生成")

            cards.append(
                GeneratedCard(
                    front=front,
                    back=back,
                    suggested_tags=tags,
                )
            )

        if not cards:
            raise AIParseError(
                "No valid cards found in response. "
                "All cards were missing required 'front'/'back' fields or were empty."
            )

        return cards

    def grade_answer(
        self,
        card_front: str,
        card_back: str,
        user_answer: str,
        language: Language = "ja",
    ) -> GradingResult:
        """ユーザーの回答を Strands Agent 経由で採点する.

        Args:
            card_front: カードの問題文。
            card_back: カードの正解。
            user_answer: ユーザーの回答。
            language: 出力言語（'ja', 'en'）。

        Returns:
            GradingResult: SM-2 グレード（0-5）と採点理由。

        Raises:
            AITimeoutError: Agent 呼び出しがタイムアウトした場合。
            AIRateLimitError: レート制限に達した場合。
            AIProviderError: プロバイダー接続エラーが発生した場合。
            AIParseError: レスポンスの解析に失敗した場合。
            AIServiceError: その他の予期しないエラーが発生した場合。
        """
        start_time = time.time()

        try:
            # プロンプトを生成
            user_prompt = get_grading_prompt(
                card_front=card_front,
                card_back=card_back,
                user_answer=user_answer,
                language=language,
            )

            # Strands Agent を作成して呼び出す
            agent = Agent(model=self.model)
            response = agent(user_prompt)

            # レスポンスをテキストに変換して解析
            response_text = str(response)
            grade, reasoning = self._parse_grading_result(response_text)

            processing_time_ms = int((time.time() - start_time) * 1000)

            return GradingResult(
                grade=grade,
                reasoning=reasoning,
                model_used=self.model_used,
                processing_time_ms=processing_time_ms,
            )

        except AIServiceError:
            # 既にマッピング済みの例外はそのまま再 raise
            raise
        except TimeoutError as e:
            raise AITimeoutError(f"Agent timed out: {e}") from e
        except ConnectionError as e:
            raise AIProviderError(f"Provider connection error: {e}") from e
        except Exception as e:
            # botocore.exceptions.ClientError などの SDK 固有例外を処理
            error_str = str(e)

            # ClientError (botocore) のレート制限チェック
            if _is_rate_limit_error(e):
                raise AIRateLimitError(f"Rate limit exceeded: {e}") from e

            # タイムアウト関連エラーのチェック
            if "timeout" in error_str.lower() or "timed out" in error_str.lower():
                raise AITimeoutError(f"Agent timed out: {e}") from e

            # 接続エラー関連チェック（エラーメッセージと例外クラス名を確認）
            if "connection" in error_str.lower() or "connect" in type(e).__name__.lower():
                raise AIProviderError(f"Provider connection error: {e}") from e

            # その他の予期しない例外を AIServiceError にラップ
            raise AIServiceError(f"Unexpected error: {e}") from e

    def _parse_grading_result(self, response_text: str) -> tuple[int, str]:
        """Strands Agent のレスポンステキストから採点結果を抽出する.

        以下の 2 種類のフォーマットに対応する:
        1. プレーン JSON: {"grade": 5, "reasoning": "..."}
        2. Markdown コードブロック: ```json\\n{...}\\n```

        Args:
            response_text: Agent から返されたレスポンステキスト。

        Returns:
            (grade: int, reasoning: str) のタプル。

        Raises:
            AIParseError: JSON の解析に失敗した場合、または必須フィールドが
                欠落している場合、または grade が整数に変換できない場合。
        """
        try:
            # Markdown コードブロックを検出して JSON を抽出
            json_match = re.search(r"```json\s*([\s\S]*?)\s*```", response_text)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response_text.strip()

            data = json.loads(json_str)

        except json.JSONDecodeError as e:
            raise AIParseError(f"Failed to parse JSON response: {e}") from e

        # 必須フィールドチェック
        if "grade" not in data:
            raise AIParseError(
                "Response missing required 'grade' field. "
                f"Available keys: {list(data.keys())}"
            )
        if "reasoning" not in data:
            raise AIParseError(
                "Response missing required 'reasoning' field. "
                f"Available keys: {list(data.keys())}"
            )

        # grade を整数に変換（変換不可の場合は AIParseError）
        try:
            grade = int(data["grade"])
        except (ValueError, TypeError) as e:
            raise AIParseError(
                f"Failed to convert 'grade' to int: {data['grade']!r}"
            ) from e

        reasoning = str(data["reasoning"])

        return grade, reasoning

    def get_learning_advice(
        self,
        review_summary: dict,
        language: Language = "ja",
    ) -> LearningAdvice:
        """学習アドバイスを取得する（Phase 3 で実装予定のスタブ）.

        Args:
            review_summary: 復習履歴の集計データ。
            language: 出力言語。

        Raises:
            NotImplementedError: このメソッドは Phase 3 で実装予定。
        """
        raise NotImplementedError(
            "get_learning_advice is not implemented yet (Phase 3)"
        )


def _is_rate_limit_error(exc: Exception) -> bool:
    """例外がレート制限エラーかどうかを判定するヘルパー関数.

    botocore.exceptions.ClientError の ThrottlingException をチェックする。

    Args:
        exc: チェック対象の例外。

    Returns:
        レート制限エラーの場合 True。
    """
    try:
        # botocore.exceptions.ClientError の場合
        error_code = exc.response["Error"]["Code"]  # type: ignore[attr-defined]
        throttling_codes = {
            "ThrottlingException",
            "Throttling",
            "RequestThrottled",
            "TooManyRequestsException",
            "ProvisionedThroughputExceededException",
        }
        return error_code in throttling_codes
    except (AttributeError, KeyError, TypeError):
        pass

    # エラーメッセージによるフォールバックチェック
    error_str = str(exc).lower()
    return any(
        keyword in error_str
        for keyword in ("throttl", "rate limit", "too many requests")
    )

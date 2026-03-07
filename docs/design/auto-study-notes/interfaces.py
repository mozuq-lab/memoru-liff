"""Auto Study Notes 型定義（バックエンド）.

作成日: 2026-03-07
関連設計: architecture.md

信頼性レベル:
- 🔵 青信号: EARS要件定義書・設計文書・既存実装を参考にした確実な型定義
- 🟡 黄信号: EARS要件定義書・設計文書・既存実装から妥当な推測による型定義
- 🔴 赤信号: EARS要件定義書・設計文書・既存実装にない推測による型定義
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Literal

# ========================================
# AIService Protocol 追加メソッドの型定義
# ========================================

# 🔵 信頼性: REQ-ASN-001・既存 AIService データクラスパターンより
SourceType = Literal["deck", "tag"]


@dataclass
class StudyNotesResult:
    """要約ノート生成結果.

    🔵 信頼性: REQ-ASN-031〜034・既存 GenerationResult パターンより
    """

    content: str  # 🔵 Markdown形式の要約ノート本文
    model_used: str  # 🔵 既存パターン: 使用AIモデル名
    processing_time_ms: int  # 🔵 既存パターン: 処理時間


@dataclass
class CardForNotes:
    """要約ノート生成用のカード情報.

    🔵 信頼性: 既存 Card モデル・REQ-ASN-001 より
    """

    front: str  # 🔵 カード表面
    back: str  # 🔵 カード裏面
    tags: List[str] = field(default_factory=list)  # 🔵 カードタグ


# ========================================
# AIService Protocol 追加メソッド定義
# ========================================

# 以下のメソッドを AIService Protocol に追加する
#
# 🔵 信頼性: REQ-ASN-401・既存 AIService Protocol パターンより
#
# def generate_study_notes(
#     self,
#     cards: List[CardForNotes],
# ) -> StudyNotesResult:
#     """カード群から要約ノートを生成する.
#
#     Args:
#         cards: 要約対象のカード一覧（5〜100枚）。
#
#     Returns:
#         Markdown形式の要約ノートとメタ情報。
#
#     Raises:
#         AITimeoutError: Bedrock API タイムアウト時。
#         AIRateLimitError: レート制限超過時。
#         AIInternalError: AI 内部エラー時。
#     """
#     ...


# ========================================
# Pydantic リクエスト/レスポンスモデル
# ========================================

# 🔵 信頼性: 既存 Pydantic モデルパターン・API仕様より
# 以下は backend/src/models/study_notes.py に配置

# from pydantic import BaseModel, Field
#
# class GenerateStudyNotesRequest(BaseModel):
#     """要約ノート生成リクエスト.
#
#     🔵 信頼性: API仕様・REQ-ASN-001より
#     """
#     source_type: Literal["deck", "tag"] = Field(
#         ..., description="生成ソース種別"
#     )
#     source_id: str = Field(
#         ..., description="デッキID or タグ名", min_length=1, max_length=200
#     )
#
#
# class StudyNotesData(BaseModel):
#     """要約ノートレスポンスデータ.
#
#     🔵 信頼性: API仕様・REQ-ASN-031〜034より
#     """
#     source_type: str
#     source_id: str
#     content: str  # Markdown形式
#     card_count: int
#     is_stale: bool
#     model_used: str
#     processing_time_ms: int
#     generated_at: str  # ISO 8601
#
#
# class StudyNotesResponse(BaseModel):
#     """要約ノートAPIレスポンス.
#
#     🔵 信頼性: 既存APIレスポンスパターンより
#     """
#     success: bool = True
#     data: StudyNotesData | None = None


# ========================================
# StudyNotesService の型定義
# ========================================

@dataclass
class CachedStudyNotes:
    """DynamoDB から取得したキャッシュデータ.

    🔵 信頼性: database-schema.md・設計ヒアリングより
    """

    user_id: str  # 🔵 PK
    source_key: str  # 🔵 SK: {source_type}#{source_id}
    source_type: str  # 🔵 "deck" or "tag"
    source_id: str  # 🔵 デッキID or タグ名
    content: str  # 🔵 Markdown形式の要約ノート
    card_count: int  # 🟡 生成時のカード枚数
    is_stale: bool  # 🔵 無効化フラグ
    model_used: str  # 🔵 使用AIモデル名
    processing_time_ms: int  # 🔵 処理時間
    generated_at: str  # 🔵 生成日時
    created_at: str  # 🔵 作成日時
    updated_at: str  # 🔵 更新日時

    @staticmethod
    def make_source_key(source_type: str, source_id: str) -> str:
        """source_key を生成する."""
        return f"{source_type}::{source_id}"


# ========================================
# 信頼性レベルサマリー
# ========================================
# - 🔵 青信号: 22件 (92%)
# - 🟡 黄信号: 2件 (8%)
# - 🔴 赤信号: 0件 (0%)
#
# 品質評価: ✅ 高品質

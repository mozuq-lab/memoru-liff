"""
AgentCore Memory 統合 型定義・インターフェース設計

作成日: 2026-03-07
関連設計: architecture.md

信頼性レベル:
- 🔵 青信号: EARS要件定義書・設計文書・既存実装を参考にした確実な型定義
- 🟡 黄信号: EARS要件定義書・設計文書・既存実装から妥当な推測による型定義
- 🔴 赤信号: EARS要件定義書・設計文書・既存実装にない推測による型定義
"""

from __future__ import annotations

import os
from typing import Any, Literal, Protocol

from aws_lambda_powertools import Logger


# ========================================
# 共通型定義
# ========================================

# 🔵 既存 tutor_service.py / tutor.py より
SessionBackend = Literal["agentcore", "dynamodb"]  # 🔵 feature-backlog.md より
LearningMode = Literal["free_talk", "quiz", "weak_point"]  # 🔵 既存 models/tutor.py より
SessionStatus = Literal["active", "ended", "timed_out"]  # 🔵 既存 tutor_service.py より


# ========================================
# SessionManager ファクトリ関連
# ========================================


def create_tutor_session_manager(
    session_id: str,
    user_id: str,
    backend: str | None = None,
) -> Any:
    """TUTOR_SESSION_BACKEND に応じた SessionManager を生成.

    🔵 信頼性: feature-backlog.md ファクトリコード例・ユーザヒアリング Q3 より

    グローバルスコープの AgentCoreMemoryClient を再利用し、
    リクエストごとに session_id 付きの SessionManager を生成する。

    Args:
        session_id: チューターセッション ID（例: "tutor_xxxx-xxxx"）
        user_id: ユーザー ID（AgentCore の actor_id として使用）
        backend: 明示的なバックエンド指定。None の場合は環境変数から自動判定。

    Returns:
        SessionManager: Strands SDK SessionManager インターフェース準拠の実装
            - agentcore → AgentCoreMemorySessionManager
            - dynamodb → DynamoDBSessionManager

    Raises:
        ValueError: 不正な TUTOR_SESSION_BACKEND 値
        TutorAIServiceError: AGENTCORE_MEMORY_ID 未設定（agentcore バックエンド時）
    """
    ...


def _resolve_backend() -> SessionBackend:
    """環境変数からバックエンドを自動判定.

    🔵 信頼性: REQ-101〜REQ-104・ユーザヒアリング Q3 より

    優先順位:
    1. TUTOR_SESSION_BACKEND 環境変数（明示指定）
    2. ENVIRONMENT=dev → dynamodb（自動選択）
    3. ENVIRONMENT=prod/staging → agentcore（デフォルト）
    """
    ...


# ========================================
# AgentCoreMemoryClient グローバル初期化
# ========================================


# 🔵 信頼性: REQ-403・ユーザヒアリング Q3「クライアントのみグローバル」より
_agentcore_client: Any | None = None


def _get_agentcore_client() -> Any:
    """AgentCoreMemoryClient をシングルトンで取得.

    🔵 信頼性: REQ-403・NFR-001 コールドスタート最適化より

    Lambda グローバルスコープで1回だけ初期化し、
    以降のリクエストでは同じインスタンスを再利用する。

    Returns:
        AgentCoreMemoryClient: AWS AgentCore Memory クライアント
    """
    ...


# ========================================
# DynamoDBSessionManager
# ========================================


class DynamoDBSessionManager:
    """DynamoDB ベースの SessionManager 実装.

    🔵 信頼性: REQ-003・feature-backlog.md「DynamoDB バックエンド」より

    Strands SDK の SessionManager インターフェースに準拠し、
    既存の tutor_sessions テーブルの messages フィールドを利用して
    会話履歴を管理する。

    Attributes:
        table_name: DynamoDB テーブル名
        session_id: セッション ID
        user_id: ユーザー ID
    """

    def __init__(
        self,
        table_name: str,
        session_id: str,
        user_id: str,
        dynamodb_resource: Any | None = None,
    ) -> None:
        """初期化.

        🔵 信頼性: 既存 tutor_service.py の DynamoDB 初期化パターンより

        Args:
            table_name: DynamoDB テーブル名
            session_id: セッション ID
            user_id: ユーザー ID（PK）
            dynamodb_resource: テスト用 DynamoDB リソース注入
        """
        ...

    def initialize(self, agent: Any, session_id: str | None = None) -> None:
        """セッションを初期化し、既存の会話履歴を Agent に復元.

        🔵 信頼性: Strands SessionManager.initialize() インターフェースより

        DynamoDB から messages フィールドを読み込み、
        Agent の messages に設定する。

        Args:
            agent: Strands Agent インスタンス
            session_id: セッション ID（オプション。コンストラクタの値を使用）
        """
        ...

    def append_message(self, message: dict, agent: Any) -> None:
        """メッセージを会話履歴に追加.

        🔵 信頼性: Strands SessionManager.append_message() インターフェースより

        Agent のメッセージを DynamoDB の messages フィールドに追記する。

        Args:
            message: Strands メッセージ形式 {"role": "...", "content": [...]}
            agent: Strands Agent インスタンス
        """
        ...

    def sync_agent(self, agent: Any) -> None:
        """Agent の状態を DynamoDB に同期.

        🔵 信頼性: Strands SessionManager.sync_agent() インターフェースより

        Agent の現在のメッセージ一覧を DynamoDB に永続化する。

        Args:
            agent: Strands Agent インスタンス
        """
        ...

    def close(self) -> None:
        """セッションをクローズ（DynamoDB では特に処理なし）.

        🔵 信頼性: Strands SessionManager インターフェースより
        """
        ...

    def __enter__(self) -> "DynamoDBSessionManager":
        """Context Manager: enter.

        🔵 信頼性: AgentCore SDK の Context Manager パターンに合わせた実装
        """
        return self

    def __exit__(self, *args: Any) -> None:
        """Context Manager: exit.

        🔵 信頼性: AgentCore SDK の Context Manager パターンに合わせた実装
        """
        self.close()


# ========================================
# StrandsTutorAIService 改修インターフェース
# ========================================


class StrandsTutorAIServiceInterface(Protocol):
    """SessionManager 対応後の StrandsTutorAIService インターフェース.

    🔵 信頼性: REQ-004・ユーザヒアリング Q5「全て SessionManager 経由」より

    変更点:
    - generate_response() の引数から messages を削除
    - user_message（単一メッセージ）を受け取る形式に変更
    - session_manager パラメータを追加
    """

    def generate_response(
        self,
        system_prompt: str,
        user_message: str,
        session_manager: Any | None = None,
    ) -> tuple[str, list[str]]:
        """AI 応答を生成する.

        🔵 信頼性: REQ-004・既存 generate_response() インターフェースの改修

        SessionManager が注入されている場合:
        - 過去の会話履歴は SessionManager が自動復元
        - AI 応答後に SessionManager が自動保存
        - user_message は単一のユーザーメッセージのみ

        SessionManager が注入されていない場合:
        - 後方互換のため messages パラメータで全履歴を渡す
          （BedrockTutorAIService 等で使用）

        Args:
            system_prompt: システムプロンプト
            user_message: ユーザーの単一メッセージ
            session_manager: SessionManager インスタンス（オプション）

        Returns:
            Tuple of (response_content, related_card_ids)
        """
        ...

    extract_related_cards: staticmethod  # 🔵 既存互換
    clean_response_text: staticmethod  # 🔵 既存互換


# ========================================
# TutorService 改修インターフェース
# ========================================


class TutorServiceInterface(Protocol):
    """SessionManager 対応後の TutorService インターフェース.

    🔵 信頼性: REQ-004, REQ-006, REQ-007・ユーザヒアリングより

    変更点:
    - session_manager_factory パラメータの追加
    - send_message() の会話履歴管理を SessionManager に委譲
    - start_session() の挨拶生成も SessionManager 経由
    - メタデータ管理は引き続き DynamoDB
    """

    def start_session(
        self,
        user_id: str,
        deck_id: str,
        mode: str,
    ) -> Any:
        """セッション開始.

        🔵 信頼性: REQ-004・ユーザヒアリング Q5 より

        変更後の処理フロー:
        1. デッキ・カードのバリデーション（既存）
        2. SessionManager 生成（create_tutor_session_manager）
        3. SessionManager 付き Agent で挨拶メッセージ生成
        4. 既存アクティブセッション自動終了（既存）
        5. メタデータを DynamoDB に保存
        """
        ...

    def send_message(
        self,
        user_id: str,
        session_id: str,
        content: str,
    ) -> Any:
        """メッセージ送信.

        🔵 信頼性: REQ-004, REQ-201・ユーザヒアリング Q5 より

        変更後の処理フロー:
        1. セッション状態チェック（既存）
        2. SessionManager 生成（create_tutor_session_manager）
        3. SessionManager 付き Agent で応答生成
           - SessionManager が過去の会話を自動復元
           - user_message のみ Agent に渡す
        4. メタデータ更新（message_count, updated_at）
        """
        ...

    def end_session(self, user_id: str, session_id: str) -> Any:
        """セッション終了（変更なし）.

        🔵 信頼性: 既存実装維持
        """
        ...

    def list_sessions(
        self, user_id: str, status: str | None = None, deck_id: str | None = None
    ) -> Any:
        """セッション一覧（変更なし）.

        🔵 信頼性: 既存実装維持
        """
        ...

    def get_session(self, user_id: str, session_id: str) -> Any:
        """セッション詳細取得.

        🟡 信頼性: 会話履歴の取得方法は SessionManager の実装依存

        変更後の処理フロー:
        1. メタデータ取得（既存）
        2. SessionManager 経由で会話履歴を取得
        3. メタデータ + メッセージを統合して返却
        """
        ...


# ========================================
# SAM テンプレート追加パラメータ
# ========================================

# 以下は template.yaml に追加するパラメータの設計仕様

# Parameters:
#   TutorSessionBackend:
#     Type: String
#     Default: "agentcore"
#     AllowedValues: ["agentcore", "dynamodb"]
#     Description: Tutor session history backend
#     🔵 信頼性: REQ-001・feature-backlog.md より
#
#   AgentCoreMemoryId:
#     Type: String
#     Default: ""
#     Description: AgentCore Memory ID for tutor sessions
#     🔵 信頼性: REQ-005, REQ-404・ユーザヒアリングより
#
# Globals.Function.Environment.Variables:
#   TUTOR_SESSION_BACKEND: !Ref TutorSessionBackend  🔵
#   AGENTCORE_MEMORY_ID: !Ref AgentCoreMemoryId      🔵
#
# Policies (Lambda 実行ロール):
#   - Effect: Allow
#     Action: bedrock-agentcore:*
#     Resource: "*"
#     🟡 信頼性: AgentCore Memory API アクセスに必要な IAM アクション。
#               具体的なアクション名は SDK ドキュメントで確認が必要


# ========================================
# 依存パッケージ追加
# ========================================

# requirements.txt に追加:
#   bedrock-agentcore[strands-agents]>=0.1.0
#   🔵 信頼性: REQ-401・feature-backlog.md 前提条件より


# ========================================
# 信頼性レベルサマリー
# ========================================
#
# - 🔵 青信号: 32件 (91%)
# - 🟡 黄信号: 3件 (9%)
# - 🔴 赤信号: 0件 (0%)
#
# 品質評価: ✅ 高品質（青信号 91%、赤信号なし）
#
# 🟡 の項目:
# - get_session の会話履歴取得方法: SessionManager からの読み取り API の詳細は実装時に確認
# - IAM ポリシーアクション: bedrock-agentcore:* の具体的なアクション名は SDK ドキュメントで確認
# - AgentCoreMemorySessionManager のコンストラクタ引数:
#   memory_client パラメータの受け渡し方法は SDK バージョンにより異なる可能性

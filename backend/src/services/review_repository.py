"""Review persistence layer (DynamoDB).

L-7: ReviewService から reviews テーブルへの DynamoDB アクセスを分離した永続化層。
SRS 計算やレスポンス組み立てといったビジネスロジックは ReviewService 側に残し、
本モジュールは「reviews テーブルをどう叩くか」「DynamoDB 固有の失敗をドメイン例外へ
変換するか」の責務のみを持つ。Cards テーブル側の SRS 更新・履歴取得は CardRepository
に集約しているため、本モジュールは分析用 reviews テーブルのみを扱う。
"""

import os
from typing import Any, Dict, List, Optional

from aws_lambda_powertools import Logger
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from utils.dynamodb_client import get_dynamodb_resource
from .card_repository import CardServiceError

logger = Logger()


class ReviewRepository:
    """Reviews テーブル永続化層: 分析用レビュー記録の読み書きを担う。"""

    def __init__(
        self,
        table_name: Optional[str] = None,
        dynamodb_resource=None,
    ):
        """Initialize ReviewRepository.

        Args:
            table_name: DynamoDB reviews table name. Defaults to REVIEWS_TABLE env var.
            dynamodb_resource: Optional boto3 DynamoDB resource for testing.
        """
        self.table_name = table_name or os.environ.get("REVIEWS_TABLE", "memoru-reviews-dev")
        self.dynamodb = get_dynamodb_resource(dynamodb_resource)
        self.table = self.dynamodb.Table(self.table_name)

    def record(self, item: Dict[str, Any]) -> None:
        """レビュー記録を reviews テーブルへ put_item する（分析専用・ベストエフォート）。

        reviews テーブルはストリーク・タグ別正答率などの集計/分析用であり、
        SRS の正 (source of truth) は card.review_history。よって書き込み失敗時も
        例外を送出せずログのみ記録し、ユーザー体験への影響を避ける。
        """
        try:
            self.table.put_item(Item=item)
        except ClientError as e:
            logger.warning(
                "Failed to record review (best-effort)",
                extra={
                    "user_id": item.get("user_id"),
                    "card_id": item.get("card_id"),
                    "error": str(e),
                },
            )

    def query_all_reviews(self, user_id: str) -> List[Dict[str, Any]]:
        """user_id-reviewed_at-index でユーザーの全レビューをページネーション取得する。

        Raises:
            CardServiceError: DynamoDB クエリ失敗時（呼び出し元 get_review_summary が
                既定値へフォールバックするために送出する）。
        """
        try:
            reviews: List[Dict[str, Any]] = []
            query_kwargs: Dict[str, Any] = {
                "IndexName": "user_id-reviewed_at-index",
                "KeyConditionExpression": Key("user_id").eq(user_id),
            }
            while True:
                response = self.table.query(**query_kwargs)
                reviews.extend(response.get("Items", []))
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key
            return reviews
        except ClientError as e:
            raise CardServiceError(f"Failed to query reviews: {e}")

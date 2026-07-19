"""Card persistence layer (DynamoDB).

CardService から DynamoDB アクセスと低レベルなエラー変換を分離した永続化層。
ビジネスロジック（deck 検証・SRS 計算・update 式の組み立て）は CardService 側に残し、
本モジュールは「DynamoDB をどう叩くか」と「DynamoDB 固有の失敗をドメイン例外へ変換する」
責務のみを持つ。
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from aws_lambda_powertools import Logger
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError

from utils.dynamodb_client import get_dynamodb_client, get_dynamodb_resource

# 【ロガー設定】: TransactionCanceledException などの内部エラーをログ出力するために必要 (EARS-009)
logger = Logger()


class CardServiceError(Exception):
    """Base exception for card service errors."""

    pass


class CardNotFoundError(CardServiceError):
    """Raised when card is not found."""

    pass


class CardLimitExceededError(CardServiceError):
    """Raised when user exceeds card limit."""

    pass


class InternalError(CardServiceError):
    """Raised when an internal transaction error occurs.

    【クラス目的】: CardLimitExceededError以外のTransactionCanceledException を
    明確に区別するための例外クラス。
    🔵 信頼性レベル: 青信号 - CR-02: 全TransactionCanceledExceptionをCardLimitExceededErrorとして
    扱う問題を解決するために追加 (EARS-005)
    """

    pass


class OptimisticLockError(CardServiceError):
    """Raised when an optimistic-lock ConditionExpression fails (concurrent update).

    L-7: ReviewService の楽観ロック付き SRS 更新を Repository 経由にした際、
    ConditionalCheckFailed を呼び出し元（ReviewService）が ConcurrentReviewError へ
    変換できるよう専用例外として表現する。
    """

    pass


class CardRepository:
    """Card 永続化層: DynamoDB アクセスを担う。"""

    def __init__(
        self,
        table_name: Optional[str] = None,
        dynamodb_resource=None,
        users_table_name: Optional[str] = None,
        reviews_table_name: Optional[str] = None,
    ):
        """Initialize CardRepository.

        Args:
            table_name: DynamoDB table name. Defaults to CARDS_TABLE env var.
            dynamodb_resource: Optional boto3 DynamoDB resource for testing.
            users_table_name: DynamoDB users table name. Defaults to USERS_TABLE env var.
            reviews_table_name: DynamoDB reviews table name. Defaults to REVIEWS_TABLE env var.
        """
        self.table_name = table_name or os.environ.get("CARDS_TABLE", "memoru-cards-dev")
        self.users_table_name = users_table_name or os.environ.get("USERS_TABLE", "memoru-users-dev")
        # 【レビューテーブル設定】: delete_card トランザクションで Reviews テーブルを参照するために必要
        self.reviews_table_name = reviews_table_name or os.environ.get("REVIEWS_TABLE", "memoru-reviews-dev")

        self.dynamodb = get_dynamodb_resource(dynamodb_resource)

        self.table = self.dynamodb.Table(self.table_name)
        self.users_table = self.dynamodb.Table(self.users_table_name)

        # 低レベルクライアント: transact_write_items 用
        # boto3.resource().meta.client はリソース層の型変換イベントハンドラーを含むため、
        # 低レベル DynamoDB JSON を二重シリアライズしてしまう。
        # 直接 boto3.client() を使うことで回避する。
        self._client = get_dynamodb_client()

    def get_item(self, user_id: str, card_id: str) -> Optional[Dict[str, Any]]:
        """カードの生 DynamoDB アイテムを取得する（存在しなければ None）。"""
        try:
            response = self.table.get_item(Key={"user_id": user_id, "card_id": card_id})
            return response.get("Item")
        except ClientError as e:
            raise CardServiceError(f"Failed to get card: {e}")

    def create_card_atomic(self, card_item: Dict[str, Any], user_id: str, max_cards: int) -> None:
        """TransactWriteItems で card_count インクリメントとカード作成をアトミックに実行する。

        Raises:
            CardLimitExceededError: カード上限超過時。
            InternalError: 上限超過以外のトランザクション失敗時。
            CardServiceError: その他の DynamoDB エラー時。
        """
        try:
            client = self._client
            serializer = TypeSerializer()

            # Serialize the card item
            serialized_card = {k: serializer.serialize(v) for k, v in card_item.items()}

            # Perform the transactional write
            client.transact_write_items(
                TransactItems=[
                    {
                        'Update': {
                            'TableName': self.users_table_name,
                            'Key': {'user_id': {'S': user_id}},
                            # 【UpdateExpression修正】: ADD を使用して
                            # card_count属性が存在しない場合は自動的に作成し、
                            # 存在する場合はインクリメントする
                            'UpdateExpression': 'ADD card_count :inc',
                            # 【ConditionExpression修正】: attribute_not_exists OR card_count < :limit
                            # card_count属性が未存在時は許可し、存在時はリミットチェック
                            'ConditionExpression': 'attribute_not_exists(card_count) OR card_count < :limit',
                            'ExpressionAttributeValues': {
                                ':inc': {'N': '1'},
                                ':limit': {'N': str(max_cards)},
                            }
                        }
                    },
                    {
                        'Put': {
                            'TableName': self.table_name,
                            'Item': serialized_card
                        }
                    }
                ]
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "TransactionCanceledException":
                # 【エラー分類修正】: CancellationReasons を解析して正確なエラーを判別する (EARS-006, EARS-007, EARS-008)
                # 以前は全TransactionCanceledExceptionをCardLimitExceededErrorとして扱っていたが、
                # 他のエラー (ValidationError等) は InternalError として区別する必要がある
                # 🔵 信頼性レベル: 青信号 - CR-02で特定された問題の修正
                reasons = e.response.get("CancellationReasons", [])
                # 【Index 0 確認】: TransactItems[0] は Users テーブルの Update (card_count チェック)
                # ConditionalCheckFailed はカード上限超過を意味する
                if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
                    raise CardLimitExceededError(f"Card limit of {max_cards} exceeded")
                # 【InternalError送出】: 上限超過以外のトランザクション失敗は InternalError
                # reasons が空/欠如、または Index 0 が ConditionalCheckFailed 以外の場合
                logger.error(f"Transaction cancelled with reasons: {reasons}")
                raise InternalError("Card creation failed due to transaction conflict")
            raise CardServiceError(f"Failed to create card: {e}")

    def update_item(
        self,
        user_id: str,
        card_id: str,
        update_expression: str,
        expression_values: Optional[Dict[str, Any]] = None,
        expression_names: Optional[Dict[str, str]] = None,
        error_message: str = "Failed to update card",
    ) -> None:
        """カードを update_item で更新する。

        High-1: DynamoDB の UpdateItem は upsert のため、ConditionExpression が無いと
        「CardService.get_card で読んだ後、この update_item を呼ぶまでの間」に
        別リクエストがカードを削除した場合、欠損アイテム（ゴースト）を新規作成して
        しまう。attribute_exists(card_id) を条件に付与し、その間に削除されていたら
        ConditionalCheckFailedException を CardNotFoundError に変換して呼び出し元
        （CardService.update_card）へ 404 相当として伝播させる。

        Args:
            error_message: ClientError を CardServiceError に変換する際のメッセージ接頭辞。

        Raises:
            CardNotFoundError: 更新対象のカードが (read 後に) 削除されていた場合。
            CardServiceError: その他の DynamoDB エラー時。
        """
        try:
            update_kwargs: Dict[str, Any] = {
                "Key": {"user_id": user_id, "card_id": card_id},
                "UpdateExpression": update_expression,
                # 【ゴースト再作成防止】: 更新対象のアイテムが存在する場合のみ更新する。
                "ConditionExpression": "attribute_exists(card_id)",
            }
            if expression_values:
                update_kwargs["ExpressionAttributeValues"] = expression_values
            if expression_names:
                update_kwargs["ExpressionAttributeNames"] = expression_names

            self.table.update_item(**update_kwargs)
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise CardNotFoundError(f"Card not found: {card_id}") from e
            raise CardServiceError(f"{error_message}: {e}")

    def delete_reviews_for_card(self, card_id: str, user_id: str) -> None:
        """カードに紐づく Reviews を全件削除する（トランザクション外、ベストエフォート）。

        Reviews テーブルのキーは card_id + reviewed_at の複合キーのため、
        TransactWriteItems の単一 Delete 操作では全レビューを一括削除できない。
        削除失敗時もカード削除を継続できるよう、本メソッドは例外を送出せずログのみ記録する。
        """
        deleted_review_count = 0
        failed_review_count = 0
        try:
            reviews_table = self.dynamodb.Table(self.reviews_table_name)
            query_kwargs: Dict[str, Any] = {
                "KeyConditionExpression": "card_id = :cid",
                "ExpressionAttributeValues": {":cid": card_id},
                "ProjectionExpression": "card_id, reviewed_at",
            }
            with reviews_table.batch_writer() as batch:
                while True:
                    response = reviews_table.query(**query_kwargs)
                    for item in response.get("Items", []):
                        try:
                            batch.delete_item(Key={"card_id": item["card_id"], "reviewed_at": item["reviewed_at"]})
                            deleted_review_count += 1
                        except Exception as item_err:
                            failed_review_count += 1
                            logger.warning(
                                "Failed to delete individual review record",
                                extra={
                                    "card_id": card_id,
                                    "reviewed_at": item.get("reviewed_at"),
                                    "error": str(item_err),
                                },
                            )
                    last_key = response.get("LastEvaluatedKey")
                    if not last_key:
                        break
                    query_kwargs["ExclusiveStartKey"] = last_key
        except Exception as e:
            logger.error(
                "Failed to delete reviews for card: review records may be orphaned",
                extra={
                    "card_id": card_id,
                    "user_id": user_id,
                    "deleted_review_count": deleted_review_count,
                    "failed_review_count": failed_review_count,
                    "error": str(e),
                },
            )

        if failed_review_count > 0:
            logger.warning(
                "Partial review deletion failure: some reviews may remain orphaned",
                extra={
                    "card_id": card_id,
                    "user_id": user_id,
                    "deleted_review_count": deleted_review_count,
                    "failed_review_count": failed_review_count,
                },
            )

    def delete_card_atomic(self, user_id: str, card_id: str) -> None:
        """TransactWriteItems でカード削除と card_count デクリメントをアトミックに実行する。

        Raises:
            CardNotFoundError: 並行削除によりカードが既に削除されていた場合 (EARS-012)。
            CardServiceError: card_count が既に 0 の場合 (EARS-013)、その他の DynamoDB エラー時。
        """
        try:
            client = self._client
            # 【トランザクション実行】: 2つの操作をアトミックに実行する
            client.transact_write_items(
                TransactItems=[
                    {
                        # 【Index 0】: Cards テーブルからカードを削除
                        # attribute_exists(card_id) でカード存在を確認 (レースコンディション対策)
                        'Delete': {
                            'TableName': self.table_name,
                            'Key': {'user_id': {'S': user_id}, 'card_id': {'S': card_id}},
                            'ConditionExpression': 'attribute_exists(card_id)'
                        }
                    },
                    {
                        # 【Index 1】: Users テーブルの card_count を 1 デクリメント
                        # card_count > :zero の条件でネガティブ値を防止 (EARS-014)
                        'Update': {
                            'TableName': self.users_table_name,
                            'Key': {'user_id': {'S': user_id}},
                            'UpdateExpression': 'SET card_count = card_count - :dec',
                            'ConditionExpression': 'card_count > :zero',
                            'ExpressionAttributeValues': {
                                ':dec': {'N': '1'},
                                ':zero': {'N': '0'}
                            }
                        }
                    }
                ]
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "TransactionCanceledException":
                reasons = e.response.get("CancellationReasons", [])
                # 【Index 0 確認】: Cards Delete の ConditionalCheckFailed はカードが既に削除された状態
                # レースコンディションにより別リクエストがカードを削除した場合 (EARS-012)
                if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
                    raise CardNotFoundError(f"Card not found: {card_id}")
                # 【Index 1 確認】: Users Update の ConditionalCheckFailed は card_count が既に 0
                # データ整合性のドリフト状態 (EARS-013)
                if len(reasons) > 1 and reasons[1].get("Code") == "ConditionalCheckFailed":
                    raise CardServiceError("Cannot delete card: card_count already at 0")
            raise CardServiceError(f"Failed to delete card: {e}")

    def query_cards_page(
        self,
        user_id: str,
        limit: int = 50,
        cursor: Optional[str] = None,
        deck_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """カード一覧を 1 ページ分取得する（生アイテムと次カーソルを返す）。"""
        try:
            query_kwargs: Dict[str, Any] = {
                "KeyConditionExpression": "user_id = :user_id",
                "ExpressionAttributeValues": {":user_id": user_id},
                "Limit": limit,
                "ScanIndexForward": False,  # Newest first
            }

            if cursor:
                query_kwargs["ExclusiveStartKey"] = {"user_id": user_id, "card_id": cursor}

            if deck_id:
                query_kwargs["FilterExpression"] = "deck_id = :deck_id"
                query_kwargs["ExpressionAttributeValues"][":deck_id"] = deck_id

            collected: List[Dict[str, Any]] = []
            next_cursor = None
            while True:
                response = self.table.query(**query_kwargs)
                items = response.get("Items", [])
                remaining = limit - len(collected)
                collected.extend(items[:remaining])

                last_key = response.get("LastEvaluatedKey")
                if len(items) > remaining:
                    # The continuation query evaluates a full page for efficiency.
                    # Resume after the last card actually returned so extra matches
                    # from this response remain available on the next request.
                    next_cursor = items[remaining - 1]["card_id"]
                    break

                if len(items) == remaining:
                    # M-10: このレスポンスで丁度 limit を満たした。
                    # まだ続きがある (last_key あり) 場合のみカーソルが必要だが、
                    # LastEvaluatedKey は FilterExpression 適用後ではなくスキャン停止
                    # 位置を指すため、deck_id フィルタ時にこれをカーソルへ流用すると
                    # 次ページで既返却カードや別 deck のカードが混ざり、境界がずれて
                    # 空ページ/スキップが生じうる。実際に返した最後のカード
                    # (items[remaining - 1]) をカーソルにすることで、フィルタ有無に
                    # 関わらず継続位置が正確になる。last_key が無い (終端) 場合は
                    # 次ページが存在しないため next_cursor は None のままにする。
                    if last_key:
                        next_cursor = items[remaining - 1]["card_id"]
                    break

                if not deck_id or len(collected) >= limit or not last_key:
                    if last_key:
                        next_cursor = last_key["card_id"]
                    break

                # DynamoDB applies Limit before FilterExpression. Continue scanning
                # until a filtered page is full so an existing deck never appears
                # empty merely because its cards were outside the first evaluated page.
                query_kwargs["ExclusiveStartKey"] = last_key

            return collected, next_cursor
        except ClientError as e:
            raise CardServiceError(f"Failed to list cards: {e}")

    def scan_all_cards(self, user_id: str) -> List[Dict[str, Any]]:
        """ユーザーの全カードをページネーションで取得する（生アイテム）。"""
        try:
            items: List[Dict[str, Any]] = []
            query_kwargs: Dict[str, Any] = {
                "KeyConditionExpression": "user_id = :user_id",
                "ExpressionAttributeValues": {":user_id": user_id},
            }
            while True:
                response = self.table.query(**query_kwargs)
                items.extend(response.get("Items", []))
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key
            return items
        except ClientError as e:
            raise CardServiceError(f"Failed to scan cards: {e}")

    def query_cards_by_reference_url(self, user_id: str, url: str) -> List[Dict[str, Any]]:
        """生成元 URL が一致するカードを reference-url-index GSI で取得する（M-13）。

        全件 scan + アプリ層完全一致から GSI Query へ置き換え、URL 重複検出のコストを
        ユーザーの蓄積カード数に依存しない O(一致件数) にする。HASH キー reference_url_key
        は "<user_id>#<url>" の複合キー。Projection=ALL のためカード本体を返せる。
        """
        key = f"{user_id}#{url}"
        try:
            items: List[Dict[str, Any]] = []
            query_kwargs: Dict[str, Any] = {
                "IndexName": "reference-url-index",
                "KeyConditionExpression": "reference_url_key = :key",
                "ExpressionAttributeValues": {":key": key},
            }
            while True:
                response = self.table.query(**query_kwargs)
                items.extend(response.get("Items", []))
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key
            return items
        except ClientError as e:
            raise CardServiceError(f"Failed to query cards by reference URL: {e}")

    def count_cards(self, user_id: str) -> int:
        """ユーザーのカード総数を返す (Select COUNT)。"""
        try:
            response = self.table.query(
                KeyConditionExpression="user_id = :user_id",
                ExpressionAttributeValues={":user_id": user_id},
                Select="COUNT",
            )
            return response.get("Count", 0)
        except ClientError as e:
            raise CardServiceError(f"Failed to get card count: {e}")

    def query_due_cards(
        self,
        user_id: str,
        limit: Optional[int] = None,
        before: Optional[datetime] = None,
        include_future: bool = False,
    ) -> List[Dict[str, Any]]:
        """復習対象カードの生アイテムを期限が古い順で取得する。"""
        try:
            # 【クエリ引数構築】: GSI (user_id-due-index) を使い、復習日時の昇順で取得する
            query_kwargs: Dict[str, Any] = {
                "IndexName": "user_id-due-index",
                "ExpressionAttributeValues": {
                    ":user_id": user_id,
                },
                "ScanIndexForward": True,  # 【昇順取得】: 期限が古い順（最も早く復習すべきカードを先頭に）
            }
            if include_future:
                query_kwargs["KeyConditionExpression"] = "user_id = :user_id"
            else:
                effective_before = before or datetime.now(timezone.utc)
                query_kwargs["KeyConditionExpression"] = (
                    "user_id = :user_id AND next_review_at <= :before"
                )
                query_kwargs["ExpressionAttributeValues"][":before"] = (
                    effective_before.isoformat()
                )

            # 【Limit 条件付き設定】: limit=None の場合は DynamoDB に Limit を渡さず全件取得する 🔵
            # limit が指定された場合のみ DynamoDB Query に Limit を付与し、レスポンスサイズを制限する。
            if limit is not None:
                query_kwargs["Limit"] = limit

            # 【ページネーション】: limit=None の場合は LastEvaluatedKey で全件取得する
            if limit is None:
                all_items = []
                while True:
                    response = self.table.query(**query_kwargs)
                    all_items.extend(response.get("Items", []))
                    last_key = response.get("LastEvaluatedKey")
                    if not last_key:
                        break
                    query_kwargs["ExclusiveStartKey"] = last_key
                return all_items
            else:
                response = self.table.query(**query_kwargs)
                return response.get("Items", [])
        except ClientError as e:
            raise CardServiceError(f"Failed to get due cards: {e}")

    def count_due_cards(
        self,
        user_id: str,
        before: Optional[datetime] = None,
        include_future: bool = False,
    ) -> int:
        """復習対象カード数を返す (Select COUNT、deck_id フィルタなし)。

        M-12: total_due_count を全件メモリ展開せずに正確に求めるための COUNT クエリ。
        Select="COUNT" によりカード本体は転送されず、ページネーションで >1MB のインデックスも
        正しく合算する。include_future=True のときは next_review_at の範囲条件を外し、
        将来分も含む全カードを集計する。

        Args:
            user_id: ユーザー ID。
            before: この時刻以前を due とみなす（既定は現在時刻）。include_future=True 時は無視。
            include_future: True なら将来分も含む全カードを集計する。
        """
        query_kwargs: Dict[str, Any] = {
            "IndexName": "user_id-due-index",
            "ExpressionAttributeValues": {":user_id": user_id},
            "Select": "COUNT",
        }
        if include_future:
            query_kwargs["KeyConditionExpression"] = "user_id = :user_id"
        else:
            if before is None:
                before = datetime.now(timezone.utc)
            query_kwargs["KeyConditionExpression"] = "user_id = :user_id AND next_review_at <= :before"
            query_kwargs["ExpressionAttributeValues"][":before"] = before.isoformat()

        try:
            count = 0
            while True:
                response = self.table.query(**query_kwargs)
                count += response.get("Count", 0)
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key
            return count
        except ClientError as e:
            raise CardServiceError(f"Failed to get due card count: {e}")

    def count_deck_due_cards(
        self,
        user_id: str,
        deck_id: str,
        before: Optional[datetime] = None,
        include_future: bool = False,
    ) -> int:
        """指定デッキの復習対象カード数を返す (Select COUNT + deck_id フィルタ)。

        M-12: deck_id 指定時の total_due_count を全件メモリ展開せずに正確に求める。
        user_id-due-index を Select="COUNT" + FilterExpression(deck_id) で集計するため、
        カード本体はアプリ層へ転送されない。Count はフィルタ適用後の件数で、
        ページネーションで全パーティションを走査して合算する。
        """
        query_kwargs: Dict[str, Any] = {
            "IndexName": "user_id-due-index",
            "ExpressionAttributeValues": {":user_id": user_id, ":deck_id": deck_id},
            "FilterExpression": "deck_id = :deck_id",
            "Select": "COUNT",
        }
        if include_future:
            query_kwargs["KeyConditionExpression"] = "user_id = :user_id"
        else:
            if before is None:
                before = datetime.now(timezone.utc)
            query_kwargs["KeyConditionExpression"] = "user_id = :user_id AND next_review_at <= :before"
            query_kwargs["ExpressionAttributeValues"][":before"] = before.isoformat()

        try:
            count = 0
            while True:
                response = self.table.query(**query_kwargs)
                count += response.get("Count", 0)
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key
            return count
        except ClientError as e:
            raise CardServiceError(f"Failed to get deck due card count: {e}")

    def query_deck_due_cards(
        self,
        user_id: str,
        deck_id: str,
        limit: int,
        before: Optional[datetime] = None,
        include_future: bool = False,
    ) -> List[Dict[str, Any]]:
        """指定デッキの復習対象カードを期限が古い順に最大 limit 件取得する。

        M-12: deck_id 指定時の本体取得を全件メモリ展開せずに行う。user_id-due-index
        (Projection=ALL) を FilterExpression(deck_id) 付きで Query し、フィルタ後の件数が
        limit に達するまでページングする。DynamoDB は Limit をフィルタ適用前に評価するため、
        1 ページあたりの走査件数を limit に抑えつつ、必要な件数だけ収集してメモリ使用を
        抑制する。ScanIndexForward=True で next_review_at 昇順（最も早く復習すべき順）。
        """
        query_kwargs: Dict[str, Any] = {
            "IndexName": "user_id-due-index",
            "ExpressionAttributeValues": {":user_id": user_id, ":deck_id": deck_id},
            "FilterExpression": "deck_id = :deck_id",
            "ScanIndexForward": True,
            "Limit": limit,
        }
        if include_future:
            query_kwargs["KeyConditionExpression"] = "user_id = :user_id"
        else:
            if before is None:
                before = datetime.now(timezone.utc)
            query_kwargs["KeyConditionExpression"] = "user_id = :user_id AND next_review_at <= :before"
            query_kwargs["ExpressionAttributeValues"][":before"] = before.isoformat()

        try:
            collected: List[Dict[str, Any]] = []
            while True:
                response = self.table.query(**query_kwargs)
                collected.extend(response.get("Items", []))
                if len(collected) >= limit:
                    return collected[:limit]
                last_key = response.get("LastEvaluatedKey")
                if not last_key:
                    break
                query_kwargs["ExclusiveStartKey"] = last_key
            return collected[:limit]
        except ClientError as e:
            raise CardServiceError(f"Failed to get deck due cards: {e}")

    def get_review_history(self, user_id: str, card_id: str) -> List[Dict[str, Any]]:
        """カードの review_history のみを取得する（取得失敗・属性欠落時は []）。

        L-7: ReviewService.undo_review が楽観ロックのベースラインとして直近の
        review_history を読む際の DynamoDB アクセスを集約する。ProjectionExpression で
        review_history のみを射影し、転送量を抑える。失敗時はアンドゥ対象なしと同義の
        空リストを返す（呼び出し元が NoReviewHistoryError へ変換する）。
        """
        try:
            response = self.table.get_item(
                Key={"user_id": user_id, "card_id": card_id},
                ProjectionExpression="review_history",
            )
            return response.get("Item", {}).get("review_history", [])
        except ClientError:
            return []

    def apply_review_update(
        self,
        user_id: str,
        card_id: str,
        update_expression: str,
        condition_expression: str,
        expression_values: Dict[str, Any],
        expression_names: Optional[Dict[str, str]] = None,
        return_values: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """楽観ロック付きで SRS 状態を update_item する（submit_review / undo 共通）。

        L-7: ReviewService に散在していた楽観ロック付き UpdateItem を集約する。
        ConditionExpression（CAS）・予約語 #interval エスケープ・キー定義といった
        DynamoDB 固有の知識を Repository 層へ寄せ、ReviewService は更新式の組み立てに
        専念できるようにする。

        High-1: condition_expression は
        ``attribute_exists(card_id) AND (SRS 値一致の CAS 条件...)`` の形を想定する
        （build_srs_optimistic_lock_condition 参照）。単一の UpdateItem
        ConditionExpression が失敗した場合、DynamoDB は AND のどちらの項が失敗したかを
        教えてくれない（TransactWriteItems の CancellationReasons のような詳細が無い）
        ため、追加で get_item を行い「カードが削除された（ゴースト再作成防止）」のか
        「カードは存在するが CAS が競合した（並行更新）」のかを区別する。

        Medium-4: return_values に "UPDATED_NEW" 等を指定すると、追加の get_item を
        挟まずに更新後の属性値（例: list_append 後の review_history 全体）を
        呼び出し元へ返せる。ReviewService の review_history 上限チェックで使用する。

        Args:
            return_values: DynamoDB UpdateItem の ReturnValues パラメータ
                （例: "UPDATED_NEW"）。指定時のみレスポンスの Attributes を返す。

        Returns:
            return_values 指定時は UpdateItem レスポンスの Attributes（無ければ None）。
            未指定時は常に None。

        Raises:
            CardNotFoundError: カードが (read 後に) 削除されていた場合。
            OptimisticLockError: カードは存在するが ConditionExpression 失敗
                （並行更新検出）時。
            CardServiceError: その他の DynamoDB エラー時。
        """
        try:
            update_kwargs: Dict[str, Any] = {
                "Key": {"user_id": user_id, "card_id": card_id},
                "UpdateExpression": update_expression,
                "ConditionExpression": condition_expression,
                "ExpressionAttributeValues": expression_values,
            }
            if expression_names:
                update_kwargs["ExpressionAttributeNames"] = expression_names
            if return_values:
                update_kwargs["ReturnValues"] = return_values

            response = self.table.update_item(**update_kwargs)
            return response.get("Attributes") if return_values else None
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # 【404 / 409 の出し分け】: 追加読み取りでカードの実在を確認する。
                if self.get_item(user_id, card_id) is None:
                    raise CardNotFoundError(f"Card not found: {card_id}") from e
                raise OptimisticLockError(
                    "Optimistic lock failed: card was modified concurrently"
                ) from e
            raise CardServiceError(f"Failed to apply review update: {e}")

    def query_next_due_after(
        self, user_id: str, after: datetime
    ) -> Optional[Dict[str, Any]]:
        """user_id-due-index で next_review_at > after の最も早いカードを 1 件取得する。

        L-7: ReviewService._get_next_due_date の GSI クエリを集約する。
        due_cards が空のとき「次の復習予定日」を求めるために用いる。取得失敗時は None。
        """
        try:
            response = self.table.query(
                IndexName="user_id-due-index",
                KeyConditionExpression="user_id = :user_id AND next_review_at > :after",
                ExpressionAttributeValues={
                    ":user_id": user_id,
                    ":after": after.isoformat(),
                },
                Limit=1,
                ScanIndexForward=True,
            )
            items = response.get("Items", [])
            return items[0] if items else None
        except ClientError:
            return None

"""URL カード生成のプレビュー → 保存導線を支える一時ストア (C-3).

LINE postback の data は 300 字制限があるため、生成済みカード本体を postback に
埋め込むことはできない。代わりに本ストアへ生成結果を保存し、postback には短い
参照キー (``ref``) のみを載せる。保存ボタンがタップされたら ref で本ストアから
カードを取り出し、再生成せずそのまま保存する（プレビューと保存内容の一致 +
Bedrock 二重課金の回避）。

テーブルは webhook 冪等サービスと同じ ``PROCESSED_EVENTS_TABLE`` を共用する
（webhook Lambda は同テーブルへ RW 権限を既に持つため template 変更不要）。
冪等レコード（キー ``webhook_event_id`` 値が LINE の event id）と衝突しないよう、
本ストアのキーは ``URLCARDS#<uuid4>`` という専用名前空間を用いる。
"""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError

from utils.dynamodb_client import get_dynamodb_resource

logger = Logger()

# プレビューカードの保持期間（秒）。期限切れ後は DynamoDB TTL で自動削除される。
_TTL_SECONDS = 24 * 60 * 60  # 24 hours

# 冪等レコードと衝突しないキー名前空間。
_KEY_PREFIX = "URLCARDS#"


class UrlCardsStore:
    """生成済み URL カードを ref key で一時保存／取得するストア。"""

    def __init__(
        self,
        table_name: Optional[str] = None,
        dynamodb_resource: Any | None = None,
    ) -> None:
        self.table_name = table_name or os.environ.get(
            "PROCESSED_EVENTS_TABLE", "memoru-processed-events-dev"
        )
        self.dynamodb = get_dynamodb_resource(dynamodb_resource)
        self.table = self.dynamodb.Table(self.table_name)

    def store_pending_cards(
        self,
        cards: List[Dict[str, Any]],
        page_url: str,
        page_title: str,
        now: float | None = None,
    ) -> str:
        """生成済みカードを保存し、postback 用の ref key を返す。

        Args:
            cards: front/back/suggested_tags を含むカード dict のリスト。
            page_url: 出典 URL（references に保存）。
            page_title: ページタイトル。
            now: テスト用の unix timestamp 上書き。

        Returns:
            ``URLCARDS#<uuid4>`` 形式の参照キー。
        """
        ref_key = f"{_KEY_PREFIX}{uuid.uuid4().hex}"
        ts = int(now if now is not None else time.time())
        self.table.put_item(
            Item={
                "webhook_event_id": ref_key,
                "cards": json.dumps(cards, ensure_ascii=False),
                "page_url": page_url,
                "page_title": page_title,
                "saved": False,
                "expires_at": ts + _TTL_SECONDS,
            }
        )
        return ref_key

    def get_pending_cards(self, ref_key: str) -> Optional[Dict[str, Any]]:
        """ref key からプレビューカードを取得する。

        Args:
            ref_key: ``store_pending_cards`` が返した参照キー。

        Returns:
            ``{"cards": [...], "page_url": str, "page_title": str, "saved": bool}``。
            レコードが無い／期限切れ（TTL 削除済み or expires_at 経過）なら None。
        """
        if not ref_key:
            return None
        try:
            response = self.table.get_item(Key={"webhook_event_id": ref_key})
        except ClientError as e:
            logger.warning(
                "Failed to load pending URL cards",
                extra={"ref_key": ref_key, "error": str(e)},
            )
            return None

        item = response.get("Item")
        if not item:
            return None

        # TTL 削除には遅延があるため、expires_at を超えていれば論理的に期限切れ扱い。
        expires_at = item.get("expires_at")
        if expires_at is not None and int(expires_at) < int(time.time()):
            return None

        raw_cards = item.get("cards", "[]")
        try:
            cards = json.loads(raw_cards) if isinstance(raw_cards, str) else raw_cards
        except (json.JSONDecodeError, TypeError):
            cards = []

        return {
            "cards": cards,
            "page_url": item.get("page_url", ""),
            "page_title": item.get("page_title", ""),
            "saved": bool(item.get("saved", False)),
        }

    def mark_saved(self, ref_key: str) -> bool:
        """二重保存防止フラグを立てる。

        既に ``saved`` が True ならフラグ更新は失敗し False を返す（再タップ時の
        二重保存を防ぐ）。レコードが無い場合も False。

        Returns:
            True  — このタップで初めて saved を立てた（保存処理を行ってよい）。
            False — 既に保存済み or レコード無し（保存処理をスキップすべき）。
        """
        if not ref_key:
            return False
        try:
            self.table.update_item(
                Key={"webhook_event_id": ref_key},
                UpdateExpression="SET #saved = :true",
                ConditionExpression=(
                    "attribute_exists(webhook_event_id) "
                    "AND (attribute_not_exists(#saved) OR #saved = :false)"
                ),
                ExpressionAttributeNames={"#saved": "saved"},
                ExpressionAttributeValues={":true": True, ":false": False},
            )
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                # 既に保存済み、またはレコードが存在しない。
                return False
            logger.warning(
                "Failed to mark URL cards saved (best-effort)",
                extra={"ref_key": ref_key, "error": str(e)},
            )
            # 不明なエラー時は二重保存を許容してでも保存導線を活かす（fail-open）。
            return True

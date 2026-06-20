#!/usr/bin/env python3
"""Backfill the ``reference_url_key`` GSI attribute on existing cards (M-13).

reference-url-index GSI は HASH キー ``reference_url_key`` ("<user_id>#<url>") を持つ
スパースインデックス。GSI 追加前に作成された既存カードはこの属性を持たないため
GSI に投影されず、URL 重複検出 (find_cards_by_reference_url) で取りこぼされる。
本スクリプトは Cards テーブルを全件 Scan し、生成元 URL（先頭の type=="url" reference）を
持つカードへ ``reference_url_key`` を後付けする。

特性:
  - 冪等: 既に正しい値を持つカードはスキップする。
  - 非破壊: 既存属性の上書きや削除は行わず、reference_url_key の SET のみ。
  - 安全: --dry-run で更新せず対象件数のみ集計する。

使い方（本番はユーザーが手動実行）:
    python backend/scripts/backfill_reference_url_key.py --table memoru-cards-prod --region ap-northeast-1
    python backend/scripts/backfill_reference_url_key.py --table memoru-cards-prod --dry-run

新規 GSI 追加後、DynamoDB のオンラインバックフィルが完了してから実行すること。
"""

import argparse
import os
import sys
from typing import Any, Dict, Optional

import boto3


def reference_url_key(user_id: str, url: str) -> str:
    """models.card.Card.reference_url_key と同一の複合キー生成（依存を避けるため再実装）。"""
    return f"{user_id}#{url}"


def extract_source_url(item: Dict[str, Any]) -> Optional[str]:
    """カードの references から生成元 URL（先頭の type=="url"）を抽出する。"""
    references = item.get("references") or []
    for ref in references:
        if isinstance(ref, dict) and ref.get("type") == "url":
            value = ref.get("value")
            if value:
                return value
    return None


def backfill(table_name: str, region: str, dry_run: bool) -> int:
    """Cards テーブルを Scan し reference_url_key を後付けする。更新件数を返す。"""
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(table_name)

    scanned = 0
    candidates = 0
    updated = 0
    skipped_existing = 0

    scan_kwargs: Dict[str, Any] = {}
    while True:
        response = table.scan(**scan_kwargs)
        for item in response.get("Items", []):
            scanned += 1
            source_url = extract_source_url(item)
            if not source_url:
                continue
            candidates += 1
            expected_key = reference_url_key(item["user_id"], source_url)
            if item.get("reference_url_key") == expected_key:
                skipped_existing += 1
                continue
            if dry_run:
                updated += 1
                continue
            table.update_item(
                Key={"user_id": item["user_id"], "card_id": item["card_id"]},
                UpdateExpression="SET reference_url_key = :k",
                ExpressionAttributeValues={":k": expected_key},
            )
            updated += 1

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key

    mode = "DRY-RUN (no writes)" if dry_run else "APPLIED"
    print(
        f"[{mode}] table={table_name} scanned={scanned} "
        f"url_cards={candidates} already_set={skipped_existing} updated={updated}"
    )
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill reference_url_key on cards (M-13).")
    parser.add_argument(
        "--table",
        default=os.environ.get("CARDS_TABLE"),
        help="Cards テーブル名（既定: 環境変数 CARDS_TABLE）。",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "ap-northeast-1"),
        help="AWS リージョン（既定: 環境変数 AWS_REGION または ap-northeast-1）。",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="更新せず対象件数のみ集計する。",
    )
    args = parser.parse_args()

    if not args.table:
        parser.error("--table または環境変数 CARDS_TABLE でテーブル名を指定してください。")

    backfill(args.table, args.region, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())

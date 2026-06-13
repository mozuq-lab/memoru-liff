"""DynamoDB リソース/クライアント生成の共通ファクトリ。

各サービスで重複していた boto3 リソース初期化ロジックを一元化する。
ローカル開発時は DYNAMODB_ENDPOINT_URL / AWS_ENDPOINT_URL で
エンドポイントを差し替えられる。
"""

import os
from typing import Any, Optional

import boto3


def get_endpoint_url() -> Optional[str]:
    """ローカル開発用の DynamoDB エンドポイント URL を返す（未設定時は None）。"""
    return os.environ.get("DYNAMODB_ENDPOINT_URL") or os.environ.get("AWS_ENDPOINT_URL")


def get_dynamodb_resource(dynamodb_resource: Optional[Any] = None) -> Any:
    """boto3 DynamoDB リソースを取得する。

    Args:
        dynamodb_resource: テスト等で注入されたリソース。指定時はそのまま返す。

    Returns:
        boto3 DynamoDB リソース。
    """
    if dynamodb_resource is not None:
        return dynamodb_resource

    endpoint_url = get_endpoint_url()
    if endpoint_url:
        return boto3.resource("dynamodb", endpoint_url=endpoint_url)
    return boto3.resource("dynamodb")


def get_dynamodb_client() -> Any:
    """低レベル boto3 DynamoDB クライアントを取得する。

    transact_write_items など低レベル DynamoDB JSON を直接扱う用途で使用する。
    boto3.resource().meta.client はリソース層の型変換イベントハンドラーを含むため、
    低レベル JSON を二重シリアライズしてしまう。直接 boto3.client() を使うことで回避する。

    Returns:
        boto3 DynamoDB クライアント。
    """
    endpoint_url = get_endpoint_url()
    if endpoint_url:
        return boto3.client("dynamodb", endpoint_url=endpoint_url)
    return boto3.client("dynamodb")

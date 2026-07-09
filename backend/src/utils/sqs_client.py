"""SQS クライアント生成の共通ファクトリ。

各サービスで重複していた boto3 SQS クライアント初期化ロジックを一元化する。
ローカル開発時は SQS_ENDPOINT_URL でエンドポイントを差し替えられる
（DynamoDB の DYNAMODB_ENDPOINT_URL と同じ役割。utils.dynamodb_client 参照）。

NOTE: DynamoDB の get_endpoint_url() と異なり AWS_ENDPOINT_URL へはフォール
バックしない。env.json では AWS_ENDPOINT_URL が DynamoDB Local
(http://dynamodb-local:8000) 用に既に使われており、共有すると SQS 呼び出しが
誤って DynamoDB のエンドポイントへ向いてしまうため、専用の SQS_ENDPOINT_URL
のみを見る。
"""

import os
from typing import Any, Optional

import boto3


def get_sqs_endpoint_url() -> Optional[str]:
    """ローカル開発用の SQS エンドポイント URL を返す（未設定時は None）。"""
    return os.environ.get("SQS_ENDPOINT_URL") or None


def get_sqs_client() -> Any:
    """boto3 SQS クライアントを取得する。"""
    endpoint_url = get_sqs_endpoint_url()
    if endpoint_url:
        return boto3.client("sqs", endpoint_url=endpoint_url)
    return boto3.client("sqs")

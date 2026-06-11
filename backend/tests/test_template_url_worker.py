"""SAM テンプレートの N-5 (URL カード生成 SQS 非同期化) リソース検証テスト。"""

import os

import pytest
import yaml


class CFLoader(yaml.SafeLoader):
    """CloudFormation 固有タグを許容するローダー."""


def _cf_constructor(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    elif isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)


CFLoader.add_multi_constructor("!", _cf_constructor)

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "template.yaml")


@pytest.fixture(scope="module")
def template():
    with open(TEMPLATE_PATH, "r") as f:
        return yaml.load(f, Loader=CFLoader)


@pytest.fixture(scope="module")
def resources(template):
    return template["Resources"]


def test_queue_and_dlq_exist(resources):
    assert "UrlGenerateQueue" in resources
    assert "UrlGenerateWorkerDLQ" in resources
    assert resources["UrlGenerateQueue"]["Type"] == "AWS::SQS::Queue"
    assert resources["UrlGenerateWorkerDLQ"]["Type"] == "AWS::SQS::Queue"


def test_queue_settings(resources):
    props = resources["UrlGenerateQueue"]["Properties"]
    # VisibilityTimeout > worker Timeout (120)
    assert props["VisibilityTimeout"] == 180
    assert props["KmsMasterKeyId"] == "alias/aws/sqs"
    assert props["RedrivePolicy"]["maxReceiveCount"] == 3


def test_max_receive_count_matches_worker_constant(resources):
    """template の maxReceiveCount とワーカーの最終試行判定定数を一致させる。"""
    from jobs.url_generate_worker_handler import MAX_RECEIVE_COUNT

    props = resources["UrlGenerateQueue"]["Properties"]
    assert props["RedrivePolicy"]["maxReceiveCount"] == MAX_RECEIVE_COUNT


def test_dlq_settings(resources):
    props = resources["UrlGenerateWorkerDLQ"]["Properties"]
    # 14 days retention (matches DuePushJobDLQ).
    assert props["MessageRetentionPeriod"] == 1209600
    assert props["KmsMasterKeyId"] == "alias/aws/sqs"


def test_worker_function_settings(resources):
    fn = resources["UrlGenerateWorkerFunction"]
    props = fn["Properties"]
    assert props["Handler"] == "jobs.url_generate_worker_handler.handler"
    assert props["Timeout"] == 120
    assert props["MemorySize"] == 512

    sqs_event = props["Events"]["UrlGenerateSqs"]
    assert sqs_event["Type"] == "SQS"
    # 1 件の処理時間が Lambda Timeout に近いため BatchSize は 1
    # （バッチ途中タイムアウトによる未処理メッセージの巻き込みを防ぐ）。
    assert sqs_event["Properties"]["BatchSize"] == 1
    assert "ReportBatchItemFailures" in sqs_event["Properties"]["FunctionResponseTypes"]
    assert sqs_event["Properties"]["ScalingConfig"]["MaximumConcurrency"] == 2


def test_webhook_function_has_queue_env_and_sqs_permission(resources):
    props = resources["LineWebhookFunction"]["Properties"]
    env = props["Environment"]["Variables"]
    assert "URL_GENERATE_QUEUE_URL" in env

    # SQS SendMessage 権限が含まれること（ポリシー文を文字列化して検査）。
    policies_text = str(props["Policies"])
    assert "sqs:SendMessage" in policies_text

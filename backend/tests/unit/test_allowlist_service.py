"""Unit tests for services/allowlist_service.py (signup-allowlist)."""

import os
from unittest.mock import patch

import boto3
import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

import services.allowlist_service as allowlist_service
from services.allowlist_service import (
    STATUS_APPROVED,
    STATUS_PENDING,
    get_status,
    record_pending,
    sanitize_display_name,
)

TABLE_NAME = "memoru-signup-allowlist-test"


@pytest.fixture
def allowlist_table():
    """moto で許可リストテーブルを作成し、モジュールキャッシュをリセットする。"""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")
        table = dynamodb.create_table(
            TableName=TABLE_NAME,
            KeySchema=[{"AttributeName": "identifier", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "identifier", "AttributeType": "S"}
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        table.wait_until_exists()
        allowlist_service._resource = None
        with patch.dict(os.environ, {"ALLOWLIST_TABLE": TABLE_NAME}):
            yield table
        allowlist_service._resource = None


class TestGetStatus:
    def test_returns_none_when_missing(self, allowlist_table):
        assert get_status("email#missing@example.com") is None

    def test_returns_approved_status(self, allowlist_table):
        allowlist_table.put_item(
            Item={"identifier": "email#a@example.com", "status": STATUS_APPROVED}
        )
        assert get_status("email#a@example.com") == STATUS_APPROVED

    def test_returns_pending_status(self, allowlist_table):
        allowlist_table.put_item(
            Item={"identifier": "idp#line_u1", "status": STATUS_PENDING}
        )
        assert get_status("idp#line_u1") == STATUS_PENDING

    def test_propagates_dynamodb_errors(self, allowlist_table):
        """テーブル未存在等の DynamoDB エラーはそのまま送出する（フェイルクローズ）。"""
        with patch.dict(os.environ, {"ALLOWLIST_TABLE": "nonexistent-table"}):
            allowlist_service._resource = None
            with pytest.raises(ClientError):
                get_status("email#a@example.com")
            allowlist_service._resource = None


class TestRecordPending:
    def test_creates_pending_record_with_expected_attributes(self, allowlist_table):
        record_pending("idp#line_u1", display_name="太郎")

        item = allowlist_table.get_item(Key={"identifier": "idp#line_u1"})["Item"]
        assert item["status"] == STATUS_PENDING
        assert item["display_name"] == "太郎"
        assert "created_at" in item
        assert "updated_at" in item
        assert "ttl" in item
        assert int(item["ttl"]) > 0

    def test_does_not_overwrite_existing_approved(self, allowlist_table):
        allowlist_table.put_item(
            Item={
                "identifier": "idp#line_u1",
                "status": STATUS_APPROVED,
                "note": "manually approved",
            }
        )

        record_pending("idp#line_u1", display_name="attacker-controlled")

        item = allowlist_table.get_item(Key={"identifier": "idp#line_u1"})["Item"]
        assert item["status"] == STATUS_APPROVED
        assert item["note"] == "manually approved"
        assert "display_name" not in item

    def test_does_not_overwrite_existing_pending(self, allowlist_table):
        record_pending("idp#line_u1", display_name="first-attempt")
        record_pending("idp#line_u1", display_name="second-attempt")

        item = allowlist_table.get_item(Key={"identifier": "idp#line_u1"})["Item"]
        assert item["display_name"] == "first-attempt"

    def test_display_name_none_stores_empty_string(self, allowlist_table):
        record_pending("idp#line_u1", display_name=None)

        item = allowlist_table.get_item(Key={"identifier": "idp#line_u1"})["Item"]
        assert item["display_name"] == ""

    def test_propagates_non_condition_dynamodb_errors(self, allowlist_table):
        with patch.dict(os.environ, {"ALLOWLIST_TABLE": "nonexistent-table"}):
            allowlist_service._resource = None
            with pytest.raises(ClientError):
                record_pending("idp#line_u1")
            allowlist_service._resource = None


class TestSanitizeDisplayName:
    def test_none_returns_empty_string(self):
        assert sanitize_display_name(None) == ""

    def test_empty_string_returns_empty_string(self):
        assert sanitize_display_name("") == ""

    def test_removes_control_characters(self):
        assert sanitize_display_name("A\x00B\x1fC\x7fD") == "ABCD"

    def test_removes_format_characters(self):
        # U+200B ZERO WIDTH SPACE はカテゴリ Cf（書式文字）
        assert sanitize_display_name("A​B") == "AB"

    def test_truncates_to_max_length(self):
        result = sanitize_display_name("あ" * 150)
        assert len(result) == 100
        assert result == "あ" * 100

    def test_normal_name_passthrough(self):
        assert sanitize_display_name("太郎") == "太郎"

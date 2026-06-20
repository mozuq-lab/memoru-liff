"""Unit tests for api.shared.parse_json_body.

全 POST/PUT ハンドラーに重複していたボディパース（json_body 取得 → dict 検証 →
Pydantic 変換 → ValidationError / JSONDecodeError ハンドリング）を一元化した
共通ヘルパーの検証。
"""

import json
from types import SimpleNamespace

from aws_lambda_powertools.event_handler import Response
from pydantic import BaseModel

from api.shared import parse_json_body


class _SampleRequest(BaseModel):
    name: str
    count: int = 1


def _resolver_with_body(body):
    """current_event.json_body が ``body`` を返す疑似 resolver を組み立てる。"""
    return SimpleNamespace(current_event=SimpleNamespace(json_body=body))


class _RaisingJsonBody:
    """json_body プロパティアクセスで JSONDecodeError を送出する疑似イベント。"""

    @property
    def json_body(self):
        raise json.JSONDecodeError("bad", "", 0)


class TestParseJsonBody:
    def test_valid_body_returns_model(self):
        resolver = _resolver_with_body({"name": "deck", "count": 3})
        result = parse_json_body(resolver, _SampleRequest)
        assert isinstance(result, _SampleRequest)
        assert result.name == "deck"
        assert result.count == 3

    def test_non_dict_body_returns_400(self):
        resolver = _resolver_with_body(["not", "a", "dict"])
        result = parse_json_body(resolver, _SampleRequest)
        assert isinstance(result, Response)
        assert result.status_code == 400
        assert "must be a JSON object" in result.body

    def test_validation_error_returns_400_with_details(self):
        # 必須フィールド name が欠落 → ValidationError。
        resolver = _resolver_with_body({"count": 2})
        result = parse_json_body(resolver, _SampleRequest)
        assert isinstance(result, Response)
        assert result.status_code == 400
        body = json.loads(result.body)
        assert body["error"] == "Invalid request"
        assert "details" in body

    def test_malformed_json_returns_400(self):
        resolver = SimpleNamespace(current_event=_RaisingJsonBody())
        result = parse_json_body(resolver, _SampleRequest)
        assert isinstance(result, Response)
        assert result.status_code == 400
        assert "Invalid JSON body" in result.body

"""Unit tests for POST /users/me/unlink-line response format.

TASK-0045: レスポンスDTO統一 + unlinkLine API使用
対象テストケース: TC-04, TC-05

RED フェーズ: 現在の実装が user_service.unlink_line() の戻り値（dict）を
              そのまま data フィールドに設定しているため、UserResponse 構造を
              期待するテストが FAIL することを確認する。
"""

import json
import pytest
from unittest.mock import patch, MagicMock


class TestUnlinkLineResponse:
    """TC-04〜05: POST /users/me/unlink-line が User 型レスポンスを返却する."""

    def test_unlink_line_returns_user_response_with_line_linked_false(
        self, api_gateway_event, lambda_context
    ):
        """LINE連携解除レスポンスが {success: true, data: User} 形式で line_linked=false を含む.

        【テスト目的】: unlink_line が User 型の data を返却し line_linked が false であることを検証
        【期待される動作】: data に UserResponse 構造が含まれ line_linked が false
        青 信頼性レベル: EARS-045-007, api-endpoints.md POST /users/me/unlink-line レスポンス仕様

        RED フェーズ失敗理由:
            handler.py L214 が {"success": True, "data": result} を返却しており、
            result は user_service.unlink_line() が返す dict {"user_id": ..., "unlinked_at": ...}。
            UserResponse 構造 (line_linked, notification_time 等) が含まれないため FAIL。
        """
        event = api_gateway_event(
            method="POST",
            path="/users/me/unlink-line",
            user_id="test-user-id",
        )

        with patch("src.api.handler.user_service") as mock_user_service:
            # unlink_line が User オブジェクトを返すようにモック
            # (GREEN フェーズ後の期待される戻り値型)
            mock_user = MagicMock()
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "user_id": "test-user-id",
                "display_name": "テストユーザー",
                "picture_url": None,
                "line_linked": False,
                "notification_time": "09:00",
                "timezone": "Asia/Tokyo",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-02T00:00:00+00:00",
            }
            mock_user.to_response.return_value = mock_response
            mock_user_service.unlink_line.return_value = mock_user

            from src.api.handler import handler
            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # 新形式の検証
        assert body["success"] is True
        assert "data" in body, (
            f"Expected 'data' key in response body, got keys: {list(body.keys())}"
        )
        assert body["data"]["user_id"] == "test-user-id"
        assert body["data"]["line_linked"] is False, (
            f"Expected line_linked=False, got: {body['data'].get('line_linked')}"
        )

        # 旧形式の否定検証: unlinked_at キーが存在しないこと
        assert "unlinked_at" not in body.get("data", {}), (
            f"Found unexpected 'unlinked_at' key in data: {body.get('data', {})}"
        )

    def test_unlink_line_includes_all_user_fields(
        self, api_gateway_event, lambda_context
    ):
        """LINE連携解除レスポンスに UserResponse の全8フィールドが含まれること.

        【テスト目的】: data オブジェクトが UserResponse 型の全フィールドを持つことを検証
        【期待される動作】: 旧形式の {user_id, unlinked_at} ではなく UserResponse 全フィールドが返る
        青 信頼性レベル: EARS-045-008

        RED フェーズ失敗理由:
            現在の実装では data が {"user_id": ..., "unlinked_at": ...} という dict であり、
            UserResponse の全フィールド (line_linked, notification_time, timezone, etc.) が存在しない。
        """
        event = api_gateway_event(
            method="POST",
            path="/users/me/unlink-line",
            user_id="test-user-id",
        )

        with patch("src.api.handler.user_service") as mock_user_service:
            mock_user = MagicMock()
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "user_id": "test-user-id",
                "display_name": "テストユーザー",
                "picture_url": None,
                "line_linked": False,
                "notification_time": "09:00",
                "timezone": "Asia/Tokyo",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-02T00:00:00+00:00",
            }
            mock_user.to_response.return_value = mock_response
            mock_user_service.unlink_line.return_value = mock_user

            from src.api.handler import handler
            response = handler(event, lambda_context)

        body = json.loads(response["body"])
        assert "data" in body, (
            f"Expected 'data' key in response body, got keys: {list(body.keys())}"
        )
        data = body["data"]

        required_fields = [
            "user_id",
            "display_name",
            "picture_url",
            "line_linked",
            "notification_time",
            "timezone",
            "created_at",
            "updated_at",
        ]
        for field in required_fields:
            assert field in data, (
                f"Missing field: {field}. Present fields: {list(data.keys())}"
            )

        # line_linked は false であること (連携解除後)
        assert data["line_linked"] is False, (
            f"Expected line_linked=False after unlink, got: {data.get('line_linked')}"
        )

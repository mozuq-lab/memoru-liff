"""Unit tests for PUT /users/me/settings response format.

TASK-0045: レスポンスDTO統一 + unlinkLine API使用
対象テストケース: TC-01, TC-02, TC-03

RED フェーズ: 現在の実装が UserSettingsResponse (success, settings) を返却しているため、
              data フィールドを期待するテストが FAIL することを確認する。
"""

import json
import pytest
from unittest.mock import patch, MagicMock


class TestUpdateSettingsResponse:
    """TC-01: PUT /users/me/settings が {success: true, data: User} 形式を返却する."""

    def test_update_settings_returns_data_not_settings(
        self, api_gateway_event, lambda_context
    ):
        """設定更新レスポンスが data フィールドを使用し settings フィールドを使用しない.

        【テスト目的】: レスポンス形式が旧 {success, settings} から新 {success, data} に変更されていることを検証
        【期待される動作】: レスポンスに data キーが存在し settings キーが存在しない
        青 信頼性レベル: EARS-045-001, api-endpoints.md の PUT /users/me/settings 変更後仕様

        RED フェーズ失敗理由:
            handler.py L191 が UserSettingsResponse を返却し、
            {"success": True, "settings": {...}} 形式のため "data" キーが存在しない。
        """
        event = api_gateway_event(
            method="PUT",
            path="/users/me/settings",
            body={"notification_time": "21:00", "timezone": "UTC"},
            user_id="test-user-id",
        )

        with patch("src.api.handler.user_service") as mock_user_service:
            mock_user = MagicMock()
            mock_user.settings = {"notification_time": "21:00", "timezone": "UTC"}
            mock_user_service.get_or_create_user.return_value = mock_user
            mock_user_service.update_settings.return_value = mock_user

            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "user_id": "test-user-id",
                "display_name": None,
                "picture_url": None,
                "line_linked": False,
                "notification_time": "21:00",
                "timezone": "UTC",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T12:00:00+00:00",
            }
            mock_user.to_response.return_value = mock_response

            from src.api.handler import handler
            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])

        # 新形式の検証: data キーが存在すること
        assert "success" in body
        assert body["success"] is True
        assert "data" in body, (
            f"Expected 'data' key in response body, got keys: {list(body.keys())}"
        )
        assert body["data"]["notification_time"] == "21:00"
        assert body["data"]["timezone"] == "UTC"
        assert body["data"]["user_id"] == "test-user-id"

        # 旧形式の否定検証: settings キーが存在しないこと
        assert "settings" not in body, (
            f"Found unexpected 'settings' key in response body: {body}"
        )

    def test_update_settings_includes_all_user_fields(
        self, api_gateway_event, lambda_context
    ):
        """設定更新レスポンスに UserResponse の全8フィールドが含まれること.

        【テスト目的】: data オブジェクトが UserResponse 型の全フィールドを持つことを検証
        【期待される動作】: user_id, display_name, picture_url, line_linked,
                          notification_time, timezone, created_at, updated_at が存在する
        青 信頼性レベル: EARS-045-002, UserResponse Pydantic モデル定義 (user.py L68-78)

        RED フェーズ失敗理由:
            現在の実装では data キーが存在しないため、フィールド検証に到達できない。
        """
        event = api_gateway_event(
            method="PUT",
            path="/users/me/settings",
            body={"notification_time": "21:00"},
            user_id="test-user-id",
        )

        with patch("src.api.handler.user_service") as mock_user_service:
            mock_user = MagicMock()
            mock_user.settings = {"notification_time": "21:00", "timezone": "Asia/Tokyo"}
            mock_user_service.get_or_create_user.return_value = mock_user
            mock_user_service.update_settings.return_value = mock_user

            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "user_id": "test-user-id",
                "display_name": "テストユーザー",
                "picture_url": None,
                "line_linked": True,
                "notification_time": "21:00",
                "timezone": "Asia/Tokyo",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-01T12:00:00+00:00",
            }
            mock_user.to_response.return_value = mock_response

            from src.api.handler import handler
            response = handler(event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert "data" in body, (
            f"Expected 'data' key in response body, got keys: {list(body.keys())}"
        )
        data = body["data"]

        # 全 UserResponse フィールドの存在検証
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

        # LINE 連携済みの場合 line_linked は true
        assert data["line_linked"] is True

        # timezone が IANA 形式であること
        assert isinstance(data["timezone"], str)
        assert "/" in data["timezone"] or data["timezone"] == "UTC"

    def test_update_settings_reflects_updated_values(
        self, api_gateway_event, lambda_context
    ):
        """設定更新レスポンスが更新後の値を正しく反映すること.

        【テスト目的】: notification_time と timezone の更新値がレスポンスに反映されることを検証
        【期待される動作】: 送信した設定値がレスポンスの data に反映される
        青 信頼性レベル: EARS-045-003

        RED フェーズ失敗理由:
            TC-01 と同一 - data キーが存在しないため更新値の検証に到達できない。
        """
        event = api_gateway_event(
            method="PUT",
            path="/users/me/settings",
            body={"notification_time": "21:00", "timezone": "UTC"},
            user_id="test-user-id",
        )

        with patch("src.api.handler.user_service") as mock_user_service:
            mock_user = MagicMock()
            mock_user.settings = {"notification_time": "21:00", "timezone": "UTC"}
            mock_user_service.get_or_create_user.return_value = mock_user
            mock_user_service.update_settings.return_value = mock_user

            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "user_id": "test-user-id",
                "display_name": None,
                "picture_url": None,
                "line_linked": False,
                "notification_time": "21:00",
                "timezone": "UTC",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-02T00:00:00+00:00",
            }
            mock_user.to_response.return_value = mock_response

            from src.api.handler import handler
            response = handler(event, lambda_context)

        body = json.loads(response["body"])
        assert "data" in body, (
            f"Expected 'data' key in response body, got keys: {list(body.keys())}"
        )
        data = body["data"]

        # 更新後の値が反映されていること
        assert data["notification_time"] == "21:00"
        assert data["timezone"] == "UTC"

        # user_id は変更されていないこと
        assert data["user_id"] == "test-user-id"

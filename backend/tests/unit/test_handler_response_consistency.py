"""Unit tests for response consistency across endpoints.

TASK-0045: レスポンスDTO統一 + unlinkLine API使用
対象テストケース: TC-06

RED フェーズ: PUT /users/me/settings と POST /users/me/unlink-line の両エンドポイントが
              同一の UserResponse フィールドセットを返却していないため FAIL することを確認する。
"""

import json
import pytest
from unittest.mock import patch, MagicMock


class TestResponseConsistency:
    """TC-06: レスポンス形式の一貫性検証."""

    def test_settings_and_unlink_return_same_user_structure(
        self, api_gateway_event, lambda_context
    ):
        """PUT /users/me/settings と POST /users/me/unlink-line が同じ User 構造を返す.

        【テスト目的】: 変更対象の2エンドポイントが同一の UserResponse フィールドセットを返すことを検証
        【期待される動作】: 両方のレスポンスの data に同一の8フィールドが含まれる
        青 信頼性レベル: EARS-045-021, EARS-045-022

        RED フェーズ失敗理由:
            - PUT /users/me/settings: UserSettingsResponse (success, settings) を返却するため
              data キーが存在しない
            - POST /users/me/unlink-line: {"user_id": ..., "unlinked_at": ...} を返却するため
              UserResponse フィールドセットと一致しない
            - 両エンドポイントでフィールドセットが不一致
        """
        user_response_fields = {
            "user_id", "display_name", "picture_url", "line_linked",
            "notification_time", "timezone", "created_at", "updated_at",
        }

        # --- PUT /users/me/settings ---
        settings_event = api_gateway_event(
            method="PUT",
            path="/users/me/settings",
            body={"notification_time": "21:00"},
            user_id="test-user-id",
        )

        with patch("src.api.handler.user_service") as mock_user_service:
            mock_user = MagicMock()
            mock_response = MagicMock()
            mock_response.model_dump.return_value = {
                "user_id": "test-user-id",
                "display_name": None,
                "picture_url": None,
                "line_linked": True,
                "notification_time": "21:00",
                "timezone": "Asia/Tokyo",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-02T00:00:00+00:00",
            }
            mock_user.to_response.return_value = mock_response
            mock_user.settings = {"notification_time": "21:00", "timezone": "Asia/Tokyo"}
            mock_user_service.get_or_create_user.return_value = mock_user
            mock_user_service.update_settings.return_value = mock_user

            from src.api.handler import handler
            settings_response = handler(settings_event, lambda_context)

        settings_body = json.loads(settings_response["body"])
        assert "data" in settings_body, (
            f"PUT /users/me/settings response missing 'data' key. "
            f"Got keys: {list(settings_body.keys())}"
        )
        settings_data_keys = set(settings_body["data"].keys())

        # --- POST /users/me/unlink-line ---
        unlink_event = api_gateway_event(
            method="POST",
            path="/users/me/unlink-line",
            user_id="test-user-id",
        )

        with patch("src.api.handler.user_service") as mock_user_service:
            mock_user2 = MagicMock()
            mock_response2 = MagicMock()
            mock_response2.model_dump.return_value = {
                "user_id": "test-user-id",
                "display_name": None,
                "picture_url": None,
                "line_linked": False,
                "notification_time": "09:00",
                "timezone": "Asia/Tokyo",
                "created_at": "2024-01-01T00:00:00+00:00",
                "updated_at": "2024-01-02T00:00:00+00:00",
            }
            mock_user2.to_response.return_value = mock_response2
            mock_user_service.unlink_line.return_value = mock_user2

            unlink_response = handler(unlink_event, lambda_context)

        unlink_body = json.loads(unlink_response["body"])
        assert "data" in unlink_body, (
            f"POST /users/me/unlink-line response missing 'data' key. "
            f"Got keys: {list(unlink_body.keys())}"
        )
        unlink_data_keys = set(unlink_body["data"].keys())

        # 両方のレスポンスが同じフィールドセットを持つことを検証
        assert settings_data_keys == user_response_fields, (
            f"Settings response fields mismatch.\n"
            f"Expected: {user_response_fields}\n"
            f"Got: {settings_data_keys}\n"
            f"Missing: {user_response_fields - settings_data_keys}\n"
            f"Extra: {settings_data_keys - user_response_fields}"
        )
        assert unlink_data_keys == user_response_fields, (
            f"Unlink response fields mismatch.\n"
            f"Expected: {user_response_fields}\n"
            f"Got: {unlink_data_keys}\n"
            f"Missing: {user_response_fields - unlink_data_keys}\n"
            f"Extra: {unlink_data_keys - user_response_fields}"
        )
        assert settings_data_keys == unlink_data_keys, (
            f"Settings and unlink responses have different field sets.\n"
            f"Settings: {settings_data_keys}\n"
            f"Unlink: {unlink_data_keys}"
        )

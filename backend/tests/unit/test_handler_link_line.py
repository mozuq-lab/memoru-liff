"""Unit tests for handler.py link_line_account with ID token verification.

TASK-0044: LINE ID トークン検証 + httpx 統一
対象テストケース: TC-07 ~ TC-10
"""

import json
import pytest
from unittest.mock import patch, MagicMock


class TestLinkLineHandler:
    """TC-07〜TC-10: link_line_account ハンドラの ID トークン検証フローのテスト."""

    def test_link_line_missing_id_token(self, api_gateway_event, lambda_context):
        """TC-07: リクエストボディに id_token がない場合に 400 エラーが返る.

        【テスト目的】: id_token フィールドが必須であることを検証する
        【テスト内容】: 空のボディでリクエストを送信し、400 レスポンスを確認する
        【期待される動作】: 400 ステータスコードと "id_token" に関するエラーメッセージが返る
        🔵 信頼性レベル: 青信号 - REQ-V2-021 の id_token 必須バリデーションに基づく
        """
        # 【テストデータ準備】: id_token なしのリクエストイベントを作成
        event = api_gateway_event(
            method="POST",
            path="/users/link-line",
            body={},  # 【初期条件設定】: id_token フィールドなし
        )

        # 【実際の処理実行】: handler を呼び出す
        with patch("api.handler.user_service") as mock_user_service, \
             patch("api.handler.line_service") as mock_line_service:
            mock_user_service.get_or_create_user.return_value = MagicMock()

            from api.handler import handler
            response = handler(event, lambda_context)

        # 【結果検証】: 400 ステータスコードが返ることを確認
        assert response["statusCode"] == 400  # 【確認内容】: id_token なしで 400 Bad Request が返る 🔵

        # 【確認内容】: レスポンスボディに id_token に関するエラーメッセージが含まれる
        body = json.loads(response["body"])
        body_str = json.dumps(body).lower()
        assert "id_token" in body_str, (
            f"Error message should mention 'id_token', got: {body}"
        )  # 🔵

    def test_link_line_empty_id_token(self, api_gateway_event, lambda_context):
        """TC-08: リクエストボディの id_token が空文字の場合に 400 エラーが返る.

        【テスト目的】: id_token の空文字バリデーションを検証する
        【テスト内容】: 空文字の id_token でリクエストを送信し、400 レスポンスを確認する
        【期待される動作】: 400 ステータスコードが返る
        🔵 信頼性レベル: 青信号 - REQ-V2-021 の min_length=1 バリデーション要件に基づく
        """
        # 【テストデータ準備】: 空文字の id_token を含むリクエストイベントを作成
        event = api_gateway_event(
            method="POST",
            path="/users/link-line",
            body={"id_token": ""},  # 【初期条件設定】: 空文字の id_token
        )

        # 【実際の処理実行】: handler を呼び出す
        with patch("api.handler.user_service") as mock_user_service, \
             patch("api.handler.line_service") as mock_line_service:
            mock_user_service.get_or_create_user.return_value = MagicMock()

            from api.handler import handler
            response = handler(event, lambda_context)

        # 【結果検証】: 400 ステータスコードが返ることを確認
        assert response["statusCode"] == 400  # 【確認内容】: 空文字の id_token で 400 Bad Request が返る 🔵

    def test_link_line_success_with_id_token(self, api_gateway_event, lambda_context):
        """TC-09: 有効な id_token を検証して LINE 連携が成功する.

        【テスト目的】: ID トークン検証フローが正しく実装されていることを検証する
        【テスト内容】:
            - line_service.verify_id_token が正しい引数で呼ばれることを確認
            - user_service.link_line が検証済み line_user_id で呼ばれることを確認
            - 成功レスポンス (200) が返ることを確認
        【期待される動作】: 検証済みの line_user_id で連携が確定し、200 が返る
        🔵 信頼性レベル: 青信号 - REQ-V2-022, REQ-V2-023 の検証フローに基づく
        """
        # 【テストデータ準備】: 有効な id_token を含むリクエストイベントを作成
        event = api_gateway_event(
            method="POST",
            path="/users/link-line",
            body={"id_token": "valid-liff-id-token"},  # 【初期条件設定】: 有効な id_token
            user_id="test-user-id",
        )

        # 【実際の処理実行】: handler を呼び出す
        with patch("api.handler.user_service") as mock_user_service, \
             patch("api.handler.line_service") as mock_line_service:
            # verify_id_token が line_user_id を返すようにモック
            mock_line_service.verify_id_token.return_value = "U1234567890abcdef1234567890abcdef"
            mock_user_service.get_or_create_user.return_value = MagicMock()

            from api.handler import handler
            response = handler(event, lambda_context)

        # 【結果検証】: 200 ステータスコードが返ることを確認
        assert response["statusCode"] == 200  # 【確認内容】: LINE 連携成功で 200 が返る 🔵

        # 【確認内容】: verify_id_token が正しい id_token で呼ばれたことを確認
        mock_line_service.verify_id_token.assert_called_once_with("valid-liff-id-token")  # 🔵

        # 【確認内容】: link_line が検証済み line_user_id で呼ばれたことを確認
        mock_user_service.link_line.assert_called_once_with(
            "test-user-id",
            "U1234567890abcdef1234567890abcdef",
        )  # 🔵

    def test_link_line_unauthorized_on_verification_failure(self, api_gateway_event, lambda_context):
        """TC-10: ID トークン検証失敗時に 401 エラーが返る.

        【テスト目的】: ID トークン検証失敗時に 401 が返ることを検証する
        【テスト内容】:
            - verify_id_token が UnauthorizedError を発生させる場合の処理を確認
            - 401 ステータスコードと適切なエラーメッセージを確認
        【期待される動作】: 401 ステータスコードが返る
        🔵 信頼性レベル: 青信号 - REQ-V2-121 の 401 レスポンス要件に基づく
        """
        from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

        # 【テストデータ準備】: id_token を含むリクエストイベントを作成
        event = api_gateway_event(
            method="POST",
            path="/users/link-line",
            body={"id_token": "invalid-token"},  # 【初期条件設定】: 無効な id_token
        )

        # 【実際の処理実行】: handler を呼び出す
        with patch("api.handler.user_service") as mock_user_service, \
             patch("api.handler.line_service") as mock_line_service:
            mock_user_service.get_or_create_user.return_value = MagicMock()
            # verify_id_token が UnauthorizedError を発生させるようにモック
            mock_line_service.verify_id_token.side_effect = UnauthorizedError(
                "LINE ID token verification failed"
            )

            from api.handler import handler
            response = handler(event, lambda_context)

        # 【結果検証】: 401 ステータスコードが返ることを確認
        assert response["statusCode"] == 401  # 【確認内容】: ID トークン検証失敗で 401 が返る 🔵

        # 【確認内容】: レスポンスボディに適切なエラーメッセージが含まれる（任意確認）
        body = json.loads(response["body"])
        body_str = json.dumps(body).lower()
        assert (
            "verification failed" in body_str
            or "unauthorized" in body_str
            or "error" in body
        ), f"Expected error message in response body, got: {body}"  # 🔵

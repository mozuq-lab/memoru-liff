"""Unit tests for LineService.verify_id_token and httpx migration.

TASK-0044: LINE ID トークン検証 + httpx 統一
対象テストケース: TC-01 ~ TC-06, TC-11 ~ TC-13
"""

import inspect
import os
import pytest
from unittest.mock import patch, MagicMock

from src.services.line_service import LineService, LineApiError


class TestVerifyIdToken:
    """TC-01〜TC-06: LineService.verify_id_token メソッドのテスト."""

    def test_verify_id_token_success(self):
        """TC-01: 有効な ID トークンを検証して line_user_id を抽出する.

        【テスト目的】: verify_id_token が LINE API を正しく呼び出し、
                      sub クレームから line_user_id を返すことを検証する
        【テスト内容】: httpx.post のモックで 200 レスポンスを返し、
                      sub フィールドの値が返却されることを確認する
        【期待される動作】: 検証済みの line_user_id が返される
        🔵 信頼性レベル: 青信号 - REQ-V2-022, REQ-V2-023 に基づく
        """
        # 【テストデータ準備】: LINE_CHANNEL_ID を設定し、LineService を初期化
        with patch.dict(os.environ, {"LINE_CHANNEL_ID": "test-channel-id"}):
            service = LineService(
                channel_access_token="test-token",
                channel_secret="test-secret",
            )

        # channel_id を直接設定（__init__ 変更後はこの方法で設定される）
        service.channel_id = "test-channel-id"

        # 【初期条件設定】: LINE API が 200 を返すモックレスポンスを準備
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "iss": "https://access.line.me",
            "sub": "U1234567890abcdef1234567890abcdef",
            "aud": "test-channel-id",
            "exp": 1234567890,
            "iat": 1234567890,
        }

        # 【実際の処理実行】: verify_id_token を呼び出し、結果と呼び出し引数を検証
        with patch("src.services.line_service.httpx.post", return_value=mock_response) as mock_post:
            # 【結果検証】: verify_id_token が実装されていないので AttributeError または NotImplementedError
            result = service.verify_id_token("valid-id-token")

            # 【期待値確認】: sub クレームの値が返却されることを確認
            assert result == "U1234567890abcdef1234567890abcdef"  # 【確認内容】: LINE User ID が正しく抽出される 🔵

            # 【確認内容】: httpx.post が正しい引数で呼ばれたことを確認
            mock_post.assert_called_once_with(
                "https://api.line.me/oauth2/v2.1/verify",
                data={
                    "id_token": "valid-id-token",
                    "client_id": "test-channel-id",
                },
                timeout=10,
            )

    def test_verify_id_token_failure_invalid_token(self):
        """TC-02: 無効な ID トークンで 400 が返ると UnauthorizedError が発生する.

        【テスト目的】: LINE API が 400 を返した場合に UnauthorizedError が発生することを検証
        【テスト内容】: httpx.post のモックで 400 レスポンスを返し、例外発生を確認
        【期待される動作】: UnauthorizedError または同等の例外が発生する
        🔵 信頼性レベル: 青信号 - REQ-V2-121, EDGE-V2-001 に基づく
        """
        # 【テストデータ準備】: LineService を初期化
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )
        service.channel_id = "test-channel-id"  # channel_id を設定

        # 【初期条件設定】: LINE API が 400 を返すモックレスポンスを準備
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_request",
            "error_description": "Invalid IdToken.",
        }

        # 【実際の処理実行】: verify_id_token を呼び出す
        with patch("src.services.line_service.httpx.post", return_value=mock_response):
            # 【結果検証】: 例外が発生することを確認
            with pytest.raises(Exception) as exc_info:
                service.verify_id_token("invalid-id-token")

            # 【期待値確認】: UnauthorizedError または検証失敗のエラーが発生
            error_name = type(exc_info.value).__name__.lower()
            error_msg = str(exc_info.value).lower()
            assert (
                "verification failed" in error_msg
                or "unauthorized" in error_name
                or "invalid" in error_msg
            ), f"Expected unauthorized/verification failed error, got: {exc_info.value}"  # 【確認内容】: 適切なエラー型で例外が発生する 🔵

    def test_verify_id_token_failure_expired_token(self):
        """TC-03: 期限切れ ID トークンで UnauthorizedError が発生する.

        【テスト目的】: 期限切れトークンに対して適切なエラーが発生することを検証
        【テスト内容】: LINE API が 400 を返した場合（期限切れを示す）の例外処理を確認
        【期待される動作】: UnauthorizedError または同等の例外が発生する
        🟡 信頼性レベル: 黄信号 - LINE API の具体的な期限切れレスポンスコードは実動作確認が必要
        """
        # 【テストデータ準備】: LineService を初期化
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )
        service.channel_id = "test-channel-id"

        # 【初期条件設定】: LINE API が 400 を返すモックレスポンスを準備（期限切れ）
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_request",
            "error_description": "IdToken expired.",
        }

        # 【実際の処理実行】: verify_id_token を呼び出す
        with patch("src.services.line_service.httpx.post", return_value=mock_response):
            # 【結果検証】: 例外が発生することを確認
            with pytest.raises(Exception) as exc_info:
                service.verify_id_token("expired-id-token")

            # 【期待値確認】: 非 200 ステータスで適切な例外が発生することを確認
            error_name = type(exc_info.value).__name__.lower()
            error_msg = str(exc_info.value).lower()
            assert (
                "verification failed" in error_msg
                or "unauthorized" in error_name
                or "invalid" in error_msg
            ), f"Expected unauthorized/verification failed error, got: {exc_info.value}"  # 【確認内容】: 期限切れトークンで適切なエラーが発生する 🟡

    def test_verify_id_token_failure_missing_sub_claim(self):
        """TC-04: LINE API が 200 を返すが sub クレームがない場合に UnauthorizedError が発生する.

        【テスト目的】: sub フィールド欠落時に適切なエラーが発生することを検証
        【テスト内容】: 200 レスポンスでも sub がない場合の例外処理を確認
        【期待される動作】: UnauthorizedError ("Invalid ID token format") が発生する
        🔵 信頼性レベル: 青信号 - REQ-V2-022 の sub クレーム検証要件に基づく
        """
        # 【テストデータ準備】: LineService を初期化
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )
        service.channel_id = "test-channel-id"

        # 【初期条件設定】: LINE API が 200 を返すが sub フィールドが欠落しているモックレスポンス
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "iss": "https://access.line.me",
            # "sub" は意図的に省略
            "aud": "test-channel-id",
            "exp": 1234567890,
            "iat": 1234567890,
        }

        # 【実際の処理実行】: verify_id_token を呼び出す
        with patch("src.services.line_service.httpx.post", return_value=mock_response):
            # 【結果検証】: sub 欠落で例外が発生することを確認
            with pytest.raises(Exception) as exc_info:
                service.verify_id_token("token-without-sub")

            # 【期待値確認】: "Invalid ID token format" または unauthorized のエラーが発生
            error_name = type(exc_info.value).__name__.lower()
            error_msg = str(exc_info.value).lower()
            assert (
                "invalid" in error_msg
                or "unauthorized" in error_name
                or "format" in error_msg
                or "sub" in error_msg
            ), f"Expected invalid token format error, got: {exc_info.value}"  # 【確認内容】: sub クレーム欠落で適切なエラーが発生する 🔵

    def test_verify_id_token_failure_channel_id_not_configured(self):
        """TC-05: LINE_CHANNEL_ID が未設定の場合に LineApiError が発生する.

        【テスト目的】: channel_id が None の場合に LineApiError が発生することを検証
        【テスト内容】: channel_id = None でメソッドを呼び出し、エラーメッセージを確認
        【期待される動作】: LineApiError("LINE_CHANNEL_ID not configured") が発生する
        🔵 信頼性レベル: 青信号 - note.md 3.4 の channel_id 未設定時のエラー仕様に基づく
        """
        # 【テストデータ準備】: channel_id を None に設定した LineService を初期化
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )
        service.channel_id = None  # 【初期条件設定】: 環境変数未設定をシミュレート

        # 【実際の処理実行】: verify_id_token を呼び出す
        # 【結果検証】: LineApiError が "LINE_CHANNEL_ID" メッセージで発生することを確認
        with pytest.raises(LineApiError, match="LINE_CHANNEL_ID"):
            service.verify_id_token("any-token")  # 【確認内容】: channel_id 未設定で LineApiError が発生する 🔵

    def test_verify_id_token_failure_network_error(self):
        """TC-06: ネットワーク障害時に LineApiError が発生する.

        【テスト目的】: httpx.RequestError が LineApiError にラップされることを検証
        【テスト内容】: httpx.post が例外を発生させた場合の LineApiError への変換を確認
        【期待される動作】: LineApiError("Failed to verify ID token: ...") が発生する
        🟡 信頼性レベル: 黄信号 - httpx の具体的な例外種別は実装時に確定
        """
        import httpx

        # 【テストデータ準備】: LineService を初期化
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )
        service.channel_id = "test-channel-id"  # 【初期条件設定】: channel_id を設定

        # 【実際の処理実行】: httpx.post がネットワークエラーを発生させるモックを設定
        with patch(
            "src.services.line_service.httpx.post",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            # 【結果検証】: LineApiError が発生することを確認
            with pytest.raises(LineApiError, match="Failed to verify ID token"):
                service.verify_id_token("valid-token")  # 【確認内容】: ネットワークエラーが LineApiError に変換される 🟡


class TestHttpxMigration:
    """TC-11〜TC-13: httpx 移行確認テスト（requests の除去と httpx への置換）."""

    def test_line_service_uses_httpx_not_requests(self):
        """TC-11: line_service.py が requests を import せず httpx を使用していることを確認する.

        【テスト目的】: HTTP クライアントが requests から httpx に移行されていることを静的検証
        【テスト内容】: line_service.py のソースコードを検査し、import の状態を確認する
        【期待される動作】: "import httpx" が存在し、"import requests" が存在しない
        🔵 信頼性レベル: 青信号 - REQ-V2-052, REQ-V2-402 に基づく
        """
        # 【テストデータ準備】: line_service モジュールのソースコードを取得
        import src.services.line_service as ls_module
        source = inspect.getsource(ls_module)  # 【初期条件設定】: ソースコードを読み込む

        # 【実際の処理実行】: ソースコード内の import 文を検査

        # 【結果検証】: httpx が import されていることを確認
        assert "import httpx" in source, (
            "line_service.py should import httpx (HTTP client must be unified to httpx)"
        )  # 【確認内容】: httpx の import 文が存在する 🔵

        # 【結果検証】: requests が import されていないことを確認
        assert "import requests" not in source, (
            "line_service.py should not import requests (remove requests dependency)"
        )  # 【確認内容】: requests の import 文が存在しない 🔵

    def test_reply_message_uses_httpx(self):
        """TC-12: reply_message が httpx.post を使用していることを確認する.

        【テスト目的】: reply_message メソッドが requests.post ではなく httpx.post を使用することを検証
        【テスト内容】: httpx.post をモックして呼び出しを確認する
        【期待される動作】: httpx.post が呼ばれ、True が返される
        🔵 信頼性レベル: 青信号 - REQ-V2-052 の reply_message 移行要件に基づく
        """
        # 【テストデータ準備】: LineService を初期化
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )

        # 【初期条件設定】: httpx.post のモックレスポンスを準備
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        # 【実際の処理実行】: httpx.post をモックして reply_message を呼び出す
        with patch("src.services.line_service.httpx.post", return_value=mock_response) as mock_post:
            result = service.reply_message(
                "reply-token",
                [{"type": "text", "text": "Hello"}],
            )

            # 【結果検証】: True が返却されることを確認
            assert result is True  # 【確認内容】: reply_message が正常に True を返す 🔵

            # 【確認内容】: httpx.post が呼ばれたことを確認（requests.post ではなく）
            mock_post.assert_called_once()  # 🔵

    def test_push_message_uses_httpx(self):
        """TC-13: push_message が httpx.post を使用していることを確認する.

        【テスト目的】: push_message メソッドが requests.post ではなく httpx.post を使用することを検証
        【テスト内容】: httpx.post をモックして呼び出しを確認する
        【期待される動作】: httpx.post が呼ばれ、True が返される
        🔵 信頼性レベル: 青信号 - REQ-V2-052 の push_message 移行要件に基づく
        """
        # 【テストデータ準備】: LineService を初期化
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )

        # 【初期条件設定】: httpx.post のモックレスポンスを準備
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        # 【実際の処理実行】: httpx.post をモックして push_message を呼び出す
        with patch("src.services.line_service.httpx.post", return_value=mock_response) as mock_post:
            result = service.push_message(
                "U1234567890",
                [{"type": "text", "text": "Hello"}],
            )

            # 【結果検証】: True が返却されることを確認
            assert result is True  # 【確認内容】: push_message が正常に True を返す 🔵

            # 【確認内容】: httpx.post が呼ばれたことを確認（requests.post ではなく）
            mock_post.assert_called_once()  # 🔵

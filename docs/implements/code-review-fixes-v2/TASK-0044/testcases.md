# TASK-0044 テストケース定義書: LINE ID トークン検証 + httpx 統一

**タスクID**: TASK-0044
**要件名**: code-review-fixes-v2
**作成日**: 2026-02-21
**タスクタイプ**: TDD (Test-Driven Development)

---

## テストケース一覧

| # | テストケース | カテゴリ | テストファイル | 信頼性 |
|---|-------------|---------|---------------|--------|
| TC-01 | verify_id_token 成功: 有効な ID トークン検証 | Backend Unit | `backend/tests/unit/test_line_service_verify.py` | :large_blue_circle: |
| TC-02 | verify_id_token 失敗: 無効なトークン (400) | Backend Unit | `backend/tests/unit/test_line_service_verify.py` | :large_blue_circle: |
| TC-03 | verify_id_token 失敗: 有効期限切れトークン (401) | Backend Unit | `backend/tests/unit/test_line_service_verify.py` | :yellow_circle: |
| TC-04 | verify_id_token 失敗: sub クレーム欠落 | Backend Unit | `backend/tests/unit/test_line_service_verify.py` | :large_blue_circle: |
| TC-05 | verify_id_token 失敗: LINE_CHANNEL_ID 未設定 | Backend Unit | `backend/tests/unit/test_line_service_verify.py` | :large_blue_circle: |
| TC-06 | verify_id_token 失敗: ネットワーク障害 (httpx.RequestError) | Backend Unit | `backend/tests/unit/test_line_service_verify.py` | :yellow_circle: |
| TC-07 | handler: id_token 未送信で 400 エラー | Backend Unit | `backend/tests/unit/test_handler_link_line.py` | :large_blue_circle: |
| TC-08 | handler: id_token 空文字で 400 エラー | Backend Unit | `backend/tests/unit/test_handler_link_line.py` | :large_blue_circle: |
| TC-09 | handler: ID トークン検証成功で LINE 連携完了 | Backend Unit | `backend/tests/unit/test_handler_link_line.py` | :large_blue_circle: |
| TC-10 | handler: ID トークン検証失敗で 401 エラー | Backend Unit | `backend/tests/unit/test_handler_link_line.py` | :large_blue_circle: |
| TC-11 | httpx 使用確認: requests が import されていない | Backend Unit | `backend/tests/unit/test_line_service_verify.py` | :large_blue_circle: |
| TC-12 | httpx 使用確認: reply_message が httpx を使用 | Backend Unit | `backend/tests/unit/test_line_service_verify.py` | :large_blue_circle: |
| TC-13 | httpx 使用確認: push_message が httpx を使用 | Backend Unit | `backend/tests/unit/test_line_service_verify.py` | :large_blue_circle: |
| TC-14 | Frontend: IDトークン送信 (id_token フィールド) | Frontend Unit | `frontend/src/pages/__tests__/LinkLinePage.idtoken.test.tsx` | :large_blue_circle: |
| TC-15 | Frontend: IDトークン取得失敗時のエラー表示 | Frontend Unit | `frontend/src/pages/__tests__/LinkLinePage.idtoken.test.tsx` | :yellow_circle: |
| TC-16 | Frontend: line_user_id ではなく id_token を使用 | Frontend Unit | `frontend/src/pages/__tests__/LinkLinePage.idtoken.test.tsx` | :large_blue_circle: |
| TC-17 | SAM Template: LineChannelId パラメータ存在確認 | Infra | `backend/tests/test_template_params.py` | :large_blue_circle: |
| TC-18 | SAM Template: LINE_CHANNEL_ID 環境変数存在確認 | Infra | `backend/tests/test_template_params.py` | :large_blue_circle: |

---

## TC-01: verify_id_token 成功 - 有効な ID トークン検証

**信頼性**: :large_blue_circle: *REQ-V2-022: サーバー側 LINE API による ID トークン検証*

**テストファイル**: `backend/tests/unit/test_line_service_verify.py`

### Given / When / Then

- **Given**: 有効な LIFF ID トークンと設定済みの LINE_CHANNEL_ID
- **When**: `line_service.verify_id_token("valid-id-token")` を呼び出す
- **Then**: LINE API が 200 を返し、`sub` フィールドから `line_user_id` が抽出される

### テスト実装

```python
import os
import pytest
from unittest.mock import patch, MagicMock

from src.services.line_service import LineService, LineApiError


class TestVerifyIdToken:
    """Tests for LineService.verify_id_token method."""

    def test_verify_id_token_success(self):
        """TC-01: Valid LIFF ID token is verified and line_user_id is extracted.

        Requirements:
            - REQ-V2-022: サーバー側で LINE API により ID トークンを検証
            - REQ-V2-023: 検証成功後の line_user_id でのみ連携確定

        Test Steps:
            1. LINE_CHANNEL_ID 環境変数を設定
            2. LineService を初期化（channel_id が設定される）
            3. httpx.post をモックして 200 レスポンスを返す
            4. verify_id_token を呼び出す
            5. 返却値が sub クレームの値であることを確認
            6. httpx.post の呼び出し引数が正しいことを確認
        """
        # Arrange
        with patch.dict(os.environ, {"LINE_CHANNEL_ID": "test-channel-id"}):
            service = LineService(
                channel_access_token="test-token",
                channel_secret="test-secret",
            )
            service.channel_id = "test-channel-id"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "iss": "https://access.line.me",
            "sub": "U1234567890abcdef1234567890abcdef",
            "aud": "test-channel-id",
            "exp": 1234567890,
            "iat": 1234567890,
        }

        # Act & Assert
        with patch("src.services.line_service.httpx.post", return_value=mock_response) as mock_post:
            result = service.verify_id_token("valid-id-token")

            assert result == "U1234567890abcdef1234567890abcdef"
            mock_post.assert_called_once_with(
                "https://api.line.me/oauth2/v2.1/verify",
                data={
                    "id_token": "valid-id-token",
                    "client_id": "test-channel-id",
                },
                timeout=10,
            )
```

---

## TC-02: verify_id_token 失敗 - 無効なトークン (400)

**信頼性**: :large_blue_circle: *REQ-V2-121: ID トークン検証失敗時に 401 を返却*

**テストファイル**: `backend/tests/unit/test_line_service_verify.py`

### Given / When / Then

- **Given**: 無効な ID トークン
- **When**: `line_service.verify_id_token("invalid-id-token")` を呼び出す
- **Then**: LINE API が 400 を返し、`UnauthorizedError` が発生する

### テスト実装

```python
    def test_verify_id_token_failure_invalid_token(self):
        """TC-02: Invalid ID token returns 400 and raises UnauthorizedError.

        Requirements:
            - REQ-V2-121: ID トークン検証失敗時に 401 を返却
            - EDGE-V2-001: 無効トークンの検出

        Test Steps:
            1. LineService を初期化
            2. httpx.post をモックして 400 レスポンスを返す
            3. verify_id_token を呼び出す
            4. UnauthorizedError が発生することを確認
        """
        # Arrange
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )
        service.channel_id = "test-channel-id"

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_request",
            "error_description": "Invalid IdToken.",
        }

        # Act & Assert
        with patch("src.services.line_service.httpx.post", return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                service.verify_id_token("invalid-id-token")

            # UnauthorizedError は aws_lambda_powertools から import される
            # または LineServiceError のサブクラスとして定義される
            assert "verification failed" in str(exc_info.value).lower() or \
                   "unauthorized" in type(exc_info.value).__name__.lower()
```

---

## TC-03: verify_id_token 失敗 - 有効期限切れトークン (401)

**信頼性**: :yellow_circle: *EDGE-V2-001: ID トークン有効期限切れ（LINE API の具体的なレスポンスコードは実動作確認が必要）*

**テストファイル**: `backend/tests/unit/test_line_service_verify.py`

### Given / When / Then

- **Given**: 有効期限切れの ID トークン
- **When**: `line_service.verify_id_token("expired-id-token")` を呼び出す
- **Then**: LINE API が 非200 ステータスを返し、`UnauthorizedError` が発生する

### テスト実装

```python
    def test_verify_id_token_failure_expired_token(self):
        """TC-03: Expired ID token raises UnauthorizedError.

        Requirements:
            - EDGE-V2-001: ID トークン有効期限切れ
            - REQ-V2-121: ID トークン検証失敗時のエラーハンドリング

        Note:
            LINE API は期限切れトークンに対して 400 を返す可能性がある。
            実装では 200 以外のすべてのステータスコードで UnauthorizedError を発生させる。

        Test Steps:
            1. LineService を初期化
            2. httpx.post をモックして 400 レスポンスを返す（expired token）
            3. verify_id_token を呼び出す
            4. UnauthorizedError が発生することを確認
        """
        # Arrange
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )
        service.channel_id = "test-channel-id"

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "error": "invalid_request",
            "error_description": "IdToken expired.",
        }

        # Act & Assert
        with patch("src.services.line_service.httpx.post", return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                service.verify_id_token("expired-id-token")

            assert "verification failed" in str(exc_info.value).lower() or \
                   "unauthorized" in type(exc_info.value).__name__.lower()
```

---

## TC-04: verify_id_token 失敗 - sub クレーム欠落

**信頼性**: :large_blue_circle: *REQ-V2-022: LINE API レスポンスの sub フィールド検証*

**テストファイル**: `backend/tests/unit/test_line_service_verify.py`

### Given / When / Then

- **Given**: LINE API が 200 を返すが `sub` フィールドが欠落したレスポンス
- **When**: `line_service.verify_id_token("token-without-sub")` を呼び出す
- **Then**: `UnauthorizedError` が発生する（"Invalid ID token format"）

### テスト実装

```python
    def test_verify_id_token_failure_missing_sub_claim(self):
        """TC-04: ID token response missing 'sub' claim raises UnauthorizedError.

        Requirements:
            - REQ-V2-022: sub クレームから line_user_id を抽出
            - note.md 3.4: sub がない場合 UnauthorizedError をスロー

        Test Steps:
            1. LineService を初期化
            2. httpx.post をモックして 200 レスポンスを返す（sub なし）
            3. verify_id_token を呼び出す
            4. UnauthorizedError が発生することを確認
        """
        # Arrange
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )
        service.channel_id = "test-channel-id"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "iss": "https://access.line.me",
            # "sub" is missing
            "aud": "test-channel-id",
            "exp": 1234567890,
            "iat": 1234567890,
        }

        # Act & Assert
        with patch("src.services.line_service.httpx.post", return_value=mock_response):
            with pytest.raises(Exception) as exc_info:
                service.verify_id_token("token-without-sub")

            assert "invalid" in str(exc_info.value).lower() or \
                   "unauthorized" in type(exc_info.value).__name__.lower()
```

---

## TC-05: verify_id_token 失敗 - LINE_CHANNEL_ID 未設定

**信頼性**: :large_blue_circle: *note.md 3.4: channel_id が None の場合 LineApiError をスロー*

**テストファイル**: `backend/tests/unit/test_line_service_verify.py`

### Given / When / Then

- **Given**: `LINE_CHANNEL_ID` 環境変数が設定されていない LineService インスタンス
- **When**: `line_service.verify_id_token("any-token")` を呼び出す
- **Then**: `LineApiError("LINE_CHANNEL_ID not configured")` が発生する

### テスト実装

```python
    def test_verify_id_token_failure_channel_id_not_configured(self):
        """TC-05: LINE_CHANNEL_ID not configured raises LineApiError.

        Requirements:
            - note.md 3.4: channel_id 未設定時の LineApiError
            - requirements.md 4.6: LINE_CHANNEL_ID 未設定エラー

        Test Steps:
            1. LineService を初期化（channel_id = None）
            2. verify_id_token を呼び出す
            3. LineApiError が発生することを確認
            4. エラーメッセージに "LINE_CHANNEL_ID" が含まれることを確認
        """
        # Arrange
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )
        service.channel_id = None  # 環境変数未設定をシミュレート

        # Act & Assert
        with pytest.raises(LineApiError, match="LINE_CHANNEL_ID"):
            service.verify_id_token("any-token")
```

---

## TC-06: verify_id_token 失敗 - ネットワーク障害

**信頼性**: :yellow_circle: *requirements.md 4.7: LINE API 通信障害時の動作*

**テストファイル**: `backend/tests/unit/test_line_service_verify.py`

### Given / When / Then

- **Given**: LINE API への通信がタイムアウトまたは接続エラー
- **When**: `line_service.verify_id_token("valid-token")` を呼び出す
- **Then**: `LineApiError` が発生する（httpx.RequestError をラップ）

### テスト実装

```python
    def test_verify_id_token_failure_network_error(self):
        """TC-06: Network error during verification raises LineApiError.

        Requirements:
            - requirements.md 4.7: LINE API 通信障害時の動作
            - note.md 3.4: httpx.RequestError のハンドリング

        Test Steps:
            1. LineService を初期化
            2. httpx.post をモックして httpx.RequestError を発生させる
            3. verify_id_token を呼び出す
            4. LineApiError が発生することを確認
        """
        import httpx

        # Arrange
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )
        service.channel_id = "test-channel-id"

        # Act & Assert
        with patch(
            "src.services.line_service.httpx.post",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            with pytest.raises(LineApiError, match="Failed to verify ID token"):
                service.verify_id_token("valid-token")
```

---

## TC-07: handler - id_token 未送信で 400 エラー

**信頼性**: :large_blue_circle: *REQ-V2-021: id_token の必須バリデーション*

**テストファイル**: `backend/tests/unit/test_handler_link_line.py`

### Given / When / Then

- **Given**: リクエストボディに `id_token` フィールドがない（`{}`）
- **When**: `POST /users/link-line` にリクエストを送信する
- **Then**: 400 ステータスコードと `"id_token is required"` エラーメッセージが返る

### テスト実装

```python
import json
import pytest
from unittest.mock import patch, MagicMock


class TestLinkLineHandler:
    """Tests for link_line_account handler with ID token verification."""

    def test_link_line_missing_id_token(self, api_gateway_event, lambda_context):
        """TC-07: Missing id_token in request body returns 400 error.

        Requirements:
            - REQ-V2-021: id_token フィールドの必須チェック
            - requirements.md 4.5: id_token 未送信時の 400 エラー

        Test Steps:
            1. リクエストボディに id_token なしのイベントを作成
            2. handler を呼び出す
            3. 400 ステータスコードが返却されることを確認
            4. エラーメッセージに "id_token" が含まれることを確認
        """
        # Arrange
        event = api_gateway_event(
            method="POST",
            path="/users/link-line",
            body={},  # id_token フィールドなし
        )

        # Act
        with patch("src.api.handler.user_service") as mock_user_service, \
             patch("src.api.handler.line_service") as mock_line_service:
            mock_user_service.get_or_create_user.return_value = MagicMock()

            from src.api.handler import handler
            response = handler(event, lambda_context)

        # Assert
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "id_token" in body.get("error", "").lower() or \
               "id_token" in json.dumps(body).lower()
```

---

## TC-08: handler - id_token 空文字で 400 エラー

**信頼性**: :large_blue_circle: *REQ-V2-021: id_token の空文字バリデーション*

**テストファイル**: `backend/tests/unit/test_handler_link_line.py`

### Given / When / Then

- **Given**: リクエストボディの `id_token` が空文字（`{"id_token": ""}`）
- **When**: `POST /users/link-line` にリクエストを送信する
- **Then**: 400 ステータスコードが返る

### テスト実装

```python
    def test_link_line_empty_id_token(self, api_gateway_event, lambda_context):
        """TC-08: Empty id_token in request body returns 400 error.

        Requirements:
            - REQ-V2-021: id_token の空文字バリデーション
            - requirements.md 2.4: min_length=1 制約

        Test Steps:
            1. リクエストボディに空の id_token を持つイベントを作成
            2. handler を呼び出す
            3. 400 ステータスコードが返却されることを確認
        """
        # Arrange
        event = api_gateway_event(
            method="POST",
            path="/users/link-line",
            body={"id_token": ""},  # 空文字
        )

        # Act
        with patch("src.api.handler.user_service") as mock_user_service, \
             patch("src.api.handler.line_service") as mock_line_service:
            mock_user_service.get_or_create_user.return_value = MagicMock()

            from src.api.handler import handler
            response = handler(event, lambda_context)

        # Assert
        assert response["statusCode"] == 400
```

---

## TC-09: handler - ID トークン検証成功で LINE 連携完了

**信頼性**: :large_blue_circle: *REQ-V2-023: 検証成功後に取得した line_user_id でのみ連携確定*

**テストファイル**: `backend/tests/unit/test_handler_link_line.py`

### Given / When / Then

- **Given**: 有効な `id_token` を含むリクエスト
- **When**: `POST /users/link-line` にリクエストを送信する
- **Then**: `line_service.verify_id_token` が呼ばれ、返却された `line_user_id` で `user_service.link_line` が実行される

### テスト実装

```python
    def test_link_line_success_with_id_token(self, api_gateway_event, lambda_context):
        """TC-09: Valid id_token is verified and LINE account is linked.

        Requirements:
            - REQ-V2-022: サーバー側で LINE API により ID トークンを検証
            - REQ-V2-023: 検証成功後の line_user_id でのみ連携確定

        Test Steps:
            1. 有効な id_token を含むイベントを作成
            2. line_service.verify_id_token をモックして line_user_id を返す
            3. handler を呼び出す
            4. verify_id_token が正しい id_token で呼ばれたことを確認
            5. user_service.link_line が検証済み line_user_id で呼ばれたことを確認
            6. 成功レスポンスが返却されることを確認
        """
        # Arrange
        event = api_gateway_event(
            method="POST",
            path="/users/link-line",
            body={"id_token": "valid-liff-id-token"},
        )

        # Act
        with patch("src.api.handler.user_service") as mock_user_service, \
             patch("src.api.handler.line_service") as mock_line_service:
            mock_user_service.get_or_create_user.return_value = MagicMock()
            mock_line_service.verify_id_token.return_value = "U1234567890abcdef1234567890abcdef"

            from src.api.handler import handler
            response = handler(event, lambda_context)

        # Assert
        assert response["statusCode"] == 200
        mock_line_service.verify_id_token.assert_called_once_with("valid-liff-id-token")
        mock_user_service.link_line.assert_called_once_with(
            "test-user-id",
            "U1234567890abcdef1234567890abcdef",
        )
```

---

## TC-10: handler - ID トークン検証失敗で 401 エラー

**信頼性**: :large_blue_circle: *REQ-V2-121: ID トークン検証失敗時に 401 を返却*

**テストファイル**: `backend/tests/unit/test_handler_link_line.py`

### Given / When / Then

- **Given**: 無効な `id_token` を含むリクエスト（`verify_id_token` が `UnauthorizedError` をスロー）
- **When**: `POST /users/link-line` にリクエストを送信する
- **Then**: 401 ステータスコードと検証失敗エラーメッセージが返る

### テスト実装

```python
    def test_link_line_unauthorized_on_verification_failure(self, api_gateway_event, lambda_context):
        """TC-10: ID token verification failure returns 401 error.

        Requirements:
            - REQ-V2-121: ID トークン検証失敗時に 401 を返却
            - requirements.md 2.6: 401 エラーレスポンス

        Test Steps:
            1. id_token を含むイベントを作成
            2. line_service.verify_id_token をモックして UnauthorizedError を発生させる
            3. handler を呼び出す
            4. 401 ステータスコードが返却されることを確認
            5. エラーメッセージに "verification failed" が含まれることを確認
        """
        from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

        # Arrange
        event = api_gateway_event(
            method="POST",
            path="/users/link-line",
            body={"id_token": "invalid-token"},
        )

        # Act
        with patch("src.api.handler.user_service") as mock_user_service, \
             patch("src.api.handler.line_service") as mock_line_service:
            mock_user_service.get_or_create_user.return_value = MagicMock()
            mock_line_service.verify_id_token.side_effect = UnauthorizedError(
                "LINE ID token verification failed"
            )

            from src.api.handler import handler
            response = handler(event, lambda_context)

        # Assert
        assert response["statusCode"] == 401
        body = json.loads(response["body"])
        assert "verification failed" in body.get("error", "").lower() or \
               "unauthorized" in json.dumps(body).lower()
```

---

## TC-11: httpx 使用確認 - requests が import されていない

**信頼性**: :large_blue_circle: *REQ-V2-052: HTTP クライアントを httpx に統一*

**テストファイル**: `backend/tests/unit/test_line_service_verify.py`

### Given / When / Then

- **Given**: `line_service.py` モジュール
- **When**: モジュールの import 状態を検査する
- **Then**: `httpx` が import されており、`requests` が import されていない

### テスト実装

```python
class TestHttpxMigration:
    """Tests for httpx migration (requests removal)."""

    def test_line_service_uses_httpx_not_requests(self):
        """TC-11: LineService uses httpx instead of requests.

        Requirements:
            - REQ-V2-052: HTTP クライアントを httpx に統一
            - REQ-V2-402: HTTP ライブラリは httpx に統一

        Test Steps:
            1. line_service モジュールを import
            2. httpx が import されていることを確認
            3. requests が import されていないことを確認
        """
        # Arrange & Act
        import src.services.line_service as ls_module
        import inspect
        source = inspect.getsource(ls_module)

        # Assert
        assert "import httpx" in source, "line_service.py should import httpx"
        assert "import requests" not in source, \
            "line_service.py should not import requests"
```

---

## TC-12: httpx 使用確認 - reply_message が httpx を使用

**信頼性**: :large_blue_circle: *REQ-V2-052: reply_message メソッドの httpx 移行*

**テストファイル**: `backend/tests/unit/test_line_service_verify.py`

### Given / When / Then

- **Given**: `LineService` インスタンス
- **When**: `reply_message` を呼び出す
- **Then**: `httpx.post` が使用される（`requests.post` ではない）

### テスト実装

```python
    def test_reply_message_uses_httpx(self):
        """TC-12: reply_message uses httpx.post instead of requests.post.

        Requirements:
            - REQ-V2-052: HTTP クライアントを httpx に統一
            - requirements.md 8.1: reply_message の置換

        Test Steps:
            1. LineService を初期化
            2. httpx.post をモックする
            3. reply_message を呼び出す
            4. httpx.post が呼ばれたことを確認
        """
        # Arrange
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        # Act & Assert
        with patch("src.services.line_service.httpx.post", return_value=mock_response) as mock_post:
            result = service.reply_message(
                "reply-token",
                [{"type": "text", "text": "Hello"}],
            )

            assert result is True
            mock_post.assert_called_once()
```

---

## TC-13: httpx 使用確認 - push_message が httpx を使用

**信頼性**: :large_blue_circle: *REQ-V2-052: push_message メソッドの httpx 移行*

**テストファイル**: `backend/tests/unit/test_line_service_verify.py`

### Given / When / Then

- **Given**: `LineService` インスタンス
- **When**: `push_message` を呼び出す
- **Then**: `httpx.post` が使用される（`requests.post` ではない）

### テスト実装

```python
    def test_push_message_uses_httpx(self):
        """TC-13: push_message uses httpx.post instead of requests.post.

        Requirements:
            - REQ-V2-052: HTTP クライアントを httpx に統一
            - requirements.md 8.1: push_message の置換

        Test Steps:
            1. LineService を初期化
            2. httpx.post をモックする
            3. push_message を呼び出す
            4. httpx.post が呼ばれたことを確認
        """
        # Arrange
        service = LineService(
            channel_access_token="test-token",
            channel_secret="test-secret",
        )

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        # Act & Assert
        with patch("src.services.line_service.httpx.post", return_value=mock_response) as mock_post:
            result = service.push_message(
                "U1234567890",
                [{"type": "text", "text": "Hello"}],
            )

            assert result is True
            mock_post.assert_called_once()
```

---

## TC-14: Frontend - IDトークン送信 (id_token フィールド)

**信頼性**: :large_blue_circle: *REQ-V2-021: フロントエンドが LIFF IDトークンを送信*

**テストファイル**: `frontend/src/pages/__tests__/LinkLinePage.idtoken.test.tsx`

### Given / When / Then

- **Given**: LIFF SDK 初期化済みで `liff.getIDToken()` が有効なトークンを返す
- **When**: LINE連携ボタンを押下する
- **Then**: `usersApi.linkLine()` に `{ id_token: "test-id-token" }` が渡される

### テスト実装

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { LinkLinePage } from '../LinkLinePage';
import type { User } from '@/types';

// Navigation mock
vi.mock('@/components/Navigation', () => ({
  Navigation: () => <nav data-testid="navigation">Navigation</nav>,
}));

// usersApi mock
const mockGetCurrentUser = vi.fn();
const mockUpdateUser = vi.fn();
const mockLinkLine = vi.fn();

vi.mock('@/services/api', () => ({
  usersApi: {
    getCurrentUser: () => mockGetCurrentUser(),
    updateUser: (...args: unknown[]) => mockUpdateUser(...args),
    linkLine: (...args: unknown[]) => mockLinkLine(...args),
  },
}));

// liff mock - getLiffIdToken を追加
const mockInitializeLiff = vi.fn();
const mockGetLiffProfile = vi.fn();
const mockIsInLiffClient = vi.fn();
const mockGetLiffIdToken = vi.fn();

vi.mock('@/services/liff', () => ({
  initializeLiff: () => mockInitializeLiff(),
  getLiffProfile: () => mockGetLiffProfile(),
  isInLiffClient: () => mockIsInLiffClient(),
  getLiffIdToken: () => mockGetLiffIdToken(),
}));

// useNavigate mock
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockUnlinkedUser: User = {
  user_id: 'user-1',
  display_name: 'Test User',
  picture_url: null,
  line_linked: false,
  notification_time: '09:00',
  timezone: 'Asia/Tokyo',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};

const mockLinkedUser: User = {
  ...mockUnlinkedUser,
  line_linked: true,
};

const renderLinkLinePage = () => {
  return render(
    <MemoryRouter>
      <LinkLinePage />
    </MemoryRouter>
  );
};

describe('LinkLinePage - ID Token Tests (TASK-0044)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetCurrentUser.mockResolvedValue(mockUnlinkedUser);
    mockLinkLine.mockResolvedValue(mockLinkedUser);
    mockInitializeLiff.mockResolvedValue(undefined);
    mockIsInLiffClient.mockReturnValue(true);
    mockGetLiffIdToken.mockReturnValue('test-liff-id-token-xyz');
  });

  it('TC-14: LINE連携ボタン押下時に id_token が送信される', async () => {
    /**
     * Requirements:
     *   - REQ-V2-021: フロントエンドが LIFF IDトークンを送信
     *
     * Test Steps:
     *   1. mockGetLiffIdToken が有効なトークンを返すよう設定
     *   2. LinkLinePage をレンダリング
     *   3. 連携ボタンをクリック
     *   4. mockLinkLine が { id_token: "test-liff-id-token-xyz" } で呼ばれることを確認
     */
    // Arrange
    const user = userEvent.setup();

    // Act
    renderLinkLinePage();
    await waitFor(() => {
      expect(screen.getByTestId('link-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('link-button'));

    // Assert
    await waitFor(() => {
      expect(mockLinkLine).toHaveBeenCalledWith({
        id_token: 'test-liff-id-token-xyz',
      });
    });
  });
```

---

## TC-15: Frontend - IDトークン取得失敗時のエラー表示

**信頼性**: :yellow_circle: *requirements.md 4.2: IDトークン取得失敗時のUIエラーメッセージ（文言は推測）*

**テストファイル**: `frontend/src/pages/__tests__/LinkLinePage.idtoken.test.tsx`

### Given / When / Then

- **Given**: `liff.getIDToken()` が `null` を返す
- **When**: LINE連携ボタンを押下する
- **Then**: エラーメッセージが表示される

### テスト実装

```typescript
  it('TC-15: IDトークン取得失敗時にエラーメッセージが表示される', async () => {
    /**
     * Requirements:
     *   - REQ-V2-021: IDトークン取得失敗時のエラーハンドリング
     *   - requirements.md 4.2: エラーメッセージ表示
     *
     * Test Steps:
     *   1. mockGetLiffIdToken が null を返すよう設定
     *   2. LinkLinePage をレンダリング
     *   3. 連携ボタンをクリック
     *   4. エラーメッセージが表示されることを確認
     *   5. linkLine API が呼ばれていないことを確認
     */
    // Arrange
    mockGetLiffIdToken.mockReturnValue(null);
    const user = userEvent.setup();

    // Act
    renderLinkLinePage();
    await waitFor(() => {
      expect(screen.getByTestId('link-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('link-button'));

    // Assert
    await waitFor(() => {
      const errorMessage = screen.getByTestId('error-message');
      expect(errorMessage).toBeInTheDocument();
      // エラーメッセージはLINE関連のエラーであることを確認
      // 具体的な文言は実装時に確定（"LINEの認証情報を取得できませんでした" または類似メッセージ）
      expect(errorMessage.textContent).toBeTruthy();
    });

    // linkLine API は呼ばれないことを確認
    expect(mockLinkLine).not.toHaveBeenCalled();
  });
```

---

## TC-16: Frontend - line_user_id ではなく id_token を使用

**信頼性**: :large_blue_circle: *REQ-V2-021: line_user_id の直接送信を廃止*

**テストファイル**: `frontend/src/pages/__tests__/LinkLinePage.idtoken.test.tsx`

### Given / When / Then

- **Given**: LIFF SDK 初期化済みで ID トークン取得可能
- **When**: LINE連携ボタンを押下する
- **Then**: `linkLine` に `line_user_id` フィールドが含まれていない

### テスト実装

```typescript
  it('TC-16: linkLine に line_user_id ではなく id_token が使用される', async () => {
    /**
     * Requirements:
     *   - REQ-V2-021: line_user_id の直接送信廃止
     *   - note.md 3.1: liff.getProfile() → liff.getIDToken() への変更
     *
     * Test Steps:
     *   1. 連携ボタンをクリック
     *   2. mockLinkLine の呼び出し引数を確認
     *   3. id_token フィールドが存在することを確認
     *   4. line_user_id フィールドが存在しないことを確認
     */
    // Arrange
    const user = userEvent.setup();

    // Act
    renderLinkLinePage();
    await waitFor(() => {
      expect(screen.getByTestId('link-button')).toBeInTheDocument();
    });
    await user.click(screen.getByTestId('link-button'));

    // Assert
    await waitFor(() => {
      expect(mockLinkLine).toHaveBeenCalled();
      const callArgs = mockLinkLine.mock.calls[0][0];
      expect(callArgs).toHaveProperty('id_token');
      expect(callArgs).not.toHaveProperty('line_user_id');
    });
  });
});
```

---

## TC-17: SAM Template - LineChannelId パラメータ存在確認

**信頼性**: :large_blue_circle: *note.md 3.6: SAM テンプレートに LineChannelId パラメータ定義*

**テストファイル**: `backend/tests/test_template_params.py`

### Given / When / Then

- **Given**: `backend/template.yaml` ファイル
- **When**: Parameters セクションを解析する
- **Then**: `LineChannelId` パラメータが定義されている

### テスト実装

```python
import yaml
import os
import pytest


class TestSAMTemplateLineChannelId:
    """Tests for LINE_CHANNEL_ID in SAM template."""

    @pytest.fixture
    def template(self):
        """Load SAM template."""
        template_path = os.path.join(
            os.path.dirname(__file__), "..", "template.yaml"
        )
        with open(template_path, "r") as f:
            return yaml.safe_load(f)

    def test_line_channel_id_parameter_exists(self, template):
        """TC-17: SAM template has LineChannelId parameter.

        Requirements:
            - note.md 3.6: LineChannelId パラメータの定義
            - requirements.md 3.6: SAM テンプレート制約

        Test Steps:
            1. template.yaml を読み込む
            2. Parameters セクションに LineChannelId が存在することを確認
            3. Type が String であることを確認
        """
        # Assert
        assert "Parameters" in template, "template.yaml should have Parameters section"
        params = template["Parameters"]
        assert "LineChannelId" in params, \
            "template.yaml should have LineChannelId parameter"
        assert params["LineChannelId"]["Type"] == "String", \
            "LineChannelId should be of type String"
```

---

## TC-18: SAM Template - LINE_CHANNEL_ID 環境変数存在確認

**信頼性**: :large_blue_circle: *note.md 3.6: ApiFunction の環境変数に LINE_CHANNEL_ID を設定*

**テストファイル**: `backend/tests/test_template_params.py`

### Given / When / Then

- **Given**: `backend/template.yaml` ファイル
- **When**: ApiFunction の環境変数を解析する
- **Then**: `LINE_CHANNEL_ID` 環境変数が `!Ref LineChannelId` で設定されている

### テスト実装

```python
    def test_line_channel_id_env_var_in_globals_or_api_function(self, template):
        """TC-18: SAM template has LINE_CHANNEL_ID environment variable.

        Requirements:
            - note.md 3.6: LINE_CHANNEL_ID 環境変数の設定
            - requirements.md 3.6: SAM テンプレート制約

        Test Steps:
            1. template.yaml を読み込む
            2. Globals または ApiFunction の環境変数に
               LINE_CHANNEL_ID が存在することを確認
        """
        # Check Globals section
        globals_env = (
            template.get("Globals", {})
            .get("Function", {})
            .get("Environment", {})
            .get("Variables", {})
        )

        # Check ApiFunction section
        api_function_env = (
            template.get("Resources", {})
            .get("ApiFunction", {})
            .get("Properties", {})
            .get("Environment", {})
            .get("Variables", {})
        )

        has_line_channel_id = (
            "LINE_CHANNEL_ID" in globals_env or
            "LINE_CHANNEL_ID" in api_function_env
        )

        assert has_line_channel_id, \
            "LINE_CHANNEL_ID should be defined in Globals or ApiFunction environment variables"
```

---

## テスト実行計画

### バックエンドテスト

```bash
cd /Volumes/external/dev/memoru-liff/backend

# TC-01 ~ TC-06, TC-11 ~ TC-13: verify_id_token + httpx 移行テスト
pytest tests/unit/test_line_service_verify.py -v

# TC-07 ~ TC-10: handler テスト
pytest tests/unit/test_handler_link_line.py -v

# TC-17 ~ TC-18: SAM テンプレートテスト
pytest tests/test_template_params.py -v

# 全テスト実行
pytest tests/ -v --cov=src
```

### フロントエンドテスト

```bash
cd /Volumes/external/dev/memoru-liff/frontend

# TC-14 ~ TC-16: LinkLinePage IDトークンテスト
npx vitest run src/pages/__tests__/LinkLinePage.idtoken.test.tsx

# 全テスト実行
npm run test
```

---

## テストカバレッジ目標

| 対象ファイル | 目標カバレッジ | 主なテストケース |
|-------------|---------------|----------------|
| `backend/src/services/line_service.py` | >= 80% | TC-01 ~ TC-06, TC-11 ~ TC-13 |
| `backend/src/api/handler.py` (link_line) | >= 80% | TC-07 ~ TC-10 |
| `frontend/src/pages/LinkLinePage.tsx` | >= 80% | TC-14 ~ TC-16 |
| `backend/template.yaml` | N/A (構造検証) | TC-17 ~ TC-18 |

---

## 既存テストへの影響

### 変更が必要な既存テスト

| テストファイル | テストケース | 変更内容 |
|---------------|-------------|---------|
| `backend/tests/unit/test_line_service.py` | `test_reply_message_success` | `requests.post` mock → `httpx.post` mock |
| `backend/tests/unit/test_line_service.py` | `test_push_message_success` | `requests.post` mock → `httpx.post` mock |
| `frontend/src/pages/__tests__/LinkLinePage.test.tsx` | テストケース3 | `{ line_user_id: '...' }` → `{ id_token: '...' }` |

### 既存テストの mock パスの変更

**変更前**:
```python
@patch("src.services.line_service.requests.post")
```

**変更後**:
```python
@patch("src.services.line_service.httpx.post")
```

---

## EARS要件・設計文書との対応表

| テストケース | EARS要件 | 設計文書参照 |
|-------------|---------|-------------|
| TC-01 | REQ-V2-022, REQ-V2-023 | architecture.md 2.1 |
| TC-02 | REQ-V2-121, EDGE-V2-001 | api-endpoints.md |
| TC-03 | EDGE-V2-001 | note.md 7.1 |
| TC-04 | REQ-V2-022 | note.md 3.4 |
| TC-05 | note.md 3.4 | requirements.md 4.6 |
| TC-06 | requirements.md 4.7 | note.md 3.4 |
| TC-07 | REQ-V2-021 | api-endpoints.md |
| TC-08 | REQ-V2-021 | requirements.md 2.4 |
| TC-09 | REQ-V2-022, REQ-V2-023 | architecture.md 2.1 |
| TC-10 | REQ-V2-121 | api-endpoints.md |
| TC-11 | REQ-V2-052, REQ-V2-402 | architecture.md 2.5 |
| TC-12 | REQ-V2-052 | requirements.md 8.1 |
| TC-13 | REQ-V2-052 | requirements.md 8.1 |
| TC-14 | REQ-V2-021 | architecture.md 2.1 |
| TC-15 | REQ-V2-021 | requirements.md 4.2 |
| TC-16 | REQ-V2-021 | note.md 3.1 |
| TC-17 | note.md 3.6 | requirements.md 3.6 |
| TC-18 | note.md 3.6 | requirements.md 3.6 |

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| :large_blue_circle: 青信号 | 15 | 83% |
| :yellow_circle: 黄信号 | 3 | 17% |
| :red_circle: 赤信号 | 0 | 0% |

### 黄信号項目の詳細

| テストケース | 理由 |
|-------------|------|
| TC-03 | LINE API が期限切れトークンに対して返すステータスコード（400 vs 401）は実動作確認が必要 |
| TC-06 | httpx の例外種別（ConnectError vs TimeoutException）は実装時に確定 |
| TC-15 | IDトークン取得失敗時のUIエラーメッセージ文言は設計文書に明確な定義なし |

---

**品質評価**: 高品質 - 18テストケースで全変更箇所をカバー

**最終更新**: 2026-02-21

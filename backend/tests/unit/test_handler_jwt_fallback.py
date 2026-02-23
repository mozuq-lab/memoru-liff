"""Unit tests for get_user_id_from_context() JWT fallback functionality."""

import base64
import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from aws_lambda_powertools.event_handler.exceptions import UnauthorizedError

from api.handler import get_user_id_from_context, app


# =============================================================================
# テストユーティリティ
# =============================================================================


def make_jwt(payload: dict) -> str:
    """テスト用 JWT トークンを生成する（署名なし）.

    Args:
        payload: JWT ペイロードとして使用する dict

    Returns:
        "header.payload.fake_signature" 形式の JWT 文字列
    """
    header = {"alg": "RS256", "typ": "JWT"}
    h = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{h}.{p}.fake_signature"


# =============================================================================
# TestGetUserIdFromContext
# =============================================================================


class TestGetUserIdFromContext:
    """get_user_id_from_context() の dev 環境 JWT フォールバック機能テスト."""

    # -------------------------------------------------------------------------
    # フィクスチャ
    # -------------------------------------------------------------------------

    @pytest.fixture
    def mock_event_ctx(self):
        """app.current_event をモックに差し替えるコンテキストマネージャを返す fixture.

        使用例:
            with mock_event_ctx(mock_event):
                result = get_user_id_from_context()
        """
        def _patch(mock_event):
            return _MockAppContext(mock_event)

        return _patch

    # -------------------------------------------------------------------------
    # 正常系
    # -------------------------------------------------------------------------

    def test_dev_env_valid_jwt_returns_sub(self, monkeypatch, mock_event_ctx):
        """TC-01: dev環境 + 有効なJWT → sub返却.

        【テスト目的】: ENVIRONMENT=dev で JWT フォールバックが正常に動作することを検証する
        【テスト内容】: authorizer context なし + 有効な JWT ヘッダーで get_user_id_from_context() を呼び出す
        【期待される動作】: JWT ペイロードの sub クレームがユーザーIDとして返る
        🔵 信頼性レベル: 青信号 - REQ-LD-061, REQ-LD-062, handler.py L84-95 より
        """
        monkeypatch.setenv("ENVIRONMENT", "dev")

        token = make_jwt({"sub": "test-user-123", "iss": "https://keycloak:8180/realms/memoru"})
        mock_event = _make_event(authorizer=None, auth_header=f"Bearer {token}")

        with mock_event_ctx(mock_event):
            result = get_user_id_from_context()

        assert result == "test-user-123"  # 🔵 JWT ペイロードの sub が正確に返る

    def test_authorizer_context_returns_sub(self, mock_event_ctx):
        """TC-02: authorizer context あり → authorizer context の sub を使用.

        【テスト目的】: authorizer context が利用可能な場合、フォールバック不使用で sub が返ることを検証する
        【テスト内容】: authorizer context に jwt.claims.sub を設定し get_user_id_from_context() を呼び出す
        【期待される動作】: authorizer context の sub が返り、JWT フォールバックは使用されない
        🔵 信頼性レベル: 青信号 - REQ-LD-101, TC-LD-061-02 より
        """
        authorizer = {"jwt": {"claims": {"sub": "authorizer-user-456"}}}
        mock_event = _make_event(authorizer=authorizer)

        with mock_event_ctx(mock_event):
            result = get_user_id_from_context()

        assert result == "authorizer-user-456"  # 🔵 authorizer context から sub が取得される
        mock_event.get_header_value.assert_not_called()  # 🔵 JWT フォールバックは使用されない

    def test_authorizer_takes_priority_over_jwt(self, monkeypatch, mock_event_ctx):
        """TC-09: authorizer context あり + JWT ヘッダーあり → authorizer context を優先.

        【テスト目的】: 両方のソースが存在する場合、authorizer context が優先されることを検証する
        【テスト内容】: authorizer context と JWT ヘッダーに異なる sub を設定し、どちらが返るかを確認する
        【期待される動作】: authorizer context の sub が返り、JWT ヘッダーの sub は無視される
        🔵 信頼性レベル: 青信号 - REQ-LD-101 より
        """
        monkeypatch.setenv("ENVIRONMENT", "dev")

        token = make_jwt({"sub": "header-user"})
        authorizer = {"jwt": {"claims": {"sub": "authorizer-user"}}}
        mock_event = _make_event(authorizer=authorizer, auth_header=f"Bearer {token}")

        with mock_event_ctx(mock_event):
            result = get_user_id_from_context()

        assert result == "authorizer-user"  # 🔵 authorizer context が優先される

    # -------------------------------------------------------------------------
    # 異常系（セキュリティ境界）
    # -------------------------------------------------------------------------

    def test_prod_env_jwt_fallback_disabled(self, monkeypatch, mock_event_ctx):
        """TC-03: ENVIRONMENT=prod + JWTヘッダーあり → UnauthorizedError（フォールバック無効）.

        【テスト目的】: 本番環境では JWT フォールバックが無効であることを検証する
        【テスト内容】: ENVIRONMENT=prod で有効な JWT ヘッダーを送信し、UnauthorizedError を確認する
        【期待される動作】: フォールバックコードパスに入らず UnauthorizedError が発生する
        🔵 信頼性レベル: 青信号 - REQ-LD-063, NFR-LD-101, TC-LD-061-B01 より
        """
        monkeypatch.setenv("ENVIRONMENT", "prod")

        token = make_jwt({"sub": "test-user-123"})
        mock_event = _make_event(authorizer=None, auth_header=f"Bearer {token}")

        with mock_event_ctx(mock_event):
            with pytest.raises(UnauthorizedError):  # 🔵 本番環境ではフォールバック不使用
                get_user_id_from_context()

    def test_no_env_jwt_fallback_disabled(self, monkeypatch, mock_event_ctx):
        """TC-04: ENVIRONMENT未設定 + JWTヘッダーあり → UnauthorizedError.

        【テスト目的】: ENVIRONMENT 環境変数が未設定の場合、フォールバックが無効であることを検証する
        【テスト内容】: ENVIRONMENT を削除し、有効な JWT ヘッダーで UnauthorizedError を確認する
        【期待される動作】: fail-safe でフォールバック無効、UnauthorizedError が発生する
        🔵 信頼性レベル: 青信号 - handler.py L87 条件分岐より
        """
        monkeypatch.delenv("ENVIRONMENT", raising=False)

        token = make_jwt({"sub": "test-user-123"})
        mock_event = _make_event(authorizer=None, auth_header=f"Bearer {token}")

        with mock_event_ctx(mock_event):
            with pytest.raises(UnauthorizedError):  # 🔵 ENVIRONMENT 未設定はフォールバック無効
                get_user_id_from_context()

    # -------------------------------------------------------------------------
    # 異常系（dev 環境フォールバック失敗）
    # -------------------------------------------------------------------------

    def test_dev_env_no_auth_header(self, monkeypatch, mock_event_ctx):
        """TC-05: dev環境 + Authorizationヘッダーなし → UnauthorizedError.

        【テスト目的】: Authorization ヘッダーがない場合に UnauthorizedError が発生することを検証する
        【テスト内容】: ENVIRONMENT=dev で Authorization ヘッダーなしの状態を再現する
        【期待される動作】: JWT フォールバックコードパスに入るが、ヘッダーなしで失敗する
        🟡 信頼性レベル: 黄信号 - TC-LD-061-E01, handler.py L89-90 より
        """
        monkeypatch.setenv("ENVIRONMENT", "dev")

        mock_event = _make_event(authorizer=None, auth_header=None)

        with mock_event_ctx(mock_event):
            with pytest.raises(UnauthorizedError):  # 🟡 Authorization ヘッダーなしは失敗
                get_user_id_from_context()

    def test_dev_env_no_bearer_prefix(self, monkeypatch, mock_event_ctx):
        """TC-06: dev環境 + "Bearer "プレフィックスなし → UnauthorizedError.

        【テスト目的】: Bearer プレフィックスがない場合にフォールバックがスキップされることを検証する
        【テスト内容】: Bearer なしの Authorization ヘッダーで UnauthorizedError を確認する
        【期待される動作】: startswith("Bearer ") が False となり、フォールバック処理をスキップする
        🟡 信頼性レベル: 黄信号 - EDGE-LD-102, TC-LD-061-B02 より
        """
        monkeypatch.setenv("ENVIRONMENT", "dev")

        raw_token = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.sig"
        mock_event = _make_event(authorizer=None, auth_header=f"Token {raw_token}")

        with mock_event_ctx(mock_event):
            with pytest.raises(UnauthorizedError):  # 🟡 Bearer プレフィックスなしはスキップ
                get_user_id_from_context()

    def test_dev_env_invalid_base64_jwt(self, monkeypatch, mock_event_ctx):
        """TC-07: dev環境 + 不正なbase64のJWT → UnauthorizedError.

        【テスト目的】: 不正な base64 ペイロードの JWT で安全に失敗することを検証する
        【テスト内容】: 不正な base64 文字列を含む JWT でデコードエラーを確認する
        【期待される動作】: base64 デコードエラーが except でキャッチされ UnauthorizedError に変換される
        🟡 信頼性レベル: 黄信号 - EDGE-LD-003, TC-LD-061-E03 より
        """
        monkeypatch.setenv("ENVIRONMENT", "dev")

        mock_event = _make_event(
            authorizer=None,
            auth_header="Bearer eyJhbGciOiJSUzI1NiJ9.!!!invalid-base64!!!.fake_sig",
        )

        with mock_event_ctx(mock_event):
            with pytest.raises(UnauthorizedError):  # 🟡 不正 base64 はデコードエラー → UnauthorizedError
                get_user_id_from_context()

    def test_dev_env_jwt_missing_sub(self, monkeypatch, mock_event_ctx):
        """TC-08: dev環境 + subクレームなしのJWT → UnauthorizedError.

        【テスト目的】: JWT ペイロードに sub クレームがない場合に UnauthorizedError が発生することを検証する
        【テスト内容】: sub を含まない JWT ペイロードでデコード後の KeyError を確認する
        【期待される動作】: decoded["sub"] で KeyError → except でキャッチ → UnauthorizedError
        🟡 信頼性レベル: 黄信号 - EDGE-LD-003 からの妥当な推測
        """
        monkeypatch.setenv("ENVIRONMENT", "dev")

        token = make_jwt({"iss": "https://keycloak:8180/realms/memoru", "aud": "memoru-client"})
        mock_event = _make_event(authorizer=None, auth_header=f"Bearer {token}")

        with mock_event_ctx(mock_event):
            with pytest.raises(UnauthorizedError):  # 🟡 sub クレームなしは KeyError → UnauthorizedError
                get_user_id_from_context()


# =============================================================================
# モジュールレベルのヘルパー
# =============================================================================


def _make_event(*, authorizer, auth_header=None):
    """テスト用 mock_event を生成する.

    Args:
        authorizer: request_context.authorizer に設定する値（None 可）
        auth_header: get_header_value("Authorization") が返す値（None 可）

    Returns:
        MagicMock オブジェクト（app.current_event 相当）
    """
    mock_event = MagicMock()
    mock_event.request_context.authorizer = authorizer
    mock_event.get_header_value.return_value = auth_header
    return mock_event


class _MockAppContext:
    """app.current_event を mock_event に差し替えるコンテキストマネージャ."""

    def __init__(self, mock_event):
        self._mock_event = mock_event
        self._patcher = patch("api.handler.app")

    def __enter__(self):
        mock_app = self._patcher.start()
        type(mock_app).current_event = PropertyMock(return_value=self._mock_event)
        return mock_app

    def __exit__(self, *args):
        self._patcher.stop()

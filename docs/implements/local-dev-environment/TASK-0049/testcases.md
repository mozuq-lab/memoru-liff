# TASK-0049: JWT フォールバック テスト検証 - テストケース定義書

**作成日**: 2026-02-23
**タスクID**: TASK-0049
**タスクタイプ**: TDD
**テストファイル**: `backend/tests/unit/test_handler_jwt_fallback.py`
**対象関数**: `get_user_id_from_context()` in `backend/src/api/handler.py` (L61-99)

---

## 開発言語・フレームワーク

- **プログラミング言語**: Python 3.12
  - **言語選択の理由**: プロジェクト全体が Python 3.12 で実装されている
  - **テストに適した機能**: monkeypatch による環境変数制御、`unittest.mock.patch` によるモジュールレベルのモック
- **テストフレームワーク**: pytest
  - **フレームワーク選択の理由**: プロジェクト既存の 251 テストが全て pytest で実装されている
  - **テスト実行環境**: `cd backend && make test` または `pytest tests/unit/test_handler_jwt_fallback.py -v`
- 🔵 信頼性レベル: 青信号 - `backend/tests/conftest.py`, 既存テストファイル群より

---

## テスト実装方針

### app.current_event のモック戦略

`get_user_id_from_context()` は引数を取らず、`app.current_event` からリクエスト情報を取得する。テストでは `unittest.mock.patch` で `api.handler.app` の `current_event` を差し替え、以下の属性をモックする:

```python
from unittest.mock import patch, MagicMock, PropertyMock

# パターン1: authorizer context なし + JWT ヘッダーあり
mock_event = MagicMock()
mock_event.request_context.authorizer = None  # authorizer context 無効
mock_event.get_header_value.return_value = "Bearer eyJ..."  # JWT ヘッダー

with patch("api.handler.app") as mock_app:
    type(mock_app).current_event = PropertyMock(return_value=mock_event)
    result = get_user_id_from_context()
```

### JWT テストトークンの生成

```python
import base64
import json

def make_jwt(payload: dict) -> str:
    """テスト用 JWT トークンを生成する（署名なし）."""
    header = {"alg": "RS256", "typ": "JWT"}
    h = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    p = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{h}.{p}.fake_signature"
```

### 環境変数制御

```python
# conftest.py で ENVIRONMENT="test" が設定済み
# dev フォールバックテストでは monkeypatch で上書き
monkeypatch.setenv("ENVIRONMENT", "dev")
```

- 🔵 信頼性レベル: 青信号 - `backend/src/api/handler.py` L61-99 の実装コード、`backend/tests/conftest.py`、`backend/tests/unit/test_unlink_line.py` の既存モックパターンより

---

## テストクラス構造

```python
class TestGetUserIdFromContext:
    """get_user_id_from_context() の dev 環境 JWT フォールバック機能テスト."""
```

---

## 1. 正常系テストケース

### TC-01: dev環境 + 有効なJWT → sub返却 🔵

- **テスト名**: `test_dev_env_valid_jwt_returns_sub`
  - **何をテストするか**: `ENVIRONMENT=dev` で authorizer context がない場合、Authorization ヘッダーの JWT ペイロードから `sub` クレームを抽出して返す
  - **期待される動作**: JWT ペイロードの base64url デコード → JSON パース → `sub` フィールドの値が返る
- **入力値**:
  - 環境変数: `ENVIRONMENT=dev`
  - authorizer context: `None`
  - Authorization ヘッダー: `Bearer {make_jwt({"sub": "test-user-123", "iss": "https://keycloak:8180/realms/memoru"})}`
  - **入力データの意味**: Keycloak が発行する実際の JWT トークン形式を模擬。SAM local で authorizer context が空の状態を再現
- **期待される結果**: `"test-user-123"` (文字列)
  - **期待結果の理由**: JWT ペイロードの `sub` クレームがそのままユーザーIDとして返される（REQ-LD-062）
- **テストの目的**: dev 環境 JWT フォールバックの基本動作確認
  - **確認ポイント**: base64url パディング処理が正しく動作すること、JSON パースが成功すること、`sub` 値が正確に返ること
- 🔵 信頼性レベル: 青信号 - REQ-LD-061, REQ-LD-062, TC-LD-061-01, handler.py L84-95 実装コードより

#### テスト実装イメージ

```python
def test_dev_env_valid_jwt_returns_sub(self, monkeypatch):
    """TC-01: dev環境 + 有効なJWT → sub返却.

    【テスト目的】: ENVIRONMENT=dev で JWT フォールバックが正常に動作することを検証する
    【テスト内容】: authorizer context なし + 有効な JWT ヘッダーで get_user_id_from_context() を呼び出す
    【期待される動作】: JWT ペイロードの sub クレームがユーザーIDとして返る
    🔵 信頼性レベル: 青信号 - REQ-LD-061, REQ-LD-062, handler.py L84-95 より
    """
    # 【テストデータ準備】: dev 環境を設定
    monkeypatch.setenv("ENVIRONMENT", "dev")

    # 【初期条件設定】: authorizer context なし + 有効な JWT ヘッダーを持つイベントを構築
    token = make_jwt({"sub": "test-user-123", "iss": "https://keycloak:8180/realms/memoru"})
    mock_event = MagicMock()
    mock_event.request_context.authorizer = None
    mock_event.get_header_value.return_value = f"Bearer {token}"

    # 【実際の処理実行】: get_user_id_from_context() を呼び出す
    with patch("api.handler.app") as mock_app:
        type(mock_app).current_event = PropertyMock(return_value=mock_event)
        result = get_user_id_from_context()

    # 【結果検証】: JWT ペイロードの sub が返ることを確認
    assert result == "test-user-123"  # 【確認内容】: sub クレームの値が正確に返る 🔵
```

---

### TC-02: authorizer context あり → authorizer context の sub を使用 🔵

- **テスト名**: `test_authorizer_context_returns_sub`
  - **何をテストするか**: authorizer context に `jwt.claims.sub` が存在する場合、フォールバックを使用せずに authorizer context から `sub` を取得する
  - **期待される動作**: `app.current_event.request_context.authorizer["jwt"]["claims"]["sub"]` の値が返る
- **入力値**:
  - 環境変数: デフォルト（`ENVIRONMENT=test`、monkeypatch 不使用）
  - authorizer context: `{"jwt": {"claims": {"sub": "authorizer-user-456"}}}`
  - Authorization ヘッダー: なし（`get_header_value` は呼ばれない）
  - **入力データの意味**: 本番環境で API Gateway JWT Authorizer が検証済み claims を設定した状態を再現
- **期待される結果**: `"authorizer-user-456"` (文字列)
  - **期待結果の理由**: authorizer context のパス（段階1）で sub が見つかるため、フォールバック（段階2）には到達しない
- **テストの目的**: 本番環境での正規パスが動作することを確認（フォールバック不使用）
  - **確認ポイント**: authorizer context が利用可能な場合、JWT フォールバックコードパスに到達しないこと
- 🔵 信頼性レベル: 青信号 - REQ-LD-101, TC-LD-061-02, handler.py L70-74 実装コードより

#### テスト実装イメージ

```python
def test_authorizer_context_returns_sub(self):
    """TC-02: authorizer context あり → authorizer context の sub を使用.

    【テスト目的】: authorizer context が利用可能な場合、フォールバック不使用でsubが返ることを検証する
    【テスト内容】: authorizer context に jwt.claims.sub を設定し get_user_id_from_context() を呼び出す
    【期待される動作】: authorizer context の sub が返り、JWT フォールバックは使用されない
    🔵 信頼性レベル: 青信号 - REQ-LD-101, TC-LD-061-02 より
    """
    # 【テストデータ準備】: authorizer context に sub を設定
    mock_event = MagicMock()
    mock_event.request_context.authorizer = {
        "jwt": {"claims": {"sub": "authorizer-user-456"}}
    }

    # 【実際の処理実行】: get_user_id_from_context() を呼び出す
    with patch("api.handler.app") as mock_app:
        type(mock_app).current_event = PropertyMock(return_value=mock_event)
        result = get_user_id_from_context()

    # 【結果検証】: authorizer context の sub が返ることを確認
    assert result == "authorizer-user-456"  # 【確認内容】: authorizer context から sub が取得される 🔵

    # 【確認内容】: get_header_value が呼ばれていないことを確認（フォールバック不使用）
    mock_event.get_header_value.assert_not_called()  # 🔵
```

---

### TC-09: authorizer context あり + JWT ヘッダーあり → authorizer context を優先 🔵

- **テスト名**: `test_authorizer_context_takes_priority_over_jwt_header`
  - **何をテストするか**: authorizer context と JWT ヘッダーの両方が存在する場合、authorizer context の `sub` が優先される
  - **期待される動作**: authorizer context のパス（段階1）で sub が見つかり、JWT フォールバック（段階2）は実行されない
- **入力値**:
  - 環境変数: `ENVIRONMENT=dev`（フォールバック有効な環境）
  - authorizer context: `{"jwt": {"claims": {"sub": "authorizer-user"}}}`
  - Authorization ヘッダー: `Bearer {make_jwt({"sub": "header-user"})}`（異なる sub 値）
  - **入力データの意味**: 本番デプロイ環境と同じく authorizer context が存在する場合のフォールバック優先順位を確認
- **期待される結果**: `"authorizer-user"` (文字列)
  - **期待結果の理由**: authorizer context は常に JWT ヘッダーより優先される（段階1 > 段階2）
- **テストの目的**: 認証ソースの優先順位が正しいことを確認
  - **確認ポイント**: JWT ヘッダーの `sub`（`"header-user"`）が返されないこと
- 🔵 信頼性レベル: 青信号 - REQ-LD-101, handler.py L70-80 の段階1コードパスより

#### テスト実装イメージ

```python
def test_authorizer_context_takes_priority_over_jwt_header(self, monkeypatch):
    """TC-09: authorizer context あり + JWT ヘッダーあり → authorizer context を優先.

    【テスト目的】: 両方のソースが存在する場合、authorizer context が優先されることを検証する
    【テスト内容】: authorizer context と JWT ヘッダーに異なる sub を設定し、どちらが返るかを確認する
    【期待される動作】: authorizer context の sub が返り、JWT ヘッダーの sub は無視される
    🔵 信頼性レベル: 青信号 - REQ-LD-101 より
    """
    # 【テストデータ準備】: dev 環境を設定（フォールバック有効条件）
    monkeypatch.setenv("ENVIRONMENT", "dev")

    # 【初期条件設定】: authorizer context と JWT ヘッダーに異なる sub を設定
    token = make_jwt({"sub": "header-user"})
    mock_event = MagicMock()
    mock_event.request_context.authorizer = {
        "jwt": {"claims": {"sub": "authorizer-user"}}
    }
    mock_event.get_header_value.return_value = f"Bearer {token}"

    # 【実際の処理実行】: get_user_id_from_context() を呼び出す
    with patch("api.handler.app") as mock_app:
        type(mock_app).current_event = PropertyMock(return_value=mock_event)
        result = get_user_id_from_context()

    # 【結果検証】: authorizer context の sub が優先されることを確認
    assert result == "authorizer-user"  # 【確認内容】: authorizer context が優先される 🔵
    assert result != "header-user"  # 【確認内容】: JWT ヘッダーの sub は使用されない 🔵
```

---

## 2. 異常系テストケース

### TC-03: ENVIRONMENT=prod + JWTヘッダーあり → UnauthorizedError（フォールバック無効） 🔵

- **テスト名**: `test_prod_env_jwt_header_raises_unauthorized`
  - **エラーケースの概要**: 本番環境（`ENVIRONMENT=prod`）では authorizer context がない場合、JWT フォールバックは使用されず UnauthorizedError が発生する
  - **エラー処理の重要性**: 本番環境でのセキュリティ確保。JWT フォールバックは署名検証を行わないため、本番で有効化されるとセキュリティリスクとなる
- **入力値**:
  - 環境変数: `ENVIRONMENT=prod`
  - authorizer context: `None`
  - Authorization ヘッダー: `Bearer {make_jwt({"sub": "test-user-123"})}`（有効な JWT）
  - **不正な理由**: 本番環境では `ENVIRONMENT != "dev"` のため、フォールバックコードパスに入れない
  - **実際の発生シナリオ**: API Gateway JWT Authorizer が何らかの理由で claims を設定しなかった場合
- **期待される結果**: `UnauthorizedError` 例外
  - **エラーメッセージの内容**: `"Unable to extract user ID from token"`
  - **システムの安全性**: JWT フォールバック（署名未検証）が本番環境で使用されないことを保証
- **テストの目的**: セキュリティ境界テスト - 本番環境でのフォールバック無効化確認
  - **品質保証の観点**: NFR-LD-101（JWT フォールバックの本番非適用）の検証
- 🔵 信頼性レベル: 青信号 - REQ-LD-063, NFR-LD-101, TC-LD-061-B01, handler.py L87 条件分岐より

#### テスト実装イメージ

```python
def test_prod_env_jwt_header_raises_unauthorized(self, monkeypatch):
    """TC-03: ENVIRONMENT=prod + JWTヘッダーあり → UnauthorizedError.

    【テスト目的】: 本番環境では JWT フォールバックが無効であることを検証する
    【テスト内容】: ENVIRONMENT=prod で有効な JWT ヘッダーを送信し、UnauthorizedError を確認する
    【期待される動作】: フォールバックコードパスに入らず UnauthorizedError が発生する
    🔵 信頼性レベル: 青信号 - REQ-LD-063, NFR-LD-101, TC-LD-061-B01 より
    """
    # 【テストデータ準備】: prod 環境を設定
    monkeypatch.setenv("ENVIRONMENT", "prod")

    # 【初期条件設定】: authorizer context なし + 有効な JWT ヘッダー
    token = make_jwt({"sub": "test-user-123"})
    mock_event = MagicMock()
    mock_event.request_context.authorizer = None
    mock_event.get_header_value.return_value = f"Bearer {token}"

    # 【実際の処理実行】: get_user_id_from_context() を呼び出す
    with patch("api.handler.app") as mock_app:
        type(mock_app).current_event = PropertyMock(return_value=mock_event)
        with pytest.raises(UnauthorizedError):  # 【結果検証】: UnauthorizedError が発生する 🔵
            get_user_id_from_context()
```

---

### TC-04: ENVIRONMENT未設定 + JWTヘッダーあり → UnauthorizedError 🔵

- **テスト名**: `test_no_env_var_jwt_header_raises_unauthorized`
  - **エラーケースの概要**: `ENVIRONMENT` 環境変数が設定されていない場合（`os.environ.get("ENVIRONMENT")` が `None`）、フォールバックは無効
  - **エラー処理の重要性**: 環境変数の未設定は `"dev"` と等しくないため、フォールバックが有効化されてはならない
- **入力値**:
  - 環境変数: `ENVIRONMENT` を削除（`monkeypatch.delenv("ENVIRONMENT", raising=False)`）
  - authorizer context: `None`
  - Authorization ヘッダー: `Bearer {make_jwt({"sub": "test-user-123"})}`
  - **不正な理由**: `os.environ.get("ENVIRONMENT")` が `None` を返し、`None == "dev"` は `False`
  - **実際の発生シナリオ**: 新しい環境で環境変数の設定が漏れた場合
- **期待される結果**: `UnauthorizedError` 例外
  - **エラーメッセージの内容**: `"Unable to extract user ID from token"`
  - **システムの安全性**: 環境変数未設定時にデフォルトで安全側（フォールバック無効）に倒れる
- **テストの目的**: fail-safe 設計の確認 - 環境変数未設定時のデフォルト動作
  - **品質保証の観点**: セキュリティの fail-safe 原則（明示的に有効化しない限り無効）
- 🔵 信頼性レベル: 青信号 - handler.py L87 `os.environ.get("ENVIRONMENT") == "dev"` 条件分岐より

#### テスト実装イメージ

```python
def test_no_env_var_jwt_header_raises_unauthorized(self, monkeypatch):
    """TC-04: ENVIRONMENT未設定 + JWTヘッダーあり → UnauthorizedError.

    【テスト目的】: ENVIRONMENT 環境変数が未設定の場合、フォールバックが無効であることを検証する
    【テスト内容】: ENVIRONMENT を削除し、有効な JWT ヘッダーで UnauthorizedError を確認する
    【期待される動作】: fail-safe でフォールバック無効、UnauthorizedError が発生する
    🔵 信頼性レベル: 青信号 - handler.py L87 条件分岐より
    """
    # 【テストデータ準備】: ENVIRONMENT 環境変数を削除
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    # 【初期条件設定】: authorizer context なし + 有効な JWT ヘッダー
    token = make_jwt({"sub": "test-user-123"})
    mock_event = MagicMock()
    mock_event.request_context.authorizer = None
    mock_event.get_header_value.return_value = f"Bearer {token}"

    # 【実際の処理実行】: get_user_id_from_context() を呼び出す
    with patch("api.handler.app") as mock_app:
        type(mock_app).current_event = PropertyMock(return_value=mock_event)
        with pytest.raises(UnauthorizedError):  # 【結果検証】: UnauthorizedError が発生する 🔵
            get_user_id_from_context()
```

---

### TC-05: dev環境 + Authorizationヘッダーなし → UnauthorizedError 🟡

- **テスト名**: `test_dev_env_no_auth_header_raises_unauthorized`
  - **エラーケースの概要**: `ENVIRONMENT=dev` でフォールバックが有効だが、Authorization ヘッダーがない場合は sub を取得できず UnauthorizedError
  - **エラー処理の重要性**: ヘッダーなしのリクエストはクライアント側のバグを示すため、適切にエラーを返す必要がある
- **入力値**:
  - 環境変数: `ENVIRONMENT=dev`
  - authorizer context: `None`
  - Authorization ヘッダー: `None`（`get_header_value("Authorization")` が `None` を返す）
  - **不正な理由**: Authorization ヘッダーが存在しないため、JWT トークンを取得できない
  - **実際の発生シナリオ**: フロントエンドがトークンをヘッダーに設定し忘れた場合
- **期待される結果**: `UnauthorizedError` 例外
  - **エラーメッセージの内容**: `"Unable to extract user ID from token"`
  - **システムの安全性**: ヘッダーなしで認証をスキップしないことを保証
- **テストの目的**: Authorization ヘッダー不在時のエラーハンドリング確認
  - **品質保証の観点**: TC-LD-061-E01（Authorization ヘッダーなし → 401）の検証
- 🟡 信頼性レベル: 黄信号 - TC-LD-061-E01, handler.py L89-90 条件分岐より（`auth_header` が `None` の場合の分岐）

#### テスト実装イメージ

```python
def test_dev_env_no_auth_header_raises_unauthorized(self, monkeypatch):
    """TC-05: dev環境 + Authorizationヘッダーなし → UnauthorizedError.

    【テスト目的】: Authorization ヘッダーがない場合に UnauthorizedError が発生することを検証する
    【テスト内容】: ENVIRONMENT=dev で Authorization ヘッダーなしの状態を再現する
    【期待される動作】: JWT フォールバックコードパスに入るが、ヘッダーなしで失敗する
    🟡 信頼性レベル: 黄信号 - TC-LD-061-E01, handler.py L89-90 より
    """
    # 【テストデータ準備】: dev 環境を設定
    monkeypatch.setenv("ENVIRONMENT", "dev")

    # 【初期条件設定】: authorizer context なし + Authorization ヘッダーなし
    mock_event = MagicMock()
    mock_event.request_context.authorizer = None
    mock_event.get_header_value.return_value = None

    # 【実際の処理実行】: get_user_id_from_context() を呼び出す
    with patch("api.handler.app") as mock_app:
        type(mock_app).current_event = PropertyMock(return_value=mock_event)
        with pytest.raises(UnauthorizedError):  # 【結果検証】: UnauthorizedError が発生する 🟡
            get_user_id_from_context()
```

---

### TC-06: dev環境 + "Bearer "プレフィックスなし → UnauthorizedError 🟡

- **テスト名**: `test_dev_env_no_bearer_prefix_raises_unauthorized`
  - **エラーケースの概要**: Authorization ヘッダーは存在するが `"Bearer "` プレフィックスがない場合、フォールバックスキップで UnauthorizedError
  - **エラー処理の重要性**: Bearer 以外のスキーム（Basic 等）を誤って処理しないよう、プレフィックスチェックが必要
- **入力値**:
  - 環境変数: `ENVIRONMENT=dev`
  - authorizer context: `None`
  - Authorization ヘッダー: `"eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.sig"`（Bearer プレフィックスなし）
  - **不正な理由**: `auth_header.startswith("Bearer ")` が `False` になるため、if 分岐に入らない
  - **実際の発生シナリオ**: クライアントが Bearer プレフィックスを付け忘れた場合
- **期待される結果**: `UnauthorizedError` 例外
  - **エラーメッセージの内容**: `"Unable to extract user ID from token"`
  - **システムの安全性**: Bearer スキーム以外を受け付けないことを保証
- **テストの目的**: Bearer プレフィックスバリデーションの確認
  - **品質保証の観点**: TC-LD-061-B02, EDGE-LD-102 の検証
- 🟡 信頼性レベル: 黄信号 - EDGE-LD-102, TC-LD-061-B02, handler.py L90 `startswith("Bearer ")` 条件より

#### テスト実装イメージ

```python
def test_dev_env_no_bearer_prefix_raises_unauthorized(self, monkeypatch):
    """TC-06: dev環境 + "Bearer "プレフィックスなし → UnauthorizedError.

    【テスト目的】: Bearer プレフィックスがない場合にフォールバックがスキップされることを検証する
    【テスト内容】: Bearer なしの Authorization ヘッダーで UnauthorizedError を確認する
    【期待される動作】: startswith("Bearer ") が False となり、フォールバック処理をスキップする
    🟡 信頼性レベル: 黄信号 - EDGE-LD-102, TC-LD-061-B02 より
    """
    # 【テストデータ準備】: dev 環境を設定
    monkeypatch.setenv("ENVIRONMENT", "dev")

    # 【初期条件設定】: authorizer context なし + Bearer プレフィックスなしの Authorization ヘッダー
    mock_event = MagicMock()
    mock_event.request_context.authorizer = None
    mock_event.get_header_value.return_value = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ0ZXN0In0.sig"

    # 【実際の処理実行】: get_user_id_from_context() を呼び出す
    with patch("api.handler.app") as mock_app:
        type(mock_app).current_event = PropertyMock(return_value=mock_event)
        with pytest.raises(UnauthorizedError):  # 【結果検証】: UnauthorizedError が発生する 🟡
            get_user_id_from_context()
```

---

### TC-07: dev環境 + 不正なbase64のJWT → UnauthorizedError 🟡

- **テスト名**: `test_dev_env_invalid_base64_jwt_raises_unauthorized`
  - **エラーケースの概要**: JWT ペイロード部分が不正な base64 文字列の場合、`base64.urlsafe_b64decode` が例外を発生させる
  - **エラー処理の重要性**: 不正なトークンで認証を突破されないよう、デコードエラーを安全に処理する必要がある
- **入力値**:
  - 環境変数: `ENVIRONMENT=dev`
  - authorizer context: `None`
  - Authorization ヘッダー: `"Bearer eyJhbGciOiJSUzI1NiJ9.!!!invalid-base64!!!.fake_sig"`
  - **不正な理由**: `!!!invalid-base64!!!` は有効な base64url 文字列ではなく、デコード時にエラーになる
  - **実際の発生シナリオ**: 改竄されたトークン、またはトークンの破損
- **期待される結果**: `UnauthorizedError` 例外
  - **エラーメッセージの内容**: `"Unable to extract user ID from token"`（except ブロックでキャッチ後、raise に到達）
  - **システムの安全性**: 不正な base64 で例外が伝播せず、安全に UnauthorizedError に変換される
- **テストの目的**: 不正な JWT 形式での安全なエラーハンドリング確認
  - **品質保証の観点**: TC-LD-061-E03, EDGE-LD-003 の検証
- 🟡 信頼性レベル: 黄信号 - EDGE-LD-003, TC-LD-061-E03, handler.py L96 except 節より

#### テスト実装イメージ

```python
def test_dev_env_invalid_base64_jwt_raises_unauthorized(self, monkeypatch):
    """TC-07: dev環境 + 不正なbase64のJWT → UnauthorizedError.

    【テスト目的】: 不正な base64 ペイロードの JWT で安全に失敗することを検証する
    【テスト内容】: 不正な base64 文字列を含む JWT でデコードエラーを確認する
    【期待される動作】: base64 デコードエラーが except でキャッチされ UnauthorizedError に変換される
    🟡 信頼性レベル: 黄信号 - EDGE-LD-003, TC-LD-061-E03 より
    """
    # 【テストデータ準備】: dev 環境を設定
    monkeypatch.setenv("ENVIRONMENT", "dev")

    # 【初期条件設定】: 不正な base64 ペイロードを含む JWT
    mock_event = MagicMock()
    mock_event.request_context.authorizer = None
    mock_event.get_header_value.return_value = "Bearer eyJhbGciOiJSUzI1NiJ9.!!!invalid-base64!!!.fake_sig"

    # 【実際の処理実行】: get_user_id_from_context() を呼び出す
    with patch("api.handler.app") as mock_app:
        type(mock_app).current_event = PropertyMock(return_value=mock_event)
        with pytest.raises(UnauthorizedError):  # 【結果検証】: UnauthorizedError が発生する 🟡
            get_user_id_from_context()
```

---

### TC-08: dev環境 + subクレームなしのJWT → UnauthorizedError 🟡

- **テスト名**: `test_dev_env_jwt_without_sub_raises_unauthorized`
  - **エラーケースの概要**: JWT ペイロードは正常にデコードできるが、`sub` クレームが含まれていない場合、`KeyError` が発生する
  - **エラー処理の重要性**: `sub` が必須であることを保証し、sub なしのトークンで認証をスキップしないようにする
- **入力値**:
  - 環境変数: `ENVIRONMENT=dev`
  - authorizer context: `None`
  - Authorization ヘッダー: `Bearer {make_jwt({"iss": "keycloak", "aud": "client"})}`（sub なし）
  - **不正な理由**: ペイロードに `sub` キーがなく、`decoded["sub"]` で `KeyError` が発生する
  - **実際の発生シナリオ**: 不完全なトークン構成、または異なるクレーム構造を持つ別サービスのトークン
- **期待される結果**: `UnauthorizedError` 例外
  - **エラーメッセージの内容**: `"Unable to extract user ID from token"`
  - **システムの安全性**: sub なしのトークンでユーザーIDが空やNoneにならないことを保証
- **テストの目的**: sub クレーム必須バリデーションの確認
  - **品質保証の観点**: REQ-LD-062（sub クレーム使用）の否定テスト
- 🟡 信頼性レベル: 黄信号 - EDGE-LD-003 からの妥当な推測、handler.py L95 `decoded["sub"]` の KeyError より

#### テスト実装イメージ

```python
def test_dev_env_jwt_without_sub_raises_unauthorized(self, monkeypatch):
    """TC-08: dev環境 + subクレームなしのJWT → UnauthorizedError.

    【テスト目的】: JWT ペイロードに sub クレームがない場合に UnauthorizedError が発生することを検証する
    【テスト内容】: sub を含まない JWT ペイロードでデコード後の KeyError を確認する
    【期待される動作】: decoded["sub"] で KeyError → except でキャッチ → UnauthorizedError
    🟡 信頼性レベル: 黄信号 - EDGE-LD-003 からの妥当な推測
    """
    # 【テストデータ準備】: dev 環境を設定
    monkeypatch.setenv("ENVIRONMENT", "dev")

    # 【初期条件設定】: sub クレームなしの JWT
    token = make_jwt({"iss": "keycloak", "aud": "client"})  # sub なし
    mock_event = MagicMock()
    mock_event.request_context.authorizer = None
    mock_event.get_header_value.return_value = f"Bearer {token}"

    # 【実際の処理実行】: get_user_id_from_context() を呼び出す
    with patch("api.handler.app") as mock_app:
        type(mock_app).current_event = PropertyMock(return_value=mock_event)
        with pytest.raises(UnauthorizedError):  # 【結果検証】: UnauthorizedError が発生する 🟡
            get_user_id_from_context()
```

---

## 3. 境界値テストケース

### TC-10: 既存テスト251件が全てpass 🔵

- **テスト名**: （テストメソッドではなく、テスト実行で確認）
  - **境界値の意味**: 新規テストファイルの追加が既存テストに影響を与えないことを確認
  - **境界値での動作保証**: テスト間の独立性（各テストで monkeypatch による環境変数復元が行われること）
- **入力値**: `cd backend && make test`
  - **境界値選択の根拠**: 既存テストが `ENVIRONMENT=test` を前提としており、新規テストで `ENVIRONMENT=dev` を使用するため、テスト間の汚染がないことを確認
  - **実際の使用場面**: CI/CD パイプラインで全テストを一括実行する場面
- **期待される結果**: 251 テスト + 新規テスト = 全て pass（252件以上）
  - **境界での正確性**: 新規テスト内で monkeypatch が正しくスコープ管理され、テスト終了後に環境変数が復元されること
  - **一貫した動作**: 新規テストの実行順序に依存せず、全テストが pass すること
- **テストの目的**: 後方互換性の確認
  - **堅牢性の確認**: テスト間の環境変数汚染がないことを保証
- 🔵 信頼性レベル: 青信号 - REQ-LD-401, `backend/tests/conftest.py` L12 `ENVIRONMENT=test` 設定より

#### 確認手順

```bash
# 全テスト実行（既存 251 テスト + 新規テスト）
cd backend && make test

# 期待される出力:
# 252+ passed (新規テスト追加分)
```

---

## 要件定義との対応関係

| テストケース | 受け入れ基準 | EARS要件 | 分類 |
|-------------|-------------|---------|------|
| TC-01 | TC-LD-061-01 | REQ-LD-061, REQ-LD-062 | 正常系 |
| TC-02 | TC-LD-061-02 | REQ-LD-101 | 正常系 |
| TC-03 | TC-LD-061-B01 | REQ-LD-063, NFR-LD-101 | 異常系（セキュリティ） |
| TC-04 | - | REQ-LD-063 | 異常系（セキュリティ） |
| TC-05 | TC-LD-061-E01 | EDGE-LD-003 | 異常系 |
| TC-06 | TC-LD-061-B02 | EDGE-LD-102 | 異常系 |
| TC-07 | TC-LD-061-E03 | EDGE-LD-003 | 異常系 |
| TC-08 | - | REQ-LD-062（否定） | 異常系 |
| TC-09 | TC-LD-061-02 | REQ-LD-101 | 正常系（優先順位） |
| TC-10 | - | REQ-LD-401 | 境界値（互換性） |

### 参照した機能概要

- `docs/spec/local-dev-environment/requirements.md` - REQ-LD-061〜064（JWT フォールバック機能要件）
- `docs/spec/local-dev-environment/requirements.md` - REQ-LD-101（authorizer context 優先）

### 参照した入力・出力仕様

- `backend/src/api/handler.py` L61-99 - `get_user_id_from_context()` 実装コード
- `docs/implements/local-dev-environment/TASK-0049/requirements.md` - セクション 2（入力・出力の仕様）

### 参照した制約条件

- `docs/implements/local-dev-environment/TASK-0049/requirements.md` - セクション 3（制約条件）
- `docs/spec/local-dev-environment/requirements.md` - REQ-LD-401（既存テスト互換性）, REQ-LD-403（環境変数制御）

### 参照した使用例

- `docs/spec/local-dev-environment/acceptance-criteria.md` - TC-LD-061-01〜TC-LD-061-B02
- `docs/spec/local-dev-environment/user-stories.md` - ストーリー 2.2

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 | 該当テストケース |
|--------|------|------|-----------------|
| 🔵 青信号 | 6件 | 60% | TC-01, TC-02, TC-03, TC-04, TC-09, TC-10 |
| 🟡 黄信号 | 4件 | 40% | TC-05, TC-06, TC-07, TC-08 |
| 🔴 赤信号 | 0件 | 0% | なし |

**品質評価**: ✅ 高品質
- テストケース分類: 正常系 3件、異常系 6件、境界値 1件 - 十分に網羅
- 期待値定義: 全テストケースで具体的な期待値（返却値または例外型）が明確
- 技術選択: Python 3.12 + pytest で確定（既存テスト基盤と一致）
- 実装可能性: 全テストケースが `unittest.mock.patch` + `monkeypatch` で実装可能
- 信頼性レベル: 🔵 60%、🟡 40%、🔴 0% - 赤信号なし

---

## テスト実行コマンド

```bash
# 新規テストのみ実行
cd backend && pytest tests/unit/test_handler_jwt_fallback.py -v

# 全テスト実行（既存 251 テスト + 新規テスト）
cd backend && make test

# カバレッジ確認
cd backend && pytest tests/unit/test_handler_jwt_fallback.py --cov=api.handler --cov-report=term-missing

# 特定テストのみ実行
cd backend && pytest tests/unit/test_handler_jwt_fallback.py::TestGetUserIdFromContext::test_dev_env_valid_jwt_returns_sub -v
```

---

**作成日**: 2026-02-23
**更新履歴**: 初版作成

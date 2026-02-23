# TASK-0049: JWT フォールバック テスト検証 - 開発ノート

**作成日**: 2026-02-23
**タスクID**: TASK-0049
**タスクタイプ**: TDD
**推定工数**: 4時間
**フェーズ**: Phase 1 - 残タスク解決

---

## 1. 技術スタック

### 言語・フレームワーク
- **言語**: Python 3.12
- **テストフレームワーク**: pytest
- **テスト実行**: `make test` で 251 テスト実施
- **参照元**: `backend/tests/conftest.py`

### バックエンド API フレームワーク
- **Lambda フレームワーク**: AWS Lambda Powertools
- **API Resolver**: APIGatewayHttpResolver
- **例外処理**: UnauthorizedError（Powertools 標準例外）
- **参照元**: `backend/src/api/handler.py`

### JWT処理
- **標準ライブラリ**: base64（urlsafe_b64decode）, json
- **処理方式**: base64url デコード + JSON パース（署名検証なし）
- **環境限定**: ENVIRONMENT=dev のみ
- **参照元**: `backend/src/api/handler.py` L84-98

---

## 2. 開発ルール

### テスト実装規約
- **テストファイル置き場**: `backend/tests/unit/` ディレクトリ
- **テストファイル名**: `test_{機能名}.py` 形式
- **クラス名**: `Test{機能名}` パスカルケース
- **テストメソッド**: `test_{シナリオ名}` スネークケース
- **参照元**: `backend/tests/unit/test_handler_link_line.py`

### テストドキュメンテーション形式
```python
def test_example_scenario(self, api_gateway_event, lambda_context):
    """TC-XX: テスト目的をJapaneseで記述.

    【テスト目的】: 何を検証するか
    【テスト内容】: どのようにテストするか
    【期待される動作】: 何が期待されるか
    🔵 信頼性レベル: 青信号 - 根拠を記述
    """
    # 【テストデータ準備】: フェーズコメント付き
    # 【初期条件設定】: フェーズコメント付き
    # 【実際の処理実行】: フェーズコメント付き
    # 【結果検証】: フェーズコメント付き
    # 【確認内容】: アサーション
```
- **参照元**: `backend/tests/unit/test_handler_link_line.py`

### Mock パターン
- **patch 対象**: `api.handler.{service_name}` モジュールパス
- **モック作成**: `MagicMock()` を使用
- **fixture 活用**: `api_gateway_event`, `lambda_context` を使用
- **参照元**: `backend/tests/conftest.py`

### 環境変数管理
- **テスト環境**: conftest.py で `ENVIRONMENT="test"` に固定
- **dev 環境テスト**: `monkeypatch` fixture で `ENVIRONMENT="dev"` に変更
- **参照元**: `backend/tests/conftest.py` L12

---

## 3. 関連実装

### 現在の実装位置
**ファイル**: `backend/src/api/handler.py`
**関数**: `get_user_id_from_context()`
**行番号**: L61-99

### 実装の3段階構成
```python
# 段階1: authorizer context から抽出（本番環境）
claims = app.current_event.request_context.authorizer
if claims and "jwt" in claims:
    return claims["jwt"]["claims"]["sub"]

# 段階2: dev環境 JWT フォールバック（L84-98）
if os.environ.get("ENVIRONMENT") == "dev":
    auth_header = app.current_event.get_header_value("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)  # base64url パディング
        decoded = json.loads(base64.urlsafe_b64decode(payload))
        return decoded["sub"]

# 段階3: 失敗時の例外
raise UnauthorizedError("Unable to extract user ID from token")
```

### 既存テスト パターン（参考実装）
**ファイル**: `backend/tests/unit/test_handler_link_line.py`

**特徴**:
- api_gateway_event fixture で HTTP API イベントを生成
- patch で handler モジュール内のサービスをモック
- handler 関数を直接呼び出してテスト
- response["statusCode"] と response["body"] を検証

**テストライフサイクル**:
```python
1. event = api_gateway_event(method="POST", path="/users/link-line", body={})
2. with patch("api.handler.user_service"), patch("api.handler.line_service"):
3. from api.handler import handler
4. response = handler(event, lambda_context)
5. assert response["statusCode"] == 400
6. assert "id_token" in json.loads(response["body"])
```

---

## 4. 設計文書・要件定義

### 関連する受け入れ基準
**ファイル**: `docs/spec/local-dev-environment/acceptance-criteria.md`

#### フォールバックテストケース（TC-LD-061-01 ~ TC-LD-061-B02）
- **TC-LD-061-01**: 正規の Keycloak トークンからユーザー ID を抽出
- **TC-LD-061-02**: authorizer context がある場合はフォールバック不使用
- **TC-LD-061-E01**: Authorization ヘッダーがない場合 → 401
- **TC-LD-061-E02**: JWT が不正な形式（ドット不足）→ 401
- **TC-LD-061-E03**: base64 デコード失敗 → 401
- **TC-LD-061-B01**: ENVIRONMENT != "dev" → フォールバック無効
- **TC-LD-061-B02**: Bearer プレフィックスなし → フォールバックスキップ

### 関連するユーザストーリー
**ファイル**: `docs/spec/local-dev-environment/user-stories.md`

#### ストーリー 2.2: 認証付き API をローカルで呼び出す
- Keycloak で JWT トークンを取得
- `Authorization: Bearer {token}` でリクエスト
- ハンドラーが JWT の `sub` クレームを抽出
- ユーザー固有のデータが返却される

**制約**:
- JWT フォールバックは dev 環境でのみ有効
- 署名検証は行わない（dev 環境限定のため）

### 関連する要件定義
**ファイル**: `docs/spec/local-dev-environment/requirements.md`

#### REQ-LD-061: dev環境 JWT フォールバック
- SAM local では JWT Authorizer が適用されない
- Authorization ヘッダーから JWT ペイロードをデコード
- base64url デコード + JSON パース
- `sub` クレームを user_id として返す

#### REQ-LD-063: 本番環境での無効化
- `ENVIRONMENT != "dev"` の場合、フォールバック無効
- authorizer context のみで認証

#### REQ-LD-101: 本番互換性
- authorizer context が利用可能な場合は優先
- フォールバックは開発専用

---

## 5. テスト対象と検証項目

### 対象関数
```python
def get_user_id_from_context() -> str:
    """Extract user_id from JWT claims in request context."""
```

### テスト対象パス
1. **authorizer context パス** (既存、要確認)
   - `claims["jwt"]["claims"]["sub"]` からの抽出
   - `claims["claims"]["sub"]` からの抽出
   - `claims["sub"]` からの抽出

2. **dev 環境 JWT フォールバック** (要テスト)
   - Authorization ヘッダーからの JWT デコード
   - base64url パディング処理
   - JSON パース
   - エラーハンドリング

### テストシナリオ一覧

#### 正常系
- [ ] **T-001**: `ENVIRONMENT=dev` + 有効な JWT → sub が返る
- [ ] **T-002**: authorizer context あり + JWT ヘッダーあり → context 優先
- [ ] **T-003**: `ENVIRONMENT=dev` + Keycloak 形式 JWT → パディング処理が動作

#### 異常系
- [ ] **T-004**: `ENVIRONMENT=dev` + Authorization ヘッダーなし → 401 (UnauthorizedError)
- [ ] **T-005**: `ENVIRONMENT=dev` + Bearer なし → 401
- [ ] **T-006**: `ENVIRONMENT=dev` + 無効な base64 → 401
- [ ] **T-007**: `ENVIRONMENT=dev` + sub クレームなし → 401

#### 境界値
- [ ] **T-008**: `ENVIRONMENT=prod` + JWT ヘッダーあり → フォールバック無効 → 401
- [ ] **T-009**: `ENVIRONMENT=staging` + JWT ヘッダー → フォールバック無効 → 401
- [ ] **T-010**: JWT ペイロードが短くてパディング必要 → 成功

---

## 6. 既存テスト環境の理解

### conftest.py の api_gateway_event fixture
**ファイル**: `backend/tests/conftest.py` L23-81

```python
@pytest.fixture
def api_gateway_event():
    """Create a base API Gateway HTTP API event."""
    def _create_event(
        method: str = "GET",
        path: str = "/",
        body: dict = None,
        headers: dict = None,
        user_id: str = "test-user-id",
    ):
        return {
            "version": "2.0",
            "rawPath": path,
            "headers": headers or {"content-type": "application/json"},
            "requestContext": {
                "authorizer": {
                    "jwt": {
                        "claims": {
                            "sub": user_id,
                            "iss": "https://keycloak.example.com/realms/memoru",
                        },
                        ...
                    }
                },
                ...
            },
            ...
        }
    return _create_event
```

### 既存テストでの authorizer context
- デフォルトで `authorizer.jwt.claims.sub` に test-user-id を設定
- `/users/me` などのエンドポイントテストで多用
- get_user_id_from_context() は通常 mock される

### 新しいテストで必要な修正
- **fixture の拡張**: `headers` パラメータを活用
- **mock の削除**: get_user_id_from_context() を直接テスト
- **authorizer 無効化**: `authorizer=None` を設定
- **環境変数切り替え**: `monkeypatch.setenv("ENVIRONMENT", "dev")`

---

## 7. テスト実装の手順

### Step 1: テストクラス構造
```python
class TestGetUserIdFromContext:
    """dev環境 JWT フォールバック機能のテスト."""
```

### Step 2: テストメソッドの実装順序
1. 正常系：有効な JWT からの抽出
2. 正常系：authorizer context 優先
3. 異常系：ヘッダーなし
4. 異常系：Bearer プレフィックスなし
5. 異常系：無効な base64
6. 異常系：sub クレームなし
7. 境界値：ENVIRONMENT != dev での無効化

### Step 3: Keycloak JWT の生成方法
```python
import base64
import json

# 手動で JWT を構築（テスト用）
header = {"alg": "RS256", "typ": "JWT"}
payload = {"sub": "test-user-123", "iss": "https://keycloak:8180/realms/memoru"}

# base64url エンコード（パディングなし）
import base64
header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b'=').decode()
payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b'=').decode()

token = f"{header_b64}.{payload_b64}.fake_signature"
```

### Step 4: 環境変数の切り替え（monkeypatch）
```python
def test_dev_fallback_enabled(self, api_gateway_event, lambda_context, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "dev")
    # テスト実行
```

### Step 5: handler 関数の呼び出しパターン
```python
from api.handler import app, get_user_id_from_context

# 直接関数を呼び出す場合
with patch("api.handler.app.current_event") as mock_event:
    mock_event.get_header_value.return_value = "Bearer eyJ..."
    result = get_user_id_from_context()
    assert result == "test-user-123"
```

---

## 8. 注意事項・制約

### テスト環境の特異性
1. **conftest.py での ENVIRONMENT="test"** 固定
   - dev フォールバックテストでは上書き必須
   - `monkeypatch.setenv()` で一時的に変更

2. **既存 251 テストの互換性**
   - 既存テストは authorizer context を mock
   - 新テストで get_user_id_from_context() を直接テストしても競合しない
   - 既存テストの mock 箇所を変更しない

### JWT デコード時の落とし穴
1. **base64url パディング処理** (L93)
   ```python
   payload += "=" * (4 - len(payload) % 4)
   ```
   - JWT ペイロードが 4 の倍数でない場合、= を追加
   - テストで様々な長さのペイロードを用意

2. **JWT 構造**
   - `header.payload.signature` の 3 部構成
   - テストでは payload（インデックス 1）のみをデコード
   - signature は使用しない

3. **例外ハンドリング**
   - IndexError: ドット不足
   - ValueError: base64 デコード失敗
   - KeyError: sub クレーム不在
   - 全て UnauthorizedError に変換

### セキュリティ考慮
- dev 環境での JWT フォールバックは署名検証なし
- 本番環境（ENVIRONMENT != "dev"）では必ず無効化
- テストで ENVIRONMENT=prod を明示的にテスト

---

## 9. 参照ファイル一覧

### コア実装
- `backend/src/api/handler.py` - get_user_id_from_context() の実装
- `backend/src/api/handler.py` - UnauthorizedError の使用箇所

### テスト基盤
- `backend/tests/conftest.py` - pytest fixture 定義
- `backend/tests/unit/test_handler_link_line.py` - テストパターン参考

### 要件・設計
- `docs/spec/local-dev-environment/requirements.md` - REQ-LD-061, REQ-LD-063
- `docs/spec/local-dev-environment/acceptance-criteria.md` - TC-LD-061-01 ~ TC-LD-061-B02
- `docs/spec/local-dev-environment/user-stories.md` - ストーリー 2.2
- `docs/design/local-dev-environment/architecture.md` - JWT フォールバック設計

### タスク定義
- `docs/tasks/local-dev-environment/TASK-0049.md` - タスク定義
- `docs/tasks/local-dev-environment/overview.md` - タスク進捗管理

---

## 10. テスト実行コマンド

### 全テスト実行（既存 251 テスト）
```bash
cd backend && make test
```

### 新規テストのみ実行
```bash
cd backend && pytest tests/unit/test_handler_jwt_fallback.py -v
```

### カバレッジ確認
```bash
cd backend && pytest tests/unit/test_handler_jwt_fallback.py --cov=api.handler --cov-report=term-missing
```

### 特定テストのみ実行
```bash
cd backend && pytest tests/unit/test_handler_jwt_fallback.py::TestGetUserIdFromContext::test_dev_fallback_valid_jwt -v
```

---

## 11. 完了条件チェックリスト

- [ ] dev 環境 JWT フォールバックパスのテストケースが存在する
- [ ] Authorization ヘッダーなしで 401 が返ることのテストが存在する
- [ ] 不正な JWT 形式で安全に失敗するテストが存在する
- [ ] ENVIRONMENT != "dev" でフォールバックが無効であるテストが存在する
- [ ] 既存テスト 251 件が引き続き全て pass する
- [ ] テストコード内に日本語ドキュメンテーション（【テスト目的】等）が含まれる

---

**ノート作成日**: 2026-02-23
**更新履歴**: 初版作成

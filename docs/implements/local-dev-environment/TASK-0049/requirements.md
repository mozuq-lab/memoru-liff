# TASK-0049: JWT フォールバック テスト検証 - TDD要件定義書

**作成日**: 2026-02-23
**タスクID**: TASK-0049
**タスクタイプ**: TDD
**対象関数**: `get_user_id_from_context()` in `backend/src/api/handler.py` (L61-99)

---

## 1. 機能の概要

### 何をする機能か 🔵

**信頼性**: 🔵 *REQ-LD-061〜064, architecture.md セクションA, 実装済みコードより*

`get_user_id_from_context()` 関数は、APIリクエストからユーザーIDを抽出する認証ヘルパーである。本番環境では API Gateway JWT Authorizer が検証済みの claims を Lambda に渡すが、SAM local では JWT Authorizer が適用されないため、dev 環境限定で Authorization ヘッダーの JWT ペイロードを直接デコードしてユーザーIDを取得するフォールバック機能を持つ。

### どのような問題を解決するか 🔵

**信頼性**: 🔵 *ユーザストーリー 2.2 より*

SAM local 環境では API Gateway JWT Authorizer が動作しないため、全ての認証付きエンドポイント（`/users/me`, `/cards`, `/reviews` 等）がユーザーIDを取得できず 401 Unauthorized になる。JWT フォールバックにより、Keycloak が発行したトークンから直接 `sub` クレームを抽出し、ローカルでのエンドツーエンド動作確認を可能にする。

### 想定されるユーザー 🔵

**信頼性**: 🔵 *ユーザストーリー 2.2 より*

LINE 環境なしでローカル開発を行う開発者。Keycloak でテストユーザー（test-user / test-password-123）としてログインし、JWT トークン付きで API を呼び出す。

### システム内での位置づけ 🔵

**信頼性**: 🔵 *architecture.md セクションA より*

```
リクエストフロー（dev環境）:
  ブラウザ → Vite(:3000) → SAM Local(:8080) → handler.py
                                                  ↓
                                          get_user_id_from_context()
                                                  ↓
                                          段階1: authorizer context → (SAM localでは空)
                                          段階2: ENVIRONMENT=="dev" → JWT フォールバック
                                          段階3: 失敗 → UnauthorizedError
```

- **参照したEARS要件**: REQ-LD-061, REQ-LD-062, REQ-LD-063, REQ-LD-064
- **参照した設計文書**: architecture.md セクションA「JWT フォールバック設計」

---

## 2. 入力・出力の仕様

### 入力パラメータ 🔵

**信頼性**: 🔵 *handler.py L61-99 実装コードより*

`get_user_id_from_context()` は引数を取らず、`app.current_event` からリクエスト情報を取得する。

| 入力ソース | 型 | 取得方法 | 用途 |
|-----------|-----|---------|------|
| authorizer context | `dict` or `None` | `app.current_event.request_context.authorizer` | 本番環境での認証情報（段階1） |
| ENVIRONMENT 環境変数 | `str` or `None` | `os.environ.get("ENVIRONMENT")` | フォールバック有効化制御 |
| Authorization ヘッダー | `str` or `None` | `app.current_event.get_header_value("Authorization")` | JWT トークン取得（段階2） |

### 出力値 🔵

**信頼性**: 🔵 *handler.py 実装コードより*

| 出力 | 型 | 説明 |
|------|-----|------|
| 正常時 | `str` | ユーザーID（JWT ペイロードの `sub` クレーム値） |
| 異常時 | `UnauthorizedError` 例外 | メッセージ: `"Unable to extract user ID from token"` |

### 入出力の関係性 🔵

**信頼性**: 🔵 *handler.py L61-99 実装コードより*

```
入力: Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ0ZXN0LXVzZXItMTIzIn0.signature
                                                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                                    base64url デコード → {"sub": "test-user-123"}

出力: "test-user-123"
```

### JWT デコード処理の詳細 🔵

**信頼性**: 🔵 *handler.py L91-95 実装コードより*

```python
# 1. "Bearer " プレフィックスを除去してトークンを取得
token = auth_header.split(" ", 1)[1]   # "eyJ...header.eyJ...payload.signature"

# 2. ドットで分割してペイロード部分を取得（インデックス1）
payload = token.split(".")[1]           # "eyJ...payload"

# 3. base64url パディングを追加
payload += "=" * (4 - len(payload) % 4) # パディング不足を補完

# 4. base64url デコード + JSON パース
decoded = json.loads(base64.urlsafe_b64decode(payload))  # {"sub": "test-user-123", ...}

# 5. sub クレームを返す
return decoded["sub"]                   # "test-user-123"
```

- **参照したEARS要件**: REQ-LD-062（sub クレーム使用）, REQ-LD-064（base64url デコードのみ、署名検証なし）
- **参照した設計文書**: architecture.md セクションA「設計方針」

---

## 3. 制約条件

### セキュリティ要件 🔵

**信頼性**: 🔵 *REQ-LD-063, NFR-LD-101 より*

- JWT フォールバックは `ENVIRONMENT == "dev"` の場合のみ有効化される
- `ENVIRONMENT` が `"dev"` 以外（`"prod"`, `"staging"`, `"test"`, 未設定）の場合、フォールバックは**絶対に**使用されない
- 本番環境では API Gateway JWT Authorizer がトークン検証済みのため、この関数に到達する時点でトークンは検証済み
- JWT フォールバックは署名検証を行わない（dev 環境限定のため）

### 互換性要件 🔵

**信頼性**: 🔵 *REQ-LD-101, REQ-LD-401 より*

- authorizer context が利用可能な場合（本番環境）、JWT フォールバックは使用されてはならない
- authorizer context の `sub` が JWT ヘッダーの `sub` よりも常に優先される
- 既存の 251 件のバックエンドテストが全て pass し続けなければならない

### 環境変数制約 🟡

**信頼性**: 🟡 *REQ-LD-403 より（妥当な推測）*

- フォールバックの有効/無効は `ENVIRONMENT` 環境変数のみで制御する
- コード内にハードコーディングされた環境判定を含めてはならない
- テスト環境では `conftest.py` で `ENVIRONMENT="test"` が設定されているため、dev フォールバックテストでは `monkeypatch.setenv("ENVIRONMENT", "dev")` で上書きが必要

### 例外処理制約 🔵

**信頼性**: 🔵 *handler.py L96-98 実装コードより*

- JWT デコード中の全てのエラー（KeyError, IndexError, ValueError, その他 Exception）は `UnauthorizedError` として伝播する
- エラーログは `logger.error()` で出力される

- **参照したEARS要件**: REQ-LD-063, REQ-LD-101, REQ-LD-401, REQ-LD-403
- **参照した設計文書**: architecture.md セクションA「セキュリティ考慮」

---

## 4. 想定される使用例

### 4.1 正常系

#### REQ-LD-061, REQ-LD-062: dev環境 + 有効なJWT → sub が返る 🔵

**信頼性**: 🔵 *REQ-LD-061, REQ-LD-062, TC-LD-061-01 より*

**前提条件**:
- `ENVIRONMENT=dev`
- authorizer context なし（SAM local 環境）

**入力**:
```
Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJ0ZXN0LXVzZXItMTIzIiwiaXNzIjoiaHR0cHM6Ly9rZXljbG9hayJ9.signature
```

**期待結果**: `"test-user-123"` が返る

#### REQ-LD-062: authorizer context 優先 🔵

**信頼性**: 🔵 *REQ-LD-101, TC-LD-061-02 より*

**前提条件**:
- authorizer context に `jwt.claims.sub = "authorizer-user"` が存在
- Authorization ヘッダーに JWT（`sub = "header-user"`）が存在

**期待結果**: `"authorizer-user"` が返る（フォールバック不使用）

### 4.2 セキュリティケース

#### REQ-LD-063: 本番環境でのフォールバック無効化 🔵

**信頼性**: 🔵 *REQ-LD-063, TC-LD-061-B01 より*

**前提条件**:
- `ENVIRONMENT=prod`（または `staging`, `test`, 未設定）
- authorizer context なし
- Authorization ヘッダーに有効な JWT が存在

**期待結果**: `UnauthorizedError` が発生する（フォールバック無効）

#### authorizer context が JWT ヘッダーより優先 🔵

**信頼性**: 🔵 *REQ-LD-101 より*

**前提条件**:
- `ENVIRONMENT=dev`
- authorizer context に `sub` が存在
- Authorization ヘッダーにも JWT が存在

**期待結果**: authorizer context の `sub` が返る（JWT ヘッダーは参照されない）

### 4.3 エラーケース

#### REQ-LD-064: Authorization ヘッダーなし 🟡

**信頼性**: 🟡 *EDGE-LD-003, TC-LD-061-E01 より（セキュリティベストプラクティスから推測）*

**前提条件**:
- `ENVIRONMENT=dev`
- authorizer context なし
- Authorization ヘッダーなし

**期待結果**: `UnauthorizedError` が発生する

#### EDGE-LD-102: Bearer プレフィックスなし 🟡

**信頼性**: 🟡 *EDGE-LD-102, TC-LD-061-B02 より*

**前提条件**:
- `ENVIRONMENT=dev`
- authorizer context なし
- `Authorization: eyJhbGciOiJSUzI1NiJ9...`（Bearer プレフィックスなし）

**期待結果**: `UnauthorizedError` が発生する（フォールバックスキップ）

#### EDGE-LD-003: 不正な base64 ペイロード 🟡

**信頼性**: 🟡 *EDGE-LD-003, TC-LD-061-E03 より*

**前提条件**:
- `ENVIRONMENT=dev`
- authorizer context なし
- `Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.!!!invalid-base64!!!.signature`

**期待結果**: `UnauthorizedError` が発生する（安全に失敗）

#### REQ-LD-064: sub クレーム不在 🟡

**信頼性**: 🟡 *EDGE-LD-003 から妥当な推測*

**前提条件**:
- `ENVIRONMENT=dev`
- authorizer context なし
- JWT ペイロードに `sub` が含まれない（例: `{"iss": "keycloak", "aud": "client"}`）

**期待結果**: `UnauthorizedError` が発生する

### 4.4 制約確認

#### REQ-LD-401: 既存テスト互換性 🔵

**信頼性**: 🔵 *REQ-LD-401 より*

**検証内容**: 新規テスト追加後、`make test` で既存 251 テストが全て pass すること

#### REQ-LD-403: 環境変数制御 🟡

**信頼性**: 🟡 *REQ-LD-403 より*

**検証内容**: フォールバックの有効/無効は `ENVIRONMENT` 環境変数のみで制御されており、コード内にハードコーディングされた環境判定がないこと

- **参照したEARS要件**: REQ-LD-061, REQ-LD-062, REQ-LD-063, REQ-LD-064, EDGE-LD-003, EDGE-LD-102
- **参照した設計文書**: architecture.md セクションA

---

## 5. EARS要件・設計文書との対応関係

### 参照したユーザストーリー
- **ストーリー 2.2**: 認証付き API をローカルで呼び出す（`docs/spec/local-dev-environment/user-stories.md`）

### 参照した機能要件
- **REQ-LD-061**: dev環境 JWT フォールバック（Authorization ヘッダーから JWT デコード）
- **REQ-LD-062**: sub クレームをユーザーIDとして使用
- **REQ-LD-063**: dev環境以外ではフォールバック無効化
- **REQ-LD-064**: base64url デコードのみ、署名検証なし

### 参照した条件付き要件
- **REQ-LD-101**: authorizer context が利用可能な場合はフォールバック不使用

### 参照した制約要件
- **REQ-LD-401**: 既存 251 テストへの影響なし
- **REQ-LD-403**: ENVIRONMENT 環境変数のみで制御

### 参照した非機能要件
- **NFR-LD-101**: JWT フォールバックの本番非適用（セキュリティ）

### 参照したEdgeケース
- **EDGE-LD-003**: 不正な JWT 形式での安全な失敗
- **EDGE-LD-102**: Bearer プレフィックスなしでのフォールバックスキップ

### 参照した受け入れ基準
- **TC-LD-061-01**: 正規の Keycloak トークンからユーザー ID を抽出
- **TC-LD-061-02**: authorizer context がある場合はフォールバック不使用
- **TC-LD-061-E01**: Authorization ヘッダーなし → 401
- **TC-LD-061-E02**: JWT が不正な形式 → 401
- **TC-LD-061-E03**: base64 デコード失敗 → 401
- **TC-LD-061-B01**: ENVIRONMENT != "dev" → フォールバック無効
- **TC-LD-061-B02**: Bearer プレフィックスなし → フォールバックスキップ

### 参照した設計文書
- **アーキテクチャ**: `docs/design/local-dev-environment/architecture.md` セクションA「JWT フォールバック設計」
- **型定義**: なし（Python バックエンド、Pydantic モデル）
- **データベース**: なし（認証ヘルパーのためDB非関与）
- **API仕様**: `backend/src/api/handler.py` L61-99（実装済みコード）

---

## 6. テスト対象コード

### 対象関数

```python
# backend/src/api/handler.py L61-99

def get_user_id_from_context() -> str:
    """Extract user_id from JWT claims in request context."""
    try:
        claims = app.current_event.request_context.authorizer
        if claims and "jwt" in claims:
            return claims["jwt"]["claims"]["sub"]
        if claims and "claims" in claims:
            return claims["claims"]["sub"]
        if claims and "sub" in claims:
            return claims["sub"]
    except (KeyError, TypeError, AttributeError) as e:
        logger.warning(f"Failed to extract user_id from authorizer context: {e}")

    if os.environ.get("ENVIRONMENT") == "dev":
        try:
            auth_header = app.current_event.get_header_value("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]
                payload = token.split(".")[1]
                payload += "=" * (4 - len(payload) % 4)
                decoded = json.loads(base64.urlsafe_b64decode(payload))
                return decoded["sub"]
        except (KeyError, IndexError, ValueError, Exception) as e:
            logger.error(f"Failed to decode JWT from Authorization header: {e}")

    raise UnauthorizedError("Unable to extract user ID from token")
```

### テストファイル配置先

```
backend/tests/unit/test_handler_jwt_fallback.py
```

### テスト環境の注意事項

- `conftest.py` で `ENVIRONMENT="test"` が設定されている → dev フォールバックテストでは `monkeypatch.setenv("ENVIRONMENT", "dev")` で上書きが必要
- 既存テストは `get_user_id_from_context()` を mock しているため、新テストとの競合はない
- `api_gateway_event` fixture で authorizer context を制御可能（`user_id` パラメータ）

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 | 該当項目 |
|--------|------|------|---------|
| 🔵 青信号 | 14件 | 70% | 機能概要、入出力仕様、セキュリティ要件、互換性要件、正常系、authorizer優先、本番無効化、既存テスト互換、テスト対象コード |
| 🟡 黄信号 | 6件 | 30% | 環境変数制約、ヘッダーなし、Bearerなし、不正base64、sub不在、環境変数制御確認 |
| 🔴 赤信号 | 0件 | 0% | なし |

**品質評価**: ✅ 高品質（青信号 70%、赤信号なし。全項目がEARS要件定義書・設計文書・実装済みコードに基づく）

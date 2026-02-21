# TASK-0045 TDD テストケース: レスポンスDTO統一 + unlinkLine API使用

**作成日**: 2026-02-21
**対象タスク**: [TASK-0045.md](../../tasks/code-review-fixes-v2/TASK-0045.md)
**関連要件**: [requirements.md](requirements.md) - EARS-045-001~026
**TDD段階**: テストケース定義 (RED フェーズ準備)

---

## テストケース凡例

| 項目 | 説明 |
|------|------|
| **Given** | テスト前提条件 (初期状態) |
| **When** | テスト実行アクション (トリガー) |
| **Then** | 期待される結果 (検証内容) |
| **信頼性** | テストケースの根拠の確実性レベル |

**信頼性レベル**:

- **青**: コード分析・API仕様・要件定義から確実に特定された検証項目
- **黄**: 設計文書・コードパターンから妥当な推測による検証項目
- **赤**: 明確な根拠がない推測による検証項目

---

## バックエンドテストケース

### TC-01: PUT /users/me/settings が {success: true, data: User} 形式を返却する

**テストファイル**: `backend/tests/unit/test_handler_settings_response.py`
**関連要件**: EARS-045-001, EARS-045-003
**信頼性**: 青 - handler.py L191-197 が `UserSettingsResponse(success, settings)` を返却している現状を確認済み。api-endpoints.md の変更後レスポンス仕様で `{success, data: User}` 形式が明示されている。

**Given**:
- 認証済みユーザー (user_id: "test-user-id") が DynamoDB に存在する
- ユーザーの初期設定: notification_time="09:00", timezone="Asia/Tokyo"

**When**:
- PUT `/users/me/settings` に `{"notification_time": "21:00", "timezone": "UTC"}` を送信する

**Then**:
- HTTP ステータスコード 200 が返る
- レスポンスボディに `success` キーが存在し、値が `true` である
- レスポンスボディに `data` キーが存在する
- レスポンスボディに `settings` キーが存在しない (旧形式の否定)
- `data.notification_time` が `"21:00"` である
- `data.timezone` が `"UTC"` である
- `data.user_id` が `"test-user-id"` である

```python
class TestUpdateSettingsResponse:
    """TC-01: PUT /users/me/settings が {success: true, data: User} 形式を返却する."""

    def test_update_settings_returns_data_not_settings(
        self, api_gateway_event, lambda_context
    ):
        """設定更新レスポンスが data フィールドを使用し settings フィールドを使用しない.

        【テスト目的】: レスポンス形式が旧 {success, settings} から新 {success, data} に変更されていることを検証
        【期待される動作】: レスポンスに data キーが存在し settings キーが存在しない
        青 信頼性レベル: EARS-045-001, api-endpoints.md の PUT /users/me/settings 変更後仕様
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

            # update_settings 後に get_user で最新ユーザーを取得する想定
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

        # 新形式の検証
        assert "success" in body
        assert body["success"] is True
        assert "data" in body
        assert body["data"]["notification_time"] == "21:00"
        assert body["data"]["timezone"] == "UTC"
        assert body["data"]["user_id"] == "test-user-id"

        # 旧形式の否定検証
        assert "settings" not in body
```

---

### TC-02: update_settings レスポンスが全 User フィールドを含む

**テストファイル**: `backend/tests/unit/test_handler_settings_response.py`
**関連要件**: EARS-045-002, EARS-045-004, EARS-045-005
**信頼性**: 青 - backend/src/models/user.py L68-78 の `UserResponse` モデル定義で 8 フィールドが明示されている。api-endpoints.md のレスポンス仕様と完全一致。

**Given**:
- 認証済みユーザー (user_id: "test-user-id") が DynamoDB に存在する
- ユーザーは LINE 連携済み (line_user_id: "U1234567890abcdef")
- display_name: "テストユーザー", picture_url: null
- notification_time: "09:00", timezone: "Asia/Tokyo"
- created_at, updated_at が ISO 8601 形式で設定済み

**When**:
- PUT `/users/me/settings` に `{"notification_time": "21:00"}` を送信する

**Then**:
- レスポンスの `data` オブジェクトに以下のフィールドがすべて含まれる:
  - `user_id` (string): "test-user-id"
  - `display_name` (string|null): "テストユーザー"
  - `picture_url` (string|null): null
  - `line_linked` (boolean): true (LINE 連携済みのため)
  - `notification_time` (string): "21:00" (更新後の値)
  - `timezone` (string): "Asia/Tokyo" (IANA タイムゾーン形式)
  - `created_at` (string): ISO 8601 datetime 形式
  - `updated_at` (string|null): ISO 8601 datetime 形式

```python
    def test_update_settings_includes_all_user_fields(
        self, api_gateway_event, lambda_context
    ):
        """設定更新レスポンスに UserResponse の全8フィールドが含まれること.

        【テスト目的】: data オブジェクトが UserResponse 型の全フィールドを持つことを検証
        【期待される動作】: user_id, display_name, picture_url, line_linked,
                          notification_time, timezone, created_at, updated_at が存在する
        青 信頼性レベル: EARS-045-002, UserResponse Pydantic モデル定義 (user.py L68-78)
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
            assert field in data, f"Missing field: {field}"

        # LINE 連携済みの場合 line_linked は true
        assert data["line_linked"] is True

        # timezone が IANA 形式であること
        assert isinstance(data["timezone"], str)
        assert "/" in data["timezone"] or data["timezone"] == "UTC"
```

---

### TC-03: update_settings レスポンスが更新後の値を正しく反映する

**テストファイル**: `backend/tests/unit/test_handler_settings_response.py`
**関連要件**: EARS-045-003
**信頼性**: 青 - api-endpoints.md の PUT `/users/me/settings` レスポンス仕様。更新後の最新状態を返却する設計が明示されている。

**Given**:
- 認証済みユーザーが存在する
- 初期設定: notification_time="09:00", timezone="Asia/Tokyo"

**When**:
- PUT `/users/me/settings` に `{"notification_time": "21:00", "timezone": "UTC"}` を送信する

**Then**:
- `data.notification_time` が `"21:00"` (更新後の値) である
- `data.timezone` が `"UTC"` (更新後の値) である
- `data.user_id` は初期値のまま変更されていない

```python
    def test_update_settings_reflects_updated_values(
        self, api_gateway_event, lambda_context
    ):
        """設定更新レスポンスが更新後の値を正しく反映すること.

        【テスト目的】: notification_time と timezone の更新値がレスポンスに反映されることを検証
        【期待される動作】: 送信した設定値がレスポンスの data に反映される
        青 信頼性レベル: EARS-045-003
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
        data = body["data"]

        # 更新後の値が反映されていること
        assert data["notification_time"] == "21:00"
        assert data["timezone"] == "UTC"

        # user_id は変更されていないこと
        assert data["user_id"] == "test-user-id"
```

---

### TC-04: POST /users/me/unlink-line が {success: true, data: User} を返却し line_linked が false

**テストファイル**: `backend/tests/unit/test_handler_unlink_line_response.py`
**関連要件**: EARS-045-007
**信頼性**: 青 - handler.py L212-214 の現在の実装が `{"success": True, "data": result}` (result は dict) を返却しており、User 型に変更する要件が api-endpoints.md で明示されている。

**Given**:
- 認証済みユーザー (user_id: "test-user-id") が DynamoDB に存在する
- ユーザーは LINE 連携済み (line_user_id: "U1234567890abcdef")

**When**:
- POST `/users/me/unlink-line` を送信する (リクエストボディなし)

**Then**:
- HTTP ステータスコード 200 が返る
- レスポンスボディに `success` キーが存在し、値が `true` である
- レスポンスボディに `data` キーが存在する
- `data.user_id` が `"test-user-id"` である
- `data.line_linked` が `false` である (連携解除後)
- `data` に `unlinked_at` キーが存在しない (旧形式の否定)

```python
class TestUnlinkLineResponse:
    """TC-04~05: POST /users/me/unlink-line が User 型レスポンスを返却する."""

    def test_unlink_line_returns_user_response_with_line_linked_false(
        self, api_gateway_event, lambda_context
    ):
        """LINE連携解除レスポンスが {success: true, data: User} 形式で line_linked=false を含む.

        【テスト目的】: unlink_line が User 型の data を返却し line_linked が false であることを検証
        【期待される動作】: data に UserResponse 構造が含まれ line_linked が false
        青 信頼性レベル: EARS-045-007, api-endpoints.md POST /users/me/unlink-line レスポンス仕様
        """
        event = api_gateway_event(
            method="POST",
            path="/users/me/unlink-line",
            user_id="test-user-id",
        )

        with patch("src.api.handler.user_service") as mock_user_service:
            # unlink_line が User オブジェクトを返すようにモック
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
        assert "data" in body
        assert body["data"]["user_id"] == "test-user-id"
        assert body["data"]["line_linked"] is False

        # 旧形式の否定検証
        assert "unlinked_at" not in body.get("data", {})
```

---

### TC-05: unlink_line レスポンスが全 User フィールドを含む

**テストファイル**: `backend/tests/unit/test_handler_unlink_line_response.py`
**関連要件**: EARS-045-008
**信頼性**: 青 - api-endpoints.md の POST `/users/me/unlink-line` レスポンス仕様で全 User フィールドが明示されている。

**Given**:
- 認証済み・LINE 連携済みユーザーが存在する
- display_name: "テストユーザー", notification_time: "09:00", timezone: "Asia/Tokyo"

**When**:
- POST `/users/me/unlink-line` を送信する

**Then**:
- レスポンスの `data` オブジェクトに以下の全フィールドが含まれる:
  - `user_id` (string)
  - `display_name` (string|null)
  - `picture_url` (string|null)
  - `line_linked` (boolean): false
  - `notification_time` (string)
  - `timezone` (string)
  - `created_at` (string): ISO 8601 datetime
  - `updated_at` (string|null): ISO 8601 datetime

```python
    def test_unlink_line_includes_all_user_fields(
        self, api_gateway_event, lambda_context
    ):
        """LINE連携解除レスポンスに UserResponse の全8フィールドが含まれること.

        【テスト目的】: data オブジェクトが UserResponse 型の全フィールドを持つことを検証
        【期待される動作】: 旧形式の {user_id, unlinked_at} ではなく UserResponse 全フィールドが返る
        青 信頼性レベル: EARS-045-008
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
            assert field in data, f"Missing field: {field}"

        # line_linked は false であること (連携解除後)
        assert data["line_linked"] is False
```

---

### TC-06: レスポンス形式の一貫性 (GET /users/me, PUT /users/me/settings, POST /users/link-line, POST /users/me/unlink-line)

**テストファイル**: `backend/tests/unit/test_handler_response_consistency.py`
**関連要件**: EARS-045-021, EARS-045-022
**信頼性**: 青 - api-endpoints.md の全変更後レスポンス仕様で `{success: true, data: UserResponse}` 形式が全エンドポイントに要求されている。GET /users/me のラッパー追加について設計判断が必要な点は黄信号。

**Given**:
- 認証済み・LINE 連携済みユーザーが存在する

**When**:
- 以下の 4 エンドポイントをそれぞれ呼び出す:
  1. GET `/users/me`
  2. PUT `/users/me/settings` (body: `{"notification_time": "21:00"}`)
  3. POST `/users/link-line` (body: `{"id_token": "valid-token"}`)
  4. POST `/users/me/unlink-line`

**Then**:
- PUT `/users/me/settings` のレスポンスが `{success: true, data: <UserResponse>}` 形式である
- POST `/users/me/unlink-line` のレスポンスが `{success: true, data: <UserResponse>}` 形式である
- 各レスポンスの `data` オブジェクトが同一のフィールドセット (8 フィールド) を持つ
- 各フィールドの型が一貫している (user_id: string, line_linked: boolean, etc.)

**注意**: GET `/users/me` は現在 `to_response().model_dump()` を直接返却 (ラッパーなし)。本テストケースでは PUT と POST の 2 エンドポイントの一貫性を主に検証する。GET のラッパー統一は設計判断待ち。

```python
class TestResponseConsistency:
    """TC-06: レスポンス形式の一貫性検証."""

    def test_settings_and_unlink_return_same_user_structure(
        self, api_gateway_event, lambda_context
    ):
        """PUT /users/me/settings と POST /users/me/unlink-line が同じ User 構造を返す.

        【テスト目的】: 変更対象の2エンドポイントが同一の UserResponse フィールドセットを返すことを検証
        【期待される動作】: 両方のレスポンスの data に同一の8フィールドが含まれる
        青 信頼性レベル: EARS-045-021, EARS-045-022
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

            response = handler(unlink_event, lambda_context)

        unlink_body = json.loads(response["body"])
        unlink_data_keys = set(unlink_body["data"].keys())

        # 両方のレスポンスが同じフィールドセットを持つことを検証
        assert settings_data_keys == user_response_fields, (
            f"Settings response fields mismatch: {settings_data_keys}"
        )
        assert unlink_data_keys == user_response_fields, (
            f"Unlink response fields mismatch: {unlink_data_keys}"
        )
        assert settings_data_keys == unlink_data_keys, (
            "Settings and unlink responses have different field sets"
        )
```

---

### TC-06b: user_service.unlink_line がUser型を返却する (サービス層テスト)

**テストファイル**: `backend/tests/unit/test_user_service_unlink.py`
**関連要件**: EARS-045-006
**信頼性**: 青 - user_service.py L311 の現在の戻り値型が `dict` であり、User 型に変更する要件が note.md セクション 8.2 の実装 2 で明示されている。

**Given**:
- DynamoDB テーブルにユーザー (user_id: "test-user-id") が存在する
- ユーザーは LINE 連携済み (line_user_id: "U1234567890abcdef")

**When**:
- `user_service.unlink_line("test-user-id")` を呼び出す

**Then**:
- 戻り値が `User` 型のインスタンスである (dict ではない)
- 戻り値の `user_id` が `"test-user-id"` である
- 戻り値の `line_user_id` が `None` である (連携解除後)

```python
class TestUnlinkLineServiceReturn:
    """TC-06b: user_service.unlink_line が User 型を返却する."""

    def test_unlink_line_returns_user_not_dict(self, user_service, dynamodb_resource):
        """unlink_line がUser型オブジェクトを返すことを検証する.

        【テスト目的】: 戻り値が dict ではなく User 型であることを検証
        【期待される動作】: User インスタンスが返り、line_user_id が None
        青 信頼性レベル: EARS-045-006
        """
        from src.models.user import User

        # Given: LINE連携済みユーザーを作成
        user_service.create_user(user_id="test-user-id")
        user_service.link_line(user_id="test-user-id", line_user_id="U1234567890abcdef")

        # When: unlink_line を呼び出す
        result = user_service.unlink_line("test-user-id")

        # Then: 戻り値が User 型であること
        assert isinstance(result, User), f"Expected User instance, got {type(result)}"
        assert result.user_id == "test-user-id"
        assert result.line_user_id is None
```

---

## フロントエンドテストケース

### TC-07: unlinkLine API メソッドが POST /users/me/unlink-line を呼び出す

**テストファイル**: `frontend/src/services/__tests__/api.test.ts`
**関連要件**: EARS-045-011, EARS-045-012, EARS-045-013, EARS-045-014
**信頼性**: 青 - api-endpoints.md の POST `/users/me/unlink-line` 仕様、handler.py L205 の `@app.post("/users/me/unlink-line")` と一致。api.ts に `unlinkLine` メソッドが現在存在しないことを確認済み。

**Given**:
- ApiClient がインスタンス化されている
- アクセストークンがセットされている
- fetch がモックされている

**When**:
- `apiClient.unlinkLine()` を呼び出す

**Then**:
- fetch が `POST ${API_BASE_URL}/users/me/unlink-line` で呼ばれる
- fetch のリクエストに `body` が含まれない (リクエストボディなし)
- fetch の `method` が `"POST"` である
- fetch の `headers` に `Authorization` ヘッダーが含まれる
- 戻り値が `User` 型として解決される

```typescript
describe('TC-07: unlinkLine API メソッド', () => {
  it('POST /users/me/unlink-line を呼び出すこと', async () => {
    /**
     * 【テスト目的】: unlinkLine メソッドが正しいエンドポイントと HTTP メソッドを使用することを検証
     * 【期待される動作】: POST /users/me/unlink-line が呼ばれ、リクエストボディがない
     * 青 信頼性レベル: EARS-045-011, EARS-045-013, EARS-045-014
     */
    const mockResponse: User = {
      user_id: 'test-user-id',
      display_name: 'テストユーザー',
      picture_url: null,
      line_linked: false,
      notification_time: '09:00',
      timezone: 'Asia/Tokyo',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockResponse),
    });

    apiClient.setAccessToken('test-token');
    const result = await apiClient.unlinkLine();

    // fetch が正しいエンドポイントで呼ばれたか
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining('/users/me/unlink-line'),
      expect.objectContaining({
        method: 'POST',
      })
    );

    // リクエストボディがないこと
    const fetchCall = (fetch as vi.Mock).mock.calls[0][1];
    expect(fetchCall.body).toBeUndefined();

    // Authorization ヘッダーが含まれること
    expect(fetchCall.headers).toHaveProperty('Authorization', 'Bearer test-token');

    // 戻り値が User 型であること
    expect(result).toEqual(mockResponse);
    expect(result.line_linked).toBe(false);
  });

  it('usersApi.unlinkLine が apiClient.unlinkLine に委譲すること', () => {
    /**
     * 【テスト目的】: usersApi エクスポートに unlinkLine が含まれることを検証
     * 青 信頼性レベル: EARS-045-012
     */
    expect(usersApi).toHaveProperty('unlinkLine');
    expect(typeof usersApi.unlinkLine).toBe('function');
  });
});
```

---

### TC-08: LinkLinePage が unlinkLine (updateUser ではない) を呼び出す

**テストファイル**: `frontend/src/pages/__tests__/LinkLinePage.test.tsx`
**関連要件**: EARS-045-015, EARS-045-016
**信頼性**: 青 - LinkLinePage.tsx L101-103 で `usersApi.updateUser()` を呼び出している現状を確認済み。REQ-V2-033 で専用エンドポイントの使用が要求されている。

**Given**:
- LINE 連携済みユーザーがログイン中
- usersApi.getCurrentUser が `{line_linked: true, ...}` を返す
- usersApi.unlinkLine がモックされている
- usersApi.updateUser がモックされている

**When**:
- LINE 連携解除ボタン (data-testid="unlink-button") をクリックする

**Then**:
- `usersApi.unlinkLine()` が呼び出される
- `usersApi.updateUser()` が呼び出されない
- 成功メッセージ「LINE連携を解除しました」が表示される
- ユーザー状態がサーバーレスポンスでそのまま更新される (手動で `line_linked: false` を上書きしない)

```typescript
describe('TC-08: LinkLinePage が unlinkLine を使用', () => {
  const mockUnlinkLine = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    // usersApi モックに unlinkLine を追加
    // vi.mock 内で mockUnlinkLine を定義
  });

  it('LINE連携解除ボタンクリックで unlinkLine が呼ばれ updateUser が呼ばれないこと', async () => {
    /**
     * 【テスト目的】: handleUnlinkLine が updateUser ではなく unlinkLine を呼ぶことを検証
     * 【期待される動作】: unlinkLine が1回呼ばれ、updateUser は呼ばれない
     * 青 信頼性レベル: EARS-045-015
     */
    const linkedUser: User = {
      user_id: 'user-1',
      display_name: 'テストユーザー',
      picture_url: null,
      line_linked: true,
      notification_time: '09:00',
      timezone: 'Asia/Tokyo',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    };

    const unlinkedUser: User = {
      ...linkedUser,
      line_linked: false,
      updated_at: '2024-01-02T00:00:00Z',
    };

    mockGetCurrentUser.mockResolvedValue(linkedUser);
    mockUnlinkLine.mockResolvedValue(unlinkedUser);

    renderLinkLinePage();

    await waitFor(() => {
      expect(screen.getByTestId('unlink-button')).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByTestId('unlink-button'));

    await waitFor(() => {
      // unlinkLine が呼ばれること
      expect(mockUnlinkLine).toHaveBeenCalledTimes(1);
      // updateUser が呼ばれないこと
      expect(mockUpdateUser).not.toHaveBeenCalled();
    });
  });

  it('LINE連携解除成功後にサーバーレスポンスで状態更新されること', async () => {
    /**
     * 【テスト目的】: setUser がサーバーレスポンスをそのまま使用することを検証
     *                 手動で line_linked: false を上書きしていないことを確認
     * 青 信頼性レベル: EARS-045-016
     */
    const linkedUser: User = {
      user_id: 'user-1',
      display_name: 'テストユーザー',
      picture_url: null,
      line_linked: true,
      notification_time: '09:00',
      timezone: 'Asia/Tokyo',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    };

    const serverResponse: User = {
      user_id: 'user-1',
      display_name: 'テストユーザー',
      picture_url: null,
      line_linked: false,
      notification_time: '09:00',
      timezone: 'Asia/Tokyo',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
    };

    mockGetCurrentUser.mockResolvedValue(linkedUser);
    mockUnlinkLine.mockResolvedValue(serverResponse);

    renderLinkLinePage();

    await waitFor(() => {
      expect(screen.getByTestId('unlink-button')).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByTestId('unlink-button'));

    // 成功メッセージが表示されること
    await waitFor(() => {
      expect(screen.getByTestId('success-message')).toHaveTextContent(
        'LINE連携を解除しました'
      );
    });

    // 状態が「未連携」に更新されること
    await waitFor(() => {
      expect(screen.getByTestId('link-status')).toHaveTextContent('未連携');
    });
  });
});
```

---

### TC-09: User 型に timezone フィールドが含まれる

**テストファイル**: `frontend/src/types/__tests__/user.test.ts`
**関連要件**: EARS-045-019
**信頼性**: 青 - frontend/src/types/user.ts L7 に `timezone: string` が既に定義されている。バックエンド UserResponse L76 との対応を確認済み。

**Given**:
- TypeScript の User インターフェースが定義されている

**When**:
- User 型のオブジェクトを作成する

**Then**:
- `timezone` フィールドが `string` 型として存在する
- `timezone` フィールドが必須である (optional ではない)
- TypeScript コンパイルエラーが発生しない

```typescript
describe('TC-09: User 型の timezone フィールド', () => {
  it('User 型に timezone フィールドが string 型で含まれること', () => {
    /**
     * 【テスト目的】: User インターフェースに timezone フィールドが存在することを型レベルで検証
     * 【期待される動作】: timezone を含むオブジェクトが User 型として有効
     * 青 信頼性レベル: EARS-045-019
     */
    const user: User = {
      user_id: 'test-user-id',
      display_name: 'テストユーザー',
      picture_url: null,
      line_linked: false,
      notification_time: '09:00',
      timezone: 'Asia/Tokyo',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    };

    expect(user.timezone).toBe('Asia/Tokyo');
    expect(typeof user.timezone).toBe('string');
  });

  it('timezone フィールドが異なるタイムゾーン値を受け入れること', () => {
    /**
     * 【テスト目的】: timezone が各種 IANA タイムゾーン文字列を受け入れることを検証
     * 青 信頼性レベル: EARS-045-019
     */
    const timezones = ['Asia/Tokyo', 'UTC', 'America/New_York', 'Europe/London'];

    timezones.forEach((tz) => {
      const user: User = {
        user_id: 'test-user-id',
        line_linked: false,
        timezone: tz,
        created_at: '2024-01-01T00:00:00Z',
      };
      expect(user.timezone).toBe(tz);
    });
  });
});
```

---

### TC-10: linkLine レスポンスが User 型として正しくパースされる

**テストファイル**: `frontend/src/services/__tests__/api.test.ts`
**関連要件**: EARS-045-010, EARS-045-026
**信頼性**: 青 - api-endpoints.md の POST `/users/link-line` 変更後レスポンス仕様で `{success: true, data: User}` が明示されている。TASK-0044 連携でバックエンドが User 型を返却する前提。

**Given**:
- ApiClient がインスタンス化されている
- fetch がモックされ、バックエンドの新レスポンス形式を返す

**When**:
- `apiClient.linkLine({ id_token: "valid-token" })` を呼び出す

**Then**:
- 戻り値が User 型のフィールドを持つ
- `line_linked` が `true` である
- `timezone` フィールドが存在する
- `user_id` が文字列である

**注意**: 現在の `request<T>` メソッドは `response.json()` を直接返却するため、バックエンドが `{success, data}` ラッパーで返却する場合のフロントエンド側パース処理の設計判断が必要 (EARS-045-026)。このテストケースは設計決定後に詳細を調整する。

```typescript
describe('TC-10: linkLine レスポンスの User 型パース', () => {
  it('linkLine が User 型のレスポンスを返すこと', async () => {
    /**
     * 【テスト目的】: linkLine の戻り値が User 型として正しくパースされることを検証
     * 【期待される動作】: レスポンスが User 型の全フィールドを持つ
     * 青 信頼性レベル: EARS-045-010
     *
     * 注意: バックエンドのレスポンス形式変更 ({success, data} ラッパー) に応じて
     *       フロントエンド側のパース処理を調整する必要がある (EARS-045-026 黄)
     */
    const mockServerResponse = {
      user_id: 'test-user-id',
      display_name: 'テストユーザー',
      picture_url: null,
      line_linked: true,
      notification_time: '09:00',
      timezone: 'Asia/Tokyo',
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-02T00:00:00Z',
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(mockServerResponse),
    });

    apiClient.setAccessToken('test-token');
    const result = await apiClient.linkLine({ id_token: 'valid-token' });

    // User 型の全フィールドが存在すること
    expect(result).toHaveProperty('user_id');
    expect(result).toHaveProperty('line_linked');
    expect(result).toHaveProperty('timezone');
    expect(result).toHaveProperty('notification_time');
    expect(result).toHaveProperty('created_at');
    expect(result).toHaveProperty('updated_at');

    // 値の検証
    expect(result.line_linked).toBe(true);
    expect(result.timezone).toBe('Asia/Tokyo');
    expect(typeof result.user_id).toBe('string');
  });
});
```

---

## テストケースサマリー

### 一覧表

| TC | テスト名 | レイヤー | テストファイル | 関連要件 | 信頼性 |
|----|---------|---------|--------------|---------|--------|
| TC-01 | update_settings が {success, data: User} 形式 | Backend | `backend/tests/unit/test_handler_settings_response.py` | EARS-045-001, 003 | 青 |
| TC-02 | update_settings に全 User フィールド | Backend | `backend/tests/unit/test_handler_settings_response.py` | EARS-045-002, 004, 005 | 青 |
| TC-03 | update_settings が更新値を反映 | Backend | `backend/tests/unit/test_handler_settings_response.py` | EARS-045-003 | 青 |
| TC-04 | unlink-line が {success, data: User} + line_linked=false | Backend | `backend/tests/unit/test_handler_unlink_line_response.py` | EARS-045-007 | 青 |
| TC-05 | unlink-line に全 User フィールド | Backend | `backend/tests/unit/test_handler_unlink_line_response.py` | EARS-045-008 | 青 |
| TC-06 | 4 エンドポイントのレスポンス一貫性 | Backend | `backend/tests/unit/test_handler_response_consistency.py` | EARS-045-021, 022 | 青 |
| TC-06b | user_service.unlink_line が User 型返却 | Backend | `backend/tests/unit/test_user_service_unlink.py` | EARS-045-006 | 青 |
| TC-07 | unlinkLine API が POST /users/me/unlink-line を呼出 | Frontend | `frontend/src/services/__tests__/api.test.ts` | EARS-045-011~014 | 青 |
| TC-08 | LinkLinePage が unlinkLine を使用 (updateUser 不使用) | Frontend | `frontend/src/pages/__tests__/LinkLinePage.test.tsx` | EARS-045-015, 016 | 青 |
| TC-09 | User 型に timezone フィールド | Frontend | `frontend/src/types/__tests__/user.test.ts` | EARS-045-019 | 青 |
| TC-10 | linkLine レスポンスが User 型パース | Frontend | `frontend/src/services/__tests__/api.test.ts` | EARS-045-010, 026 | 青 |

### 信頼性レベルサマリー

| レベル | テストケース数 | 割合 |
|--------|-------------|------|
| 青 (確実な定義) | 11 | 100% |
| 黄 (妥当な推測) | 0 | 0% |
| 赤 (確実でない推測) | 0 | 0% |

### EARS 要件カバレッジ

| 要件 ID | カバーする TC |
|---------|-------------|
| EARS-045-001 | TC-01 |
| EARS-045-002 | TC-02 |
| EARS-045-003 | TC-01, TC-03 |
| EARS-045-004 | TC-02 |
| EARS-045-005 | TC-02 |
| EARS-045-006 | TC-06b |
| EARS-045-007 | TC-04 |
| EARS-045-008 | TC-05 |
| EARS-045-009 | (既存テストで対応可能: handler.py L215-220) |
| EARS-045-010 | TC-10 |
| EARS-045-011 | TC-07 |
| EARS-045-012 | TC-07 |
| EARS-045-013 | TC-07 |
| EARS-045-014 | TC-07 |
| EARS-045-015 | TC-08 |
| EARS-045-016 | TC-08 |
| EARS-045-017 | (既存テスト「テストケース7」で対応済み) |
| EARS-045-018 | (既存テスト「ローディング状態」で対応済み) |
| EARS-045-019 | TC-09 |
| EARS-045-020 | (型定義のみ、ランタイムテスト不要) |
| EARS-045-021 | TC-06 |
| EARS-045-022 | TC-06 |
| EARS-045-023 | (既存バリデーションテストで対応可能) |
| EARS-045-024 | (既存バリデーションテストで対応可能) |
| EARS-045-025 | (既存エラーハンドリングテストで対応可能) |
| EARS-045-026 | TC-10 (設計判断後に詳細調整) |

---

## テスト実装時の注意事項

### 1. バックエンドテストのモック戦略

既存テスト (`test_handler_link_line.py`) のパターンに従い、以下のモック戦略を使用する:

```python
with patch("src.api.handler.user_service") as mock_user_service, \
     patch("src.api.handler.line_service") as mock_line_service:
    # user_service と line_service をモックした上でハンドラーを呼び出す
    from src.api.handler import handler
    response = handler(event, lambda_context)
```

- `user_service.unlink_line` の戻り値は `User` オブジェクト (修正後) を `MagicMock` で模倣
- `User.to_response()` → `UserResponse.model_dump(mode="json")` のチェーンをモック

### 2. フロントエンドテストのモック追加

既存テスト (`LinkLinePage.test.tsx`) のモック定義に `mockUnlinkLine` を追加する必要がある:

```typescript
const mockUnlinkLine = vi.fn();

vi.mock('@/services/api', () => ({
  usersApi: {
    getCurrentUser: () => mockGetCurrentUser(),
    updateUser: (...args: unknown[]) => mockUpdateUser(...args),
    linkLine: (...args: unknown[]) => mockLinkLine(...args),
    unlinkLine: () => mockUnlinkLine(),  // 新規追加
  },
}));
```

### 3. RED フェーズでの失敗確認ポイント

各テストケースが RED フェーズで失敗する理由:

| TC | 失敗理由 |
|----|---------|
| TC-01 | handler.py L191 が `UserSettingsResponse` を返却し `data` キーが存在しない |
| TC-02 | `data` キーが存在しないためフィールド検証に到達できない |
| TC-03 | TC-01 と同一の理由 |
| TC-04 | handler.py L214 が `{"success": True, "data": dict}` を返却し User 型ではない |
| TC-05 | `data` が dict 形式で UserResponse フィールドが欠落 |
| TC-06 | TC-01, TC-04 の合わせ技 |
| TC-06b | user_service.py L332 が `dict` を返却し `User` ではない |
| TC-07 | api.ts に `unlinkLine` メソッドが存在しない |
| TC-08 | LinkLinePage.tsx L101 が `updateUser` を呼んでいる |
| TC-09 | 既にパスする可能性あり (user.ts L7 に timezone 定義済み) |
| TC-10 | レスポンス形式の変更がまだ反映されていない |

### 4. 設計判断が必要な項目

| 項目 | 判断内容 | 影響する TC |
|------|---------|-----------|
| GET /users/me のラッパー | `{success, data}` ラッパーを追加するか | TC-06 |
| フロントエンドの data 抽出 | `request<T>` で data フィールドを自動抽出するか | TC-07, TC-08, TC-10 |
| UserSettingsResponse 削除 | 不要になったモデルを削除するか | TC-01 (REFACTOR) |

---

**作成者**: Claude Code
**最終更新**: 2026-02-21

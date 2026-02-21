# TASK-0045 TDD要件定義: レスポンスDTO統一 + unlinkLine API使用

**作成日**: 2026-02-21
**対象タスク**: [TASK-0045.md](../../tasks/code-review-fixes-v2/TASK-0045.md)
**関連要件**: REQ-V2-031, REQ-V2-032, REQ-V2-033
**TDD段階**: 要件定義 (EARS記法)

---

## EARS記法凡例

本文書では EARS (Easy Approach to Requirements Syntax) 記法を使用する。

| パターン | 構文 | 用途 |
|---------|------|------|
| **Ubiquitous** | The `<system>` shall `<action>` | 常に成立する要件 |
| **Event-Driven** | When `<trigger>`, the `<system>` shall `<action>` | イベント駆動の要件 |
| **State-Driven** | While `<state>`, the `<system>` shall `<action>` | 状態依存の要件 |
| **Unwanted Behaviour** | If `<condition>`, then the `<system>` shall `<action>` | 異常系の要件 |
| **Optional Feature** | Where `<feature>`, the `<system>` shall `<action>` | オプション機能の要件 |

**信頼性レベル**:

- 🔵 **青信号**: コードレビュー結果・既存コード・設計文書・API仕様から確実に特定された要件
- 🟡 **黄信号**: 設計文書・コードパターンから妥当な推測による要件
- 🔴 **赤信号**: 明確な根拠がない推測による要件

---

## 1. バックエンド要件: update_settings レスポンス統一

### EARS-045-001: update_settings レスポンス形式 🔵

**パターン**: Event-Driven

> When an authenticated user sends a PUT request to `/users/me/settings` with valid settings data, the system shall return a response body containing `{"success": true, "data": <UserResponse>}` where `<UserResponse>` is a User type object.

**根拠**: handler.py L191-197 が `UserSettingsResponse(success=True, settings={...})` を返却しているが、frontend api.ts L141-146 の `updateUser()` は `User` 型を期待している。api-endpoints.md の変更後レスポンス仕様に準拠。

**検証方法**: PUT `/users/me/settings` のレスポンスボディに `data` キーが存在し、その値が UserResponse 構造であること。

**現状コード** (`handler.py` L191-197):
```python
return UserSettingsResponse(
    success=True,
    settings={
        "notification_time": user.settings.get("notification_time"),
        "timezone": user.settings.get("timezone"),
    },
).model_dump()
```

**期待コード**:
```python
return {
    "success": True,
    "data": user.to_response().model_dump(mode="json")
}
```

---

### EARS-045-002: update_settings レスポンスの全フィールド包含 🔵

**パターン**: Ubiquitous

> The update_settings response `data` object shall contain all UserResponse fields: `user_id` (string), `display_name` (string|null), `picture_url` (string|null), `line_linked` (boolean), `notification_time` (string|null), `timezone` (string), `created_at` (ISO 8601 datetime), `updated_at` (ISO 8601 datetime|null).

**根拠**: backend/src/models/user.py L68-78 の `UserResponse` モデル定義。api-endpoints.md のレスポンス仕様で全フィールドが明示されている。

**検証方法**: レスポンス `data` に上記8フィールドすべてが含まれ、型が正しいこと。

---

### EARS-045-003: update_settings レスポンスの設定値反映 🔵

**パターン**: Event-Driven

> When a user updates `notification_time` to "21:00" via PUT `/users/me/settings`, the system shall return a response where `data.notification_time` equals "21:00" and other User fields retain their current values.

**根拠**: api-endpoints.md の PUT `/users/me/settings` レスポンス仕様。更新後の最新状態を返却する設計。

**検証方法**: 更新リクエストで送信した値がレスポンスの `data` に正しく反映されていること。

---

### EARS-045-004: update_settings レスポンスの timezone フィールド 🔵

**パターン**: Ubiquitous

> The update_settings response `data` object shall include a `timezone` field containing a valid IANA timezone string.

**根拠**: backend/src/models/user.py L76 の `UserResponse.timezone: str = "Asia/Tokyo"`。H-03対応で追加されたフィールド。api-endpoints.md の User 型定義に `timezone` が明記。

**検証方法**: レスポンス `data.timezone` が文字列であり、IANA形式 (例: "Asia/Tokyo", "UTC") であること。

---

### EARS-045-005: update_settings で LINE連携済みユーザーの line_linked 反映 🔵

**パターン**: State-Driven

> While a user has a linked LINE account, the update_settings response `data.line_linked` shall be `true`.

**根拠**: backend/src/models/user.py L99 の `to_response()` で `line_linked=self.line_user_id is not None` と変換している。レスポンスは `line_user_id` ではなく `line_linked` boolean を返却する設計。

**検証方法**: LINE連携済みユーザーで設定更新後、`data.line_linked` が `true` であること。

---

## 2. バックエンド要件: unlink_line レスポンス統一

### EARS-045-006: unlink_line サービス層の戻り値型変更 🔵

**パターン**: Event-Driven

> When `user_service.unlink_line(user_id)` is called successfully, the method shall return a `User` object (not a dict) representing the user's state after LINE account unlinking.

**根拠**: user_service.py L311 の現在の戻り値型が `dict` (`{"user_id": ..., "unlinked_at": ...}`) であり、User 型に統一する必要がある。note.md セクション 8.2 の実装 2 で明示。

**現状コード** (`user_service.py` L311-332):
```python
def unlink_line(self, user_id: str) -> dict:
    ...
    return {"user_id": user_id, "unlinked_at": now.isoformat()}
```

**期待コード**:
```python
def unlink_line(self, user_id: str) -> User:
    ...
    return self.get_user(user_id)
```

---

### EARS-045-007: unlink_line ハンドラーのレスポンス形式 🔵

**パターン**: Event-Driven

> When an authenticated user sends a POST request to `/users/me/unlink-line` and the user has a linked LINE account, the system shall return a response body containing `{"success": true, "data": <UserResponse>}` where `data.line_linked` is `false`.

**根拠**: handler.py L212-214 の現在の実装が `{"success": True, "data": result}` (result は dict) を返却している。api-endpoints.md のレスポンス仕様でUser型に統一。

**現状コード** (`handler.py` L212-214):
```python
result = user_service.unlink_line(user_id)
return {"success": True, "data": result}
```

**期待コード**:
```python
user = user_service.unlink_line(user_id)
return {
    "success": True,
    "data": user.to_response().model_dump(mode="json")
}
```

---

### EARS-045-008: unlink_line レスポンスの全フィールド包含 🔵

**パターン**: Ubiquitous

> The unlink_line response `data` object shall contain all UserResponse fields: `user_id`, `display_name`, `picture_url`, `line_linked` (= false), `notification_time`, `timezone`, `created_at`, `updated_at`.

**根拠**: api-endpoints.md の POST `/users/me/unlink-line` レスポンス仕様。全エンドポイントで統一されたUser型を返却する設計。

**検証方法**: レスポンス `data` に8フィールドすべてが含まれ、`line_linked` が `false` であること。

---

### EARS-045-009: unlink_line の LINE未連携エラー 🔵

**パターン**: Unwanted Behaviour

> If a user without a linked LINE account sends a POST request to `/users/me/unlink-line`, then the system shall return HTTP 400 with `{"error": "LINE account not linked"}`.

**根拠**: handler.py L215-220 の既存エラーハンドリング。user_service.py L334-335 の `LineNotLinkedError` 例外。

**検証方法**: LINE未連携ユーザーで unlink_line を呼び出し、400エラーが返ること。

---

## 3. バックエンド要件: link_line レスポンス統一 (TASK-0044連携確認)

### EARS-045-010: link_line レスポンス形式確認 🔵

**パターン**: Event-Driven

> When an authenticated user sends a POST request to `/users/link-line` with a valid `id_token` and the linking succeeds, the system shall return a response body containing `{"success": true, "data": <UserResponse>}` where `data.line_linked` is `true`.

**根拠**: handler.py L138 の現在の実装が `LinkLineResponse(success=True, message=...)` を返却している。TASK-0044 で修正予定。api-endpoints.md の変更後レスポンス仕様に準拠。

**注意**: この要件はTASK-0044の修正範囲であるが、TASK-0045のレスポンスDTO統一の一貫性検証として確認する。

---

## 4. フロントエンド要件: unlinkLine APIメソッド追加

### EARS-045-011: ApiClient に unlinkLine メソッドを追加 🔵

**パターン**: Ubiquitous

> The ApiClient class shall provide an `unlinkLine()` method that sends a POST request to `/users/me/unlink-line` and returns a `Promise<User>`.

**根拠**: frontend/src/services/api.ts に `unlinkLine` メソッドが存在しない。REQ-V2-033 でフロントエンドが専用エンドポイントを使用する要件。api-endpoints.md のフロントエンド修正仕様。

**期待コード** (`api.ts` ApiClient内):
```typescript
async unlinkLine(): Promise<User> {
  return this.request<User>('/users/me/unlink-line', {
    method: 'POST',
  });
}
```

---

### EARS-045-012: usersApi エクスポートに unlinkLine を追加 🔵

**パターン**: Ubiquitous

> The `usersApi` export object shall include an `unlinkLine` property that delegates to `apiClient.unlinkLine()`.

**根拠**: frontend/src/services/api.ts L173-177 の `usersApi` オブジェクトに `unlinkLine` が不在。note.md セクション 8.2 の実装 4 で明示。

**現状コード** (`api.ts` L173-177):
```typescript
export const usersApi = {
  getCurrentUser: () => apiClient.getCurrentUser(),
  updateUser: (data: UpdateUserRequest) => apiClient.updateUser(data),
  linkLine: (data: LinkLineRequest) => apiClient.linkLine(data),
};
```

**期待コード**:
```typescript
export const usersApi = {
  getCurrentUser: () => apiClient.getCurrentUser(),
  updateUser: (data: UpdateUserRequest) => apiClient.updateUser(data),
  linkLine: (data: LinkLineRequest) => apiClient.linkLine(data),
  unlinkLine: () => apiClient.unlinkLine(),
};
```

---

### EARS-045-013: unlinkLine メソッドのHTTPメソッドとパス 🔵

**パターン**: Ubiquitous

> The `unlinkLine()` method shall use HTTP method `POST` and endpoint path `/users/me/unlink-line`.

**根拠**: api-endpoints.md の POST `/users/me/unlink-line` 仕様。handler.py L205 の `@app.post("/users/me/unlink-line")` と一致。

**検証方法**: unlinkLine呼び出し時のfetchリクエストが `POST ${API_BASE_URL}/users/me/unlink-line` であること。

---

### EARS-045-014: unlinkLine メソッドにリクエストボディがないこと 🔵

**パターン**: Ubiquitous

> The `unlinkLine()` method shall not send a request body.

**根拠**: api-endpoints.md の POST `/users/me/unlink-line` 仕様にリクエストボディの定義がない。handler.py L205-223 でリクエストボディを参照していない。

**検証方法**: fetchリクエストに `body` パラメータが含まれないこと。

---

## 5. フロントエンド要件: LinkLinePage 修正

### EARS-045-015: LINE連携解除で unlinkLine API を使用 🔵

**パターン**: Event-Driven

> When the user clicks the LINE unlink button on LinkLinePage, the system shall call `usersApi.unlinkLine()` instead of `usersApi.updateUser()`.

**根拠**: LinkLinePage.tsx L101-103 で `usersApi.updateUser({notification_time: user?.notification_time})` を呼び出している。REQ-V2-033 で専用エンドポイントの使用が要求されている。

**現状コード** (`LinkLinePage.tsx` L100-105):
```typescript
try {
  const updatedUser = await usersApi.updateUser({
    notification_time: user?.notification_time,
  });
  setUser({ ...updatedUser, line_linked: false });
```

**期待コード**:
```typescript
try {
  const updatedUser = await usersApi.unlinkLine();
  setUser(updatedUser);
```

---

### EARS-045-016: LINE連携解除後の状態更新でサーバーレスポンスをそのまま使用 🔵

**パターン**: Event-Driven

> When `usersApi.unlinkLine()` returns successfully, the system shall set the user state directly from the response without manual field overrides.

**根拠**: LinkLinePage.tsx L105 で `setUser({ ...updatedUser, line_linked: false })` と手動で `line_linked` を上書きしている。統一レスポンスではサーバーが `line_linked: false` を返却するため、手動上書きが不要になる。

**検証方法**: `setUser(updatedUser)` のように、レスポンスオブジェクトをそのまま状態にセットすること。

---

### EARS-045-017: LINE連携解除のエラーハンドリング維持 🔵

**パターン**: Unwanted Behaviour

> If `usersApi.unlinkLine()` throws an error, then the system shall display the error message "LINE連携の解除に失敗しました".

**根拠**: LinkLinePage.tsx L107-108 の既存エラーハンドリング。API呼び出し先の変更のみであり、エラー表示ロジックは維持。

---

### EARS-045-018: LINE連携解除のローディング状態維持 🔵

**パターン**: State-Driven

> While the LINE unlink operation is in progress, the system shall display "解除中..." on the unlink button and disable it.

**根拠**: LinkLinePage.tsx L96-111 の既存ローディング状態管理。`isUnlinking` フラグの動作は変更なし。

---

## 6. フロントエンド要件: User型定義

### EARS-045-019: User 型に timezone フィールドが存在すること 🔵

**パターン**: Ubiquitous

> The frontend `User` interface shall include a `timezone` field of type `string`.

**根拠**: frontend/src/types/user.ts L7 に `timezone: string;` が既に定義されている。バックエンド UserResponse L76 の `timezone: str = "Asia/Tokyo"` と対応。

**検証方法**: `User` インターフェースに `timezone: string` が含まれること。

**現状確認**: 既に実装済み。追加作業不要。

---

### EARS-045-020: UpdateUserRequest 型に timezone フィールドを追加 🟡

**パターン**: Ubiquitous

> The frontend `UpdateUserRequest` interface shall include an optional `timezone` field of type `string`.

**根拠**: frontend/src/types/user.ts L12-15 の `UpdateUserRequest` に `timezone` フィールドがない。バックエンド `UserSettingsRequest` (user.py L23-58) は `timezone` を受け付ける。設定画面でタイムゾーン変更が可能になる前提。

**注意**: 直接的なコードレビュー指摘ではないが、バックエンドとの型整合性の観点で推測追加。

**現状コード** (`user.ts` L12-15):
```typescript
export interface UpdateUserRequest {
  display_name?: string;
  notification_time?: string;
}
```

**期待コード**:
```typescript
export interface UpdateUserRequest {
  display_name?: string;
  notification_time?: string;
  timezone?: string;
}
```

---

## 7. レスポンス形式一貫性要件

### EARS-045-021: ユーザー関連エンドポイントのレスポンス統一 🔵

**パターン**: Ubiquitous

> All user-related endpoints that return user data (GET `/users/me`, PUT `/users/me/settings`, POST `/users/link-line`, POST `/users/me/unlink-line`) shall return responses in the format `{"success": true, "data": <UserResponse>}`.

**根拠**: api-endpoints.md の全変更後レスポンス仕様。REQ-V2-031, REQ-V2-032, REQ-V2-033 でレスポンス形式統一が要求されている。

**注意**: GET `/users/me` は現在 `user.to_response().model_dump(mode="json")` を直接返却しており (handler.py L100)、`{success, data}` ラッパーを使用していない。本タスクのスコープで GET `/users/me` のラッパー追加を行うかは設計判断が必要。

---

### EARS-045-022: UserResponse 型の一意構造保証 🔵

**パターン**: Ubiquitous

> The `UserResponse` type returned in all user-related endpoints shall have the identical field set: `user_id`, `display_name`, `picture_url`, `line_linked`, `notification_time`, `timezone`, `created_at`, `updated_at`.

**根拠**: backend/src/models/user.py L68-78 の `UserResponse` Pydantic モデル。api-endpoints.md の User 型定義。

**検証方法**: 各エンドポイントのレスポンス `data` が同一のフィールドセットを持つこと。

---

## 8. 異常系要件

### EARS-045-023: update_settings のバリデーションエラー 🔵

**パターン**: Unwanted Behaviour

> If the PUT `/users/me/settings` request body contains an invalid `notification_time` format (not HH:MM), then the system shall return HTTP 400 with `{"error": "Invalid request", "details": [...]}`.

**根拠**: handler.py L168-174 の既存バリデーションエラーハンドリング。user.py L29-37 の `validate_notification_time` バリデータ。レスポンス形式変更がバリデーションエラーに影響しないことの確認。

---

### EARS-045-024: update_settings の不正JSONエラー 🔵

**パターン**: Unwanted Behaviour

> If the PUT `/users/me/settings` request body is not valid JSON, then the system shall return HTTP 400 with `{"error": "Invalid JSON body"}`.

**根拠**: handler.py L175-180 の既存エラーハンドリング。変更なし。

---

### EARS-045-025: update_settings のユーザー不在エラー 🔵

**パターン**: Unwanted Behaviour

> If the user does not exist when PUT `/users/me/settings` is called, then the system shall return HTTP 404.

**根拠**: handler.py L198-199 の `UserNotFoundError` ハンドリング。変更なし。

---

## 9. フロントエンド API レスポンスパース要件

### EARS-045-026: フロントエンドが data フィールドからUser情報を抽出 🟡

**パターン**: Event-Driven

> When the frontend receives a response from PUT `/users/me/settings` or POST `/users/me/unlink-line`, the system shall extract the User object from the `data` field of the response body.

**根拠**: api.ts L25-72 の `request<T>` メソッドは `response.json()` を直接返却する。バックエンドが `{success, data}` ラッパーで返却する場合、フロントエンド側で `data` フィールドを抽出するロジックが必要になる可能性がある。

**注意**: 現在の `request<T>` メソッドは生のJSONレスポンスをそのまま型Tとして返却する。`{success: true, data: User}` を返却する場合、`request<{success: boolean, data: User}>` とするか、ラッパーを設けるかの設計判断が必要。既存の GET `/users/me` が `to_response().model_dump()` (ラッパーなし) を返却している点との整合性にも注意。

---

## 信頼性レベルサマリー

| カテゴリ | 要件ID | 🔵 青 | 🟡 黄 | 🔴 赤 |
|---------|--------|-------|-------|-------|
| BE: update_settings | EARS-045-001 ~ 005 | 5 | 0 | 0 |
| BE: unlink_line | EARS-045-006 ~ 009 | 4 | 0 | 0 |
| BE: link_line確認 | EARS-045-010 | 1 | 0 | 0 |
| FE: unlinkLine API | EARS-045-011 ~ 014 | 4 | 0 | 0 |
| FE: LinkLinePage | EARS-045-015 ~ 018 | 4 | 0 | 0 |
| FE: User型 | EARS-045-019 ~ 020 | 1 | 1 | 0 |
| レスポンス統一 | EARS-045-021 ~ 022 | 2 | 0 | 0 |
| 異常系 | EARS-045-023 ~ 025 | 3 | 0 | 0 |
| FE: レスポンスパース | EARS-045-026 | 0 | 1 | 0 |
| **合計** | **26件** | **24** | **2** | **0** |

**品質評価**: 高品質 (青信号 92%, 黄信号 8%, 赤信号 0%)

---

## テストケースへのマッピング

| 要件ID | テストケース | テストファイル |
|--------|-------------|--------------|
| EARS-045-001, 003 | 設定更新レスポンスがUser型 | `backend/tests/unit/test_handler.py` |
| EARS-045-002, 004, 005 | 設定更新レスポンスに全フィールド含む | `backend/tests/unit/test_handler.py` |
| EARS-045-006 | unlink_line サービス戻り値型 | `backend/tests/unit/test_user_service.py` |
| EARS-045-007, 008 | unlink_line レスポンスがUser型 | `backend/tests/unit/test_handler.py` |
| EARS-045-009 | unlink_line LINE未連携エラー | `backend/tests/unit/test_handler.py` |
| EARS-045-011, 012, 013, 014 | unlinkLine APIメソッド | `frontend/src/services/__tests__/api.test.ts` |
| EARS-045-015, 016 | LinkLinePageがunlinkLine使用 | `frontend/src/pages/__tests__/LinkLinePage.test.tsx` |
| EARS-045-017, 018 | エラー/ローディング状態維持 | `frontend/src/pages/__tests__/LinkLinePage.test.tsx` |
| EARS-045-021, 022 | レスポンスDTO一貫性テスト | 統合テスト |
| EARS-045-023, 024, 025 | 異常系テスト | `backend/tests/unit/test_handler.py` |

---

## 設計上の懸念事項

### 懸念1: GET /users/me とのレスポンスラッパー不一致 🟡

GET `/users/me` (handler.py L100) は `user.to_response().model_dump(mode="json")` を直接返却しており、`{success, data}` ラッパーを使用していない。他のエンドポイントのみラッパーを追加すると、フロントエンドの `request<T>` メソッドでの型推論が複雑になる。

**推奨対応**: GREEN フェーズで実装時に、GET `/users/me` も同じラッパー形式に統一するか、フロントエンド側で各メソッドごとにレスポンス構造を処理するか決定する。

### 懸念2: UserSettingsResponse / LinkLineResponse の廃止 🟡

レスポンスがUser型に統一された後、`UserSettingsResponse` (user.py L61-65) と `LinkLineResponse` (user.py L16-20) は不要になる。REFACTOR フェーズで削除を検討する。handler.py L14 の import 文も更新が必要。

---

**作成者**: Claude Code
**最終更新**: 2026-02-21

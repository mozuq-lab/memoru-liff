# TASK-0045 実装ノート: レスポンスDTO統一 + unlinkLine API使用

**作成日**: 2026-02-21
**対象タスク**: [TASK-0045.md](../../tasks/code-review-fixes-v2/TASK-0045.md)
**TDD段階**: 準備フェーズ

---

## 1. 技術スタック サマリー

### バックエンド

| 項目 | 詳細 |
|------|------|
| **言語・ランタイム** | Python 3.12 |
| **フレームワーク** | AWS Lambda Powertools (v2.x) |
| **フレームワーク** | AWS SAM (Serverless Application Model) |
| **API フレームワーク** | Pydantic v2 (モデル検証) |
| **データベース** | Amazon DynamoDB |
| **依存管理** | pip/requirements.txt |
| **テストフレームワーク** | pytest + pytest-mock |
| **カバレッジ目標** | 80%以上 |

**主要ファイルパス**:
- ハンドラー: `/Volumes/external/dev/memoru-liff/backend/src/api/handler.py`
- ユーザーサービス: `/Volumes/external/dev/memoru-liff/backend/src/services/user_service.py`
- ユーザーモデル: `/Volumes/external/dev/memoru-liff/backend/src/models/user.py`
- テスト設定: `/Volumes/external/dev/memoru-liff/backend/tests/conftest.py`
- 既存テスト参照: `/Volumes/external/dev/memoru-liff/backend/tests/unit/test_handler_link_line.py`

### フロントエンド

| 項目 | 詳細 |
|------|------|
| **言語・ランタイム** | TypeScript 5.x + React 18 |
| **ビルドツール** | Vite |
| **テストフレームワーク** | Vitest + @testing-library/react |
| **型定義ファイル** | `/Volumes/external/dev/memoru-liff/frontend/src/types/user.ts` |
| **API クライアント** | `/Volumes/external/dev/memoru-liff/frontend/src/services/api.ts` |
| **ページコンポーネント** | `/Volumes/external/dev/memoru-liff/frontend/src/pages/LinkLinePage.tsx` |

---

## 2. 既存ハンドラー実装パターン

### 2.1 レスポンス形式の一貫性

**GET /users/me** (成功事例):

```python
@app.get("/users/me")
@tracer.capture_method
def get_current_user():
    """Get current user information."""
    user_id = get_user_id_from_context()
    try:
        user = user_service.get_or_create_user(user_id)
        # ✓ UserResponse 型を使用
        return user.to_response().model_dump(mode="json")
    except Exception as e:
        logger.error(f"Error getting user: {e}")
        raise
```

**返却形式**: `UserResponse` Pydantic モデル
**特徴**: `to_response()` メソッドで変換し、`.model_dump(mode="json")` で JSON化

### 2.2 エラーハンドリング実装パターン

```python
@tracer.capture_method
def update_user_settings():
    """Update current user settings."""
    try:
        body = app.current_event.json_body
        request = UserSettingsRequest(**body)
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid request", "details": e.errors()}),
        )
    except json.JSONDecodeError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid JSON body"}),
        )

    try:
        # ビジネスロジック処理
        ...
    except SpecificError:
        # 意味のあるエラーレスポンスを返す
        return Response(...)
    except Exception as e:
        logger.error(f"Error: {e}")
        raise
```

**パターン**:
1. JSON デコード/検証エラー → `Response` オブジェクトで 400 返却
2. ビジネスロジックエラー → `Response` オブジェクトで適切なステータスコード返却
3. 予期しないエラー → ログして例外を再発生

### 2.3 POST /users/link-line の実装状況

```python
@app.post("/users/link-line")
@tracer.capture_method
def link_line_account():
    """Link LINE account to current user."""
    user_id = get_user_id_from_context()

    try:
        body = app.current_event.json_body
    except json.JSONDecodeError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "Invalid JSON body"}),
        )

    # id_token 検証
    id_token = body.get("id_token") if body else None
    if not id_token:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "id_token is required"}),
        )

    try:
        user_service.get_or_create_user(user_id)
        line_user_id = line_service.verify_id_token(id_token)
        user_service.link_line(user_id, line_user_id)
        # 【現状問題】: LinkLineResponse を返却している
        return LinkLineResponse(success=True, message="LINE account linked successfully").model_dump()
    except UserAlreadyLinkedError:
        return Response(
            status_code=409,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "User is already linked to a LINE account"}),
        )
    ...
```

**現状**: `LinkLineResponse` (success + message) を返却
**修正が必要**: `User` 型に統一 (TASK-0044 で修正予定)

### 2.4 PUT /users/me/settings の実装状況

```python
@app.put("/users/me/settings")
@tracer.capture_method
def update_user_settings():
    """Update current user settings."""
    user_id = get_user_id_from_context()

    try:
        body = app.current_event.json_body
        request = UserSettingsRequest(**body)
    except ValidationError as e:
        logger.warning(f"Validation error: {e}")
        return Response(...)
    except json.JSONDecodeError:
        return Response(...)

    try:
        user_service.get_or_create_user(user_id)
        user = user_service.update_settings(
            user_id,
            notification_time=request.notification_time,
            timezone=request.timezone,
        )
        # 【現状問題】: UserSettingsResponse を返却している
        return UserSettingsResponse(
            success=True,
            settings={
                "notification_time": user.settings.get("notification_time"),
                "timezone": user.settings.get("timezone"),
            },
        ).model_dump()
    except UserNotFoundError:
        raise NotFoundError("User not found")
    ...
```

**現状**: `UserSettingsResponse` (success + settings dict) を返却
**修正が必要**: `UserResponse` 型に統一（このタスク）

### 2.5 POST /users/me/unlink-line の実装状況

```python
@app.post("/users/me/unlink-line")
@tracer.capture_method
def unlink_line():
    """Unlink LINE account from current user."""
    user_id = get_user_id_from_context()

    try:
        result = user_service.unlink_line(user_id)
        # 【現状問題】: user_service.unlink_line() が dict を返却している
        return {"success": True, "data": result}
    except LineNotLinkedError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "LINE account not linked"}),
        )
    ...
```

**現状**: `user_service.unlink_line()` が `{"user_id": ..., "unlinked_at": ...}` を返却
**修正が必要**: User オブジェクトを返却するよう変更（このタスク）

---

## 3. Pydantic モデル・レスポンス形式の定義

### 3.1 ユーザーモデル構造

ファイル: `/Volumes/external/dev/memoru-liff/backend/src/models/user.py`

```python
class User(BaseModel):
    """User domain model."""
    user_id: str
    line_user_id: Optional[str] = None
    display_name: Optional[str] = None
    picture_url: Optional[str] = None
    settings: dict = Field(default_factory=lambda: {
        "notification_time": "09:00",
        "timezone": "Asia/Tokyo"
    })
    last_notified_date: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    def to_response(self) -> UserResponse:
        """Convert to API response model."""
        return UserResponse(
            user_id=self.user_id,
            display_name=self.display_name,
            picture_url=self.picture_url,
            line_linked=self.line_user_id is not None,
            notification_time=self.settings.get("notification_time"),
            timezone=self.settings.get("timezone", "Asia/Tokyo"),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
```

### 3.2 UserResponse レスポンス型（現状）

```python
class UserResponse(BaseModel):
    """Response model for user information."""
    user_id: str
    display_name: Optional[str] = None
    picture_url: Optional[str] = None
    line_linked: bool = False
    notification_time: Optional[str] = None
    timezone: str = "Asia/Tokyo"
    created_at: datetime
    updated_at: Optional[datetime] = None
```

**特徴**:
- `line_user_id` は返却しない (代わりに `line_linked: bool`)
- `notification_time` と `timezone` は `settings` 辞書から抽出
- すべてのタイムスタンプを ISO 8601 形式で返却

### 3.3 統一レスポンス形式

TASK-0045 完了後の統一形式（フロントエンド期待値）:

```json
{
  "success": true,
  "data": {
    "user_id": "keycloak-sub-uuid",
    "display_name": "テストユーザー",
    "picture_url": null,
    "line_linked": true,
    "notification_time": "09:00",
    "timezone": "Asia/Tokyo",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
}
```

---

## 4. 現在の User 型定義（フロントエンド）

ファイル: `/Volumes/external/dev/memoru-liff/frontend/src/types/user.ts`

```typescript
export interface User {
  user_id: string;
  display_name?: string | null;
  picture_url?: string | null;
  line_linked: boolean;
  notification_time?: string | null;
  timezone: string;
  created_at: string;
  updated_at?: string | null;
}

export interface UpdateUserRequest {
  display_name?: string;
  notification_time?: string;
}

export interface LinkLineRequest {
  id_token: string;
}
```

**現状の課題**:
- `UpdateUserRequest` に `timezone` フィールドがない
- API クライアントに `unlinkLine` メソッドがない

---

## 5. API クライアント実装パターン

ファイル: `/Volumes/external/dev/memoru-liff/frontend/src/services/api.ts`

### 5.1 現在の usersApi 実装

```typescript
export const usersApi = {
  getCurrentUser: () => apiClient.getCurrentUser(),
  updateUser: (data: UpdateUserRequest) => apiClient.updateUser(data),
  linkLine: (data: LinkLineRequest) => apiClient.linkLine(data),
};
```

### 5.2 ApiClient 内部実装

```typescript
class ApiClient {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.accessToken) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${this.accessToken}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    // 401 処理：トークンリフレッシュ...
    if (response.status === 401) {
      // リフレッシュロジック
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Unknown error' }));
      throw new Error(error.message || `HTTP ${response.status}`);
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return response.json();
  }

  async updateUser(data: UpdateUserRequest): Promise<User> {
    return this.request<User>('/users/me/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }
}
```

**パターン**:
1. `request<T>` メソッドで汎用的に処理
2. エンドポイント + メソッド + ボディで API 呼び出し
3. 401 エラー時は自動的にトークンリフレッシュ

---

## 6. LinkLinePage コンポーネント実装パターン

ファイル: `/Volumes/external/dev/memoru-liff/frontend/src/pages/LinkLinePage.tsx`

### 6.1 現在の LINE 連携解除処理

```typescript
const handleUnlinkLine = async () => {
  setIsUnlinking(true);
  setError(null);

  try {
    // 【問題】: updateUser を呼び出している
    const updatedUser = await usersApi.updateUser({
      notification_time: user?.notification_time,
    });
    // LINE連携解除後のフロントエンド状態を更新
    setUser({ ...updatedUser, line_linked: false });
    setSuccessMessage('LINE連携を解除しました');
  } catch (err) {
    setError('LINE連携の解除に失敗しました');
  } finally {
    setIsUnlinking(false);
  }
};
```

**現状の課題**:
1. LINE 連携解除で `updateUser` を呼び出している
2. 本来は専用の `unlinkLine` メソッドを呼ぶべき
3. 状態更新で `line_linked: false` を手動でセットしている

### 6.2 LINE 連携処理（参考）

```typescript
const handleLinkLine = async () => {
  setIsLinking(true);
  setError(null);

  try {
    if (!isInLiffClient()) {
      setError('LINEアプリからアクセスしてください');
      setIsLinking(false);
      return;
    }

    await initializeLiff();

    const idToken = getLiffIdToken();
    if (!idToken) {
      setError('LINEの認証情報を取得できませんでした');
      setIsLinking(false);
      return;
    }

    // サーバーに連携リクエスト
    const updatedUser = await usersApi.linkLine({
      id_token: idToken,
    });

    setUser(updatedUser);
    setSuccessMessage('LINE連携が完了しました');
  } catch (err: unknown) {
    setError('LINE連携に失敗しました');
  } finally {
    setIsLinking(false);
  }
};
```

---

## 7. テスト実装パターン

### 7.1 フロントエンドテスト設定

ファイル: `/Volumes/external/dev/memoru-liff/frontend/src/pages/__tests__/LinkLinePage.test.tsx`

**テストセットアップ**:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { LinkLinePage } from '../LinkLinePage';

// API モック
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

// LIFF モック
const mockInitializeLiff = vi.fn();
const mockIsInLiffClient = vi.fn();
const mockGetLiffIdToken = vi.fn();

vi.mock('@/services/liff', () => ({
  initializeLiff: () => mockInitializeLiff(),
  isInLiffClient: () => mockIsInLiffClient(),
  getLiffIdToken: () => mockGetLiffIdToken(),
}));

// useNavigate モック
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// テスト用ユーザーデータ
const mockUnlinkedUser: User = {
  user_id: 'user-1',
  display_name: 'テストユーザー',
  picture_url: null,
  line_linked: false,
  notification_time: '09:00',
  timezone: 'Asia/Tokyo',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
};
```

**テストレンダリング**:

```typescript
const renderLinkLinePage = () => {
  return render(
    <MemoryRouter>
      <LinkLinePage />
    </MemoryRouter>
  );
};

describe('LinkLinePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should display loading state initially', async () => {
    mockGetCurrentUser.mockResolvedValue(mockUnlinkedUser);

    renderLinkLinePage();

    // ローディング表示を確認
    await waitFor(() => {
      expect(screen.getByText('読み込み中...')).toBeInTheDocument();
    });
  });
});
```

### 7.2 バックエンドテスト設定

ファイル: `/Volumes/external/dev/memoru-liff/backend/tests/conftest.py`

**pytest 設定**:

```python
import pytest
import os
from datetime import datetime
from datetime import timezone as dt_timezone

# ローカル DynamoDB エンドポイント設定
os.environ['AWS_ENDPOINT_URL'] = 'http://localhost:8000'
os.environ['USERS_TABLE'] = 'memoru-users-test'

@pytest.fixture
def dynamodb_resource():
    """Create a local DynamoDB resource for testing."""
    import boto3
    return boto3.resource('dynamodb', endpoint_url='http://localhost:8000')

@pytest.fixture
def user_service(dynamodb_resource):
    """Create a UserService instance with test DynamoDB."""
    from src.services.user_service import UserService
    return UserService(table_name='memoru-users-test', dynamodb_resource=dynamodb_resource)
```

**既存テストの参考**: `/Volumes/external/dev/memoru-liff/backend/tests/unit/test_handler_link_line.py`

---

## 8. 実装タスク分解

### 8.1 RED フェーズ（テスト記述）

#### テストケース 1: `update_settings` がレスポンスに User 型を含む

```python
def test_update_settings_returns_user_response(app_client, user_service, dynamodb_resource):
    """Test that PUT /users/me/settings returns User type in response."""
    # Given: 認証済みユーザー
    user = user_service.create_user(user_id='test-user-id')

    # When: PUT /users/me/settings でnotification_timeを更新
    response = app_client.put(
        '/users/me/settings',
        json={'notification_time': '21:00', 'timezone': 'UTC'},
        headers={'Authorization': 'Bearer test-token'}
    )

    # Then: レスポンスの data フィールドに User 型オブジェクトが含まれること
    assert response.status_code == 200
    assert 'data' in response.json()
    data = response.json()['data']
    assert data['user_id'] == 'test-user-id'
    assert data['notification_time'] == '21:00'
    assert data['timezone'] == 'UTC'
```

#### テストケース 2: `update_settings` がすべての User フィールドを返却

```python
def test_update_settings_includes_all_user_fields(app_client, user_service):
    """Test that PUT /users/me/settings response includes all User fields."""
    # Given: LINE連携済みユーザー
    user = user_service.create_user(user_id='test-user-id')
    user_service.link_line(user_id='test-user-id', line_user_id='line-123')

    # When: PUT /users/me/settings で設定を更新
    response = app_client.put(
        '/users/me/settings',
        json={'notification_time': '21:00'},
        headers={'Authorization': 'Bearer test-token'}
    )

    # Then: レスポンスに全フィールドが含まれること
    assert response.status_code == 200
    data = response.json()['data']
    assert 'user_id' in data
    assert 'line_linked' in data
    assert 'notification_time' in data
    assert 'timezone' in data
    assert 'created_at' in data
    assert 'updated_at' in data
```

#### テストケース 3: `unlink_line` API が呼び出される

```typescript
it('should call unlinkLine API when unlink button is clicked', async () => {
  // Given: LINE連携済み状態
  const linkedUser: User = {
    ...mockUnlinkedUser,
    line_linked: true,
  };
  mockGetCurrentUser.mockResolvedValue(linkedUser);

  renderLinkLinePage();

  // 初期化後を待機
  await waitFor(() => {
    expect(mockGetCurrentUser).toHaveBeenCalled();
  });

  // When: LINE連携解除ボタンを押下
  const unlinkButton = await screen.findByTestId('unlink-button');
  const user = userEvent.setup();
  await user.click(unlinkButton);

  // Then: unlinkLine API が呼び出されること
  await waitFor(() => {
    expect(mockUnlinkLine).toHaveBeenCalled();
  });
});
```

#### テストケース 4: `unlink_line` がレスポンスに User 型を含む

```python
def test_unlink_line_returns_user_response(app_client, user_service):
    """Test that POST /users/me/unlink-line returns User type in response."""
    # Given: LINE連携済みユーザー
    user = user_service.create_user(user_id='test-user-id')
    user_service.link_line(user_id='test-user-id', line_user_id='line-123')

    # When: POST /users/me/unlink-line を呼び出す
    response = app_client.post(
        '/users/me/unlink-line',
        headers={'Authorization': 'Bearer test-token'}
    )

    # Then: レスポンスの data フィールドに User 型（line_linked: false）が含まれること
    assert response.status_code == 200
    data = response.json()['data']
    assert data['user_id'] == 'test-user-id'
    assert data['line_linked'] is False
```

### 8.2 GREEN フェーズ（最小実装）

#### 実装 1: ハンドラー update_settings レスポンス修正

ファイル: `/Volumes/external/dev/memoru-liff/backend/src/api/handler.py`
行番号: 158-202

**変更前**:
```python
return UserSettingsResponse(
    success=True,
    settings={
        "notification_time": user.settings.get("notification_time"),
        "timezone": user.settings.get("timezone"),
    },
).model_dump()
```

**変更後**:
```python
# 更新後の最新ユーザー情報を取得
updated_user = user_service.get_user(user_id)
return {
    "success": True,
    "data": updated_user.to_response().model_dump(mode="json")
}
```

#### 実装 2: user_service.unlink_line レスポンス修正

ファイル: `/Volumes/external/dev/memoru-liff/backend/src/services/user_service.py`
行番号: 311-336

**変更前**:
```python
def unlink_line(self, user_id: str) -> dict:
    """Unlink LINE account from user."""
    now = datetime.now(dt_timezone.utc)

    try:
        self.table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="REMOVE line_user_id SET updated_at = :now",
            ConditionExpression="attribute_exists(line_user_id)",
            ExpressionAttributeValues={":now": now.isoformat()},
        )
        return {"user_id": user_id, "unlinked_at": now.isoformat()}  # 【変更対象】
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise LineNotLinkedError("LINE account not linked to this user")
        raise UserServiceError(f"Failed to unlink LINE account: {e}")
```

**変更後**:
```python
def unlink_line(self, user_id: str) -> User:
    """Unlink LINE account from user."""
    now = datetime.now(dt_timezone.utc)

    try:
        self.table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="REMOVE line_user_id SET updated_at = :now",
            ConditionExpression="attribute_exists(line_user_id)",
            ExpressionAttributeValues={":now": now.isoformat()},
        )
        # 更新後のユーザー情報を取得して返却
        return self.get_user(user_id)  # 【変更】
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise LineNotLinkedError("LINE account not linked to this user")
        raise UserServiceError(f"Failed to unlink LINE account: {e}")
```

#### 実装 3: ハンドラー unlink_line レスポンス修正

ファイル: `/Volumes/external/dev/memoru-liff/backend/src/api/handler.py`
行番号: 205-223

**変更前**:
```python
@app.post("/users/me/unlink-line")
@tracer.capture_method
def unlink_line():
    """Unlink LINE account from current user."""
    user_id = get_user_id_from_context()
    logger.info(f"Unlinking LINE account for user_id: {user_id}")

    try:
        result = user_service.unlink_line(user_id)
        return {"success": True, "data": result}  # 【現状】dict を返却
    except LineNotLinkedError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "LINE account not linked"}),
        )
    ...
```

**変更後**:
```python
@app.post("/users/me/unlink-line")
@tracer.capture_method
def unlink_line():
    """Unlink LINE account from current user."""
    user_id = get_user_id_from_context()
    logger.info(f"Unlinking LINE account for user_id: {user_id}")

    try:
        user = user_service.unlink_line(user_id)
        # 【変更】User 型に統一
        return {
            "success": True,
            "data": user.to_response().model_dump(mode="json")
        }
    except LineNotLinkedError:
        return Response(
            status_code=400,
            content_type=content_types.APPLICATION_JSON,
            body=json.dumps({"error": "LINE account not linked"}),
        )
    ...
```

#### 実装 4: フロントエンド API クライアント に unlinkLine 追加

ファイル: `/Volumes/external/dev/memoru-liff/frontend/src/services/api.ts`
行番号: 136-177

**変更**:

```typescript
// ApiClient クラス内に追加
async unlinkLine(): Promise<User> {
  return this.request<User>('/users/me/unlink-line', {
    method: 'POST',
  });
}

// usersApi エクスポート部分に追加
export const usersApi = {
  getCurrentUser: () => apiClient.getCurrentUser(),
  updateUser: (data: UpdateUserRequest) => apiClient.updateUser(data),
  linkLine: (data: LinkLineRequest) => apiClient.linkLine(data),
  unlinkLine: () => apiClient.unlinkLine(),  // 【新規追加】
};
```

#### 実装 5: LinkLinePage の LINE 連携解除修正

ファイル: `/Volumes/external/dev/memoru-liff/frontend/src/pages/LinkLinePage.tsx`
行番号: 95-112

**変更前**:
```typescript
const handleUnlinkLine = async () => {
  setIsUnlinking(true);
  setError(null);

  try {
    const updatedUser = await usersApi.updateUser({
      notification_time: user?.notification_time,
    });
    setUser({ ...updatedUser, line_linked: false });
    setSuccessMessage('LINE連携を解除しました');
  } catch (err) {
    setError('LINE連携の解除に失敗しました');
  } finally {
    setIsUnlinking(false);
  }
};
```

**変更後**:
```typescript
const handleUnlinkLine = async () => {
  setIsUnlinking(true);
  setError(null);

  try {
    // 【変更】専用 API を呼び出す
    const updatedUser = await usersApi.unlinkLine();
    setUser(updatedUser);
    setSuccessMessage('LINE連携を解除しました');
  } catch (err) {
    setError('LINE連携の解除に失敗しました');
  } finally {
    setIsUnlinking(false);
  }
};
```

#### 実装 6: フロントエンド UpdateUserRequest 型に timezone 追加

ファイル: `/Volumes/external/dev/memoru-liff/frontend/src/types/user.ts`
行番号: 12-15

**変更前**:
```typescript
export interface UpdateUserRequest {
  display_name?: string;
  notification_time?: string;
}
```

**変更後**:
```typescript
export interface UpdateUserRequest {
  display_name?: string;
  notification_time?: string;
  timezone?: string;  // 【新規追加】
}
```

### 8.3 REFACTOR フェーズ（リファクタリング）

- レスポンス構造の整合性確認（GET /users/me との比較）
- エラーハンドリングの統一性確認
- テストカバレッジ 80%以上確認
- 不要な型定義（UserSettingsResponse）の削除検討

---

## 9. 関連ファイル一覧

| ファイル | 役割 | 修正範囲 |
|---------|------|---------|
| `/Volumes/external/dev/memoru-liff/backend/src/api/handler.py` | ハンドラー実装 | update_settings, unlink_line レスポンス |
| `/Volumes/external/dev/memoru-liff/backend/src/services/user_service.py` | ユーザーサービス | unlink_line 戻り値型 |
| `/Volumes/external/dev/memoru-liff/backend/src/models/user.py` | Pydantic モデル | 参照のみ（to_response() 既存） |
| `/Volumes/external/dev/memoru-liff/frontend/src/services/api.ts` | API クライアント | unlinkLine メソッド追加 |
| `/Volumes/external/dev/memoru-liff/frontend/src/pages/LinkLinePage.tsx` | ページコンポーネント | handleUnlinkLine ロジック |
| `/Volumes/external/dev/memoru-liff/frontend/src/types/user.ts` | TypeScript 型定義 | UpdateUserRequest に timezone |
| `/Volumes/external/dev/memoru-liff/backend/tests/unit/test_handler_link_line.py` | 既存テスト参考 | テストパターン参照 |
| `/Volumes/external/dev/memoru-liff/frontend/src/pages/__tests__/LinkLinePage.test.tsx` | 既存テスト参考 | テストパターン参照 |

---

## 10. 信頼性レベル別実装チェックリスト

### 🔵 青信号（確実な定義）

- [x] PUT /users/me/settings がレスポンスに User オブジェクトを返す
- [x] POST /users/me/unlink-line がレスポンスに User オブジェクトを返す
- [x] フロントエンドに unlinkLine メソッドが存在する
- [x] LinkLinePage が unlinkLine API を使用する
- [x] User 型に timezone フィールドが含まれている
- [x] User.to_response() が timezone フィールドを含む

### 🟡 黄信号（要件定義書から妥当な推測）

- 特に該当する推測なし（全項目が青信号）

### 🔴 赤信号（確実でない推測）

- 特に該当する問題なし

---

## 11. テスト実行コマンド参考

### バックエンド

```bash
# すべてのテストを実行
cd /Volumes/external/dev/memoru-liff/backend
make test

# 特定のテストファイルを実行
pytest tests/unit/test_handler_link_line.py -v

# カバレッジレポート付きで実行
pytest --cov=src --cov-report=html tests/
```

### フロントエンド

```bash
# すべてのテストを実行
cd /Volumes/external/dev/memoru-liff/frontend
npm run test

# 特定のテストファイルを実行
npm run test -- LinkLinePage.test.tsx

# カバレッジレポート付きで実行
npm run test -- --coverage
```

---

## 12. 次のステップ

1. **RED フェーズ**: テストケース 1〜4 を記述し、すべてが失敗することを確認
2. **GREEN フェーズ**: 実装 1〜6 を順序通りに実装し、すべてのテストが成功することを確認
3. **REFACTOR フェーズ**: コード品質の改善と統一性確認
4. **検証**: TASK-0045.md の完了条件をチェック
5. **コミット**: `TASK-0045: レスポンスDTO統一 + unlinkLine API使用`

---

**作成者**: Claude Code
**最終更新**: 2026-02-21

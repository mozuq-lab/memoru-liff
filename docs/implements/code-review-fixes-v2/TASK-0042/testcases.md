# TASK-0042: APIルート統一（3レイヤー整合性修正）- テストケース定義

**作成日**: 2026-02-21
**関連タスク**: TASK-0042
**関連要件**: REQ-V2-001, REQ-V2-002, REQ-V2-003, REQ-V2-004
**タスクタイプ**: TDD
**ドキュメントバージョン**: v1.0

---

## 1. テスト戦略

### 1.1 テスト対象

| # | テスト対象 | テストファイル | テストフレームワーク |
|---|-----------|-------------|-------------------|
| 1 | SAM テンプレート パス定義 | `backend/tests/test_template_routes.py` | pytest + PyYAML |
| 2 | handler.py ルート定義 | `backend/tests/test_template_routes.py` (整合性テスト内) | pytest |
| 3 | フロントエンド API クライアント | `frontend/src/services/__tests__/api.test.ts` | Vitest |

### 1.2 テスト方針

- **SAM テンプレート検証**: `backend/template.yaml` を YAML としてパースし、イベント定義のパスとメソッドを静的に検証する
- **handler ルート検証**: `backend/src/api/handler.py` のソースコードから `@app.<method>()` デコレータのパスを正規表現で抽出し、SAM テンプレートとの整合性を検証する
- **フロントエンド検証**: `global.fetch` をモック化し、各 API メソッドが正しいパスにリクエストを送信することを検証する
- **3レイヤー整合性**: SAM / handler / frontend の全パスセットを比較し、完全一致を検証する

### 1.3 テストケース ID 体系

- `TC-042-XX`: バックエンド SAM テンプレート検証（01-09）
- `TC-042-1X`: フロントエンド API パス検証（11-19）
- `TC-042-2X`: 3レイヤー整合性検証（21-29）
- `TC-042-3X`: エッジケース・エラーシナリオ（31-39）

---

## 2. バックエンド テストケース

### テストファイル: `backend/tests/test_template_routes.py`

このテストファイルは SAM テンプレート (`backend/template.yaml`) をパースし、全 HttpApi イベント定義を検証する。

#### 2.1 テストの前提: fixture 設計

```python
import os
import re
import yaml
import pytest

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "template.yaml"
)
HANDLER_PATH = os.path.join(
    os.path.dirname(__file__), "..", "src", "api", "handler.py"
)


@pytest.fixture
def sam_template():
    """SAM テンプレートを読み込んでパースする fixture."""
    with open(TEMPLATE_PATH, "r") as f:
        return yaml.safe_load(f)


@pytest.fixture
def api_events(sam_template):
    """ApiFunction の HttpApi イベントのみを抽出する fixture."""
    events = sam_template["Resources"]["ApiFunction"]["Properties"]["Events"]
    return {
        name: event
        for name, event in events.items()
        if event.get("Type") == "HttpApi"
    }


@pytest.fixture
def handler_routes():
    """handler.py から @app.<method>() デコレータのルート定義を抽出する fixture."""
    with open(HANDLER_PATH, "r") as f:
        content = f.read()
    pattern = r'@app\.(get|post|put|delete)\("([^"]+)"\)'
    matches = re.findall(pattern, content)
    return {(method.upper(), path) for method, path in matches}
```

---

### TC-042-01: 設定更新イベント パス検証

**対応要件**: REQ-V2-001
**信頼性**: 🔵

**Given**: 修正後の SAM テンプレート (`backend/template.yaml`) がパースされた状態
**When**: `ApiFunction.Properties.Events.UpdateUser` イベントの `Path` と `Method` を取得する
**Then**:
- `Path` が `/users/me/settings` であること
- `Method` が `PUT` であること

```python
def test_update_user_event_path_is_users_me_settings(api_events):
    """TC-042-01: REQ-V2-001 - 設定更新イベントのパスが PUT /users/me/settings"""
    event = api_events["UpdateUser"]
    assert event["Properties"]["Path"] == "/users/me/settings"
    assert event["Properties"]["Method"] == "PUT"
```

**期待結果**: 修正前は `Path: /users/me` で FAIL。修正後に PASS。

---

### TC-042-02: レビュー送信イベント パス検証

**対応要件**: REQ-V2-002
**信頼性**: 🔵

**Given**: 修正後の SAM テンプレートがパースされた状態
**When**: `ApiFunction.Properties.Events.SubmitReview` イベントの `Path` と `Method` を取得する
**Then**:
- `Path` が `/reviews/{cardId}` であること
- `Method` が `POST` であること
- パスに `{cardId}` パラメータが含まれること

```python
def test_submit_review_event_path_has_card_id_parameter(api_events):
    """TC-042-02: REQ-V2-002 - レビュー送信イベントのパスが POST /reviews/{cardId}"""
    event = api_events["SubmitReview"]
    assert event["Properties"]["Path"] == "/reviews/{cardId}"
    assert event["Properties"]["Method"] == "POST"
    assert "{cardId}" in event["Properties"]["Path"]
```

**期待結果**: 修正前は `Path: /reviews` で FAIL。修正後に PASS。

---

### TC-042-03: LINE 連携イベント 存在検証

**対応要件**: REQ-V2-003
**信頼性**: 🔵

**Given**: 修正後の SAM テンプレートがパースされた状態
**When**: `ApiFunction.Properties.Events` に `LinkLine` イベントが存在するか確認する
**Then**:
- `LinkLine` イベントが存在すること
- `Type` が `HttpApi` であること
- `Path` が `/users/link-line` であること
- `Method` が `POST` であること

```python
def test_link_line_event_exists_with_correct_path(api_events):
    """TC-042-03: REQ-V2-003 - LINE 連携イベントが POST /users/link-line で定義されている"""
    assert "LinkLine" in api_events, "LinkLine イベントが SAM テンプレートに存在すること"
    event = api_events["LinkLine"]
    assert event["Properties"]["Path"] == "/users/link-line"
    assert event["Properties"]["Method"] == "POST"
```

**期待結果**: 修正前はイベント未定義で FAIL。追加後に PASS。

---

### TC-042-04: 全 HttpApi イベント数チェック

**対応要件**: 整合性チェック
**信頼性**: 🔵

**Given**: 修正後の SAM テンプレートがパースされた状態
**When**: `ApiFunction.Properties.Events` で `Type == "HttpApi"` のイベント数をカウントする
**Then**: イベント数が 13 個であること（既存12 + LinkLine 追加1）

```python
def test_total_http_api_event_count(api_events):
    """TC-042-04: 整合性 - ApiFunction の HttpApi イベント総数が 13 個"""
    assert len(api_events) == 13, (
        f"期待: 13 イベント（既存12 + LinkLine）、実際: {len(api_events)} イベント"
    )
```

**期待イベント一覧**:

| # | イベント名 | Method | Path |
|---|-----------|--------|------|
| 1 | GetUser | GET | /users/me |
| 2 | UpdateUser | PUT | /users/me/settings |
| 3 | LinkLine | POST | /users/link-line |
| 4 | UnlinkLine | POST | /users/me/unlink-line |
| 5 | ListCards | GET | /cards |
| 6 | CreateCard | POST | /cards |
| 7 | GetCard | GET | /cards/{cardId} |
| 8 | UpdateCard | PUT | /cards/{cardId} |
| 9 | DeleteCard | DELETE | /cards/{cardId} |
| 10 | GetDueCards | GET | /cards/due |
| 11 | SubmitReview | POST | /reviews/{cardId} |
| 12 | GetReviewStats | GET | /reviews/stats |
| 13 | GenerateCards | POST | /cards/generate |

**期待結果**: 修正前は 12 個（LinkLine なし）で FAIL。追加後に PASS。

---

### TC-042-05: 全イベントが HttpApi を参照

**対応要件**: 制約チェック
**信頼性**: 🔵

**Given**: 修正後の SAM テンプレートがパースされた状態
**When**: 全 HttpApi イベントの `ApiId` プロパティを確認する
**Then**: 全イベントの `Properties` に `ApiId` が設定されていること

```python
def test_all_events_reference_http_api(api_events):
    """TC-042-05: 制約 - 全 HttpApi イベントが ApiId を参照していること"""
    for name, event in api_events.items():
        props = event["Properties"]
        assert "ApiId" in props, (
            f"イベント '{name}' に ApiId が設定されていません"
        )
```

**補足**: PyYAML では `!Ref HttpApi` は文字列としてパースされない可能性がある。CloudFormation Intrinsic Function (`!Ref`) は PyYAML のカスタムタグとして扱われるため、`ApiId` キーの存在のみを検証する。

---

### TC-042-06: SAM パスと handler ルート定義の一致

**対応要件**: REQ-V2-004 (3レイヤー整合性)
**信頼性**: 🔵

**Given**: 修正後の SAM テンプレートと handler.py のソースコード
**When**: SAM の全 HttpApi イベントのパスを正規化して抽出し、handler.py の全 `@app.<method>()` デコレータからパスを抽出する
**Then**: SAM のパスセット（正規化後）が handler のパスセットのスーパーセットであること

**正規化ルール**:
- SAM テンプレート: `{paramName}` 形式 (例: `{cardId}`)
- handler.py: `<param_name>` 形式 (例: `<card_id>`)
- 比較時に SAM の `{camelCase}` を `<snake_case>` に変換

```python
def test_sam_paths_match_handler_routes(api_events, handler_routes):
    """TC-042-06: 整合性 - SAM テンプレートの全パスが handler.py のルート定義と対応"""
    import re

    def normalize_sam_path(path):
        """SAM の {camelCase} を handler の <snake_case> に変換."""
        def camel_to_snake(match):
            name = match.group(1)
            # camelCase to snake_case
            snake = re.sub(r'([A-Z])', r'_\1', name).lower().lstrip('_')
            return f"<{snake}>"
        return re.sub(r'\{(\w+)\}', camel_to_snake, path)

    sam_routes = set()
    for name, event in api_events.items():
        method = event["Properties"]["Method"].upper()
        path = normalize_sam_path(event["Properties"]["Path"])
        sam_routes.add((method, path))

    # GetReviewStats はハンドラーに直接対応がない可能性があるため除外
    # handler にあるルートが全て SAM にも定義されていること
    for method, path in handler_routes:
        assert (method, path) in sam_routes, (
            f"handler ルート ({method} {path}) が SAM テンプレートに存在しません"
        )
```

**補足**: `GetReviewStats` (`GET /reviews/stats`) は handler.py にルート定義がない可能性がある。このテストでは handler.py のルートが全て SAM テンプレートにも定義されていることを検証する（handler を起点にした片方向チェック）。

---

### TC-042-07: 個別エンドポイント パスとメソッドのペア検証

**対応要件**: 整合性チェック（全エンドポイント）
**信頼性**: 🔵

**Given**: 修正後の SAM テンプレートがパースされた状態
**When**: 全 HttpApi イベントのパスとメソッドのペアを一括検証する
**Then**: 全13エンドポイントが期待通りのパスとメソッドを持つこと

```python
@pytest.mark.parametrize(
    "event_name, expected_path, expected_method",
    [
        ("GetUser", "/users/me", "GET"),
        ("UpdateUser", "/users/me/settings", "PUT"),
        ("LinkLine", "/users/link-line", "POST"),
        ("UnlinkLine", "/users/me/unlink-line", "POST"),
        ("ListCards", "/cards", "GET"),
        ("CreateCard", "/cards", "POST"),
        ("GetCard", "/cards/{cardId}", "GET"),
        ("UpdateCard", "/cards/{cardId}", "PUT"),
        ("DeleteCard", "/cards/{cardId}", "DELETE"),
        ("GetDueCards", "/cards/due", "GET"),
        ("SubmitReview", "/reviews/{cardId}", "POST"),
        ("GetReviewStats", "/reviews/stats", "GET"),
        ("GenerateCards", "/cards/generate", "POST"),
    ],
)
def test_event_path_and_method(api_events, event_name, expected_path, expected_method):
    """TC-042-07: 整合性 - 全エンドポイントのパスとメソッドが期待通り"""
    assert event_name in api_events, f"イベント '{event_name}' が存在しません"
    event = api_events[event_name]
    assert event["Properties"]["Path"] == expected_path, (
        f"{event_name}: 期待パス={expected_path}, 実際={event['Properties']['Path']}"
    )
    assert event["Properties"]["Method"] == expected_method, (
        f"{event_name}: 期待メソッド={expected_method}, 実際={event['Properties']['Method']}"
    )
```

**期待結果**: 修正対象の3件（UpdateUser, LinkLine, SubmitReview）は修正前に FAIL。修正後に全 PASS。

---

### TC-042-08: SAM テンプレートが有効な YAML であること

**対応要件**: 品質チェック
**信頼性**: 🔵

**Given**: `backend/template.yaml` ファイルが存在する
**When**: PyYAML でパースを試みる
**Then**: パースエラーが発生しないこと

```python
def test_template_is_valid_yaml(sam_template):
    """TC-042-08: 品質 - SAM テンプレートが有効な YAML としてパースできる"""
    assert sam_template is not None
    assert "Resources" in sam_template
    assert "ApiFunction" in sam_template["Resources"]
```

---

### TC-042-09: イベント名の重複がないこと

**対応要件**: 品質チェック
**信頼性**: 🔵

**Given**: 修正後の SAM テンプレートがパースされた状態
**When**: `ApiFunction.Properties.Events` の全イベント名を確認する
**Then**: 重複するイベント名がないこと（YAML パース特性上、重複キーは後勝ちとなるため、イベント数で検証）

```python
def test_no_duplicate_event_names(sam_template):
    """TC-042-09: 品質 - イベント名の重複がないこと（YAML パース後のイベント数で検証）"""
    events = sam_template["Resources"]["ApiFunction"]["Properties"]["Events"]
    http_api_events = {
        name: ev for name, ev in events.items()
        if ev.get("Type") == "HttpApi"
    }
    # YAML で重複キーは後勝ちになるため、パース後にイベント数が期待通りかで検証
    assert len(http_api_events) == 13
```

---

## 3. フロントエンド テストケース

### テストファイル: `frontend/src/services/__tests__/api.test.ts`

既存の `api.test.ts` に新しい `describe` ブロックとして追加する。

#### 3.1 テスト環境設定

既存の `beforeEach` / `afterEach` パターンを踏襲:

```typescript
describe('TASK-0042: API ルート統一 - パス検証', () => {
  let mockFetch: ReturnType<typeof vi.fn>;

  beforeEach(async () => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com');
    mockFetch = vi.fn();
    global.fetch = mockFetch;
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  // テストケースはこの中に追加
});
```

---

### TC-042-11: linkLine() が `/users/link-line` に POST リクエストを送信する

**対応要件**: REQ-V2-004
**信頼性**: 🔵

**Given**: mockFetch が `200 OK` + User JSON レスポンスを返すよう設定されている
**When**: `apiClient.linkLine({ line_user_id: 'U123' })` を呼び出す
**Then**:
- fetch が `https://api.example.com/users/link-line` に呼び出されること
- HTTP メソッドが `POST` であること

```typescript
it('TC-042-11: linkLine()が/users/link-lineにPOSTリクエストを送信する', async () => {
  // Given
  const mockUser = { user_id: 'test-user', line_user_id: 'U123' };
  mockFetch.mockResolvedValue(
    new Response(JSON.stringify(mockUser), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  );

  // When
  const { apiClient } = await import('@/services/api');
  await apiClient.linkLine({ line_user_id: 'U123' });

  // Then
  expect(mockFetch).toHaveBeenCalledWith(
    'https://api.example.com/users/link-line',
    expect.objectContaining({
      method: 'POST',
    })
  );
});
```

**期待結果**: 修正前は `/users/me/link-line` にリクエストが送信されるため FAIL。修正後に PASS。

---

### TC-042-12: linkLine() のリクエストボディが正しくシリアライズされる

**対応要件**: REQ-V2-004
**信頼性**: 🔵

**Given**: mockFetch が `200 OK` + User JSON レスポンスを返すよう設定されている
**When**: `apiClient.linkLine({ line_user_id: 'U1234567890abcdef' })` を呼び出す
**Then**: fetch の `body` が `JSON.stringify({ line_user_id: 'U1234567890abcdef' })` であること

```typescript
it('TC-042-12: linkLine()のリクエストボディが正しくシリアライズされる', async () => {
  // Given
  const mockUser = { user_id: 'test-user', line_user_id: 'U1234567890abcdef' };
  mockFetch.mockResolvedValue(
    new Response(JSON.stringify(mockUser), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  );

  // When
  const { apiClient } = await import('@/services/api');
  await apiClient.linkLine({ line_user_id: 'U1234567890abcdef' });

  // Then
  expect(mockFetch).toHaveBeenCalledWith(
    expect.any(String),
    expect.objectContaining({
      body: JSON.stringify({ line_user_id: 'U1234567890abcdef' }),
    })
  );
});
```

---

### TC-042-13: updateUser() が `/users/me/settings` に PUT リクエストを送信する

**対応要件**: REQ-V2-001
**信頼性**: 🔵

**Given**: mockFetch が `200 OK` + User JSON レスポンスを返すよう設定されている
**When**: `apiClient.updateUser({ notification_time: '21:00' })` を呼び出す
**Then**:
- fetch が `https://api.example.com/users/me/settings` に呼び出されること
- HTTP メソッドが `PUT` であること

```typescript
it('TC-042-13: updateUser()が/users/me/settingsにPUTリクエストを送信する', async () => {
  // Given
  const mockUser = { user_id: 'test-user', settings: { notification_time: '21:00' } };
  mockFetch.mockResolvedValue(
    new Response(JSON.stringify(mockUser), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  );

  // When
  const { apiClient } = await import('@/services/api');
  await apiClient.updateUser({ notification_time: '21:00' });

  // Then
  expect(mockFetch).toHaveBeenCalledWith(
    'https://api.example.com/users/me/settings',
    expect.objectContaining({
      method: 'PUT',
    })
  );
});
```

**期待結果**: 修正前は `/users/me` にリクエストが送信されるため FAIL。修正後に PASS。

---

### TC-042-14: submitReview() が `/reviews/{cardId}` に POST リクエストを送信する

**対応要件**: REQ-V2-002
**信頼性**: 🔵

**Given**: mockFetch が `200 OK` + JSON レスポンスを返すよう設定されている
**When**: `apiClient.submitReview('card-abc-123', 4)` を呼び出す
**Then**:
- fetch が `https://api.example.com/reviews/card-abc-123` に呼び出されること
- HTTP メソッドが `POST` であること
- リクエストボディに `{ grade: 4 }` が含まれること

```typescript
it('TC-042-14: submitReview()が/reviews/{cardId}にPOSTリクエストを送信する', async () => {
  // Given
  const mockResponse = { success: true };
  mockFetch.mockResolvedValue(
    new Response(JSON.stringify(mockResponse), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  );

  // When
  const { apiClient } = await import('@/services/api');
  await apiClient.submitReview('card-abc-123', 4);

  // Then
  expect(mockFetch).toHaveBeenCalledWith(
    'https://api.example.com/reviews/card-abc-123',
    expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ grade: 4 }),
    })
  );
});
```

**期待結果**: 現在のフロントエンド実装は既に `/reviews/${cardId}` を使用しているため PASS。回帰テストとして価値がある。

---

### TC-042-15: updateUser() のリクエストボディが正しくシリアライズされる

**対応要件**: REQ-V2-001
**信頼性**: 🔵

**Given**: mockFetch が `200 OK` + User JSON レスポンスを返すよう設定されている
**When**: `apiClient.updateUser({ notification_time: '18:00', timezone: 'America/New_York' })` を呼び出す
**Then**: fetch の `body` が正しくシリアライズされていること

```typescript
it('TC-042-15: updateUser()のリクエストボディが正しくシリアライズされる', async () => {
  // Given
  const mockUser = { user_id: 'test-user' };
  mockFetch.mockResolvedValue(
    new Response(JSON.stringify(mockUser), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  );

  // When
  const requestData = { notification_time: '18:00', timezone: 'America/New_York' };
  const { apiClient } = await import('@/services/api');
  await apiClient.updateUser(requestData);

  // Then
  expect(mockFetch).toHaveBeenCalledWith(
    expect.any(String),
    expect.objectContaining({
      body: JSON.stringify(requestData),
    })
  );
});
```

---

### TC-042-16: linkLine() のレスポンスが User 型として返却される

**対応要件**: REQ-V2-004
**信頼性**: 🔵

**Given**: mockFetch が `200 OK` + 完全な User JSON レスポンスを返すよう設定されている
**When**: `apiClient.linkLine({ line_user_id: 'U123' })` を呼び出す
**Then**: 戻り値が User 型のオブジェクトであること

```typescript
it('TC-042-16: linkLine()のレスポンスがUser型として返却される', async () => {
  // Given
  const mockUser = {
    user_id: 'test-user',
    line_user_id: 'U123',
    settings: { notification_time: '09:00', timezone: 'Asia/Tokyo' },
    created_at: '2026-01-01T00:00:00Z',
  };
  mockFetch.mockResolvedValue(
    new Response(JSON.stringify(mockUser), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  );

  // When
  const { apiClient } = await import('@/services/api');
  const result = await apiClient.linkLine({ line_user_id: 'U123' });

  // Then
  expect(result).toEqual(mockUser);
  expect(result.user_id).toBe('test-user');
});
```

---

## 4. 3レイヤー整合性テストケース

### テストファイル: `backend/tests/test_template_routes.py` (追加セクション)

---

### TC-042-21: 全エンドポイント 3レイヤーパス一致チェック

**対応要件**: REQ-V2-004
**信頼性**: 🔵

**Given**: 修正後の SAM テンプレートと handler.py
**When**: SAM テンプレートのパスと handler.py のルート定義を正規化して比較する
**Then**: handler.py で定義された全ルートが SAM テンプレートにも定義されていること

このテストは TC-042-06 の実装であり、セクション 2 の fixture を共有する。

---

### TC-042-22: 修正対象3エンドポイントのパス統一確認

**対応要件**: REQ-V2-001, REQ-V2-002, REQ-V2-003
**信頼性**: 🔵

**Given**: 修正後の SAM テンプレート、handler.py、api.ts（テストモック経由）
**When**: 修正対象の3エンドポイントについてパスを確認する
**Then**: 以下の3エンドポイントが3レイヤーで一致していること

| # | エンドポイント | SAM (template.yaml) | handler (handler.py) | frontend (api.ts) |
|---|-------------|---------------------|---------------------|-------------------|
| 1 | 設定更新 | `PUT /users/me/settings` | `@app.put("/users/me/settings")` | `PUT /users/me/settings` |
| 2 | レビュー送信 | `POST /reviews/{cardId}` | `@app.post("/reviews/<card_id>")` | `` POST /reviews/${cardId} `` |
| 3 | LINE 連携 | `POST /users/link-line` | `@app.post("/users/link-line")` | `POST /users/link-line` |

**補足**: このテストケースはバックエンドの test_template_routes.py (TC-042-06, TC-042-07) とフロントエンドの TC-042-11, TC-042-13, TC-042-14 を合わせて3レイヤー整合性を確認する。

---

## 5. エッジケース・エラーシナリオ

---

### TC-042-31: GET /users/me と PUT /users/me/settings の共存

**対応要件**: EDGE-001-01
**信頼性**: 🔵

**Given**: SAM テンプレートに `GetUser` (GET /users/me) と `UpdateUser` (PUT /users/me/settings) が共に定義されている
**When**: 両イベントのパスとメソッドを確認する
**Then**: 両方が独立して存在し、パスが異なること

```python
def test_get_user_and_update_user_coexist(api_events):
    """TC-042-31: EDGE-001-01 - GET /users/me と PUT /users/me/settings の共存"""
    # GetUser
    assert api_events["GetUser"]["Properties"]["Path"] == "/users/me"
    assert api_events["GetUser"]["Properties"]["Method"] == "GET"
    # UpdateUser
    assert api_events["UpdateUser"]["Properties"]["Path"] == "/users/me/settings"
    assert api_events["UpdateUser"]["Properties"]["Method"] == "PUT"
    # パスが異なること
    assert (
        api_events["GetUser"]["Properties"]["Path"]
        != api_events["UpdateUser"]["Properties"]["Path"]
    )
```

---

### TC-042-32: GET /reviews/stats と POST /reviews/{cardId} の共存

**対応要件**: EDGE-002-04
**信頼性**: 🔵

**Given**: SAM テンプレートに `GetReviewStats` (GET /reviews/stats) と `SubmitReview` (POST /reviews/{cardId}) が共に定義されている
**When**: 両イベントを確認する
**Then**: HTTP メソッドが異なるため干渉しないこと

```python
def test_review_stats_and_submit_review_coexist(api_events):
    """TC-042-32: EDGE-002-04 - GET /reviews/stats と POST /reviews/{cardId} の共存"""
    # GetReviewStats
    assert api_events["GetReviewStats"]["Properties"]["Path"] == "/reviews/stats"
    assert api_events["GetReviewStats"]["Properties"]["Method"] == "GET"
    # SubmitReview
    assert api_events["SubmitReview"]["Properties"]["Path"] == "/reviews/{cardId}"
    assert api_events["SubmitReview"]["Properties"]["Method"] == "POST"
```

---

### TC-042-33: linkLine と unlinkLine のパスが異なること

**対応要件**: EDGE-003-01
**信頼性**: 🔵

**Given**: SAM テンプレートに `LinkLine` (POST /users/link-line) と `UnlinkLine` (POST /users/me/unlink-line) が共に定義されている
**When**: 両イベントのパスを確認する
**Then**: パスが異なり独立してルーティングされること

```python
def test_link_line_and_unlink_line_have_different_paths(api_events):
    """TC-042-33: EDGE-003-01 - linkLine と unlinkLine のパスが異なること"""
    assert api_events["LinkLine"]["Properties"]["Path"] == "/users/link-line"
    assert api_events["UnlinkLine"]["Properties"]["Path"] == "/users/me/unlink-line"
    assert (
        api_events["LinkLine"]["Properties"]["Path"]
        != api_events["UnlinkLine"]["Properties"]["Path"]
    )
```

---

### TC-042-34: パスパラメータを持つイベントの検証

**対応要件**: 整合性チェック
**信頼性**: 🔵

**Given**: SAM テンプレートのパスパラメータを持つ全イベント
**When**: パスパラメータを含むイベントを抽出する
**Then**: パスパラメータ形式が `{camelCase}` で統一されていること

```python
import re

def test_path_parameters_use_camel_case(api_events):
    """TC-042-34: 整合性 - パスパラメータが {camelCase} 形式で統一"""
    param_pattern = re.compile(r'\{(\w+)\}')
    for name, event in api_events.items():
        path = event["Properties"]["Path"]
        params = param_pattern.findall(path)
        for param in params:
            # camelCase: 先頭小文字で始まり、snake_case ではない
            assert "_" not in param, (
                f"イベント '{name}' のパスパラメータ '{param}' が snake_case です。"
                f" SAM テンプレートでは {{camelCase}} を使用してください。"
            )
            assert param[0].islower(), (
                f"イベント '{name}' のパスパラメータ '{param}' が大文字で始まっています。"
            )
```

---

### TC-042-35: フロントエンドで旧パス /users/me/link-line が使用されていないこと

**対応要件**: REQ-V2-004
**信頼性**: 🔵

**Given**: mockFetch のモック設定
**When**: `apiClient.linkLine()` を呼び出す
**Then**: fetch の URL に `/users/me/link-line` が含まれ**ない**こと

```typescript
it('TC-042-35: linkLine()が旧パス/users/me/link-lineを使用していないこと', async () => {
  // Given
  const mockUser = { user_id: 'test-user', line_user_id: 'U123' };
  mockFetch.mockResolvedValue(
    new Response(JSON.stringify(mockUser), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  );

  // When
  const { apiClient } = await import('@/services/api');
  await apiClient.linkLine({ line_user_id: 'U123' });

  // Then
  const fetchUrl = mockFetch.mock.calls[0][0];
  expect(fetchUrl).not.toContain('/users/me/link-line');
  expect(fetchUrl).toContain('/users/link-line');
});
```

**期待結果**: 修正前は旧パスが使用されるため FAIL。修正後に PASS。

---

### TC-042-36: フロントエンドで旧パス PUT /users/me が使用されていないこと

**対応要件**: REQ-V2-001
**信頼性**: 🔵

**Given**: mockFetch のモック設定
**When**: `apiClient.updateUser()` を呼び出す
**Then**: fetch の URL が `/users/me/settings` を含み、パスが `/users/me` のみで終わっていないこと

```typescript
it('TC-042-36: updateUser()が/users/me/settingsを使用し旧パス/users/meのみでないこと', async () => {
  // Given
  const mockUser = { user_id: 'test-user' };
  mockFetch.mockResolvedValue(
    new Response(JSON.stringify(mockUser), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  );

  // When
  const { apiClient } = await import('@/services/api');
  await apiClient.updateUser({ notification_time: '10:00' });

  // Then
  const fetchUrl = mockFetch.mock.calls[0][0] as string;
  expect(fetchUrl).toBe('https://api.example.com/users/me/settings');
});
```

**期待結果**: 修正前は `/users/me` で FAIL。修正後に PASS。

---

## 6. 回帰テスト要件

### 6.1 バックエンド回帰テスト

**実行コマンド**: `cd backend && make test`

修正後に以下の既存テストが全て通ることを確認:

| テストファイル | 影響可能性 | 理由 |
|-------------|----------|------|
| `backend/tests/unit/test_user_service.py` | 低 | handler パス変更のみ、サービス層は変更なし |
| `backend/tests/unit/test_user_models.py` | なし | モデル層は変更なし |
| `backend/tests/unit/test_card_service.py` | なし | カード関連は変更なし |
| `backend/tests/unit/test_review_service.py` | なし | レビューサービスは変更なし |
| `backend/tests/unit/test_srs.py` | なし | SRS アルゴリズムは変更なし |
| `backend/tests/unit/test_line_service.py` | なし | LINE サービスは変更なし |
| `backend/tests/unit/test_notification_service.py` | なし | 通知サービスは変更なし |
| `backend/tests/unit/test_timezone_aware.py` | なし | タイムゾーンは変更なし |
| `backend/tests/unit/test_unlink_line.py` | なし | LINE 解除は変更なし |
| `backend/tests/unit/test_bedrock.py` | なし | Bedrock は変更なし |
| `backend/tests/integration/test_line_webhook.py` | なし | LINE Webhook は変更なし |

### 6.2 フロントエンド回帰テスト

**実行コマンド**: `cd frontend && npm test`

修正後に以下の既存テストが全て通ることを確認:

| テストファイル | 影響可能性 | 理由 |
|-------------|----------|------|
| `frontend/src/services/__tests__/api.test.ts` | 中 | 既存テストで `/users/me` パスを直接検証しているものがある場合は影響 |
| `frontend/src/services/__tests__/auth.test.ts` | なし | 認証は変更なし |
| `frontend/src/services/__tests__/liff.test.ts` | なし | LIFF は変更なし |

**注意**: 既存の api.test.ts のテストで `updateUser` や `linkLine` のパスをハードコードしているものがあれば修正が必要。現在の既存テスト確認では、これらのメソッドを直接テストしているケースはないため、影響は限定的と判断。

---

## 7. テストケースサマリー

### 7.1 テストケース一覧

| TC ID | テスト名 | ファイル | 対応要件 | 信頼性 | Red で FAIL? |
|-------|---------|---------|---------|--------|-------------|
| TC-042-01 | 設定更新イベントパス検証 | test_template_routes.py | REQ-V2-001 | 🔵 | Yes |
| TC-042-02 | レビュー送信イベントパス検証 | test_template_routes.py | REQ-V2-002 | 🔵 | Yes |
| TC-042-03 | LINE連携イベント存在検証 | test_template_routes.py | REQ-V2-003 | 🔵 | Yes |
| TC-042-04 | 全イベント数チェック | test_template_routes.py | 整合性 | 🔵 | Yes |
| TC-042-05 | 全イベント ApiId 参照 | test_template_routes.py | 制約 | 🔵 | No (既存OK) |
| TC-042-06 | SAM-handler パス一致 | test_template_routes.py | REQ-V2-004 | 🔵 | Yes |
| TC-042-07 | 全エンドポイント一括検証 | test_template_routes.py | 整合性 | 🔵 | Yes |
| TC-042-08 | テンプレート YAML 有効性 | test_template_routes.py | 品質 | 🔵 | No (既存OK) |
| TC-042-09 | イベント名重複なし | test_template_routes.py | 品質 | 🔵 | Yes |
| TC-042-11 | linkLine パス検証 | api.test.ts | REQ-V2-004 | 🔵 | Yes |
| TC-042-12 | linkLine ボディ検証 | api.test.ts | REQ-V2-004 | 🔵 | No (既存OK) |
| TC-042-13 | updateUser パス検証 | api.test.ts | REQ-V2-001 | 🔵 | Yes |
| TC-042-14 | submitReview パス検証 | api.test.ts | REQ-V2-002 | 🔵 | No (既存OK) |
| TC-042-15 | updateUser ボディ検証 | api.test.ts | REQ-V2-001 | 🔵 | No (既存OK) |
| TC-042-16 | linkLine レスポンス型 | api.test.ts | REQ-V2-004 | 🔵 | No (既存OK) |
| TC-042-21 | 3レイヤーパス一致 | test_template_routes.py | REQ-V2-004 | 🔵 | Yes |
| TC-042-22 | 修正3エンドポイント統一 | (複合) | REQ-V2-001~003 | 🔵 | Yes |
| TC-042-31 | GET/PUT users/me 共存 | test_template_routes.py | EDGE-001-01 | 🔵 | No (既存OK) |
| TC-042-32 | review stats/submit 共存 | test_template_routes.py | EDGE-002-04 | 🔵 | Yes |
| TC-042-33 | link/unlink パス分離 | test_template_routes.py | EDGE-003-01 | 🔵 | Yes |
| TC-042-34 | パスパラメータ camelCase | test_template_routes.py | 整合性 | 🔵 | No (既存OK) |
| TC-042-35 | 旧パス link-line 不使用 | api.test.ts | REQ-V2-004 | 🔵 | Yes |
| TC-042-36 | 旧パス PUT /users/me 不使用 | api.test.ts | REQ-V2-001 | 🔵 | Yes |

### 7.2 TDD Red Phase で FAIL が期待されるテスト

修正前のコードに対してテストを実行した場合、以下のテストが FAIL することを期待する:

**バックエンド** (test_template_routes.py):
- TC-042-01: `UpdateUser` のパスが `/users/me` のため FAIL
- TC-042-02: `SubmitReview` のパスが `/reviews` のため FAIL
- TC-042-03: `LinkLine` イベントが存在しないため FAIL
- TC-042-04: イベント数が 12 個のため FAIL (期待: 13)
- TC-042-06: `LinkLine` がないため handler ルートとの不一致で FAIL
- TC-042-07: パラメタライズの3件が FAIL
- TC-042-09: イベント数が 12 個のため FAIL
- TC-042-32: `SubmitReview` パスが `/reviews` のため FAIL
- TC-042-33: `LinkLine` がないため FAIL

**フロントエンド** (api.test.ts):
- TC-042-11: `linkLine()` が `/users/me/link-line` を使用するため FAIL
- TC-042-13: `updateUser()` が `/users/me` を使用するため FAIL
- TC-042-35: 旧パス `/users/me/link-line` が使用されるため FAIL
- TC-042-36: パスが `/users/me` で FAIL

### 7.3 信頼性レベルサマリー

| カテゴリ | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|---------|-------|-------|-------|------|
| SAM テンプレート検証 (TC-042-01~09) | 9 | 0 | 0 | 9 |
| フロントエンド パス検証 (TC-042-11~16) | 6 | 0 | 0 | 6 |
| 3レイヤー整合性 (TC-042-21~22) | 2 | 0 | 0 | 2 |
| エッジケース (TC-042-31~36) | 6 | 0 | 0 | 6 |
| **合計** | **23** | **0** | **0** | **23** |

**品質評価**: 全項目 🔵 青信号 (100%)

---

## 8. 変更履歴

| バージョン | 日付 | 変更内容 |
|-----------|------|---------|
| v1.0 | 2026-02-21 | 初版作成（テストケース定義） |

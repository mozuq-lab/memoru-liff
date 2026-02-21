# TASK-0042: APIルート統一（3レイヤー整合性修正）- TDD要件定義

**作成日**: 2026-02-21
**関連タスク**: TASK-0042
**関連要件**: REQ-V2-001, REQ-V2-002, REQ-V2-003, REQ-V2-004
**タスクタイプ**: TDD
**ドキュメントバージョン**: v1.0

---

## 1. 要件概要

SAM テンプレート (`backend/template.yaml`)、Lambda ハンドラー (`backend/src/api/handler.py`)、フロントエンド API クライアント (`frontend/src/services/api.ts`) の3レイヤーで API パスが不一致になっている問題を修正する。設計文書 (`docs/design/code-review-fixes-v2/api-endpoints.md`) の定義を Single Source of Truth (SSOT) とし、3つのエンドポイントのパスを統一する。

### 1.1 正規パス定義（api-endpoints.md 準拠）

| エンドポイント | 正規パス | HTTP メソッド |
|---------------|---------|-------------|
| 設定更新 | `/users/me/settings` | PUT |
| レビュー送信 | `/reviews/{cardId}` | POST |
| LINE 連携 | `/users/link-line` | POST |

### 1.2 修正対象レイヤーの優先順序

1. **設計文書** (`api-endpoints.md`) = 定義元（変更不要）
2. **SAM テンプレート** (`template.yaml`) = インフラ SSOT（修正対象）
3. **Lambda ハンドラー** (`handler.py`) = 実装（変更不要：既に正規パスと一致）
4. **フロントエンド API** (`api.ts`) = 呼び出し側（修正対象）

---

## 2. REQ-V2-001: 設定更新エンドポイント SAM パス修正

### 2.1 現在の状態

| レイヤー | ファイル | 行番号 | 現在のパス | 期待パス | 状態 |
|---------|--------|--------|-----------|---------|------|
| SAM テンプレート | `backend/template.yaml` | L255-260 | `PUT /users/me` | `PUT /users/me/settings` | **不一致** |
| Lambda ハンドラー | `backend/src/api/handler.py` | L151 | `PUT /users/me/settings` | `PUT /users/me/settings` | 一致 |
| Frontend API | `frontend/src/services/api.ts` | L141-145 | `PUT /users/me` | `PUT /users/me/settings` | **不一致** |

### 2.2 受け入れ基準（EARS記法）

#### REQ-V2-001-AC01: SAM テンプレート修正 🔵

**信頼性**: 🔵 *CR-01: SAM L255-260 の `UpdateUser` イベントが `PUT /users/me` で handler の `PUT /users/me/settings` と不一致。api-endpoints.md に準拠*

**Where** `backend/template.yaml` の `ApiFunction.Properties.Events.UpdateUser` セクション（L255-260）において、
**When** API Gateway が PUT リクエストを受信した場合、
**the system shall** パス `/users/me/settings` でルーティングする。

**具体的な変更内容**:

```yaml
# Before (L255-260):
UpdateUser:
  Type: HttpApi
  Properties:
    ApiId: !Ref HttpApi
    Path: /users/me
    Method: PUT

# After:
UpdateUser:
  Type: HttpApi
  Properties:
    ApiId: !Ref HttpApi
    Path: /users/me/settings
    Method: PUT
```

**検証方法**:
- template.yaml をパースし、`UpdateUser` イベントの `Path` が `/users/me/settings` であること
- `Method` が `PUT` であること
- `ApiId` が `!Ref HttpApi` であること

#### REQ-V2-001-AC02: フロントエンド API パス修正 🔵

**信頼性**: 🔵 *CR-01: api.ts L141-145 の `updateUser()` が `/users/me` で handler の `/users/me/settings` と不一致*

**Where** `frontend/src/services/api.ts` の `updateUser()` メソッド（L141-145）において、
**When** ユーザー設定更新リクエストを送信する場合、
**the system shall** パス `/users/me/settings` に PUT リクエストを送信する。

**具体的な変更内容**:

```typescript
// Before (L141-145):
async updateUser(data: UpdateUserRequest): Promise<User> {
  return this.request<User>('/users/me', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

// After:
async updateUser(data: UpdateUserRequest): Promise<User> {
  return this.request<User>('/users/me/settings', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}
```

**検証方法**:
- `updateUser()` を呼び出した際、fetch が `${API_BASE_URL}/users/me/settings` に PUT リクエストを送信すること
- リクエストボディが正しく JSON シリアライズされること
- レスポンスが `User` 型として返却されること

### 2.3 エッジケース・エラーシナリオ

| ID | シナリオ | 期待動作 | 信頼性 |
|----|---------|---------|--------|
| EDGE-001-01 | `GET /users/me` と `PUT /users/me/settings` の共存 | 両方が独立してルーティングされる（`GET /users/me` は変更なし） | 🔵 |
| EDGE-001-02 | `PUT /users/me` に対する旧パスへのリクエスト | API Gateway が 404 を返す（SAM 修正後） | 🔵 |

---

## 3. REQ-V2-002: レビュー送信エンドポイント SAM パス修正

### 3.1 現在の状態

| レイヤー | ファイル | 行番号 | 現在のパス | 期待パス | 状態 |
|---------|--------|--------|-----------|---------|------|
| SAM テンプレート | `backend/template.yaml` | L305-310 | `POST /reviews` | `POST /reviews/{cardId}` | **不一致** |
| Lambda ハンドラー | `backend/src/api/handler.py` | L493 | `POST /reviews/<card_id>` | `POST /reviews/{cardId}` | 一致 |
| Frontend API | `frontend/src/services/api.ts` | L129-133 | `` POST /reviews/${cardId} `` | `POST /reviews/{cardId}` | 一致 |

### 3.2 受け入れ基準（EARS記法）

#### REQ-V2-002-AC01: SAM テンプレート修正 🔵

**信頼性**: 🔵 *CR-01: SAM L305-310 の `SubmitReview` イベントが `POST /reviews` でパスパラメータなし。handler は `/reviews/<card_id>` で一致*

**Where** `backend/template.yaml` の `ApiFunction.Properties.Events.SubmitReview` セクション（L305-310）において、
**When** API Gateway が POST リクエストを受信した場合、
**the system shall** パス `/reviews/{cardId}` でルーティングし、パスパラメータ `cardId` を Lambda ハンドラーに渡す。

**具体的な変更内容**:

```yaml
# Before (L305-310):
SubmitReview:
  Type: HttpApi
  Properties:
    ApiId: !Ref HttpApi
    Path: /reviews
    Method: POST

# After:
SubmitReview:
  Type: HttpApi
  Properties:
    ApiId: !Ref HttpApi
    Path: /reviews/{cardId}
    Method: POST
```

**検証方法**:
- template.yaml をパースし、`SubmitReview` イベントの `Path` が `/reviews/{cardId}` であること
- パスパラメータ `{cardId}` が含まれていること
- `Method` が `POST` であること

### 3.3 エッジケース・エラーシナリオ

| ID | シナリオ | 期待動作 | 信頼性 |
|----|---------|---------|--------|
| EDGE-002-01 | `POST /reviews` にパスパラメータなしでリクエスト | API Gateway が 404 を返す（SAM 修正後） | 🔵 |
| EDGE-002-02 | `POST /reviews/{cardId}` でカードIDが存在しない | handler.py が 404 `Card not found` を返す（既存動作） | 🔵 |
| EDGE-002-03 | `POST /reviews/{cardId}` でカードIDが空文字列 | API Gateway レベルでマッチしない（パスパラメータは必須） | 🟡 |
| EDGE-002-04 | `GET /reviews/stats` との共存 | `GET /reviews/stats` が先にマッチし、`POST /reviews/{cardId}` と干渉しない | 🔵 |

---

## 4. REQ-V2-003: LINE 連携エンドポイント SAM イベント定義追加

### 4.1 現在の状態

| レイヤー | ファイル | 行番号 | 現在のパス | 期待パス | 状態 |
|---------|--------|--------|-----------|---------|------|
| SAM テンプレート | `backend/template.yaml` | - | **定義なし** | `POST /users/link-line` | **欠落** |
| Lambda ハンドラー | `backend/src/api/handler.py` | L104 | `POST /users/link-line` | `POST /users/link-line` | 一致 |
| Frontend API | `frontend/src/services/api.ts` | L148-153 | `POST /users/me/link-line` | `POST /users/link-line` | **不一致** |

### 4.2 受け入れ基準（EARS記法）

#### REQ-V2-003-AC01: SAM テンプレート イベント追加 🔵

**信頼性**: 🔵 *CR-01: SAM テンプレートに LINE 連携 (`POST /users/link-line`) のイベント定義が完全に欠落*

**Where** `backend/template.yaml` の `ApiFunction.Properties.Events` セクションにおいて、
**the system shall** `LinkLine` イベント定義を新規追加し、パス `/users/link-line`、メソッド `POST` で API Gateway にルーティングを設定する。

**具体的な変更内容**:

```yaml
# backend/template.yaml - ApiFunction.Properties.Events に追加
# UnlinkLine イベント (L261-266) の後に挿入

LinkLine:
  Type: HttpApi
  Properties:
    ApiId: !Ref HttpApi
    Path: /users/link-line
    Method: POST
```

**挿入位置**: `UnlinkLine` イベント（L261-266）の直後、`# Card endpoints` コメント（L267）の直前

**検証方法**:
- template.yaml をパースし、`LinkLine` イベントが存在すること
- `Path` が `/users/link-line` であること
- `Method` が `POST` であること
- `ApiId` が `!Ref HttpApi` であること
- `Type` が `HttpApi` であること

### 4.3 エッジケース・エラーシナリオ

| ID | シナリオ | 期待動作 | 信頼性 |
|----|---------|---------|--------|
| EDGE-003-01 | `POST /users/link-line` と `POST /users/me/unlink-line` の共存 | 異なるパスのため独立してルーティングされる | 🔵 |
| EDGE-003-02 | SAM テンプレートに重複イベント名が存在 | `sam build` がエラーを返す（テスト対象外、ビルド確認で検出） | 🔵 |

---

## 5. REQ-V2-004: フロントエンド LINE 連携パス修正

### 5.1 現在の状態

| レイヤー | ファイル | 行番号 | 現在のパス | 期待パス | 状態 |
|---------|--------|--------|-----------|---------|------|
| Frontend API | `frontend/src/services/api.ts` | L148-153 | `POST /users/me/link-line` | `POST /users/link-line` | **不一致** |

### 5.2 受け入れ基準（EARS記法）

#### REQ-V2-004-AC01: linkLine() メソッドのパス修正 🔵

**信頼性**: 🔵 *CR-01: api.ts L148-153 の `linkLine()` が `/users/me/link-line` で handler `/users/link-line` と不一致*

**Where** `frontend/src/services/api.ts` の `linkLine()` メソッド（L148-153）において、
**When** LINE 連携リクエストを送信する場合、
**the system shall** パス `/users/link-line` に POST リクエストを送信する。

**具体的な変更内容**:

```typescript
// Before (L148-153):
async linkLine(data: LinkLineRequest): Promise<User> {
  return this.request<User>('/users/me/link-line', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// After:
async linkLine(data: LinkLineRequest): Promise<User> {
  return this.request<User>('/users/link-line', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
```

**検証方法**:
- `linkLine()` を呼び出した際、fetch が `${API_BASE_URL}/users/link-line` に POST リクエストを送信すること
- リクエストボディが正しく JSON シリアライズされること
- レスポンスが `User` 型として返却されること

### 5.3 エッジケース・エラーシナリオ

| ID | シナリオ | 期待動作 | 信頼性 |
|----|---------|---------|--------|
| EDGE-004-01 | `linkLine()` に空の data オブジェクトを渡した場合 | リクエストは送信されるが、バックエンドで 400 バリデーションエラー | 🔵 |
| EDGE-004-02 | `linkLine()` の戻り値の型一致 | `User` 型のオブジェクトが返却される（型チェックで検証） | 🔵 |

---

## 6. 3レイヤー整合性テスト要件

### 6.1 全エンドポイント整合性チェック 🔵

**信頼性**: 🔵 *CR-01: 修正後の全エンドポイントで 3レイヤーのパスが完全一致すること*

**the system shall** 以下の全12エンドポイントについて、SAM テンプレート、Lambda ハンドラー、フロントエンド API クライアントの3レイヤーでパスが完全一致すること。

| # | HTTP メソッド | 正規パス | SAM イベント名 | handler デコレータ | api.ts メソッド |
|---|-------------|---------|--------------|-------------------|---------------|
| 1 | GET | `/users/me` | `GetUser` (L249-254) | `@app.get("/users/me")` (L89) | `getCurrentUser()` (L137-139) |
| 2 | PUT | `/users/me/settings` | `UpdateUser` (L255-260) **修正** | `@app.put("/users/me/settings")` (L151) | `updateUser()` (L141-145) **修正** |
| 3 | POST | `/users/link-line` | `LinkLine` **新規追加** | `@app.post("/users/link-line")` (L104) | `linkLine()` (L148-153) **修正** |
| 4 | POST | `/users/me/unlink-line` | `UnlinkLine` (L261-266) | `@app.post("/users/me/unlink-line")` (L198) | *未実装（TASK-0045 対応）* |
| 5 | GET | `/cards` | `ListCards` (L268-272) | `@app.get("/cards")` (L307) | `getCards()` (L82-85) |
| 6 | POST | `/cards` | `CreateCard` (L273-277) | `@app.post("/cards")` (L337) | `createCard()` (L91-96) |
| 7 | GET | `/cards/{cardId}` | `GetCard` (L278-282) | `@app.get("/cards/<card_id>")` (L385) | `getCard()` (L87-89) |
| 8 | PUT | `/cards/{cardId}` | `UpdateCard` (L283-287) | `@app.put("/cards/<card_id>")` (L402) | `updateCard()` (L98-103) |
| 9 | DELETE | `/cards/{cardId}` | `DeleteCard` (L288-292) | `@app.delete("/cards/<card_id>")` (L443) | `deleteCard()` (L105-109) |
| 10 | GET | `/cards/due` | `GetDueCards` (L299-303) | `@app.get("/cards/due")` (L469) | `getDueCards()` (L118-121) |
| 11 | POST | `/reviews/{cardId}` | `SubmitReview` (L305-310) **修正** | `@app.post("/reviews/<card_id>")` (L493) | `submitReview()` (L129-133) |
| 12 | POST | `/cards/generate` | `GenerateCards` (L317-321) | `@app.post("/cards/generate")` (L224) | `generateCards()` (L111-116) |

**注記**:
- Lambda Powertools の `APIGatewayHttpResolver` はパスパラメータを `<param_name>` 形式で記述する（例: `/cards/<card_id>`）
- SAM テンプレートは `{paramName}` 形式（例: `/cards/{cardId}`）
- これらは同一のパスとして扱われる（camelCase/snake_case の変換は API Gateway と Powertools が自動処理）
- `GET /reviews/stats` は SAM テンプレート (L311-316) に定義あり。handler.py には直接ルート定義がないが、テンプレート上は存在する

### 6.2 SAM テンプレートパス検証テスト要件 🔵

**信頼性**: 🔵 *REQ-V2-004: 3レイヤー整合性テスト*

**テストファイル**: `backend/tests/test_template_routes.py`

**テスト方針**:
- `backend/template.yaml` を YAML としてパースする
- `ApiFunction.Properties.Events` セクションから全 `HttpApi` イベントを抽出する
- 各イベントの `Path` と `Method` が期待値と一致することを検証する

#### テストケース一覧

| TC ID | テストケース | 対応要件 | 信頼性 |
|-------|------------|---------|--------|
| TC-042-01 | 設定更新イベントのパスが `/users/me/settings`、メソッドが `PUT` | REQ-V2-001 | 🔵 |
| TC-042-02 | レビュー送信イベントのパスが `/reviews/{cardId}`、メソッドが `POST` | REQ-V2-002 | 🔵 |
| TC-042-03 | LINE 連携イベントが存在し、パスが `/users/link-line`、メソッドが `POST` | REQ-V2-003 | 🔵 |
| TC-042-04 | 全 HttpApi イベントの総数が 13 個（12 + GetReviewStats）であること | 整合性 | 🔵 |
| TC-042-05 | 全イベントが `ApiId: !Ref HttpApi` を参照していること | 制約 | 🔵 |
| TC-042-06 | SAM テンプレートの全パスが handler.py のルート定義と一致すること | 整合性 | 🔵 |

#### TC-042-01: 設定更新イベント パス検証

```python
def test_update_user_event_path_is_users_me_settings():
    """REQ-V2-001: SAM テンプレートの設定更新イベントパスが PUT /users/me/settings"""
    # Given: 修正後の SAM テンプレート
    # When: UpdateUser イベントの Path を取得
    # Then: Path == "/users/me/settings" AND Method == "PUT"
```

#### TC-042-02: レビュー送信イベント パス検証

```python
def test_submit_review_event_path_has_card_id_parameter():
    """REQ-V2-002: SAM テンプレートのレビュー送信イベントパスが POST /reviews/{cardId}"""
    # Given: 修正後の SAM テンプレート
    # When: SubmitReview イベントの Path を取得
    # Then: Path == "/reviews/{cardId}" AND Method == "POST"
    # Then: パスに "{cardId}" パラメータが含まれること
```

#### TC-042-03: LINE 連携イベント 存在検証

```python
def test_link_line_event_exists_with_correct_path():
    """REQ-V2-003: SAM テンプレートに LINE 連携エンドポイント POST /users/link-line が定義"""
    # Given: 修正後の SAM テンプレート
    # When: LinkLine イベントの存在を確認
    # Then: LinkLine イベントが存在すること
    # Then: Path == "/users/link-line" AND Method == "POST"
    # Then: Type == "HttpApi"
```

#### TC-042-04: 全イベント数チェック

```python
def test_total_http_api_event_count():
    """整合性: ApiFunction の HttpApi イベント総数が期待通りであること"""
    # Given: 修正後の SAM テンプレート
    # When: ApiFunction の Events で Type == "HttpApi" のイベント数をカウント
    # Then: 13 個（既存12 + LinkLine 追加1）
```

#### TC-042-05: ApiId 統一チェック

```python
def test_all_events_reference_http_api():
    """制約: 全 HttpApi イベントが ApiId で HttpApi を参照していること"""
    # Given: 修正後の SAM テンプレート
    # When: 全 HttpApi イベントの ApiId を確認
    # Then: 全て ApiId が設定されていること（CloudFormation 参照形式）
```

#### TC-042-06: SAM パスと handler ルート定義の一致

```python
def test_sam_paths_match_handler_routes():
    """整合性: SAM テンプレートの全パスが handler.py のルート定義と対応すること"""
    # Given: 修正後の SAM テンプレートと handler.py
    # When: SAM の全 HttpApi イベントパスを抽出
    # And: handler.py の全 @app.{method}() デコレータからパスを抽出
    # Then: SAM のパスセット（正規化後）== handler のパスセット（正規化後）
    # 正規化: {paramName} → <param_name> 変換、またはその逆
```

### 6.3 フロントエンド API パス検証テスト要件 🔵

**信頼性**: 🔵 *REQ-V2-004: フロントエンドのパス修正確認*

**テストファイル**: `frontend/src/services/__tests__/api.test.ts`

#### テストケース一覧

| TC ID | テストケース | 対応要件 | 信頼性 |
|-------|------------|---------|--------|
| TC-042-11 | `linkLine()` が `/users/link-line` に POST リクエストを送信する | REQ-V2-004 | 🔵 |
| TC-042-12 | `linkLine()` のリクエストボディが正しくシリアライズされる | REQ-V2-004 | 🔵 |
| TC-042-13 | `updateUser()` が `/users/me/settings` に PUT リクエストを送信する | REQ-V2-001 | 🔵 |
| TC-042-14 | `submitReview()` が `/reviews/{cardId}` に POST リクエストを送信する | REQ-V2-002 | 🔵 |

#### TC-042-11: linkLine パス検証

```typescript
it('TC-042-11: linkLine()が/users/link-lineにPOSTリクエストを送信する', async () => {
  // Given: mockFetch が 200 + User JSON レスポンスを返すよう設定
  // When: apiClient.linkLine({ line_user_id: 'U123' }) を呼び出す
  // Then: fetch が '${API_BASE_URL}/users/link-line' に POST で呼ばれること
  // Then: Authorization ヘッダーが付与されること（トークン設定時）
});
```

#### TC-042-12: linkLine リクエストボディ検証

```typescript
it('TC-042-12: linkLine()のリクエストボディが正しくシリアライズされる', async () => {
  // Given: mockFetch が 200 + User JSON レスポンスを返すよう設定
  // When: apiClient.linkLine({ line_user_id: 'U123' }) を呼び出す
  // Then: fetch の body が JSON.stringify({ line_user_id: 'U123' }) であること
});
```

#### TC-042-13: updateUser パス検証

```typescript
it('TC-042-13: updateUser()が/users/me/settingsにPUTリクエストを送信する', async () => {
  // Given: mockFetch が 200 + User JSON レスポンスを返すよう設定
  // When: apiClient.updateUser({ notification_time: '21:00' }) を呼び出す
  // Then: fetch が '${API_BASE_URL}/users/me/settings' に PUT で呼ばれること
});
```

#### TC-042-14: submitReview パス検証

```typescript
it('TC-042-14: submitReview()が/reviews/{cardId}にPOSTリクエストを送信する', async () => {
  // Given: mockFetch が 200 + JSON レスポンスを返すよう設定
  // When: apiClient.submitReview('card-123', 4) を呼び出す
  // Then: fetch が '${API_BASE_URL}/reviews/card-123' に POST で呼ばれること
});
```

---

## 7. 回帰テスト要件

### 7.1 既存バックエンドテスト 🔵

**信頼性**: 🔵 *修正後の全テスト通過を確認*

**the system shall** 以下の既存テストスイートが修正後もすべて通ること。

| テストファイル | テスト内容 | 影響可能性 |
|-------------|---------|----------|
| `backend/tests/unit/test_user_service.py` | ユーザーサービスのCRUD | 低（handler パス変更のみ） |
| `backend/tests/unit/test_user_models.py` | ユーザーモデルのバリデーション | なし |
| `backend/tests/unit/test_card_service.py` | カードサービスのCRUD | なし |
| `backend/tests/unit/test_review_service.py` | レビューサービス | なし |
| `backend/tests/unit/test_srs.py` | SRS アルゴリズム | なし |
| `backend/tests/unit/test_line_service.py` | LINE サービス | なし |
| `backend/tests/unit/test_notification_service.py` | 通知サービス | なし |
| `backend/tests/unit/test_timezone_aware.py` | タイムゾーン判定 | なし |
| `backend/tests/unit/test_unlink_line.py` | LINE 解除 | なし |
| `backend/tests/unit/test_bedrock.py` | Bedrock AI 生成 | なし |
| `backend/tests/integration/test_line_webhook.py` | LINE Webhook | なし |

**実行コマンド**: `cd backend && make test`

### 7.2 既存フロントエンドテスト 🔵

**信頼性**: 🔵 *修正後の全テスト通過を確認*

**the system shall** 以下の既存テストスイートが修正後もすべて通ること。

| テストファイル | テスト内容 | 影響可能性 |
|-------------|---------|----------|
| `frontend/src/services/__tests__/api.test.ts` | API クライアント | 中（パス変更による影響確認） |
| `frontend/src/services/__tests__/auth.test.ts` | 認証サービス | なし |
| `frontend/src/services/__tests__/liff.test.ts` | LIFF サービス | なし |

**実行コマンド**: `cd frontend && npm test`

---

## 8. 品質指標

### 8.1 テストカバレッジ要件 🔵

**信頼性**: 🔵 *CLAUDE.md 指定要件*

| 指標 | 目標値 | 測定方法 |
|------|-------|---------|
| バックエンド テストカバレッジ | 80% 以上 | `cd backend && make test` （pytest-cov） |
| フロントエンド テストカバレッジ | 80% 以上 | `cd frontend && npm test -- --coverage` |
| 既存テスト通過率 | 100% | 全テストがパスすること |
| TypeScript 型チェック | エラー 0 件 | `cd frontend && npm run type-check` |

### 8.2 SAM ビルド確認 🔵

**信頼性**: 🔵 *SAM テンプレート修正後の整合性確認*

**the system shall** `cd backend && make build` が正常に完了すること。

---

## 9. 制約事項

### 9.1 本タスクのスコープ制限

| 制約 | 内容 | 理由 |
|------|------|------|
| パスのみ修正 | `linkLine()` の引数型変更は **TASK-0044** で実施 | H-01 LINE連携本人性検証は別タスク |
| レスポンス DTO | レスポンス形式の変更は **TASK-0045** で実施 | H-02 レスポンスDTO統一は別タスク |
| unlinkLine API | フロントエンドの `unlinkLine()` メソッド追加は **TASK-0045** で実施 | H-02 の範囲 |
| SAM SSOT | SAM テンプレートが API パスの実装定義元 | 設計文書 api-endpoints.md が最上位定義 |
| デプロイ | AWS リソースの実際のデプロイはユーザーが手動で実行 | CLAUDE.md の注意事項 |
| handler 変更なし | Lambda ハンドラーのルート定義は変更不要（既に正規パスと一致） | コード分析で確認済み |

### 9.2 SAM テンプレート特記事項

- イベントタイプは `HttpApi` （REST API ではない）
- 全イベントは `ApiId: !Ref HttpApi` で HTTP API にバインド
- Method は大文字指定（`GET`, `POST`, `PUT`, `DELETE`）- 既存テンプレートの慣例に従う
- パスパラメータは `{camelCase}` 形式（例: `{cardId}`）
- `GetReviewStats` イベント（`GET /reviews/stats`）は L311-316 に存在し、handler.py にはルート定義がない（別パス or 未実装の可能性あり）。本タスクの修正対象外

---

## 10. 修正ファイルサマリー

| # | ファイル | 変更種別 | 変更内容 | 対応要件 |
|---|--------|---------|---------|---------|
| 1 | `backend/template.yaml` L255-260 | **修正** | `UpdateUser` パス: `/users/me` → `/users/me/settings` | REQ-V2-001 |
| 2 | `backend/template.yaml` L305-310 | **修正** | `SubmitReview` パス: `/reviews` → `/reviews/{cardId}` | REQ-V2-002 |
| 3 | `backend/template.yaml` (L261-266 後) | **追加** | `LinkLine` イベント: `POST /users/link-line` | REQ-V2-003 |
| 4 | `frontend/src/services/api.ts` L142 | **修正** | `updateUser()` パス: `/users/me` → `/users/me/settings` | REQ-V2-001 |
| 5 | `frontend/src/services/api.ts` L149 | **修正** | `linkLine()` パス: `/users/me/link-line` → `/users/link-line` | REQ-V2-004 |
| 6 | `backend/tests/test_template_routes.py` | **新規** | SAM テンプレートパス検証テスト | REQ-V2-001~004 |
| 7 | `frontend/src/services/__tests__/api.test.ts` | **追加** | フロントエンドパス検証テスト | REQ-V2-001~004 |

---

## 11. 信頼性レベルサマリー

### 項目別信頼性

| カテゴリ | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|---------|-------|-------|-------|------|
| 受け入れ基準 | 5 | 0 | 0 | 5 |
| テストケース（Backend） | 6 | 0 | 0 | 6 |
| テストケース（Frontend） | 4 | 0 | 0 | 4 |
| エッジケース | 7 | 1 | 0 | 8 |
| 品質指標 | 3 | 0 | 0 | 3 |
| 回帰テスト | 2 | 0 | 0 | 2 |

### 全体評価

- **総項目数**: 28 項目
- 🔵 **青信号**: 27 項目 (96%)
- 🟡 **黄信号**: 1 項目 (4%) - EDGE-002-03: 空パスパラメータのAPI Gatewayレベル挙動
- 🔴 **赤信号**: 0 項目 (0%)

**品質評価**: 高品質（青信号が 96%、赤信号なし）

---

## 12. 変更履歴

| バージョン | 日付 | 変更内容 |
|-----------|------|---------|
| v1.0 | 2026-02-21 | 初版作成（TDD要件定義） |

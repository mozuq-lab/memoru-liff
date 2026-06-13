# code-review-fixes-v2 API エンドポイント仕様（変更差分）

**作成日**: 2026-02-17
**関連設計**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/code-review-fixes-v2/requirements.md)
**既存 API 仕様**: [api-endpoints.md](../memoru-liff/api-endpoints.md)

**【信頼性レベル凡例】**:

- 🔵 **青信号**: 要件定義書・設計文書・ユーザヒアリング・コード分析から確実な定義
- 🟡 **黄信号**: 要件定義書・設計文書から妥当な推測による定義
- 🔴 **赤信号**: 要件定義書・設計文書にない推測による定義

---

## 変更概要

本文書は既存 API 仕様（`docs/design/memoru-liff/api-endpoints.md`）からの **変更差分のみ** を記載する。変更がないエンドポイントは既存仕様を参照。

| エンドポイント | 変更種別 | 対応項目 |
|---------------|---------|---------|
| POST /users/link-line | **リクエスト変更** + SAM定義追加 | CR-01, H-01 |
| PUT /users/me/settings | **SAM定義修正** + レスポンス統一 | CR-01, H-02 |
| POST /reviews/{cardId} | **SAM定義修正** | CR-01 |
| POST /users/me/unlink-line | **フロントエンド連携修正** | H-02 |

---

## POST /users/link-line（変更） 🔵

**信頼性**: 🔵 *H-01: ユーザヒアリングで LIFF IDトークン検証方式に決定*

**関連要件**: REQ-V2-021〜023, REQ-V2-121

**変更点**:

1. リクエストボディを `line_user_id` から `id_token` に変更
2. サーバー側で LINE API によるID トークン検証を追加
3. レスポンスを User 型オブジェクトに変更
4. SAM テンプレートにイベント定義を追加

### SAM テンプレート追加 🔵

```yaml
# backend/template.yaml に追加
LinkLineEvent:
  Type: Api
  Properties:
    Path: /users/link-line
    Method: post
    RestApiId: !Ref MemoruApi
```

### リクエスト（変更後） 🔵

```json
{
  "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**変更前**:

```json
{
  "line_user_id": "U1234567890abcdef"
}
```

**バリデーション**:

- `id_token`: 必須、非空文字列

### レスポンス（成功）（変更後） 🔵

```json
{
  "success": true,
  "data": {
    "user_id": "keycloak-sub-uuid",
    "display_name": "Memoru User",
    "picture_url": "https://example.com/profile.png",
    "line_linked": true,
    "notification_time": "09:00",
    "timezone": "Asia/Tokyo",
    "day_start_hour": 4,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-02-17T10:00:00Z"
  }
}
```

**変更前**:

```json
{
  "success": true,
  "data": {
    "user_id": "keycloak-sub-uuid",
    "line_user_id": "U1234567890abcdef",
    "linked_at": "2026-01-05T10:00:00Z"
  }
}
```

### エラーコード（追加） 🔵

| HTTPステータス | コード | 説明 |
|---------------|--------|------|
| 400 | `VALIDATION_ERROR` | id_token が空または未送信 |
| 401 | `ID_TOKEN_INVALID` | LINE ID トークン検証失敗（無効/期限切れ） |
| 409 | `ALREADY_LINKED` | 既に別の LINE アカウントと連携済み |
| 409 | `LINE_ID_IN_USE` | この LINE ID は別のユーザーが使用中 |

### サーバー側処理フロー 🔵

1. リクエストから `id_token` を取得
2. LINE API `POST https://api.line.me/oauth2/v2.1/verify` で検証
   - パラメータ: `id_token`, `client_id` (LIFF Channel ID)
3. 検証成功: レスポンスの `sub` フィールドから `line_user_id` を取得
4. 検証失敗: `401 ID_TOKEN_INVALID` を返却
5. `user_service.link_line(user_id, line_user_id)` で連携
6. 更新後の User オブジェクトを返却

---

## PUT /users/me/settings（変更） 🔵

**信頼性**: 🔵 *CR-01: SAMパス修正、H-02: レスポンス統一*

**関連要件**: REQ-V2-001, REQ-V2-031

**変更点**:

1. SAM テンプレートのパスを `/users/me` → `/users/me/settings` に修正
2. レスポンスを User 型オブジェクトに変更

### SAM テンプレート修正 🔵

```yaml
# backend/template.yaml
# Before:
UpdateSettingsEvent:
  Type: Api
  Properties:
    Path: /users/me
    Method: put

# After:
UpdateSettingsEvent:
  Type: Api
  Properties:
    Path: /users/me/settings
    Method: put
```

### リクエスト（変更なし） 🔵

```json
{
  "notification_time": "21:00",
  "timezone": "Asia/Tokyo"
}
```

**バリデーション**:

- `notification_time`: オプション、HH:mm 形式（00:00〜23:59）
- `timezone`: オプション、IANA タイムゾーン名

### レスポンス（成功）（変更後） 🔵

```json
{
  "success": true,
  "data": {
    "user_id": "keycloak-sub-uuid",
    "display_name": "Memoru User",
    "picture_url": "https://example.com/profile.png",
    "line_linked": true,
    "notification_time": "21:00",
    "timezone": "Asia/Tokyo",
    "day_start_hour": 4,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-02-17T10:00:00Z"
  }
}
```

**変更前**:

```json
{
  "success": true,
  "settings": {
    "notification_time": "21:00",
    "updated_at": "2026-01-05T10:00:00Z"
  }
}
```

---

## POST /reviews/{cardId}（SAM修正のみ） 🔵

**信頼性**: 🔵 *CR-01: SAMパス修正*

**関連要件**: REQ-V2-002

**変更点**: SAM テンプレートのパスにパスパラメータを追加

### SAM テンプレート修正 🔵

```yaml
# backend/template.yaml
# Before:
SubmitReviewEvent:
  Type: Api
  Properties:
    Path: /reviews
    Method: post

# After:
SubmitReviewEvent:
  Type: Api
  Properties:
    Path: /reviews/{cardId}
    Method: post
```

リクエスト/レスポンスは変更なし。既存 API 仕様を参照。

---

## POST /users/me/unlink-line（フロントエンド連携修正） 🔵

**信頼性**: 🔵 *H-02: フロントエンドが専用 API を使用していない問題*

**関連要件**: REQ-V2-033

**変更点**: フロントエンドの LINE 連携解除で専用エンドポイントを使用するよう修正

### フロントエンド修正 🔵

```typescript
// frontend/src/services/api.ts に追加
async unlinkLine(): Promise<User> {
  const response = await this.request<{ success: boolean; data: User }>('/users/me/unlink-line', {
    method: 'POST',
  });
  return response.data;
}
```

```typescript
// frontend/src/pages/LinkLinePage.tsx
// Before:
const updatedUser = await usersApi.updateUser({ line_user_id: null });

// After:
const updatedUser = await usersApi.unlinkLine();
```

バックエンド側は前回修正（TASK-0033）で実装済み。レスポンスの統一のみ確認。

### レスポンス（確認） 🔵

```json
{
  "success": true,
  "data": {
    "user_id": "keycloak-sub-uuid",
    "display_name": "Memoru User",
    "picture_url": "https://example.com/profile.png",
    "line_linked": false,
    "notification_time": "09:00",
    "timezone": "Asia/Tokyo",
    "day_start_hour": 4,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-02-17T10:00:00Z"
  }
}
```

---

## User 型定義（レスポンス共通） 🔵

**信頼性**: 🔵 *H-02: 全ユーザー関連エンドポイントで統一する型*

設定更新、LINE 連携、LINE 連携解除の全エンドポイントで返却する User 型:

```typescript
interface User {
  user_id: string;
  display_name: string | null;
  picture_url: string | null;
  line_linked: boolean;
  notification_time: string | null; // HH:mm
  timezone: string;                 // IANA timezone name
  day_start_hour: number;           // 0-23
  created_at: string;               // ISO 8601
  updated_at: string | null;        // ISO 8601
}
```

更新系エンドポイントは共通して `{ success: true, data: User }` を返却する。

---

## 3レイヤー整合性チェック表 🔵

**信頼性**: 🔵 *CR-01: 修正後の全エンドポイント整合性*

修正後の全エンドポイントについて、3レイヤーの整合性を確認:

| エンドポイント | SAM template | handler.py | api.ts | 状態 |
|---------------|-------------|------------|--------|------|
| GET /users/me | ✓ | ✓ | ✓ | ✓ 一致 |
| PUT /users/me/settings | **修正** | ✓ | **確認** | ✓ 一致 |
| POST /users/link-line | **追加** | ✓ | **修正** | ✓ 一致 |
| POST /users/me/unlink-line | ✓ | ✓ | **追加** | ✓ 一致 |
| GET /cards | ✓ | ✓ | ✓ | ✓ 一致 |
| POST /cards | ✓ | ✓ | ✓ | ✓ 一致 |
| GET /cards/{cardId} | ✓ | ✓ | ✓ | ✓ 一致 |
| PUT /cards/{cardId} | ✓ | ✓ | ✓ | ✓ 一致 |
| DELETE /cards/{cardId} | ✓ | ✓ | ✓ | ✓ 一致 |
| GET /cards/due | ✓ | ✓ | ✓ | ✓ 一致 |
| POST /reviews/{cardId} | **修正** | ✓ | ✓ | ✓ 一致 |
| POST /cards/generate | ✓ | ✓ | ✓ | ✓ 一致 |

---

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **既存 API 仕様**: [api-endpoints.md](../memoru-liff/api-endpoints.md)
- **要件定義**: [requirements.md](../../spec/code-review-fixes-v2/requirements.md)

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 18件 | 100% |
| 🟡 黄信号 | 0件 | 0% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（全項目が青信号）

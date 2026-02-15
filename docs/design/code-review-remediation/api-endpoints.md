# code-review-remediation API エンドポイント仕様

**作成日**: 2026-02-15
**関連設計**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/code-review-remediation/requirements.md)
**既存 API 仕様**: [api-endpoints.md](../memoru-liff/api-endpoints.md)

**【信頼性レベル凡例】**:

- 🔵 **青信号**: コードレビュー結果・既存 API 仕様・ユーザヒアリングを参考にした確実な定義
- 🟡 **黄信号**: コードレビュー結果・既存 API 仕様・ユーザヒアリングから妥当な推測による定義
- 🔴 **赤信号**: コードレビュー結果・既存 API 仕様・ユーザヒアリングにない推測による定義

---

## 変更概要

本ドキュメントでは、コードレビュー修正に伴う API の **変更・追加** のみを記載します。既存 API の完全な仕様は `docs/design/memoru-liff/api-endpoints.md` を参照してください。

### 変更一覧

| 種別 | エンドポイント | 内容 | 対応項目 |
|------|---------------|------|---------|
| 修正 | GET /cards/due | SAM テンプレートのパスを統一 | C-01 |
| 修正 | DELETE /cards/:card_id | レスポンスの 204 処理を Frontend で対応 | C-05 |
| 追加 | POST /users/me/unlink-line | LINE 連携解除 | H-04 |

---

## 修正: GET /cards/due — パス統一 (C-01) 🔵

**信頼性**: 🔵 *C-01: 設計文書 api-endpoints.md の定義を正とする*

**関連要件**: REQ-CR-001, REQ-CR-002

### 現状の問題

```
handler.py:    @app.get("/cards/due")      ← 正
template.yaml: Path: /reviews/due           ← 誤
api.ts:        (要確認)                      ← 要統一
```

### 修正後

```
handler.py:    @app.get("/cards/due")      ← 変更なし
template.yaml: Path: /cards/due             ← 修正
api.ts:        GET /cards/due               ← 統一確認
```

### 仕様（変更なし）

既存の `GET /cards/due` の仕様はそのまま維持。詳細は[既存 API 仕様](../memoru-liff/api-endpoints.md#get-cardsdue-)を参照。

---

## 修正: DELETE /cards/:card_id — 204 レスポンス処理 (C-05) 🔵

**信頼性**: 🔵 *C-05: HTTP 仕様・既存実装から確認*

**関連要件**: REQ-CR-004, REQ-CR-101

### Backend レスポンス仕様

Backend の DELETE 応答は変更なし（204 No Content）:

```
HTTP/1.1 204 No Content
```

### Frontend 側の修正

```typescript
// api.ts の request() メソッド内
if (response.status === 204) {
  return undefined as T;
}
return response.json();
```

**注意**: Backend が 204 以外のレスポンス（例: `{"success": true, "data": {...}}`）を返す場合は、Backend 側を 204 に統一するか、Frontend を対応させる。

---

## 追加: POST /users/me/unlink-line (H-04) 🔵

**信頼性**: 🔵 *H-04: Frontend UI の連携解除ボタンと Backend の実装差から確認*

**関連要件**: REQ-CR-018

**説明**: LINE アカウントとの連携を解除する

### リクエスト

```http
POST /users/me/unlink-line
Authorization: Bearer {keycloak_jwt_token}
```

**リクエストボディ**: なし

### レスポンス（成功）

```json
{
  "success": true,
  "data": {
    "user_id": "keycloak-sub-uuid",
    "unlinked_at": "2026-02-15T10:00:00Z"
  }
}
```

### レスポンス（エラー）

#### 400: 未連携状態での解除試行 🟡

**信頼性**: 🟡 *エラーケースは推測*

```json
{
  "success": false,
  "error": {
    "code": "LINE_NOT_LINKED",
    "message": "LINE アカウントは連携されていません"
  }
}
```

### 処理フロー

1. JWT から `user_id` を取得
2. `users` テーブルから当該ユーザーを取得
3. `line_user_id` が設定されていることを確認
4. `line_user_id` を REMOVE（DynamoDB UpdateItem）
5. 成功レスポンスを返却

### SAM テンプレート定義

```yaml
UnlinkLineEvent:
  Type: Api
  Properties:
    Path: /users/me/unlink-line
    Method: post
    RestApiId: !Ref MemoruApi
```

### Backend 実装方針 🔵

```python
# handler.py
@app.post("/users/me/unlink-line")
def unlink_line():
    user_id = app.current_event.request_context.authorizer.claims["sub"]
    result = user_service.unlink_line(user_id)
    return {"success": True, "data": result}

# user_service.py
def unlink_line(self, user_id: str) -> dict:
    self.users_table.update_item(
        Key={'user_id': user_id},
        UpdateExpression='REMOVE line_user_id SET updated_at = :now',
        ConditionExpression='attribute_exists(line_user_id)',
        ExpressionAttributeValues={
            ':now': datetime.now(timezone.utc).isoformat()
        }
    )
    return {
        "user_id": user_id,
        "unlinked_at": datetime.now(timezone.utc).isoformat()
    }
```

---

## API レスポンス契約統一 (C-02) 🔵

**信頼性**: 🔵 *C-02: Backend モデルと Frontend 型定義の比較から確認*

**関連要件**: REQ-CR-003

### 統一方針

Backend の Pydantic レスポンスモデルを正として、Frontend の TypeScript 型を合わせる。

### 確認・修正対象

| Backend モデル | Frontend 型 | 確認項目 |
|---------------|------------|---------|
| `backend/src/models/card.py` | `frontend/src/types/card.ts` | フィールド名、型、Optional |
| `backend/src/models/user.py` | `frontend/src/types/user.ts` | フィールド名、型、Optional |

### 共通レスポンスフォーマット（変更なし）

```json
{
  "success": true,
  "data": { ... },
  "pagination": { ... }
}
```

---

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **要件定義**: [requirements.md](../../spec/code-review-remediation/requirements.md)
- **既存 API 仕様**: [api-endpoints.md](../memoru-liff/api-endpoints.md)

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 6件 | 86% |
| 🟡 黄信号 | 1件 | 14% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（青信号が86%、赤信号なし）

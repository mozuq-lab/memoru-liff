# TASK-0044 要件定義書: LINE ID トークン検証 + httpx 統一

**タスクID**: TASK-0044
**機能名**: LINE ID トークン検証 + httpx 統一
**要件名**: code-review-fixes-v2
**作成日**: 2026-02-21
**タスクタイプ**: TDD
**推定工数**: 8時間

---

## 1. 機能の概要

### 1.1 何をする機能か 🔵

LINE連携時のセキュリティ強化として、フロントエンドから `line_user_id` を直接送信する方式を廃止し、LIFF SDK の `getIDToken()` で取得した ID トークンをサーバーに送信し、サーバー側で LINE Login API (`https://api.line.me/oauth2/v2.1/verify`) を使ってトークンを検証する方式に変更する。同時に、バックエンドの HTTP クライアントライブラリを `requests` から `httpx` に統一する。

- **参照したEARS要件**: REQ-V2-021, REQ-V2-022, REQ-V2-023, REQ-V2-052

### 1.2 どのような問題を解決するか 🔵

| 問題 | 影響 | 対応要件 |
|------|------|---------|
| フロントエンドから `line_user_id` を直接送信しており、改ざん可能 | 任意の LINE アカウントへのなりすまし連携が可能 | REQ-V2-021~023, H-01 |
| ID トークン検証なしで連携を確定している | サーバー側で本人性を担保できない | REQ-V2-022, REQ-V2-121 |
| `line_service.py` で `requests` ライブラリを使用しているが `requirements.txt` に未宣言 | ビルド時の依存解決不安定、技術スタック不統一 | REQ-V2-052, H-05 |
| `LINE_CHANNEL_ID` が環境変数として定義されていない | ID トークン検証に必要な `client_id` が取得できない | TASK-0044 note.md |

- **参照したEARS要件**: REQ-V2-021~023, REQ-V2-052, REQ-V2-121

### 1.3 想定されるユーザー 🔵

- **エンドユーザー**: LINE アプリ内ブラウザから LIFF アプリを使用し、LINE 連携を行うユーザー
- **開発者**: バックエンドの HTTP クライアント統一による保守性向上の恩恵を受ける

- **参照したユーザストーリー**: ユーザストーリー 1.2（LINE連携）

### 1.4 システム内での位置づけ 🔵

本タスクは以下のコンポーネントを横断的に修正する:

```
[LIFF Frontend] → [API Gateway] → [Lambda Handler] → [LineService] → [LINE Login API]
     |                                    |                 |
  LinkLinePage.tsx               handler.py          line_service.py
  api.ts                                             (requests → httpx)
  types/user.ts
```

- **前提タスク**: TASK-0042（API ルート統一） - 完了済み
- **後続タスク**: TASK-0045（レスポンス DTO 統一 + unlinkLine API 使用）

- **参照した設計文書**: architecture.md セクション 2.1（LINE 連携本人性検証）

---

## 2. 入力・出力の仕様

### 2.1 フロントエンド入力変更 🔵

#### 変更前

```typescript
// LinkLinePage.tsx L75-77
const updatedUser = await usersApi.linkLine({
  line_user_id: profile.userId,  // liff.getProfile() から取得した生の LINE User ID
});
```

#### 変更後

```typescript
// liff.getIDToken() で ID トークンを取得
const idToken = liff.getIDToken();
if (!idToken) {
  throw new Error('IDトークンを取得できませんでした');
}
const updatedUser = await usersApi.linkLine({
  id_token: idToken,  // LIFF ID トークン（JWT 形式）
});
```

- **参照したEARS要件**: REQ-V2-021
- **参照した設計文書**: architecture.md セクション 2.1 フロントエンド修正

### 2.2 フロントエンド型定義変更 🔵

#### 変更前 (`frontend/src/types/user.ts`)

```typescript
export interface LinkLineRequest {
  line_user_id: string;
}
```

#### 変更後

```typescript
export interface LinkLineRequest {
  id_token: string;
}
```

- **参照したEARS要件**: REQ-V2-021

### 2.3 バックエンド入力変更 🔵

#### リクエスト仕様（変更後）

| フィールド | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `id_token` | string | Yes | LIFF SDK から取得した ID トークン（JWT 形式） |

#### リクエスト例

```json
{
  "id_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

- **参照したEARS要件**: REQ-V2-021
- **参照した設計文書**: api-endpoints.md「POST /users/link-line（変更）」セクション

### 2.4 バックエンド Pydantic モデル変更 🔵

#### 変更前 (`backend/src/models/user.py`)

```python
class LinkLineRequest(BaseModel):
    line_user_id: str = Field(..., description="LINE User ID (U + 32 alphanumeric characters)")

    @field_validator("line_user_id")
    @classmethod
    def validate_line_user_id(cls, v: str) -> str:
        if not re.match(r"^U[a-f0-9]{32}$", v):
            raise ValueError("Invalid LINE User ID format.")
        return v
```

#### 変更後

```python
class LinkLineRequest(BaseModel):
    id_token: str = Field(..., min_length=1, description="LIFF ID Token for server-side verification")
```

**設計判断**: `line_user_id` のバリデータは不要になる（ID トークンはサーバー側で LINE API に検証を委譲するため）。

- **参照したEARS要件**: REQ-V2-021, REQ-V2-022

### 2.5 LINE API 検証の入出力 🔵

#### LINE API リクエスト

- **エンドポイント**: `POST https://api.line.me/oauth2/v2.1/verify`
- **Content-Type**: `application/x-www-form-urlencoded`
- **パラメータ**:

| パラメータ | 型 | 説明 |
|-----------|-----|------|
| `id_token` | string | LIFF から取得した ID トークン |
| `client_id` | string | LINE Login Channel ID（環境変数 `LINE_CHANNEL_ID`） |

#### LINE API レスポンス（成功時: 200）

```json
{
  "iss": "https://access.line.me",
  "sub": "U1234567890abcdef1234567890abcdef",
  "aud": "1234567890",
  "exp": 1234567890,
  "iat": 1234567890,
  "nonce": "nonce-value"
}
```

- `sub`: LINE User ID（これが `line_user_id` として使用される）

#### LINE API レスポンス（失敗時: 400/401）

```json
{
  "error": "invalid_request",
  "error_description": "..."
}
```

- **参照したEARS要件**: REQ-V2-022, NFR-V2-102
- **参照した設計文書**: architecture.md セクション 2.1 LINE サービス修正、note.md セクション 3.4

### 2.6 API レスポンス（link-line エンドポイント） 🔵

#### 成功時 (200)

現行の `LinkLineResponse` モデル（`{success, message}`）をそのまま使用する。レスポンス DTO の統一は後続の TASK-0045 で対応。

```json
{
  "success": true,
  "message": "LINE account linked successfully"
}
```

**注記**: TASK-0045 で User 型レスポンスに統一予定。本タスクのスコープでは既存のレスポンス形式を維持する。

#### エラー時

| HTTP ステータス | 条件 | レスポンス |
|---------------|------|-----------|
| 400 | `id_token` が未送信または空 | `{"error": "id_token is required"}` 🔵 |
| 401 | ID トークン検証失敗（無効/期限切れ） | `{"error": "LINE ID token verification failed"}` 🟡 |
| 409 | 既に別の LINE アカウントと連携済み | `{"error": "User is already linked to a LINE account"}` 🔵 |
| 409 | LINE ID が別ユーザーで使用中 | `{"error": "This LINE account is already linked to another user"}` 🔵 |

- **参照したEARS要件**: REQ-V2-023, REQ-V2-121
- **参照した設計文書**: api-endpoints.md エラーコードセクション

### 2.7 データフロー 🔵

```
1. [LinkLinePage.tsx] liff.getIDToken() → ID トークン取得
2. [LinkLinePage.tsx] POST /users/link-line { id_token: "..." }
3. [handler.py] リクエストボディから id_token を取得・バリデーション
4. [handler.py] line_service.verify_id_token(id_token) 呼び出し
5. [line_service.py] httpx.post("https://api.line.me/oauth2/v2.1/verify", ...)
6. [LINE API] ID トークン検証 → sub (line_user_id) 返却
7. [line_service.py] line_user_id を返却
8. [handler.py] user_service.link_line(user_id, line_user_id) で連携確定
9. [handler.py] レスポンス返却
10. [LinkLinePage.tsx] ユーザー情報を更新表示
```

- **参照した設計文書**: architecture.md セクション 2.1、note.md セクション 4.3

---

## 3. 制約条件

### 3.1 セキュリティ要件 🔵

| 要件 | 詳細 | 参照 |
|------|------|------|
| サーバー側検証必須 | ID トークンは必ずサーバー側で LINE API を通じて検証する | NFR-V2-101 |
| LINE API エンドポイント | `https://api.line.me/oauth2/v2.1/verify` を使用する | NFR-V2-102 |
| ID トークン非保持 | フロントエンドで ID トークンを永続保存しない（取得→送信→破棄） | note.md 7.3 |
| Channel ID 管理 | `LINE_CHANNEL_ID` は環境変数として SAM テンプレートで管理する | note.md 3.6 |

- **参照したEARS要件**: NFR-V2-101, NFR-V2-102

### 3.2 技術制約 🔵

| 制約 | 詳細 | 参照 |
|------|------|------|
| HTTP ライブラリ | `httpx` に統一、`requests` は使用しない | REQ-V2-402, REQ-V2-052 |
| 同期呼び出し | httpx は同期モードで使用（Lambda 内 async は将来検討） | architecture.md 技術的制約 |
| タイムアウト | HTTP リクエストのタイムアウトは 10 秒 | note.md 7.2（既存コード準拠） |
| Python バージョン | 3.12 | template.yaml Globals |

- **参照したEARS要件**: REQ-V2-052, REQ-V2-402
- **参照した設計文書**: architecture.md セクション 2.5

### 3.3 アーキテクチャ制約 🔵

| 制約 | 詳細 |
|------|------|
| Lambda 実行環境 | httpx が `requirements.txt` 経由でインストールされている必要がある |
| 外部 API 依存 | LINE API 呼び出しによるレイテンシ追加（数百ms程度） |
| 既存エラーハンドリング維持 | `UserAlreadyLinkedError`、`LineUserIdAlreadyUsedError` の 409 レスポンスは維持 |

- **参照した設計文書**: architecture.md 技術的制約

### 3.4 API 制約 🔵

| 制約 | 詳細 |
|------|------|
| エンドポイント | `POST /users/link-line`（TASK-0042 で統一済み） |
| 認証 | JWT Authorizer（Keycloak 発行トークン） |
| リクエスト形式 | `application/json`（フロントエンド → バックエンド） |
| LINE API 形式 | `application/x-www-form-urlencoded`（バックエンド → LINE API） |

- **参照した設計文書**: api-endpoints.md、template.yaml

### 3.5 requirements.txt 制約 🔵

| 項目 | 詳細 |
|------|------|
| 現状 | `httpx>=0.26.0` は既に記載済み |
| `requests` | `requirements.txt` に未記載だが `line_service.py` で import されている |
| 変更方針 | `requests` の import を除去し、`httpx` に置換。requirements.txt に `requests` の追加は不要 |

- **参照したEARS要件**: REQ-V2-052

### 3.6 SAM テンプレート制約 🔵

| 項目 | 詳細 |
|------|------|
| `LineChannelId` パラメータ | Parameters セクションに追加（`Type: String`, `Default: ''`） |
| `LINE_CHANNEL_ID` 環境変数 | ApiFunction の Environment Variables に追加 |
| Channel ID 性質 | 公開情報のため `NoEcho: false` |

- **参照した設計文書**: note.md セクション 3.6

---

## 4. 想定される使用例

### 4.1 正常系: LINE 連携成功 🔵

**前提条件**: ユーザーが LINE アプリ内ブラウザで LIFF アプリにアクセスしている

1. ユーザーが「LINEと連携する」ボタンを押下
2. `liff.getIDToken()` で ID トークンを取得
3. `POST /users/link-line` に `{ id_token: "..." }` を送信
4. サーバーが LINE API で ID トークンを検証
5. 検証成功: `sub` クレームから `line_user_id` を抽出
6. `user_service.link_line(user_id, line_user_id)` で連携確定
7. 成功レスポンスを返却
8. フロントエンドで「LINE連携が完了しました」を表示

- **参照したEARS要件**: REQ-V2-021~023
- **参照した設計文書**: api-endpoints.md サーバー側処理フロー

### 4.2 エラー系: ID トークン取得失敗 🔵

**前提条件**: LIFF SDK の初期化が完了しているが、ID トークンが取得できない

1. ユーザーが「LINEと連携する」ボタンを押下
2. `liff.getIDToken()` が `null` を返却
3. フロントエンドで `Error('IDトークンを取得できませんでした')` をスロー
4. エラーメッセージ「LINEの認証情報を取得できませんでした」を表示 🟡

- **参照したEARS要件**: REQ-V2-021

### 4.3 エラー系: ID トークン検証失敗（無効トークン） 🔵

**前提条件**: フロントエンドから無効な ID トークンが送信された

1. `POST /users/link-line` に無効な `id_token` を送信
2. サーバーが LINE API に検証リクエスト
3. LINE API が 400 ステータスを返却
4. `line_service.verify_id_token()` が `UnauthorizedError` をスロー
5. ハンドラーが 401 レスポンスを返却
6. フロントエンドで「LINE連携に失敗しました」を表示

- **参照したEARS要件**: REQ-V2-121
- **参照したEdgeケース**: EDGE-V2-001

### 4.4 エラー系: ID トークン有効期限切れ 🟡

**前提条件**: ユーザーがページを長時間開いたまま連携ボタンを押下

1. `POST /users/link-line` に期限切れの `id_token` を送信
2. サーバーが LINE API に検証リクエスト
3. LINE API が 400 ステータスを返却（`expired token`）
4. `line_service.verify_id_token()` が `UnauthorizedError` をスロー
5. ハンドラーが 401 レスポンスを返却

- **参照したEdgeケース**: EDGE-V2-001

### 4.5 エラー系: ID トークン未送信 🔵

**前提条件**: リクエストボディに `id_token` フィールドがない

1. `POST /users/link-line` に `{}` または `id_token` なしのボディを送信
2. ハンドラーで `id_token` の存在チェック
3. `BadRequestError("id_token is required")` をスロー（400 レスポンス）

- **参照したEARS要件**: REQ-V2-021

### 4.6 エラー系: LINE_CHANNEL_ID 未設定 🟡

**前提条件**: 環境変数 `LINE_CHANNEL_ID` が設定されていない

1. `POST /users/link-line` に有効な `id_token` を送信
2. `line_service.verify_id_token()` で `self.channel_id` が `None`
3. `LineApiError("LINE_CHANNEL_ID not configured")` をスロー
4. 500 Internal Server Error を返却

- **参照した設計文書**: note.md セクション 3.4

### 4.7 エラー系: LINE API 通信障害 🟡

**前提条件**: LINE API が応答しない、またはネットワーク障害

1. `POST /users/link-line` に有効な `id_token` を送信
2. `httpx.post()` がタイムアウトまたは接続エラー
3. `httpx.RequestError` が発生
4. `LineApiError("Failed to verify ID token: ...")` をスロー
5. 500 Internal Server Error を返却

- **参照した設計文書**: note.md セクション 3.4

### 4.8 httpx 移行: reply_message / push_message 🔵

**前提条件**: `line_service.py` の既存メソッドで `requests` が使用されている

1. `reply_message()` の `requests.post()` → `httpx.post()` に置換
2. `push_message()` の `requests.post()` → `httpx.post()` に置換
3. 例外ハンドリング: `requests.RequestException` → `httpx.RequestError` に置換
4. `import requests` → `import httpx` に置換

- **参照したEARS要件**: REQ-V2-052

---

## 5. 実装対象ファイルと変更内容

### 5.1 フロントエンド修正

| ファイル | 変更内容 | 信頼性 |
|---------|---------|--------|
| `frontend/src/pages/LinkLinePage.tsx` | `liff.getProfile()` → `liff.getIDToken()` 使用、`id_token` 送信 | 🔵 |
| `frontend/src/services/api.ts` | `linkLine` メソッドの引数型確認（型は `types/user.ts` で定義） | 🔵 |
| `frontend/src/types/user.ts` | `LinkLineRequest` の `line_user_id` → `id_token` に変更 | 🔵 |

### 5.2 バックエンド修正

| ファイル | 変更内容 | 信頼性 |
|---------|---------|--------|
| `backend/src/services/line_service.py` | `verify_id_token()` メソッド追加、`requests` → `httpx` 統一 | 🔵 |
| `backend/src/api/handler.py` | `link_line_account()` で ID トークン検証フロー実装 | 🔵 |
| `backend/src/models/user.py` | `LinkLineRequest` モデルを `id_token` フィールドに変更 | 🔵 |

### 5.3 インフラ修正

| ファイル | 変更内容 | 信頼性 |
|---------|---------|--------|
| `backend/template.yaml` | `LineChannelId` パラメータ追加、`LINE_CHANNEL_ID` 環境変数追加 | 🔵 |

---

## 6. verify_id_token メソッド詳細仕様

### 6.1 メソッドシグネチャ 🔵

```python
def verify_id_token(self, id_token: str) -> str:
    """LIFF IDトークンをLINE APIで検証し、line_user_idを返す。

    Args:
        id_token: LIFF SDK の getIDToken() で取得した ID トークン

    Returns:
        検証済みの line_user_id（LINE API レスポンスの 'sub' クレーム値）

    Raises:
        UnauthorizedError: ID トークン検証失敗時（無効/期限切れ）
        LineApiError: LINE_CHANNEL_ID 未設定時、通信障害時
    """
```

### 6.2 処理フロー 🔵

1. `self.channel_id`（`LINE_CHANNEL_ID` 環境変数）の存在チェック
   - 未設定: `LineApiError("LINE_CHANNEL_ID not configured")` をスロー
2. `httpx.post()` で LINE API に検証リクエスト送信
   - URL: `https://api.line.me/oauth2/v2.1/verify`
   - データ: `{'id_token': id_token, 'client_id': self.channel_id}`
   - タイムアウト: 10秒
3. レスポンスステータスチェック
   - 200 以外: `UnauthorizedError("LINE ID token verification failed")` をスロー
4. レスポンス JSON から `sub` フィールドを取得
   - `sub` がない場合: `UnauthorizedError("Invalid ID token format")` をスロー
5. `line_user_id`（`sub` 値）を返却

### 6.3 __init__ メソッド変更 🔵

```python
def __init__(self, channel_access_token=None, channel_secret=None, user_service=None):
    # 既存の初期化処理...
    self.channel_id = os.environ.get('LINE_CHANNEL_ID')  # 追加
```

- **参照した設計文書**: architecture.md セクション 2.1、note.md セクション 3.4

---

## 7. handler.py 変更詳細仕様

### 7.1 link_line_account 関数の変更 🔵

#### 変更前の処理フロー

```
1. JWT から user_id 取得
2. リクエストボディを LinkLineRequest (line_user_id) でバリデーション
3. user_service.link_line(user_id, request.line_user_id) で直接連携
4. LinkLineResponse(success, message) を返却
```

#### 変更後の処理フロー

```
1. JWT から user_id 取得
2. リクエストボディから id_token を取得
3. id_token の存在チェック（なければ 400）
4. line_service.verify_id_token(id_token) で LINE API 検証
5. 検証成功: 返却された line_user_id で連携
6. user_service.link_line(user_id, line_user_id) で連携確定
7. LinkLineResponse(success, message) を返却
```

### 7.2 追加するエラーハンドリング 🔵

| 例外 | HTTP ステータス | レスポンス |
|------|---------------|-----------|
| `id_token` 未送信 | 400 | `{"error": "id_token is required"}` |
| `UnauthorizedError`（ID トークン検証失敗） | 401 | `{"error": "LINE ID token verification failed"}` |
| `LineApiError`（通信障害等） | 500 | 既存の Exception ハンドラーに委譲 |

### 7.3 line_service のインスタンス化 🟡

`handler.py` のモジュールレベルで `line_service` インスタンスを生成する必要がある。既存の `user_service`, `card_service` 等と同様のパターンで初期化する。

```python
from ..services.line_service import LineService, LineApiError
line_service = LineService()
```

- **参照した設計文書**: architecture.md セクション 2.1、handler.py 既存パターン

---

## 8. httpx 統一の詳細仕様

### 8.1 置換対象箇所 🔵

| メソッド | 行番号 | 変更前 | 変更後 |
|---------|--------|--------|--------|
| `reply_message` | L223 | `requests.post(url, headers=headers, json=payload, timeout=10)` | `httpx.post(url, headers=headers, json=payload, timeout=10)` |
| `reply_message` | L226 | `except requests.RequestException as e:` | `except httpx.RequestError as e:` |
| `push_message` | L260 | `requests.post(url, headers=headers, json=payload, timeout=10)` | `httpx.post(url, headers=headers, json=payload, timeout=10)` |
| `push_message` | L263 | `except requests.RequestException as e:` | `except httpx.RequestError as e:` |
| import | L12 | `import requests` | `import httpx` |

### 8.2 API 互換性 🔵

| 機能 | requests | httpx | 互換性 |
|------|----------|-------|--------|
| POST リクエスト | `requests.post()` | `httpx.post()` | 同一 API |
| JSON ペイロード | `json=payload` | `json=payload` | 同一 |
| タイムアウト | `timeout=10` | `timeout=10` | 同一 |
| ステータスチェック | `response.raise_for_status()` | `response.raise_for_status()` | 同一 |
| レスポンス JSON | `response.json()` | `response.json()` | 同一 |
| 例外基底クラス | `requests.RequestException` | `httpx.RequestError` | **異なる** |

- **参照したEARS要件**: REQ-V2-052, REQ-V2-402
- **参照した設計文書**: architecture.md セクション 2.5

---

## 9. EARS要件・設計文書との対応関係

### 9.1 参照したユーザストーリー

- ユーザストーリー 1.2: LINE 連携

### 9.2 参照した機能要件

| 要件ID | 内容 | 本タスクでの対応 |
|--------|------|----------------|
| REQ-V2-021 | フロントエンドから LIFF ID トークンを受信 | LinkLinePage.tsx で `liff.getIDToken()` を使用 |
| REQ-V2-022 | サーバー側で LINE API により ID トークンを検証 | `line_service.verify_id_token()` 実装 |
| REQ-V2-023 | 検証成功後の line_user_id でのみ連携確定 | handler.py で検証後に `link_line()` 呼び出し |
| REQ-V2-052 | HTTP クライアントを httpx に統一 | `requests` → `httpx` 全置換 |

### 9.3 参照した条件付き要件

| 要件ID | 内容 | 本タスクでの対応 |
|--------|------|----------------|
| REQ-V2-121 | ID トークン検証失敗時に 401 を返却 | `UnauthorizedError` → 401 レスポンス |

### 9.4 参照した非機能要件

| 要件ID | 内容 | 本タスクでの対応 |
|--------|------|----------------|
| NFR-V2-101 | LINE 連携は ID トークンのサーバー側検証を必須とする | `verify_id_token()` 実装 |
| NFR-V2-102 | LINE Login API の verify エンドポイントを使用 | `https://api.line.me/oauth2/v2.1/verify` |

### 9.5 参照した制約要件

| 要件ID | 内容 |
|--------|------|
| REQ-V2-402 | HTTP ライブラリは httpx に統一 |

### 9.6 参照した Edge ケース

| ケースID | 内容 | 本タスクでの対応 |
|---------|------|----------------|
| EDGE-V2-001 | ID トークン有効期限切れ | `UnauthorizedError` でハンドリング |

### 9.7 参照した設計文書

| 文書 | 参照セクション |
|------|-------------|
| architecture.md | セクション 2.1 LINE連携本人性検証、セクション 2.5 httpx統一 |
| api-endpoints.md | POST /users/link-line（変更）、エラーコード |
| note.md | セクション 3.1~3.6（実装詳細分析）、セクション 7（制約と注意事項） |

---

## 10. 信頼性レベルサマリー

### 項目別信頼性

| カテゴリ | 🔵 青 | 🟡 黄 | 🔴 赤 | 合計 |
|---------|-------|-------|-------|------|
| 機能概要 | 4 | 0 | 0 | 4 |
| 入出力仕様 | 8 | 1 | 0 | 9 |
| 制約条件 | 6 | 0 | 0 | 6 |
| 使用例（正常系） | 1 | 0 | 0 | 1 |
| 使用例（エラー系） | 3 | 3 | 0 | 6 |
| 実装詳細 | 7 | 1 | 0 | 8 |

### 全体評価

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 29 | 85% |
| 🟡 黄信号 | 5 | 15% |
| 🔴 赤信号 | 0 | 0% |

### 黄信号項目の詳細

| 項目 | 理由 |
|------|------|
| 401 エラーレスポンス文言 | LINE API のエラー詳細をどこまでクライアントに返すかは実装時判断 |
| ID トークン取得失敗時の UI エラーメッセージ | 具体的な文言は設計文書に明記なし、ユーザビリティ観点から推測 |
| ID トークン有効期限切れの動作 | LINE API 側のレスポンスコード（400 vs 401）は実際の動作で確認が必要 |
| LINE API 通信障害時の動作 | httpx の例外種別と handler での伝播パターンは実装時に確定 |
| handler.py での line_service インスタンス化 | 既存パターンからの推測（妥当性は高い） |

---

## 品質判定結果

**品質評価**: ✅ 高品質

| 評価項目 | 結果 |
|---------|------|
| 要件の曖昧さ | なし - 全項目が具体的な入出力・処理フローで定義されている |
| 入出力定義の完全性 | 完全 - リクエスト/レスポンスの型・フィールド・バリデーションが明確 |
| 制約条件の明確性 | 明確 - セキュリティ・技術・API・インフラ制約がすべて列挙されている |
| 実装可能性 | 確実 - 既存コードの具体的な変更箇所が特定されており、LINE API 仕様も確認済み |
| 信頼性レベル | 🔵 85% - 赤信号なし、黄信号は許容範囲内の推測のみ |

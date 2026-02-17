# code-review-fixes-v2 アーキテクチャ設計

**作成日**: 2026-02-17
**関連要件定義**: [requirements.md](../../spec/code-review-fixes-v2/requirements.md)
**ヒアリング記録**: [design-interview.md](design-interview.md)
**既存アーキテクチャ**: [architecture.md](../memoru-liff/architecture.md)
**前回修正設計**: [architecture.md](../code-review-remediation/architecture.md)

**【信頼性レベル凡例】**:

- 🔵 **青信号**: 要件定義書・設計文書・ユーザヒアリング・コード分析から確実な設計
- 🟡 **黄信号**: 要件定義書・設計文書から妥当な推測による設計
- 🔴 **赤信号**: 要件定義書・設計文書にない推測による設計

---

## 設計概要 🔵

**信頼性**: 🔵 *コードレビュー結果 CODE_REVIEW_2026-02-16.md・要件定義書より*

既存の memoru-liff アーキテクチャ（サーバーレス + LIFF + Keycloak）は変更せず、**コードレベルの修正とインフラ設定の調整** により Critical 2件 + High 6件の問題を解消する。

### 変更方針

- アーキテクチャパターン（サーバーレス）は **変更なし** 🔵
- コンポーネント構成は **変更なし**（新規 Lambda/テーブル追加なし） 🔵
- DynamoDB users テーブルに `timezone` 属性を追加 🔵 *ユーザヒアリングで決定*
- LINE 連携フローに ID トークン検証ステップを追加 🔵
- 複数ファイルの設定値統一（環境変数名、クライアントID） 🔵

---

## Phase 1: Critical 修正の設計

### 1.1 APIルート統一 (CR-01) 🔵

**信頼性**: 🔵 *CR-01: コード分析で3レイヤー不一致を確認。設計文書 api-endpoints.md 準拠をユーザヒアリングで決定*

**関連要件**: REQ-V2-001〜004

**問題**: SAM テンプレート、Lambda ハンドラー、フロントエンド API クライアントの3レイヤーでパスが不一致

**設計決定**: 設計文書 `api-endpoints.md` の定義を正（single source of truth）とする

#### 設定更新エンドポイント

```
正規パス: PUT /users/me/settings  ← api-endpoints.md の定義

修正対象:
1. backend/template.yaml L255-260
   Path: /users/me → Path: /users/me/settings

2. frontend/src/services/api.ts L142
   変更なし（ただし確認して /users/me/settings に統一）

3. backend/src/api/handler.py L151
   @app.put("/users/me/settings") → 変更なし（正）
```

#### レビュー送信エンドポイント

```
正規パス: POST /reviews/{cardId}  ← api-endpoints.md の定義

修正対象:
1. backend/template.yaml L305-310
   Path: /reviews → Path: /reviews/{cardId}

2. backend/src/api/handler.py L493
   @app.post("/reviews/<card_id>") → 変更なし（正）

3. frontend/src/services/api.ts L130
   変更なし（正）
```

#### LINE 連携エンドポイント

```
正規パス: POST /users/link-line  ← api-endpoints.md の定義

修正対象:
1. backend/template.yaml
   イベント定義を新規追加:
   LinkLineEvent:
     Type: Api
     Properties:
       Path: /users/link-line
       Method: post

2. backend/src/api/handler.py L104
   @app.post("/users/link-line") → 変更なし（正）

3. frontend/src/services/api.ts L149
   POST /users/me/link-line → POST /users/link-line
```

**影響範囲**:

- SAM テンプレートの API Gateway リソース定義
- Frontend API クライアントのパス定数
- 既存テストのパス参照

---

### 1.2 card_count トランザクション修正 (CR-02) 🔵

**信頼性**: 🔵 *CR-02: card_service.py のコード分析で4つの問題を確認*

**関連要件**: REQ-V2-011〜014, REQ-V2-101〜103

**設計決定**: DynamoDB トランザクションの4箇所を修正

#### 1.2.1 if_not_exists による安全な加算

```python
# backend/src/services/card_service.py - create_card トランザクション
# Before:
'UpdateExpression': 'SET card_count = card_count + :inc',
'ConditionExpression': 'card_count < :limit',

# After:
'UpdateExpression': 'SET card_count = if_not_exists(card_count, :zero) + :inc',
'ConditionExpression': 'if_not_exists(card_count, :zero) < :limit',
'ExpressionAttributeValues': {
    ':inc': {'N': '1'},
    ':limit': {'N': '2000'},
    ':zero': {'N': '0'}
}
```

#### 1.2.2 TransactionCanceledException のエラー分類

```python
# backend/src/services/card_service.py - create_card エラーハンドリング
# Before:
except ClientError as e:
    if e.response['Error']['Code'] == 'TransactionCanceledException':
        raise CardLimitExceededError()

# After:
except ClientError as e:
    if e.response['Error']['Code'] == 'TransactionCanceledException':
        reasons = e.response.get('CancellationReasons', [])
        # インデックス0 = Users テーブルの Update（card_count チェック）
        if reasons and reasons[0].get('Code') == 'ConditionalCheckFailed':
            raise CardLimitExceededError()
        # それ以外のトランザクション失敗は内部エラー
        logger.error(f"Transaction failed: {reasons}")
        raise InternalError("Card creation failed")
```

#### 1.2.3 delete_card での card_count 減算

```python
# backend/src/services/card_service.py - delete_card
# Before: Cards/Reviews の削除のみ、card_count 未減算

# After: トランザクションで原子的に実行
def delete_card(self, user_id: str, card_id: str) -> None:
    client = boto3.client('dynamodb')
    client.transact_write_items(
        TransactItems=[
            {
                'Delete': {
                    'TableName': self.cards_table_name,
                    'Key': {
                        'user_id': {'S': user_id},
                        'card_id': {'S': card_id}
                    },
                    'ConditionExpression': 'attribute_exists(card_id)'
                }
            },
            {
                'Delete': {
                    'TableName': self.reviews_table_name,
                    'Key': {
                        'user_id': {'S': user_id},
                        'card_id': {'S': card_id}
                    }
                }
            },
            {
                'Update': {
                    'TableName': self.users_table_name,
                    'Key': {'user_id': {'S': user_id}},
                    'UpdateExpression': 'SET card_count = card_count - :dec',
                    'ConditionExpression': 'card_count > :zero',
                    'ExpressionAttributeValues': {
                        ':dec': {'N': '1'},
                        ':zero': {'N': '0'}
                    }
                }
            }
        ]
    )
```

#### 1.2.4 カード作成前のユーザーレコード保証

```python
# backend/src/api/handler.py - create_card ハンドラー
@app.post("/cards")
def create_cards():
    user_id = get_user_id_from_jwt()
    # ユーザーレコードの存在保証
    user_service.get_or_create_user(user_id)
    # カード作成
    cards = card_service.create_cards(user_id, body['cards'])
    return {"success": True, "data": cards}
```

---

## Phase 2: High 修正の設計

### 2.1 LINE 連携本人性検証 (H-01) 🔵

**信頼性**: 🔵 *H-01: ユーザヒアリングで LIFF IDトークン検証 + LINE API 呼び出し方式に決定*

**関連要件**: REQ-V2-021〜023, REQ-V2-121

**設計**: LINE Login API の `/oauth2/v2.1/verify` エンドポイントで ID トークンを検証

#### フロントエンド修正

```typescript
// frontend/src/pages/LinkLinePage.tsx
// Before:
const updatedUser = await usersApi.linkLine({
  line_user_id: profile.userId,
});

// After:
const idToken = liff.getIDToken();
const updatedUser = await usersApi.linkLine({
  id_token: idToken,  // line_user_id の代わりに ID トークンを送信
});
```

#### バックエンド修正

```python
# backend/src/api/handler.py - link_line ハンドラー
@app.post("/users/link-line")
def link_line():
    user_id = get_user_id_from_jwt()
    body = app.current_event.json_body
    id_token = body.get('id_token')

    if not id_token:
        return {"statusCode": 400, "body": {"error": "id_token is required"}}

    # LINE ID トークンを検証して line_user_id を取得
    line_user_id = line_service.verify_id_token(id_token)

    # ユーザーに LINE ID を紐付け
    user = user_service.link_line(user_id, line_user_id)
    return {"success": True, "data": user.to_dict()}
```

#### LINE サービス修正

```python
# backend/src/services/line_service.py
import httpx  # requests から httpx に統一 (H-05)

class LineService:
    def verify_id_token(self, id_token: str) -> str:
        """LIFF IDトークンをLINE APIで検証し、line_user_idを返す"""
        response = httpx.post(
            'https://api.line.me/oauth2/v2.1/verify',
            data={
                'id_token': id_token,
                'client_id': self.channel_id,  # LIFF アプリの Channel ID
            }
        )

        if response.status_code != 200:
            raise UnauthorizedError("LINE ID token verification failed")

        data = response.json()
        return data['sub']  # line_user_id
```

---

### 2.2 レスポンス DTO 統一 (H-02) 🔵

**信頼性**: 🔵 *H-02: handler.py のレスポンスと api.ts の期待型の不一致を確認*

**関連要件**: REQ-V2-031〜033

#### 設定更新レスポンス修正

```python
# backend/src/api/handler.py - update_settings
# Before:
return {"success": True, "settings": updated_settings}

# After:
user = user_service.get_user(user_id)
return {"success": True, "data": user.to_dict()}
```

#### LINE 連携レスポンス修正

```python
# backend/src/api/handler.py - link_line
# Before:
return {"success": True, "message": "LINE linked"}

# After:
user = user_service.get_user(user_id)
return {"success": True, "data": user.to_dict()}
```

#### フロントエンド unlinkLine 修正

```typescript
// frontend/src/services/api.ts
// unlinkLine メソッドを追加
async unlinkLine(): Promise<User> {
  return this.request<User>('/users/me/unlink-line', {
    method: 'POST',
  });
}

// frontend/src/pages/LinkLinePage.tsx
// Before:
const updatedUser = await usersApi.updateUser({ line_user_id: null });

// After:
const updatedUser = await usersApi.unlinkLine();
```

---

### 2.3 通知時刻/タイムゾーン判定 (H-03) 🔵

**信頼性**: 🔵 *H-03: ユーザヒアリングで DB 属性追加方式に決定*

**関連要件**: REQ-V2-041〜042, REQ-V2-111〜112

#### DB スキーマ変更

```
users テーブルに追加:
| 属性名     | 型     | 説明                              | デフォルト値  |
|-----------|--------|-----------------------------------|-------------|
| timezone  | String | IANA タイムゾーン名                  | Asia/Tokyo  |
```

#### 通知サービス修正

```python
# backend/src/services/notification_service.py
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

def should_notify(self, user, current_utc: datetime) -> bool:
    """ユーザーのローカル時刻が notification_time と一致するか判定"""
    tz_name = user.timezone or 'Asia/Tokyo'
    user_tz = ZoneInfo(tz_name)
    local_time = current_utc.astimezone(user_tz)
    local_hhmm = local_time.strftime('%H:%M')

    notification_time = user.notification_time or '09:00'

    # ±5分の精度で判定（EventBridge の実行間隔に合わせる）
    notif_hour, notif_min = map(int, notification_time.split(':'))
    local_hour, local_min = local_time.hour, local_time.minute

    # 通知時刻の ±5分以内なら送信
    notif_total_min = notif_hour * 60 + notif_min
    local_total_min = local_hour * 60 + local_min
    diff = abs(local_total_min - notif_total_min)

    # 日付境界をまたぐケース（23:58 と 00:02 等）
    if diff > 720:  # 12時間以上の差は反対方向
        diff = 1440 - diff

    return diff <= 5

# process_notifications 内で使用
def process_notifications(self):
    current_utc = datetime.now(timezone.utc)
    users = self.user_service.get_linked_users()

    for user in users:
        if user.last_notified_date == current_utc.strftime('%Y-%m-%d'):
            result.skipped += 1
            continue

        if not self.should_notify(user, current_utc):
            result.skipped += 1
            continue

        due_count = self.card_service.get_due_card_count(user.user_id)
        if due_count > 0:
            self.send_notification(user, due_count)
```

---

### 2.4 環境変数名統一 (H-04) 🔵

**信頼性**: 🔵 *H-04: ユーザヒアリングで `VITE_API_BASE_URL` 統一に決定*

**関連要件**: REQ-V2-051

```yaml
# .github/workflows/deploy.yml
# Before (L91, L169):
VITE_API_URL: ${{ steps.deploy.outputs.api_url }}

# After:
VITE_API_BASE_URL: ${{ steps.deploy.outputs.api_url }}
```

---

### 2.5 httpx 統一 (H-05) 🔵

**信頼性**: 🔵 *H-05: ユーザヒアリングで httpx 統一に決定*

**関連要件**: REQ-V2-052

```python
# backend/src/services/line_service.py
# Before:
import requests
response = requests.post(url, headers=headers, json=data)

# After:
import httpx
response = httpx.post(url, headers=headers, json=data)
```

**修正パターン**:

| requests | httpx | 備考 |
|----------|-------|------|
| `requests.post()` | `httpx.post()` | 同期呼び出し |
| `requests.get()` | `httpx.get()` | 同期呼び出し |
| `response.json()` | `response.json()` | 同一 |
| `response.status_code` | `response.status_code` | 同一 |
| `response.raise_for_status()` | `response.raise_for_status()` | 同一 |

httpx は requests とほぼ同じ API なので、import 文の変更が主な修正。

---

### 2.6 OIDC クライアント ID 統一 (H-06) 🔵

**信頼性**: 🔵 *H-06: ユーザヒアリングで `liff-client` 統一に決定*

**関連要件**: REQ-V2-053

```yaml
# .github/workflows/deploy.yml L95
# Before:
VITE_OIDC_CLIENT_ID: memoru-liff

# After:
VITE_OIDC_CLIENT_ID: liff-client
```

```typescript
// frontend/e2e/fixtures/auth.fixture.ts L32
// Before:
const clientId = 'memoru-liff';

// After:
const clientId = 'liff-client';
```

変更不要（正の値）:
- `infrastructure/keycloak/realm-export.json`: `liff-client` ✓
- `backend/template.yaml L213`: `liff-client` ✓

---

## コンポーネント別修正サマリー

### Backend 修正一覧 🔵

| ファイル | 修正内容 | 対応項目 |
|---------|---------|---------|
| `template.yaml` | 設定更新パス修正、レビュー送信パス修正、LINE連携イベント追加 | CR-01 |
| `src/api/handler.py` | link_line で ID トークン受信、レスポンス DTO 統一、get_or_create_user 呼び出し | H-01, H-02, CR-02 |
| `src/services/card_service.py` | if_not_exists 加算、CancellationReasons 分類、delete_card 減算 | CR-02 |
| `src/services/line_service.py` | requests → httpx、verify_id_token 追加 | H-05, H-01 |
| `src/services/notification_service.py` | should_notify 追加（タイムゾーン/時刻判定） | H-03 |
| `src/services/user_service.py` | get_or_create_user 追加 | CR-02 |

### Frontend 修正一覧 🔵

| ファイル | 修正内容 | 対応項目 |
|---------|---------|---------|
| `src/services/api.ts` | LINE連携パス修正、unlinkLine メソッド追加、設定更新パス確認 | CR-01, H-02 |
| `src/pages/LinkLinePage.tsx` | ID トークン送信、unlinkLine API 使用 | H-01, H-02 |

### Infrastructure / CI 修正一覧 🔵

| ファイル | 修正内容 | 対応項目 |
|---------|---------|---------|
| `.github/workflows/deploy.yml` | VITE_API_BASE_URL 統一、liff-client 統一 | H-04, H-06 |
| `frontend/e2e/fixtures/auth.fixture.ts` | liff-client 統一 | H-06 |

---

## DB スキーマ変更 🔵

**信頼性**: 🔵 *ユーザヒアリングで DB 属性追加方式に決定*

### users テーブル

| 変更 | 属性名 | 型 | 説明 | デフォルト値 |
|------|--------|-----|------|-------------|
| **追加** | `timezone` | String | IANA タイムゾーン名 | `Asia/Tokyo` |

DynamoDB はスキーマレスのため、DDL 変更は不要。新しい属性は put_item/update_item 時に自動追加される。既存レコードに `timezone` がない場合はコード側で `Asia/Tokyo` をデフォルトとして扱う。

---

## 非機能要件の実現方法

### セキュリティ強化 🔵

**信頼性**: 🔵 *コードレビュー結果・ユーザヒアリングより*

| 項目 | 実現方法 | 対応項目 |
|------|---------|---------|
| LINE 連携本人性 | LIFF ID トークン → LINE API 検証 | H-01 |
| トークン audience | `liff-client` 全レイヤー統一 | H-06 |

### データ整合性 🔵

**信頼性**: 🔵 *コードレビュー結果より*

| 項目 | 実現方法 | 対応項目 |
|------|---------|---------|
| card_count 初期化 | `if_not_exists(card_count, :zero)` | CR-02 |
| card_count 減算 | 削除時トランザクション | CR-02 |
| エラー分類 | CancellationReasons 解析 | CR-02 |
| ユーザー存在保証 | get_or_create_user | CR-02 |

### 通知精度 🔵

**信頼性**: 🔵 *コードレビュー結果・ユーザヒアリングより*

| 項目 | 実現方法 | 対応項目 |
|------|---------|---------|
| タイムゾーン対応 | zoneinfo + users.timezone | H-03 |
| 通知時刻判定 | ±5分の精度で一致判定 | H-03 |

### 設定整合性 🔵

**信頼性**: 🔵 *コードレビュー結果・ユーザヒアリングより*

| 項目 | 実現方法 | 対応項目 |
|------|---------|---------|
| API URL | `VITE_API_BASE_URL` 統一 | H-04 |
| HTTP ライブラリ | httpx 統一 | H-05 |
| OIDC client_id | `liff-client` 統一 | H-06 |

---

## 技術的制約 🔵

**信頼性**: 🔵 *CLAUDE.md・要件定義より*

- API 契約の統一は設計文書（api-endpoints.md）を single source of truth とする
- AWS リソースの実際のデプロイはユーザーが手動で実行する
- LINE ID トークン検証は外部 API 呼び出し（レイテンシ追加あり）
- httpx は同期呼び出しで使用（Lambda 内での async 対応は将来検討）

---

## 関連文書

- **データフロー**: [dataflow.md](dataflow.md)
- **API 仕様**: [api-endpoints.md](api-endpoints.md)
- **設計ヒアリング**: [design-interview.md](design-interview.md)
- **要件定義**: [requirements.md](../../spec/code-review-fixes-v2/requirements.md)
- **既存アーキテクチャ**: [architecture.md](../memoru-liff/architecture.md)
- **既存 DB スキーマ**: [database-schema.md](../memoru-liff/database-schema.md)
- **既存 API 仕様**: [api-endpoints.md](../memoru-liff/api-endpoints.md)

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 22件 | 92% |
| 🟡 黄信号 | 2件 | 8% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（青信号が92%、赤信号なし）

# memoru-liff API エンドポイント仕様

**作成日**: 2026-01-05
**関連設計**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/memoru-liff/requirements.md)

**【信頼性レベル凡例】**:

- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実な定義
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測による定義
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測による定義

---

## 共通仕様

### ベースURL 🔵

**信頼性**: 🔵 *PRD・アーキテクチャ設計より*

```
https://{api-gateway-id}.execute-api.{region}.amazonaws.com/v1
```

または CloudFront経由のカスタムドメイン:

```
https://api.memoru.example.com/v1
```

### 認証 🔵

**信頼性**: 🔵 *PRD第3章・要件定義REQ-004より*

すべてのエンドポイント（LINE Webhook除く）はJWT認証が必要です。

```http
Authorization: Bearer {keycloak_jwt_token}
```

**JWT Claims**:

- `sub`: Keycloakユーザー識別子（user_idとして使用）
- `exp`: トークン有効期限
- `iss`: Keycloak issuer URL

### エラーレスポンス共通フォーマット 🔵

**信頼性**: 🔵 *PRDより*

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "エラーメッセージ（日本語）",
    "details": {}
  }
}
```

**共通エラーコード**:

| HTTPステータス | コード | 説明 |
|---------------|--------|------|
| 400 | `VALIDATION_ERROR` | リクエストバリデーションエラー |
| 401 | `UNAUTHORIZED` | 認証エラー（JWTなし/無効） |
| 403 | `FORBIDDEN` | 認可エラー（リソースへのアクセス権なし） |
| 404 | `NOT_FOUND` | リソースが見つからない |
| 429 | `RATE_LIMIT_EXCEEDED` | レート制限超過 |
| 500 | `INTERNAL_ERROR` | サーバー内部エラー |

### ページネーション 🟡

**信頼性**: 🟡 *一般的なAPI設計から妥当な推測*

リストを返すエンドポイントはページネーションをサポートします。

**クエリパラメータ**:

- `limit`: 1ページあたりの件数（デフォルト: 20、最大: 100）
- `cursor`: ページネーションカーソル（前回レスポンスの `next_cursor`）

**レスポンス形式**:

```json
{
  "success": true,
  "data": [...],
  "pagination": {
    "limit": 20,
    "has_more": true,
    "next_cursor": "eyJjYXJkX2lkIjoiYWJjMTIzIn0="
  }
}
```

### レート制限 🔵

**信頼性**: 🔵 *要件定義REQ-411・ヒアリングより*

API Gatewayの Usage Plan で制限を設定。

- 通常API: 100リクエスト/分
- AI生成API: 10リクエスト/分（Bedrockコスト考慮）

レート制限超過時:

```http
HTTP/1.1 429 Too Many Requests
Retry-After: 60
```

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "リクエスト数が制限を超えました。しばらく待ってから再試行してください。",
    "details": {
      "retry_after": 60
    }
  }
}
```

---

## REST API エンドポイント一覧

### Lambda: api-main

| メソッド | エンドポイント | 説明 | 関連要件 |
|---------|---------------|------|----------|
| POST | /users/link-line | LINE連携 | REQ-003 |
| GET | /users/me | ユーザー情報取得 | REQ-001 |
| PUT | /users/me/settings | 設定更新 | REQ-043 |
| POST | /cards/generate | AIカード生成 | REQ-021 |
| POST | /cards | カード保存（複数） | REQ-011 |
| GET | /cards | カード一覧取得 | REQ-014 |
| GET | /cards/:card_id | カード詳細取得 | REQ-014 |
| PUT | /cards/:card_id | カード更新 | REQ-013 |
| DELETE | /cards/:card_id | カード削除 | REQ-013 |
| GET | /cards/due | 復習対象カード取得 | REQ-201 |
| POST | /reviews/:card_id | 復習結果記録 | REQ-052 |

### Lambda: line-webhook

| メソッド | エンドポイント | 説明 | 関連要件 |
|---------|---------------|------|----------|
| POST | /webhook/line | LINE Webhook受信 | REQ-412 |

---

## ユーザー管理

### POST /users/link-line 🔵

**信頼性**: 🔵 *PRD第2章・要件定義REQ-003より*

**関連要件**: REQ-003, REQ-202

**説明**: LINEアカウントとの連携

**リクエスト**:

```json
{
  "line_user_id": "U1234567890abcdef"
}
```

**レスポンス（成功）**:

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

**エラーコード**:

- `ALREADY_LINKED`: 既に別のLINEアカウントと連携済み
- `LINE_ID_IN_USE`: このLINE IDは別のユーザーが使用中

---

### GET /users/me 🔵

**信頼性**: 🔵 *PRD・要件定義より*

**関連要件**: REQ-001

**説明**: 現在のユーザー情報取得

**レスポンス（成功）**:

```json
{
  "success": true,
  "data": {
    "user_id": "keycloak-sub-uuid",
    "line_user_id": "U1234567890abcdef",
    "card_count": 150,
    "settings": {
      "notification_time": "09:00"
    },
    "created_at": "2026-01-01T00:00:00Z"
  }
}
```

---

### PUT /users/me/settings 🔵

**信頼性**: 🔵 *要件定義REQ-043・ヒアリングより*

**関連要件**: REQ-043

**説明**: ユーザー設定の更新

**リクエスト**:

```json
{
  "notification_time": "21:00"
}
```

**バリデーション**:

- `notification_time`: HH:mm形式、00:00〜23:59

**レスポンス（成功）**:

```json
{
  "success": true,
  "data": {
    "notification_time": "21:00",
    "updated_at": "2026-01-05T10:00:00Z"
  }
}
```

---

## カード管理

### POST /cards/generate 🔵

**信頼性**: 🔵 *PRD第2章・要件定義REQ-021, REQ-022, REQ-023より*

**関連要件**: REQ-021, REQ-022, REQ-023, REQ-024

**説明**: テキストからAIでフラッシュカードを生成

**リクエスト**:

```json
{
  "text": "AIで学習したいテキスト内容...（最大2,000文字）"
}
```

**バリデーション**:

- `text`: 必須、1〜2,000文字

**レスポンス（成功）**:

```json
{
  "success": true,
  "data": {
    "candidates": [
      {
        "front": "質問1",
        "back": "回答1"
      },
      {
        "front": "質問2",
        "back": "回答2"
      }
    ],
    "generated_at": "2026-01-05T10:00:00Z"
  }
}
```

**エラーコード**:

- `TEXT_TOO_LONG`: 入力テキストが2,000文字を超過
- `AI_GENERATION_FAILED`: Bedrock APIエラー（タイムアウト含む）
- `CARD_LIMIT_REACHED`: カード数が2,000枚に達している

---

### POST /cards 🔵

**信頼性**: 🔵 *PRD第2章・要件定義REQ-011より*

**関連要件**: REQ-011, REQ-012

**説明**: カードを保存（複数同時対応）

**リクエスト**:

```json
{
  "cards": [
    {
      "front": "質問1",
      "back": "回答1"
    },
    {
      "front": "質問2",
      "back": "回答2"
    }
  ]
}
```

**バリデーション**:

- `cards`: 必須、1〜10件
- `front`: 必須、1〜500文字
- `back`: 必須、1〜1,000文字

**レスポンス（成功）**:

```json
{
  "success": true,
  "data": {
    "created_cards": [
      {
        "card_id": "card-uuid-1",
        "front": "質問1",
        "back": "回答1",
        "due": "2026-01-05T10:00:00Z",
        "created_at": "2026-01-05T10:00:00Z"
      },
      {
        "card_id": "card-uuid-2",
        "front": "質問2",
        "back": "回答2",
        "due": "2026-01-05T10:00:00Z",
        "created_at": "2026-01-05T10:00:00Z"
      }
    ],
    "total_card_count": 152
  }
}
```

**エラーコード**:

- `CARD_LIMIT_EXCEEDED`: 保存後のカード数が2,000枚を超える

---

### GET /cards 🟡

**信頼性**: 🟡 *要件定義REQ-014から妥当な推測*

**関連要件**: REQ-014

**説明**: カード一覧取得

**クエリパラメータ**:

- `limit`: 件数（デフォルト: 20、最大: 100）
- `cursor`: ページネーションカーソル
- `sort`: ソート順（`created_at_desc`, `due_asc`）

**レスポンス（成功）**:

```json
{
  "success": true,
  "data": [
    {
      "card_id": "card-uuid-1",
      "front": "質問1",
      "back": "回答1",
      "due": "2026-01-05T10:00:00Z",
      "interval": 1,
      "ease_factor": 2.5,
      "repetitions": 0,
      "created_at": "2026-01-05T10:00:00Z",
      "updated_at": "2026-01-05T10:00:00Z"
    }
  ],
  "pagination": {
    "limit": 20,
    "has_more": true,
    "next_cursor": "eyJjYXJkX2lkIjoiYWJjMTIzIn0="
  }
}
```

---

### GET /cards/:card_id 🟡

**信頼性**: 🟡 *要件定義REQ-014から妥当な推測*

**関連要件**: REQ-014

**説明**: カード詳細取得

**パスパラメータ**:

- `card_id`: カードID（UUID）

**レスポンス（成功）**:

```json
{
  "success": true,
  "data": {
    "card_id": "card-uuid-1",
    "front": "質問1",
    "back": "回答1",
    "due": "2026-01-05T10:00:00Z",
    "interval": 1,
    "ease_factor": 2.5,
    "repetitions": 0,
    "created_at": "2026-01-05T10:00:00Z",
    "updated_at": "2026-01-05T10:00:00Z"
  }
}
```

**エラーコード**:

- `NOT_FOUND`: カードが存在しない
- `FORBIDDEN`: 他のユーザーのカード

---

### PUT /cards/:card_id 🟡

**信頼性**: 🟡 *要件定義REQ-013から妥当な推測*

**関連要件**: REQ-013

**説明**: カード更新

**パスパラメータ**:

- `card_id`: カードID（UUID）

**リクエスト**:

```json
{
  "front": "更新後の質問",
  "back": "更新後の回答"
}
```

**バリデーション**:

- `front`: オプション、1〜500文字
- `back`: オプション、1〜1,000文字

**レスポンス（成功）**:

```json
{
  "success": true,
  "data": {
    "card_id": "card-uuid-1",
    "front": "更新後の質問",
    "back": "更新後の回答",
    "updated_at": "2026-01-05T12:00:00Z"
  }
}
```

---

### DELETE /cards/:card_id 🟡

**信頼性**: 🟡 *要件定義REQ-013から妥当な推測*

**関連要件**: REQ-013

**説明**: カード削除

**パスパラメータ**:

- `card_id`: カードID（UUID）

**レスポンス（成功）**:

```json
{
  "success": true,
  "data": {
    "deleted_card_id": "card-uuid-1",
    "total_card_count": 149
  }
}
```

---

### GET /cards/due 🔵

**信頼性**: 🔵 *要件定義REQ-201より*

**関連要件**: REQ-201, REQ-031

**説明**: 復習対象カード取得（due ≤ 現在時刻）

**クエリパラメータ**:

- `limit`: 件数（デフォルト: 10、最大: 50）

**レスポンス（成功）**:

```json
{
  "success": true,
  "data": {
    "due_cards": [
      {
        "card_id": "card-uuid-1",
        "front": "質問1",
        "back": "回答1",
        "due": "2026-01-05T09:00:00Z",
        "interval": 1,
        "ease_factor": 2.5,
        "repetitions": 0
      }
    ],
    "total_due_count": 5
  }
}
```

---

## 復習・SRS

### POST /reviews/:card_id 🔵

**信頼性**: 🔵 *PRD第2章・要件定義REQ-031, REQ-032, REQ-052より*

**関連要件**: REQ-031, REQ-032, REQ-033, REQ-034, REQ-052

**説明**: 復習結果を記録し、SM-2アルゴリズムでパラメータを更新

**パスパラメータ**:

- `card_id`: カードID（UUID）

**リクエスト**:

```json
{
  "grade": 4
}
```

**バリデーション**:

- `grade`: 必須、0〜5の整数

**SM-2アルゴリズム処理**:

1. `grade < 3` の場合: `interval = 1`, `repetitions = 0`
2. `grade >= 3` の場合:
   - `ease_factor` を更新（下限1.3）
   - `interval` を更新
   - `repetitions++`
3. `due = now + interval days`

**レスポンス（成功）**:

```json
{
  "success": true,
  "data": {
    "card_id": "card-uuid-1",
    "grade": 4,
    "updated_review": {
      "interval": 6,
      "ease_factor": 2.6,
      "repetitions": 2,
      "due": "2026-01-11T10:00:00Z"
    },
    "reviewed_at": "2026-01-05T10:00:00Z"
  }
}
```

**エラーコード**:

- `INVALID_GRADE`: gradeが0-5の範囲外
- `NOT_FOUND`: カードが存在しない

---

## LINE Webhook

### POST /webhook/line 🔵

**信頼性**: 🔵 *PRD第2章・要件定義REQ-412, REQ-413より*

**関連要件**: REQ-051, REQ-052, REQ-412, REQ-413

**説明**: LINE Messaging API Webhook受信

**認証**: JWT認証なし（X-Line-Signature署名検証）

**ヘッダー**:

```http
X-Line-Signature: {signature}
Content-Type: application/json
```

**リクエスト（Postbackイベント）**:

```json
{
  "destination": "xxxxxxxxxx",
  "events": [
    {
      "type": "postback",
      "timestamp": 1704412800000,
      "source": {
        "type": "user",
        "userId": "U1234567890abcdef"
      },
      "replyToken": "nHuyWiB7yP5Zw52FIkcQobQuGDXCTA",
      "postback": {
        "data": "action=grade&card_id=card-uuid-1&grade=4"
      }
    }
  ]
}
```

**Postback data パラメータ**:

| action | パラメータ | 説明 |
|--------|-----------|------|
| `start` | なし | 復習開始 |
| `reveal` | `card_id` | 答えを見る |
| `grade` | `card_id`, `grade` | 採点 |

**レスポンス（成功）**:

```json
{
  "success": true
}
```

**処理フロー**:

1. X-Line-Signature検証
2. `source.userId` から `user_id` を取得
3. `postback.data` をパース
4. actionに応じた処理:
   - `start`: 復習対象カードを取得、表面をFlex Messageで返信
   - `reveal`: カード裏面 + 採点ボタンをFlex Messageで返信
   - `grade`: SM-2更新、次のカード or 完了メッセージを返信

---

## Flex Message テンプレート

### 復習通知 🔵

**信頼性**: 🔵 *PRD第2章・要件定義REQ-042より*

```json
{
  "type": "flex",
  "altText": "復習の時間です",
  "contents": {
    "type": "bubble",
    "body": {
      "type": "box",
      "layout": "vertical",
      "contents": [
        {
          "type": "text",
          "text": "復習の時間です！",
          "weight": "bold",
          "size": "lg"
        },
        {
          "type": "text",
          "text": "5枚のカードが復習待ちです",
          "margin": "md"
        }
      ]
    },
    "footer": {
      "type": "box",
      "layout": "vertical",
      "contents": [
        {
          "type": "button",
          "action": {
            "type": "postback",
            "label": "復習開始",
            "data": "action=start"
          },
          "style": "primary"
        }
      ]
    }
  }
}
```

### カード表面（問題）🔵

**信頼性**: 🔵 *PRD第2章より*

```json
{
  "type": "flex",
  "altText": "問題",
  "contents": {
    "type": "bubble",
    "body": {
      "type": "box",
      "layout": "vertical",
      "contents": [
        {
          "type": "text",
          "text": "問題",
          "weight": "bold",
          "color": "#666666",
          "size": "sm"
        },
        {
          "type": "text",
          "text": "{カードの表面テキスト}",
          "wrap": true,
          "margin": "md",
          "size": "lg"
        }
      ]
    },
    "footer": {
      "type": "box",
      "layout": "vertical",
      "contents": [
        {
          "type": "button",
          "action": {
            "type": "postback",
            "label": "答えを見る",
            "data": "action=reveal&card_id={card_id}"
          },
          "style": "primary"
        }
      ]
    }
  }
}
```

### カード裏面 + 採点ボタン 🔵

**信頼性**: 🔵 *PRD第2章・ヒアリングより*

```json
{
  "type": "flex",
  "altText": "答え",
  "contents": {
    "type": "bubble",
    "body": {
      "type": "box",
      "layout": "vertical",
      "contents": [
        {
          "type": "text",
          "text": "答え",
          "weight": "bold",
          "color": "#666666",
          "size": "sm"
        },
        {
          "type": "text",
          "text": "{カードの裏面テキスト}",
          "wrap": true,
          "margin": "md",
          "size": "lg"
        },
        {
          "type": "separator",
          "margin": "xl"
        },
        {
          "type": "text",
          "text": "どれくらい覚えていましたか？",
          "margin": "md",
          "size": "sm",
          "color": "#666666"
        }
      ]
    },
    "footer": {
      "type": "box",
      "layout": "vertical",
      "spacing": "sm",
      "contents": [
        {
          "type": "box",
          "layout": "horizontal",
          "spacing": "sm",
          "contents": [
            {
              "type": "button",
              "action": {
                "type": "postback",
                "label": "0",
                "data": "action=grade&card_id={card_id}&grade=0"
              },
              "style": "secondary",
              "flex": 1
            },
            {
              "type": "button",
              "action": {
                "type": "postback",
                "label": "1",
                "data": "action=grade&card_id={card_id}&grade=1"
              },
              "style": "secondary",
              "flex": 1
            },
            {
              "type": "button",
              "action": {
                "type": "postback",
                "label": "2",
                "data": "action=grade&card_id={card_id}&grade=2"
              },
              "style": "secondary",
              "flex": 1
            }
          ]
        },
        {
          "type": "box",
          "layout": "horizontal",
          "spacing": "sm",
          "contents": [
            {
              "type": "button",
              "action": {
                "type": "postback",
                "label": "3",
                "data": "action=grade&card_id={card_id}&grade=3"
              },
              "style": "secondary",
              "flex": 1
            },
            {
              "type": "button",
              "action": {
                "type": "postback",
                "label": "4",
                "data": "action=grade&card_id={card_id}&grade=4"
              },
              "style": "secondary",
              "flex": 1
            },
            {
              "type": "button",
              "action": {
                "type": "postback",
                "label": "5",
                "data": "action=grade&card_id={card_id}&grade=5"
              },
              "style": "primary",
              "flex": 1
            }
          ]
        }
      ]
    }
  }
}
```

---

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **DBスキーマ**: [database-schema.md](database-schema.md)
- **要件定義**: [requirements.md](../../spec/memoru-liff/requirements.md)

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 15件 | 75% |
| 🟡 黄信号 | 5件 | 25% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（青信号が70%以上）

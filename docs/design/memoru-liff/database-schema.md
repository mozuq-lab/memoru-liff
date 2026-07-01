# memoru-liff データベーススキーマ

> ⚠️ **この資料は MVP 初期設計（2026-01-05）であり、現行実装と乖離しています。**
> テーブル数（実際は 7）、reviews テーブルの役割（実際は分析専用の追記ログ）、
> SRS 状態の置き場所（実際は cards テーブル）などが現在と異なります。
> **最新の正は [`docs/database-schema.md`](../../database-schema.md) を参照してください。**
> 本ファイルは設計経緯の歴史的参考として残しています。

**作成日**: 2026-01-05
**関連設計**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/memoru-liff/requirements.md)

**【信頼性レベル凡例】**:

- 🔵 **青信号**: EARS要件定義書・設計文書・ユーザヒアリングを参考にした確実な定義
- 🟡 **黄信号**: EARS要件定義書・設計文書・ユーザヒアリングから妥当な推測による定義
- 🔴 **赤信号**: EARS要件定義書・設計文書・ユーザヒアリングにない推測による定義

---

## データストア概要 🔵

**信頼性**: 🔵 *PRD第1章・要件定義REQ-402より*

| データストア | 用途 | 理由 |
|-------------|------|------|
| **DynamoDB** | メインデータストア | PRD指定、サーバーレス親和性、オンデマンドキャパシティ |
| **RDS PostgreSQL** | Keycloak専用 | Keycloak標準サポート |

本ドキュメントでは、アプリケーションデータを格納する **DynamoDB** のスキーマを定義します。

---

## DynamoDB テーブル設計方針 🔵

**信頼性**: 🔵 *DynamoDBベストプラクティスより*

### シングルテーブル設計 vs マルチテーブル設計

本プロジェクトでは **マルチテーブル設計** を採用します。

**理由**:

1. MVPの段階でシンプルさを優先
2. テーブル間の関連が明確（users → cards → reviews）
3. アクセスパターンが限定的
4. 開発・デバッグの容易さ

---

## テーブル定義

### users テーブル 🔵

**信頼性**: 🔵 *PRD第2章・要件定義より*

**関連要件**: REQ-001, REQ-003, REQ-043, REQ-202

**用途**: ユーザー情報、LINE連携情報、設定を格納

#### テーブル構成

| 属性名 | 型 | キー | 説明 | 信頼性 |
|--------|-----|------|------|--------|
| `user_id` | String | PK | Keycloak sub（UUID） | 🔵 |
| `line_user_id` | String | GSI-PK | LINE ユーザーID | 🔵 |
| `notification_time` | String | - | 通知時間（HH:mm形式） | 🔵 |
| `card_count` | Number | - | 所有カード数（キャッシュ） | 🟡 |
| `created_at` | String | - | 作成日時（ISO 8601） | 🔵 |
| `updated_at` | String | - | 更新日時（ISO 8601） | 🔵 |

#### キー設計

```yaml
TableName: memoru-users
KeySchema:
  - AttributeName: user_id
    KeyType: HASH

GlobalSecondaryIndexes:
  - IndexName: line_user_id-index
    KeySchema:
      - AttributeName: line_user_id
        KeyType: HASH
    Projection:
      ProjectionType: ALL
```

#### アクセスパターン

| パターン | 操作 | キー | 信頼性 |
|---------|------|------|--------|
| ユーザー取得（認証後） | GetItem | `user_id` | 🔵 |
| LINE IDからユーザー特定 | Query (GSI) | `line_user_id` | 🔵 |
| 通知対象ユーザー取得 | Scan + Filter | `notification_time` | 🟡 |

#### サンプルデータ

```json
{
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "line_user_id": "U1234567890abcdef1234567890abcdef",
  "notification_time": "09:00",
  "card_count": 150,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-01-05T10:00:00Z"
}
```

---

### cards テーブル 🔵

**信頼性**: 🔵 *PRD第2章・要件定義より*

**関連要件**: REQ-011, REQ-012, REQ-013, REQ-014

**用途**: フラッシュカードデータを格納

#### テーブル構成

| 属性名 | 型 | キー | 説明 | 信頼性 |
|--------|-----|------|------|--------|
| `user_id` | String | PK | 所有ユーザーID | 🔵 |
| `card_id` | String | SK | カードID（UUID） | 🔵 |
| `front` | String | - | カード表面（問題） | 🔵 |
| `back` | String | - | カード裏面（答え） | 🔵 |
| `created_at` | String | - | 作成日時（ISO 8601） | 🔵 |
| `updated_at` | String | - | 更新日時（ISO 8601） | 🔵 |

#### キー設計

```yaml
TableName: memoru-cards
KeySchema:
  - AttributeName: user_id
    KeyType: HASH
  - AttributeName: card_id
    KeyType: RANGE
```

#### アクセスパターン

| パターン | 操作 | キー | 信頼性 |
|---------|------|------|--------|
| ユーザーのカード一覧 | Query | `user_id` | 🔵 |
| カード詳細取得 | GetItem | `user_id` + `card_id` | 🔵 |
| カード作成 | PutItem | `user_id` + `card_id` | 🔵 |
| カード更新 | UpdateItem | `user_id` + `card_id` | 🔵 |
| カード削除 | DeleteItem | `user_id` + `card_id` | 🔵 |
| カード数カウント | Query (Select: COUNT) | `user_id` | 🔵 |

#### サンプルデータ

```json
{
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "card_id": "card-1111-2222-3333-444455556666",
  "front": "日本の首都は？",
  "back": "東京",
  "created_at": "2026-01-05T10:00:00Z",
  "updated_at": "2026-01-05T10:00:00Z"
}
```

---

### reviews テーブル 🔵

**信頼性**: 🔵 *PRD第2章・要件定義より*

**関連要件**: REQ-031, REQ-032, REQ-033, REQ-034, REQ-201

**用途**: SRS（間隔反復学習）パラメータを格納

#### テーブル構成

| 属性名 | 型 | キー | 説明 | 信頼性 |
|--------|-----|------|------|--------|
| `user_id` | String | PK | 所有ユーザーID | 🔵 |
| `card_id` | String | SK | カードID | 🔵 |
| `due` | String | GSI-SK | 次回復習日時（ISO 8601） | 🔵 |
| `interval` | Number | - | 復習間隔（日数） | 🔵 |
| `ease_factor` | Number | - | 難易度係数（≥1.3） | 🔵 |
| `repetitions` | Number | - | 連続正解回数 | 🔵 |
| `last_reviewed_at` | String | - | 最終復習日時 | 🟡 |

#### キー設計

```yaml
TableName: memoru-reviews
KeySchema:
  - AttributeName: user_id
    KeyType: HASH
  - AttributeName: card_id
    KeyType: RANGE

GlobalSecondaryIndexes:
  - IndexName: user_id-due-index
    KeySchema:
      - AttributeName: user_id
        KeyType: HASH
      - AttributeName: due
        KeyType: RANGE
    Projection:
      ProjectionType: ALL
```

#### アクセスパターン

| パターン | 操作 | キー | 信頼性 |
|---------|------|------|--------|
| カードのSRSパラメータ取得 | GetItem | `user_id` + `card_id` | 🔵 |
| 復習対象カード取得 | Query (GSI) | `user_id` + `due <= now` | 🔵 |
| SRSパラメータ更新 | UpdateItem | `user_id` + `card_id` | 🔵 |
| 初期パラメータ作成 | PutItem | `user_id` + `card_id` | 🔵 |

#### 初期値（新規カード作成時）🔵

**信頼性**: 🔵 *SM-2アルゴリズム仕様より*

```json
{
  "interval": 1,
  "ease_factor": 2.5,
  "repetitions": 0,
  "due": "{作成日時}"
}
```

#### サンプルデータ

```json
{
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "card_id": "card-1111-2222-3333-444455556666",
  "due": "2026-01-10T09:00:00Z",
  "interval": 6,
  "ease_factor": 2.6,
  "repetitions": 2,
  "last_reviewed_at": "2026-01-04T09:00:00Z"
}
```

---

### settings テーブル 🟡

**信頼性**: 🟡 *将来の拡張性を考慮した妥当な推測*

**関連要件**: REQ-043

**用途**: システム設定、将来の拡張用

**備考**: MVP段階では `users` テーブルの `notification_time` で対応。拡張が必要になった場合に分離を検討。

---

## ER図（概念） 🔵

**信頼性**: 🔵 *PRD・要件定義より*

```
┌─────────────────────────────────────────────────────────────────────┐
│                           DynamoDB Tables                           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────┐
│     users       │
├─────────────────┤
│ PK: user_id     │───────────────────────────────────────┐
│    (Keycloak    │                                       │
│     sub UUID)   │                                       │
├─────────────────┤                                       │
│ line_user_id    │◄──── GSI: line_user_id-index         │
│ notification_   │       (Webhook時のユーザー特定用)      │
│   time          │                                       │
│ card_count      │                                       │
│ created_at      │                                       │
│ updated_at      │                                       │
└─────────────────┘                                       │
                                                          │
        ┌─────────────────────────────────────────────────┤
        │                                                 │
        ▼                                                 ▼
┌─────────────────┐                           ┌─────────────────┐
│     cards       │                           │    reviews      │
├─────────────────┤                           ├─────────────────┤
│ PK: user_id     │                           │ PK: user_id     │
│ SK: card_id     │◄─────────────────────────►│ SK: card_id     │
├─────────────────┤      1:1 関係             ├─────────────────┤
│ front           │                           │ due             │◄─ GSI
│ back            │                           │ interval        │
│ created_at      │                           │ ease_factor     │
│ updated_at      │                           │ repetitions     │
└─────────────────┘                           │ last_reviewed_at│
                                              └─────────────────┘
```

---

## データ整合性 🟡

**信頼性**: 🟡 *DynamoDB特性から妥当な推測*

### cards と reviews の整合性

cards と reviews は 1:1 の関係があり、整合性を保つ必要があります。

#### カード作成時

**TransactWriteItems** を使用して原子的に操作:

```python
transact_items = [
    {
        'Put': {
            'TableName': 'memoru-cards',
            'Item': {
                'user_id': {'S': user_id},
                'card_id': {'S': card_id},
                'front': {'S': front},
                'back': {'S': back},
                'created_at': {'S': now},
                'updated_at': {'S': now}
            }
        }
    },
    {
        'Put': {
            'TableName': 'memoru-reviews',
            'Item': {
                'user_id': {'S': user_id},
                'card_id': {'S': card_id},
                'due': {'S': now},
                'interval': {'N': '1'},
                'ease_factor': {'N': '2.5'},
                'repetitions': {'N': '0'}
            }
        }
    },
    {
        'Update': {
            'TableName': 'memoru-users',
            'Key': {'user_id': {'S': user_id}},
            'UpdateExpression': 'SET card_count = card_count + :inc',
            'ExpressionAttributeValues': {':inc': {'N': '1'}}
        }
    }
]
```

#### カード削除時

**TransactWriteItems** を使用:

```python
transact_items = [
    {
        'Delete': {
            'TableName': 'memoru-cards',
            'Key': {'user_id': {'S': user_id}, 'card_id': {'S': card_id}}
        }
    },
    {
        'Delete': {
            'TableName': 'memoru-reviews',
            'Key': {'user_id': {'S': user_id}, 'card_id': {'S': card_id}}
        }
    },
    {
        'Update': {
            'TableName': 'memoru-users',
            'Key': {'user_id': {'S': user_id}},
            'UpdateExpression': 'SET card_count = card_count - :dec',
            'ExpressionAttributeValues': {':dec': {'N': '1'}}
        }
    }
]
```

---

## カード数制限の実装 🔵

**信頼性**: 🔵 *要件定義REQ-012・ヒアリングより*

**関連要件**: REQ-012, EDGE-101

### 方式1: card_count キャッシュ（推奨）

`users.card_count` を使用して高速にチェック。

```python
# カード作成前のチェック
response = table.get_item(Key={'user_id': user_id})
if response['Item']['card_count'] >= 2000:
    raise CardLimitExceededError()
```

### 方式2: Query Count（正確だが遅い）

```python
response = cards_table.query(
    KeyConditionExpression=Key('user_id').eq(user_id),
    Select='COUNT'
)
if response['Count'] >= 2000:
    raise CardLimitExceededError()
```

---

## GSI 設計詳細 🔵

**信頼性**: 🔵 *アクセスパターンより*

### line_user_id-index (users)

**用途**: LINE Webhook受信時に `line_user_id` から `user_id` を特定

```yaml
IndexName: line_user_id-index
KeySchema:
  - AttributeName: line_user_id
    KeyType: HASH
Projection:
  ProjectionType: ALL
ProvisionedThroughput:
  ReadCapacityUnits: 5
  WriteCapacityUnits: 5
```

### user_id-due-index (reviews)

**用途**: 復習対象カードの効率的な取得

```yaml
IndexName: user_id-due-index
KeySchema:
  - AttributeName: user_id
    KeyType: HASH
  - AttributeName: due
    KeyType: RANGE
Projection:
  ProjectionType: ALL
ProvisionedThroughput:
  ReadCapacityUnits: 10
  WriteCapacityUnits: 5
```

**クエリ例**:

```python
response = reviews_table.query(
    IndexName='user_id-due-index',
    KeyConditionExpression=
        Key('user_id').eq(user_id) & Key('due').lte(now)
)
```

---

## キャパシティ設計 🟡

**信頼性**: 🟡 *NFR要件から妥当な推測*

### オンデマンドキャパシティ（推奨）

MVP段階ではオンデマンドキャパシティモードを使用。

```yaml
BillingMode: PAY_PER_REQUEST
```

**理由**:

- 初期トラフィックが予測困難
- 自動スケーリング
- 低コスト（使用量に応じた課金）

### 将来のプロビジョンドキャパシティ移行

ユーザー数が増加し、トラフィックパターンが安定した場合に検討。

---

## バックアップ・リストア 🟡

**信頼性**: 🟡 *NFR要件から妥当な推測*

### ポイントインタイムリカバリ（PITR）

```yaml
PointInTimeRecoverySpecification:
  PointInTimeRecoveryEnabled: true
```

### オンデマンドバックアップ

重要なマイグレーション前に手動バックアップを取得。

---

## SAM テンプレート例 🔵

**信頼性**: 🔵 *PRD・アーキテクチャ設計より*

```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  UsersTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: memoru-users
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: user_id
          AttributeType: S
        - AttributeName: line_user_id
          AttributeType: S
      KeySchema:
        - AttributeName: user_id
          KeyType: HASH
      GlobalSecondaryIndexes:
        - IndexName: line_user_id-index
          KeySchema:
            - AttributeName: line_user_id
              KeyType: HASH
          Projection:
            ProjectionType: ALL
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true

  CardsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: memoru-cards
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: user_id
          AttributeType: S
        - AttributeName: card_id
          AttributeType: S
      KeySchema:
        - AttributeName: user_id
          KeyType: HASH
        - AttributeName: card_id
          KeyType: RANGE
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true

  ReviewsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: memoru-reviews
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: user_id
          AttributeType: S
        - AttributeName: card_id
          AttributeType: S
        - AttributeName: due
          AttributeType: S
      KeySchema:
        - AttributeName: user_id
          KeyType: HASH
        - AttributeName: card_id
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: user_id-due-index
          KeySchema:
            - AttributeName: user_id
              KeyType: HASH
            - AttributeName: due
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
```

---

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **API仕様**: [api-endpoints.md](api-endpoints.md)
- **要件定義**: [requirements.md](../../spec/memoru-liff/requirements.md)

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 28件 | 80% |
| 🟡 黄信号 | 7件 | 20% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（青信号が80%以上）

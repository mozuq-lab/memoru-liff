# Auto Study Notes データベーススキーマ

**作成日**: 2026-03-07
**関連設計**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/auto-study-notes/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・既存DBスキーマを参考にした確実な定義
- 🟡 **黄信号**: EARS要件定義書・設計文書・既存DBスキーマから妥当な推測による定義
- 🔴 **赤信号**: EARS要件定義書・設計文書・既存DBスキーマにない推測による定義

---

## 新規テーブル: study-notes 🔵

**信頼性**: 🔵 *設計ヒアリング「新規テーブル」選択・REQ-ASN-021より*

**関連要件**: REQ-ASN-021, REQ-ASN-022, REQ-ASN-023

**用途**: 要約ノートのキャッシュを格納

### テーブル構成

| 属性名 | 型 | キー | 説明 | 信頼性 |
|--------|-----|------|------|--------|
| `user_id` | String | PK | 所有ユーザーID（Keycloak sub UUID） | 🔵 |
| `source_key` | String | SK | `{source_type}::{source_id}`（例: `deck::deck-uuid`, `tag::english`） | 🔵 |
| `source_type` | String | - | 生成ソース種別（`deck` or `tag`） | 🔵 |
| `source_id` | String | - | デッキID or タグ名 | 🔵 |
| `content` | String | - | 要約ノート本文（Markdown形式） | 🔵 |
| `card_count` | Number | - | 生成時のカード枚数 | 🟡 |
| `is_stale` | Boolean | - | 無効化フラグ（`true` = キャッシュ古い） | 🔵 |
| `model_used` | String | - | 使用したAIモデル名 | 🔵 |
| `processing_time_ms` | Number | - | AI生成所要時間（ミリ秒） | 🔵 |
| `generated_at` | String | - | 生成日時（ISO 8601） | 🔵 |
| `created_at` | String | - | レコード作成日時（ISO 8601） | 🔵 |
| `updated_at` | String | - | レコード更新日時（ISO 8601） | 🔵 |

### キー設計

```yaml
TableName: memoru-study-notes
KeySchema:
  - AttributeName: user_id
    KeyType: HASH
  - AttributeName: source_key
    KeyType: RANGE
```

**設計理由**:
- PK = `user_id`: ユーザーデータの分離を保証（REQ-ASN-405）
- SK = `source_key`: `{source_type}::{source_id}` 形式で、デッキ・タグの両方を1テーブルで管理
- GSIは不要（アクセスパターンがPK+SKのみ）

### アクセスパターン

| パターン | 操作 | キー | 用途 | 信頼性 |
|---------|------|------|------|--------|
| キャッシュ取得 | GetItem | `user_id` + `source_key` | 要約ノート表示時 | 🔵 |
| キャッシュ保存/更新 | PutItem | `user_id` + `source_key` | 要約ノート生成後 | 🔵 |
| キャッシュ無効化 | UpdateItem | `user_id` + `source_key` | カードCRUD時 (`is_stale=true`) | 🔵 |
| ユーザーの全キャッシュ取得 | Query | `user_id` | デバッグ/管理用 | 🟡 |

### サンプルデータ

**デッキ単位のキャッシュ**:
```json
{
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "source_key": "deck::deck-1111-2222-3333-444455556666",
  "source_type": "deck",
  "source_id": "deck-1111-2222-3333-444455556666",
  "content": "## 全体像\n\nこのデッキは日本の地理に関する...\n\n## 重要ポイント\n\n- 日本の首都は東京\n- ...\n\n## カード間の関連性\n\n...\n\n## 学習のヒント\n\n...",
  "card_count": 25,
  "is_stale": false,
  "model_used": "anthropic.claude-3-sonnet-20240229-v1:0",
  "processing_time_ms": 8500,
  "generated_at": "2026-03-07T10:00:00Z",
  "created_at": "2026-03-07T10:00:00Z",
  "updated_at": "2026-03-07T10:00:00Z"
}
```

**タグ単位のキャッシュ**:
```json
{
  "user_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "source_key": "tag::english",
  "source_type": "tag",
  "source_id": "english",
  "content": "## Overview\n\nThis collection covers English grammar...",
  "card_count": 40,
  "is_stale": true,
  "model_used": "anthropic.claude-3-sonnet-20240229-v1:0",
  "processing_time_ms": 12000,
  "generated_at": "2026-03-06T15:00:00Z",
  "created_at": "2026-03-06T15:00:00Z",
  "updated_at": "2026-03-07T08:00:00Z"
}
```

---

## キャッシュ無効化の実装 🔵

**信頼性**: 🔵 *設計ヒアリング「同期的フラグ更新」選択より*

### カードCRUD時の無効化処理

カードの作成・更新・削除時に、該当カードの `deck_id` と `tags` に紐づくキャッシュを無効化する。

**注意**: カード更新時にタグやデッキIDが変更された場合は、**旧値と新値の両方**のキャッシュを無効化する必要がある。

```python
# card_service.py 内のカードCRUD操作後に追加
def _invalidate_study_notes_cache(
    self,
    user_id: str,
    deck_id: str,
    tags: list[str],
    old_deck_id: str | None = None,
    old_tags: list[str] | None = None,
) -> None:
    """カードCRUD後にstudy-notesキャッシュを無効化.

    カード更新時にdeck_idやtagsが変更された場合、旧値のキャッシュも無効化する。
    """
    keys_to_invalidate: set[str] = set()

    # 現在のデッキのキャッシュ
    if deck_id:
        keys_to_invalidate.add(f"deck::{deck_id}")

    # 旧デッキのキャッシュ（デッキ移動時）
    if old_deck_id and old_deck_id != deck_id:
        keys_to_invalidate.add(f"deck::{old_deck_id}")

    # 現在のタグのキャッシュ
    for tag in tags:
        keys_to_invalidate.add(f"tag::{tag}")

    # 旧タグのキャッシュ（タグ変更時）
    if old_tags:
        for tag in old_tags:
            keys_to_invalidate.add(f"tag::{tag}")

    for source_key in keys_to_invalidate:
        try:
            self.study_notes_table.update_item(
                Key={"user_id": user_id, "source_key": source_key},
                UpdateExpression="SET is_stale = :true, updated_at = :now",
                ExpressionAttributeValues={
                    ":true": True,
                    ":now": datetime.now(UTC).isoformat(),
                },
                ConditionExpression="attribute_exists(user_id)",
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise  # キャッシュが存在しない場合は無視
```

---

## SAM テンプレート追加 🔵

**信頼性**: 🔵 *既存SAMテンプレート・マルチテーブル設計より*

```yaml
# template.yaml に追加
StudyNotesTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: memoru-study-notes
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - AttributeName: user_id
        AttributeType: S
      - AttributeName: source_key
        AttributeType: S
    KeySchema:
      - AttributeName: user_id
        KeyType: HASH
      - AttributeName: source_key
        KeyType: RANGE
    PointInTimeRecoverySpecification:
      PointInTimeRecoveryEnabled: true
```

---

## 既存テーブルへの影響 🔵

**信頼性**: 🔵 *既存DBスキーマ・アーキテクチャ設計より*

### cards テーブル

変更なし。既存の `deck_id` と `tags` 属性をキャッシュ無効化のキーとして使用する。

### reviews テーブル

変更なし。100枚超デッキの代表カード選択時に `ease_factor` と `repetitions` を参照する。

### users テーブル

変更なし。

---

## ER図（study-notes 追加後） 🔵

**信頼性**: 🔵 *既存ER図・新規テーブル設計より*

```
┌─────────────────┐
│     users       │
├─────────────────┤
│ PK: user_id     │─────────────────────────────┐
└─────────────────┘                              │
        │                                        │
        ▼                                        ▼
┌─────────────────┐     1:1     ┌─────────────────┐
│     cards       │◄───────────►│    reviews      │
├─────────────────┤             ├─────────────────┤
│ PK: user_id     │             │ PK: user_id     │
│ SK: card_id     │             │ SK: card_id     │
│ deck_id         │──┐          │ ease_factor     │
│ tags            │──┤          │ repetitions     │
└─────────────────┘  │          └─────────────────┘
                     │
                     │ deck_id/tags で
                     │ キャッシュ無効化
                     ▼
              ┌─────────────────┐
              │  study-notes    │  ← NEW
              ├─────────────────┤
              │ PK: user_id     │
              │ SK: source_key  │
              │ content         │
              │ is_stale        │
              │ card_count      │
              └─────────────────┘
```

---

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **API仕様**: [api-endpoints.md](api-endpoints.md)
- **既存DBスキーマ**: [../../design/memoru-liff/database-schema.md](../memoru-liff/database-schema.md)

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 16件 | 89% |
| 🟡 黄信号 | 2件 | 11% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（青信号が89%、赤信号なし）

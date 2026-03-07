# Auto Study Notes API エンドポイント仕様

**作成日**: 2026-03-07
**関連設計**: [architecture.md](architecture.md)
**関連要件定義**: [requirements.md](../../spec/auto-study-notes/requirements.md)

**【信頼性レベル凡例】**:
- 🔵 **青信号**: EARS要件定義書・設計文書・既存API仕様を参考にした確実な定義
- 🟡 **黄信号**: EARS要件定義書・設計文書・既存API仕様から妥当な推測による定義
- 🔴 **赤信号**: EARS要件定義書・設計文書・既存API仕様にない推測による定義

---

## 共通仕様 🔵

**信頼性**: 🔵 *既存API仕様より*

既存の API 共通仕様（認証、エラーフォーマット、レート制限）を継承します。
詳細は [既存API仕様](../memoru-liff/api-endpoints.md) を参照。

- **認証**: `Authorization: Bearer {keycloak_jwt_token}` 必須
- **レート制限**: AI生成API枠 — 10リクエスト/分
- **エラーフォーマット**: 既存の `{"success": false, "error": {...}}` 形式

---

## エンドポイント一覧

### Lambda: api-main（既存Lambdaに追加）

| メソッド | エンドポイント | 説明 | 関連要件 | 信頼性 |
|---------|---------------|------|----------|--------|
| POST | /study-notes/generate | 要約ノート生成 | REQ-ASN-001, REQ-ASN-002 | 🔵 |
| GET | /study-notes | 要約ノート取得（キャッシュ） | REQ-ASN-023 | 🔵 |

---

## POST /study-notes/generate 🔵

**信頼性**: 🔵 *REQ-ASN-001, REQ-ASN-002, REQ-ASN-021・設計ヒアリング「同期レスポンス」選択より*

**関連要件**: REQ-ASN-001, REQ-ASN-002, REQ-ASN-021, REQ-ASN-031〜034, REQ-ASN-051

**説明**: デッキまたはタグの要約ノートを生成（キャッシュがない場合や再生成時）

### リクエスト

```json
{
  "source_type": "deck",
  "source_id": "deck-uuid-1234"
}
```

**バリデーション**:

| パラメータ | 型 | 必須 | 制約 | 信頼性 |
|-----------|-----|------|------|--------|
| `source_type` | String | Yes | `"deck"` or `"tag"` | 🔵 |
| `source_id` | String | Yes | デッキID（UUID）またはタグ名 | 🔵 |

### レスポンス（成功 — 200 OK）

```json
{
  "success": true,
  "data": {
    "source_type": "deck",
    "source_id": "deck-uuid-1234",
    "content": "## 全体像\n\nこのデッキは...\n\n## 重要ポイント\n\n- ポイント1\n- ポイント2\n\n## カード間の関連性\n\n...\n\n## 学習のヒント\n\n...",
    "card_count": 25,
    "is_stale": false,
    "model_used": "anthropic.claude-3-sonnet-20240229-v1:0",
    "processing_time_ms": 8500,
    "generated_at": "2026-03-07T10:00:00Z"
  }
}
```

### エラーコード

| HTTPステータス | コード | 条件 | 信頼性 |
|---------------|--------|------|--------|
| 400 | `INSUFFICIENT_CARDS` | 対象カード数が5枚未満 | 🔵 |
| 400 | `VALIDATION_ERROR` | source_type/source_id が不正 | 🔵 |
| 403 | `FORBIDDEN` | 他ユーザーのデッキへのアクセス | 🔵 |
| 404 | `NOT_FOUND` | デッキが存在しない | 🔵 |
| 429 | `RATE_LIMIT_EXCEEDED` | AI生成APIレート制限超過 | 🔵 |
| 504 | `AI_TIMEOUT` | Bedrock APIタイムアウト | 🟡 |
| 503 | `AI_PROVIDER_ERROR` | Bedrock APIエラー | 🟡 |

### エラーレスポンス例

**カード数不足**:
```json
{
  "success": false,
  "error": {
    "code": "INSUFFICIENT_CARDS",
    "message": "要約ノートの生成には5枚以上のカードが必要です。現在3枚です。",
    "details": {
      "current_count": 3,
      "minimum_required": 5
    }
  }
}
```

**AIタイムアウト**:
```json
{
  "success": false,
  "error": {
    "code": "AI_TIMEOUT",
    "message": "要約の生成に失敗しました。しばらく後に再試行してください。",
    "details": {
      "retry_after": 30
    }
  }
}
```

---

## GET /study-notes 🔵

**信頼性**: 🔵 *REQ-ASN-023・設計ヒアリングより*

**関連要件**: REQ-ASN-023, REQ-ASN-103, NFR-ASN-002

**説明**: キャッシュされた要約ノートを取得。キャッシュが存在しない場合は `null` を返す。

### クエリパラメータ

| パラメータ | 型 | 必須 | 制約 | 信頼性 |
|-----------|-----|------|------|--------|
| `source_type` | String | Yes | `"deck"` or `"tag"` | 🔵 |
| `source_id` | String | Yes | デッキID（UUID）またはタグ名 | 🔵 |

### リクエスト例

```
GET /study-notes?source_type=deck&source_id=deck-uuid-1234
```

### レスポンス（キャッシュヒット — 200 OK）

```json
{
  "success": true,
  "data": {
    "source_type": "deck",
    "source_id": "deck-uuid-1234",
    "content": "## 全体像\n\n...",
    "card_count": 25,
    "is_stale": false,
    "model_used": "anthropic.claude-3-sonnet-20240229-v1:0",
    "processing_time_ms": 8500,
    "generated_at": "2026-03-07T10:00:00Z"
  }
}
```

### レスポンス（キャッシュ古い — 200 OK） 🟡

**信頼性**: 🟡 *REQ-ASN-103・UX設計として妥当な推測*

```json
{
  "success": true,
  "data": {
    "source_type": "deck",
    "source_id": "deck-uuid-1234",
    "content": "## 全体像\n\n...(古い内容)",
    "card_count": 20,
    "is_stale": true,
    "model_used": "anthropic.claude-3-sonnet-20240229-v1:0",
    "processing_time_ms": 7200,
    "generated_at": "2026-03-05T10:00:00Z"
  }
}
```

### レスポンス（キャッシュなし — 200 OK）

```json
{
  "success": true,
  "data": null
}
```

### エラーコード

| HTTPステータス | コード | 条件 | 信頼性 |
|---------------|--------|------|--------|
| 400 | `VALIDATION_ERROR` | source_type/source_id が不正 | 🔵 |
| 401 | `UNAUTHORIZED` | 認証なし | 🔵 |

---

## 既存エンドポイントへの影響 🔵

**信頼性**: 🔵 *設計ヒアリング「同期的フラグ更新」選択より*

以下の既存エンドポイントに、キャッシュ無効化のサイドエフェクトが追加されます:

| エンドポイント | 追加処理 | 信頼性 |
|---------------|---------|--------|
| `POST /cards` | カード作成後、`deck_id`/`tags` の study-notes キャッシュを `is_stale=true` に更新 | 🔵 |
| `PUT /cards/:card_id` | カード更新後、`deck_id`/`tags` の study-notes キャッシュを `is_stale=true` に更新。deck_id/tags変更時は旧値のキャッシュも無効化 | 🔵 |
| `DELETE /cards/:card_id` | カード削除後、`deck_id`/`tags` の study-notes キャッシュを `is_stale=true` に更新 | 🔵 |

---

## 関連文書

- **アーキテクチャ**: [architecture.md](architecture.md)
- **データフロー**: [dataflow.md](dataflow.md)
- **DBスキーマ**: [database-schema.md](database-schema.md)
- **既存API仕様**: [../memoru-liff/api-endpoints.md](../memoru-liff/api-endpoints.md)
- **要件定義**: [requirements.md](../../spec/auto-study-notes/requirements.md)

---

## 信頼性レベルサマリー

| レベル | 件数 | 割合 |
|--------|------|------|
| 🔵 青信号 | 16件 | 84% |
| 🟡 黄信号 | 3件 | 16% |
| 🔴 赤信号 | 0件 | 0% |

**品質評価**: ✅ 高品質（青信号が84%、赤信号なし）

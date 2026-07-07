# AI 非同期ジョブ基盤 — API 契約

## 共通: ジョブ submit レスポンス（全 AI エンドポイント）

既存パス・既存リクエストボディは維持し、レスポンスのみ変更する。

```
POST /cards/generate          (既存ボディ: GenerateCardsRequest)
POST /cards/generate-from-url (既存ボディ: GenerateFromUrlRequest)
POST /cards/refine            (既存ボディ: RefineCardRequest)
POST /reviews/{cardId}/grade-ai (既存ボディ: GradeAnswerRequest)
POST /advice?language=ja      (GET から変更。ボディなし)
POST /tutor/sessions          (既存ボディ: StartSessionRequest)
POST /tutor/sessions/{sessionId}/messages (既存ボディ: SendMessageRequest)

→ 202 Accepted
{
  "job_id": "aijob_7f9c...",
  "job_type": "generate",
  "status": "queued"
}
```

同期のまま返すエラー（従来どおり）:

| ステータス | 条件 |
|---|---|
| 400 | Pydantic バリデーション / URL バリデーション（SSRF）/ 空デッキ |
| 401 | 認証エラー |
| 404 | grade_ai のカード不在 / tutor のセッション・デッキ不在 |
| 409 | tutor セッション ended・メッセージ上限 |
| 429 | ユーザー単位レート制限（#78、Retry-After 付き） |
| 501 | generate-from-url の profile_id 指定 |

## GET /ai-jobs/{jobId}

認証必須。ジョブ所有者以外・存在しない job_id は 404。

```
→ 200 OK (status: queued | processing)
{
  "job_id": "aijob_7f9c...",
  "job_type": "generate",
  "status": "processing",
  "created_at": "2026-07-07T12:00:00+00:00",
  "updated_at": "2026-07-07T12:00:01+00:00"
}

→ 200 OK (status: completed)
{
  "job_id": "...",
  "job_type": "generate",
  "status": "completed",
  "result": { ...現行同期レスポンスと同一スキーマ... },
  "created_at": "...",
  "updated_at": "..."
}

→ 200 OK (status: failed)
{
  "job_id": "...",
  "job_type": "generate",
  "status": "failed",
  "error": {
    "status": 504,                       // 現行 map_ai_error_to_http と同じ分類
    "code": "ai_timeout",                // ai_timeout | ai_rate_limit | ai_unavailable |
                                         // ai_error | not_found | conflict | internal
    "message": "AI service timeout"
  },
  "created_at": "...",
  "updated_at": "..."
}

→ 404 Not Found（存在しない / 他ユーザーのジョブ / TTL 失効後）
{ "error": "Job not found" }
```

## job_type 別 result スキーマ（現行同期レスポンスと同一）

| job_type | result の型（現行モデル） |
|---|---|
| `generate` | `GenerateCardsResponse` |
| `generate_from_url` | `GenerateFromUrlResponse`（duplicate_warning 含む） |
| `refine` | `RefineCardResponse` |
| `grade_ai` | `GradeAnswerResponse` |
| `advice` | `LearningAdviceResponse` |
| `tutor_start` | `TutorSessionResponse` |
| `tutor_message` | `SendMessageResponse` |

## エラーコード → フロントの扱い

フロントの `submitAndPollAiJob` は `failed` の `error.status` から `ApiError` を組み立てて
throw する。既存のエラー分類（`ApiError.status` による 504/429/503/400 分岐、
`getUserFacingMessage`）がそのまま機能する。

| error.code | error.status | 由来 |
|---|---|---|
| `ai_timeout` | 504 | AITimeoutError |
| `ai_rate_limit` | 429 | AIRateLimitError |
| `ai_unavailable` | 503 | AIProviderError / Tutor unavailable |
| `ai_error` | 500 | AIParseError ほか AIServiceError |
| `not_found` | 404 | ワーカー実行時点でカード等が消えていた |
| `conflict` | 409 | ConcurrentSendError / SessionEnded（ワーカー時点） |
| `internal` | 500 | 想定外例外 |

## ポーリング仕様（フロント）

- 間隔: 1.5 秒固定（inline モード・高速ジョブでは 1 回目で completed）
- 全体タイムアウト: 既存のフロー別定数を継続使用
  （生成 `MAX_GENERATION_TIME`、URL 生成 `MAX_URL_GENERATION_TIME`、
  Tutor `TUTOR_AI_TIMEOUT_MS`、refine `REFINE_AI_TIMEOUT_MS` 等）。
  呼び出し元が合成済み signal を渡し、abort でポーリングを停止する。
- 移行互換: submit レスポンスが 200（旧同期形式）の場合はそのまま結果として返す
  （フロント先行デプロイを可能にするデュアル対応）。

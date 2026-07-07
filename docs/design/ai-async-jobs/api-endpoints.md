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

同期のまま返すエラー（**現行のステータス・メッセージ文言を完全維持**）:

| ステータス | 条件 |
|---|---|
| 400 | Pydantic バリデーション / URL バリデーション（SSRF） |
| 401 | 認証エラー |
| 404 | grade_ai のカード不在 / tutor のセッション・デッキ不在 |
| 409 | tutor セッション ended / timed_out |
| 422 | tutor_start の空デッキ・レビュー不足（現行文言維持。フロントは 422+文言で UI を出し分ける） |
| 429 | ユーザー単位レート制限（#78、Retry-After 付き）/ tutor メッセージ上限（現行維持） |
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
    "status": 504,                       // 新設の classify_ai_job_error による分類
    "code": "ai_timeout",                // 下記コード表参照
    "message": "AI service timeout"      // 現行同期ハンドラーと同一文言
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
| `generate_from_url` | `GenerateFromUrlResponse`（重複警告は現行フィールド名 `warning`） |
| `refine` | `RefineCardResponse` |
| `grade_ai` | `GradeAnswerResponse` |
| `advice` | `LearningAdviceResponse`（`average_grade` 等の float は store で Decimal 変換） |
| `tutor_start` | `TutorSessionResponse` |
| `tutor_message` | `SendMessageResponse` |

## エラーコード → フロントの扱い

フロントの `submitAndPollAiJob` は `failed` の `error.status` / `error.message` から
`ApiError` を組み立てて throw する。既存のエラー分類（`ApiError.status` 分岐、
`getUserFacingMessage`、TutorContext の 422+文言判定）がそのまま機能するよう、
**status と message は現行同期ハンドラーの分類・文言と完全一致させる**。

分類は新設の共有関数 `classify_ai_job_error(exc)` に一元化する
（現行 `map_ai_error_to_http` は code を持たないため流用ではなく移設・拡張。
ai_handler の ContentFetchError 分岐もここへ移す）:

| error.code | error.status | 由来 |
|---|---|---|
| `ai_timeout` | 504 | AITimeoutError / TutorAITimeoutError |
| `ai_rate_limit` | 429 | AIRateLimitError |
| `ai_unavailable` | 503 | AIProviderError / Tutor unavailable (USE_STRANDS=false) |
| `ai_error` | 500 | AIParseError ほか AIServiceError |
| `content_fetch_timeout` | 408 | ContentFetchError（タイムアウト系。現行 ai_handler の分岐を移設） |
| `content_forbidden` | 403 | ContentFetchError（private/blocked 系） |
| `content_unsupported` | 422 | ContentFetchError（unsupported/meaningful 系）/ EmptyContentError / 生成 0 件 |
| `content_fetch_error` | 502 | ContentFetchError（その他） |
| `validation_error` | 422 | EmptyDeckError / InsufficientReviewDataError（ワーカー実行時。文言は現行と同一） |
| `message_limit` | 429 | MessageLimitError（ワーカー実行時。現行 429 を維持） |
| `not_found` | 404 | ワーカー実行時点でカード・セッション等が消えていた |
| `conflict` | 409 | ConcurrentSendError / SessionEndedError（ワーカー時点） |
| `internal` | 500 | 想定外例外 / 未知の schema_version |

## ポーリング仕様（フロント）

- 間隔: 1.5 秒固定（inline モード・高速ジョブでは 1 回目で completed）
- 全体タイムアウト: フロー別定数を使用。generate は 30s→**45s**、refine は 35s→**45s**、
  URL 生成は 90s→**150s** に引き上げ（heavy ジョブの処理想定上限 120s +
  キュー配信・コールドスタート・ポーリング粒度のオーバーヘッド。Tutor 90s は据え置き）。
  デッドラインは `submitAndPollAiJob` 内部で `createRequestSignal(timeoutMs, externalSignal)`
  により必ず合成する（外部 signal を渡さない tutor 系呼び出しでも打ち切りが効く）。
- 移行互換: submit レスポンスが **2xx かつ body に `job_id` フィールドがない**場合は
  旧同期形式としてそのまま結果を返す（ステータス数値に依存しない判定。
  tutor_start の現行 201 も安全に旧形式と判定される）。
- **デプロイ順序: フロント先行が必須**。デュアル対応が保護するのは
  「新フロント + 旧バックエンド」のみ。旧フロントは 202 ボディを成功として解釈し
  壊れるため、バックエンド先行デプロイは行わない。

# AI 非同期ジョブ基盤 — データフロー

## 正常系（SQS モード）

```
Frontend            Submit Lambda        AiJobsTable      AiJobQueue     Worker Lambda
   │ POST /cards/generate  │                  │               │               │
   │──────────────────────>│ 検証(400/401/429)│               │               │
   │                       │ PutItem queued ─>│               │               │
   │                       │ SendMessage ────────────────────>│               │
   │<── 202 {job_id} ──────│                  │               │──{job_id}────>│
   │                       │                  │<─ claim: queued→processing ───│
   │ GET /ai-jobs/{id}     │                  │               │  (条件付き更新)│
   │──────────────────────>│ GetItem ────────>│               │               │
   │<── 200 processing ────│                  │               │  AI 実行      │
   │  (1.5s 間隔で繰返し)   │                  │<─ completed + result ─────────│
   │ GET /ai-jobs/{id}     │                  │               │               │
   │──────────────────────>│ GetItem ────────>│               │               │
   │<── 200 completed ─────│                  │               │               │
```

## 正常系（inline モード / ローカル開発）

```
Frontend            Submit Lambda                AiJobsTable
   │ POST ────────────────>│ 検証                     │
   │                       │ PutItem queued ─────────>│
   │                       │ executor を同期実行       │
   │                       │ completed + result ─────>│
   │<── 202 {job_id} ──────│                          │
   │ GET /ai-jobs/{id} ───>│ GetItem（即 completed）──>│
   │<── 200 completed ─────│                          │
```

判定: `AI_JOB_WORKER_MODE == "inline"` または `AI_JOB_QUEUE_URL` 未設定 → inline。
（`webhook/line_actions._should_enqueue` と同じ規約。）

## ワーカーの状態遷移と再試行

```
                    ┌──────────────────────────────────────────┐
                    │  SQS 受信 {job_id}                        │
                    └──────────────┬───────────────────────────┘
                                   ▼
     claim: UpdateItem status=processing
     Condition: #st = queued OR (#st = processing AND updated_at < now-180s)
                    ┌── 条件不成立（completed/failed/フレッシュ processing）
                    │        → スキップ（重複配信の吸収。成功扱い）
                    ▼
              executor 実行 (job_type 別)
                    │
        ┌───────────┼──────────────────────────────┐
        ▼           ▼                              ▼
     成功        AI/ドメインエラー               インフラ起因の想定外例外
  completed     (AIServiceError,               （DynamoDB 障害等で status
  + result       SessionEnded 等)                更新に失敗した場合を含む）
  を書込        → failed + error を書込          → release（processing→queued、
  （リトライ     （リトライしない。SQS 上は        ベストエフォート）
   しない）       成功扱いで削除）                → batchItemFailures に積み
                                                  SQS リトライ（最大3回）→ DLQ
```

**設計判断: AI エラーを SQS リトライしない理由**

- ユーザーはフロントの既存タイムアウト（30〜90 秒）内でポーリング待機しており、
  SQS の可視性タイムアウトを挟む自動再試行はその予算内に収まらない
- 失敗時の自動再試行は Bedrock 課金を最大 3 倍にする
- 現行の同期 UX（即エラー表示 → ユーザーが再操作）との一貫性を保つ

**completed/failed の書き込み自体が失敗した場合**: ジョブは processing のまま残るが、
claim 条件の stale 判定（180 秒）により SQS 再配信時に再実行される。最終的に
maxReceiveCount 超過で DLQ へ。フロントはタイムアウトでエラー表示する。

## tutor_message の二重防御

```
submit 時（同期・fail-fast）        worker 時（権威）
├ セッション存在 → 404             ├ send_message() 内で再チェック
├ status ended → 409               ├ in-flight ロック取得（processing_started_at）
└ メッセージ上限 → 409             │   → 二重 submit は ConcurrentSendError → failed(409)
                                   └ ended 競合は complete_send の status=active 条件で
                                     終了済みセッションへの書込みを防止（レビュー #9 対応済み）
```

## ジョブレコードのライフサイクル

```
作成 (queued) → 処理 (processing) → 終了 (completed | failed)
                                        │
                                        └ TTL 24h で自動削除
```

- ポーリング側のタイムアウト・画面離脱はジョブに影響しない（キャンセル API は設けない。
  ワーカーは完走し、結果は TTL まで参照可能）
- TTL 失効後の GET は 404（フロントは既にタイムアウト表示済みのため実害なし）

## フロントエンドのフロー（サービス層内部）

```
submitAndPollAiJob(submitFn, { signal }):
  1. res = submitFn()                    … 既存パスへ POST
  2. res.status == 200 → return res      … 旧同期形式（移行互換）
  3. res.status == 202 → job_id 取得
  4. loop（signal.aborted まで）:
       1.5s 待機 → GET /ai-jobs/{job_id}
       - completed → return result
       - failed    → throw ApiError(error.status, error.message)
       - queued/processing → 継続
  5. signal abort → AbortError/TimeoutError を従来どおり伝播
     （呼び出し元の既存エラーハンドリングが機能する）
```

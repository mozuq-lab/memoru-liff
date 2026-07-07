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

判定: `AI_JOB_WORKER_MODE == "inline"` または対象キューの URL 未設定 → inline。
（`webhook/line_actions._should_enqueue` と同じ規約。）

## ワーカーの状態遷移と再試行

**設計原則: executor（Bedrock 呼び出し）の実行前と実行後で失敗の扱いを分ける。**
実行後の再実行は tutor の履歴二重追加・message_count 二重加算・二重課金を招くため厳禁
（設計レビュー C-2）。

```
                    ┌──────────────────────────────────────────┐
                    │  SQS 受信 {job_id}                        │
                    └──────────────┬───────────────────────────┘
                                   ▼
  【Phase A: claim（executor 未実行 → 再試行安全）】
     UpdateItem status=processing
     Condition: #st = queued OR (#st = processing AND updated_at < now-240s)
       ※ stale 240s > ワーカー Timeout 180s（安全マージン。レビュー H-1）
                    ┌── 条件不成立 → スキップ（重複配信の吸収。成功扱い）
                    ├── DynamoDB エラー → raise → batchItemFailures
                    │     → SQS リトライ（executor 未実行なので安全）
                    ▼
  【Phase B: executor 実行 (job_type 別)】
                    │
        ┌───────────┴───────────────┐
        ▼                           ▼
     成功                     AI/ドメインエラー（classify_ai_job_error で分類）
        │                           │
        ▼                           ▼
  【Phase C: 結果記録（executor 実行済み → 再実行厳禁）】
   completed + result 書込      failed + error 書込
   （いずれもリトライしない。SQS 上は成功扱いで削除）
        │
        └─ 書き込み失敗時: 同一実行内で短いバックオフ付き再試行（最大3回）
           → それでも失敗: release しない・batchItemFailures にも積まない
             （ジョブは processing のまま TTL で朽ちる。フロントはタイムアウト表示。
              再実行による二重課金・データ破損より安全側に倒す）
```

**設計判断: AI エラーを SQS リトライしない理由**

- ユーザーはフロントのフロー別タイムアウト（45〜150 秒。architecture.md §9 参照）内でポーリング待機しており、
  SQS の可視性タイムアウトを挟む自動再試行はその予算内に収まらない
- 失敗時の自動再試行は Bedrock 課金を最大 3 倍にする
- 現行の同期 UX（即エラー表示 → ユーザーが再操作）との一貫性を保つ

**Lambda ハードタイムアウト（Phase B 中の強制終了）**: メッセージは削除されず再配信され、
stale 再 claim で再実行されうる。interactive キューは AI 内部タイムアウト（30/60s）が
ワーカー Timeout 180s より十分内側のため実質発生しない。heavy キュー
（generate_from_url）は maxReceiveCount=1 のため再実行されず DLQ へ
（回避したかった 3× 課金経路の遮断。レビュー H-5）。

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
submitAndPollAiJob(submit, { timeoutMs, signal, pollIntervalMs = 1500 }):
  0. deadline = createRequestSignal(timeoutMs ?? 既定, signal)
     … 全体デッドラインをヘルパー内部で必ず合成（tutor 系は signal を渡さないため。
       レビュー H-3）
  1. { status, body } = submit()          … 既存パスへ POST（status 可視の低レベル呼び出し）
  2. 2xx かつ body.job_id なし → return body   … 旧同期形式（201 含む。レビュー H-2/H-5）
  3. 2xx かつ body.job_id あり → ポーリングへ
  4. loop（deadline.aborted まで）:
       1.5s 待機 → GET /ai-jobs/{job_id}（個々の GET は timeoutMs: 10_000）
       - completed → return result
       - failed    → throw ApiError(error.status, error.message)
       - queued/processing → 継続
  5. deadline 超過 → AbortError/TimeoutError を従来どおり伝播
     （呼び出し元の既存エラーハンドリングが機能する）
```

**デプロイ順序**: フロント先行が必須（旧フロントは 202 ボディを成功として解釈するため、
バックエンド先行では UI が静かに壊れる。レビュー H-3）。

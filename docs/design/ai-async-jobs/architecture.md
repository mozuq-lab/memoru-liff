# AI 非同期ジョブ基盤 (ai-async-jobs) — アーキテクチャ設計

## 背景と目的

API Gateway HTTP API の統合タイムアウトは **30 秒固定（引き上げ不可）** である一方、
AI 系エンドポイントの内部タイムアウトは 30〜120 秒に設定されており、AI 応答が 30 秒を
超えるたびに API Gateway 自体が 504 を返す（コードレビュー指摘 #3）。

- Lambda はバックグラウンドで処理を継続するため「クライアントは失敗・サーバーは成功」
  というデータ不整合が発生しうる
- フロントのタイムアウト延長（a85748d）では API Gateway の 30 秒上限は回避できない
- REST API (v1) への移行は HTTP API ネイティブ JWT オーソライザーを失うため不採用

**方針: AI 系 REST エンドポイントをすべて SQS 非同期ジョブパターンに統一する。**
受付（submit）は検証とジョブ登録のみを行って `202 Accepted` + `job_id` を即返し、
実際の AI 処理は SQS ワーカーが実行、フロントはポーリングで結果を取得する。

LINE Webhook の URL カード生成フロー（N-5: `UrlGenerateQueue` + LINE push 通知）は
既に非同期であり、通知セマンティクスが異なるため**現状維持**とする（統合は将来課題）。

## 対象エンドポイント

| # | エンドポイント | 現行 Lambda (Timeout) | job_type |
|---|---|---|---|
| 1 | POST /cards/generate | ApiFunction (120s) | `generate` |
| 2 | POST /cards/generate-from-url | UrlGenerateFunction (120s) | `generate_from_url` |
| 3 | POST /cards/refine | ApiFunction (120s) | `refine` |
| 4 | POST /reviews/{cardId}/grade-ai | ReviewsGradeAiFunction (60s) | `grade_ai` |
| 5 | GET → **POST** /advice | AdviceFunction (60s) | `advice` |
| 6 | POST /tutor/sessions | ApiFunction | `tutor_start` |
| 7 | POST /tutor/sessions/{id}/messages | ApiFunction | `tutor_message` |

- /advice はジョブ作成（非冪等）になるため **POST に変更**する。フロントは自前のため追随可能。
- 変換後、専用 Lambda（ReviewsGradeAi / Advice / UrlGenerate）は受付のみの軽量処理になる。
  関数統合（ApiFunction への集約）はスコープ外の follow-up とし、本件では
  Timeout / MemorySize の縮小のみ行う。

## 全体構成

```
[LIFF Frontend]
   │ POST /cards/generate 等（既存パス・既存ボディ）
   ▼
[Submit ハンドラー]  … 同期検証（認証・バリデーション・レート制限・所有権）
   │ 1. AiJobsTable にジョブ登録 (status=queued, payload)
   │ 2. AiJobQueue へ {job_id} を enqueue
   ▼ 202 Accepted {job_id, status}
[Frontend]
   │ GET /ai-jobs/{job_id} を 1.5 秒間隔でポーリング（既存のフロー別タイムアウト内）
   ▼
[AiJobQueue (SQS)] ──→ [AiJobWorkerFunction]
                          │ 1. ジョブ claim (queued→processing 条件付き更新)
                          │ 2. job_type 別 executor 実行（既存サービス層を再利用）
                          │ 3. 結果/エラーを AiJobsTable へ書き込み (completed/failed)
                          ▼
                       [AiJobsTable (DynamoDB, TTL 24h)]
```

## コンポーネント設計

### 1. AiJobsTable (DynamoDB)

| 属性 | 型 | 説明 |
|---|---|---|
| `job_id` (PK) | S | `aijob_` + UUID |
| `user_id` | S | 所有者（ポーリング時の認可に使用） |
| `job_type` | S | 上記 7 種 |
| `status` | S | `queued` → `processing` → `completed` \| `failed` |
| `payload` | M | executor への入力（リクエストボディ相当 + card_id 等のコンテキスト） |
| `result` | M | 成功時のみ。**現行同期レスポンスと同一スキーマ**（フロントの型を再利用） |
| `error` | M | 失敗時のみ。`{status: int, code: str, message: str}`（map_ai_error_to_http と同じ分類） |
| `created_at` / `updated_at` | S | ISO 8601 UTC |
| `ttl` | N | created_at + 24h（使い捨てデータのため DeletionPolicy: Retain は付けない） |

- GSI なし（クライアントは job_id を保持してポーリングするだけ）。
- 生成結果は最大でもカード 10 枚程度の JSON であり 400KB 制限に対して十分小さい。
- アクセス層は `services/ai_job_store.py` に集約（`get_dynamodb_resource` 経由・DI 対応）。

### 2. AiJobQueue / AiJobDLQ (SQS)

- Standard キュー。メッセージは `{"job_id": "..."}` のみ（ペイロードはテーブルが正）。
- `RedrivePolicy.maxReceiveCount: 3`、`VisibilityTimeout: 270`（ワーカー Timeout 180 の 1.5 倍。
  UrlGenerateQueue の既存比率を踏襲）。
- ESM: `BatchSize: 5` / `FunctionResponseTypes: [ReportBatchItemFailures]` /
  `ScalingConfig.MaximumConcurrency: 5`（Bedrock 同時呼び出しの抑制。
  ユーザー単位の流量は既存のレート制限 #78 が submit 時に抑止済み）。

### 3. AiJobWorkerFunction (Lambda)

- `jobs/ai_job_worker_handler.py`。Timeout 180s / MemorySize 512 / 予約同時実行なし
  （SQS の MaximumConcurrency で制御）。
- `url_generate_worker_handler` と同じ部分バッチ失敗（batchItemFailures）方式。
- job_type → executor のディスパッチテーブル。executor は既存サービス層を薄く呼ぶだけ:
  - `generate` → `create_ai_service().generate_cards(...)`
  - `generate_from_url` → `fetch_and_generate_cards(...)`（重複 URL 警告もワーカーで算出し result に含める）
  - `refine` → `create_ai_service().refine_card(...)`
  - `grade_ai` → `card_service.get_card` + `grade_answer`（カードが submit 後に削除された場合は failed(404) ）
  - `advice` → `get_review_summary(user_timezone 配線込み)` + `get_learning_advice`
  - `tutor_start` → `tutor_service.start_session(...)`
  - `tutor_message` → `tutor_service.send_message(...)`（in-flight ロック・#9 の ended 競合対策はそのまま有効）

### 4. 冪等性と再試行の設計

ジョブレコード自体を claim に使う（webhook_idempotency の別レコードは不要）:

1. **claim**: `status=queued → processing` の条件付き更新
   （`ConditionExpression: #st = :queued OR (#st = :processing AND updated_at < :stale)`。
   stale 閾値 = ワーカー Timeout と同じ 180 秒。processing のままワーカーが死んだ場合の再 claim を許可）。
   条件不成立（completed/failed/フレッシュな processing）はスキップ＝重複配信の吸収。
2. **AI 系エラー（AIServiceError / Tutor 系例外）は SQS リトライしない**。
   即 `failed` + error を書き込み、成功扱いで確定する。
   - 理由: ユーザーはフロントの既存タイムアウト（30〜90 秒）内で待機しており、
     SQS の再試行を待つより「即エラー表示 → ユーザーが再実行」の方が現行 UX と一致する。
     また自動リトライは失敗時の Bedrock 課金を最大 3 倍にする。
3. **インフラ起因の失敗**（ジョブレコード読み書きの DynamoDB エラー・想定外例外で
   status を更新できなかった場合）のみ release（processing→queued に戻す。ベストエフォート）
   して batchItemFailures → SQS リトライ / DLQ。
4. ポーリング側のタイムアウト（フロント）はジョブを取り消さない。ワーカーは完走し
   結果はテーブルに残る（TTL 24h）。「クライアント失敗・サーバー成功」の不整合は、
   ユーザーが再ポーリング／再操作した際に既存の冪等機構（tutor の in-flight ロック等）で
   吸収される。

### 5. Submit 時の同期検証（fail-fast）

4xx 系は従来どおり submit 時に同期で返す（ジョブ化しない）:

- 認証 401 / リクエストボディ 400（Pydantic）/ レート制限 429（#78 の check_ai_rate_limit）
- `grade_ai`: カード存在＋所有権 404
- `tutor_message`: セッション存在 404・ended/timed_out 409・メッセージ上限 409
  （**授権チェックのみ**。in-flight ロック取得と最終的な状態遷移はワーカー内の
  `send_message` が引き続き権威を持つ。二重 submit はワーカーで ConcurrentSendError
  → failed(409) になる）
- `tutor_start`: デッキ存在 404・空デッキ 400
- `generate_from_url`: URL バリデーション（SSRF 対策 validate_url）400 / profile_id 501

### 6. ローカル開発（inline モード）

既存 `URL_WORKER_MODE=inline` パターンを踏襲する:

- `AI_JOB_WORKER_MODE=inline` または `AI_JOB_QUEUE_URL` 未設定時、submit ハンドラーが
  ジョブ登録後に**その場で executor を同期実行**して結果を書き込み、その後 202 を返す。
- フロントは常にポーリングするため、inline では 1 回目の GET で completed が返る。
  フロント側の分岐は不要（本番と同一コードパス）。
- LocalStack を導入する場合も `AWS_ENDPOINT_URL` の既存配線で SQS/DynamoDB とも
  同一エンドポイントに解決される（コード変更不要）。

### 7. レート制限との関係（#78）

- submit エンドポイントで従来どおり `check_ai_rate_limit` を適用（AI 実行 1 回 = ジョブ 1 件）。
- GET /ai-jobs/{id} は軽量な DynamoDB GetItem のみでありレート制限対象外。

### 8. タイムアウト予算の整合（本件で 30 秒問題が解消される根拠）

| 区間 | 上限 | 変換後の所要 |
|---|---|---|
| submit（API GW 経由） | 30s | 検証 + PutItem + SendMessage ≈ 数百 ms |
| poll（API GW 経由） | 30s | GetItem ≈ 数十 ms |
| ワーカー（API GW を経由しない） | Lambda 180s | AI 呼び出し 30〜120s（既存の AI_AGENT_TIMEOUT_* が内側で有効） |

- `TUTOR_AI_AGENT_TIMEOUT_SECONDS=60` はワーカー内で完走可能になる（現行は API GW が 30 秒で切断）。
- 専用 Lambda（ReviewsGradeAi / Advice / UrlGenerate）は Timeout 15s / MemorySize 256 に縮小。

## フロントエンド設計

**呼び出し側コンポーネント・フックを無変更に保つ**ため、API サービス層の内部実装のみを差し替える:

- `api.ts` に `submitAndPollAiJob<T>(submitFn, {signal, pollIntervalMs})` を追加:
  1. submit を実行。**レスポンスが 202 + job_id ならポーリング、200 なら従来の同期
     レスポンスとしてそのまま返す**（デュアル対応。バックエンド先行デプロイ時に旧フロントが
     壊れないよう、フロント先行デプロイを可能にする移行戦略）。
  2. `GET /ai-jobs/{job_id}` を 1.5 秒間隔でポーリング。`completed` → result を返す。
     `failed` → error.status/code から `ApiError` を組み立てて throw（既存のエラー分類・
     表示ロジックがそのまま機能する）。
  3. 呼び出し元から渡される signal（既存の `MAX_GENERATION_TIME` / `TUTOR_AI_TIMEOUT_MS` 等の
     タイムアウト合成済み signal）で中断可能。ポーリングの個々の GET は `timeoutMs: 10_000`。
- 差し替え対象: `aiApi.generateCards` / `generateFromUrl` / `refineCard`、
  `reviewsApi.gradeAnswer`、`adviceApi.getAdvice`（POST 化）、
  `tutorApi.startSession` / `sendMessage`。
- ポーリング全体のタイムアウトは既存定数を継続使用（延長しない）。

## セキュリティ

- GET /ai-jobs/{id}: JWT の user_id とジョブの user_id が一致しない場合は **404**
  （403 だと job_id の存在が推測可能になるため。既存 IDOR 対策方針と同じ）。
- job_id は UUIDv4 由来で推測不能。payload/result にはユーザー自身の入力・生成物のみが入る。
- ワーカーの IAM は AiJobsTable / 既存テーブル群 / Bedrock（inference profile 限定）のみ。

## スコープ外（follow-up として記録）

1. 専用 Lambda 3 関数の ApiFunction への統合（受付軽量化後のコスト削減）
2. LINE Webhook URL 生成フローの AiJobQueue への統合
3. Tutor のレスポンスストリーミング化（Lambda Function URL。ポーリング UX で不足が出た場合）
4. DLQ 滞留の CloudWatch Alarm（既存 follow-up と合わせて対応）
5. WebSocket / Server-Sent Events による push 型の完了通知

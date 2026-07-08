# AI 非同期ジョブ基盤 (ai-async-jobs) — アーキテクチャ設計

> v1.1: 設計レビュー（アーキテクチャ視点 / 整合性・セキュリティ視点の2系統）の指摘を反映。
> 反映内容の対応表は design-review.md を参照。

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

| # | エンドポイント | 現行 Lambda | job_type | キュー | フロント消費者 |
|---|---|---|---|---|---|
| 1 | POST /cards/generate | ApiFunction | `generate` | interactive | useCardGeneration |
| 2 | POST /cards/generate-from-url | UrlGenerateFunction | `generate_from_url` | **heavy** | useCardGeneration |
| 3 | POST /cards/refine | ApiFunction | `refine` | interactive | CardForm |
| 4 | POST /reviews/{cardId}/grade-ai | ReviewsGradeAiFunction | `grade_ai` | interactive | **なし**（未使用） |
| 5 | GET → **POST** /advice | AdviceFunction | `advice` | interactive | **なし**（未使用） |
| 6 | POST /tutor/sessions | ApiFunction | `tutor_start` | interactive | TutorContext |
| 7 | POST /tutor/sessions/{id}/messages | ApiFunction | `tutor_message` | interactive | TutorContext |

- grade_ai / advice は**フロント未使用**（grep 確認済み）のため、バックエンドのみの変更で
  デュアル互換対応は不要。/advice の GET → POST 変更も追随作業なし。将来フロントに
  組み込む際は本基盤のポーリング方式を最初から使う。
- 専用 Lambda 3 関数（ReviewsGradeAi / Advice / UrlGenerate）の **Timeout 縮小は行わない**
  （inline モードでは submit ハンドラーが AI を同期実行するため矛盾する。レビュー M-2/H-6）。
  関数統合と Timeout 最適化は follow-up。

## 全体構成

```
[LIFF Frontend]
   │ POST /cards/generate 等（既存パス・既存ボディ）
   ▼
[Submit ハンドラー]  … 同期検証（認証・バリデーション・レート制限・所有権・422系）
   │ 1. AiJobsTable にジョブ登録 (status=queued, payload, schema_version)
   │ 2. job_type に応じたキューへ {job_id} を enqueue
   ▼ 202 Accepted {job_id, job_type, status}
[Frontend]
   │ GET /ai-jobs/{job_id} を 1.5 秒間隔でポーリング（フロー別タイムアウト内）
   ▼
[AiJobQueue (interactive)] ──┐
[AiJobHeavyQueue (heavy)] ───┴─→ [AiJobWorkerFunction]
                                   │ 1. claim (queued→processing 条件付き更新)
                                   │ 2. job_type 別 executor 実行（既存サービス層を再利用）
                                   │ 3. 結果/エラーを書き込み (completed/failed)
                                   ▼
                                [AiJobsTable (DynamoDB, TTL 24h)]
```

## コンポーネント設計

### 1. AiJobsTable (DynamoDB)

| 属性 | 型 | 説明 |
|---|---|---|
| `job_id` (PK) | S | `aijob_` + UUIDv4 |
| `user_id` | S | 所有者（ポーリング時の認可に使用） |
| `job_type` | S | 上記 7 種 |
| `status` | S | `queued` → `processing` → `completed` \| `failed` |
| `schema_version` | N | payload スキーマ版（現行 1）。ワーカーは未知版を failed(internal) にする |
| `payload` | M | executor への入力（リクエストボディ相当 + card_id 等のコンテキスト） |
| `result` | M | 成功時のみ。**現行同期レスポンスと同一スキーマ**（フロントの型を再利用） |
| `error` | M | 失敗時のみ。`{status: int, code: str, message: str}` |
| `created_at` / `updated_at` | S | ISO 8601 UTC |
| `ttl` | N | created_at + 24h（使い捨てデータのため DeletionPolicy: Retain は付けない） |

- GSI なし（クライアントは job_id を保持してポーリングするだけ）。
- 生成結果は最大でもカード 10 枚程度の JSON であり 400KB 制限に対して十分小さい。
- アクセス層は `services/ai_job_store.py` に集約（`get_dynamodb_resource` 経由・DI 対応）。
- **Decimal 変換（レビュー C-1 対応・必須要件）**: result には float が混入する
  （例: advice の `study_stats.average_grade`）。boto3 リソースは float を受け付けないため、
  store の書き込み側で `json.loads(json.dumps(x), parse_float=Decimal)` により再帰変換し、
  読み出し側で Decimal → int/float に逆変換してから JSON レスポンス化する。
  float を含む result のユニットテストを必須とする。

### 2. SQS キュー（2 本 + 各 DLQ）

処理時間プロファイルが異なるジョブを混在させると、重いジョブが軽いジョブの
レイテンシ・リトライ勘定を汚染するため（レビュー C-1/H-4/H-5）、2 本に分離する。

| | AiJobQueue (interactive) | AiJobHeavyQueue (heavy) |
|---|---|---|
| 対象 job_type | generate / refine / grade_ai / advice / tutor_start / tutor_message | generate_from_url |
| 想定処理時間 | 〜60s（AI_AGENT_TIMEOUT 30s / TUTOR 60s） | 〜120s（fetch + 複数 chunk × Bedrock） |
| BatchSize | **1**（既存 UrlGenerateQueue の設計判断を踏襲。バッチ内タイムアウトの巻き込みによる不当な DLQ 送りを防ぐ） | **1** |
| MaximumConcurrency | 5 | 2（既存 UrlGenerateQueue と同値） |
| maxReceiveCount | 3 | **1**（再試行しない。Lambda ハードタイムアウト経由の再実行で AI を丸ごとやり直す 3× 課金経路を遮断。レビュー H-5） |
| VisibilityTimeout | 270（ワーカー Timeout 180 × 1.5。既存比率踏襲） | 270 |
| DLQ | AiJobDLQ | AiJobHeavyDLQ |

- メッセージは `{"job_id": "..."}` のみ（ペイロードはテーブルが正）。
- **heavy キューの maxReceiveCount=1 の意図的トレードオフ**: Phase A（claim 前）の
  一時的な DynamoDB エラーに対しても再試行猶予がゼロになり、executor 未実行のまま
  即 DLQ 行きになる。発生確率は極めて低く（PAY_PER_REQUEST のスロットリングは稀）、
  Phase B 後の 3× 課金防止を優先する（実装レビュー #4 で明文化）。
- **DLQ 滞留の CloudWatch Alarm を本件スコープに含める**（レビュー M-4 で格上げ。
  ApproximateNumberOfMessagesVisible > 0。通知先 SNS の配線は follow-up とし、
  アラーム状態はコンソール/ダッシュボードで可視化する）。既存 2 DLQ 分も同時に追加する。

### 3. AiJobWorkerFunction (Lambda)

- `jobs/ai_job_worker_handler.py`。Timeout 180s / MemorySize 512 / 予約同時実行なし
  （SQS の MaximumConcurrency で制御）。両キューの ESM を同一関数に張る。
- `url_generate_worker_handler` と同じ部分バッチ失敗（batchItemFailures）方式。
- job_type → executor のディスパッチテーブル。executor は既存サービス層を呼ぶ:
  - `generate` → `create_ai_service().generate_cards(...)`
  - `generate_from_url` → `fetch_and_generate_cards(...)` + 重複 URL 警告
    （`find_cards_by_reference_url`）もワーカーで算出し result（`warning` フィールド）に含める
  - `refine` → `create_ai_service().refine_card(...)`
  - `grade_ai` → `card_service.get_card` + `grade_answer`（カードが submit 後に削除された場合は failed(404)）
  - `advice` → `get_review_summary(user_timezone 配線込み)` + `get_learning_advice`
  - `tutor_start` → `tutor_service.start_session(...)`
  - `tutor_message` → `tutor_service.send_message(...)`（in-flight ロック・#9 の ended 競合対策はそのまま有効）
- IAM: AiJobsTable CRUD + 既存テーブル群（Users/Cards/Reviews/Decks/TutorSessions）CRUD +
  Bedrock（inference profile 限定）+ AgentCore（条件付き）。
  submit 側の全関数（ApiFunction / ReviewsGradeAi / Advice / UrlGenerate）には
  AiJobsTable CRUD + 対象キューへの sqs:SendMessage を追加（レビュー M-4）。
- `GET /ai-jobs/{jobId}` は **ApiFunction** のルートとして実装する。

### 4. 冪等性と再試行の設計

ジョブレコード自体を claim に使う。**「executor 実行前」と「実行後」で失敗の扱いを
明確に区別する**（レビュー C-2 対応。実行後の再実行は tutor の履歴二重追加・
message_count 二重加算・Bedrock 二重課金を招くため厳禁）:

```
Phase A: claim（executor 未実行 → 再試行安全）
  UpdateItem status=processing
  Condition: #st = queued OR (#st = processing AND updated_at < now - 240s)
    ※ stale 閾値 240s > ワーカー Timeout 180s（webhook_idempotency の
      「stale 閾値は Lambda timeout を超える」原則を踏襲。レビュー H-1）
  - 条件不成立（completed/failed/フレッシュ processing）→ スキップ（重複配信の吸収）
  - DynamoDB エラー → raise → batchItemFailures → SQS リトライ（executor 未実行なので安全）

Phase B: executor 実行
  - AI/ドメインエラー → Phase C で failed + error を記録（SQS リトライしない）
  - Lambda ハードタイムアウト → 再配信 + stale 再 claim で再実行されうる。
    interactive キューは AI 内部タイムアウト（30/60s）≪ 180s のためこの経路は実質発生しない。
    heavy キューは maxReceiveCount=1 のため再実行されず DLQ へ（3× 課金の遮断）

Phase C: 結果記録（executor 実行済み → 再実行厳禁）
  - completed/failed の書き込み失敗時は同一 Lambda 実行内で短いバックオフ付き再試行（最大3回）
  - それでも失敗した場合は **release しない**・batchItemFailures にも積まない
    （メッセージは削除され、ジョブは processing のまま TTL で朽ちる。
     フロントはタイムアウト表示。再実行より安全側に倒す）
```

**AI 系エラーを SQS リトライしない理由**（維持）:
- ユーザーはフロントのフロー別タイムアウト（45〜150 秒。§9 参照）内でポーリング待機しており、
  SQS の再試行はその予算に収まらない
- 失敗時の自動リトライは Bedrock 課金を最大 3 倍にする
- 現行の同期 UX（即エラー表示 → ユーザーが再操作）との一貫性を保つ

**既知の制限（現行同期と同等）**: 別 job_id での二重 submit（多重クリック）はジョブ間の
dedup を持たない。tutor_message は in-flight ロックで片方が failed(409) になり、
generate 系は副作用がないため実害は二重課金のみ。claim が吸収するのは
「同一 job_id の SQS 重複配信」であることを明記する。

### 5. Submit 時の同期検証（fail-fast）

4xx 系は従来どおり submit 時に同期で返す（ジョブ化しない）。
**ステータスコードとメッセージ文言は現行実装と完全一致させる**
（フロント TutorContext は `status === 422` + メッセージ文言で UI を出し分けるため。レビュー C-3/H-1）:

| 対象 | 検証 | ステータス（現行維持） |
|---|---|---|
| 共通 | 認証 / Pydantic / レート制限 | 401 / 400 / 429 |
| grade_ai | カード存在＋所有権 | 404 |
| tutor_start | デッキ存在 | 404 |
| tutor_start | 空デッキ (`EmptyDeckError`) | **422**（現行文言維持） |
| tutor_start | レビュー不足 (`InsufficientReviewDataError`, weak_point) | **422**（現行文言維持） |
| tutor_message | セッション不在 / ended | 404 / 409 |
| tutor_message | メッセージ上限 (`MessageLimitError`) | **429**（現行維持。409 に変更しない） |
| generate_from_url | URL バリデーション（SSRF validate_url）/ profile_id | 400 / 501 |

- tutor_start の fail-fast には `TutorService` の検証ロジック分離が必要
  （`start_session` はデッキ取得〜AI 呼び出しが一体のため）。
  `TutorService.validate_start_session(user_id, deck_id, mode)` を新設し、
  submit とワーカー（`start_session` 内部）の双方から同一検証を通す（レビュー M-3）。
- 同じ例外がワーカー実行時に発生した場合も、下記 §6 のエラー分類で
  **同一の status / code / message** が failed ジョブに記録される。

### 6. ジョブエラー分類（classify_ai_job_error）

現行 `map_ai_error_to_http` は `{"error": ...}` のみで code を持たないため、
ジョブ用に **新設の共有分類関数** `classify_ai_job_error(exc) -> JobError{status, code, message}`
を `api/shared.py` 近傍に実装する（レビュー C-2/H-2/L-2）。
sync ハンドラーの分類（特に ai_handler の ContentFetchError → 408/403/422/502 分岐）を
この関数に**移設**し、sync 経路とワーカー経路で単一の分類を共有する。
コード表は api-endpoints.md を参照（422/408/403/502/429 を含む完全版）。

### 7. ローカル開発（inline モード）

既存 `URL_WORKER_MODE=inline` パターンを踏襲する:

- `AI_JOB_WORKER_MODE=inline` または対象キューの URL 未設定時、submit ハンドラーが
  ジョブ登録後に**その場で executor を同期実行**して結果を書き込み、その後 202 を返す。
- フロントは常にポーリングするため、inline では 1 回目の GET で completed が返る
  （本番と同一コードパス）。
- 専用 Lambda の Timeout を現状維持するのはこのため（inline では submit が AI を同期実行する）。
- LocalStack 導入時も `AWS_ENDPOINT_URL` の既存配線で SQS/DynamoDB とも解決される。

### 8. レート制限との関係（#78）

- submit エンドポイントで従来どおり `check_ai_rate_limit` を適用（AI 実行 1 回 = ジョブ 1 件）。
- GET /ai-jobs/{id} は軽量な GetItem のみでレート制限対象外。
  ポーリングは ApiFunction の Invocation を増やす（最大 ~60 回/ジョブ）ため、
  ReservedConcurrentExecutions(100) の消費を監視項目に加える（レビュー L-2）。

### 9. タイムアウト予算の整合

| 区間 | 上限 | 変換後の所要 |
|---|---|---|
| submit（API GW 経由） | 30s | 検証 + PutItem + SendMessage ≈ 数百 ms |
| poll（API GW 経由） | 30s | GetItem ≈ 数十 ms |
| ワーカー（API GW を経由しない） | Lambda 180s | AI 呼び出し 30〜120s（AI_AGENT_TIMEOUT_* が内側で有効） |

**フロント側のポーリング予算（レビュー M-3 対応）**: SQS 配信 + コールドスタート +
ポーリング粒度 1.5s のオーバーヘッドが上乗せされるため、バックエンド内部タイムアウトと
同値だった予算を引き上げる:

| フロー | 現行予算 | 変更後 |
|---|---|---|
| generate (`MAX_GENERATION_TIME`) | 30s | **45s** |
| refine (`REFINE_AI_TIMEOUT_MS`) | 35s | **45s** |
| generate_from_url (`MAX_URL_GENERATION_TIME`) | 90s | **150s**（heavy ジョブの処理想定上限 120s + オーバーヘッド 30s。ワーカー Timeout 180s の内側。PR #79 レビュー） |
| tutor (`TUTOR_AI_TIMEOUT_MS` 既定) | 90s | 90s（据え置き） |

## フロントエンド設計

**呼び出し側コンポーネント・フックを無変更に保つ**ため、API サービス層の内部のみを差し替える:

- `api.ts` に submit 用の低レベルヘルパー（HTTP ステータスとボディの両方を返す。
  現行 `request()` は 2xx で body しか返さないため新設が必要。レビュー H-3）と
  `submitAndPollAiJob<T>(submit, {timeoutMs?, signal?, pollIntervalMs?})` を追加:
  1. submit を実行。**2xx かつ body に `job_id` があればポーリング、
     それ以外の 2xx は旧同期形式としてそのまま返す**
     （ステータス数値の一致に依存しない判定。tutor_start の現行 201 も安全。レビュー H-2/H-5）。
  2. 全体デッドラインは**ヘルパー内部で必ず合成**する:
     `createRequestSignal(timeoutMs ?? DEFAULT, externalSignal)`。
     generate 系（外部 signal 方式）と tutor 系（timeoutMs 方式・signal なし）の
     両方の呼び出し規約を吸収する（レビュー H-3）。
  3. `GET /ai-jobs/{job_id}` を 1.5 秒間隔でポーリング（個々の GET は `timeoutMs: 10_000`）。
     `completed` → result を返す。`failed` → `error.status / message` から `ApiError` を
     組み立てて throw（既存のエラー分類・表示ロジックがそのまま機能する）。
  4. デッドライン超過 → 従来どおり TimeoutError / AbortError を伝播。
- 差し替え対象: `aiApi.generateCards` / `generateFromUrl` / `refineCard`、
  `tutorApi.startSession` / `sendMessage`。（grade_ai / advice はフロント未使用のため対象外）
- **デプロイ順序: フロント先行を必須とする**（レビュー H-3 (整合性)）。
  デュアル対応が保護するのは「新フロント + 旧バックエンド」のみであり、
  逆順（旧フロント + 新バックエンド）では旧フロントが 202 ボディを成功レスポンスとして
  解釈し UI が壊れる。リリース手順書に明記する。

## セキュリティ

- GET /ai-jobs/{id}: JWT の user_id とジョブの user_id が一致しない場合は **404**
  （403 だと job_id の存在が推測可能になるため。既存 IDOR 対策方針と同じ）。
- job_id は UUIDv4 由来で推測不能。payload/result にはユーザー自身の入力・生成物のみが入る。
- ワーカーの IAM は §3 記載の最小セット。

## スコープ外（follow-up として記録）

1. 専用 Lambda 3 関数の ApiFunction への統合と Timeout/Memory 最適化
2. LINE Webhook URL 生成フローの heavy キューへの統合
3. Tutor のレスポンスストリーミング化（Lambda Function URL。ポーリング UX で不足が出た場合）
4. DLQ アラームの SNS 通知配線（アラーム自体は本件で作成）
5. WebSocket / SSE による push 型の完了通知
6. ジョブ間 dedup（多重クリックの重複 submit 抑止。フロントの既存 isSubmitting ガードで実用上は抑止済み）

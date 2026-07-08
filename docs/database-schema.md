# Memoru LIFF — DynamoDB スキーマ（現行版）

**最終更新**: 2026-06-25
**ステータス**: ✅ 現行実装の正（`backend/template.yaml` および `backend/src/` 実装と突き合わせ済み）

> ⚠️ 旧資料 [`docs/design/memoru-liff/database-schema.md`](design/memoru-liff/database-schema.md) は
> 2026-01-05 の MVP 初期設計であり、現行実装と乖離しています（テーブル数・reviews の役割・SRS 状態の置き場所が異なる）。
> **最新の構造は本ドキュメントを参照してください。**

## このドキュメントの読み方（構造の「正」はどこにあるか）

DynamoDB の構造は 2 レベルに分かれており、それぞれ別ファイルが正となります。

| レベル | 内容 | 正となるファイル |
|--------|------|------------------|
| 物理スキーマ | テーブル名・キー・GSI・TTL・暗号化 | `backend/template.yaml` |
| 論理スキーマ | 各アイテムの属性（フィールド） | `backend/src/models/*.py` の `to_dynamodb_item` / `from_dynamodb_item`、および各リポジトリ |

本ドキュメントは上記 2 つを統合した一覧です。実装変更時は本ファイルも更新してください。

---

## データストア全体像

| データストア | 用途 | 備考 |
|-------------|------|------|
| **DynamoDB** | アプリの全データ | 本ドキュメントの対象。マルチテーブル設計 |
| Bedrock AgentCore Memory | AI チューターの会話履歴（**prod のみ**） | dev は DynamoDB(`tutor-sessions`)へフォールバック。`tutor_session_factory.py` で切替 |
| RDS PostgreSQL | Keycloak 認証基盤専用 | アプリコードからはアクセスしない（CDK `keycloak-stack.ts`）。Cognito 利用時は不要 |
| SQS | URL カード生成の非同期キュー / AI 非同期ジョブのキュー | DB ではない（`memoru-url-generate-*` / `memoru-ai-job-*` / `memoru-ai-job-heavy-*`） |
| S3 + CloudFront | LIFF フロント静的ホスティング | DB ではない（CDK `liff-hosting-stack.ts`） |

---

## テーブル一覧（コアデータ 7 + 運用 2 テーブル）

テーブル名はすべて `-${Environment}`（`dev` / `staging` / `prod`）サフィックス付き。

**コアデータテーブル（7）** — ドメインデータを保持し、Retain を持つ（PITR は `processed-events` を除く 6 テーブルのみ。詳細は下記[共通プロパティ](#コアデータテーブル共通プロパティ)）:

| # | テーブル | PK | SK | GSI | TTL | 用途 |
|---|---------|----|----|-----|-----|------|
| 1 | `memoru-users` | `user_id` | — | `line_user_id-index` | — | ユーザー・LINE 連携・設定 |
| 2 | `memoru-cards` | `user_id` | `card_id` | 3 本 | — | カード本体 + **SRS 状態** |
| 3 | `memoru-reviews` | `card_id` | `reviewed_at` | `user_id-reviewed_at-index` | — | 復習履歴ログ（**分析専用**） |
| 4 | `memoru-tutor-sessions` | `user_id` | `session_id` | `user_id-status-index` | `ttl` | チューターのセッションメタ |
| 5 | `memoru-decks` | `user_id` | `deck_id` | — | — | デッキ |
| 6 | `memoru-browser-profiles` | `user_id` | `profile_id` | — | — | ブラウザプロファイル（⚠️未実装） |
| 7 | `memoru-processed-events` | `webhook_event_id` | — | — | `expires_at` | 冪等管理 + 一時ストア（**3 用途を相乗り**） |

**運用テーブル（2）** — 使い捨ての一時データ。TTL で自動失効し、Retain / PITR は持たない:

| # | テーブル | PK | TTL | 用途 |
|---|---------|----|-----|------|
| 8 | `memoru-ai-jobs` | `job_id` | `ttl`（24h） | AI 非同期ジョブの状態・結果（ai-async-jobs、[§8](#8-memoru-ai-jobs) 参照） |
| 9 | `memoru-rate-limits` | `pk` | `ttl` | AI 系エンドポイントのユーザー単位レート制限カウンタ（固定ウィンドウ） |

### コアデータテーブル共通プロパティ

- `BillingMode: PAY_PER_REQUEST`（オンデマンド）
- `SSESpecification: KMS`（保管時暗号化）
- `PointInTimeRecoveryEnabled: true`（PITR）※ `processed-events` を除く
- `DeletionPolicy / UpdateReplacePolicy: Retain`
- `DeletionProtectionEnabled`: prod のみ true

> **運用テーブル（`ai-jobs` / `rate-limits`）の差異**: KMS 暗号化・PAY_PER_REQUEST は共通だが、
> 使い捨てデータのため **Retain / PITR / DeletionProtection は付けない**（TTL で自動削除）。
> `rate-limits` はローカルでは無効（`RATE_LIMITS_TABLE=""`）のため docker-compose では作成しない。
> `ai-jobs` は inline モードでもジョブレコードを保存するためローカルでも作成する。

---

## ⚠️ 重要な設計ポイント（旧資料との差分）

1. **SRS 状態は `cards` テーブルにある**（旧資料は `reviews` に置いていた）。
   `interval` / `ease_factor` / `repetitions` / `next_review_at` と、Undo・スケジューリングの**正（source of truth）である `review_history`** はすべて `cards` アイテムに保持。
2. **`reviews` テーブルは追記型の分析専用ログ**。キーは `card_id` + `reviewed_at`。
   ストリークやタグ別正答率の集計に使い、書き込みはベストエフォート（失敗してもユーザー影響なし）。Undo には使わない。
3. **`processed-events` は 1 テーブルを 3 用途で共用**。キー名前空間（生 ID / `URLCARDS#` / `URLGENWORK#`）で衝突を回避。

---

## 1. `memoru-users`

ユーザー情報・LINE 連携・各種設定。

**キー / インデックス**

| 種別 | 属性 | 型 | 備考 |
|------|------|----|------|
| PK | `user_id` | S | Keycloak / Cognito の `sub`（UUID） |
| GSI `line_user_id-index` | `line_user_id` | S | HASH のみ・Projection ALL。Webhook 時に LINE ID → user 特定 |

**属性**（`src/models/user.py`）

| 属性 | 型 | 必須 | 説明 |
|------|----|------|------|
| `user_id` | S | ✓ | PK |
| `line_user_id` | S | | GSI PK。LINE 連携時にセット |
| `display_name` | S | | |
| `picture_url` | S | | |
| `settings` | Map | ✓ | `{ notification_time: "HH:MM", timezone: IANA文字列, day_start_hour: 0-23 }` |
| `last_notified_date` | S | | `YYYY-MM-DD`。リマインダー重複送信防止 |
| `created_at` | S | ✓ | ISO 8601 |
| `updated_at` | S | | ISO 8601 |

**主なアクセスパターン**

- 認証後のユーザー取得: `GetItem(user_id)`
- Webhook 受信時: `Query(line_user_id-index)`
- リマインダー: `due_push_handler` が `last_notified_date` を `UpdateItem`

---

## 2. `memoru-cards`

カード本体に加え、**SRS（間隔反復）状態**を保持する中心テーブル。

**キー / インデックス**

| 種別 | 属性 | 型 | Projection | 用途 |
|------|------|----|-----------|------|
| PK | `user_id` | S | — | |
| SK | `card_id` | S | — | UUID |
| GSI `user_id-due-index` | `user_id`(H) / `next_review_at`(R) | S | ALL | 復習対象カード取得（`next_review_at <= now`） |
| GSI `deck-cards-index` | `deck_index_key`(H) / `next_review_at`(R) | S | KEYS_ONLY | デッキ別カウント。**スパース**（`deck_id` 無しは投影されない） |
| GSI `reference-url-index` | `reference_url_key`(H) | S | ALL | URL からの重複検出。**スパース** |

> `next_review_at` は ISO 8601 文字列。辞書順 = 時刻順のため範囲条件で due 判定可能。

**属性**（`src/models/card.py`、`review_history` は `card_repository.py` / `review_service.py`）

| 属性 | 型 | 必須 | 説明 |
|------|----|------|------|
| `user_id` | S | ✓ | PK |
| `card_id` | S | ✓ | SK |
| `front` | S | ✓ | 表面（問題） |
| `back` | S | ✓ | 裏面（答え） |
| `tags` | List(S) | ✓ | 最大 10・各 50 字 |
| `interval` | N | ✓ | 復習間隔（日） |
| `ease_factor` | **S** | ✓ | SM-2 係数。**float 非対応のため文字列で保存**（例 `"2.5"`） |
| `repetitions` | N | ✓ | 連続正解回数 |
| `created_at` | S | ✓ | ISO 8601 |
| `references` | List(Map) | | `[{ type: "url"\|"book"\|"note", value: S }]` 最大 5 |
| `reference_url_key` | S | | `"<user_id>#<url>"`。GSI 用・スパース |
| `deck_id` | S | | 所属デッキ |
| `deck_index_key` | S | | `"<user_id>#<deck_id>"`。GSI 用・スパース・永続化専用 |
| `next_review_at` | S | | ISO 8601。次回復習日時（GSI キー） |
| `updated_at` | S | | ISO 8601 |
| `review_history` | List(Map) | | **SRS / Undo の正**。下記参照。`list_append` で追記 |

**`review_history` エントリ**（`ReviewHistoryEntry`）

`reviewed_at`, `grade`, `ease_factor_before/after`, `interval_before/after`, `repetitions_before/after`, `next_review_at_before/after`

**主なアクセスパターン**

- カード一覧: `Query(user_id)`
- 復習対象: `Query(user_id-due-index, next_review_at <= now)`
- デッキ別枚数 / due 数: `Query(deck-cards-index, Select=COUNT)`
- URL 重複検出: `Query(reference-url-index)`
- レビュー確定: `next_review_at`/`interval`/`ease_factor`/`repetitions` 更新 + `review_history` 追記を 1 回の `UpdateItem`（CAS 条件付き）

---

## 3. `memoru-reviews`

復習の**追記型ログ**。集計・分析専用で、SRS の正ではない。

**キー / インデックス**

| 種別 | 属性 | 型 | 備考 |
|------|------|----|------|
| PK | `card_id` | S | |
| SK | `reviewed_at` | S | ISO 8601 |
| GSI `user_id-reviewed_at-index` | `user_id`(H) / `reviewed_at`(R) | S | Projection ALL。ユーザー全レビュー取得 |

**TTL なし**（統計用に永久保持。`expires_at` は書き込まれない）。

**属性**（`src/services/review_service.py` `_record_review`）

| 属性 | 型 | 説明 |
|------|----|------|
| `card_id` | S | PK |
| `reviewed_at` | S | SK・ISO 8601 |
| `user_id` | S | GSI PK |
| `grade` | N | 0–5 |
| `ease_factor_before` / `ease_factor_after` | S | 文字列保存 |
| `interval_before` / `interval_after` | N | |

**主なアクセスパターン**

- 学習サマリ（ストリーク・正答率等）: `Query(user_id-reviewed_at-index)` 全ページ取得 → 集計
- 書き込みはベストエフォート（`put_item` 失敗時もログのみで例外を出さない）

---

## 4. `memoru-tutor-sessions`

AI チューターのセッション**メタデータ**。

> 会話メッセージ本体は SessionManager が保存する：**prod = Bedrock AgentCore Memory** / **dev = DynamoDB**（`TUTOR_SESSION_BACKEND` で切替、`tutor_session_factory.py`）。本テーブルはメタデータ側。

**キー / インデックス**

| 種別 | 属性 | 型 | 備考 |
|------|------|----|------|
| PK | `user_id` | S | |
| SK | `session_id` | S | |
| GSI `user_id-status-index` | `user_id`(H) / `status`(R) | S | Projection ALL。状態別フィルタ |

**TTL**: `ttl`（有効）。`ended` / `timed_out` 遷移時にセット。

**属性**（`src/services/tutor_service.py` / `tutor_session_repository.py`）

| 属性 | 型 | 説明 |
|------|----|------|
| `user_id` | S | PK |
| `session_id` | S | SK |
| `deck_id` | S | 対象デッキ |
| `mode` | S | `free_talk` \| `quiz` \| `weak_point` |
| `status` | S | `active` \| `ended` \| `timed_out`（GSI SK） |
| `message_count` | N | |
| `created_at` / `updated_at` | S | ISO 8601 |
| `system_prompt` | S | |
| `deck_card_ids` | List(S) | コンテキスト用カード ID |
| `processing_started_at` | S | in-flight ロック（二重送信 / Bedrock 二重呼び出し防止）。完了時に REMOVE |
| `ended_at` | S | 終了日時 |
| `ttl` | N | TTL 属性 |

---

## 5. `memoru-decks`

デッキ（カードのグループ）。

**キー**: PK `user_id` / SK `deck_id`（UUID）。GSI・TTL なし。

**属性**（`src/models/deck.py`）

| 属性 | 型 | 必須 | 説明 |
|------|----|------|------|
| `user_id` | S | ✓ | PK |
| `deck_id` | S | ✓ | SK |
| `name` | S | ✓ | 最大 100 字 |
| `description` | S | | 最大 500 字 |
| `color` | S | | `#RRGGBB` |
| `created_at` | S | ✓ | ISO 8601 |
| `updated_at` | S | | ISO 8601 |

> `card_count` / `due_count` はデッキには保存せず、レスポンス時に `cards` テーブル（`deck-cards-index`）から集計する。

---

## 6. `memoru-browser-profiles`

認証付きページ取得用のブラウザプロファイル。

> ⚠️ **AgentCore Browser 統合は未実装**（`browser_service.py` はプレースホルダ）。現状ほぼ未使用。

**キー**: PK `user_id` / SK `profile_id`（`bp-<hex12>`）。GSI・TTL なし。

**属性**（`src/services/browser_profile_service.py`）

| 属性 | 型 | 説明 |
|------|----|------|
| `user_id` | S | PK |
| `profile_id` | S | SK |
| `name` | S | 表示名 |
| `created_at` | S | ISO 8601 |

---

## 7. `memoru-processed-events`

**3 つの用途で共用**する汎用テーブル。キー名前空間で衝突を回避。

**キー**: PK `webhook_event_id`（S）のみ。GSI なし。
**TTL**: `expires_at`（有効、いずれの用途も 24 時間）。

### 用途 A: LINE Webhook 冪等（`webhook_idempotency.py`）

キー = LINE の `webhookEventId`（生値）。二相クレーム（in_progress → processed）。

| 属性 | 型 | 説明 |
|------|----|------|
| `webhook_event_id` | S | PK（= LINE event id） |
| `status` | S | `in_progress` \| `processed` |
| `claimed_at` | N | unix 秒。stale 判定用（180 秒） |
| `expires_at` | N | unix 秒。TTL |

### 用途 B: URL カードプレビュー一時ストア（`url_cards_store.py`）

キー = `"URLCARDS#<uuid4>"`。LINE postback の 300 字制限を回避し、生成済みカードを ref で受け渡す。

| 属性 | 型 | 説明 |
|------|----|------|
| `webhook_event_id` | S | PK（= `URLCARDS#...`） |
| `cards` | S | カード配列の JSON 文字列 |
| `page_url` | S | 出典 URL |
| `page_title` | S | ページタイトル |
| `saved` | Bool | 二重保存防止フラグ |
| `expires_at` | N | unix 秒。TTL |

### 用途 C: URL 生成ワーカーの冪等クレーム（`jobs/url_generate_worker_handler.py`）

キー = `"URLGENWORK#<webhookEventId>"`。SQS ワーカー側の重複処理防止。

---

## 8. `memoru-ai-jobs`

AI 系 REST エンドポイントの非同期ジョブ（ai-async-jobs）。受付ハンドラーが `queued` で登録し、
SQS ワーカーが `claim`（`queued`→`processing` の条件付き更新）して実行、結果を書き込む。
ジョブレコード自体が SQS at-least-once 配信に対する冪等 claim を兼ねる。
実装: `src/services/ai_job_store.py`。

**キー**

| 種別 | 属性 | 型 | 備考 |
|------|------|----|------|
| PK | `job_id` | S | `aijob_` + UUIDv4 |

**属性**

| 属性 | 型 | 説明 |
|------|----|------|
| `job_id` | S | PK |
| `user_id` | S | 所有者。`GET /ai-jobs/{jobId}` の認可（不一致は 404） |
| `job_type` | S | `generate` / `generate_from_url` / `refine` / `grade_ai` / `advice` / `tutor_start` / `tutor_message` |
| `status` | S | `queued` → `processing` → `completed` \| `failed` |
| `schema_version` | N | payload スキーマ版（現行 1）。未知版は `failed(internal)` |
| `payload` | Map | executor 入力（リクエストボディ相当。float は Decimal 変換して保存） |
| `result` | Map | 成功時のみ。現行同期レスポンスと同一スキーマ |
| `error` | Map | 失敗時のみ。`{ status, code, message }`（現行同期ハンドラーと同一分類・文言） |
| `created_at` / `updated_at` | S | ISO 8601 |
| `ttl` | N | unix 秒。`created_at + 24h` |

> **設計上の注意**: `result` / `payload` は `float` を含みうる（例: advice の `average_grade`）。
> boto3 リソースは `float` 非対応のため、書き込み時に Decimal へ再帰変換し、読み出し時に逆変換する。
> claim の stale 閾値は 240 秒（ワーカー Timeout 180 秒より長い）。
> 詳細: [`docs/design/ai-async-jobs/architecture.md`](design/ai-async-jobs/architecture.md)。

---

## ER 図（概念）

```
                          ┌──────────────┐
                          │    users     │  PK: user_id
                          │              │  GSI: line_user_id-index
                          └──────┬───────┘
                                 │ 1
              ┌──────────────────┼──────────────────┐
              │ N                │ N                 │ N
       ┌──────▼──────┐    ┌──────▼──────┐     ┌──────▼──────────┐
       │    decks    │    │    cards    │     │ tutor-sessions  │
       │ PK user_id  │    │ PK user_id  │     │ PK user_id      │
       │ SK deck_id  │◄───┤ SK card_id  │     │ SK session_id   │
       └─────────────┘    │  + SRS状態  │     │ GSI status      │
              ▲           │  + review_  │     │ (会話本体は     │
              │ deck_id   │    history  │     │  AgentCore/DDB) │
              └───────────┤             │     └─────────────────┘
                          │ GSI: due /  │
                          │  deck /     │
                          │  ref-url    │
                          └──────┬──────┘
                                 │ card_id（追記ログ）
                          ┌──────▼──────────────────┐
                          │        reviews          │  PK: card_id
                          │  （分析専用・追記型）    │  SK: reviewed_at
                          │                         │  GSI: user_id-reviewed_at
                          └─────────────────────────┘

  browser-profiles（PK user_id / SK profile_id・⚠️未実装）
  processed-events（PK webhook_event_id・冪等 + URLCARDS# + URLGENWORK# 相乗り）

  ── 運用テーブル（他テーブルと FK 関係なし・TTL 失効） ──
  ai-jobs（PK job_id・AI 非同期ジョブの状態/結果・TTL 24h）
  rate-limits（PK pk・レート制限カウンタ・TTL）
```

---

## 参照

- 物理スキーマ: `backend/template.yaml`
- 論理スキーマ（属性）:
  - `backend/src/models/user.py` / `card.py` / `deck.py` / `tutor.py`
  - `backend/src/services/review_repository.py` / `review_service.py`（reviews, review_history）
  - `backend/src/services/tutor_session_repository.py` / `tutor_service.py`（tutor-sessions）
  - `backend/src/services/browser_profile_service.py`（browser-profiles）
  - `backend/src/services/webhook_idempotency.py` / `url_cards_store.py`（processed-events）
- チューター履歴バックエンド切替: `backend/src/services/tutor_session_factory.py`
- 旧 MVP 設計（歴史的参考）: `docs/design/memoru-liff/database-schema.md`

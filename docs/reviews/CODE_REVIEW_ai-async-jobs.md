# ai-async-jobs 実装レビュー記録 (2026-07-08)

feat/ai-async-jobs ブランチ（設計: docs/design/ai-async-jobs/）に対し、
バックエンド（Python/インフラ）とフロントエンド（React/TS）の2系統で実装レビューを実施。
設計レビュー記録は docs/design/ai-async-jobs/design-review.md を参照。

## 指摘と対応状況

### バックエンド

| # | Severity | 指摘 | 対応 |
|---|---|---|---|
| B-1 | HIGH | Router 系 submit ハンドラー（generate/generate-from-url/refine/tutor_start/tutor_message/ai-jobs GET）が submit・get_job のインフラ例外を保護しておらず、Lambda 未処理例外 → API Gateway 独自形式の 500 になる | **修正**: 全箇所に try/except を追加し、スタンドアロンハンドラーと同じ `{"error": ...}` 形式の統一 500 を返却。回帰テスト追加 |
| B-2 | MEDIUM | `validate_send_message` がタイムアウト検出時に `_mark_timed_out` を呼ばず、status=active・TTL 未設定のセッションが無期限残存しうる | **修正**: `send_message` と同じマーキング副作用を追加。回帰テスト追加 |
| B-3 | MEDIUM | Phase B の想定外例外（internal）が warning ログで埋もれ、ERROR ベース監視で検知不能 | **修正**: `error_code == "internal"` のみ logger.error に昇格 |
| B-4 | MEDIUM | heavy キュー maxReceiveCount=1 は Phase A（claim 前）の一時的 DynamoDB エラーにも再試行猶予ゼロ | **設計書に明記**（意図的トレードオフ。architecture.md §2） |
| B-5 | LOW | tutor 404/409 の文言が submit fail-fast とワーカー経由で微差（TOCTOU 時のみ表面化） | **記録のみ**（フロント分岐に影響なし） |
| B-6 | LOW | tutor_start は submit と worker で deck/cards を二重読み取り | **記録のみ**（二段階設計の必然的トレードオフ） |
| B-7 | LOW | キュー設定値（maxReceiveCount/VisibilityTimeout/MaximumConcurrency）の回帰テストなし | **修正**: test_template_routes.py に H-1/H-5 を担保する検証を追加 |
| B-8 | LOW | Decimal→int 変換で整数値の float フィールドが JSON 上 int になる | **記録のみ**（JSON は型を区別せず実害なし） |

### フロントエンド

| # | Severity | 指摘 | 対応 |
|---|---|---|---|
| F-1 | HIGH | ポーリング GET の単発失敗（ネットワーク瞬断・個別タイムアウト・5xx）で全体が即失敗する（1ジョブ最大60回 GET のためモバイル網で顕在化しやすい） | **修正**: 全体デッドライン内なら次の間隔で再試行（連続 `MAX_CONSECUTIVE_POLL_FAILURES`=3 回で断念、404 は即時失敗）。テスト4件追加 |
| F-2 | LOW | `requestWithStatus` が不要に public | **修正**: private 化 |
| F-3 | LOW | ポーリング 404 時に英語の "Job not found" がそのまま表示されうる（TTL 失効時のみ） | **記録のみ**（通常のポーリング時間内では発生しない。将来の文言統一課題） |
| F-4 | 情報 | ネイティブ `AbortSignal.any` 経路のポーリング E2E は fake timers 制約により未検証 | **記録のみ**（`createRequestSignal` 単体は両経路検証済み） |

### レビューで妥当性が確認された事項（抜粋）

- 設計レビュー CRITICAL 対応（C-1 Decimal 変換 / C-2 Phase A/B/C 分離 / C-3 422・429 の文言完全一致 / H-1 stale 240s / H-5 heavy maxReceiveCount 1）はすべて実装・テストに反映済み
- GET /ai-jobs の IDOR 対策（404 統一・payload 非公開）、submit 側/ワーカーの IAM 最小権限
- 旧同期形式とのデュアル互換判定（2xx + job_id なし。201 対応）と全体デッドラインの内部合成
- inline / SQS ワーカーの単一実行パス（run_job_inline 共有）

## 最終検証結果

- backend: pytest 1768 件全パス / ruff / mypy / `sam validate --lint` パス
- frontend: vitest 875 件（59 ファイル）全パス / type-check / build パス

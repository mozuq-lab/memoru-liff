# ai-async-jobs 設計レビュー記録 (2026-07-07)

設計 v1.0 に対し、独立した2系統のレビュー（アーキテクチャ視点 / 整合性・セキュリティ視点）を
実施した。指摘と v1.1 での対応を記録する。

## CRITICAL

| # | 指摘 | 対応 |
|---|---|---|
| AC-1 | BatchSize 5 は既存 UrlGenerateWorker の「BatchSize 1」設計判断（バッチ内タイムアウト巻き込みによる不当な DLQ 送り防止）と矛盾 | **反映**: 両キューとも BatchSize 1 |
| AC-2 / SH-2 | エラーコード表が 7 種のみで、現行の 422 (EmptyDeck/InsufficientReviewData/EmptyContent/生成0件)・408/403/422/502 (ContentFetchError)・429 (MessageLimit) が internal(500) に潰れる | **反映**: `classify_ai_job_error` を新設し 13 コードに拡張。ai_handler の ContentFetchError 分岐を移設し sync/worker で共有 |
| SC-1 | advice の result に float (average_grade) が混入し DynamoDB 書き込みが毎回失敗 → 3回再実行で Bedrock 3× 課金 + ジョブが completed にならない | **反映**: ai_job_store の書き込みで Decimal 再帰変換・読み出しで逆変換を必須要件化。float 混入テストを必須化 |
| SC-2 | 「インフラ起因失敗 → release → SQS リトライ」が executor 実行後の書き込み失敗にも適用され、tutor_message の再実行で AI 応答の履歴二重追加・message_count 二重加算・二重課金 | **反映**: Phase A(実行前)/C(実行後) を分離。実行後の書き込み失敗は release せず processing のまま朽ちさせる（再実行より安全側） |
| SC-3 / AH-1 | 設計が空デッキを 400 と誤記（現行 422）。InsufficientReviewDataError が設計から完全欠落。フロント TutorContext は 422+文言で UI を出し分けるため回帰する | **反映**: 422 維持・文言完全一致を明記。InsufficientReviewData を fail-fast 表と validation_error(422) コードに追加。TutorService.validate_start_session の分離を設計に明記 |

## HIGH

| # | 指摘 | 対応 |
|---|---|---|
| AH-2 / SH-5 | tutor_start の現行成功レスポンスは 201 で、「200 なら旧同期形式」判定から漏れる | **反映**: 「2xx かつ body に job_id なし → 旧同期形式」の否定形判定に変更 |
| AH-3 | request() は 2xx で body しか返さず status 分岐が不可能。tutor 系は外部 signal を渡さないためポーリング打ち切りが効かない | **反映**: status 可視の submit ヘルパー新設 + submitAndPollAiJob 内部で createRequestSignal によるデッドライン合成を必須化 |
| AH-4 / SM-1 | 単一キュー MaximumConcurrency 5 で重量ジョブが対話系を head-of-line blocking | **反映**: interactive / heavy の 2 キューに分離（heavy = generate_from_url, MaxConcurrency 2） |
| AH-5 | 重量ジョブが worker Timeout を超えた場合、stale 再 claim で AI を丸ごと再実行し「回避したかった 3× 課金」が起きる | **反映**: heavy キューは maxReceiveCount 1（リトライなし） |
| SH-1 | claim stale 閾値 180s = worker Timeout 180s で安全マージンゼロ（webhook_idempotency の原則違反） | **反映**: stale 閾値を 240s に変更 |
| SH-3 | 「バックエンド先行デプロイでも安全」という説明が実メカニズムと逆（保護されるのはフロント先行のみ） | **反映**: フロント先行デプロイを必須手順として明記。誤記を修正 |
| SH-4 / AM-1 | MessageLimitError は現行 429（設計は 409 と誤記） | **反映**: 429 維持を明記（message_limit コード） |
| SH-6 / AM-2 | 専用 Lambda の Timeout 15s 縮小が inline モード（submit が AI を同期実行）と矛盾し、ローカルで 3 エンドポイントが常に失敗 | **反映**: Timeout 縮小を取りやめ（関数統合 follow-up 時に実施） |
| SH-7 | /advice の GET→POST はどちらのデプロイ順序でも安全に失敗しない | **反映**: フロント未使用と確認されたため実害なし。将来組み込み時の注意として記録 |

## MEDIUM / LOW（主要なもの）

| # | 指摘 | 対応 |
|---|---|---|
| AM-3 | text generate（フロント予算 30s）は非同期化でオーバーヘッド分だけ悪化し「成功したのに失敗表示」 | **反映**: generate 30→45s / refine 35→45s に予算引き上げ |
| AM-5 | reviewsApi.gradeAnswer / adviceApi.getAdvice はフロントに存在しない（未使用機能） | **反映**: バックエンドのみ変更・デュアル互換不要と明記 |
| SM-2 | payload のスキーマバージョニング未定義 | **反映**: schema_version 属性を追加（未知版は failed(internal)） |
| SM-3 | tutor_start の fail-fast には検証/実行の分離リファクタが必要 | **反映**: validate_start_session 新設を明記 |
| SM-4 | DLQ アラームが follow-up のままでは 3×課金・DLQ 滞留を検知できない | **反映**: DLQ アラーム（新規2本+既存2本）を本件スコープに格上げ。SNS 配線のみ follow-up |
| AM-4 | submit 側関数の IAM（AiJobsTable + sqs:SendMessage）と GET ルートの帰属が未定義 | **反映**: §3 に明記（GET /ai-jobs は ApiFunction） |
| AL-4 / SL-1 | 重複警告フィールド名は `warning`（`duplicate_warning` は誤記） | **反映**: 修正 |
| SL-2 | map_ai_error_to_http は code を返さないため「流用」ではなく新設が必要 | **反映**: classify_ai_job_error の新設として明記 |
| AL-1 | ジョブ間 dedup（多重クリック）は無い | **反映**: 既知の制限として明記（現行同期と同等。フロントの isSubmitting ガードで実用上抑止） |
| AL-2 | ポーリングによる ApiFunction Invocation 増 | **反映**: 監視項目として明記 |

## レビューで妥当性が確認された設計（変更なし）

- claim = ジョブレコード自体の条件付き更新（既存 webhook_idempotency と同思想）
- inline モード判定規約（_should_enqueue と対称）
- GET /ai-jobs/{id} の 404 統一（既存 IDOR 対策と一貫）
- submit 時レート制限 / poll 対象外の切り分け
- tutor 二重防御（worker 内 send_message が権威、in-flight ロック + #9 対応の温存）
- VisibilityTimeout = worker Timeout × 1.5 の既存比率踏襲
- result = 現行同期レスポンスモデル / TTL 24h / LINE Webhook フロー据え置き

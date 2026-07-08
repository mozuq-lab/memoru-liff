/**
 * カード AI 補足（refine）関連の共有定数。
 */

/**
 * AI 補足（/cards/refine）呼び出しのタイムアウト（ミリ秒）。
 * 非同期ジョブ基盤（202 + ポーリング）ではバックエンドの AI 内部タイムアウト
 * （AI_AGENT_TIMEOUT_SECONDS=30 秒）に SQS 配信・コールドスタート・
 * ポーリング粒度 1.5 秒のオーバーヘッドが上乗せされるため 45 秒に設定する
 * （docs/design/ai-async-jobs/architecture.md §9。useCardGeneration の
 * MAX_GENERATION_TIME=45 秒、Tutor 系の TUTOR_AI_TIMEOUT_MS=90 秒と同様の
 * AI 呼び出し用タイムアウト定数）。
 */
export const REFINE_AI_TIMEOUT_MS = 45_000;

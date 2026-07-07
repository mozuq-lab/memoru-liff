/**
 * カード AI 補足（refine）関連の共有定数。
 */

/**
 * AI 補足（/cards/refine）呼び出しのタイムアウト（ミリ秒）。
 * バックエンドは AI_AGENT_TIMEOUT_SECONDS=30 秒 + API Gateway 上限 30 秒のため、
 * バックエンド側のタイムアウト応答（504 等）を取りこぼさないよう少し長めの
 * 35 秒に設定する（useCardGeneration の MAX_GENERATION_TIME=30 秒、
 * Tutor 系の TUTOR_AI_TIMEOUT_MS=90 秒と同様の AI 呼び出し用タイムアウト定数）。
 */
export const REFINE_AI_TIMEOUT_MS = 35_000;

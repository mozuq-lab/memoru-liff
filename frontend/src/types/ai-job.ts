/**
 * AI 非同期ジョブ基盤 (ai-async-jobs) の型定義。
 *
 * AI 系エンドポイント（生成・補足・チューター等）は submit で
 * 202 Accepted + job_id を返し、フロントは GET /ai-jobs/{job_id} を
 * ポーリングして結果を取得する（docs/design/ai-async-jobs/api-endpoints.md）。
 */

/** ジョブの状態。queued → processing → completed | failed と遷移する。 */
export type AiJobStatus = "queued" | "processing" | "completed" | "failed";

/**
 * failed 時のエラー情報。
 * status / message は現行同期ハンドラーの分類・文言と完全一致するため、
 * フロントはこれをそのまま ApiError に組み立てて既存のエラー分類を再利用できる。
 */
export interface AiJobError {
  status: number;
  code: string;
  message: string;
}

/** GET /ai-jobs/{jobId} のレスポンス（submit の 202 ボディは job_id/job_type/status のみ）。 */
export interface AiJobResponse {
  job_id: string;
  job_type: string;
  status: AiJobStatus;
  /** completed 時のみ。現行同期レスポンスと同一スキーマ。 */
  result?: unknown;
  /** failed 時のみ。 */
  error?: AiJobError;
  created_at: string;
  updated_at: string;
}

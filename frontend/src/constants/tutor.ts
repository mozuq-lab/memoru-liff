/**
 * AI チューター関連の共有定数。
 * TutorContext（ロジック）と TutorPage（表示）の二重管理を避けるため集約する。
 */

/** セッションの非アクティブタイムアウト閾値（ミリ秒）。30分。 */
export const TIMEOUT_MS = 30 * 60 * 1000;

/** セッションあたりのメッセージ（ラウンドトリップ）上限数。 */
export const MESSAGE_LIMIT = 20;

/** タイムアウト閾値を分に換算した値（表示用）。 */
export const TIMEOUT_MINUTES = TIMEOUT_MS / 60_000;

/** Vite env から正の整数のタイムアウト(ms)を解決する。未設定・非数値・非正値は fallback。 */
const resolveMs = (raw: unknown, fallback: number): number => {
  const value = Number(raw);
  return Number.isFinite(value) && value > 0 ? value : fallback;
};

/**
 * チューターAI呼び出し（セッション開始のあいさつ生成 / メッセージ送信）の fetch
 * タイムアウト（ミリ秒）。AI 生成を伴うため既定の 30 秒では足りず、ローカル LLM
 * 利用時は特に中断されやすい。バックエンドのチューター用タイムアウト以上に設定すること
 * （フロントが先に abort するとバックエンドの応答/エラーが届かない）。
 * VITE_TUTOR_AI_TIMEOUT_MS で上書き可能（既定 90 秒）。
 */
export const TUTOR_AI_TIMEOUT_MS = resolveMs(
  import.meta.env.VITE_TUTOR_AI_TIMEOUT_MS,
  90_000,
);

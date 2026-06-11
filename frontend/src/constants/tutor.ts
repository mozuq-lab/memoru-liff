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

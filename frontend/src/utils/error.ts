/**
 * 任意の throw 値を Error に正規化する。
 * Error はそのまま返し、それ以外は String 化してラップする。
 *
 * catch (err) の err は unknown 型のため、error state へ格納する際に
 * 各所で `err instanceof Error ? err : new Error(String(err))` が重複していたのを集約する。
 */
export function toError(err: unknown): Error {
  return err instanceof Error ? err : new Error(String(err));
}

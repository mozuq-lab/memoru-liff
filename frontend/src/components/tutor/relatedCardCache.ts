import { cardsApi } from "@/services/api";
import type { Card } from "@/types";

/**
 * F-5: cardId -> 表面テキストのモジュールレベルキャッシュ。
 * 同一 cardId の再フェッチ（チップごと・再マウントごと）を防ぐ。
 * - 解決済みの値（string）または「削除済み」を表す null を保持
 * - 取得中は in-flight Promise を共有し、同時リクエストの重複も防ぐ
 *
 * RelatedCardChip と分離しているのは Fast Refresh
 * (react-refresh/only-export-components) を維持するため。
 */
const frontTextCache = new Map<string, string | null>();
const inFlight = new Map<string, Promise<string | null>>();

/** キャッシュ済みの表面テキストを同期取得する（未取得なら undefined） */
export const getCachedFrontText = (cardId: string): string | null | undefined =>
  frontTextCache.has(cardId) ? frontTextCache.get(cardId) : undefined;

/** cardId の表面テキストを取得する。キャッシュ・in-flight Promise を共有する */
export const fetchFrontText = (cardId: string): Promise<string | null> => {
  // キャッシュヒット（削除済みの null も含む）はそのまま返す
  if (frontTextCache.has(cardId)) {
    return Promise.resolve(frontTextCache.get(cardId) ?? null);
  }
  // 取得中なら同じ Promise を共有してリクエスト重複を防ぐ
  const existing = inFlight.get(cardId);
  if (existing) return existing;

  const promise = cardsApi
    .getCard(cardId)
    .then((card: Card) => {
      frontTextCache.set(cardId, card.front);
      return card.front;
    })
    .catch(() => {
      // カードが削除済み等で取得失敗 → null をキャッシュしフォールバック表示
      frontTextCache.set(cardId, null);
      return null;
    })
    .finally(() => {
      inFlight.delete(cardId);
    });

  inFlight.set(cardId, promise);
  return promise;
};

/** テスト用: キャッシュをクリアする */
export const __clearRelatedCardCache = () => {
  frontTextCache.clear();
  inFlight.clear();
};

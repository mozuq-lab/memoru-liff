/**
 * deck-review-fixes 型定義（修正差分）
 *
 * 作成日: 2026-03-01
 * 関連設計: architecture.md
 *
 * 本ファイルは deck-review-fixes で修正が必要な型定義の差分を示す。
 * 既存の型定義ファイルに対する変更点のみを記載。
 *
 * 信頼性レベル:
 * - 🔵 青信号: EARS要件定義書・設計文書・既存実装を参考にした確実な型定義
 * - 🟡 黄信号: EARS要件定義書・設計文書・既存実装から妥当な推測による型定義
 * - 🔴 赤信号: EARS要件定義書・設計文書・既存実装にない推測による型定義
 */

// ========================================
// H-2: UpdateCardRequest の deck_id 型修正
// ファイル: frontend/src/types/card.ts
// ========================================

/**
 * カード更新リクエスト（修正後）
 * 🔵 信頼性: レビュー H-2・要件定義 REQ-002, REQ-103, REQ-104 より
 *
 * 変更点:
 * - deck_id: string | undefined → string | null | undefined
 * - undefined（キーなし）: deck_id を変更しない
 * - null: deck_id を REMOVE する（未分類に戻す）
 * - string: deck_id を指定値に SET する
 */
export interface UpdateCardRequest {
  front?: string; // 🔵 既存実装より（変更なし）
  back?: string; // 🔵 既存実装より（変更なし）
  deck_id?: string | null; // 🔵 H-2 修正: null 許容に変更
  tags?: string[]; // 🔵 既存実装より（変更なし）
  interval?: number; // 🔵 既存実装より（変更なし）
}

// ========================================
// M-3: UpdateDeckRequest の description/color 型修正
// ファイル: frontend/src/types/deck.ts
// ========================================

/**
 * デッキ更新リクエスト（修正後）
 * 🔵 信頼性: レビュー M-3・要件定義 REQ-105, REQ-106 より
 *
 * 変更点:
 * - description: string | undefined → string | null | undefined
 * - color: string | undefined → string | null | undefined
 * - undefined（キーなし）: フィールドを変更しない
 * - null: フィールドを REMOVE する（初期状態に戻す）
 * - string: フィールドを指定値に SET する
 */
export interface UpdateDeckRequest {
  name?: string; // 🔵 既存実装より（変更なし）
  description?: string | null; // 🔵 M-3 修正: null 許容に変更
  color?: string | null; // 🔵 M-3 修正: null 許容に変更
}

// ========================================
// M-4: DeckFormModal 差分送信用型
// ファイル: frontend/src/components/DeckFormModal.tsx
// ========================================

/**
 * DeckFormModal の差分検出に使用する初期値型
 * 🔵 信頼性: レビュー M-4・要件定義 REQ-202 より
 *
 * edit モードで開いた時のフォーム初期値を保持し、
 * 保存時に各フィールドの変更を検出するために使用する。
 */
export interface DeckFormInitialValues {
  name: string; // 🔵 既存実装より
  description: string | null; // 🔵 M-3 対応: null 許容
  color: string | null; // 🔵 M-3 対応: null 許容
}

// ========================================
// H-1: CardsContext fetchCards/fetchDueCards パラメータ拡張
// ファイル: frontend/src/contexts/CardsContext.tsx
// ========================================

/**
 * CardsContext の関数シグネチャ（修正後）
 * 🔵 信頼性: レビュー H-1・要件定義 REQ-001, REQ-102 より
 *
 * 変更点:
 * - fetchCards(deckId?: string): deck_id パラメータ追加
 * - fetchDueCards(deckId?: string): deck_id パラメータ追加
 * - deckId が undefined の場合は従来動作（全件取得）
 */
export interface CardsContextValue {
  cards: Card[];
  dueCards: Card[];
  isLoading: boolean;
  error: string | null;
  totalDueCount: number;
  fetchCards: (deckId?: string) => Promise<void>; // 🔵 H-1: deckId パラメータ追加
  fetchDueCards: (deckId?: string) => Promise<void>; // 🔵 H-1: deckId パラメータ追加
  createCard: (data: CreateCardRequest) => Promise<void>;
  updateCard: (cardId: string, data: UpdateCardRequest) => Promise<void>;
  deleteCard: (cardId: string) => Promise<void>;
}

// ========================================
// H-3, H-4: バックエンド エラーレスポンス（参考）
// ファイル: backend/src/api/handlers/decks_handler.py
// ========================================

/**
 * デッキ制限超過エラーレスポンス（参考定義）
 * 🔵 信頼性: 追加レビュー H-3・要件定義 REQ-003 より
 *
 * HTTP 409 Conflict で返却される。
 * 旧: HTTP 400 Bad Request
 * 新: HTTP 409 Conflict
 */
export interface DeckLimitExceededErrorResponse {
  error: 'Deck limit exceeded. Maximum 50 decks per user.'; // 🔵 H-3 修正
}

// ========================================
// バックエンド: Sentinel パターン（参考・Python）
// ファイル: backend/src/services/card_service.py, deck_service.py
// ========================================

/**
 * Python 側の Sentinel パターン（TypeScript での参考記載）
 * 🔵 信頼性: レビュー H-2, M-3・architecture.md REMOVE パターンより
 *
 * Python 実装:
 *   _UNSET = object()
 *
 *   def update_card(self, ..., deck_id=_UNSET):
 *       if deck_id is None:       → REMOVE deck_id
 *       elif deck_id is not _UNSET: → SET deck_id = value
 *       # _UNSET → 変更なし
 *
 *   def update_deck(self, ..., description=_UNSET, color=_UNSET):
 *       if description is None:       → REMOVE description
 *       elif description is not _UNSET: → SET description = value
 *       # _UNSET → 変更なし
 */

// ========================================
// 信頼性レベルサマリー
// ========================================
/**
 * - 🔵 青信号: 18件 (100%)
 * - 🟡 黄信号: 0件 (0%)
 * - 🔴 赤信号: 0件 (0%)
 *
 * 品質評価: ✅ 高品質
 *
 * 全型定義がレビュー文書・要件定義書・既存実装に基づいており、
 * 推測による定義は含まれていない。
 */

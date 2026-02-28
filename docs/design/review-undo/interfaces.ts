/**
 * review-undo 型定義
 *
 * 作成日: 2026-02-28
 * 関連設計: architecture.md
 *
 * 信頼性レベル:
 * - 🔵 青信号: EARS要件定義書・設計文書・既存実装を参考にした確実な型定義
 * - 🟡 黄信号: EARS要件定義書・設計文書・既存実装から妥当な推測による型定義
 * - 🔴 赤信号: EARS要件定義書・設計文書・既存実装にない推測による型定義
 */

// ========================================
// セッション結果型定義
// ========================================

/**
 * セッション中のカード結果タイプ
 * 🔵 信頼性: 要件定義REQ-001〜004・ユーザヒアリングより
 */
export type SessionCardResultType = 'graded' | 'skipped' | 'undone';

/**
 * セッション中の各カードの結果
 * 🔵 信頼性: 要件定義REQ-001〜004・ユーザヒアリングより
 *
 * ReviewPageのstateで保持し、ReviewCompleteに渡す
 */
export interface SessionCardResult {
  /** カードID */
  cardId: string; // 🔵 既存DueCard.card_idより
  /** カード表面テキスト（完了画面での表示用） */
  front: string; // 🔵 要件定義REQ-002より
  /** 採点グレード (0-5)。スキップ・取り消し済みの場合はnull */
  grade: number | null; // 🔵 要件定義REQ-002より
  /** 次回復習日 (ISO日付文字列 "YYYY-MM-DD")。スキップ・取り消し済みの場合はnull */
  nextReviewDate: string | null; // 🔵 要件定義REQ-002より
  /** 結果タイプ */
  type: SessionCardResultType; // 🔵 要件定義REQ-003, REQ-004より
}

// ========================================
// コンポーネント Props（変更・新規）
// ========================================

/**
 * ReviewComplete コンポーネント Props（変更）
 * 🔵 信頼性: 要件定義REQ-001〜008・architecture.mdより
 *
 * 既存: { reviewedCount: number }
 * 変更後: 結果一覧・取り消し操作を受け持つ
 */
export interface ReviewCompleteProps {
  /** セッション中の全カード結果 */
  results: SessionCardResult[]; // 🔵 要件定義REQ-001より
  /** 取り消しハンドラ (結果配列のindex) */
  onUndo: (index: number) => void; // 🔵 要件定義REQ-005より
  /** undo API呼び出し中フラグ */
  isUndoing: boolean; // 🟡 UXパターンから妥当な推測
  /** undo中のカードindex (ローディング表示用) */
  undoingIndex: number | null; // 🟡 UXパターンから妥当な推測
}

/**
 * ReviewResultItem コンポーネント Props（新規）
 * 🟡 信頼性: 要件定義REQ-001〜005からの設計推測
 */
export interface ReviewResultItemProps {
  /** カード結果 */
  result: SessionCardResult; // 🔵 要件定義REQ-001〜002より
  /** 結果配列内のindex */
  index: number; // 🟡 実装都合
  /** 取り消しハンドラ */
  onUndo: (index: number) => void; // 🔵 要件定義REQ-005より
  /** この項目がundo中か */
  isUndoing: boolean; // 🟡 UXパターンから妥当な推測
}

// ========================================
// API レスポンス型（新規）
// ========================================

/**
 * POST /reviews/{cardId}/undo レスポンス
 * 🔵 信頼性: 要件定義REQ-009〜012・既存ReviewResponseパターンより
 */
export interface UndoReviewResponse {
  /** カードID */
  card_id: string; // 🔵 既存ReviewResponse.card_idパターンより
  /** 復元後のSRSパラメータ */
  restored: UndoRestoredState; // 🔵 要件定義REQ-010より
  /** undo実行日時 */
  undone_at: string; // 🟡 API設計の一般的なパターンから推測
}

/**
 * Undo後の復元状態
 * 🔵 信頼性: 要件定義REQ-010・既存ReviewPreviousStateパターンより
 */
export interface UndoRestoredState {
  /** 復元後のease_factor */
  ease_factor: number; // 🔵 既存ReviewPreviousState.ease_factorより
  /** 復元後のinterval */
  interval: number; // 🔵 既存ReviewPreviousState.intervalより
  /** 復元後のrepetitions */
  repetitions: number; // 🔵 既存ReviewPreviousState.repetitionsより
  /** 復元後の次回復習日 */
  due_date: string; // 🔵 既存ReviewPreviousState.due_dateより
}

// ========================================
// グレード表示用ユーティリティ型
// ========================================

/**
 * グレード表示設定（完了画面用）
 * 🟡 信頼性: 既存GradeButtonsの色スキームから妥当な推測
 *
 * 既存のGRADE_CONFIGSと統一した色分けを完了画面でも使用
 */
export interface GradeDisplayConfig {
  /** グレード値 (0-5) */
  grade: number;
  /** 表示テキスト */
  label: string;
  /** 背景色のTailwind CSSクラス */
  bgClass: string;
  /** テキスト色のTailwind CSSクラス */
  textClass: string;
}

/**
 * グレード表示設定（定数）
 * 🟡 信頼性: 既存GradeButtons.tsxの色スキームから妥当な推測
 */
export const GRADE_DISPLAY_CONFIGS: GradeDisplayConfig[] = [
  { grade: 0, label: '0', bgClass: 'bg-red-50',    textClass: 'text-red-700' },
  { grade: 1, label: '1', bgClass: 'bg-orange-50', textClass: 'text-orange-700' },
  { grade: 2, label: '2', bgClass: 'bg-amber-50',  textClass: 'text-amber-700' },
  { grade: 3, label: '3', bgClass: 'bg-yellow-50', textClass: 'text-yellow-700' },
  { grade: 4, label: '4', bgClass: 'bg-lime-50',   textClass: 'text-lime-700' },
  { grade: 5, label: '5', bgClass: 'bg-green-50',  textClass: 'text-green-700' },
];

// ========================================
// 信頼性レベルサマリー
// ========================================
/**
 * - 🔵 青信号: 17件 (71%)
 * - 🟡 黄信号: 7件 (29%)
 * - 🔴 赤信号: 0件 (0%)
 *
 * 品質評価: ✅ 高品質
 * 黄信号はUXパターン推測・実装都合・表示設定のみ
 */

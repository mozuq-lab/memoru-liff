/**
 * review-flow 型定義
 *
 * 作成日: 2026-02-25
 * 関連設計: architecture.md
 *
 * 信頼性レベル:
 * - 🔵 青信号: EARS要件定義書・設計文書・既存実装を参考にした確実な型定義
 * - 🟡 黄信号: EARS要件定義書・設計文書・既存実装から妥当な推測による型定義
 * - 🔴 赤信号: EARS要件定義書・設計文書・既存実装にない推測による型定義
 */

// ========================================
// 既存型定義（参照用 - frontend/src/types/card.ts に定義済み）
// ========================================

/**
 * DueCard - GET /cards/due レスポンスのカード情報
 * 🔵 信頼性: 既存 API レスポンス・型定義より
 * 参照: frontend/src/types/card.ts
 */
// export interface DueCard {
//   card_id: string;
//   front: string;
//   back: string;
//   deck_id?: string;
//   due_date: string | null;
//   overdue_days: number;
// }

// ========================================
// 復習セッション状態
// ========================================

/**
 * 復習セッションのフェーズ
 * 🔵 信頼性: 要件定義REQ-RV-001〜005・dataflow.mdの状態遷移図より
 */
export type ReviewPhase =
  | 'loading'    // 初期読み込み中
  | 'empty'      // 復習対象カード0枚
  | 'error'      // エラー状態
  | 'reviewing'  // 復習セッション中
  | 'complete';  // 復習完了

/**
 * カードの表示状態
 * 🔵 信頼性: 要件定義REQ-RV-201〜202・ユーザヒアリングより
 */
export type CardSide = 'front' | 'back';

// ========================================
// コンポーネント Props
// ========================================

/**
 * FlipCard コンポーネント Props
 * 🔵 信頼性: 要件定義REQ-RV-002・architecture.mdより
 */
export interface FlipCardProps {
  /** カード表面テキスト（質問） */
  front: string; // 🔵 既存カードデータ構造より
  /** カード裏面テキスト（解答） */
  back: string; // 🔵 既存カードデータ構造より
  /** フリップ状態 */
  isFlipped: boolean; // 🔵 要件定義REQ-RV-002より
  /** フリップハンドラ（タップ/クリック時） */
  onFlip: () => void; // 🔵 要件定義REQ-RV-002より
}

/**
 * GradeButtons コンポーネント Props
 * 🔵 信頼性: 要件定義REQ-RV-003・architecture.mdより
 */
export interface GradeButtonsProps {
  /** 採点ハンドラ (grade: 0-5) */
  onGrade: (grade: number) => void; // 🔵 既存API仕様 POST /reviews/{id}より
  /** スキップハンドラ */
  onSkip: () => void; // 🔵 要件定義REQ-RV-020より
  /** 送信中のボタン無効化 */
  disabled: boolean; // 🟡 UXベストプラクティスから妥当な推測
}

/**
 * ReviewProgress コンポーネント Props
 * 🔵 信頼性: 要件定義REQ-RV-005・architecture.mdより
 */
export interface ReviewProgressProps {
  /** 現在のカード番号（1始まり） */
  current: number; // 🔵 要件定義REQ-RV-005より
  /** 全体枚数 */
  total: number; // 🔵 要件定義REQ-RV-005より
}

/**
 * ReviewComplete コンポーネント Props
 * 🔵 信頼性: 要件定義REQ-RV-010〜011・architecture.mdより
 */
export interface ReviewCompleteProps {
  /** 採点済みカード数（スキップ除く） */
  reviewedCount: number; // 🔵 要件定義REQ-RV-010より
}

// ========================================
// 採点ボタン定義
// ========================================

/**
 * SM-2 グレード (0-5)
 * 🔵 信頼性: 既存バックエンドAPI仕様・REQ-032より
 */
export type SM2Grade = 0 | 1 | 2 | 3 | 4 | 5;

/**
 * 採点ボタンの表示情報
 * 🟡 信頼性: architecture.mdのボタンデザインから妥当な推測
 */
export interface GradeButtonConfig {
  /** SM-2 グレード値 */
  grade: SM2Grade;
  /** ボタンラベル */
  label: string;
  /** Tailwind CSS カラークラス */
  colorClass: string;
  /** SM-2 での意味 */
  description: string;
}

/**
 * 採点ボタン設定（定数）
 * 🟡 信頼性: architecture.mdのボタンデザイン表から妥当な推測
 */
export const GRADE_BUTTON_CONFIGS: GradeButtonConfig[] = [
  { grade: 0, label: '0', colorClass: 'bg-red-600',    description: '全く覚えていない' },
  { grade: 1, label: '1', colorClass: 'bg-orange-600', description: '間違えた' },
  { grade: 2, label: '2', colorClass: 'bg-amber-500',  description: '間違えたが見覚えあり' },
  { grade: 3, label: '3', colorClass: 'bg-yellow-500', description: '難しかったが正解' },
  { grade: 4, label: '4', colorClass: 'bg-lime-500',   description: 'やや迷ったが正解' },
  { grade: 5, label: '5', colorClass: 'bg-green-600',  description: '完璧' },
];

// ========================================
// API レスポンス型（参照用 - 既存実装に定義済み）
// ========================================

/**
 * GET /cards/due レスポンス
 * 🔵 信頼性: 既存API仕様・実装より
 * 参照: frontend/src/services/api.ts, backend/src/models/review.py
 */
// export interface DueCardsResponse {
//   due_cards: DueCard[];
//   total_due_count: number;
//   next_due_date: string | null;
// }

/**
 * POST /reviews/{card_id} リクエスト
 * 🔵 信頼性: 既存API仕様・実装より
 * 参照: frontend/src/services/api.ts
 */
// export interface SubmitReviewRequest {
//   grade: SM2Grade;
// }

// ========================================
// 信頼性レベルサマリー
// ========================================
/**
 * - 🔵 青信号: 14件 (82%)
 * - 🟡 黄信号: 3件 (18%)
 * - 🔴 赤信号: 0件 (0%)
 *
 * 品質評価: ✅ 高品質（青信号が80%以上）
 * 黄信号はボタンデザイン設定（実装時に確定）とdisabledプロパティのみ
 */

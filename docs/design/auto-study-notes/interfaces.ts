/**
 * Auto Study Notes 型定義（フロントエンド）
 *
 * 作成日: 2026-03-07
 * 関連設計: architecture.md
 *
 * 信頼性レベル:
 * - 🔵 青信号: EARS要件定義書・設計文書・既存実装を参考にした確実な型定義
 * - 🟡 黄信号: EARS要件定義書・設計文書・既存実装から妥当な推測による型定義
 * - 🔴 赤信号: EARS要件定義書・設計文書・既存実装にない推測による型定義
 */

// ========================================
// API リクエスト/レスポンス型
// ========================================

/**
 * 生成ソース種別
 * 🔵 信頼性: REQ-ASN-001, REQ-ASN-002・API仕様より
 */
export type SourceType = "deck" | "tag";

/**
 * 要約ノート生成リクエスト
 * 🔵 信頼性: API仕様・REQ-ASN-001より
 */
export interface GenerateStudyNotesRequest {
  source_type: SourceType; // 🔵 API仕様より
  source_id: string; // 🔵 API仕様より
}

/**
 * 要約ノートデータ
 * 🔵 信頼性: API仕様・REQ-ASN-031〜034より
 */
export interface StudyNotesData {
  source_type: SourceType; // 🔵 API仕様より
  source_id: string; // 🔵 API仕様より
  content: string; // 🔵 Markdown形式の要約ノート本文
  card_count: number; // 🟡 生成時のカード枚数
  is_stale: boolean; // 🔵 無効化フラグ
  model_used: string; // 🔵 既存パターンより
  processing_time_ms: number; // 🔵 既存パターンより
  generated_at: string; // 🔵 ISO 8601
}

/**
 * 要約ノート API レスポンス
 * 🔵 信頼性: 既存APIレスポンスパターンより
 */
export interface StudyNotesResponse {
  success: boolean; // 🔵 既存パターンより
  data: StudyNotesData | null; // 🔵 キャッシュなし時はnull
}

/**
 * API エラーレスポンス
 * 🔵 信頼性: 既存APIエラーパターンより
 */
export interface StudyNotesErrorResponse {
  success: false; // 🔵 既存パターンより
  error: {
    code: string; // 🔵 INSUFFICIENT_CARDS, AI_TIMEOUT等
    message: string; // 🔵 ユーザー向けメッセージ
    details?: Record<string, unknown>; // 🔵 既存パターンより
  };
}

// ========================================
// フロントエンド状態管理型
// ========================================

/**
 * 要約ノートの表示状態
 * 🟡 信頼性: Reactの一般的な状態管理パターンから妥当な推測
 */
export type StudyNotesStatus =
  | "idle" // 初期状態
  | "loading" // キャッシュ確認中
  | "generating" // AI生成中
  | "cached" // キャッシュヒット（最新）
  | "stale" // キャッシュ古い
  | "empty" // キャッシュなし
  | "error"; // エラー

/**
 * useStudyNotes フックの戻り値
 * 🟡 信頼性: 既存カスタムフックパターンから妥当な推測
 */
export interface UseStudyNotesReturn {
  status: StudyNotesStatus;
  data: StudyNotesData | null;
  error: string | null;
  generate: () => Promise<void>;
  refresh: () => Promise<void>;
}

// ========================================
// 信頼性レベルサマリー
// ========================================
/**
 * - 🔵 青信号: 16件 (84%)
 * - 🟡 黄信号: 3件 (16%)
 * - 🔴 赤信号: 0件 (0%)
 *
 * 品質評価: ✅ 高品質
 */

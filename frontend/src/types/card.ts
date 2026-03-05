// 参考情報の型定義
export type ReferenceType = "url" | "book" | "note";

export interface Reference {
  type: ReferenceType;
  value: string;
}

export interface Card {
  card_id: string;
  user_id: string;
  front: string;
  back: string;
  deck_id?: string | null;
  tags: string[];
  references?: Reference[];
  next_review_at?: string | null;
  interval: number;
  ease_factor: number;
  repetitions: number;
  created_at: string;
  updated_at?: string | null;
}

export interface CreateCardRequest {
  front: string;
  back: string;
  deck_id?: string;
  tags?: string[];
  references?: Reference[];
}

export interface UpdateCardRequest {
  front?: string;
  back?: string;
  deck_id?: string | null;
  tags?: string[];
  references?: Reference[];
  // 【追加フィールド】: 復習間隔調整機能（TASK-0079）で追加。1〜365の整数を受け付ける 🔵
  interval?: number;
}

export interface GenerateCardsRequest {
  input_text: string;
  card_count?: number;
  difficulty?: 'easy' | 'medium' | 'hard';
  language?: 'ja' | 'en';
}

export interface GeneratedCard {
  front: string;
  back: string;
  suggested_tags: string[];
}

/** フロントエンド用の一時ID付き生成カード */
export interface GeneratedCardWithId extends GeneratedCard {
  tempId: string;
}

export interface GenerateCardsResponse {
  generated_cards: GeneratedCard[];
  generation_info: {
    input_length: number;
    model_used: string;
    processing_time_ms: number;
  };
}

// URL-based card generation types
export type CardType = 'qa' | 'definition' | 'cloze';

export interface GenerateFromUrlRequest {
  url: string;
  card_type?: CardType;
  target_count?: number;
  difficulty?: 'easy' | 'medium' | 'hard';
  language?: 'ja' | 'en';
  deck_id?: string;
}

export interface UrlGenerationInfo {
  model_used: string;
  processing_time_ms: number;
  fetch_method: 'http' | 'browser';
  chunk_count: number;
  content_length: number;
}

export interface PageInfo {
  url: string;
  title: string;
  fetched_at: string;
}

export interface GenerateFromUrlResponse {
  generated_cards: GeneratedCard[];
  generation_info: UrlGenerationInfo;
  page_info: PageInfo;
}

// AI Refine types
export interface RefineCardRequest {
  front: string;
  back: string;
  language?: 'ja' | 'en';
}

export interface RefineCardResponse {
  refined_front: string;
  refined_back: string;
  model_used: string;
  processing_time_ms: number;
}

// Review types
export interface ReviewPreviousState {
  ease_factor: number;
  interval: number;
  repetitions: number;
  due_date: string | null;
}

export interface ReviewUpdatedState {
  ease_factor: number;
  interval: number;
  repetitions: number;
  due_date: string;
}

export interface ReviewResponse {
  card_id: string;
  grade: number;
  previous: ReviewPreviousState;
  updated: ReviewUpdatedState;
  reviewed_at: string;
}

// Undo types
export interface UndoRestoredState {
  ease_factor: number;
  interval: number;
  repetitions: number;
  due_date: string;
}

export interface UndoReviewResponse {
  card_id: string;
  restored: UndoRestoredState;
  undone_at: string;
}

// セッション結果の型定義
// 【SessionCardResultType】: 各カードの処理結果を表すユニオン型
// - 'graded'     : SM-2 API で採点済み
// - 'skipped'    : スキップされた（SM-2 評価なし）
// - 'undone'     : 取り消し済み（再採点待ち）
// - 'reconfirmed': 再確認ループで「覚えた」として確認済み（TASK-0081 追加）
// 🔵 信頼性レベル: 要件定義書 REQ-001, REQ-501 より
export type SessionCardResultType = 'graded' | 'skipped' | 'undone' | 'reconfirmed';

/**
 * 【SessionCardResult】: 1枚のカードのセッション処理結果を表すインターフェース
 * - grade, nextReviewDate は 'graded' / 'reconfirmed' 時に設定
 * - reconfirmResult は 'reconfirmed' 時に設定（現在は 'remembered' のみ）
 * 🔵 信頼性レベル: 要件定義書 REQ-003, REQ-501 より
 */
export interface SessionCardResult {
  cardId: string;
  front: string;
  grade?: number;
  nextReviewDate?: string;
  type: SessionCardResultType;
  // 【再確認結果】: 'reconfirmed' type のカードのみ設定される（TASK-0081 追加）
  reconfirmResult?: 'remembered';
}

/**
 * 【ReconfirmCard】: 再確認キューに入れるカードの型（TASK-0081 追加）
 * quality 0-2 で評価されたカードを再確認ループで表示するために使用する
 * セッション内フロントエンド state のみで管理（バックエンド API 呼び出しなし）
 * 🔵 信頼性レベル: 要件定義書 REQ-001, REQ-201・architecture.md より
 */
export interface ReconfirmCard {
  cardId: string;
  front: string;
  back: string;
  // 【元の評価値】: quality 0, 1, or 2 のいずれか（SM-2 は初回評価時に設定済み）
  originalGrade: number;
}

export interface DueCard {
  card_id: string;
  front: string;
  back: string;
  deck_id?: string | null;
  due_date?: string | null;
  overdue_days: number;
  references?: Reference[];
}

export interface DueCardsResponse {
  due_cards: DueCard[];
  total_due_count: number;
  next_due_date: string | null;
}

// ===== カード検索・フィルター・ソート型定義 =====

/**
 * カードの復習状態フィルター
 * - 'all': すべてのカード
 * - 'new': repetitions === 0
 * - 'due': repetitions > 0 かつ next_review_at <= 今日
 * - 'learning': repetitions > 0 かつ next_review_at > 今日
 */
export type ReviewStatusFilter = 'all' | 'new' | 'due' | 'learning';

/**
 * カードのソートキー
 * - 'created_at': 作成日順
 * - 'next_review_at': 次回復習日順（null は末尾）
 * - 'ease_factor': 習熟度順（低い = 苦手なカード）
 */
export type SortByOption = 'created_at' | 'next_review_at' | 'ease_factor';

/**
 * ソート方向
 */
export type SortOrder = 'asc' | 'desc';

/**
 * カード検索・フィルター・ソートの状態
 * useCardSearch フックが管理する状態の型
 */
export interface CardFilterState {
  /** キーワード検索文字列（空文字 = フィルターなし） */
  query: string;
  /** 復習状態フィルター */
  reviewStatus: ReviewStatusFilter;
  /** ソートキー */
  sortBy: SortByOption;
  /** ソート方向 */
  sortOrder: SortOrder;
}

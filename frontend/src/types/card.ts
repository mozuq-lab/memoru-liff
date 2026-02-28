export interface Card {
  card_id: string;
  user_id: string;
  front: string;
  back: string;
  deck_id?: string | null;
  tags: string[];
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
}

export interface UpdateCardRequest {
  front?: string;
  back?: string;
  deck_id?: string;
  tags?: string[];
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

// Session result types
export type SessionCardResultType = 'graded' | 'skipped' | 'undone';

export interface SessionCardResult {
  cardId: string;
  front: string;
  grade?: number;
  nextReviewDate?: string;
  type: SessionCardResultType;
}

export interface DueCard {
  card_id: string;
  front: string;
  back: string;
  deck_id?: string | null;
  due_date?: string | null;
  overdue_days: number;
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

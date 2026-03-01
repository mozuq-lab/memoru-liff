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
  deck_id?: string | null;
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

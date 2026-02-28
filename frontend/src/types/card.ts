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
}

export interface DueCardsResponse {
  due_cards: DueCard[];
  total_due_count: number;
  next_due_date: string | null;
}

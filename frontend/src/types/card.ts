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

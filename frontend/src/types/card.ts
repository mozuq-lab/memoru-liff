export interface Card {
  id: string;
  user_id: string;
  front: string;
  back: string;
  tags: string[];
  ease_factor: number;
  interval: number;
  repetitions: number;
  due_date: string;
  created_at: string;
  updated_at: string;
}

export interface CreateCardRequest {
  front: string;
  back: string;
  tags?: string[];
}

export interface UpdateCardRequest {
  front?: string;
  back?: string;
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
  due_date: string;
  overdue_days: number;
}

export interface DueCardsResponse {
  due_cards: DueCard[];
  total_due_count: number;
  next_due_date: string | null;
}

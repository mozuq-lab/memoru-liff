export interface StatsResponse {
  total_cards: number;
  learned_cards: number;
  unlearned_cards: number;
  cards_due_today: number;
  total_reviews: number;
  average_grade: number;
  streak_days: number;
  tag_performance: Record<string, number>;
}

export interface WeakCard {
  card_id: string;
  front: string;
  back: string;
  ease_factor: number;
  repetitions: number;
  deck_id?: string | null;
}

export interface WeakCardsResponse {
  weak_cards: WeakCard[];
  total_count: number;
}

export interface ForecastDay {
  date: string;
  due_count: number;
}

export interface ForecastResponse {
  forecast: ForecastDay[];
}

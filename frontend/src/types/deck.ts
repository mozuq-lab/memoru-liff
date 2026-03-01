export interface Deck {
  deck_id: string;
  user_id: string;
  name: string;
  description?: string | null;
  color?: string | null;
  card_count: number;
  due_count: number;
  created_at: string;
  updated_at?: string | null;
}

export interface CreateDeckRequest {
  name: string;
  description?: string;
  color?: string;
}

export interface UpdateDeckRequest {
  name?: string;
  description?: string | null;
  color?: string | null;
}

export interface DeckListResponse {
  decks: Deck[];
  total: number;
}

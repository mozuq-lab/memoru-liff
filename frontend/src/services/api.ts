import type {
  Card,
  CreateCardRequest,
  UpdateCardRequest,
  GenerateCardsRequest,
  GenerateCardsResponse,
  DueCardsResponse,
  User,
  UpdateUserRequest,
  LinkLineRequest,
} from '@/types';
import { authService } from './auth';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

class ApiClient {
  private accessToken: string | null = null;
  private isRefreshing = false;
  private refreshPromise: Promise<void> | null = null;

  setAccessToken(token: string | null) {
    this.accessToken = token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.accessToken) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${this.accessToken}`;
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    // 401 Unauthorized - トークンリフレッシュ処理
    if (response.status === 401) {
      if (!this.isRefreshing) {
        this.isRefreshing = true;
        this.refreshPromise = this.refreshToken();
      }
      try {
        await this.refreshPromise;
        // リフレッシュ成功後に元のリクエストを再実行
        return this.request<T>(endpoint, options);
      } catch {
        // リフレッシュ失敗 - ログイン画面にリダイレクト
        authService.login();
        throw new Error('Session expired');
      } finally {
        this.isRefreshing = false;
        this.refreshPromise = null;
      }
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ message: 'Unknown error' }));
      throw new Error(error.message || `HTTP ${response.status}`);
    }

    if (response.status === 204) {
      return undefined as T;
    }
    return response.json();
  }

  private async refreshToken(): Promise<void> {
    await authService.refreshToken();
    // リフレッシュ後に新しいアクセストークンを取得してセット
    const newToken = await authService.getAccessToken();
    this.setAccessToken(newToken);
  }

  // カード API
  async getCards(): Promise<Card[]> {
    const response = await this.request<{ cards: Card[] }>('/cards');
    return response.cards;
  }

  async getCard(id: string): Promise<Card> {
    return this.request<Card>(`/cards/${id}`);
  }

  async createCard(data: CreateCardRequest): Promise<Card> {
    return this.request<Card>('/cards', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateCard(id: string, data: UpdateCardRequest): Promise<Card> {
    return this.request<Card>(`/cards/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteCard(id: string): Promise<void> {
    await this.request<void>(`/cards/${id}`, {
      method: 'DELETE',
    });
  }

  async generateCards(data: GenerateCardsRequest): Promise<GenerateCardsResponse> {
    return this.request<GenerateCardsResponse>('/cards/generate', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getDueCards(limit?: number): Promise<DueCardsResponse> {
    const params = limit ? `?limit=${limit}` : '';
    return this.request<DueCardsResponse>(`/cards/due${params}`);
  }

  async getDueCount(): Promise<number> {
    const response = await this.getDueCards(1);
    return response.total_due_count;
  }

  // レビュー API
  async submitReview(cardId: string, grade: number): Promise<void> {
    await this.request<void>(`/reviews/${cardId}`, {
      method: 'POST',
      body: JSON.stringify({ grade }),
    });
  }

  // ユーザー API
  async getCurrentUser(): Promise<User> {
    return this.request<User>('/users/me');
  }

  async updateUser(data: UpdateUserRequest): Promise<User> {
    return this.request<User>('/users/me/settings', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async linkLine(data: LinkLineRequest): Promise<User> {
    return this.request<User>('/users/link-line', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async unlinkLine(): Promise<User> {
    return this.request<User>('/users/me/unlink-line', {
      method: 'POST',
    });
  }
}

export const apiClient = new ApiClient();

export const cardsApi = {
  getCards: () => apiClient.getCards(),
  getCard: (id: string) => apiClient.getCard(id),
  createCard: (data: CreateCardRequest) => apiClient.createCard(data),
  updateCard: (id: string, data: UpdateCardRequest) => apiClient.updateCard(id, data),
  deleteCard: (id: string) => apiClient.deleteCard(id),
  generateCards: (data: GenerateCardsRequest) => apiClient.generateCards(data),
  getDueCards: (limit?: number) => apiClient.getDueCards(limit),
  getDueCount: () => apiClient.getDueCount(),
};

export const reviewsApi = {
  submitReview: (cardId: string, grade: number) => apiClient.submitReview(cardId, grade),
};

export const usersApi = {
  getCurrentUser: () => apiClient.getCurrentUser(),
  updateUser: (data: UpdateUserRequest) => apiClient.updateUser(data),
  linkLine: (data: LinkLineRequest) => apiClient.linkLine(data),
  unlinkLine: () => apiClient.unlinkLine(),
};

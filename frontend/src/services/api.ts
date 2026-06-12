import type {
  Card,
  CreateCardRequest,
  UpdateCardRequest,
  GenerateCardsRequest,
  GenerateCardsResponse,
  GenerateFromUrlRequest,
  GenerateFromUrlResponse,
  RefineCardRequest,
  RefineCardResponse,
  DueCardsResponse,
  ReviewResponse,
  UndoReviewResponse,
  User,
  UpdateUserRequest,
  LinkLineRequest,
  Deck,
  CreateDeckRequest,
  UpdateDeckRequest,
  DeckListResponse,
  StatsResponse,
  WeakCardsResponse,
  ForecastResponse,
  BrowserProfile,
  BrowserProfileListResponse,
  TutorSession,
  StartSessionRequest,
  SendMessageRequest,
  SendMessageResponse,
  SessionListResponse,
} from "@/types";
import { authService } from "./auth";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

/**
 * API エラー応答を構造化して保持する Error。
 * E-3: status / code を捨てずに保持し、呼び出し側がメッセージ文字列に依存せず
 * 業務エラー（4xx + code）と想定外エラー（5xx・ネットワーク等）を判別できるようにする。
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

/** 想定外エラー時にユーザーへ表示する固定文言。 */
export const GENERIC_ERROR_MESSAGE =
  "エラーが発生しました。時間をおいて再度お試しください。";

/**
 * E-1/E-3: ユーザー表示用のエラーメッセージを返す。
 * - ApiError かつ 4xx（業務エラー）: バックエンドのメッセージをそのまま表示
 * - それ以外（5xx・ネットワーク・非 ApiError・status 不明）: 固定文言に差し替え
 *
 * @param fallback 業務エラーにメッセージが無い場合などに使う既定文言（省略時は固定文言）
 */
export function getUserFacingMessage(err: unknown, fallback?: string): string {
  if (err instanceof ApiError && err.status >= 400 && err.status < 500) {
    return err.message || fallback || GENERIC_ERROR_MESSAGE;
  }
  return fallback ?? GENERIC_ERROR_MESSAGE;
}

class ApiClient {
  private accessToken: string | null = null;
  private isRefreshing = false;
  private refreshPromise: Promise<void> | null = null;

  setAccessToken(token: string | null) {
    this.accessToken = token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    _isRetry = false,
  ): Promise<T> {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
      ...options.headers,
    };

    if (this.accessToken) {
      (headers as Record<string, string>)["Authorization"] =
        `Bearer ${this.accessToken}`;
    }

    const signal = options.signal ?? AbortSignal.timeout(30_000);

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
      signal,
    });

    // 401 Unauthorized - トークンリフレッシュ処理（リトライは1回のみ）
    if (response.status === 401) {
      if (_isRetry) {
        // リトライ後も 401 - ログイン画面にリダイレクト
        authService.login().catch((e) => {
          console.error("Login redirect failed:", e);
        });
        throw new Error("Session expired");
      }

      if (!this.isRefreshing) {
        this.isRefreshing = true;
        this.refreshPromise = this.refreshToken().finally(() => {
          this.isRefreshing = false;
          this.refreshPromise = null;
        });
      }
      try {
        await this.refreshPromise;
        // リフレッシュ成功後に元のリクエストを再実行（_isRetry=true で再帰を1回に制限）
        return this.request<T>(endpoint, options, true);
      } catch {
        // リフレッシュ失敗 - ログイン画面にリダイレクト
        authService.login().catch((e) => {
          console.error("Login redirect failed:", e);
        });
        throw new Error("Session expired");
      }
    }

    if (!response.ok) {
      const error = await response
        .json()
        .catch(() => ({ message: "Unknown error" }));
      // E-3: status/code を保持した ApiError を throw（message は従来互換）
      throw new ApiError(
        error.error || error.message || `HTTP ${response.status}`,
        response.status,
        typeof error.code === "string" ? error.code : undefined,
      );
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
  /**
   * 【機能概要】: カード一覧を取得する（オプションで deck_id フィルタ対応）
   * 【実装方針】: getDueCards と同様に URLSearchParams でクエリ文字列を構築する
   * 【テスト対応】: TC-091-001, TC-091-002
   * 🔵 青信号: architecture.md セクション6・既存 getDueCards 実装パターンに基づく
   * @param deckId - フィルタするデッキID（省略時は全カード取得）
   */
  async getCards(
    deckId?: string,
    options?: { signal?: AbortSignal },
  ): Promise<Card[]> {
    // 【クエリ文字列構築】: deckId が指定された場合のみ deck_id パラメータを追加
    const searchParams = new URLSearchParams();
    if (deckId) searchParams.set("deck_id", deckId);
    const qs = searchParams.toString();
    // F-3: signal を fetch まで伝播し、古いリクエストを実際にキャンセルする
    const response = await this.request<{ cards: Card[] }>(
      `/cards${qs ? `?${qs}` : ""}`,
      { signal: options?.signal },
    );
    return response.cards;
  }

  async getCard(id: string): Promise<Card> {
    return this.request<Card>(`/cards/${encodeURIComponent(id)}`);
  }

  async createCard(data: CreateCardRequest): Promise<Card> {
    return this.request<Card>("/cards", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateCard(id: string, data: UpdateCardRequest): Promise<Card> {
    return this.request<Card>(`/cards/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async deleteCard(id: string): Promise<void> {
    await this.request<void>(`/cards/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  }

  async generateCards(
    data: GenerateCardsRequest,
    options?: { signal?: AbortSignal },
  ): Promise<GenerateCardsResponse> {
    return this.request<GenerateCardsResponse>("/cards/generate", {
      method: "POST",
      body: JSON.stringify(data),
      signal: options?.signal,
    });
  }

  async generateFromUrl(data: GenerateFromUrlRequest, options?: { signal?: AbortSignal }): Promise<GenerateFromUrlResponse> {
    return this.request<GenerateFromUrlResponse>('/cards/generate-from-url', {
      method: 'POST',
      body: JSON.stringify(data),
      signal: options?.signal,
    });
  }

  async refineCard(
    data: RefineCardRequest,
    options?: { signal?: AbortSignal },
  ): Promise<RefineCardResponse> {
    return this.request<RefineCardResponse>("/cards/refine", {
      method: "POST",
      body: JSON.stringify(data),
      signal: options?.signal,
    });
  }

  async getDueCards(
    limit?: number,
    deckId?: string,
    options?: { signal?: AbortSignal },
  ): Promise<DueCardsResponse> {
    const searchParams = new URLSearchParams();
    if (limit) searchParams.set("limit", String(limit));
    if (deckId) searchParams.set("deck_id", deckId);
    const qs = searchParams.toString();
    // F-3: signal を fetch まで伝播し、古いリクエストを実際にキャンセルする
    return this.request<DueCardsResponse>(`/cards/due${qs ? `?${qs}` : ""}`, {
      signal: options?.signal,
    });
  }

  async getDueCount(): Promise<number> {
    const response = await this.getDueCards(1);
    return response.total_due_count;
  }

  // レビュー API
  async submitReview(cardId: string, grade: number): Promise<ReviewResponse> {
    return this.request<ReviewResponse>(`/reviews/${encodeURIComponent(cardId)}`, {
      method: "POST",
      body: JSON.stringify({ grade }),
    });
  }

  async undoReview(cardId: string): Promise<UndoReviewResponse> {
    return this.request<UndoReviewResponse>(`/reviews/${encodeURIComponent(cardId)}/undo`, {
      method: "POST",
    });
  }

  // ユーザー API
  async getCurrentUser(): Promise<User> {
    return this.request<User>("/users/me");
  }

  async updateUser(data: UpdateUserRequest): Promise<User> {
    const response = await this.request<{ success: boolean; data: User }>("/users/me/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    });
    return response.data;
  }

  async linkLine(data: LinkLineRequest): Promise<User> {
    const response = await this.request<{ success: boolean; data: User }>("/users/link-line", {
      method: "POST",
      body: JSON.stringify(data),
    });
    return response.data;
  }

  async unlinkLine(): Promise<User> {
    const response = await this.request<{ success: boolean; data: User }>("/users/me/unlink-line", {
      method: "POST",
    });
    return response.data;
  }

  // デッキ API
  async getDecks(): Promise<Deck[]> {
    const response = await this.request<DeckListResponse>("/decks");
    return response.decks;
  }

  async createDeck(data: CreateDeckRequest): Promise<Deck> {
    return this.request<Deck>("/decks", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async updateDeck(id: string, data: UpdateDeckRequest): Promise<Deck> {
    return this.request<Deck>(`/decks/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(data),
    });
  }

  async deleteDeck(id: string): Promise<void> {
    await this.request<void>(`/decks/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  }

  // 統計 API
  async getStats(): Promise<StatsResponse> {
    return this.request<StatsResponse>("/stats");
  }

  async getWeakCards(limit?: number): Promise<WeakCardsResponse> {
    const searchParams = new URLSearchParams();
    if (limit) searchParams.set("limit", String(limit));
    const qs = searchParams.toString();
    return this.request<WeakCardsResponse>(
      `/stats/weak-cards${qs ? `?${qs}` : ""}`,
    );
  }

  async getForecast(days?: number): Promise<ForecastResponse> {
    const searchParams = new URLSearchParams();
    if (days) searchParams.set("days", String(days));
    const qs = searchParams.toString();
    return this.request<ForecastResponse>(
      `/stats/forecast${qs ? `?${qs}` : ""}`,
    );
  }

  // Tutor API
  async startTutorSession(data: StartSessionRequest): Promise<TutorSession> {
    return this.request<TutorSession>("/tutor/sessions", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  async sendTutorMessage(
    sessionId: string,
    data: SendMessageRequest,
  ): Promise<SendMessageResponse> {
    return this.request<SendMessageResponse>(
      `/tutor/sessions/${encodeURIComponent(sessionId)}/messages`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    );
  }

  async endTutorSession(sessionId: string): Promise<TutorSession> {
    return this.request<TutorSession>(
      `/tutor/sessions/${encodeURIComponent(sessionId)}`,
      {
        method: "DELETE",
      },
    );
  }

  async listTutorSessions(
    status?: string,
    deckId?: string,
  ): Promise<SessionListResponse> {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (deckId) params.set("deck_id", deckId);
    const qs = params.toString();
    return this.request<SessionListResponse>(
      `/tutor/sessions${qs ? `?${qs}` : ""}`,
    );
  }

  async getTutorSession(sessionId: string): Promise<TutorSession> {
    return this.request<TutorSession>(
      `/tutor/sessions/${encodeURIComponent(sessionId)}`,
    );
  }

  // Browser Profile API
  async getBrowserProfiles(): Promise<BrowserProfile[]> {
    const response = await this.request<BrowserProfileListResponse>('/browser-profiles');
    return response.profiles;
  }

  async createBrowserProfile(name: string): Promise<BrowserProfile> {
    return this.request<BrowserProfile>('/browser-profiles', {
      method: 'POST',
      body: JSON.stringify({ name }),
    });
  }

  async deleteBrowserProfile(profileId: string): Promise<void> {
    await this.request<void>(`/browser-profiles/${encodeURIComponent(profileId)}`, {
      method: 'DELETE',
    });
  }
}

export const apiClient = new ApiClient();
export * from "./tutor-api";

export const cardsApi = {
  // 【deckId 対応】: deckId パラメータを API クライアントに転送 🔵
  getCards: (deckId?: string, options?: { signal?: AbortSignal }) =>
    apiClient.getCards(deckId, options),
  getCard: (id: string) => apiClient.getCard(id),
  createCard: (data: CreateCardRequest) => apiClient.createCard(data),
  updateCard: (id: string, data: UpdateCardRequest) =>
    apiClient.updateCard(id, data),
  deleteCard: (id: string) => apiClient.deleteCard(id),
  generateCards: (data: GenerateCardsRequest, options?: { signal?: AbortSignal }) => apiClient.generateCards(data, options),
  generateFromUrl: (data: GenerateFromUrlRequest, options?: { signal?: AbortSignal }) => apiClient.generateFromUrl(data, options),
  refineCard: (data: RefineCardRequest, options?: { signal?: AbortSignal }) => apiClient.refineCard(data, options),
  getDueCards: (limit?: number, deckId?: string, options?: { signal?: AbortSignal }) =>
    apiClient.getDueCards(limit, deckId, options),
  getDueCount: () => apiClient.getDueCount(),
};

export const decksApi = {
  getDecks: () => apiClient.getDecks(),
  createDeck: (data: CreateDeckRequest) => apiClient.createDeck(data),
  updateDeck: (id: string, data: UpdateDeckRequest) =>
    apiClient.updateDeck(id, data),
  deleteDeck: (id: string) => apiClient.deleteDeck(id),
};

export const reviewsApi = {
  submitReview: (cardId: string, grade: number) =>
    apiClient.submitReview(cardId, grade),
  undoReview: (cardId: string) => apiClient.undoReview(cardId),
};

export const usersApi = {
  getCurrentUser: () => apiClient.getCurrentUser(),
  updateUser: (data: UpdateUserRequest) => apiClient.updateUser(data),
  linkLine: (data: LinkLineRequest) => apiClient.linkLine(data),
  unlinkLine: () => apiClient.unlinkLine(),
};

export const statsApi = {
  getStats: () => apiClient.getStats(),
  getWeakCards: (limit?: number) => apiClient.getWeakCards(limit),
  getForecast: (days?: number) => apiClient.getForecast(days),
};

export const browserProfilesApi = {
  getProfiles: () => apiClient.getBrowserProfiles(),
  createProfile: (name: string) => apiClient.createBrowserProfile(name),
  deleteProfile: (profileId: string) => apiClient.deleteBrowserProfile(profileId),
};

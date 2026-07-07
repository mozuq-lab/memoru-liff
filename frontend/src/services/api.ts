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
import { TUTOR_AI_TIMEOUT_MS } from "@/constants/tutor";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

/**
 * M-37: getCards の全ページ取得ループに対するタイムアウト上限（ミリ秒）。
 * request() の 1 リクエストあたり 30 秒タイムアウトとは別に、ループ全体が
 * 無限にハングしないよう 1 本の合成シグナルで全ページを縛る。
 */
const GET_CARDS_LOOP_TIMEOUT_MS = 60_000;

/**
 * クエリパラメータからクエリ文字列を構築する。
 * undefined / null / 空文字の値はスキップする。
 * パラメータが 1 件以上ある場合のみ先頭に "?" を付与し、無ければ空文字を返す。
 */
export function buildQueryString(
  params: Record<string, string | number | undefined | null>,
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

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

/** request() の 1 リクエストあたり既定タイムアウト（ミリ秒）。 */
export const DEFAULT_REQUEST_TIMEOUT_MS = 30_000;

/**
 * 外部の中断用 signal とタイムアウトを常に合成した AbortSignal を生成する。
 *
 * 従来は `options.signal ?? AbortSignal.timeout(...)` としていたため、呼び出し側が
 * 中断専用の signal（タイマーなし）を渡すと既定タイムアウトが完全に無効化されていた。
 * 本ヘルパーは外部 signal の有無に関わらずタイムアウトを必ず適用する。
 *
 * LIFF は LINE アプリ内 WebView（iOS WKWebView）で動作し、iOS 17.4 未満では
 * AbortSignal.any が未実装のため、その場合は AbortController + 'abort' リスナー +
 * setTimeout による手動合成にフォールバックする。手動合成ではリスナーとタイマーが
 * リークしないよう、リクエスト完了後に必ず cleanup() を呼ぶこと。
 *
 * abort reason はタイムアウト起因では TimeoutError（AbortSignal.timeout と同一）、
 * 外部起因では外部 signal の reason（既定 AbortError）を維持し、呼び出し側の
 * エラー分類（AbortError / TimeoutError の判別）を変えない。
 */
export function createRequestSignal(
  timeoutMs: number,
  externalSignal?: AbortSignal | null,
): { signal: AbortSignal; cleanup: () => void } {
  const noop = () => {};

  if (typeof AbortSignal.any === "function") {
    const timeoutSignal = AbortSignal.timeout(timeoutMs);
    return {
      signal: externalSignal
        ? AbortSignal.any([externalSignal, timeoutSignal])
        : timeoutSignal,
      cleanup: noop,
    };
  }

  // 【フォールバック】: AbortSignal.any 未実装環境（iOS 17.4 未満の WKWebView 等）向けの手動合成
  const controller = new AbortController();

  if (externalSignal?.aborted) {
    controller.abort(externalSignal.reason);
    return { signal: controller.signal, cleanup: noop };
  }

  const onExternalAbort = () => controller.abort(externalSignal?.reason);
  externalSignal?.addEventListener("abort", onExternalAbort);
  const timerId = setTimeout(() => {
    controller.abort(
      new DOMException("The operation timed out.", "TimeoutError"),
    );
  }, timeoutMs);

  return {
    signal: controller.signal,
    cleanup: () => {
      clearTimeout(timerId);
      externalSignal?.removeEventListener("abort", onExternalAbort);
    },
  };
}

/**
 * L-30: セッション切れでログイン画面へリダイレクトしようとして失敗した際に
 * 発火するグローバルイベント名。
 * signinRedirect の失敗（リダイレクト URL 設定ミス等）がサイレントな
 * console.error で終わると、ユーザーは「セッション切れ」エラーだけ受け取って
 * ログイン画面に遷移できず操作不能になる。アプリ層はこのイベントを購読して
 * UI でログイン誘導やエラー表示を行うこと。
 */
export const LOGIN_REDIRECT_FAILED_EVENT = "memoru:login-redirect-failed";

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

  /**
   * L-30: セッション切れ時にログイン画面へリダイレクトする。
   * signinRedirect は通常ブラウザ遷移を起こして戻ってこないが、リダイレクト
   * 自体が失敗するケース（設定ミス等）では Promise が reject する。その失敗を
   * console.error だけで握りつぶすとユーザーが操作不能のまま放置されるため、
   * グローバルイベントを発火してアプリ層が UI で対処できるようにする。
   */
  private redirectToLogin(): void {
    authService.login().catch((e) => {
      console.error("Login redirect failed:", e);
      if (typeof window !== "undefined") {
        window.dispatchEvent(
          new CustomEvent(LOGIN_REDIRECT_FAILED_EVENT, { detail: e }),
        );
      }
    });
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit & { timeoutMs?: number } = {},
    _isRetry = false,
  ): Promise<T> {
    const { timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS, ...init } = options;

    const headers: HeadersInit = {
      "Content-Type": "application/json",
      ...init.headers,
    };

    if (this.accessToken) {
      (headers as Record<string, string>)["Authorization"] =
        `Bearer ${this.accessToken}`;
    }

    // 外部 signal（中断用）とタイムアウトを常に合成する。
    // 外部 signal を渡してもタイムアウトが無効化されない（H-1 修正）。
    const { signal, cleanup } = createRequestSignal(timeoutMs, init.signal);

    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...init,
        headers,
        signal,
      });

      // 401 Unauthorized - トークンリフレッシュ処理（リトライは1回のみ）
      if (response.status === 401) {
        if (_isRetry) {
          // リトライ後も 401 - ログイン画面にリダイレクト
          this.redirectToLogin();
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
        } catch {
          // リフレッシュ失敗 - ログイン画面にリダイレクト
          this.redirectToLogin();
          throw new Error("Session expired");
        }
        // リフレッシュ成功後に元のリクエストを再実行（_isRetry=true で再帰を1回に制限）
        return await this.request<T>(endpoint, options, true);
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
      return await response.json();
    } finally {
      // フォールバック合成時のリスナー・タイマーをリークさせない
      cleanup();
    }
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
    const cards: Card[] = [];
    let cursor: string | undefined;

    // M-37: request() はページごとに新しい 30 秒タイムアウトを張るため、
    // ループ全体に対するタイムアウト上限を 1 本だけ用意し、全ページに渡す。
    // 外部 signal は createRequestSignal で合成する（AbortSignal.any 未実装環境でも動作）。
    const { signal: loopSignal, cleanup } = createRequestSignal(
      GET_CARDS_LOOP_TIMEOUT_MS,
      options?.signal,
    );

    try {
      do {
        const qs = buildQueryString({ limit: 100, deck_id: deckId, cursor });

        // The cards screen performs client-side search and sorting, so it needs
        // every page rather than silently limiting the visible collection.
        const response = await this.request<{
          cards: Card[];
          next_cursor?: string | null;
        }>(`/cards${qs}`, {
          signal: loopSignal,
        });
        cards.push(...response.cards);
        cursor = response.next_cursor ?? undefined;
      } while (cursor);

      return cards;
    } finally {
      cleanup();
    }
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
    options?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<GenerateCardsResponse> {
    return this.request<GenerateCardsResponse>("/cards/generate", {
      method: "POST",
      body: JSON.stringify(data),
      signal: options?.signal,
      timeoutMs: options?.timeoutMs,
    });
  }

  async generateFromUrl(data: GenerateFromUrlRequest, options?: { signal?: AbortSignal; timeoutMs?: number }): Promise<GenerateFromUrlResponse> {
    return this.request<GenerateFromUrlResponse>('/cards/generate-from-url', {
      method: 'POST',
      body: JSON.stringify(data),
      signal: options?.signal,
      timeoutMs: options?.timeoutMs,
    });
  }

  async refineCard(
    data: RefineCardRequest,
    options?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<RefineCardResponse> {
    return this.request<RefineCardResponse>("/cards/refine", {
      method: "POST",
      body: JSON.stringify(data),
      signal: options?.signal,
      timeoutMs: options?.timeoutMs,
    });
  }

  async getDueCards(
    limit?: number,
    deckId?: string,
    options?: { signal?: AbortSignal },
  ): Promise<DueCardsResponse> {
    const qs = buildQueryString({ limit, deck_id: deckId });
    // F-3: signal を fetch まで伝播し、古いリクエストを実際にキャンセルする
    return this.request<DueCardsResponse>(`/cards/due${qs}`, {
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
    const qs = buildQueryString({ limit });
    return this.request<WeakCardsResponse>(`/stats/weak-cards${qs}`);
  }

  async getForecast(days?: number): Promise<ForecastResponse> {
    const qs = buildQueryString({ days });
    return this.request<ForecastResponse>(`/stats/forecast${qs}`);
  }

  // Tutor API
  // start / sendMessage は AI 生成（あいさつ・応答）を伴い遅いため、request() の既定
  // 30 秒ではなく TUTOR_AI_TIMEOUT_MS を使う。ローカル LLM で生成が 30 秒を超えると
  // フロントが先に abort し「セッションの開始に失敗しました」になる問題への対処。
  async startTutorSession(data: StartSessionRequest): Promise<TutorSession> {
    return this.request<TutorSession>("/tutor/sessions", {
      method: "POST",
      body: JSON.stringify(data),
      timeoutMs: TUTOR_AI_TIMEOUT_MS,
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
        timeoutMs: TUTOR_AI_TIMEOUT_MS,
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
    const qs = buildQueryString({ status, deck_id: deckId });
    return this.request<SessionListResponse>(`/tutor/sessions${qs}`);
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
  generateCards: (data: GenerateCardsRequest, options?: { signal?: AbortSignal; timeoutMs?: number }) => apiClient.generateCards(data, options),
  generateFromUrl: (data: GenerateFromUrlRequest, options?: { signal?: AbortSignal; timeoutMs?: number }) => apiClient.generateFromUrl(data, options),
  refineCard: (data: RefineCardRequest, options?: { signal?: AbortSignal; timeoutMs?: number }) => apiClient.refineCard(data, options),
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

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// 【テスト目的】: AI 非同期ジョブ基盤（submitAndPollAiJob + AI 系 API メソッドの 202 経路）の検証
// 【対応設計】: docs/design/ai-async-jobs/dataflow.md「フロントエンドのフロー（サービス層内部）」
//   - 2xx + job_id なし → 旧同期形式としてそのまま返す（200/201 両方。ステータス数値に依存しない）
//   - 2xx + job_id あり → GET /ai-jobs/{id} をポーリングし completed の result を返す
//   - failed → error.status / message / code から ApiError を組み立てて throw
//   - 全体デッドライン超過 → TimeoutError / 外部 signal abort → AbortError を伝播
//   - 待機中の setTimeout は abort 時に確実にクリーンアップ（タイマーリークなし）

const JSON_HEADERS = { 'Content-Type': 'application/json' };

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });

describe('submitAndPollAiJob', () => {
  let mockFetch: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com');
    mockFetch = vi.fn();
    (globalThis as Record<string, unknown>).fetch = mockFetch;
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  describe('(a) 旧同期形式（2xx + job_id なし）の互換', () => {
    it('200 + job_id なしのボディはポーリングせずそのまま返す', async () => {
      const { apiClient } = await import('@/services/api');
      const body = { generated_cards: [{ front: 'Q', back: 'A', suggested_tags: [] }] };
      const submit = vi.fn().mockResolvedValue({ status: 200, body });

      const result = await apiClient.submitAndPollAiJob(submit, {});

      // 【検証項目】: 旧同期形式のボディがそのまま返り、GET /ai-jobs は呼ばれない
      expect(result).toEqual(body);
      expect(submit).toHaveBeenCalledTimes(1);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('201 + job_id なしのボディも旧形式として安全に判定される（ステータス数値に依存しない）', async () => {
      const { apiClient } = await import('@/services/api');
      // tutor_start の現行 201 レスポンスを想定
      const body = { session_id: 's1', status: 'active' };
      const submit = vi.fn().mockResolvedValue({ status: 201, body });

      const result = await apiClient.submitAndPollAiJob(submit, {});

      expect(result).toEqual(body);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('submit には合成デッドライン signal と全体タイムアウト(ms)が渡される', async () => {
      const { apiClient } = await import('@/services/api');
      const submit = vi.fn().mockResolvedValue({ status: 200, body: {} });

      await apiClient.submitAndPollAiJob(submit, { timeoutMs: 45_000 });

      // 【検証項目】: 旧バックエンド（同期 AI 実行）でも request() の既定 30 秒に
      // 切られないよう、submit へ全体予算が伝わること
      expect(submit).toHaveBeenCalledWith(expect.any(AbortSignal), 45_000);
    });

    it('timeoutMs 未指定時は既定タイムアウトが submit に渡される', async () => {
      const { apiClient, DEFAULT_REQUEST_TIMEOUT_MS } = await import('@/services/api');
      const submit = vi.fn().mockResolvedValue({ status: 200, body: {} });

      await apiClient.submitAndPollAiJob(submit, {});

      expect(submit).toHaveBeenCalledWith(
        expect.any(AbortSignal),
        DEFAULT_REQUEST_TIMEOUT_MS,
      );
    });
  });

  // ポーリング経路は待機 1.5 秒を決定的に進めるため fake timers を使う。
  // AbortSignal.timeout は vi のフェイクタイマーに乗らないため、既存テストと同様に
  // AbortSignal.any を無効化して createRequestSignal の手動合成（setTimeout ベース）
  // フォールバックを通す（iOS 17.4 未満 WKWebView 相当のパスも同時に検証される）。
  describe('ポーリング経路（fake timers + 手動合成フォールバック）', () => {
    let originalAny: typeof AbortSignal.any;

    beforeEach(() => {
      originalAny = AbortSignal.any;
      // @ts-expect-error AbortSignal.any 未実装環境をシミュレート
      AbortSignal.any = undefined;
      vi.useFakeTimers();
    });

    afterEach(() => {
      AbortSignal.any = originalAny;
      vi.useRealTimers();
    });

    it('(b) 202 + job_id → 1.5 秒後に GET /ai-jobs/{id} し completed の result を返す', async () => {
      const { apiClient } = await import('@/services/api');
      const resultBody = { generated_cards: [{ front: 'Q', back: 'A', suggested_tags: [] }] };
      mockFetch.mockResolvedValue(
        jsonResponse({
          job_id: 'aijob_1',
          job_type: 'generate',
          status: 'completed',
          result: resultBody,
          created_at: '2026-07-07T00:00:00+00:00',
          updated_at: '2026-07-07T00:00:02+00:00',
        }),
      );
      const submit = vi.fn().mockResolvedValue({
        status: 202,
        body: { job_id: 'aijob_1', job_type: 'generate', status: 'queued' },
      });

      const promise = apiClient.submitAndPollAiJob(submit, { timeoutMs: 45_000 });
      await vi.advanceTimersByTimeAsync(1_500);

      // 【検証項目】: completed の result がそのまま返り、GET は正しい URL で 1 回だけ
      await expect(promise).resolves.toEqual(resultBody);
      expect(mockFetch).toHaveBeenCalledTimes(1);
      expect(mockFetch).toHaveBeenCalledWith(
        'https://api.example.com/ai-jobs/aijob_1',
        expect.any(Object),
      );
    });

    it('(c) failed → error.status/message/code から ApiError が組み立てられて throw される', async () => {
      const { apiClient, ApiError } = await import('@/services/api');
      mockFetch.mockResolvedValue(
        jsonResponse({
          job_id: 'aijob_2',
          job_type: 'refine',
          status: 'failed',
          error: { status: 504, code: 'ai_timeout', message: 'AI service timeout' },
          created_at: '2026-07-07T00:00:00+00:00',
          updated_at: '2026-07-07T00:00:02+00:00',
        }),
      );
      const submit = vi.fn().mockResolvedValue({
        status: 202,
        body: { job_id: 'aijob_2', job_type: 'refine', status: 'queued' },
      });

      const promise = apiClient
        .submitAndPollAiJob(submit, { timeoutMs: 45_000 })
        .catch((e: unknown) => e);
      await vi.advanceTimersByTimeAsync(1_500);
      const err = await promise;

      // 【検証項目】: 既存のエラー分類（ApiError.status 分岐）がそのまま機能する形で throw される
      expect(err).toBeInstanceOf(ApiError);
      const apiErr = err as InstanceType<typeof ApiError>;
      expect(apiErr.status).toBe(504);
      expect(apiErr.message).toBe('AI service timeout');
      expect(apiErr.code).toBe('ai_timeout');
    });

    it('(d) 全体タイムアウト超過で TimeoutError として打ち切られる', async () => {
      const { apiClient } = await import('@/services/api');
      // ずっと queued のままのジョブ
      mockFetch.mockImplementation(() =>
        Promise.resolve(
          jsonResponse({
            job_id: 'aijob_3',
            job_type: 'generate',
            status: 'queued',
            created_at: '2026-07-07T00:00:00+00:00',
            updated_at: '2026-07-07T00:00:00+00:00',
          }),
        ),
      );
      const submit = vi.fn().mockResolvedValue({
        status: 202,
        body: { job_id: 'aijob_3', job_type: 'generate', status: 'queued' },
      });

      const promise = apiClient
        .submitAndPollAiJob(submit, { timeoutMs: 5_000 })
        .catch((e: unknown) => e);
      // 1.5s ごとのポーリングを 2 回消化した後、t=5s で全体デッドラインが発火する
      await vi.advanceTimersByTimeAsync(5_000);
      const err = await promise;

      // 【検証項目】: 既存の TimeoutError 分類がそのまま機能する
      expect((err as DOMException).name).toBe('TimeoutError');
    });

    it('(e) 外部 signal の abort で停止し、待機タイマーがリークしない', async () => {
      const { apiClient } = await import('@/services/api');
      const submit = vi.fn().mockResolvedValue({
        status: 202,
        body: { job_id: 'aijob_4', job_type: 'generate', status: 'queued' },
      });
      const external = new AbortController();

      const promise = apiClient
        .submitAndPollAiJob(submit, { timeoutMs: 45_000, signal: external.signal })
        .catch((e: unknown) => e);

      // submit 解決後、ポーリング待機タイマー + 全体デッドラインタイマーが張られている
      await vi.advanceTimersByTimeAsync(0);
      expect(vi.getTimerCount()).toBeGreaterThan(0);

      external.abort();
      const err = await promise;

      // 【検証項目】: AbortError として伝播し、setTimeout がすべてクリーンアップされる
      expect((err as DOMException).name).toBe('AbortError');
      expect(vi.getTimerCount()).toBe(0);
      expect(mockFetch).not.toHaveBeenCalled();
    });

    it('(f) queued → processing → completed の遷移を継続ポーリングして result を返す', async () => {
      const { apiClient } = await import('@/services/api');
      const resultBody = { refined_back: 'improved' };
      const jobBase = {
        job_id: 'aijob_5',
        job_type: 'refine',
        created_at: '2026-07-07T00:00:00+00:00',
        updated_at: '2026-07-07T00:00:00+00:00',
      };
      mockFetch
        .mockResolvedValueOnce(jsonResponse({ ...jobBase, status: 'queued' }))
        .mockResolvedValueOnce(jsonResponse({ ...jobBase, status: 'processing' }))
        .mockResolvedValueOnce(
          jsonResponse({ ...jobBase, status: 'completed', result: resultBody }),
        );
      const submit = vi.fn().mockResolvedValue({
        status: 202,
        body: { job_id: 'aijob_5', job_type: 'refine', status: 'queued' },
      });

      const promise = apiClient.submitAndPollAiJob(submit, { timeoutMs: 45_000 });
      await vi.advanceTimersByTimeAsync(1_500); // → queued
      await vi.advanceTimersByTimeAsync(1_500); // → processing
      await vi.advanceTimersByTimeAsync(1_500); // → completed

      await expect(promise).resolves.toEqual(resultBody);
      expect(mockFetch).toHaveBeenCalledTimes(3);
    });

    it('pollIntervalMs を指定するとその間隔でポーリングする', async () => {
      const { apiClient } = await import('@/services/api');
      mockFetch.mockResolvedValue(
        jsonResponse({
          job_id: 'aijob_6',
          job_type: 'generate',
          status: 'completed',
          result: { ok: true },
          created_at: '2026-07-07T00:00:00+00:00',
          updated_at: '2026-07-07T00:00:01+00:00',
        }),
      );
      const submit = vi.fn().mockResolvedValue({
        status: 202,
        body: { job_id: 'aijob_6', job_type: 'generate', status: 'queued' },
      });

      const promise = apiClient.submitAndPollAiJob(submit, {
        timeoutMs: 45_000,
        pollIntervalMs: 500,
      });
      // 既定 1.5 秒より短い 500ms で最初の GET が発火する
      await vi.advanceTimersByTimeAsync(500);

      await expect(promise).resolves.toEqual({ ok: true });
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });
  });
});

describe('AI 系 API メソッドの 202 経路', () => {
  let mockFetch: ReturnType<typeof vi.fn>;
  let originalAny: typeof AbortSignal.any;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com');
    mockFetch = vi.fn();
    (globalThis as Record<string, unknown>).fetch = mockFetch;
    originalAny = AbortSignal.any;
    // @ts-expect-error AbortSignal.any 未実装環境をシミュレート（fake timers でポーリングを進めるため）
    AbortSignal.any = undefined;
    vi.useFakeTimers();
  });

  afterEach(() => {
    AbortSignal.any = originalAny;
    vi.useRealTimers();
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  /** POST（submit）→ 202、GET /ai-jobs/{id} → job レスポンス、の URL ルーティングモック */
  const routeFetch = (submitPath: string, submitBody: unknown, jobBody: unknown) => {
    mockFetch.mockImplementation((url: string) => {
      if (url.includes('/ai-jobs/')) {
        return Promise.resolve(jsonResponse(jobBody));
      }
      if (url.endsWith(submitPath)) {
        return Promise.resolve(jsonResponse(submitBody, 202));
      }
      return Promise.reject(new Error(`Unexpected URL: ${url}`));
    });
  };

  it('generateCards: 202 + job_id → ポーリングして completed の result を返す', async () => {
    const { apiClient } = await import('@/services/api');
    const resultBody = { generated_cards: [{ front: 'Q', back: 'A', suggested_tags: [] }] };
    routeFetch(
      '/cards/generate',
      { job_id: 'aijob_g1', job_type: 'generate', status: 'queued' },
      {
        job_id: 'aijob_g1',
        job_type: 'generate',
        status: 'completed',
        result: resultBody,
        created_at: '2026-07-07T00:00:00+00:00',
        updated_at: '2026-07-07T00:00:02+00:00',
      },
    );

    const promise = apiClient.generateCards(
      { input_text: 'テスト用の入力テキスト', card_count: 3, language: 'ja' },
      { timeoutMs: 45_000 },
    );
    await vi.advanceTimersByTimeAsync(1_500);

    await expect(promise).resolves.toEqual(resultBody);
    // 【検証項目】: submit → poll の順で正しい URL が呼ばれる
    expect(mockFetch).toHaveBeenNthCalledWith(
      1,
      'https://api.example.com/cards/generate',
      expect.objectContaining({ method: 'POST' }),
    );
    expect(mockFetch).toHaveBeenNthCalledWith(
      2,
      'https://api.example.com/ai-jobs/aijob_g1',
      expect.any(Object),
    );
  });

  it('generateFromUrl: 202 + job_id → completed の result（page_info 含む）を返す', async () => {
    const { apiClient } = await import('@/services/api');
    const resultBody = {
      generated_cards: [{ front: 'Q', back: 'A', suggested_tags: [] }],
      page_info: { url: 'https://example.com', title: 'Example' },
    };
    routeFetch(
      '/cards/generate-from-url',
      { job_id: 'aijob_u1', job_type: 'generate_from_url', status: 'queued' },
      {
        job_id: 'aijob_u1',
        job_type: 'generate_from_url',
        status: 'completed',
        result: resultBody,
        created_at: '2026-07-07T00:00:00+00:00',
        updated_at: '2026-07-07T00:01:00+00:00',
      },
    );

    const promise = apiClient.generateFromUrl(
      {
        url: 'https://example.com',
        card_type: 'qa',
        target_count: 10,
        difficulty: 'medium',
        language: 'ja',
      },
      { timeoutMs: 90_000 },
    );
    await vi.advanceTimersByTimeAsync(1_500);

    await expect(promise).resolves.toEqual(resultBody);
  });

  it('refineCard: failed ジョブは ApiError(status/message) として throw される', async () => {
    const { apiClient, ApiError } = await import('@/services/api');
    routeFetch(
      '/cards/refine',
      { job_id: 'aijob_r1', job_type: 'refine', status: 'queued' },
      {
        job_id: 'aijob_r1',
        job_type: 'refine',
        status: 'failed',
        error: { status: 429, code: 'ai_rate_limit', message: 'AI service rate limit exceeded' },
        created_at: '2026-07-07T00:00:00+00:00',
        updated_at: '2026-07-07T00:00:02+00:00',
      },
    );

    const promise = apiClient
      .refineCard({ front: 'Q', back: 'A' }, { timeoutMs: 45_000 })
      .catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(1_500);
    const err = await promise;

    expect(err).toBeInstanceOf(ApiError);
    const apiErr = err as InstanceType<typeof ApiError>;
    expect(apiErr.status).toBe(429);
    expect(apiErr.message).toBe('AI service rate limit exceeded');
  });

  it('startTutorSession: 旧同期形式（201 + job_id なし）はポーリングせずそのまま返す', async () => {
    const { apiClient } = await import('@/services/api');
    const session = { session_id: 's1', status: 'active', deck_id: 'd1' };
    mockFetch.mockResolvedValue(jsonResponse(session, 201));

    const result = await apiClient.startTutorSession({ deck_id: 'd1', mode: 'free_talk' });

    // 【検証項目】: 旧バックエンド互換（新フロント + 旧バックエンド）で UI が壊れない
    expect(result).toEqual(session);
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('sendTutorMessage: 202 + job_id → completed の result を返す', async () => {
    const { apiClient } = await import('@/services/api');
    const resultBody = {
      message: { role: 'assistant', content: 'こんにちは' },
      session_id: 's1',
      message_count: 1,
      is_limit_reached: false,
    };
    routeFetch(
      '/tutor/sessions/s1/messages',
      { job_id: 'aijob_t1', job_type: 'tutor_message', status: 'queued' },
      {
        job_id: 'aijob_t1',
        job_type: 'tutor_message',
        status: 'completed',
        result: resultBody,
        created_at: '2026-07-07T00:00:00+00:00',
        updated_at: '2026-07-07T00:00:05+00:00',
      },
    );

    const promise = apiClient.sendTutorMessage('s1', { content: 'hi' });
    await vi.advanceTimersByTimeAsync(1_500);

    await expect(promise).resolves.toEqual(resultBody);
  });
});

// 実装レビュー FH-1: ポーリング GET の単発失敗（ネットワーク瞬断・個別タイムアウト・5xx）で
// 全体を落とさず、全体デッドライン内なら次の間隔で再試行することの検証。
describe('ポーリング GET の再試行（実装レビュー FH-1）', () => {
  const JSON_HEADERS = { 'Content-Type': 'application/json' };
  const jsonResponse = (body: unknown, status = 200) =>
    new Response(JSON.stringify(body), { status, headers: JSON_HEADERS });

  let mockFetch: ReturnType<typeof vi.fn>;
  let originalAny: typeof AbortSignal.any;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.resetModules();
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com');
    mockFetch = vi.fn();
    (globalThis as Record<string, unknown>).fetch = mockFetch;
    originalAny = AbortSignal.any;
    // @ts-expect-error AbortSignal.any 未実装環境をシミュレート（fake timers 対応）
    AbortSignal.any = undefined;
    vi.useFakeTimers();
  });

  afterEach(() => {
    AbortSignal.any = originalAny;
    vi.useRealTimers();
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  const completedResponse = (result: unknown) =>
    jsonResponse({
      job_id: 'aijob_1',
      job_type: 'generate',
      status: 'completed',
      result,
      created_at: '2026-07-07T00:00:00+00:00',
      updated_at: '2026-07-07T00:00:02+00:00',
    });

  const submit202 = () =>
    vi.fn().mockResolvedValue({
      status: 202,
      body: { job_id: 'aijob_1', job_type: 'generate', status: 'queued' },
    });

  it('単発のネットワーク失敗では諦めず、次のポーリングで completed を返す', async () => {
    const { apiClient } = await import('@/services/api');
    const resultBody = { generated_cards: [] };
    mockFetch
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(completedResponse(resultBody));

    const promise = apiClient.submitAndPollAiJob(submit202(), { timeoutMs: 45_000 });
    const assertion = expect(promise).resolves.toEqual(resultBody);
    await vi.advanceTimersByTimeAsync(1_500); // 1回目 GET → 失敗（再試行へ）
    await vi.advanceTimersByTimeAsync(1_500); // 2回目 GET → completed
    await assertion;

    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('404（ジョブ不在）は再試行せず即座に失敗する', async () => {
    const { apiClient } = await import('@/services/api');
    mockFetch.mockResolvedValue(jsonResponse({ error: 'Job not found' }, 404));

    const promise = apiClient.submitAndPollAiJob(submit202(), { timeoutMs: 45_000 });
    const assertion = expect(promise).rejects.toMatchObject({ status: 404 });
    await vi.advanceTimersByTimeAsync(1_500);
    await assertion;

    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('連続 MAX_CONSECUTIVE_POLL_FAILURES 回失敗した場合は諦めてエラーを伝播する', async () => {
    const { apiClient, MAX_CONSECUTIVE_POLL_FAILURES } = await import('@/services/api');
    mockFetch.mockRejectedValue(new TypeError('Failed to fetch'));

    const promise = apiClient.submitAndPollAiJob(submit202(), { timeoutMs: 60_000 });
    const assertion = expect(promise).rejects.toBeTruthy();
    for (let i = 0; i < MAX_CONSECUTIVE_POLL_FAILURES; i += 1) {
      await vi.advanceTimersByTimeAsync(1_500);
    }
    await assertion;

    expect(mockFetch).toHaveBeenCalledTimes(MAX_CONSECUTIVE_POLL_FAILURES);
  });

  it('失敗を挟んでも成功でカウンタがリセットされ、その後の単発失敗も許容される', async () => {
    const { apiClient } = await import('@/services/api');
    const resultBody = { ok: true };
    const processing = () =>
      jsonResponse({
        job_id: 'aijob_1',
        job_type: 'generate',
        status: 'processing',
        created_at: '2026-07-07T00:00:00+00:00',
        updated_at: '2026-07-07T00:00:01+00:00',
      });
    mockFetch
      .mockRejectedValueOnce(new TypeError('Failed to fetch')) // 失敗1
      .mockResolvedValueOnce(processing()) // 成功（カウンタリセット）
      .mockRejectedValueOnce(new TypeError('Failed to fetch')) // 失敗2（連続ではない）
      .mockResolvedValueOnce(completedResponse(resultBody));

    const promise = apiClient.submitAndPollAiJob(submit202(), { timeoutMs: 60_000 });
    const assertion = expect(promise).resolves.toEqual(resultBody);
    for (let i = 0; i < 4; i += 1) {
      await vi.advanceTimersByTimeAsync(1_500);
    }
    await assertion;

    expect(mockFetch).toHaveBeenCalledTimes(4);
  });
});

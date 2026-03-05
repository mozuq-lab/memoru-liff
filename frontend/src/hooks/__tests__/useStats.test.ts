/**
 * 【テスト概要】: useStats フックのテスト
 * 【テスト対象】: useStats フック
 * 【テスト対応】: ローディング状態, データ取得成功, エラーハンドリング, リフレッシュ
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';
import { useStats } from '../useStats';
import type { StatsResponse, WeakCardsResponse, ForecastResponse } from '@/types';

// statsApi をモック
vi.mock('@/services/api', () => ({
  statsApi: {
    getStats: vi.fn(),
    getWeakCards: vi.fn(),
    getForecast: vi.fn(),
  },
}));

// モジュールのモックを取得
import { statsApi } from '@/services/api';

const mockStats: StatsResponse = {
  total_cards: 100,
  learned_cards: 60,
  unlearned_cards: 40,
  cards_due_today: 15,
  total_reviews: 500,
  average_grade: 3.2,
  streak_days: 7,
  tag_performance: { math: 0.8, science: 0.6 },
};

const mockWeakCards: WeakCardsResponse = {
  weak_cards: [
    {
      card_id: 'wc-1',
      front: '弱点カード1',
      back: '答え1',
      ease_factor: 1.3,
      repetitions: 2,
      deck_id: null,
    },
    {
      card_id: 'wc-2',
      front: '弱点カード2',
      back: '答え2',
      ease_factor: 1.5,
      repetitions: 1,
      deck_id: 'deck-1',
    },
  ],
  total_count: 2,
};

const mockForecast: ForecastResponse = {
  forecast: [
    { date: '2026-03-05', due_count: 10 },
    { date: '2026-03-06', due_count: 8 },
    { date: '2026-03-07', due_count: 12 },
  ],
};

describe('useStats', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('初期状態で isLoading が true である', () => {
    // API を解決しないまま保持して loading 状態を確認
    vi.mocked(statsApi.getStats).mockReturnValue(new Promise(() => {}));
    vi.mocked(statsApi.getWeakCards).mockReturnValue(new Promise(() => {}));
    vi.mocked(statsApi.getForecast).mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useStats());

    expect(result.current.isLoading).toBe(true);
    expect(result.current.stats).toBeNull();
    expect(result.current.weakCards).toBeNull();
    expect(result.current.forecast).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('データ取得成功時に正しいデータが返る', async () => {
    vi.mocked(statsApi.getStats).mockResolvedValue(mockStats);
    vi.mocked(statsApi.getWeakCards).mockResolvedValue(mockWeakCards);
    vi.mocked(statsApi.getForecast).mockResolvedValue(mockForecast);

    const { result } = renderHook(() => useStats());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.stats).toEqual(mockStats);
    expect(result.current.weakCards).toEqual(mockWeakCards);
    expect(result.current.forecast).toEqual(mockForecast);
    expect(result.current.error).toBeNull();
  });

  it('3つの API が並列で呼び出される', async () => {
    vi.mocked(statsApi.getStats).mockResolvedValue(mockStats);
    vi.mocked(statsApi.getWeakCards).mockResolvedValue(mockWeakCards);
    vi.mocked(statsApi.getForecast).mockResolvedValue(mockForecast);

    renderHook(() => useStats());

    await waitFor(() => {
      expect(statsApi.getStats).toHaveBeenCalledTimes(1);
    });

    expect(statsApi.getWeakCards).toHaveBeenCalledTimes(1);
    expect(statsApi.getForecast).toHaveBeenCalledTimes(1);
  });

  it('エラー時にエラー状態が設定される', async () => {
    const mockError = new Error('API error');
    vi.mocked(statsApi.getStats).mockRejectedValue(mockError);
    vi.mocked(statsApi.getWeakCards).mockResolvedValue(mockWeakCards);
    vi.mocked(statsApi.getForecast).mockResolvedValue(mockForecast);

    const { result } = renderHook(() => useStats());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toEqual(mockError);
    expect(result.current.stats).toBeNull();
    expect(result.current.weakCards).toBeNull();
    expect(result.current.forecast).toBeNull();
  });

  it('refresh() でデータが再取得される', async () => {
    vi.mocked(statsApi.getStats).mockResolvedValue(mockStats);
    vi.mocked(statsApi.getWeakCards).mockResolvedValue(mockWeakCards);
    vi.mocked(statsApi.getForecast).mockResolvedValue(mockForecast);

    const { result } = renderHook(() => useStats());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    // 初回取得で 1 回ずつ呼ばれている
    expect(statsApi.getStats).toHaveBeenCalledTimes(1);

    // 更新データ
    const updatedStats: StatsResponse = {
      ...mockStats,
      total_reviews: 510,
      streak_days: 8,
    };
    vi.mocked(statsApi.getStats).mockResolvedValue(updatedStats);

    await act(async () => {
      await result.current.refresh();
    });

    expect(statsApi.getStats).toHaveBeenCalledTimes(2);
    expect(statsApi.getWeakCards).toHaveBeenCalledTimes(2);
    expect(statsApi.getForecast).toHaveBeenCalledTimes(2);
    expect(result.current.stats).toEqual(updatedStats);
  });

  it('refresh() でエラー後にデータが正常に取得できる', async () => {
    // 初回はエラー
    vi.mocked(statsApi.getStats).mockRejectedValue(new Error('API error'));
    vi.mocked(statsApi.getWeakCards).mockResolvedValue(mockWeakCards);
    vi.mocked(statsApi.getForecast).mockResolvedValue(mockForecast);

    const { result } = renderHook(() => useStats());

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.error).toBeTruthy();

    // リフレッシュで成功
    vi.mocked(statsApi.getStats).mockResolvedValue(mockStats);

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.error).toBeNull();
    expect(result.current.stats).toEqual(mockStats);
    expect(result.current.weakCards).toEqual(mockWeakCards);
    expect(result.current.forecast).toEqual(mockForecast);
  });
});

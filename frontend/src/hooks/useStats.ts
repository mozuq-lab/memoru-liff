/**
 * 【機能概要】: 学習統計データを取得・管理するカスタムフック
 * 【実装方針】: Promise.all で 3 API を並列取得、loading/error/data 状態を管理
 * 【テスト対応】: useStats.test.ts
 * 🔵 信頼性レベル: 要件定義書・architecture.md より
 */
import { useState, useCallback, useEffect } from 'react';
import type { StatsResponse, WeakCardsResponse, ForecastResponse } from '@/types';
import { statsApi } from '@/services/api';

interface UseStatsReturn {
  stats: StatsResponse | null;
  weakCards: WeakCardsResponse | null;
  forecast: ForecastResponse | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

export const useStats = (): UseStatsReturn => {
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const [weakCards, setWeakCards] = useState<WeakCardsResponse | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [statsData, weakCardsData, forecastData] = await Promise.all([
        statsApi.getStats(),
        statsApi.getWeakCards(),
        statsApi.getForecast(),
      ]);
      setStats(statsData);
      setWeakCards(weakCardsData);
      setForecast(forecastData);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  return {
    stats,
    weakCards,
    forecast,
    isLoading,
    error,
    refresh: fetchAll,
  };
};
